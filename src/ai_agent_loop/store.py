"""Local persistence for agent loop runs."""

from __future__ import annotations

import json
from pathlib import Path

from ai_agent_loop.goal import Goal
from ai_agent_loop.loop import LoopResult


class RunStore:
    def __init__(self, root: Path | str = ".agent") -> None:
        self.root = Path(root)

    def save(self, result: LoopResult) -> Path:
        run_dir = self.root / "runs" / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(run_dir / "goal.json", result.goal.to_dict())
        self._write_events(run_dir / "events.jsonl", result)
        (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")

        return run_dir

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

    return (
        f"# Agent Run {result.run_id}\n\n"
        f"Status: {result.status}\n\n"
        f"## Goal\n\n{result.goal.description}\n\n"
        f"## Assumptions\n\n{assumptions}\n\n"
        f"## Success Criteria\n\n{criteria}\n\n"
        f"## Loop Trace\n\n{steps}\n"
    )
