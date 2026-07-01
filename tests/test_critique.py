import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, RunStore, build_change_set_critique, build_critique, render_change_set_critique, render_critique
from ai_agent_loop.tools import ShellTools


class CritiqueTests(unittest.TestCase):
    def test_successful_run_gets_structured_critique(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store_root = Path(temp_dir) / ".agent"
            run = Agent(store_root=store_root).run("Critique success")
            store = RunStore(store_root)

            rendered = render_critique(store.read_events(run.run_id))
            report = store.read_report(run.run_id)

            self.assertIn("### Scope control", rendered)
            self.assertIn("### Product alignment", rendered)
            self.assertIn("### Verification quality", rendered)
            self.assertIn("### Risk review", rendered)
            self.assertIn("### Next action", rendered)
            self.assertIn("Verification is present", rendered)
            self.assertIn("## Change-set Critique", report)
            self.assertIn("### Maintainability", report)

    def test_blocked_run_critique_mentions_blocked_decision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Critique blocked")
            store = RunStore(store_root, project_path=project)

            ShellTools(store, run.run_id).run("git push origin main")
            critique = build_critique(store.read_events(run.run_id))
            report = store.read_report(run.run_id)

            self.assertIn("blocked", critique["Verification quality"])
            self.assertIn("Risk handling worked", critique["Risk review"])
            self.assertIn("### Risk review", report)

    def test_failed_run_critique_mentions_failed_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Critique failed")
            store = RunStore(store_root, project_path=project)
            command = f'"{sys.executable}" -c "raise SystemExit(2)"'

            ShellTools(store, run.run_id).run(command)
            critique = build_critique(store.read_events(run.run_id))

            self.assertIn("failed event", critique["Verification quality"])
            self.assertIn("Inspect failed tool output", critique["Next action"])

    def test_change_set_critique_reviews_diff_evidence(self) -> None:
        critique = build_change_set_critique(
            ["src/ai_agent_loop/critique.py", "tests/test_critique.py"],
            diff_text="+def example():\n+    return True\n",
            test_summary="79 tests OK",
            risk_summary="reserved no execution",
            smoke_summary="Chrome smoke OK",
        )
        rendered = render_change_set_critique(
            ["src/ai_agent_loop/critique.py", "tests/test_critique.py"],
            test_summary="79 tests OK",
            risk_summary="reserved no execution",
            smoke_summary="Chrome smoke OK",
        )

        self.assertIn("bounded", critique["Scope control"])
        self.assertIn("agent loop source", critique["Product alignment"])
        self.assertIn("strong", critique["Verification quality"])
        self.assertIn("Risk is controlled", critique["Risk review"])
        self.assertIn("### Maintainability", rendered)

    def test_change_set_critique_flags_private_files(self) -> None:
        critique = build_change_set_critique(["AGENTS.md"])

        self.assertIn("private files", critique["Scope control"])
        self.assertIn("private files", critique["Risk review"])

    def test_change_set_critique_accepts_hyphenated_no_execution_evidence(self) -> None:
        critique = build_change_set_critique(
            ["src/ai_agent_loop/reviewer_handoff.py"],
            diff_text="+No approve, resume, write, commit, push, or delete action was executed.",
            risk_summary="reviewer handoff is read-only and no-execution",
        )

        self.assertIn("Risk is controlled", critique["Risk review"])


if __name__ == "__main__":
    unittest.main()
