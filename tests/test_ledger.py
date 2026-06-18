import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop.approval import evaluate_approval_contract
from ai_agent_loop.ledger import (
    approval_scope,
    approval_scope_evidence,
    build_ledger_decision_record,
    build_ledger_revocation_record,
    read_approval_ledger,
    request_id,
    scope_hash,
    summarize_ledger,
)


class ApprovalLedgerTests(unittest.TestCase):
    def test_scope_hash_and_request_id_are_stable(self) -> None:
        request = evaluate_approval_contract(
            [
                {
                    "name": "file.write",
                    "status": "done",
                    "risk": {"level": "medium", "reason": "File write can change project state."},
                }
            ]
        ).required_approvals[0]

        self.assertEqual(scope_hash(["b", "a"]), scope_hash(["a", "b"]))
        self.assertEqual(
            request_id("run-1", request, ["app.py"]),
            request_id("run-1", request, ["app.py"]),
        )

    def test_ledger_status_groups_active_expired_and_revoked_entries(self) -> None:
        request = evaluate_approval_contract(
            [
                {
                    "name": "git.push.blocked",
                    "status": "blocked",
                    "risk": {"level": "high", "reason": "Git push can publish local changes."},
                    "metadata": {"command": "git push origin main"},
                }
            ]
        ).required_approvals[0]
        active = build_ledger_decision_record(
            "run-1",
            request,
            actor="alice",
            created_at="2026-06-18T00:00:00Z",
            expires_at="2999-01-01T00:00:00Z",
            scope=["app.py"],
            decision="approved",
            reason="Reviewed diff.",
        )
        expired = build_ledger_decision_record(
            "run-1",
            request,
            actor="bob",
            created_at="2020-01-01T00:00:00Z",
            expires_at="2020-01-02T00:00:00Z",
            scope=["app.py"],
            decision="approved",
            reason="Old approval.",
        )
        revoked = build_ledger_revocation_record(
            active["decision_id"],
            actor="alice",
            created_at="2026-06-18T01:00:00Z",
            reason="Scope changed.",
        )

        summary = summarize_ledger([active, expired, revoked])

        self.assertEqual(summary["entry_count"], 3)
        self.assertEqual(len(summary["active_approvals"]), 0)
        self.assertEqual(len(summary["expired_approvals"]), 1)
        self.assertEqual(len(summary["revoked_approvals"]), 2)

    def test_ledger_status_groups_denied_and_conflict_entries(self) -> None:
        request = evaluate_approval_contract(
            [
                {
                    "name": "file.write",
                    "status": "done",
                    "risk": {"level": "medium", "reason": "File write can change project state."},
                }
            ]
        ).required_approvals[0]
        approved = build_ledger_decision_record(
            "run-1",
            request,
            actor="alice",
            created_at="2026-06-18T00:00:00Z",
            expires_at="2999-01-01T00:00:00Z",
            scope=["app.py"],
            decision="approved",
            reason="Reviewed.",
        )
        denied = build_ledger_decision_record(
            "run-1",
            request,
            actor="bob",
            created_at="2026-06-18T01:00:00Z",
            expires_at="2999-01-01T00:00:00Z",
            scope=["other.py"],
            decision="denied",
            reason="Too broad.",
        )

        summary = summarize_ledger([approved, approved, denied])

        self.assertEqual(len(summary["conflict_approvals"]), 2)
        self.assertEqual(len(summary["denied_approvals"]), 1)

    def test_read_approval_ledger_reads_jsonl_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            entry = {
                "entry_type": "decision",
                "request_id": "req_1",
                "decision_id": "dec_1",
                "actor": "alice",
                "created_at": "2026-06-18T00:00:00Z",
                "expires_at": "2999-01-01T00:00:00Z",
                "scope_hash": "abc",
                "decision": "approved",
                "reason": "Reviewed.",
            }
            (run_dir / "approvals.jsonl").write_text(
                json.dumps(entry, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            entries = read_approval_ledger(run_dir)

            self.assertEqual(entries[0]["decision_id"], "dec_1")
            self.assertEqual(entries[0]["status"], "active")

    def test_scope_replay_marks_execution_ready_only_when_matched(self) -> None:
        events = [
            {
                "name": "shell.run",
                "status": "done",
                "detail": "Recorded tool call",
                "risk": {"level": "medium", "reason": "Shell command can change project state."},
                "metadata": {"command": "echo approval"},
            }
        ]
        scope = approval_scope(events)
        request = evaluate_approval_contract(events).required_approvals[0]
        entry = build_ledger_decision_record(
            "run-1",
            request,
            actor="alice",
            created_at="2026-06-18T00:00:00Z",
            expires_at="2999-01-01T00:00:00Z",
            scope=scope,
            decision="approved",
            reason="Reviewed.",
        )

        matched = summarize_ledger([entry], scope)
        changed = summarize_ledger([entry], ["command:echo changed"])
        missing = summarize_ledger([entry], [])

        self.assertEqual(matched["scope_replay"][0]["replay_status"], "matched")
        self.assertTrue(matched["execution_ready_approvals"][0]["execution_ready"])
        self.assertEqual(matched["scope_replay"][0]["signature_status"], "unsigned")
        self.assertEqual(changed["scope_replay"][0]["replay_status"], "changed")
        self.assertEqual(changed["execution_ready_approvals"], [])
        self.assertEqual(missing["scope_replay"][0]["replay_status"], "missing evidence")

    def test_scope_evidence_groups_changed_diff_risk_and_command_parts(self) -> None:
        events = [
            {
                "name": "git.diff",
                "status": "done",
                "risk": {"level": "medium", "reason": "Diff review required."},
                "metadata": {"changed_files": ["app.py"], "command": "git diff"},
                "artifacts": {"diff": "git/diff.patch"},
                "artifact_previews": {"diff": {"content": "diff --git a/app.py b/app.py\n"}},
            }
        ]

        evidence = approval_scope_evidence(events)

        self.assertTrue(evidence["has_evidence"])
        self.assertEqual(evidence["changed_files"], ["app.py"])
        self.assertEqual(len(evidence["diff_hashes"]), 1)
        self.assertEqual(evidence["command_scope"], ["git diff"])
        self.assertEqual(len(evidence["risk_scope"]), 1)


if __name__ == "__main__":
    unittest.main()
