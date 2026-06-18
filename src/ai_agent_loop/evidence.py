"""Evidence manifest helpers for replayable run artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.ledger import approval_scope, scope_hash, scope_values


EVIDENCE_MANIFEST_FILENAME = "evidence_manifest.json"


def manifest_path(run_dir: Path) -> Path:
    return run_dir / EVIDENCE_MANIFEST_FILENAME


def read_evidence_manifest(run_dir: Path) -> dict[str, object]:
    path = manifest_path(run_dir)
    if not path.exists():
        return {
            "status": "missing manifest",
            "manifest_file": EVIDENCE_MANIFEST_FILENAME,
            "scope_replay_source": "events",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "invalid manifest",
            "manifest_file": EVIDENCE_MANIFEST_FILENAME,
            "scope_replay_source": "events",
        }
    if not isinstance(data, dict):
        return {
            "status": "invalid manifest",
            "manifest_file": EVIDENCE_MANIFEST_FILENAME,
            "scope_replay_source": "events",
        }
    data.setdefault("status", "present")
    data.setdefault("manifest_file", EVIDENCE_MANIFEST_FILENAME)
    data.setdefault("scope_replay_source", "manifest")
    return data


def write_evidence_manifest(run_dir: Path, events: list[dict[str, object]] | None = None) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    data = build_evidence_manifest(run_dir, events)
    path = manifest_path(run_dir)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_evidence_manifest(
    run_dir: Path,
    events: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    resolved_events = events if events is not None else read_events(run_dir / "events.jsonl")
    scope_parts = approval_scope(resolved_events)
    artifact_hashes = collect_artifact_hashes(run_dir, resolved_events)
    core_hashes = {
        name: file_hash(run_dir / name)
        for name in ("events.jsonl", "report.md", "approvals.jsonl")
    }
    return {
        "version": 1,
        "status": "present",
        "manifest_file": EVIDENCE_MANIFEST_FILENAME,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope_replay_source": "manifest",
        "core_hashes": core_hashes,
        "artifact_hashes": artifact_hashes,
        "changed_files": scope_values(scope_parts, "changed:"),
        "diff_hashes": scope_values(scope_parts, "diff:"),
        "risk_scope": scope_values(scope_parts, "risk:"),
        "command_scope": scope_values(scope_parts, "command:"),
        "scope_parts": scope_parts,
        "scope_hash": scope_hash(scope_parts),
    }


def scope_from_manifest_or_events(
    manifest: dict[str, object],
    events: list[dict[str, object]],
) -> list[str]:
    if manifest.get("status") == "present":
        parts = manifest.get("scope_parts", [])
        if isinstance(parts, list):
            return sorted(str(part) for part in parts)
    return approval_scope(events)


def scope_evidence_from_manifest_or_events(
    manifest: dict[str, object],
    events: list[dict[str, object]],
) -> dict[str, object]:
    scope_parts = scope_from_manifest_or_events(manifest, events)
    return {
        "scope_hash": scope_hash(scope_parts),
        "scope_parts": scope_parts,
        "changed_files": scope_values(scope_parts, "changed:"),
        "diff_hashes": scope_values(scope_parts, "diff:"),
        "risk_scope": scope_values(scope_parts, "risk:"),
        "command_scope": scope_values(scope_parts, "command:"),
        "has_evidence": bool(scope_parts),
        "manifest_status": manifest.get("status", "missing manifest"),
        "scope_replay_source": manifest.get("scope_replay_source", "events"),
        "manifest_file": manifest.get("manifest_file", EVIDENCE_MANIFEST_FILENAME),
    }


def collect_artifact_hashes(
    run_dir: Path,
    events: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    candidates: dict[str, Path] = {}
    for event in events:
        artifacts = event.get("artifacts", {})
        if not isinstance(artifacts, dict):
            continue
        for name, value in artifacts.items():
            path = resolve_run_path(run_dir, value)
            if path is not None:
                candidates[f"{name}:{relative_to_run(run_dir, path)}"] = path
    for path in [run_dir / "diff.patch", run_dir / "git" / "diff.patch"]:
        if path.exists():
            candidates[f"diff:{relative_to_run(run_dir, path)}"] = path
    artifact_hashes: dict[str, dict[str, object]] = {}
    for key, path in sorted(candidates.items()):
        artifact_hashes[key] = {
            "path": relative_to_run(run_dir, path),
            "sha256": file_hash(path),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
    return artifact_hashes


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def resolve_run_path(run_dir: Path, value: object) -> Path | None:
    path = Path(str(value))
    candidate = path if path.is_absolute() else run_dir / path
    try:
        resolved = candidate.resolve()
        if not resolved.is_relative_to(run_dir.resolve()):
            return None
    except OSError:
        return None
    return resolved


def relative_to_run(run_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return str(path)
