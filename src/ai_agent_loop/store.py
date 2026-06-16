"""Local persistence for agent loop runs."""

from __future__ import annotations

import json
from pathlib import Path

from ai_agent_loop.goal import Goal
from ai_agent_loop.loop import AgentStep, LoopResult


class RunStore:
    def __init__(self, root: Path | str = ".agent") -> None:
        self.root = Path(root)

    def save(self, result: LoopResult) -> Path:
        run_dir = self.root / "runs" / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(run_dir / "goal.json", goal_to_record(result))
        self._write_events(run_dir / "events.jsonl", result)
        (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")

        return run_dir

    def list_runs(self) -> list[dict[str, object]]:
        runs_dir = self.root / "runs"
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
        return {
            "run_id": run_id,
            "project": goal_record.get("project", "unknown"),
            "status": goal_record.get("status", infer_status(events)),
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
        return report_path.read_text(encoding="utf-8")

    def run_dir(self, run_id: str) -> Path:
        return self.root / "runs" / run_id

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
    critique = "\n".join(
        f"- {step.detail}" for step in result.steps if step.name == "critique"
    )

    return (
        f"# Agent Run {result.run_id}\n\n"
        f"Status: {result.status}\n\n"
        f"Project: {result.project}\n\n"
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
    record["status"] = result.status
    return record


def infer_status(events: list[dict[str, object]]) -> str:
    statuses = {str(event.get("status", "")) for event in events}
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if "cancelled" in statuses:
        return "cancelled"
    return "done" if events else "unknown"
