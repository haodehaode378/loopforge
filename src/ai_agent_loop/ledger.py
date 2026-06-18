"""Approval ledger model and status helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.approval import ApprovalContract, ApprovalRequest


LEDGER_FILENAME = "approvals.jsonl"


@dataclass(frozen=True)
class LedgerEntry:
    entry_type: str
    request_id: str
    decision_id: str
    actor: str
    created_at: str
    expires_at: str
    scope_hash: str
    decision: str
    reason: str
    scope_parts: tuple[str, ...] = ()
    actor_signature: str = ""
    signature_status: str = "unsigned"

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_type": self.entry_type,
            "request_id": self.request_id,
            "decision_id": self.decision_id,
            "actor": self.actor,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "scope_hash": self.scope_hash,
            "decision": self.decision,
            "reason": self.reason,
            "scope_parts": list(self.scope_parts),
            "actor_signature": self.actor_signature,
            "signature_status": self.signature_status,
        }


def ledger_path(run_dir: Path) -> Path:
    return run_dir / LEDGER_FILENAME


def read_approval_ledger(run_dir: Path) -> list[dict[str, object]]:
    path = ledger_path(run_dir)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(normalize_ledger_entry(json.loads(line)))
    return entries


def append_approval_ledger(run_dir: Path, entry: dict[str, object]) -> Path:
    path = ledger_path(run_dir)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def normalize_ledger_entry(data: dict[str, object]) -> dict[str, object]:
    scope_parts = data.get("scope_parts", [])
    if not isinstance(scope_parts, list):
        scope_parts = []
    entry = LedgerEntry(
        entry_type=str(data.get("entry_type") or data.get("type") or "decision"),
        request_id=str(data.get("request_id") or ""),
        decision_id=str(data.get("decision_id") or ""),
        actor=str(data.get("actor") or "unknown"),
        created_at=str(data.get("created_at") or ""),
        expires_at=str(data.get("expires_at") or ""),
        scope_hash=str(data.get("scope_hash") or ""),
        decision=str(data.get("decision") or ""),
        reason=str(data.get("reason") or ""),
        scope_parts=tuple(str(part) for part in scope_parts),
        actor_signature=str(data.get("actor_signature") or ""),
        signature_status=str(data.get("signature_status") or "unsigned"),
    ).to_dict()
    entry["status"] = ledger_entry_status(entry)
    return entry


def ledger_entry_status(entry: dict[str, object], now: datetime | None = None) -> str:
    if entry.get("entry_type") == "revocation":
        return "revoked"
    expires_at = str(entry.get("expires_at") or "")
    if expires_at and parse_time(expires_at) <= (now or datetime.now(timezone.utc)):
        return "expired"
    decision = str(entry.get("decision") or "")
    if decision == "approved":
        return "active"
    if decision in {"deny", "denied"}:
        return "denied"
    return "inactive"


def summarize_ledger(
    entries: list[dict[str, object]],
    current_scope: list[str] | None = None,
) -> dict[str, object]:
    entries = [normalize_ledger_entry(entry) for entry in entries]
    revoked_decision_ids = {
        str(entry.get("decision_id"))
        for entry in entries
        if entry.get("entry_type") == "revocation"
    }
    for entry in entries:
        if entry.get("entry_type") != "revocation" and entry.get("decision_id") in revoked_decision_ids:
            entry["status"] = "revoked"
    conflict_request_ids = find_conflict_request_ids(entries)
    for entry in entries:
        if entry.get("request_id") in conflict_request_ids and entry.get("status") in {"active", "denied"}:
            entry["status"] = "conflict"
    for entry in entries:
        entry["replay_status"] = replay_status(entry, current_scope)
        entry["execution_ready"] = is_execution_ready(entry, current_scope)
    active = [entry for entry in entries if entry.get("status") == "active"]
    expired = [entry for entry in entries if entry.get("status") == "expired"]
    revoked = [entry for entry in entries if entry.get("status") == "revoked"]
    denied = [entry for entry in entries if entry.get("status") == "denied"]
    conflicts = [entry for entry in entries if entry.get("status") == "conflict"]
    replay_records = [ledger_replay_record(entry) for entry in entries]
    return {
        "ledger_file": LEDGER_FILENAME,
        "entry_count": len(entries),
        "active_approvals": active,
        "expired_approvals": expired,
        "revoked_approvals": revoked,
        "denied_approvals": denied,
        "conflict_approvals": conflicts,
        "scope_replay": replay_records,
        "replay_status_counts": replay_status_counts(replay_records),
        "execution_ready_approvals": [
            entry for entry in entries
            if entry.get("execution_ready")
        ],
        "status": "present" if entries else "empty",
    }


def replay_status(
    entry: dict[str, object],
    current_scope: list[str] | None,
) -> str:
    status = str(entry.get("status") or "")
    if status in {"expired", "revoked", "denied", "conflict"}:
        return status
    if current_scope is None:
        return "missing evidence"
    if not current_scope or not entry.get("scope_hash"):
        return "missing evidence"
    return "matched" if entry.get("scope_hash") == scope_hash(current_scope) else "changed"


def is_execution_ready(
    entry: dict[str, object],
    current_scope: list[str] | None,
) -> bool:
    return entry.get("status") == "active" and replay_status(entry, current_scope) == "matched"


def ledger_replay_record(entry: dict[str, object]) -> dict[str, object]:
    return {
        "request_id": entry.get("request_id", ""),
        "decision_id": entry.get("decision_id", ""),
        "decision": entry.get("decision", ""),
        "status": entry.get("status", ""),
        "replay_status": entry.get("replay_status", "missing evidence"),
        "execution_ready": bool(entry.get("execution_ready")),
        "scope_hash": entry.get("scope_hash", ""),
        "actor": entry.get("actor", ""),
        "actor_signature": entry.get("actor_signature", ""),
        "signature_status": entry.get("signature_status", "unsigned"),
    }


def replay_status_counts(records: list[dict[str, object]]) -> dict[str, int]:
    counts = {
        "matched": 0,
        "changed": 0,
        "missing evidence": 0,
        "expired": 0,
        "revoked": 0,
        "denied": 0,
        "conflict": 0,
    }
    for record in records:
        status = str(record.get("replay_status") or "missing evidence")
        counts[status] = counts.get(status, 0) + 1
    return counts


def find_conflict_request_ids(entries: list[dict[str, object]]) -> set[str]:
    decisions_by_request: dict[str, int] = {}
    for entry in entries:
        if entry.get("entry_type") == "revocation":
            continue
        if entry.get("status") in {"expired", "revoked"}:
            continue
        request_id_value = str(entry.get("request_id") or "")
        if request_id_value:
            decisions_by_request[request_id_value] = decisions_by_request.get(request_id_value, 0) + 1
    return {
        request_id_value
        for request_id_value, count in decisions_by_request.items()
        if count > 1
    }


def scope_hash(parts: list[str]) -> str:
    payload = "\n".join(sorted(str(part) for part in parts))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def approval_scope(events: list[dict[str, object]]) -> list[str]:
    scope: list[str] = []
    for event in events:
        name = str(event.get("name") or "")
        metadata = event.get("metadata", {})
        risk = event.get("risk", {})
        artifacts = event.get("artifacts", {})
        if not isinstance(metadata, dict):
            metadata = {}
        if not isinstance(risk, dict):
            risk = {}
        if not isinstance(artifacts, dict):
            artifacts = {}
        changed = metadata.get("changed_files", [])
        if isinstance(changed, list):
            scope.extend(f"changed:{item}" for item in changed)
        path = metadata.get("relative_path") or metadata.get("path")
        if name == "file.write" and path:
            scope.append(f"changed:{path}")
        if risk or event.get("status") == "blocked":
            scope.append(
                "risk:"
                + "|".join(
                    [
                        name,
                        str(event.get("status") or ""),
                        str(risk.get("level") or ""),
                        str(risk.get("reason") or event.get("detail") or ""),
                        str(metadata.get("command") or ""),
                    ]
                )
            )
        command = metadata.get("command")
        if command:
            scope.append(f"command:{command}")
        if artifacts.get("diff"):
            diff_value = str(artifacts.get("diff"))
            preview = event.get("artifact_previews", {})
            content = ""
            if isinstance(preview, dict):
                diff_preview = preview.get("diff", {})
                if isinstance(diff_preview, dict):
                    content = str(diff_preview.get("content") or "")
            evidence = content if content else diff_value
            scope.append(f"diff:{scope_hash([evidence])}")
    return sorted(set(scope))


def approval_scope_evidence(events: list[dict[str, object]]) -> dict[str, object]:
    parts = approval_scope(events)
    return {
        "scope_hash": scope_hash(parts),
        "scope_parts": parts,
        "changed_files": scope_values(parts, "changed:"),
        "diff_hashes": scope_values(parts, "diff:"),
        "risk_scope": scope_values(parts, "risk:"),
        "command_scope": scope_values(parts, "command:"),
        "has_evidence": bool(parts),
    }


def scope_values(parts: list[str], prefix: str) -> list[str]:
    return [
        part[len(prefix):]
        for part in parts
        if part.startswith(prefix)
    ]


def request_id(run_id: str, request: ApprovalRequest, scope: list[str]) -> str:
    return "req_" + scope_hash(
        [run_id, request.action, request.required_approval, request.source_event, *scope]
    )


def approval_requests_with_ids(
    run_id: str,
    contract: ApprovalContract,
    scope: list[str],
) -> list[dict[str, object]]:
    records = []
    for request in contract.required_approvals:
        record = request.to_dict()
        record["request_id"] = request_id(run_id, request, scope)
        record["scope_hash"] = scope_hash(scope)
        records.append(record)
    return records


def find_request_by_id(
    run_id: str,
    contract: ApprovalContract,
    scope: list[str],
    request_id_value: str,
) -> ApprovalRequest | None:
    for request in contract.required_approvals:
        if request_id(run_id, request, scope) == request_id_value:
            return request
    return None


def decision_id(request_id_value: str, actor: str, created_at: str) -> str:
    return "dec_" + scope_hash([request_id_value, actor, created_at])


def build_ledger_decision_record(
    run_id: str,
    request: ApprovalRequest,
    actor: str,
    created_at: str,
    expires_at: str,
    scope: list[str],
    decision: str,
    reason: str,
) -> dict[str, object]:
    req_id = request_id(run_id, request, scope)
    return LedgerEntry(
        entry_type="decision",
        request_id=req_id,
        decision_id=decision_id(req_id, actor, created_at),
        actor=actor,
        created_at=created_at,
        expires_at=expires_at,
        scope_hash=scope_hash(scope),
        decision=decision,
        reason=reason,
        scope_parts=tuple(sorted(scope)),
        actor_signature="",
        signature_status="unsigned",
    ).to_dict()


def validate_decision_record(
    run_id: str,
    contract: ApprovalContract,
    scope: list[str],
    entries: list[dict[str, object]],
    request_id_value: str,
) -> tuple[ApprovalRequest | None, str]:
    request = find_request_by_id(run_id, contract, scope, request_id_value)
    if request is None:
        return None, "request-id is not part of the current approval contract scope."
    expected_scope_hash = scope_hash(scope)
    for entry in summarize_ledger(entries)["active_approvals"]:
        if entry.get("request_id") == request_id_value:
            return request, "conflict: active decision already exists for this request-id."
        if entry.get("scope_hash") != expected_scope_hash:
            return request, "conflict: active approval scope hash differs from current scope."
    for entry in summarize_ledger(entries)["denied_approvals"]:
        if entry.get("request_id") == request_id_value:
            return request, "conflict: denial already exists for this request-id."
    return request, ""


def build_ledger_revocation_record(
    decision_id_value: str,
    actor: str,
    created_at: str,
    reason: str,
) -> dict[str, object]:
    return LedgerEntry(
        entry_type="revocation",
        request_id="",
        decision_id=decision_id_value,
        actor=actor,
        created_at=created_at,
        expires_at="",
        scope_hash="",
        decision="revoked",
        reason=reason,
    ).to_dict()


def parse_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
