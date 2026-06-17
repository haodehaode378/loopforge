"""Bounded autonomous development runner for fixture projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_agent_loop.events import EventRecord
from ai_agent_loop.risk import classify_file_read, classify_file_write
from ai_agent_loop.store import RunStore
from ai_agent_loop.tools import ShellTools


FIXTURE_MARKER = ".loopforge-fixture"
TASK_FILE = ".loopforge-task.json"


@dataclass(frozen=True)
class AutomationTask:
    target_file: str
    initial_content: str
    adjusted_content: str
    test_command: str
    context_files: list[str]


class AutonomousRunner:
    def __init__(self, store: RunStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.project_path = Path(store.project.path)

    def run(self, goal: str, test_command: str = "") -> None:
        if not (self.project_path / FIXTURE_MARKER).exists():
            self.store.append_event(
                self.run_id,
                EventRecord(
                    type="policy_decision",
                    name="automation.blocked",
                    detail="Autonomous writes are only enabled for fixture projects.",
                    status="blocked",
                    metadata={"required_marker": FIXTURE_MARKER},
                ).to_dict(),
            )
            return

        task = self.load_task(goal, test_command)
        self.record_context(task)
        self.record_plan(task)
        self.write_file(task.target_file, task.initial_content)

        first_result = ShellTools(self.store, self.run_id).run(task.test_command)
        if first_result.exit_code == 0:
            self.record_verification(task.test_command, "done")
            self.record_next_steps("Review the generated file and continue with the next bounded task.")
            return

        self.store.append_event(
            self.run_id,
            EventRecord(
                type="loop_step",
                name="automation.adjust",
                detail="Verification failed; applying one bounded adjustment before retry.",
                status="done",
                metadata={"failed_command": task.test_command, "exit_code": first_result.exit_code},
            ).to_dict(),
        )
        self.write_file(task.target_file, task.adjusted_content)
        second_result = ShellTools(self.store, self.run_id).run(task.test_command)
        final_status = "done" if second_result.exit_code == 0 else "failed"
        self.record_verification(task.test_command, final_status)
        next_step = (
            "Review the adjusted file and promote the pattern to real project automation."
            if final_status == "done"
            else "Inspect command artifacts before increasing automation scope."
        )
        self.record_next_steps(next_step)

    def load_task(self, goal: str, test_command: str) -> AutomationTask:
        path = self.project_path / TASK_FILE
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return AutomationTask(
                target_file=str(data.get("target_file", "loopforge_auto.txt")),
                initial_content=str(data.get("initial_content", goal)),
                adjusted_content=str(data.get("adjusted_content", data.get("initial_content", goal))),
                test_command=str(data.get("test_command", test_command or "python -m unittest discover -s tests")),
                context_files=[str(item) for item in data.get("context_files", ["README.md"])],
            )
        return AutomationTask(
            target_file="loopforge_auto.txt",
            initial_content=f"{goal}\n",
            adjusted_content=f"{goal}\n",
            test_command=test_command or "python -m unittest discover -s tests",
            context_files=["README.md"],
        )

    def record_context(self, task: AutomationTask) -> None:
        read_files = []
        for relative_path in task.context_files:
            target = self.resolve_existing_file(relative_path)
            if not target:
                continue
            content = target.read_text(encoding="utf-8")
            read_files.append(relative_path)
            self.store.append_event(
                self.run_id,
                EventRecord(
                    type="tool_call",
                    name="file.read",
                    detail=f"Read context {relative_path}",
                    status="done",
                    risk=classify_file_read(relative_path).to_dict(),
                    metadata={"path": str(target), "bytes": len(content.encode("utf-8"))},
                ).to_dict(),
            )
        self.store.append_event(
            self.run_id,
            EventRecord(
                type="loop_step",
                name="automation.context",
                detail=f"Loaded {len(read_files)} context file(s).",
                status="done",
                metadata={"files": read_files},
            ).to_dict(),
        )

    def record_plan(self, task: AutomationTask) -> None:
        self.store.append_event(
            self.run_id,
            EventRecord(
                type="loop_step",
                name="automation.plan",
                detail="Bounded plan: update one fixture file, run one verification command, retry once if needed.",
                status="done",
                metadata={
                    "target_file": task.target_file,
                    "test_command": task.test_command,
                    "max_retries": 1,
                },
            ).to_dict(),
        )

    def write_file(self, relative_path: str, content: str) -> None:
        target = self.resolve_project_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(content, encoding="utf-8")
        self.store.append_event(
            self.run_id,
            EventRecord(
                type="tool_call",
                name="file.write",
                detail=f"Write {relative_path}",
                status="done",
                risk=classify_file_write(relative_path).to_dict(),
                metadata={
                    "relative_path": relative_path,
                    "path": str(target),
                    "bytes_before": len(before.encode("utf-8")),
                    "bytes_after": len(content.encode("utf-8")),
                },
            ).to_dict(),
        )

    def record_verification(self, command: str, status: str) -> None:
        self.store.append_event(
            self.run_id,
            EventRecord(
                type="loop_step",
                name="automation.verify",
                detail=f"Verification {status}: {command}",
                status=status,
                metadata={"command": command},
            ).to_dict(),
        )

    def record_next_steps(self, detail: str) -> None:
        self.store.append_event(
            self.run_id,
            EventRecord(
                type="loop_step",
                name="automation.next_steps",
                detail=detail,
                status="done",
            ).to_dict(),
        )

    def resolve_project_path(self, relative_path: str) -> Path:
        target = (self.project_path / relative_path).resolve()
        if not target.is_relative_to(self.project_path):
            raise ValueError(f"path escapes project: {relative_path}")
        return target

    def resolve_existing_file(self, relative_path: str) -> Path | None:
        target = self.resolve_project_path(relative_path)
        return target if target.is_file() else None
