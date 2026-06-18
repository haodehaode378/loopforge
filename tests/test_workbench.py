import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, MultiAgentRunner, RunStore
from ai_agent_loop.approval import evaluate_approval_contract
from ai_agent_loop.cli import build_parser, normalize_argv
from ai_agent_loop.evidence import write_evidence_manifest
from ai_agent_loop.ledger import approval_scope, build_ledger_decision_record
from ai_agent_loop.tools import GitTools, ShellTools
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
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "LoopForge Test"], cwd=project, check=True)
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True, capture_output=True)
            store_root = root / ".agent"

            done = Agent(store_root=store_root, project_path=project).run("Render workbench")
            done_store = RunStore(store_root, project_path=project)
            ShellTools(done_store, done.run_id).run("echo workbench-evidence")
            done_events = done_store.read_events(done.run_id)
            request = evaluate_approval_contract(done_events).required_approvals[0]
            ledger_entry = build_ledger_decision_record(
                done.run_id,
                request,
                actor="reviewer",
                created_at="2026-06-18T00:00:00Z",
                expires_at="2999-01-01T00:00:00Z",
                scope=approval_scope(done_events),
                decision="approved",
                reason="Reviewed shell output.",
            )
            (done_store.run_dir(done.run_id) / "approvals.jsonl").write_text(
                json.dumps(ledger_entry, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            write_evidence_manifest(done_store.run_dir(done.run_id), done_events)
            (project / "app.py").write_text("print('changed')\n", encoding="utf-8")
            diff_run = Agent(store_root=store_root, project_path=project).run("Review diff")
            diff_store = RunStore(store_root, project_path=project)
            GitTools(diff_store, diff_run.run_id).diff()
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
            self.assertIn(diff_run.run_id, run_ids)
            self.assertIn(blocked.run_id, run_ids)
            self.assertIn(multi.parent_run_id, run_ids)
            self.assertGreaterEqual(project_data["analytics"]["status_counts"]["blocked"], 1)
            self.assertGreaterEqual(project_data["analytics"]["command_count"], 1)

            parent = next(run for run in project_data["runs"] if run["run_id"] == multi.parent_run_id)
            self.assertEqual(parent["child_run_ids"], multi.child_run_ids)
            self.assertIn("Multi-Agent Summary", parent["sections"])
            self.assertIn("Sharp Review", parent["sections"])

            done_run = next(run for run in project_data["runs"] if run["run_id"] == done.run_id)
            self.assertEqual(done_run["provider"]["provider"], "Deterministic Local")
            self.assertIn("workbench-evidence", done_run["command_outputs"][0]["stdout"]["content"])
            self.assertTrue(done_run["approval"]["required_approvals"])
            self.assertTrue(done_run["approval"]["missing_approvals"])
            self.assertTrue(done_run["approval"]["blocked_actions"])
            self.assertEqual(done_run["approval"]["ledger"]["status"], "present")
            self.assertEqual(len(done_run["approval"]["ledger"]["active_approvals"]), 1)
            self.assertEqual(done_run["approval"]["ledger"]["scope_replay"][0]["replay_status"], "matched")
            self.assertEqual(done_run["approval"]["ledger"]["scope_replay"][0]["signature_status"], "unsigned")
            self.assertTrue(done_run["approval"]["ledger"]["execution_ready_approvals"])
            self.assertTrue(done_run["approval"]["scope_evidence"]["has_evidence"])
            self.assertEqual(done_run["approval"]["scope_evidence"]["manifest_status"], "present")
            self.assertEqual(done_run["approval"]["scope_evidence"]["scope_replay_source"], "manifest")
            self.assertIn("execution_gate", done_run["approval"])
            self.assertEqual(done_run["approval"]["execution_gate"]["executable_actions"], [])
            self.assertEqual(done_run["evidence_manifest"]["status"], "present")
            self.assertEqual(done_run["evidence_manifest"]["integrity_status"], "verified")
            self.assertTrue(done_run["evidence_manifest"]["core_hashes"]["events.jsonl"])

            diff_data = next(run for run in project_data["runs"] if run["run_id"] == diff_run.run_id)
            self.assertIn("app.py", diff_data["changed_files"])
            self.assertIn("print('changed')", diff_data["diff"]["content"])
            self.assertTrue(diff_data["approval"]["ready_for_review"])
            self.assertEqual(diff_data["approval"]["executable_actions"], [])
            self.assertIn("inspect", diff_data["approval"]["eligible_actions"])
            self.assertFalse(diff_data["approval"]["resume_eligibility"]["eligible"])
            self.assertIn("Approval Readiness", diff_data["sections"])
            self.assertIn("Required approvals", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Missing approvals", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Blocked actions", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Resume eligibility", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Ledger status", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Scope replay", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Execution readiness", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Execution gate", diff_data["sections"]["Approval Readiness"])
            self.assertIn("Evidence manifest", diff_data["sections"]["Approval Readiness"])
            self.assertTrue(diff_data["risk_decisions"])

            blocked_run = next(run for run in project_data["runs"] if run["run_id"] == blocked.run_id)
            self.assertEqual(blocked_run["effective_status"], "blocked")
            self.assertIn("Blocked Reason", blocked_run["sections"])

            self.assertIn("项目", html)
            self.assertIn("运行历史", html)
            self.assertIn("事件时间线", html)
            self.assertIn("图表", html)
            self.assertIn("Provider 指标", html)
            self.assertIn("命令输出", html)
            self.assertIn("事件 JSON", html)
            self.assertIn("section 深链", html)
            self.assertIn("审批骨架", html)
            self.assertIn("所需审批", html)
            self.assertIn("缺失审批", html)
            self.assertIn("可展示动作", html)
            self.assertIn("被阻止动作", html)
            self.assertIn("恢复资格", html)
            self.assertIn("审批账本", html)
            self.assertIn("有效审批", html)
            self.assertIn("过期审批", html)
            self.assertIn("撤销审批", html)
            self.assertIn("Scope replay", html)
            self.assertIn("Execution ready", html)
            self.assertIn("Execution gate", html)
            self.assertIn("Evidence manifest", html)
            self.assertIn("变更文件", html)
            self.assertIn("风险决策", html)
            self.assertIn("Diff 查看器", html)
            self.assertIn("disabled-action", html)
            self.assertIn('"reserved_actions": ["approve", "resume", "write", "commit", "push", "delete"]', html)
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
