"""Pure approval policy contract helpers."""

from __future__ import annotations

from dataclasses import dataclass, field


RESERVED_ACTIONS = ("approve", "resume", "write", "commit", "push", "delete")
READ_ONLY_ACTIONS = ("inspect", "report", "critique", "workbench.view")
RISK_APPROVALS = {
    "low": "none",
    "medium": "user-approval",
    "high": "explicit-high-risk-approval",
    "unknown": "policy-review",
}


@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    risk_level: str
    required_approval: str
    reason: str
    source_event: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "risk_level": self.risk_level,
            "required_approval": self.required_approval,
            "reason": self.reason,
            "source_event": self.source_event,
        }


@dataclass(frozen=True)
class ApprovalDecision:
    action: str
    allowed: bool
    reason: str
    required_approval: str = "none"

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
            "required_approval": self.required_approval,
        }


@dataclass(frozen=True)
class ResumeEligibility:
    eligible: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ApprovalContract:
    mode: str = "read-only approval contract"
    executable_actions: tuple[str, ...] = ()
    reserved_actions: tuple[str, ...] = RESERVED_ACTIONS
    eligible_actions: tuple[str, ...] = READ_ONLY_ACTIONS
    required_approvals: tuple[ApprovalRequest, ...] = ()
    missing_approvals: tuple[ApprovalRequest, ...] = ()
    blocked_actions: tuple[ApprovalDecision, ...] = ()
    resume_eligibility: ResumeEligibility = field(
        default_factory=lambda: ResumeEligibility(False, "Run is not blocked; resume is not needed.")
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "executable_actions": list(self.executable_actions),
            "reserved_actions": list(self.reserved_actions),
            "eligible_actions": list(self.eligible_actions),
            "required_approvals": [item.to_dict() for item in self.required_approvals],
            "missing_approvals": [item.to_dict() for item in self.missing_approvals],
            "blocked_actions": [item.to_dict() for item in self.blocked_actions],
            "resume_eligibility": self.resume_eligibility.to_dict(),
        }


def evaluate_approval_contract(events: list[dict[str, object]]) -> ApprovalContract:
    required = tuple(collect_required_approvals(events))
    approved = collect_approved_keys(events)
    missing = tuple(
        request for request in required
        if approval_key(request) not in approved
    )
    resume = evaluate_resume_eligibility(events, missing)
    blocked = tuple(
        evaluate_reserved_action(action, missing, resume)
        for action in RESERVED_ACTIONS
    )
    return ApprovalContract(
        required_approvals=required,
        missing_approvals=missing,
        blocked_actions=blocked,
        resume_eligibility=resume,
    )


def collect_required_approvals(events: list[dict[str, object]]) -> list[ApprovalRequest]:
    requests = []
    for event in events:
        risk = event.get("risk", {})
        if not isinstance(risk, dict):
            risk = {}
        level = str(risk.get("level") or ("high" if event.get("status") == "blocked" else "low"))
        required = approval_for_risk(level)
        if required == "none" and event.get("status") != "blocked":
            continue
        requests.append(
            ApprovalRequest(
                action=event_action(event),
                risk_level=level,
                required_approval=required,
                reason=str(risk.get("reason") or event.get("detail") or "Policy review required."),
                source_event=str(event.get("name") or "unknown"),
            )
        )
    return requests


def approval_for_risk(level: str) -> str:
    return RISK_APPROVALS.get(level, RISK_APPROVALS["unknown"])


def event_action(event: dict[str, object]) -> str:
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    command = str(metadata.get("command") or "")
    name = str(event.get("name") or "")
    if name == "file.write":
        return "write"
    if name.startswith("git.commit"):
        return "commit"
    if name.startswith("git.push"):
        return "push"
    if "delete" in name:
        return "delete"
    if command:
        return "shell"
    return name or "unknown"


def collect_approved_keys(events: list[dict[str, object]]) -> set[tuple[str, str, str]]:
    approved = set()
    for event in events:
        if event.get("name") != "approval.decision":
            continue
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict) or metadata.get("decision") != "approved":
            continue
        approved.add(
            (
                str(metadata.get("action") or ""),
                str(metadata.get("required_approval") or ""),
                str(metadata.get("source_event") or ""),
            )
        )
    return approved


def approval_key(request: ApprovalRequest) -> tuple[str, str, str]:
    return (request.action, request.required_approval, request.source_event)


def evaluate_resume_eligibility(
    events: list[dict[str, object]],
    missing_approvals: tuple[ApprovalRequest, ...],
) -> ResumeEligibility:
    statuses = {str(event.get("status") or "") for event in events}
    if "blocked" not in statuses:
        return ResumeEligibility(False, "Run is not blocked; resume is not needed.")
    if missing_approvals:
        return ResumeEligibility(False, "Resume requires missing approvals to be resolved first.")
    return ResumeEligibility(True, "Run is blocked and required approvals are satisfied.")


def evaluate_reserved_action(
    action: str,
    missing_approvals: tuple[ApprovalRequest, ...],
    resume: ResumeEligibility,
) -> ApprovalDecision:
    if action == "resume" and not resume.eligible:
        return ApprovalDecision(
            action=action,
            allowed=False,
            reason=resume.reason,
            required_approval="resume-eligibility",
        )
    missing_for_action = [
        request for request in missing_approvals
        if request.action == action or action in {"approve", "resume"}
    ]
    if missing_for_action:
        return ApprovalDecision(
            action=action,
            allowed=False,
            reason="Missing required approval contract decisions.",
            required_approval=", ".join(sorted({item.required_approval for item in missing_for_action})),
        )
    return ApprovalDecision(
        action=action,
        allowed=False,
        reason="Execution is reserved in this loop; contract is display-only.",
        required_approval="execution-adapter",
    )


def build_approval_event(
    run_id: str,
    request: ApprovalRequest,
    decision: str,
    actor: str = "user",
    reason: str = "",
) -> dict[str, object]:
    return {
        "type": "approval",
        "name": "approval.decision",
        "detail": reason or f"{decision} {request.action}",
        "status": "done",
        "risk": {},
        "metadata": {
            "run_id": run_id,
            "action": request.action,
            "decision": decision,
            "actor": actor,
            "required_approval": request.required_approval,
            "source_event": request.source_event,
            "reason": reason,
        },
        "artifacts": {},
    }
