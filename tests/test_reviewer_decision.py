import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop.reviewer_decision import (
    evaluate_reviewer_status,
    read_reviewer_decisions,
    read_reviewer_decisions_summary,
    record_reviewer_decision,
    render_reviewer_decisions_summary,
)


class ReviewerDecisionTests(unittest.TestCase):
    def test_records_decision_and_marks_duplicate_conflict(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            handoff_id = "handoff-1"
            handoff_dir = run_dir / "reviewer_handoff" / handoff_id
            handoff_dir.mkdir(parents=True)
            (handoff_dir / "reviewer_manifest.json").write_text(
                json.dumps({"handoff_id": handoff_id}),
                encoding="utf-8",
            )

            first, first_error = record_reviewer_decision(
                run_dir,
                "run-1",
                handoff_id,
                "request-changes",
                "tester",
                "Need stronger verification.",
                created_at="2026-07-01T00:00:00Z",
            )
            second, second_error = record_reviewer_decision(
                run_dir,
                "run-1",
                handoff_id,
                "approve",
                "tester",
                "Changed my mind.",
                created_at="2026-07-01T00:01:00Z",
            )

            entries = read_reviewer_decisions(run_dir)
            summary = read_reviewer_decisions_summary(run_dir)
            self.assertEqual(first_error, "")
            self.assertEqual(second_error, "")
            self.assertEqual(first["status"], "recorded")
            self.assertEqual(second["status"], "conflict")
            self.assertEqual(second["conflict_with"], [first["decision_id"]])
            self.assertEqual(len(entries), 2)
            self.assertEqual(summary["status_counts"]["recorded"], 1)
            self.assertEqual(summary["status_counts"]["conflict"], 1)
            self.assertIn("latest_reviewer_decision: approve", render_reviewer_decisions_summary(run_dir))

    def test_rejects_missing_handoff(self) -> None:
        with TemporaryDirectory() as temp_dir:
            entry, error = record_reviewer_decision(
                Path(temp_dir),
                "run-1",
                "missing-handoff",
                "block",
                "tester",
                "No matching handoff.",
            )

            self.assertIsNone(entry)
            self.assertIn("handoff-id", error)

    def test_reviewer_status_maps_decisions_to_next_actions(self) -> None:
        self.assertEqual(evaluate_reviewer_status([])["state"], "waiting-review")
        self.assertFalse(evaluate_reviewer_status([])["execution_authority"])

        approved = [{"decision": "approve", "status": "recorded"}]
        self.assertEqual(evaluate_reviewer_status(approved)["state"], "review-passed")
        self.assertTrue(evaluate_reviewer_status(approved)["ready_for_next_loop"])

        changes = [{"decision": "request-changes", "status": "recorded"}]
        self.assertEqual(evaluate_reviewer_status(changes)["state"], "changes-requested")
        self.assertTrue(evaluate_reviewer_status(changes)["ready_for_next_loop"])

        blocked = [{"decision": "block", "status": "recorded"}]
        self.assertEqual(evaluate_reviewer_status(blocked)["state"], "blocked-by-review")
        self.assertFalse(evaluate_reviewer_status(blocked)["ready_for_next_loop"])

        conflict = [{"decision": "approve", "status": "conflict"}]
        self.assertEqual(evaluate_reviewer_status(conflict)["state"], "conflict")
        self.assertFalse(evaluate_reviewer_status(conflict)["ready_for_next_loop"])


if __name__ == "__main__":
    unittest.main()
