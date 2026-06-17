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
            "metadata": goal_record.get("metadata", {}),
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
        report = replace_automation_summary(report, render_automation_summary(events))
        report = replace_git_summary(report, render_git_summary(events))
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
    metadata = render_metadata(result.metadata)

    return (
        f"# Agent Run {result.run_id}\n\n"
        f"Status: {result.status}\n\n"
        f"Project: {result.project}\n\n"
        f"Project ID: {result.project_id}\n\n"
        f"Project Path: {result.project_path}\n\n"
        f"## Run Metadata\n\n{metadata}\n\n"
        f"## Goal\n\n{result.goal.description}\n\n"
        f"## Assumptions\n\n{assumptions}\n\n"
        f"## Success Criteria\n\n{criteria}\n\n"
        f"## Automation Summary\n\nNo autonomous actions recorded.\n\n"
        f"## Git Summary\n\nNo git actions recorded.\n\n"
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
    record["metadata"] = result.metadata
    return record


def render_metadata(metadata: dict[str, object]) -> str:
    if not metadata:
        return "- provider: unknown"
    keys = [
        "provider",
        "provider_kind",
        "model",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    ]
    return "\n".join(f"- {key}: {metadata.get(key)}" for key in keys)


def render_automation_summary(events: list[dict[str, object]]) -> str:
    writes = [event for event in events if event.get("name") == "file.write"]
    commands = [event for event in events if event.get("name") == "shell.run"]
    verifications = [event for event in events if event.get("name") == "automation.verify"]
    next_steps = [event for event in events if event.get("name") == "automation.next_steps"]
    risk_events = [event for event in events if event.get("risk")]
    if not writes and not commands and not verifications:
        return "No autonomous actions recorded."

    return "\n\n".join(
        [
            "Changed files:\n" + render_event_paths(writes),
            "Commands:\n" + render_event_commands(commands),
            "Verification:\n" + render_event_details(verifications),
            "Risks:\n" + render_event_risks(risk_events),
            "Next steps:\n" + render_event_details(next_steps),
        ]
    )


def render_event_paths(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        metadata = event.get("metadata", {})
        lines.append(f"- {metadata.get('relative_path') or metadata.get('path')}")
    return "\n".join(lines)


def render_event_commands(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        metadata = event.get("metadata", {})
        lines.append(f"- {metadata.get('command')} -> exit {metadata.get('exit_code')}")
    return "\n".join(lines)


def render_event_details(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    return "\n".join(f"- {event.get('detail', '')}" for event in events)


def render_event_risks(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        risk = event.get("risk", {})
        lines.append(f"- {event.get('name')}: {risk.get('level')} - {risk.get('reason')}")
    return "\n".join(lines)


def render_git_summary(events: list[dict[str, object]]) -> str:
    git_events = [
        event for event in events
        if str(event.get("name", "")).startswith("git.")
    ]
    if not git_events:
        return "No git actions recorded."

    commits = [event for event in git_events if event.get("name") == "git.commit"]
    pushes = [event for event in git_events if event.get("name") == "git.push.blocked"]
    return "\n\n".join(
        [
            "Commit SHA:\n" + render_git_commits(commits),
            "Branch:\n" + render_git_branches(git_events),
            "Remote target:\n" + render_git_remote_targets(pushes),
            "Changed files:\n" + render_git_changed_files(git_events),
            "Commands:\n" + render_git_commands(git_events),
            "Risk decision:\n" + render_git_risk_decisions(git_events),
        ]
    )


def render_git_commits(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    return "\n".join(f"- {event.get('metadata', {}).get('commit_sha') or 'none'}" for event in events)


def render_git_branches(events: list[dict[str, object]]) -> str:
    branches = [
        str(event.get("metadata", {}).get("branch"))
        for event in events
        if event.get("metadata", {}).get("branch")
    ]
    if not branches:
        return "- unknown"
    return "\n".join(f"- {branch}" for branch in sorted(set(branches)))


def render_git_remote_targets(events: list[dict[str, object]]) -> str:
    targets = [
        str(event.get("metadata", {}).get("remote_target"))
        for event in events
        if event.get("metadata", {}).get("remote_target")
    ]
    if not targets:
        return "- none"
    return "\n".join(f"- {target}" for target in targets)


def render_git_changed_files(events: list[dict[str, object]]) -> str:
    files: list[str] = []
    for event in events:
        changed = event.get("metadata", {}).get("changed_files", [])
        if isinstance(changed, list):
            files.extend(str(item) for item in changed)
    if not files:
        return "- none"
    return "\n".join(f"- {path}" for path in sorted(set(files)))


def render_git_commands(events: list[dict[str, object]]) -> str:
    commands = [
        str(event.get("metadata", {}).get("command"))
        for event in events
        if event.get("metadata", {}).get("command")
    ]
    if not commands:
        return "- none"
    return "\n".join(f"- {command}" for command in commands)


def render_git_risk_decisions(events: list[dict[str, object]]) -> str:
    lines = []
    for event in events:
        risk = event.get("risk", {})
        lines.append(
            f"- {event.get('name')}: {event.get('status')} - "
            f"{risk.get('level')} - {event.get('detail')}"
        )
    return "\n".join(lines) if lines else "- none"


def infer_status(events: list[dict[str, object]]) -> str:
    statuses = {str(event.get("status", "")) for event in events}
    if "blocked" in statuses:
        return "blocked"
    automation_verifications = [
        event for event in events
        if event.get("name") == "automation.verify"
    ]
    if automation_verifications:
        return str(automation_verifications[-1].get("status", "unknown"))
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


def replace_automation_summary(report: str, summary: str) -> str:
    heading = "## Automation Summary"
    next_heading = "\n## Git Summary"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"


def replace_git_summary(report: str, summary: str) -> str:
    heading = "## Git Summary"
    next_heading = "\n## Sharp Review"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"
