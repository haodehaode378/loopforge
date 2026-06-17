"""Local persistence for agent loop runs."""

from __future__ import annotations

import json
from pathlib import Path

from ai_agent_loop.goal import Goal
from ai_agent_loop.critique import render_critique
from ai_agent_loop.loop import AgentStep, LoopResult
from ai_agent_loop.project import Project, ProjectRegistry


class RunStore:
    def __init__(
        self,
        root: Path | str = ".agent",
        project: Project | None = None,
        project_path: Path | str | None = None,
    ) -> None:
        self.root = Path(root)
        self.registry = ProjectRegistry(self.root)
        self.project = project or self.registry.ensure_project(project_path)
        self.registry.ensure_project_files(self.project)

    def save(self, result: LoopResult) -> Path:
        run_dir = self.run_dir(result.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(run_dir / "goal.json", goal_to_record(result))
        self._write_events(run_dir / "events.jsonl", result)
        (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")

        return run_dir

    def list_runs(self) -> list[dict[str, object]]:
        runs_dir = self.runs_dir()
        if not runs_dir.exists():
            return []

        records = []
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            try:
                records.append(self.read_summary(run_dir.name))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return records

    def read_summary(self, run_id: str) -> dict[str, object]:
        run_dir = self.run_dir(run_id)
        goal_path = run_dir / "goal.json"
        if not goal_path.exists():
            raise ValueError(f"run not found: {run_id}")

        goal_record = json.loads(goal_path.read_text(encoding="utf-8"))
        events = self.read_events(run_id)
        blocked_reason = find_blocked_reason(events)
        return {
            "run_id": run_id,
            "project": goal_record.get("project", "unknown"),
            "project_id": goal_record.get("project_id", self.project.id),
            "project_path": goal_record.get("project_path", self.project.path),
            "status": goal_record.get("status", infer_status(events)),
            "effective_status": infer_status(events),
            "blocked_reason": blocked_reason,
            "goal": goal_record.get("description", ""),
            "event_count": len(events),
            "report_path": str(run_dir / "report.md"),
        }

    def read_events(self, run_id: str) -> list[dict[str, object]]:
        events_path = self.run_dir(run_id) / "events.jsonl"
        if not events_path.exists():
            return []
        events = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def read_report(self, run_id: str) -> str:
        report_path = self.run_dir(run_id) / "report.md"
        if not report_path.exists():
            raise ValueError(f"report not found: {run_id}")
        report = report_path.read_text(encoding="utf-8")
        events = self.read_events(run_id)
        effective_status = infer_status(events)
        report = replace_status_line(report, effective_status)
        report = replace_sharp_review(report, render_critique(events))
        blocked_reason = find_blocked_reason(events)
        if blocked_reason and "## Blocked Reason" not in report:
            report += f"\n## Blocked Reason\n\n{blocked_reason}\n"
        return report

    def append_event(self, run_id: str, event: dict[str, object]) -> None:
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        events_path = run_dir / "events.jsonl"
        with events_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def write_artifact(
        self,
        run_id: str,
        group: str,
        name: str,
        content: str,
    ) -> Path:
        artifact_dir = self.run_dir(run_id) / group
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def next_artifact_id(self, run_id: str, prefix: str) -> str:
        artifact_dir = self.run_dir(run_id) / "commands"
        existing = len(list(artifact_dir.glob(f"{prefix}-*.stdout.txt"))) if artifact_dir.exists() else 0
        return f"{prefix}-{existing + 1:04d}"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir() / run_id

    def runs_dir(self) -> Path:
        return self.registry.project_dir(self.project) / "runs"

    @staticmethod
    def _write_json(path: Path, data: dict[str, object]) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_events(path: Path, result: LoopResult) -> None:
        lines = [
            json.dumps(step.to_dict(), ensure_ascii=False)
            for step in result.steps
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(result: LoopResult) -> str:
    criteria = "\n".join(
        f"- {item}" for item in result.goal.success_criteria
    )
    assumptions = "\n".join(
        f"- {item}" for item in result.goal.assumptions
    )
    steps = "\n".join(
        f"- {step.name}: {step.detail}" for step in result.steps
    )
    critique = render_critique([step.to_dict() for step in result.steps])

    return (
        f"# Agent Run {result.run_id}\n\n"
        f"Status: {result.status}\n\n"
        f"Project: {result.project}\n\n"
        f"Project ID: {result.project_id}\n\n"
        f"Project Path: {result.project_path}\n\n"
        f"## Goal\n\n{result.goal.description}\n\n"
        f"## Assumptions\n\n{assumptions}\n\n"
        f"## Success Criteria\n\n{criteria}\n\n"
        f"## Sharp Review\n\n{critique}\n\n"
        f"## Loop Trace\n\n{steps}\n"
    )


def goal_to_record(result: LoopResult) -> dict[str, object]:
    record = result.goal.to_dict()
    record["run_id"] = result.run_id
    record["project"] = result.project
    record["project_id"] = result.project_id
    record["project_path"] = result.project_path
    record["status"] = result.status
    return record


def infer_status(events: list[dict[str, object]]) -> str:
    statuses = {str(event.get("status", "")) for event in events}
    if "blocked" in statuses:
        return "blocked"
    if "failed" in statuses:
        return "failed"
    if "cancelled" in statuses:
        return "cancelled"
    return "done" if events else "unknown"


def find_blocked_reason(events: list[dict[str, object]]) -> str:
    for event in reversed(events):
        if event.get("status") == "blocked":
            return str(event.get("detail") or event.get("metadata", {}).get("reason") or "")
    return ""


def replace_status_line(report: str, status: str) -> str:
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Status: "):
            lines[index] = f"Status: {status}"
            return "\n".join(lines) + ("\n" if report.endswith("\n") else "")
    return report


def replace_sharp_review(report: str, critique: str) -> str:
    heading = "## Sharp Review"
    next_heading = "\n## Loop Trace"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{critique}\n{next_heading}{after}"
