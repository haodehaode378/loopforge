import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from ai_agent_loop import Agent, ProjectRegistry, RunStore, run_loop


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
            run_dir = store_root / "projects" / result.project_id / "runs" / result.run_id

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
            self.assertIn("Project ID:", report)
            self.assertIn("Project Path:", report)
            self.assertIn("## Sharp Review", report)
            self.assertIn("Render report", report)

    def test_projects_have_isolated_run_histories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store_root = root / ".agent"
            project_a = root / "project-a"
            project_b = root / "project-b"
            project_a.mkdir()
            project_b.mkdir()

            run_a = Agent(store_root=store_root, project_path=project_a).run("Task A")
            run_b = Agent(store_root=store_root, project_path=project_b).run("Task B")

            runs_a = RunStore(store_root, project_path=project_a).list_runs()
            runs_b = RunStore(store_root, project_path=project_b).list_runs()

            self.assertEqual([item["run_id"] for item in runs_a], [run_a.run_id])
            self.assertEqual([item["run_id"] for item in runs_b], [run_b.run_id])
            self.assertNotEqual(run_a.project_id, run_b.project_id)

    def test_project_registry_writes_metadata_and_memory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store_root = root / ".agent"
            project_dir = root / "sample-project"
            project_dir.mkdir()

            registry = ProjectRegistry(store_root)
            project = registry.ensure_project(project_dir)
            project_store_dir = registry.project_dir(project)

            self.assertTrue((store_root / "projects.json").exists())
            self.assertTrue((project_store_dir / "project.json").exists())
            self.assertTrue((project_store_dir / "memory.json").exists())
            self.assertIn(project.id, (store_root / "projects.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
