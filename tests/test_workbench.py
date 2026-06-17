import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, MultiAgentRunner, RunStore
from ai_agent_loop.cli import build_parser, normalize_argv
from ai_agent_loop.tools import ShellTools
from ai_agent_loop.workbench import build_workbench_snapshot, render_workbench_html


class WorkbenchTests(unittest.TestCase):
    def test_workbench_snapshot_reads_projects_runs_and_reports(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("Project docs\n", encoding="utf-8")
            (project / "app.py").write_text("print('hi')\n", encoding="utf-8")
            tests_dir = project / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_app.py").write_text("import unittest\n", encoding="utf-8")
            store_root = root / ".agent"

            done = Agent(store_root=store_root, project_path=project).run("Render workbench")
            blocked = Agent(store_root=store_root, project_path=project).run("Blocked workbench")
            ShellTools(RunStore(store_root, project_path=project), blocked.run_id).run("git push origin main")
            multi = MultiAgentRunner(store_root=str(store_root), project_path=str(project)).run(
                "Assess workbench"
            )

            snapshot = build_workbench_snapshot(store_root)
            html = render_workbench_html(snapshot)

            self.assertEqual(snapshot["totals"]["projects"], 1)
            self.assertGreaterEqual(snapshot["totals"]["runs"], 3)
            self.assertGreaterEqual(snapshot["totals"]["blocked"], 1)
            project_data = snapshot["projects"][0]
            run_ids = {run["run_id"] for run in project_data["runs"]}
            self.assertIn(done.run_id, run_ids)
            self.assertIn(blocked.run_id, run_ids)
            self.assertIn(multi.parent_run_id, run_ids)

            parent = next(run for run in project_data["runs"] if run["run_id"] == multi.parent_run_id)
            self.assertEqual(parent["child_run_ids"], multi.child_run_ids)
            self.assertIn("Multi-Agent Summary", parent["sections"])
            self.assertIn("Sharp Review", parent["sections"])

            blocked_run = next(run for run in project_data["runs"] if run["run_id"] == blocked.run_id)
            self.assertEqual(blocked_run["effective_status"], "blocked")
            self.assertIn("Blocked Reason", blocked_run["sections"])

            self.assertIn("项目", html)
            self.assertIn("运行历史", html)
            self.assertIn("事件时间线", html)
            self.assertIn("Multi-Agent Summary", html)
            self.assertIn("Git Summary", html)
            self.assertIn("Automation Summary", html)
            self.assertIn("Critique", html)

    def test_workbench_command_parses_snapshot_flag(self) -> None:
        args = build_parser().parse_args(
            normalize_argv(["workbench", "--host", "127.0.0.1", "--port", "9999", "--snapshot"])
        )

        self.assertEqual(args.command, "workbench")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 9999)
        self.assertTrue(args.snapshot)


if __name__ == "__main__":
    unittest.main()
