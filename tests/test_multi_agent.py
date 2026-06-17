import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import MultiAgentRunner, RunStore


class MultiAgentTests(unittest.TestCase):
    def test_multi_agent_run_creates_parent_children_and_reviewer(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("Project context\n", encoding="utf-8")
            (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
            tests_dir = project / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_app.py").write_text("import unittest\n", encoding="utf-8")
            store_root = root / ".agent"

            result = MultiAgentRunner(store_root=str(store_root), project_path=str(project)).run(
                "Assess project readiness"
            )
            store = RunStore(store_root, project_path=project)
            parent_summary = store.read_summary(result.parent_run_id)
            parent_events = store.read_events(result.parent_run_id)
            parent_report = store.read_report(result.parent_run_id)

            self.assertEqual(len(result.child_run_ids), 3)
            self.assertTrue(result.reviewer_run_id)
            self.assertEqual(parent_summary["metadata"]["child_run_ids"], result.child_run_ids)
            self.assertEqual(parent_summary["metadata"]["reviewer_run_id"], result.reviewer_run_id)
            self.assertIn("## Multi-Agent Summary", parent_report)
            self.assertIn("Child runs:", parent_report)
            self.assertIn("Conflict detection:", parent_report)
            self.assertIn("Reviewer decision:", parent_report)
            self.assertIn("Merged summary:", parent_report)
            self.assertIn("multi.child_created", [event["name"] for event in parent_events])
            self.assertIn("multi.reviewer_decision", [event["name"] for event in parent_events])

            all_child_ids = result.child_run_ids + [result.reviewer_run_id]
            for child_run_id in all_child_ids:
                child_summary = store.read_summary(child_run_id)
                child_events = store.read_events(child_run_id)
                child_report = store.read_report(child_run_id)

                self.assertEqual(child_summary["metadata"]["parent_run_id"], result.parent_run_id)
                self.assertTrue((store.run_dir(child_run_id) / "report.md").exists())
                self.assertIn("# Agent Run", child_report)
                forbidden_events = {
                    "file.write",
                    "git.commit",
                    "git.push.blocked",
                    "shell.run",
                }
                self.assertFalse(forbidden_events & {event["name"] for event in child_events})

            for child_run_id in result.child_run_ids:
                self.assertTrue((store.run_dir(child_run_id) / "multi" / "summary.md").exists())
            self.assertTrue((store.run_dir(result.reviewer_run_id) / "multi" / "review.md").exists())

    def test_multi_agent_cli_command_parses_goal(self) -> None:
        from ai_agent_loop.cli import build_parser, normalize_argv

        args = build_parser().parse_args(normalize_argv(["multi", "Assess project"]))

        self.assertEqual(args.command, "multi")
        self.assertEqual(args.goal, "Assess project")


if __name__ == "__main__":
    unittest.main()
