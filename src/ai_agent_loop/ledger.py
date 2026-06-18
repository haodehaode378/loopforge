"""Read-only approval ledger model and status helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.approval import ApprovalRequest


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
    return "active" if decision == "approved" else "inactive"


def summarize_ledger(entries: list[dict[str, object]]) -> dict[str, object]:
    entries = [normalize_ledger_entry(entry) for entry in entries]
    active = [entry for entry in entries if entry.get("status") == "active"]
    expired = [entry for entry in entries if entry.get("status") == "expired"]
    revoked = [entry for entry in entries if entry.get("status") == "revoked"]
    return {
        "ledger_file": LEDGER_FILENAME,
        "entry_count": len(entries),
        "active_approvals": active,
        "expired_approvals": expired,
        "revoked_approvals": revoked,
        "status": "present" if entries else "empty",
    }


def scope_hash(parts: list[str]) -> str:
    payload = "\n".join(sorted(str(part) for part in parts))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def request_id(run_id: str, request: ApprovalRequest, scope: list[str]) -> str:
    return "req_" + scope_hash(
        [run_id, request.action, request.required_approval, request.source_event, *scope]
    )


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
