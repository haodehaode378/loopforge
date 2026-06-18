"""Read-only execution readiness gate for reserved actions."""

from __future__ import annotations

from ai_agent_loop.approval import RESERVED_ACTIONS


def evaluate_execution_gates(
    contract: dict[str, object],
    ledger: dict[str, object],
    manifest: dict[str, object],
) -> dict[str, object]:
    gates = [
        evaluate_execution_gate(action, contract, ledger, manifest)
        for action in RESERVED_ACTIONS
    ]
    return {
        "mode": "read-only execution readiness",
        "executable_actions": [],
        "ready_actions": [
            gate["action"] for gate in gates
            if gate["ready_for_execution_adapter"]
        ],
        "blocked_actions": [
            gate for gate in gates
            if not gate["ready_for_execution_adapter"]
        ],
        "gates": gates,
    }


def evaluate_execution_gate(
    action: str,
    contract: dict[str, object],
    ledger: dict[str, object],
    manifest: dict[str, object],
) -> dict[str, object]:
    blockers = gate_blockers(action, contract, ledger, manifest)
    return {
        "action": action,
        "executable": False,
        "ready_for_execution_adapter": not blockers,
        "reason": "Execution adapter is not implemented." if not blockers else "; ".join(blockers),
        "blockers": blockers,
    }


def gate_blockers(
    action: str,
    contract: dict[str, object],
    ledger: dict[str, object],
    manifest: dict[str, object],
) -> list[str]:
    blockers: list[str] = []
    if manifest.get("integrity_status") != "verified":
        blockers.append(f"manifest integrity is {manifest.get('integrity_status', 'missing manifest')}")
    if ledger.get("denied_approvals"):
        blockers.append("approval ledger contains denied decisions")
    if ledger.get("conflict_approvals"):
        blockers.append("approval ledger contains conflict decisions")
    if ledger.get("revoked_approvals"):
        blockers.append("approval ledger contains revoked decisions")
    if ledger.get("expired_approvals"):
        blockers.append("approval ledger contains expired decisions")
    missing = contract.get("missing_approvals", [])
    if action in {"approve", "resume"}:
        if missing:
            blockers.append("required approvals are missing")
    elif requires_approval_for_action(action, missing):
        blockers.append(f"approval for {action} is missing")
    if action == "resume":
        resume = contract.get("resume_eligibility", {})
        if not isinstance(resume, dict) or not resume.get("eligible"):
            blockers.append("resume is not eligible")
    if action not in {"approve", "resume"} and not ledger.get("execution_ready_approvals"):
        blockers.append("no active matched approval is execution-ready")
    return blockers


def requires_approval_for_action(action: str, missing: object) -> bool:
    if not isinstance(missing, list):
        return False
    return any(
        isinstance(item, dict) and item.get("action") == action
        for item in missing
    )
