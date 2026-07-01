import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop.evidence import write_evidence_manifest
from ai_agent_loop.evidence_bundle import export_evidence_bundle
from ai_agent_loop.reviewer_handoff import export_reviewer_handoff, read_reviewer_handoff_summary


class ReviewerHandoffTests(unittest.TestCase):
    def test_export_reviewer_handoff_writes_read_only_review_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            events = [
                {
                    "name": "shell.run",
                    "status": "done",
                    "metadata": {"command": "echo review"},
                    "risk": {"level": "medium", "reason": "Shell command can change project state."},
                }
            ]
            (run_dir / "goal.json").write_text(
                json.dumps({"description": "Review me", "status": "done", "project": "fixture"}),
                encoding="utf-8",
            )
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            (run_dir / "report.md").write_text("# Report\n\nBody\n", encoding="utf-8")
            (run_dir / "approvals.jsonl").write_text("", encoding="utf-8")
            write_evidence_manifest(run_dir, events)
            bundle = export_evidence_bundle(run_dir, "run-1")

            handoff = export_reviewer_handoff(
                run_dir,
                "run-1",
                approval_readiness="Approval Readiness",
                change_set_critique="Change-set Critique",
            )

            handoff_dir = Path(str(handoff["handoff_dir"]))
            input_path = handoff_dir / "reviewer_input.json"
            prompt_path = handoff_dir / "reviewer_prompt.md"
            manifest_path = handoff_dir / "reviewer_manifest.json"
            reviewer_input = json.loads(input_path.read_text(encoding="utf-8"))
            prompt = prompt_path.read_text(encoding="utf-8")
            summary = read_reviewer_handoff_summary(run_dir)

            self.assertTrue(input_path.exists())
            self.assertTrue(prompt_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertEqual(reviewer_input["run"]["goal"], "Review me")
            self.assertEqual(reviewer_input["evidence_bundle"]["bundle_hash"], bundle["bundle_hash"])
            self.assertIn("Approval Readiness", reviewer_input["approval_readiness"])
            self.assertIn("Do not approve, resume, write, commit, push, delete, or execute commands.", prompt)
            self.assertEqual(summary["handoff_count"], 1)
            self.assertTrue(summary["latest"]["handoff_hash"])


if __name__ == "__main__":
    unittest.main()
