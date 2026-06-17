import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, RunStore


class AutonomousRunTests(unittest.TestCase):
    def test_auto_run_adjusts_once_and_reports_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "fixture"
            project.mkdir()
            (project / ".loopforge-fixture").write_text("ok", encoding="utf-8")
            (project / "README.md").write_text("fixture project", encoding="utf-8")
            tests_dir = project / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_generated.py").write_text(
                "\n".join(
                    [
                        "from pathlib import Path",
                        "import unittest",
                        "",
                        "class GeneratedContentTest(unittest.TestCase):",
                        "    def test_generated_content(self):",
                        "        self.assertEqual(Path('generated.txt').read_text(encoding='utf-8'), 'pass\\n')",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (project / ".loopforge-task.json").write_text(
                json.dumps(
                    {
                        "target_file": "generated.txt",
                        "initial_content": "fail\n",
                        "adjusted_content": "pass\n",
                        "test_command": f'"{sys.executable}" -m unittest discover -s tests',
                        "context_files": ["README.md"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            store_root = root / ".agent"

            result = Agent(store_root=store_root, project_path=project).run(
                "Implement fixture change",
                auto=True,
            )
            store = RunStore(store_root, project_path=project)
            events = store.read_events(result.run_id)
            report = store.read_report(result.run_id)

            self.assertEqual((project / "generated.txt").read_text(encoding="utf-8"), "pass\n")
            self.assertEqual(store.read_summary(result.run_id)["effective_status"], "done")
            self.assertEqual([event["name"] for event in events].count("file.write"), 2)
            self.assertEqual([event["name"] for event in events].count("shell.run"), 2)
            self.assertIn("automation.adjust", [event["name"] for event in events])
            self.assertIn("Changed files:", report)
            self.assertIn("Commands:", report)
            self.assertIn("Verification:", report)
            self.assertIn("Risks:", report)
            self.assertIn("Next steps:", report)
            self.assertIn("- provider: Deterministic Local", report)
            self.assertIn("Verification recovered after adjustment", report)

    def test_auto_run_blocks_outside_fixture_project(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "real-project"
            project.mkdir()
            store_root = root / ".agent"

            result = Agent(store_root=store_root, project_path=project).run(
                "Do not write outside fixture",
                auto=True,
            )
            store = RunStore(store_root, project_path=project)
            summary = store.read_summary(result.run_id)
            events = store.read_events(result.run_id)

            self.assertEqual(summary["effective_status"], "blocked")
            self.assertEqual(events[-1]["name"], "automation.blocked")
            self.assertFalse((project / "loopforge_auto.txt").exists())


if __name__ == "__main__":
    unittest.main()
