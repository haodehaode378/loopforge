"""Git tool adapter with conservative policy gates."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_agent_loop.events import EventRecord
from ai_agent_loop.risk import RiskAssessment, classify_git_push
from ai_agent_loop.store import RunStore


DEFAULT_BRANCHES = {"main", "master"}
FIXTURE_MARKER = ".loopforge-fixture"
PRIVATE_GIT_PATHS = {".agent", "AGENTS.md", "docs/loop-spec.md"}


@dataclass(frozen=True)
class GitResult:
    action: str
    exit_code: int
    stdout: str
    stderr: str
    branch: str
    commit_sha: str = ""


class GitTools:
    def __init__(self, store: RunStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.project_path = Path(store.project.path)

    def status(self) -> GitResult:
        branch = self.current_branch()
        result = self.run_git(["status", "--short", "--branch"], "status")
        self.record_event(
            name="git.status",
            detail="Read git status",
            result=result,
            risk=RiskAssessment("low", "Read-only git status.").to_dict(),
            metadata={"branch": branch, "changed_files": self.changed_files()},
        )
        return result

    def diff(self) -> GitResult:
        branch = self.current_branch()
        result = self.run_git(["diff", "--"], "diff")
        artifact = self.store.write_artifact(
            self.run_id,
            "git",
            "diff.patch",
            result.stdout,
        )
        self.record_event(
            name="git.diff",
            detail="Read git diff",
            result=result,
            risk=RiskAssessment("low", "Read-only git diff.").to_dict(),
            metadata={"branch": branch, "changed_files": self.changed_files()},
            artifacts={"diff": str(artifact)},
        )
        return result

    def commit(self, message: str) -> GitResult:
        branch = self.current_branch()
        changed_files = self.changed_files()
        risk = RiskAssessment("medium", "Git commit changes local history.").to_dict()
        if branch in DEFAULT_BRANCHES and not self.is_fixture_project():
            result = GitResult(
                action="commit",
                exit_code=-1,
                stdout="",
                stderr="Git commit is only allowed on non-default branches or fixture projects.",
                branch=branch,
            )
            self.record_event(
                name="git.commit.blocked",
                detail=result.stderr,
                result=result,
                risk=risk,
                metadata={
                    "branch": branch,
                    "changed_files": changed_files,
                    "policy": "default_branch_commit_blocked",
                },
                status="blocked",
            )
            return result

        self.run_git(
            [
                "add",
                "-A",
                "--",
                ".",
                ":(exclude).agent",
                ":(exclude)AGENTS.md",
                ":(exclude)docs/loop-spec.md",
            ],
            "add",
        )
        result = self.run_git(["commit", "-m", message], "commit")
        commit_sha = self.rev_parse_head() if result.exit_code == 0 else ""
        result = GitResult(
            action="commit",
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            branch=branch,
            commit_sha=commit_sha,
        )
        self.record_event(
            name="git.commit",
            detail=f"Git commit on {branch}: {commit_sha or 'failed'}",
            result=result,
            risk=risk,
            metadata={
                "branch": branch,
                "commit_sha": commit_sha,
                "changed_files": changed_files,
                "message": message,
            },
            status="done" if result.exit_code == 0 else "failed",
        )
        return result

    def push(self, remote: str = "origin", branch: str = "") -> GitResult:
        resolved_branch = branch or self.current_branch()
        risk = classify_git_push(remote, resolved_branch)
        result = GitResult(
            action="push",
            exit_code=-1,
            stdout="",
            stderr="Git push is not executable in this loop; policy approval is required.",
            branch=resolved_branch,
        )
        self.record_event(
            name="git.push.blocked",
            detail=result.stderr,
            result=result,
            risk=risk.to_dict(),
            metadata={
                "remote": remote,
                "branch": resolved_branch,
                "remote_target": f"{remote}/{resolved_branch}",
                "policy": "push_execution_reserved",
            },
            status="blocked",
        )
        return result

    def run_git(self, args: list[str], action: str) -> GitResult:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.project_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return GitResult(
            action=action,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            branch=self.current_branch(allow_unknown=True),
        )

    def record_event(
        self,
        name: str,
        detail: str,
        result: GitResult,
        risk: dict[str, object],
        metadata: dict[str, object],
        artifacts: dict[str, str] | None = None,
        status: str | None = None,
    ) -> None:
        event_status = status or ("done" if result.exit_code == 0 else "failed")
        recorded_artifacts = dict(artifacts or {})
        artifact_id = len(self.store.read_events(self.run_id)) + 1
        if result.stdout:
            stdout_path = self.store.write_artifact(
                self.run_id,
                "git",
                f"git-{artifact_id:04d}.stdout.txt",
                result.stdout,
            )
            recorded_artifacts["stdout"] = str(stdout_path)
        if result.stderr:
            stderr_path = self.store.write_artifact(
                self.run_id,
                "git",
                f"git-{artifact_id:04d}.stderr.txt",
                result.stderr,
            )
            recorded_artifacts["stderr"] = str(stderr_path)
        self.store.append_event(
            self.run_id,
            EventRecord(
                type="tool_call" if event_status != "blocked" else "policy_decision",
                name=name,
                detail=detail,
                status=event_status,
                risk=risk,
                metadata={
                    "command": self.command_for_action(result.action),
                    "exit_code": result.exit_code,
                    **metadata,
                },
                artifacts=recorded_artifacts,
            ).to_dict(),
        )

    def current_branch(self, allow_unknown: bool = False) -> str:
        completed = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.project_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        branch = completed.stdout.strip()
        if branch or allow_unknown:
            return branch or "unknown"
        raise ValueError("not a git repository or detached HEAD")

    def changed_files(self) -> list[str]:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.project_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        files = []
        for line in completed.stdout.splitlines():
            if len(line) > 3:
                path = line[3:].strip()
                if not self.is_private_path(path):
                    files.append(path)
        return files

    def rev_parse_head(self) -> str:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    def is_fixture_project(self) -> bool:
        return (self.project_path / FIXTURE_MARKER).exists()

    def command_for_action(self, action: str) -> str:
        commands = {
            "status": "git status --short --branch",
            "diff": "git diff --",
            "commit": "git add -A with private path exclusions && git commit -m <message>",
            "push": "git push <remote> <branch>",
        }
        return commands.get(action, f"git {action}")

    def is_private_path(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        return any(
            normalized == private_path or normalized.startswith(f"{private_path}/")
            for private_path in PRIVATE_GIT_PATHS
        )
