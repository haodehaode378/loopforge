"""Agent facade for running a complete work loop."""

from __future__ import annotations

from pathlib import Path

from ai_agent_loop.loop import LoopResult, run_loop
from ai_agent_loop.store import RunStore


class Agent:
    """Small facade kept intentionally thin until real capabilities are added."""

    def __init__(self, store_root: Path | str = ".agent") -> None:
        self.store = RunStore(store_root)

    def run(self, goal: str, persist: bool = True) -> LoopResult:
        result = run_loop(goal)
        if persist:
            self.store.save(result)
        return result
