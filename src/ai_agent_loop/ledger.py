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


def summarize_ledger(entries: list[dict[str, object]]) -> dict[str, object]:
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
    active = [entry for entry in entries if entry.get("status") == "active"]
    expired = [entry for entry in entries if entry.get("status") == "expired"]
    revoked = [entry for entry in entries if entry.get("status") == "revoked"]
    denied = [entry for entry in entries if entry.get("status") == "denied"]
    conflicts = [entry for entry in entries if entry.get("status") == "conflict"]
    return {
        "ledger_file": LEDGER_FILENAME,
        "entry_count": len(entries),
        "active_approvals": active,
        "expired_approvals": expired,
        "revoked_approvals": revoked,
        "denied_approvals": denied,
        "conflict_approvals": conflicts,
        "status": "present" if entries else "empty",
    }


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
        if artifacts.get("diff"):
            scope.append(f"diff:{artifacts.get('diff')}")
    return sorted(set(scope))


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
