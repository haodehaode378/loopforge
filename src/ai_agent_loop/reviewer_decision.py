"""Read-only reviewer decision records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.evidence import stable_hash
from ai_agent_loop.reviewer_handoff import HANDOFF_DIRNAME, REVIEWER_MANIFEST


REVIEWER_DECISIONS_FILENAME = "reviewer_decisions.jsonl"
VALID_DECISIONS = {"approve", "request-changes", "block"}
NO_EXECUTION_GUARANTEE = (
    "Reviewer decisions are review records only and do not approve, resume, write, "
    "commit, push, or delete."
)


def record_reviewer_decision(
    run_dir: Path,
    run_id: str,
    handoff_id: str,
    decision: str,
    actor: str,
    reason: str,
    created_at: str | None = None,
) -> tuple[dict[str, object] | None, str]:
    error = validate_reviewer_decision(run_dir, handoff_id, decision, actor, reason)
    if error:
        return None, error

    entries = read_reviewer_decisions(run_dir)
    conflicts = [
        str(entry.get("decision_id"))
        for entry in entries
        if entry.get("handoff_id") == handoff_id and entry.get("status") == "recorded"
    ]
    status = "conflict" if conflicts else "recorded"
    entry = build_reviewer_decision_record(
        run_id=run_id,
        handoff_id=handoff_id,
        decision=decision,
        actor=actor,
        reason=reason,
        status=status,
        conflict_with=conflicts,
        created_at=created_at,
    )
    append_reviewer_decision(run_dir, entry)
    return entry, ""


def validate_reviewer_decision(
    run_dir: Path,
    handoff_id: str,
    decision: str,
    actor: str,
    reason: str,
) -> str:
    if decision not in VALID_DECISIONS:
        return f"invalid decision: {decision}"
    if not actor.strip():
        return "actor is required"
    if not reason.strip():
        return "reason is required"
    if not handoff_manifest_path(run_dir, handoff_id).exists():
        return "handoff-id is not part of the current reviewer handoff set."
    return ""


def build_reviewer_decision_record(
    run_id: str,
    handoff_id: str,
    decision: str,
    actor: str,
    reason: str,
    status: str = "recorded",
    conflict_with: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    created = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "run_id": run_id,
        "handoff_id": handoff_id,
        "decision": decision,
        "actor": actor,
        "reason": reason,
        "created_at": created,
        "status": status,
        "conflict_with": conflict_with or [],
    }
    return {
        "entry_type": "reviewer_decision",
        "decision_id": "rdec_" + stable_hash(payload)[:16],
        **payload,
        "no_execution_guarantee": NO_EXECUTION_GUARANTEE,
    }


def append_reviewer_decision(run_dir: Path, entry: dict[str, object]) -> None:
    path = reviewer_decisions_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def read_reviewer_decisions(run_dir: Path) -> list[dict[str, object]]:
    path = reviewer_decisions_path(run_dir)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            entries.append(data)
    return entries


def read_reviewer_decisions_summary(run_dir: Path) -> dict[str, object]:
    entries = read_reviewer_decisions(run_dir)
    latest = entries[-1] if entries else {}
    status = evaluate_reviewer_status(entries)
    return {
        "decision_file": str(reviewer_decisions_path(run_dir)),
        "entry_count": len(entries),
        "latest": latest,
        "recorded_decisions": [entry for entry in entries if entry.get("status") == "recorded"],
        "conflict_decisions": [entry for entry in entries if entry.get("status") == "conflict"],
        "status_counts": status_counts(entries),
        "reviewer_status": status,
        "no_execution_guarantee": NO_EXECUTION_GUARANTEE,
    }


def render_reviewer_decisions_summary(run_dir: Path) -> str:
    summary = read_reviewer_decisions_summary(run_dir)
    if not summary["entry_count"]:
        return "- none"
    latest = summary.get("latest", {})
    if not isinstance(latest, dict):
        latest = {}
    counts = summary.get("status_counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return "\n".join(
        [
            f"- decision_count: {summary.get('entry_count', 0)}",
            f"- recorded_count: {counts.get('recorded', 0)}",
            f"- conflict_count: {counts.get('conflict', 0)}",
            f"- latest_decision_id: {latest.get('decision_id', '')}",
            f"- latest_handoff_id: {latest.get('handoff_id', '')}",
            f"- latest_reviewer_decision: {latest.get('decision', '')}",
            f"- latest_status: {latest.get('status', '')}",
            f"- decision_file: {summary.get('decision_file', '')}",
            f"- no_execution: {NO_EXECUTION_GUARANTEE}",
        ]
    )


def evaluate_reviewer_status(entries: list[dict[str, object]]) -> dict[str, object]:
    conflicts = [entry for entry in entries if entry.get("status") == "conflict"]
    recorded = [entry for entry in entries if entry.get("status") == "recorded"]
    if conflicts:
        return reviewer_status(
            "conflict",
            "Resolve duplicate reviewer decisions before relying on the review signal.",
            ready_for_next_loop=False,
        )
    if not recorded:
        return reviewer_status(
            "waiting-review",
            "Record a reviewer decision for the latest reviewer handoff.",
            ready_for_next_loop=False,
        )

    latest = recorded[-1]
    decision = str(latest.get("decision") or "")
    if decision == "approve":
        return reviewer_status(
            "review-passed",
            "Proceed to the next planning loop with reviewer approval as evidence only.",
            ready_for_next_loop=True,
        )
    if decision == "request-changes":
        return reviewer_status(
            "changes-requested",
            "Plan a follow-up loop to address reviewer-requested changes.",
            ready_for_next_loop=True,
        )
    if decision == "block":
        return reviewer_status(
            "blocked-by-review",
            "Stop autonomous continuation until the reviewer block is resolved.",
            ready_for_next_loop=False,
        )
    return reviewer_status(
        "unknown-review",
        "Review decision is unreadable; inspect reviewer_decisions.jsonl.",
        ready_for_next_loop=False,
    )


def reviewer_status(state: str, next_action: str, ready_for_next_loop: bool) -> dict[str, object]:
    return {
        "state": state,
        "next_action": next_action,
        "ready_for_next_loop": ready_for_next_loop,
        "execution_authority": False,
        "mode": "advisory-only reviewer status",
        "no_execution_guarantee": NO_EXECUTION_GUARANTEE,
    }


def render_reviewer_status(run_dir: Path) -> str:
    summary = read_reviewer_decisions_summary(run_dir)
    status = summary.get("reviewer_status", {})
    if not isinstance(status, dict):
        status = {}
    return "\n".join(
        [
            f"- state: {status.get('state', 'waiting-review')}",
            f"- ready_for_next_loop: {status.get('ready_for_next_loop', False)}",
            f"- execution_authority: {status.get('execution_authority', False)}",
            f"- mode: {status.get('mode', 'advisory-only reviewer status')}",
            f"- next_action: {status.get('next_action', '')}",
            f"- no_execution: {status.get('no_execution_guarantee', NO_EXECUTION_GUARANTEE)}",
        ]
    )


def status_counts(entries: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def handoff_manifest_path(run_dir: Path, handoff_id: str) -> Path:
    return run_dir / HANDOFF_DIRNAME / handoff_id / REVIEWER_MANIFEST


def reviewer_decisions_path(run_dir: Path) -> Path:
    return run_dir / REVIEWER_DECISIONS_FILENAME
