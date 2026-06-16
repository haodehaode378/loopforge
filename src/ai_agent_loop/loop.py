"""Core loop primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_agent_loop.goal import Goal


@dataclass(frozen=True)
class AgentStep:
    name: str
    detail: str
    status: str = "done"

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "detail": self.detail,
            "status": self.status,
        }


@dataclass(frozen=True)
class LoopResult:
    run_id: str
    goal: Goal
    steps: list[AgentStep]
    status: str
    project: str
    project_id: str
    project_path: str

    @property
    def done(self) -> bool:
        return self.status == "done"


def run_loop(
    goal: str,
    project: str | None = None,
    project_id: str | None = None,
    project_path: str | None = None,
) -> LoopResult:
    """Run the minimal deterministic loop for a user goal."""

    parsed_goal = Goal.from_text(goal)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    cwd = Path.cwd()
    resolved_project = project or cwd.name or str(cwd)
    resolved_project_path = project_path or str(cwd)
    resolved_project_id = project_id or resolved_project

    steps = [
        AgentStep("goal", parsed_goal.description),
        AgentStep("context", "Load local project instructions and current workspace state."),
        AgentStep("assumptions", "; ".join(parsed_goal.assumptions)),
        AgentStep("criteria", "; ".join(parsed_goal.success_criteria)),
        AgentStep("plan", "Choose one small implementation step with a clear check."),
        AgentStep("act", "Record the deterministic loop trace for this MVP."),
        AgentStep("observe", "Loop trace was produced and can be persisted."),
        AgentStep("adjust", "No adjustment needed for the deterministic MVP path."),
        AgentStep("verify", "Goal is non-empty and result is structured."),
        AgentStep(
            "critique",
            "Sharp review: the change is acceptable only if it stays scoped, "
            "verified, and aligned with the current loop goal.",
        ),
        AgentStep("report", "Return the loop result and write inspectable artifacts."),
    ]

    return LoopResult(
        run_id=run_id,
        goal=parsed_goal,
        steps=steps,
        status="done",
        project=resolved_project,
        project_id=resolved_project_id,
        project_path=resolved_project_path,
    )
