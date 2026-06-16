"""Agent facade for running a complete work loop."""

from __future__ import annotations

from pathlib import Path

from ai_agent_loop.loop import LoopResult, run_loop
from ai_agent_loop.project import Project, ProjectRegistry
from ai_agent_loop.store import RunStore


class Agent:
    """Small facade kept intentionally thin until real capabilities are added."""

    def __init__(
        self,
        store_root: Path | str = ".agent",
        project_path: Path | str | None = None,
    ) -> None:
        self.registry = ProjectRegistry(store_root)
        self.project: Project = self.registry.ensure_project(project_path)
        self.store = RunStore(store_root, project=self.project)

    def run(self, goal: str, persist: bool = True) -> LoopResult:
        result = run_loop(
            goal,
            project=self.project.name,
            project_id=self.project.id,
            project_path=self.project.path,
        )
        if persist:
            self.store.save(result)
        return result
