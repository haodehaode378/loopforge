"""Risk metadata for tool calls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskAssessment:
    level: str
    reason: str
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
        }


LOW_RISK = RiskAssessment("low", "Read-only local operation.")


def classify_file_read(path: str) -> RiskAssessment:
    return RiskAssessment("low", f"Read-only file access: {path}")


def classify_file_search(pattern: str) -> RiskAssessment:
    return RiskAssessment("low", f"Read-only file search: {pattern}")


def classify_shell_command(command: str) -> RiskAssessment:
    lowered = command.lower()
    dangerous_tokens = [
        " rm ",
        "del ",
        "remove-item",
        "rmdir",
        "format ",
        "git push",
        "git reset",
        "shutdown",
    ]
    if any(token in f" {lowered} " for token in dangerous_tokens):
        return RiskAssessment(
            "high",
            "Shell command may modify files, history, remote state, or system state.",
            requires_confirmation=True,
        )
    return RiskAssessment("medium", "Shell command execution can change project state.")


def classify_file_delete(path: str) -> RiskAssessment:
    return RiskAssessment(
        "high",
        f"File deletion is destructive and is not executable in Loop 3: {path}",
        requires_confirmation=True,
    )


def classify_git_push(remote: str = "origin", branch: str = "") -> RiskAssessment:
    target = f"{remote}/{branch}" if branch else remote
    return RiskAssessment(
        "high",
        f"Git push can publish local changes to a remote target: {target}",
        requires_confirmation=True,
    )
