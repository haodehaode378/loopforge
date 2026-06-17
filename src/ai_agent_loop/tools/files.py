"""Read-only file tools."""

from __future__ import annotations

from pathlib import Path

from ai_agent_loop.events import EventRecord
from ai_agent_loop.risk import classify_file_read, classify_file_search
from ai_agent_loop.store import RunStore


class FileTools:
    def __init__(self, store: RunStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.project_path = Path(store.project.path)

    def read_file(self, path: str) -> str:
        target = self._resolve_project_path(path)
        content = target.read_text(encoding="utf-8")
        event = EventRecord(
            type="tool_call",
            name="file.read",
            detail=f"Read {target.relative_to(self.project_path)}",
            status="done",
            risk=classify_file_read(path).to_dict(),
            metadata={
                "path": str(target),
                "bytes": len(content.encode("utf-8")),
            },
        )
        self.store.append_event(self.run_id, event.to_dict())
        return content

    def search_files(self, pattern: str, limit: int = 50) -> list[str]:
        matches: list[str] = []
        for path in self.project_path.rglob(pattern):
            if len(matches) >= limit:
                break
            if self._is_ignored(path):
                continue
            if path.is_file():
                matches.append(str(path.relative_to(self.project_path)))

        event = EventRecord(
            type="tool_call",
            name="file.search",
            detail=f"Search {pattern}: {len(matches)} matches",
            status="done",
            risk=classify_file_search(pattern).to_dict(),
            metadata={
                "pattern": pattern,
                "limit": limit,
                "matches": matches,
            },
        )
        self.store.append_event(self.run_id, event.to_dict())
        return matches

    def _resolve_project_path(self, path: str) -> Path:
        target = (self.project_path / path).resolve()
        if not target.is_relative_to(self.project_path):
            raise ValueError(f"path escapes project: {path}")
        if not target.is_file():
            raise ValueError(f"file not found: {path}")
        return target

    def _is_ignored(self, path: Path) -> bool:
        parts = set(path.relative_to(self.project_path).parts)
        return bool({".git", ".agent", ".loopforge", "__pycache__"} & parts)
