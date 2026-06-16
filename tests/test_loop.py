import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from ai_agent_loop import Agent, RunStore, run_loop


class RunLoopTests(unittest.TestCase):
    def test_run_loop_returns_structured_steps(self) -> None:
        result = run_loop("  Build a tool  ")

        self.assertEqual(result.goal.description, "Build a tool")
        self.assertTrue(result.project)
        self.assertTrue(result.done)
        self.assertEqual([step.name for step in result.steps], [
            "goal",
            "context",
            "assumptions",
            "criteria",
            "plan",
            "act",
            "observe",
            "adjust",
            "verify",
            "critique",
            "report",
        ])

    def test_run_loop_rejects_empty_goal(self) -> None:
        with self.assertRaises(ValueError):
            run_loop("   ")

    def test_agent_persists_run_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store_root = Path(temp_dir) / ".agent"
            result = Agent(store_root=store_root).run("Ship the MVP")
            run_dir = store_root / "runs" / result.run_id

            self.assertTrue((run_dir / "goal.json").exists())
            self.assertTrue((run_dir / "events.jsonl").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertIn("Ship the MVP", (run_dir / "report.md").read_text(encoding="utf-8"))

    def test_run_store_lists_and_reads_run_summary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store_root = Path(temp_dir) / ".agent"
            result = Agent(store_root=store_root).run("Inspect history")
            store = RunStore(store_root)

            runs = store.list_runs()
            summary = store.read_summary(result.run_id)

            self.assertEqual(len(runs), 1)
            self.assertEqual(summary["run_id"], result.run_id)
            self.assertEqual(summary["goal"], "Inspect history")
            self.assertEqual(summary["status"], "done")
            self.assertEqual(summary["project"], result.project)
            self.assertEqual(summary["event_count"], len(result.steps))

    def test_run_store_reads_report(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store_root = Path(temp_dir) / ".agent"
            result = Agent(store_root=store_root).run("Render report")
            report = RunStore(store_root).read_report(result.run_id)

            self.assertIn("# Agent Run", report)
            self.assertIn("Project:", report)
            self.assertIn("## Sharp Review", report)
            self.assertIn("Render report", report)


if __name__ == "__main__":
    unittest.main()
