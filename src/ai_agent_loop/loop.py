"""Core loop primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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

    @property
    def done(self) -> bool:
        return self.status == "done"


def run_loop(goal: str) -> LoopResult:
    """Run the minimal deterministic loop for a user goal."""

    parsed_goal = Goal.from_text(goal)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

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
        AgentStep("report", "Return the loop result and write inspectable artifacts."),
    ]

    return LoopResult(run_id=run_id, goal=parsed_goal, steps=steps, status="done")
