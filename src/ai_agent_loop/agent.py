"""Agent facade for running a complete work loop."""

from __future__ import annotations

from pathlib import Path

from ai_agent_loop.events import EventRecord
from ai_agent_loop.loop import LoopResult, run_loop
from ai_agent_loop.provider import resolve_provider
from ai_agent_loop.project import Project, ProjectRegistry
from ai_agent_loop.settings import load_settings
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

    def run(
        self,
        goal: str,
        persist: bool = True,
        require_model: bool = False,
    ) -> LoopResult:
        settings = load_settings(self.registry.root, project=self.project)
        provider = resolve_provider(settings, require_model=require_model)
        result = run_loop(
            goal,
            project=self.project.name,
            project_id=self.project.id,
            project_path=self.project.path,
            metadata=provider.metadata,
        )
        if persist:
            self.store.save(result)
            if provider.blocked:
                self.store.append_event(
                    result.run_id,
                    EventRecord(
                        type="setup",
                        name="provider.setup",
                        detail=provider.blocked_reason,
                        status="blocked",
                        metadata=provider.metadata,
                    ).to_dict(),
                )
        return result
