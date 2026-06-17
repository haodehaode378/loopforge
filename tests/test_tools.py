import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from ai_agent_loop import Agent, RunStore
from ai_agent_loop.risk import classify_file_delete, classify_git_push
from ai_agent_loop.tools import FileTools, ShellTools


class ToolTests(unittest.TestCase):
    def test_file_tools_record_read_and_search_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello", encoding="utf-8")
            (project / "app.py").write_text("print('hi')", encoding="utf-8")
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Tool test")
            store = RunStore(store_root, project_path=project)
            tools = FileTools(store, run.run_id)

            self.assertEqual(tools.read_file("README.md"), "hello")
            self.assertEqual(tools.search_files("*.py"), ["app.py"])

            events = store.read_events(run.run_id)
            self.assertEqual(events[-2]["name"], "file.read")
            self.assertEqual(events[-2]["risk"]["level"], "low")
            self.assertEqual(events[-1]["name"], "file.search")
            self.assertEqual(events[-1]["metadata"]["matches"], ["app.py"])

    def test_file_read_rejects_paths_outside_project(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            (root / "secret.txt").write_text("secret", encoding="utf-8")
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Tool test")
            tools = FileTools(RunStore(store_root, project_path=project), run.run_id)

            with self.assertRaises(ValueError):
                tools.read_file("../secret.txt")

    def test_shell_tool_records_output_artifacts_and_risk(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Shell test")
            store = RunStore(store_root, project_path=project)
            command = f'"{sys.executable}" -c "print(\'hello\')"'

            result = ShellTools(store, run.run_id).run(command)

            self.assertEqual(result.exit_code, 0)
            self.assertIn("hello", result.stdout)
            events = store.read_events(run.run_id)
            event = events[-1]
            self.assertEqual(event["name"], "shell.run")
            self.assertEqual(event["status"], "done")
            self.assertEqual(event["risk"]["level"], "medium")
            self.assertTrue(Path(event["artifacts"]["stdout"]).exists())
            self.assertTrue(Path(event["artifacts"]["stderr"]).exists())
            self.assertIn("hello", Path(event["artifacts"]["stdout"]).read_text(encoding="utf-8"))

    def test_risk_interfaces_define_destructive_operations_without_execution(self) -> None:
        delete_risk = classify_file_delete("src/app.py")
        push_risk = classify_git_push("origin", "main")

        self.assertEqual(delete_risk.level, "high")
        self.assertTrue(delete_risk.requires_confirmation)
        self.assertEqual(push_risk.level, "high")
        self.assertTrue(push_risk.requires_confirmation)


if __name__ == "__main__":
    unittest.main()
