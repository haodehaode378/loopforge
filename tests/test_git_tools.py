import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_agent_loop import Agent, RunStore
from ai_agent_loop.tools import GitTools


class GitToolTests(unittest.TestCase):
    def test_git_status_diff_commit_and_push_are_recorded(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "fixture-repo"
            project.mkdir()
            init_git_repo(project)
            (project / ".loopforge-fixture").write_text("ok", encoding="utf-8")
            (project / "feature.txt").write_text("hello\n", encoding="utf-8")
            (project / "AGENTS.md").write_text("private", encoding="utf-8")
            (project / "docs").mkdir()
            (project / "docs" / "loop-spec.md").write_text("private", encoding="utf-8")
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Git fixture")
            store = RunStore(store_root, project_path=project)
            tools = GitTools(store, run.run_id)

            status = tools.status()
            diff = tools.diff()
            commit = tools.commit("Add fixture feature")
            push = tools.push("origin", "main")
            report = store.read_report(run.run_id)

            self.assertEqual(status.exit_code, 0)
            self.assertEqual(diff.exit_code, 0)
            self.assertEqual(commit.exit_code, 0)
            self.assertTrue(commit.commit_sha)
            self.assertEqual(push.exit_code, -1)
            self.assertEqual(store.read_summary(run.run_id)["effective_status"], "blocked")
            self.assertIn("## Git Summary", report)
            self.assertIn("Commit SHA:", report)
            self.assertIn(commit.commit_sha, report)
            self.assertIn("Branch:", report)
            self.assertIn("Remote target:", report)
            self.assertIn("origin/main", report)
            self.assertIn("Changed files:", report)
            self.assertIn("feature.txt", report)
            self.assertIn("Commands:", report)
            self.assertIn("Risk decision:", report)
            self.assertIn("git.push.blocked", report)
            committed_files = git_tracked_files(project, commit.commit_sha)
            self.assertIn("feature.txt", committed_files)
            self.assertNotIn("AGENTS.md", committed_files)
            self.assertNotIn("docs/loop-spec.md", committed_files)
            self.assertNotIn("AGENTS.md", report)

    def test_git_commit_blocks_default_branch_outside_fixture(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "real-repo"
            project.mkdir()
            init_git_repo(project)
            (project / "feature.txt").write_text("hello\n", encoding="utf-8")
            store_root = root / ".agent"
            run = Agent(store_root=store_root, project_path=project).run("Git blocked")
            store = RunStore(store_root, project_path=project)

            result = GitTools(store, run.run_id).commit("Blocked commit")
            events = store.read_events(run.run_id)

            self.assertEqual(result.exit_code, -1)
            self.assertEqual(events[-1]["name"], "git.commit.blocked")
            self.assertEqual(events[-1]["status"], "blocked")
            self.assertEqual(store.read_summary(run.run_id)["effective_status"], "blocked")


def init_git_repo(project: Path) -> None:
    run(project, ["git", "init", "-b", "main"])
    run(project, ["git", "config", "user.email", "loopforge@example.test"])
    run(project, ["git", "config", "user.name", "LoopForge Test"])
    (project / "README.md").write_text("fixture\n", encoding="utf-8")
    run(project, ["git", "add", "README.md"])
    run(project, ["git", "commit", "-m", "Initial commit"])


def run(cwd: Path, command: list[str]) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"{command} failed: {completed.stderr}")


def git_tracked_files(project: Path, commit_sha: str) -> set[str]:
    completed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit_sha],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return set(completed.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
