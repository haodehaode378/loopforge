"""Read-only evidence bundle export for run audit handoff."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.evidence import file_hash, read_evidence_manifest, relative_to_run, resolve_run_path, stable_hash


BUNDLE_DIRNAME = "evidence_bundle"
BUNDLE_MANIFEST = "bundle_manifest.json"


def export_evidence_bundle(run_dir: Path, run_id: str) -> dict[str, object]:
    run_dir = run_dir.resolve()
    bundle_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    bundle_dir = run_dir / BUNDLE_DIRNAME / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_evidence_manifest(run_dir)
    source_paths = collect_bundle_sources(run_dir, manifest)
    copied = []
    for relative_path, source in source_paths:
        target = bundle_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists() and source.is_file():
            shutil.copy2(source, target)
        copied.append(bundle_file_record(run_dir, bundle_dir, relative_path, source))

    bundle = {
        "version": 1,
        "run_id": run_id,
        "bundle_id": bundle_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "read-only evidence bundle",
        "no_execution_guarantee": "No approve, resume, write, commit, push, or delete action was executed.",
        "source_manifest_status": manifest.get("status", "missing manifest"),
        "source_integrity_status": manifest.get("integrity_status", manifest.get("status", "missing manifest")),
        "source_audit_status": manifest.get("audit_status", "missing audit digest"),
        "files": copied,
    }
    bundle["bundle_hash"] = stable_hash(bundle)
    (bundle_dir / BUNDLE_MANIFEST).write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    zip_path = write_bundle_zip(bundle_dir, run_dir / f"evidence_bundle-{bundle_id}.zip")
    bundle["bundle_dir"] = str(bundle_dir)
    bundle["zip_path"] = str(zip_path)
    bundle["zip_sha256"] = file_hash(zip_path)
    return bundle


def collect_bundle_sources(run_dir: Path, manifest: dict[str, object]) -> list[tuple[str, Path]]:
    sources: dict[str, Path] = {}
    for name in ("goal.json", "events.jsonl", "report.md", "evidence_manifest.json", "approvals.jsonl"):
        path = run_dir / name
        if path.exists():
            sources[name] = path

    artifacts = manifest.get("artifact_hashes", {})
    if isinstance(artifacts, dict):
        for record in artifacts.values():
            if not isinstance(record, dict):
                continue
            path = resolve_run_path(run_dir, record.get("path", ""))
            if path is not None and path.exists() and path.is_file():
                sources[relative_to_run(run_dir, path)] = path

    return sorted(sources.items())


def bundle_file_record(run_dir: Path, bundle_dir: Path, relative_path: str, source: Path) -> dict[str, object]:
    target = bundle_dir / relative_path
    return {
        "path": relative_path,
        "source_sha256": file_hash(source),
        "bundle_sha256": file_hash(target),
        "size_bytes": target.stat().st_size if target.exists() else 0,
        "copied": target.exists(),
    }


def write_bundle_zip(bundle_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir).as_posix())
    return zip_path
