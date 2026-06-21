import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ai_agent_loop import Agent, RunStore
from ai_agent_loop.approval import evaluate_approval_contract
from ai_agent_loop.cli import build_parser, main, normalize_argv
from ai_agent_loop.ledger import approval_requests_with_ids, approval_scope, read_approval_ledger
from ai_agent_loop.tools import ShellTools


class CliArgTests(unittest.TestCase):
    def test_normalize_argv_keeps_explicit_command(self) -> None:
        self.assertEqual(
            normalize_argv(["inspect", "run-1"]),
            ["inspect", "run-1"],
        )

    def test_normalize_argv_converts_legacy_goal(self) -> None:
        self.assertEqual(
            normalize_argv(["Ship the MVP"]),
            ["run", "Ship the MVP"],
        )

    def test_normalize_argv_skips_store_value(self) -> None:
        self.assertEqual(
            normalize_argv(["--store", "tmp-runs", "inspect"]),
            ["--store", "tmp-runs", "inspect"],
        )

    def test_normalize_argv_skips_project_value(self) -> None:
        self.assertEqual(
            normalize_argv(["--project", "sample-project", "inspect"]),
            ["--project", "sample-project", "inspect"],
        )

    def test_normalize_argv_converts_legacy_goal_after_store(self) -> None:
        self.assertEqual(
            normalize_argv(["--store", "tmp-runs", "Ship the MVP"]),
            ["--store", "tmp-runs", "run", "Ship the MVP"],
        )

    def test_shell_tool_command_does_not_override_top_level_command(self) -> None:
        args = build_parser().parse_args(normalize_argv(["tool", "shell", "python --version"]))

        self.assertEqual(args.command, "tool")
        self.assertEqual(args.tool_command, "shell")
        self.assertEqual(args.shell_command, "python --version")

    def test_run_can_require_model_provider(self) -> None:
        args = build_parser().parse_args(normalize_argv(["run", "--require-model", "Ship"]))

        self.assertEqual(args.command, "run")
        self.assertTrue(args.require_model)
        self.assertEqual(args.goal, "Ship")

    def test_run_can_enable_auto_with_test_command(self) -> None:
        args = build_parser().parse_args(
            normalize_argv(["run", "--auto", "--test-command", "python -m unittest", "Ship"])
        )

        self.assertEqual(args.command, "run")
        self.assertTrue(args.auto)
        self.assertEqual(args.test_command, "python -m unittest")
        self.assertEqual(args.goal, "Ship")

    def test_git_tool_commit_parses_message(self) -> None:
        args = build_parser().parse_args(
            normalize_argv(["tool", "git", "commit", "Save work"])
        )

        self.assertEqual(args.command, "tool")
        self.assertEqual(args.tool_command, "git")
        self.assertEqual(args.git_command, "commit")
        self.assertEqual(args.message, "Save work")

    def test_git_tool_push_parses_target(self) -> None:
        args = build_parser().parse_args(
            normalize_argv(["tool", "git", "push", "origin", "feature"])
        )

        self.assertEqual(args.tool_command, "git")
        self.assertEqual(args.git_command, "push")
        self.assertEqual(args.remote, "origin")
        self.assertEqual(args.branch, "feature")

    def test_resume_command_is_reserved(self) -> None:
        args = build_parser().parse_args(normalize_argv(["resume", "run-1"]))

        self.assertEqual(args.command, "resume")
        self.assertEqual(args.run_id, "run-1")

    def test_critique_command_parses_run_id(self) -> None:
        args = build_parser().parse_args(normalize_argv(["critique", "run-1"]))

        self.assertEqual(args.command, "critique")
        self.assertEqual(args.critique_command, "show")
        self.assertEqual(args.run_id, "run-1")

    def test_critique_changes_command_parses_summaries(self) -> None:
        args = build_parser().parse_args(
            normalize_argv(["critique", "changes", "--tests", "79 tests OK", "--risk", "reserved no execution"])
        )

        self.assertEqual(args.command, "critique")
        self.assertEqual(args.critique_command, "changes")
        self.assertEqual(args.tests, "79 tests OK")
        self.assertEqual(args.risk, "reserved no execution")

    def test_execution_command_parses_run_id(self) -> None:
        args = build_parser().parse_args(normalize_argv(["execution", "run-1"]))

        self.assertEqual(args.command, "execution")
        self.assertEqual(args.run_id, "run-1")

    def test_critique_changes_reads_current_git_diff(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "LoopForge Test"], cwd=project, check=True)
            (project / "app.py").write_text("print('hi')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True, capture_output=True)
            (project / "app.py").write_text("print('changed')\n", encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--project",
                        str(project),
                        "critique",
                        "changes",
                        "--tests",
                        "79 tests OK",
                        "--risk",
                        "reserved no execution",
                        "--smoke",
                        "Chrome smoke OK",
                    ]
                )

            output = stdout.getvalue()
            self.assertIn("### Scope control", output)
            self.assertIn("public changed file", output)
            self.assertIn("Verification is strong", output)
            self.assertIn("Risk is controlled", output)

    def test_approval_command_parses_run_id(self) -> None:
        args = build_parser().parse_args(normalize_argv(["approval", "run-1"]))

        self.assertEqual(args.command, "approval")
        self.assertEqual(args.approval_command, "show")
        self.assertEqual(args.run_id, "run-1")

    def test_approval_gate_command_parses_record_flag(self) -> None:
        args = build_parser().parse_args(normalize_argv(["approval", "gate", "run-1", "--record"]))

        self.assertEqual(args.command, "approval")
        self.assertEqual(args.approval_command, "gate")
        self.assertEqual(args.run_id, "run-1")
        self.assertTrue(args.record)

    def test_approval_revoke_command_parses_decision_id(self) -> None:
        args = build_parser().parse_args(
            normalize_argv(["approval", "revoke", "run-1", "--decision-id", "dec-1", "--actor", "tester", "--reason", "Scope changed"])
        )

        self.assertEqual(args.command, "approval")
        self.assertEqual(args.approval_command, "revoke")
        self.assertEqual(args.run_id, "run-1")
        self.assertEqual(args.decision_id, "dec-1")

    def test_approval_decide_records_decision_without_execution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            result = Agent(store_root=store_root, project_path=project).run("Approval test")
            run_store = RunStore(store_root, project_path=project)
            ShellTools(run_store, result.run_id).run("echo approval")
            events = run_store.read_events(result.run_id)
            request = approval_requests_with_ids(
                result.run_id,
                evaluate_approval_contract(events),
                approval_scope(events),
            )[0]

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "decide",
                        result.run_id,
                        "--request-id",
                        str(request["request_id"]),
                        "--decision",
                        "approve",
                        "--actor",
                        "tester",
                        "--reason",
                        "Reviewed output.",
                        "--expires-at",
                        "2999-01-01T00:00:00Z",
                    ]
                )

            entries = read_approval_ledger(run_store.run_dir(result.run_id))
            self.assertIn("decision_recorded: true", stdout.getvalue())
            self.assertIn("No approval, resume, write, commit, push, or delete action was executed.", stdout.getvalue())
            self.assertEqual(entries[0]["decision"], "approved")
            self.assertEqual(entries[0]["actor"], "tester")

    def test_execution_command_shows_adapter_contract_without_execution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            result = Agent(store_root=store_root, project_path=project).run("Execution adapter contract")
            run_store = RunStore(store_root, project_path=project)
            ShellTools(run_store, result.run_id).run("echo adapter")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "execution",
                        result.run_id,
                    ]
                )

            output = stdout.getvalue()
            self.assertIn("execution_adapter_contract:", output)
            self.assertIn("reserved execution adapter contract", output)
            self.assertIn('"executable_actions": []', output)
            self.assertIn("No approval, resume, write, commit, push, or delete action was executed.", output)

    def test_approval_decide_rejects_duplicate_active_decision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            result = Agent(store_root=store_root, project_path=project).run("Approval duplicate")
            run_store = RunStore(store_root, project_path=project)
            ShellTools(run_store, result.run_id).run("echo approval")
            events = run_store.read_events(result.run_id)
            request = approval_requests_with_ids(
                result.run_id,
                evaluate_approval_contract(events),
                approval_scope(events),
            )[0]
            argv = [
                "--store",
                str(store_root),
                "--project",
                str(project),
                "approval",
                "decide",
                result.run_id,
                "--request-id",
                str(request["request_id"]),
                "--decision",
                "approve",
                "--actor",
                "tester",
                "--reason",
                "Reviewed output.",
                "--expires-at",
                "2999-01-01T00:00:00Z",
            ]
            with redirect_stdout(io.StringIO()):
                main(argv)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(argv)

            entries = read_approval_ledger(run_store.run_dir(result.run_id))
            self.assertEqual(len(entries), 1)
            self.assertIn("decision_recorded: false", stdout.getvalue())
            self.assertIn("conflict", stdout.getvalue())

    def test_approval_show_prints_scope_replay_and_execution_readiness(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            result = Agent(store_root=store_root, project_path=project).run("Approval show")
            run_store = RunStore(store_root, project_path=project)
            ShellTools(run_store, result.run_id).run("echo approval")
            events = run_store.read_events(result.run_id)
            request = approval_requests_with_ids(
                result.run_id,
                evaluate_approval_contract(events),
                approval_scope(events),
            )[0]
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "decide",
                        result.run_id,
                        "--request-id",
                        str(request["request_id"]),
                        "--decision",
                        "approve",
                        "--actor",
                        "tester",
                        "--reason",
                        "Reviewed output.",
                        "--expires-at",
                        "2999-01-01T00:00:00Z",
                    ]
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "show",
                        result.run_id,
                    ]
                )

            output = stdout.getvalue()
            self.assertIn("evidence_manifest:", output)
            self.assertIn('"status": "present"', output)
            self.assertIn('"integrity_status": "verified"', output)
            self.assertIn('"scope_replay_source": "manifest"', output)
            self.assertIn("scope_evidence:", output)
            self.assertIn("scope_replay:", output)
            self.assertIn("execution_ready_approvals:", output)
            self.assertIn("execution_gate:", output)
            self.assertIn('"executable": false', output)
            self.assertIn('"replay_status": "matched"', output)
            self.assertIn('"signature_status": "unsigned"', output)
            self.assertIn('"actor_id": "actor_', output)
            self.assertIn('"actor_kind": "local-user"', output)
            self.assertIn('"signature_algorithm": "placeholder-local-audit-v1"', output)
            self.assertIn('"signature_payload_hash":', output)

    def test_approval_gate_records_audit_event_without_execution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            result = Agent(store_root=store_root, project_path=project).run("Gate audit")
            run_store = RunStore(store_root, project_path=project)
            ShellTools(run_store, result.run_id).run("echo gate")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "gate",
                        result.run_id,
                        "--record",
                    ]
                )

            events = run_store.read_events(result.run_id)
            gate_events = [event for event in events if event.get("name") == "execution.gate.evaluated"]
            output = stdout.getvalue()
            self.assertEqual(len(gate_events), 1)
            self.assertIn("gate_event_recorded: true", output)
            self.assertIn("No approval, resume, write, commit, push, or delete action was executed.", output)
            self.assertEqual(gate_events[0]["metadata"]["executable_actions"], [])
            self.assertIn("Gate audit", run_store.read_report(result.run_id))

    def test_approval_revoke_records_revocation_without_execution(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            store_root = root / ".agent"
            result = Agent(store_root=store_root, project_path=project).run("Approval revoke")
            run_store = RunStore(store_root, project_path=project)
            ShellTools(run_store, result.run_id).run("echo approval")
            events = run_store.read_events(result.run_id)
            request = approval_requests_with_ids(
                result.run_id,
                evaluate_approval_contract(events),
                approval_scope(events),
            )[0]
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "decide",
                        result.run_id,
                        "--request-id",
                        str(request["request_id"]),
                        "--decision",
                        "approve",
                        "--actor",
                        "tester",
                        "--reason",
                        "Reviewed output.",
                        "--expires-at",
                        "2999-01-01T00:00:00Z",
                    ]
                )
            decision_id = read_approval_ledger(run_store.run_dir(result.run_id))[0]["decision_id"]

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "revoke",
                        result.run_id,
                        "--decision-id",
                        str(decision_id),
                        "--actor",
                        "tester",
                        "--reason",
                        "Scope changed.",
                    ]
                )

            entries = read_approval_ledger(run_store.run_dir(result.run_id))
            output = stdout.getvalue()
            self.assertEqual(len(entries), 2)
            self.assertIn("revocation_recorded: true", output)
            self.assertIn("No approval, resume, write, commit, push, or delete action was executed.", output)
            self.assertIn("Revoked approvals", run_store.read_report(result.run_id))
            self.assertIn("Ledger integrity", run_store.read_report(result.run_id))
            self.assertIn(str(decision_id), run_store.read_report(result.run_id))

            duplicate = io.StringIO()
            with redirect_stdout(duplicate):
                main(
                    [
                        "--store",
                        str(store_root),
                        "--project",
                        str(project),
                        "approval",
                        "revoke",
                        result.run_id,
                        "--decision-id",
                        str(decision_id),
                        "--actor",
                        "tester",
                        "--reason",
                        "Again.",
                    ]
                )

            self.assertIn("revocation_recorded: false", duplicate.getvalue())
            self.assertIn("already revoked", duplicate.getvalue())


if __name__ == "__main__":
    unittest.main()
