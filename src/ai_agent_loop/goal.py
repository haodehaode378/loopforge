"""Goal model used by the agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Goal:
    description: str
    assumptions: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> "Goal":
        description = text.strip()
        if not description:
            raise ValueError("goal must not be empty")

        return cls(
            description=description,
            assumptions=[
                "Run locally before adding remote services.",
                "Prefer the smallest verifiable next step.",
            ],
            success_criteria=[
                "A structured loop result is produced.",
                "The run can be inspected after completion.",
            ],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "description": self.description,
            "assumptions": self.assumptions,
            "success_criteria": self.success_criteria,
        }
