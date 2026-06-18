import unittest

from ai_agent_loop.approval import (
    approval_for_risk,
    build_approval_event,
    evaluate_approval_contract,
)


class ApprovalContractTests(unittest.TestCase):
    def test_risk_levels_map_to_required_approvals(self) -> None:
        self.assertEqual(approval_for_risk("low"), "none")
        self.assertEqual(approval_for_risk("medium"), "user-approval")
        self.assertEqual(approval_for_risk("high"), "explicit-high-risk-approval")
        self.assertEqual(approval_for_risk("surprise"), "policy-review")

    def test_missing_approvals_block_reserved_actions_and_resume(self) -> None:
        contract = evaluate_approval_contract(
            [
                {
                    "name": "git.push.blocked",
                    "status": "blocked",
                    "risk": {
                        "level": "high",
                        "reason": "Git push can publish local changes.",
                    },
                    "metadata": {"command": "git push origin main"},
                }
            ]
        )
        data = contract.to_dict()

        self.assertEqual(data["required_approvals"][0]["required_approval"], "explicit-high-risk-approval")
        self.assertEqual(data["missing_approvals"][0]["action"], "push")
        self.assertFalse(data["resume_eligibility"]["eligible"])
        self.assertIn("missing approvals", data["resume_eligibility"]["reason"])
        push_decision = next(item for item in data["blocked_actions"] if item["action"] == "push")
        self.assertFalse(push_decision["allowed"])
        self.assertIn("explicit-high-risk-approval", push_decision["required_approval"])

    def test_approved_blocked_run_can_be_resume_eligible_but_still_not_executable(self) -> None:
        events = [
            {
                "name": "git.push.blocked",
                "status": "blocked",
                "risk": {"level": "high", "reason": "Git push can publish local changes."},
                "metadata": {"command": "git push origin main"},
            }
        ]
        request = evaluate_approval_contract(events).required_approvals[0]
        events.append(build_approval_event("run-1", request, "approved", reason="Reviewed diff."))

        data = evaluate_approval_contract(events).to_dict()

        self.assertEqual(data["missing_approvals"], [])
        self.assertTrue(data["resume_eligibility"]["eligible"])
        resume_decision = next(item for item in data["blocked_actions"] if item["action"] == "resume")
        self.assertFalse(resume_decision["allowed"])
        self.assertEqual(resume_decision["required_approval"], "execution-adapter")

    def test_approval_event_shape_is_recordable(self) -> None:
        request = evaluate_approval_contract(
            [
                {
                    "name": "file.write",
                    "status": "done",
                    "risk": {"level": "medium", "reason": "File write can change project state."},
                }
            ]
        ).required_approvals[0]

        event = build_approval_event("run-1", request, "denied", actor="reviewer", reason="Too broad.")

        self.assertEqual(event["name"], "approval.decision")
        self.assertEqual(event["type"], "approval")
        self.assertEqual(event["metadata"]["run_id"], "run-1")
        self.assertEqual(event["metadata"]["decision"], "denied")
        self.assertEqual(event["metadata"]["actor"], "reviewer")


if __name__ == "__main__":
    unittest.main()
