"""Project settings models without secret persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_agent_loop.project import Project, ProjectRegistry


@dataclass(frozen=True)
class ProviderSettings:
    kind: str
    name: str
    model: str
    base_url: str = ""
    api_key_env: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "name": self.name,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
        }


@dataclass(frozen=True)
class LoopSettings:
    provider: ProviderSettings | None = None
    local_fallback: bool = True

    @property
    def has_provider_config(self) -> bool:
        return self.provider is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider.to_dict() if self.provider else None,
            "local_fallback": self.local_fallback,
        }


def load_settings(
    root: Path | str = ".agent",
    project: Project | None = None,
    project_path: Path | str | None = None,
) -> LoopSettings:
    registry = ProjectRegistry(root)
    resolved_project = project or registry.ensure_project(project_path)
    path = settings_path(registry, resolved_project)
    if not path.exists():
        return LoopSettings()

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    provider_data = data.get("provider")
    provider = parse_provider(provider_data) if isinstance(provider_data, dict) else None
    return LoopSettings(
        provider=provider,
        local_fallback=bool(data.get("local_fallback", True)),
    )


def settings_path(registry: ProjectRegistry, project: Project) -> Path:
    return registry.project_dir(project) / "settings.json"


def parse_provider(data: dict[str, object]) -> ProviderSettings:
    return ProviderSettings(
        kind=str(data.get("kind", "")),
        name=str(data.get("name", "")),
        model=str(data.get("model", "")),
        base_url=str(data.get("base_url", "")),
        api_key_env=str(data.get("api_key_env", "")),
    )


def provider_template(kind: str) -> ProviderSettings:
    if kind == "openai-compatible":
        return ProviderSettings(
            kind=kind,
            name="OpenAI Compatible",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
        )
    if kind == "claude-compatible":
        return ProviderSettings(
            kind=kind,
            name="Claude Compatible",
            model="claude-sonnet",
            base_url="https://api.anthropic.com",
            api_key_env="ANTHROPIC_API_KEY",
        )
    if kind == "local-http":
        return ProviderSettings(
            kind=kind,
            name="Local HTTP",
            model="local-model",
            base_url="http://localhost:11434",
        )
    if kind == "deterministic-fake":
        return ProviderSettings(
            kind=kind,
            name="Deterministic Fake",
            model="deterministic-fake",
        )
    raise ValueError(f"unknown provider kind: {kind}")
