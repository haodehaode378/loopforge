import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop.evidence import (
    build_evidence_manifest,
    read_evidence_manifest,
    scope_evidence_from_manifest_or_events,
    scope_from_manifest_or_events,
    verify_evidence_manifest,
    write_evidence_manifest,
)
from ai_agent_loop.ledger import approval_scope, scope_hash


class EvidenceManifestTests(unittest.TestCase):
    def test_manifest_records_core_artifact_and_scope_hashes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "commands").mkdir()
            stdout = run_dir / "commands" / "shell-0001.stdout.txt"
            stdout.write_text("hello\n", encoding="utf-8")
            events = [
                {
                    "name": "shell.run",
                    "status": "done",
                    "risk": {"level": "medium", "reason": "Shell command can change project state."},
                    "metadata": {"command": "echo hello"},
                    "artifacts": {"stdout": str(stdout)},
                }
            ]
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            (run_dir / "report.md").write_text("# Report\n", encoding="utf-8")
            (run_dir / "approvals.jsonl").write_text("", encoding="utf-8")

            manifest = build_evidence_manifest(run_dir, events)

            self.assertEqual(manifest["status"], "present")
            self.assertEqual(manifest["scope_replay_source"], "manifest")
            self.assertEqual(manifest["scope_hash"], scope_hash(approval_scope(events)))
            self.assertTrue(manifest["core_hashes"]["events.jsonl"])
            self.assertTrue(manifest["core_hashes"]["report.md"])
            self.assertEqual(manifest["command_scope"], ["echo hello"])
            self.assertEqual(len(manifest["artifact_hashes"]), 1)

    def test_manifest_scope_is_preferred_and_missing_manifest_falls_back(self) -> None:
        events = [
            {
                "name": "shell.run",
                "status": "done",
                "risk": {"level": "medium", "reason": "Shell command can change project state."},
                "metadata": {"command": "echo fallback"},
            }
        ]
        manifest = {
            "status": "present",
            "scope_replay_source": "manifest",
            "scope_parts": ["command:echo manifest"],
        }
        missing = {"status": "missing manifest", "scope_replay_source": "events"}

        self.assertEqual(scope_from_manifest_or_events(manifest, events), ["command:echo manifest"])
        self.assertEqual(scope_from_manifest_or_events(missing, events), approval_scope(events))
        evidence = scope_evidence_from_manifest_or_events(missing, events)
        self.assertEqual(evidence["manifest_status"], "missing manifest")
        self.assertEqual(evidence["scope_replay_source"], "events")

    def test_write_and_read_manifest_roundtrip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "events.jsonl").write_text("", encoding="utf-8")
            (run_dir / "report.md").write_text("# Report\n", encoding="utf-8")

            write_evidence_manifest(run_dir, [])
            manifest = read_evidence_manifest(run_dir)

            self.assertEqual(manifest["status"], "present")
            self.assertEqual(manifest["manifest_file"], "evidence_manifest.json")
            self.assertEqual(manifest["integrity_status"], "verified")

    def test_manifest_integrity_detects_core_file_tampering(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            events = [{"name": "goal", "status": "done", "detail": "tamper test"}]
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            (run_dir / "report.md").write_text("# Report\n", encoding="utf-8")
            write_evidence_manifest(run_dir, events)

            self.assertEqual(read_evidence_manifest(run_dir)["integrity_status"], "verified")
            (run_dir / "report.md").write_text("# Changed\n", encoding="utf-8")
            manifest = read_evidence_manifest(run_dir)

            self.assertEqual(manifest["integrity_status"], "tampered")
            self.assertEqual(manifest["integrity_issues"][0]["path"], "report.md")

    def test_manifest_integrity_detects_artifact_tampering(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "commands").mkdir()
            stdout = run_dir / "commands" / "shell-0001.stdout.txt"
            stdout.write_text("original\n", encoding="utf-8")
            events = [
                {
                    "name": "shell.run",
                    "status": "done",
                    "metadata": {"command": "echo original"},
                    "risk": {"level": "medium", "reason": "Shell command can change project state."},
                    "artifacts": {"stdout": str(stdout)},
                }
            ]
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            (run_dir / "report.md").write_text("# Report\n", encoding="utf-8")
            manifest = build_evidence_manifest(run_dir, events)
            (run_dir / "evidence_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )

            stdout.write_text("changed\n", encoding="utf-8")
            integrity = verify_evidence_manifest(run_dir, manifest)

            self.assertEqual(integrity["integrity_status"], "tampered")
            self.assertEqual(integrity["integrity_issues"][0]["kind"], "artifact")

    def test_tampered_manifest_scope_falls_back_to_events(self) -> None:
        events = [
            {
                "name": "shell.run",
                "status": "done",
                "risk": {"level": "medium", "reason": "Shell command can change project state."},
                "metadata": {"command": "echo fallback"},
            }
        ]
        manifest = {
            "status": "present",
            "integrity_status": "tampered",
            "scope_replay_source": "manifest",
            "scope_parts": ["command:echo manifest"],
        }

        self.assertEqual(scope_from_manifest_or_events(manifest, events), approval_scope(events))


if __name__ == "__main__":
    unittest.main()
