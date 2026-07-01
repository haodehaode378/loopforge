"""Read-only reviewer handoff package generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.evidence import file_hash, read_evidence_manifest, stable_hash


HANDOFF_DIRNAME = "reviewer_handoff"
REVIEWER_INPUT = "reviewer_input.json"
REVIEWER_PROMPT = "reviewer_prompt.md"
REVIEWER_MANIFEST = "reviewer_manifest.json"


def export_reviewer_handoff(
    run_dir: Path,
    run_id: str,
    approval_readiness: str,
    change_set_critique: str,
) -> dict[str, object]:
    run_dir = run_dir.resolve()
    handoff_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    handoff_dir = run_dir / HANDOFF_DIRNAME / handoff_id
    handoff_dir.mkdir(parents=True, exist_ok=True)

    goal = read_json(run_dir / "goal.json")
    events = read_events(run_dir / "events.jsonl")
    report = read_text(run_dir / "report.md")
    evidence_manifest = read_evidence_manifest(run_dir)
    bundle = latest_evidence_bundle(run_dir)
    risk_summary = summarize_risks(events)
    questions = reviewer_questions(events, evidence_manifest, bundle)
    reviewer_input = {
        "version": 1,
        "mode": "read-only reviewer handoff",
        "run_id": run_id,
        "handoff_id": handoff_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "no_execution_guarantee": "No approve, resume, write, commit, push, or delete action was executed.",
        "run": {
            "goal": goal.get("description", ""),
            "status": goal.get("status", ""),
            "project": goal.get("project", ""),
            "project_id": goal.get("project_id", ""),
            "project_path": goal.get("project_path", ""),
        },
        "evidence_bundle": bundle,
        "report_summary": report_summary(report),
        "approval_readiness": approval_readiness,
        "evidence_manifest": {
            "status": evidence_manifest.get("status", "missing manifest"),
            "integrity_status": evidence_manifest.get(
                "integrity_status",
                evidence_manifest.get("status", "missing manifest"),
            ),
            "audit_status": evidence_manifest.get("audit_status", "missing audit digest"),
            "audit_digest": evidence_manifest.get("audit_digest", ""),
            "integrity_issues": evidence_manifest.get("integrity_issues", []),
        },
        "change_set_critique": change_set_critique,
        "risk_summary": risk_summary,
        "reviewer_questions": questions,
    }

    input_path = handoff_dir / REVIEWER_INPUT
    prompt_path = handoff_dir / REVIEWER_PROMPT
    manifest_path = handoff_dir / REVIEWER_MANIFEST
    input_path.write_text(
        json.dumps(reviewer_input, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    prompt_path.write_text(render_reviewer_prompt(reviewer_input), encoding="utf-8")
    manifest = build_reviewer_manifest(run_id, handoff_id, handoff_dir)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        **manifest,
        "handoff_dir": str(handoff_dir),
        "reviewer_input": str(input_path),
        "reviewer_prompt": str(prompt_path),
        "reviewer_manifest": str(manifest_path),
    }


def latest_evidence_bundle(run_dir: Path) -> dict[str, object]:
    bundle_root = run_dir / "evidence_bundle"
    manifests = sorted(bundle_root.glob("*/bundle_manifest.json"), reverse=True) if bundle_root.exists() else []
    if not manifests:
        return {"status": "missing", "bundle_id": "", "bundle_hash": "", "zip_path": ""}
    data = read_json(manifests[0])
    bundle_id = str(data.get("bundle_id") or "")
    return {
        "status": "present",
        "bundle_id": bundle_id,
        "bundle_hash": data.get("bundle_hash", ""),
        "manifest_path": str(manifests[0]),
        "zip_path": str(run_dir / f"evidence_bundle-{bundle_id}.zip") if bundle_id else "",
        "file_count": len(data.get("files", [])) if isinstance(data.get("files"), list) else 0,
    }


def read_reviewer_handoff_summary(run_dir: Path) -> dict[str, object]:
    handoff_root = run_dir / HANDOFF_DIRNAME
    manifests = sorted(handoff_root.glob("*/reviewer_manifest.json"), reverse=True) if handoff_root.exists() else []
    if not manifests:
        return {"handoff_count": 0, "latest": {}}
    latest = read_json(manifests[0])
    return {
        "handoff_count": len(manifests),
        "latest": latest,
        "manifest_path": str(manifests[0]),
    }


def render_reviewer_handoff_summary(run_dir: Path) -> str:
    summary = read_reviewer_handoff_summary(run_dir)
    if not summary.get("handoff_count"):
        return "- none"
    latest = summary.get("latest", {})
    if not isinstance(latest, dict):
        latest = {}
    return "\n".join(
        [
            f"- handoff_count: {summary.get('handoff_count', 0)}",
            f"- latest_handoff_id: {latest.get('handoff_id', '')}",
            f"- latest_handoff_hash: {latest.get('handoff_hash', '')}",
            f"- latest_prompt: {latest.get('files', {}).get('reviewer_prompt.md', {}).get('path', '') if isinstance(latest.get('files'), dict) else ''}",
            f"- manifest: {summary.get('manifest_path', '')}",
        ]
    )


def build_reviewer_manifest(run_id: str, handoff_id: str, handoff_dir: Path) -> dict[str, object]:
    files = {}
    for name in (REVIEWER_INPUT, REVIEWER_PROMPT):
        path = handoff_dir / name
        files[name] = {
            "path": str(path),
            "sha256": file_hash(path),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
    manifest = {
        "version": 1,
        "run_id": run_id,
        "handoff_id": handoff_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "read-only reviewer handoff",
        "no_execution_guarantee": "No approve, resume, write, commit, push, or delete action was executed.",
        "files": files,
    }
    manifest["handoff_hash"] = stable_hash(manifest)
    return manifest


def render_reviewer_prompt(reviewer_input: dict[str, object]) -> str:
    run = reviewer_input.get("run", {})
    if not isinstance(run, dict):
        run = {}
    questions = reviewer_input.get("reviewer_questions", [])
    if not isinstance(questions, list):
        questions = []
    return "\n".join(
        [
            "# Reviewer Handoff",
            "",
            "You are reviewing a LoopForge run from a read-only evidence package.",
            "Do not approve, resume, write, commit, push, delete, or execute commands.",
            "",
            f"- Run ID: {reviewer_input.get('run_id', '')}",
            f"- Goal: {run.get('goal', '')}",
            f"- Status: {run.get('status', '')}",
            f"- Evidence bundle: {reviewer_input.get('evidence_bundle', {}).get('bundle_hash', '') if isinstance(reviewer_input.get('evidence_bundle'), dict) else ''}",
            "",
            "## Review Questions",
            *[f"- {question}" for question in questions],
            "",
            "## Expected Output",
            "",
            "- Scope findings",
            "- Verification findings",
            "- Risk findings",
            "- Product alignment findings",
            "- Recommended next action",
            "",
        ]
    )


def reviewer_questions(
    events: list[dict[str, object]],
    evidence_manifest: dict[str, object],
    bundle: dict[str, object],
) -> list[str]:
    questions = [
        "Does the run evidence support the claimed status?",
        "Are approval readiness and scope replay consistent with the evidence manifest?",
        "Are there unresolved risks or blocked actions that should stop the next loop?",
        "Is the change-set critique aligned with the actual run evidence?",
    ]
    if evidence_manifest.get("integrity_status") != "verified":
        questions.append("The evidence manifest is not verified; what evidence is missing or tampered?")
    if bundle.get("status") != "present":
        questions.append("No evidence bundle was found; should a bundle be exported before review?")
    if any(event.get("status") == "blocked" for event in events):
        questions.append("What decision is required to resolve the blocked run?")
    return questions


def summarize_risks(events: list[dict[str, object]]) -> dict[str, object]:
    risks = []
    for event in events:
        risk = event.get("risk", {})
        if isinstance(risk, dict) and risk:
            risks.append(
                {
                    "event": event.get("name", ""),
                    "status": event.get("status", ""),
                    "level": risk.get("level", "unknown"),
                    "reason": risk.get("reason", ""),
                }
            )
    return {
        "risk_count": len(risks),
        "blocked_count": sum(1 for event in events if event.get("status") == "blocked"),
        "risks": risks,
    }


def report_summary(report: str, limit: int = 2000) -> str:
    return report[:limit]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events
