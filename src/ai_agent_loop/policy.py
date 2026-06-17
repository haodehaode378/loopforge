"""Policy decisions for risky actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
        }


def evaluate_risk(risk: dict[str, object]) -> PolicyDecision:
    if risk.get("requires_confirmation") or risk.get("level") == "high":
        return PolicyDecision(
            action="block",
            allowed=False,
            reason=str(risk.get("reason", "High-risk action requires confirmation.")),
        )
    return PolicyDecision(
        action="allow",
        allowed=True,
        reason="Risk is within current execution policy.",
    )


def should_block_for_repeated_failures(events: list[dict[str, object]], limit: int = 3) -> bool:
    failures = 0
    for event in reversed(events):
        status = event.get("status")
        if status == "failed":
            failures += 1
            if failures >= limit:
                return True
            continue
        if status in {"done", "blocked", "cancelled"}:
            return False
    return False
