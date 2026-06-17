"""Shell command tool with captured artifacts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ai_agent_loop.events import EventRecord
from ai_agent_loop.policy import evaluate_risk, should_block_for_repeated_failures
from ai_agent_loop.risk import classify_shell_command
from ai_agent_loop.store import RunStore


@dataclass(frozen=True)
class ShellResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


class ShellTools:
    def __init__(self, store: RunStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id

    def run(self, command: str, timeout_seconds: int = 60) -> ShellResult:
        risk = classify_shell_command(command)
        decision = evaluate_risk(risk.to_dict())
        if not decision.allowed:
            event = EventRecord(
                type="policy_decision",
                name="policy.blocked",
                detail=decision.reason,
                status="blocked",
                risk=risk.to_dict(),
                metadata={
                    "command": command,
                    "policy": decision.to_dict(),
                },
            )
            self.store.append_event(self.run_id, event.to_dict())
            return ShellResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=decision.reason,
            )

        completed = subprocess.run(
            command,
            cwd=self.store.project.path,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        result = ShellResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

        step_id = self.store.next_artifact_id(self.run_id, "shell")
        stdout_path = self.store.write_artifact(
            self.run_id,
            "commands",
            f"{step_id}.stdout.txt",
            result.stdout,
        )
        stderr_path = self.store.write_artifact(
            self.run_id,
            "commands",
            f"{step_id}.stderr.txt",
            result.stderr,
        )
        status = "done" if result.exit_code == 0 else "failed"
        event = EventRecord(
            type="tool_call",
            name="shell.run",
            detail=f"{command} -> exit {result.exit_code}",
            status=status,
            risk=risk.to_dict(),
            metadata={
                "command": command,
                "exit_code": result.exit_code,
                "timeout_seconds": timeout_seconds,
            },
            artifacts={
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            },
        )
        self.store.append_event(self.run_id, event.to_dict())
        if status == "failed" and should_block_for_repeated_failures(self.store.read_events(self.run_id)):
            blocked = EventRecord(
                type="policy_decision",
                name="policy.blocked",
                detail="Three consecutive failures reached the blocked threshold.",
                status="blocked",
                metadata={
                    "reason": "repeated_failures",
                    "failure_limit": 3,
                },
            )
            self.store.append_event(self.run_id, blocked.to_dict())
        return result
