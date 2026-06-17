"""Provider protocol and deterministic local fallback."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from ai_agent_loop.settings import LoopSettings, ProviderSettings


@dataclass(frozen=True)
class ProviderResult:
    text: str
    metadata: dict[str, object]


class ModelProvider(Protocol):
    settings: ProviderSettings

    def generate(self, prompt: str) -> ProviderResult:
        """Generate a response for a prompt."""


class DeterministicFakeProvider:
    def __init__(self, settings: ProviderSettings | None = None) -> None:
        self.settings = settings or ProviderSettings(
            kind="deterministic-fake",
            name="Deterministic Fake",
            model="deterministic-fake",
        )

    def generate(self, prompt: str) -> ProviderResult:
        started = perf_counter()
        text = f"deterministic response for {len(prompt.strip())} chars"
        latency_ms = int((perf_counter() - started) * 1000)
        return ProviderResult(
            text=text,
            metadata=provider_metadata(
                self.settings,
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
            ),
        )


@dataclass(frozen=True)
class ProviderResolution:
    provider: ModelProvider | None
    metadata: dict[str, object]
    blocked_reason: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)


def resolve_provider(settings: LoopSettings, require_model: bool = False) -> ProviderResolution:
    if settings.provider is None:
        metadata = provider_metadata(
            ProviderSettings(
                kind="deterministic-local",
                name="Deterministic Local",
                model="deterministic-local",
            ),
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
        if require_model:
            return ProviderResolution(
                provider=None,
                metadata=metadata,
                blocked_reason="Model provider configuration is required for this run.",
            )
        return ProviderResolution(
            provider=DeterministicFakeProvider(),
            metadata=metadata,
        )

    if settings.provider.kind == "deterministic-fake":
        provider = DeterministicFakeProvider(settings.provider)
        return ProviderResolution(provider=provider, metadata=provider.generate("").metadata)

    if require_model:
        return ProviderResolution(
            provider=None,
            metadata=provider_metadata(settings.provider),
            blocked_reason="Configured provider adapter is not implemented yet.",
        )
    return ProviderResolution(
        provider=None,
        metadata=provider_metadata(settings.provider),
    )


def provider_metadata(
    settings: ProviderSettings,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> dict[str, object]:
    return {
        "provider": settings.name,
        "provider_kind": settings.kind,
        "model": settings.model,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }
