import json
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop.evidence import write_evidence_manifest
from ai_agent_loop.evidence_bundle import export_evidence_bundle


class EvidenceBundleTests(unittest.TestCase):
    def test_export_evidence_bundle_copies_core_files_and_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "commands").mkdir()
            stdout = run_dir / "commands" / "shell-0001.stdout.txt"
            stdout.write_text("hello\n", encoding="utf-8")
            events = [
                {
                    "name": "shell.run",
                    "status": "done",
                    "metadata": {"command": "echo hello"},
                    "risk": {"level": "medium", "reason": "Shell command can change project state."},
                    "artifacts": {"stdout": str(stdout)},
                }
            ]
            (run_dir / "goal.json").write_text('{"description": "bundle"}\n', encoding="utf-8")
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            (run_dir / "report.md").write_text("# Report\n", encoding="utf-8")
            (run_dir / "approvals.jsonl").write_text("", encoding="utf-8")
            write_evidence_manifest(run_dir, events)

            bundle = export_evidence_bundle(run_dir, "run-1")

            bundle_dir = Path(str(bundle["bundle_dir"]))
            manifest_path = bundle_dir / "bundle_manifest.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(Path(str(bundle["zip_path"])).exists())
            self.assertTrue(bundle["zip_sha256"])
            self.assertTrue((bundle_dir / "events.jsonl").exists())
            self.assertTrue((bundle_dir / "commands" / "shell-0001.stdout.txt").exists())
            self.assertEqual(bundle["source_integrity_status"], "verified")
            self.assertEqual(len(bundle["files"]), 6)
            with zipfile.ZipFile(str(bundle["zip_path"])) as archive:
                self.assertIn("bundle_manifest.json", archive.namelist())
                self.assertIn("commands/shell-0001.stdout.txt", archive.namelist())


if __name__ == "__main__":
    unittest.main()
