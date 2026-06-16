"""Project registry and metadata."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
        }


class ProjectRegistry:
    def __init__(self, root: Path | str = ".agent") -> None:
        self.root = Path(root)
        self.registry_path = self.root / "projects.json"

    def ensure_project(self, project_path: Path | str | None = None) -> Project:
        path = Path.cwd() if project_path is None else Path(project_path)
        resolved = path.resolve()
        project = Project(
            id=project_id_for_path(resolved),
            name=resolved.name or str(resolved),
            path=str(resolved),
        )

        projects = self.list_projects()
        if project.id not in {item.id for item in projects}:
            projects.append(project)
            self._write_projects(projects)

        self.ensure_project_files(project)
        return project

    def list_projects(self) -> list[Project]:
        if not self.registry_path.exists():
            return []
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        return [Project(**item) for item in data.get("projects", [])]

    def project_dir(self, project: Project) -> Path:
        return self.root / "projects" / project.id

    def ensure_project_files(self, project: Project) -> None:
        project_dir = self.project_dir(project)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "project.json").write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        memory_path = project_dir / "memory.json"
        if not memory_path.exists():
            memory_path.write_text(
                json.dumps(default_memory(project), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def _write_projects(self, projects: list[Project]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        data = {"projects": [project.to_dict() for project in projects]}
        self.registry_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def project_id_for_path(path: Path) -> str:
    name = slugify(path.name or "project")
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    return f"{name}-{digest}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
    return slug or "project"


def default_memory(project: Project) -> dict[str, object]:
    return {
        "project_id": project.id,
        "project_name": project.name,
        "project_path": project.path,
        "goals": [],
        "user_preferences": [],
        "tech_stack": [],
        "common_commands": [],
        "historical_failures": [],
        "protected_paths": [],
        "privacy_exclusions": [
            ".env",
            ".env.*",
            ".git/",
            ".agent/",
            ".loopforge/",
        ],
    }
