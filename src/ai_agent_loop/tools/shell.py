"""Shell command tool with captured artifacts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ai_agent_loop.events import EventRecord
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
            risk=classify_shell_command(command).to_dict(),
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
        return result
