"""Read-only execution adapter contract skeleton.

This module intentionally does not execute any action. It converts execution
gate readiness into adapter-shaped records so later loops can add real adapter
implementations behind the same contract.
"""

from __future__ import annotations


def evaluate_execution_adapter_contract(gates: dict[str, object]) -> dict[str, object]:
    gate_records = [
        record for record in gates.get("gates", [])
        if isinstance(record, dict)
    ]
    adapters = [adapter_contract(record) for record in gate_records]
    ready_count = sum(1 for adapter in adapters if adapter["ready_for_adapter"])
    return {
        "mode": "reserved execution adapter contract",
        "dry_run_only": True,
        "executable_actions": [],
        "ready_adapter_count": ready_count,
        "blocked_adapter_count": len(adapters) - ready_count,
        "required_inputs": [
            "approval_contract",
            "approval_ledger",
            "evidence_manifest",
            "execution_gate",
        ],
        "no_execution_guarantee": "No approve, resume, write, commit, push, or delete action is executed.",
        "adapters": adapters,
    }


def adapter_contract(gate: dict[str, object]) -> dict[str, object]:
    action = str(gate.get("action") or "unknown")
    ready = bool(gate.get("ready_for_execution_adapter"))
    blockers = gate.get("blockers", [])
    if not isinstance(blockers, list):
        blockers = []
    return {
        "action": action,
        "adapter": f"{action}.reserved",
        "status": "ready" if ready else "blocked",
        "ready_for_adapter": ready,
        "dry_run_supported": True,
        "execute_supported": False,
        "executable": False,
        "blockers": [str(item) for item in blockers],
        "reason": "Adapter contract is reserved; execution is disabled.",
    }
