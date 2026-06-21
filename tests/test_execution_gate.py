import unittest

from ai_agent_loop.execution_gate import (
    build_execution_gate_event,
    collect_execution_gate_events,
    evaluate_execution_gates,
)


class ExecutionGateTests(unittest.TestCase):
    def test_verified_manifest_and_ready_approval_make_future_gate_ready_not_executable(self) -> None:
        contract = {
            "missing_approvals": [],
            "resume_eligibility": {"eligible": True},
        }
        ledger = {
            "execution_ready_approvals": [{"decision_id": "dec_1"}],
            "denied_approvals": [],
            "conflict_approvals": [],
            "revoked_approvals": [],
            "expired_approvals": [],
        }
        manifest = {"integrity_status": "verified"}

        gates = evaluate_execution_gates(contract, ledger, manifest)

        write_gate = next(item for item in gates["gates"] if item["action"] == "write")
        self.assertTrue(write_gate["ready_for_execution_adapter"])
        self.assertFalse(write_gate["executable"])

    def test_tampered_manifest_blocks_all_gates(self) -> None:
        gates = evaluate_execution_gates(
            {"missing_approvals": [], "resume_eligibility": {"eligible": True}},
            {"execution_ready_approvals": [{"decision_id": "dec_1"}]},
            {"integrity_status": "tampered"},
        )

        self.assertTrue(gates["blocked_actions"])
        self.assertIn("tampered", gates["blocked_actions"][0]["reason"])

    def test_denied_or_missing_approval_blocks_gate(self) -> None:
        gates = evaluate_execution_gates(
            {"missing_approvals": [{"action": "write"}], "resume_eligibility": {"eligible": False}},
            {"execution_ready_approvals": [], "denied_approvals": [{"decision_id": "dec_1"}]},
            {"integrity_status": "verified"},
        )

        write_gate = next(item for item in gates["gates"] if item["action"] == "write")
        self.assertFalse(write_gate["ready_for_execution_adapter"])
        self.assertIn("approval for write is missing", write_gate["reason"])
        self.assertIn("denied", write_gate["reason"])

    def test_gate_event_is_read_only_audit_record(self) -> None:
        gates = evaluate_execution_gates(
            {"missing_approvals": [], "resume_eligibility": {"eligible": True}},
            {"execution_ready_approvals": [{"decision_id": "dec_1"}]},
            {"integrity_status": "verified"},
        )

        event = build_execution_gate_event("run-1", gates, {"integrity_status": "verified"})

        self.assertEqual(event["name"], "execution.gate.evaluated")
        self.assertEqual(event["status"], "done")
        self.assertEqual(event["metadata"]["run_id"], "run-1")
        self.assertEqual(event["metadata"]["executable_actions"], [])
        self.assertEqual(collect_execution_gate_events([event]), [event])


if __name__ == "__main__":
    unittest.main()
