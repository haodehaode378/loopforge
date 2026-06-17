"""Structured event records."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventRecord:
    type: str
    name: str
    detail: str
    status: str
    risk: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "name": self.name,
            "detail": self.detail,
            "status": self.status,
            "risk": self.risk,
            "metadata": self.metadata,
            "artifacts": self.artifacts,
        }
