import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, RunStore
from ai_agent_loop.policy import evaluate_risk, should_block_for_repeated_failures
from ai_agent_loop.risk import classify_shell_command
from ai_agent_loop.tools import ShellTools


class PolicyTests(unittest.TestCase):
    def test_evaluate_risk_blocks_high_risk_shell_command(self) -> None:
        risk = classify_shell_command("git push origin main")
        decision = evaluate_risk(risk.to_dict())

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.action, "block")

    def test_high_risk_shell_command_is_not_executed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Policy test")
            store = RunStore(store_root, project_path=project)

            result = ShellTools(store, run.run_id).run("git push origin main")

            self.assertEqual(result.exit_code, -1)
            events = store.read_events(run.run_id)
            self.assertEqual(events[-1]["name"], "policy.blocked")
            self.assertEqual(events[-1]["status"], "blocked")
            self.assertEqual(store.read_summary(run.run_id)["effective_status"], "blocked")

    def test_three_consecutive_failures_block_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Failure test")
            store = RunStore(store_root, project_path=project)
            command = f'"{sys.executable}" -c "raise SystemExit(2)"'

            for _ in range(3):
                ShellTools(store, run.run_id).run(command)

            events = store.read_events(run.run_id)
            self.assertTrue(should_block_for_repeated_failures(events[:-1]))
            self.assertEqual(events[-1]["status"], "blocked")
            summary = store.read_summary(run.run_id)
            self.assertEqual(summary["effective_status"], "blocked")
            self.assertIn("Three consecutive failures", summary["blocked_reason"])
            report = store.read_report(run.run_id)
            self.assertIn("Status: blocked", report)
            self.assertIn("## Blocked Reason", report)


if __name__ == "__main__":
    unittest.main()
