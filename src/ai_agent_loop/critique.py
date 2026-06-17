"""Dynamic critique generation from run events."""

from __future__ import annotations


CRITIQUE_SECTIONS = [
    "Scope control",
    "Product alignment",
    "Verification quality",
    "Risk review",
    "Next action",
]


def build_critique(events: list[dict[str, object]]) -> dict[str, str]:
    statuses = [str(event.get("status", "")) for event in events]
    event_names = [str(event.get("name", "")) for event in events]
    high_risk_events = [
        event for event in events
        if event.get("risk", {}).get("level") == "high"
    ]
    blocked_events = [event for event in events if event.get("status") == "blocked"]
    failed_events = [event for event in events if event.get("status") == "failed"]
    tool_events = [event for event in events if event.get("type") == "tool_call"]

    return {
        "Scope control": critique_scope(tool_events, high_risk_events),
        "Product alignment": critique_alignment(event_names, tool_events),
        "Verification quality": critique_verification(event_names, statuses, failed_events),
        "Risk review": critique_risk(high_risk_events, blocked_events),
        "Next action": critique_next_action(blocked_events, failed_events, tool_events),
    }


def render_critique(events: list[dict[str, object]]) -> str:
    critique = build_critique(events)
    return "\n".join(
        f"### {section}\n\n{critique[section]}\n"
        for section in CRITIQUE_SECTIONS
    ).rstrip()


def critique_scope(
    tool_events: list[dict[str, object]],
    high_risk_events: list[dict[str, object]],
) -> str:
    if not tool_events:
        return "Scope stayed minimal; no tool calls were recorded."
    if high_risk_events:
        return "Scope touched high-risk actions and was correctly constrained by policy."
    return f"Scope stayed inside recorded tool activity with {len(tool_events)} tool event(s)."


def critique_alignment(
    event_names: list[str],
    tool_events: list[dict[str, object]],
) -> str:
    if "policy.blocked" in event_names:
        return "The run aligned with the safety-first product direction by stopping instead of executing risky work."
    if tool_events:
        return "The run aligned with LoopForge's inspectable developer workflow by recording tool actions."
    return "The run aligned with the current foundation stage; it remained a structured local run."


def critique_verification(
    event_names: list[str],
    statuses: list[str],
    failed_events: list[dict[str, object]],
) -> str:
    if "blocked" in statuses:
        return "Verification is incomplete because the run is blocked and needs a decision before success can be claimed."
    if failed_events:
        return f"Verification found {len(failed_events)} failed event(s); the run should not be treated as complete."
    if "verify" in event_names:
        return "Verification is present in the loop trace and no failed events were recorded."
    return "Verification is weak because no explicit verify event was recorded."


def critique_risk(
    high_risk_events: list[dict[str, object]],
    blocked_events: list[dict[str, object]],
) -> str:
    if blocked_events:
        return f"Risk handling worked: {len(blocked_events)} blocked event(s) prevented unsafe continuation."
    if high_risk_events:
        return "High-risk metadata was recorded, but no blocked event is present; policy handling should be checked."
    return "No high-risk events were recorded."


def critique_next_action(
    blocked_events: list[dict[str, object]],
    failed_events: list[dict[str, object]],
    tool_events: list[dict[str, object]],
) -> str:
    if blocked_events:
        return "Resolve the blocked decision or use the reserved resume flow once recovery is implemented."
    if failed_events:
        return "Inspect failed tool output, adjust the plan, and rerun the narrowest failing step."
    if tool_events:
        return "Continue with the next planned loop only after reviewing recorded tool events and artifacts."
    return "Proceed to the next loop after confirming the generated report matches the goal."
