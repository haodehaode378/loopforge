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
            "integrity_status": "missing manifest",
            "manifest_file": EVIDENCE_MANIFEST_FILENAME,
            "scope_replay_source": "events",
            "integrity_issues": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "invalid manifest",
            "integrity_status": "invalid manifest",
            "manifest_file": EVIDENCE_MANIFEST_FILENAME,
            "scope_replay_source": "events",
            "integrity_issues": [],
        }
    if not isinstance(data, dict):
        return {
            "status": "invalid manifest",
            "integrity_status": "invalid manifest",
            "manifest_file": EVIDENCE_MANIFEST_FILENAME,
            "scope_replay_source": "events",
            "integrity_issues": [],
        }
    data.setdefault("status", "present")
    data.setdefault("manifest_file", EVIDENCE_MANIFEST_FILENAME)
    data.setdefault("scope_replay_source", "manifest")
    integrity = verify_evidence_manifest(run_dir, data)
    data["integrity_status"] = integrity["integrity_status"]
    data["integrity_issues"] = integrity["integrity_issues"]
    data["audit_status"] = audit_status(run_dir, data)
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
    audit_chain = build_event_chain(resolved_events)
    digest_inputs = {
        "version": 1,
        "core_hashes": core_hashes,
        "artifact_hashes": artifact_hashes,
        "scope_hash": scope_hash(scope_parts),
        "audit_chain_head": audit_chain["head"],
        "event_count": audit_chain["event_count"],
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
        "audit_chain": audit_chain,
        "audit_digest": stable_hash(digest_inputs),
        "audit_status": "verified",
    }


def scope_from_manifest_or_events(
    manifest: dict[str, object],
    events: list[dict[str, object]],
) -> list[str]:
    if manifest.get("status") == "present" and manifest.get("integrity_status") != "tampered":
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
        "integrity_status": manifest.get("integrity_status", manifest.get("status", "missing manifest")),
        "scope_replay_source": manifest.get("scope_replay_source", "events"),
        "manifest_file": manifest.get("manifest_file", EVIDENCE_MANIFEST_FILENAME),
    }


def verify_evidence_manifest(
    run_dir: Path,
    manifest: dict[str, object] | None = None,
) -> dict[str, object]:
    data = manifest or read_evidence_manifest(run_dir)
    if data.get("status") != "present":
        return {
            "integrity_status": data.get("status", "missing manifest"),
            "integrity_issues": [],
        }
    issues: list[dict[str, object]] = []
    issues.extend(compare_core_hashes(run_dir, data))
    issues.extend(compare_artifact_hashes(run_dir, data))
    issues.extend(compare_scope_hash(run_dir, data))
    issues.extend(compare_audit_digest(run_dir, data))
    return {
        "integrity_status": "tampered" if issues else "verified",
        "integrity_issues": issues,
    }


def build_event_chain(events: list[dict[str, object]]) -> dict[str, object]:
    previous = ""
    records = []
    for index, event in enumerate(events):
        current = stable_hash(
            {
                "index": index,
                "previous": previous,
                "event": event,
            }
        )
        records.append(
            {
                "index": index,
                "name": event.get("name", "unknown"),
                "status": event.get("status", "unknown"),
                "hash": current,
            }
        )
        previous = current
    return {
        "algorithm": "sha256-json-event-chain-v1",
        "event_count": len(events),
        "head": previous,
        "records": records,
    }


def stable_hash(data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def recompute_audit_digest(run_dir: Path, events: list[dict[str, object]]) -> dict[str, object]:
    scope_parts = approval_scope(events)
    core_hashes = {
        name: file_hash(run_dir / name)
        for name in ("events.jsonl", "report.md", "approvals.jsonl")
    }
    audit_chain = build_event_chain(events)
    digest_inputs = {
        "version": 1,
        "core_hashes": core_hashes,
        "artifact_hashes": collect_artifact_hashes(run_dir, events),
        "scope_hash": scope_hash(scope_parts),
        "audit_chain_head": audit_chain["head"],
        "event_count": audit_chain["event_count"],
    }
    return {
        "audit_chain": audit_chain,
        "audit_digest": stable_hash(digest_inputs),
    }


def audit_status(run_dir: Path, manifest: dict[str, object]) -> str:
    if manifest.get("status") != "present":
        return str(manifest.get("status", "missing manifest"))
    if not manifest.get("audit_digest") or not manifest.get("audit_chain"):
        return "missing audit digest"
    current = recompute_audit_digest(run_dir, read_events(run_dir / "events.jsonl"))
    if manifest.get("audit_digest") != current["audit_digest"]:
        return "tampered"
    chain = manifest.get("audit_chain", {})
    if not isinstance(chain, dict) or chain.get("head") != current["audit_chain"]["head"]:
        return "tampered"
    return "verified"


def compare_audit_digest(run_dir: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    if not manifest.get("audit_digest") or not manifest.get("audit_chain"):
        return []
    current = recompute_audit_digest(run_dir, read_events(run_dir / "events.jsonl"))
    issues = []
    if manifest.get("audit_digest") != current["audit_digest"]:
        issues.append(
            {
                "kind": "audit",
                "path": "audit_digest",
                "expected": str(manifest.get("audit_digest") or ""),
                "current": str(current["audit_digest"]),
                "reason": "audit digest mismatch",
            }
        )
    chain = manifest.get("audit_chain", {})
    expected_head = chain.get("head") if isinstance(chain, dict) else ""
    current_head = current["audit_chain"]["head"]
    if expected_head != current_head:
        issues.append(
            {
                "kind": "audit",
                "path": "audit_chain.head",
                "expected": str(expected_head or ""),
                "current": str(current_head),
                "reason": "event chain head mismatch",
            }
        )
    return issues


def compare_core_hashes(run_dir: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    core = manifest.get("core_hashes", {})
    if not isinstance(core, dict):
        return [{"kind": "core", "path": "core_hashes", "reason": "core hashes are missing or invalid"}]
    issues: list[dict[str, object]] = []
    for name, expected in core.items():
        current = file_hash(run_dir / str(name))
        if str(expected or "") != current:
            issues.append(
                {
                    "kind": "core",
                    "path": str(name),
                    "expected": str(expected or ""),
                    "current": current,
                    "reason": "hash mismatch",
                }
            )
    return issues


def compare_artifact_hashes(run_dir: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    artifacts = manifest.get("artifact_hashes", {})
    if not isinstance(artifacts, dict):
        return [{"kind": "artifact", "path": "artifact_hashes", "reason": "artifact hashes are missing or invalid"}]
    issues: list[dict[str, object]] = []
    for key, record in artifacts.items():
        if not isinstance(record, dict):
            issues.append({"kind": "artifact", "path": str(key), "reason": "artifact record is invalid"})
            continue
        path_value = record.get("path", "")
        path = resolve_run_path(run_dir, path_value)
        current = file_hash(path) if path is not None else ""
        expected = str(record.get("sha256") or "")
        if expected != current:
            issues.append(
                {
                    "kind": "artifact",
                    "path": str(path_value),
                    "expected": expected,
                    "current": current,
                    "reason": "hash mismatch",
                }
            )
    return issues


def compare_scope_hash(run_dir: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    events = read_events(run_dir / "events.jsonl")
    current_scope = approval_scope(events)
    current_hash = scope_hash(current_scope)
    expected = str(manifest.get("scope_hash") or "")
    if expected == current_hash:
        return []
    return [
        {
            "kind": "scope",
            "path": "scope_hash",
            "expected": expected,
            "current": current_hash,
            "reason": "scope hash mismatch",
        }
    ]


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
