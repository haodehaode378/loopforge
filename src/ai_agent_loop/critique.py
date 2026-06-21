"""Dynamic critique generation from run events."""

from __future__ import annotations

from pathlib import Path


CRITIQUE_SECTIONS = [
    "Scope control",
    "Product alignment",
    "Verification quality",
    "Risk review",
    "Next action",
]

CHANGE_SET_CRITIQUE_SECTIONS = [
    "Scope control",
    "Product alignment",
    "Verification quality",
    "Risk review",
    "Maintainability",
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
    automation_verifications = [
        event for event in events
        if event.get("name") == "automation.verify"
    ]

    return {
        "Scope control": critique_scope(tool_events, high_risk_events),
        "Product alignment": critique_alignment(event_names, tool_events),
        "Verification quality": critique_verification(
            event_names,
            statuses,
            failed_events,
            automation_verifications,
        ),
        "Risk review": critique_risk(high_risk_events, blocked_events),
        "Next action": critique_next_action(blocked_events, failed_events, tool_events),
    }


def render_critique(events: list[dict[str, object]]) -> str:
    critique = build_critique(events)
    return "\n".join(
        f"### {section}\n\n{critique[section]}\n"
        for section in CRITIQUE_SECTIONS
    ).rstrip()


def build_change_set_critique(
    changed_files: list[str],
    diff_text: str = "",
    test_summary: str = "",
    risk_summary: str = "",
    smoke_summary: str = "",
) -> dict[str, str]:
    return {
        "Scope control": critique_change_scope(changed_files),
        "Product alignment": critique_change_alignment(changed_files),
        "Verification quality": critique_change_verification(test_summary, smoke_summary),
        "Risk review": critique_change_risk(changed_files, diff_text, risk_summary),
        "Maintainability": critique_change_maintainability(changed_files, diff_text),
        "Next action": critique_change_next_action(test_summary, risk_summary),
    }


def render_change_set_critique(
    changed_files: list[str],
    diff_text: str = "",
    test_summary: str = "",
    risk_summary: str = "",
    smoke_summary: str = "",
) -> str:
    critique = build_change_set_critique(
        changed_files,
        diff_text=diff_text,
        test_summary=test_summary,
        risk_summary=risk_summary,
        smoke_summary=smoke_summary,
    )
    return "\n".join(
        f"### {section}\n\n{critique[section]}\n"
        for section in CHANGE_SET_CRITIQUE_SECTIONS
    ).rstrip()


def changed_files_from_diff_name_output(output: str) -> list[str]:
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


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
    automation_verifications: list[dict[str, object]],
) -> str:
    if "blocked" in statuses:
        return "Verification is incomplete because the run is blocked and needs a decision before success can be claimed."
    if automation_verifications and automation_verifications[-1].get("status") == "done":
        if failed_events:
            return "Verification recovered after adjustment; the final automation check passed."
        return "Verification passed through the autonomous run check."
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


def critique_change_scope(changed_files: list[str]) -> str:
    if not changed_files:
        return "No changed files were detected; there is no change-set to review."
    private = [path for path in changed_files if is_private_path(path)]
    if private:
        return f"Scope is unsafe because private files are present: {', '.join(private)}."
    if len(changed_files) > 12:
        return f"Scope is broad with {len(changed_files)} changed files; split the next loop if possible."
    return f"Scope is bounded to {len(changed_files)} public changed file(s)."


def critique_change_alignment(changed_files: list[str]) -> str:
    if any(path.startswith("src/ai_agent_loop/") for path in changed_files):
        return "The change aligns with LoopForge's developer-tool core by modifying agent loop source."
    if any(path.startswith("tests/") for path in changed_files):
        return "The change mostly improves verification coverage, which supports LoopForge's reliability direction."
    if any(path.startswith("docs/") for path in changed_files):
        return "The change is documentation-heavy; confirm implementation still advances the loop goal."
    return "Product alignment is unclear from file paths alone; inspect the diff before treating this as aligned."


def critique_change_verification(test_summary: str, smoke_summary: str) -> str:
    combined = f"{test_summary}\n{smoke_summary}".lower()
    if "failed" in combined or "error" in combined:
        return "Verification is not acceptable because the supplied summary includes failures or errors."
    if "ok" in combined and ("smoke" in combined or "chrome" in combined or "snapshot" in combined):
        return "Verification is strong: automated tests passed and a UI or snapshot smoke check is present."
    if "ok" in combined or "passed" in combined:
        return "Verification is partial: automated tests passed, but no smoke evidence was supplied."
    return "Verification is weak because no passing test summary was supplied."


def critique_change_risk(changed_files: list[str], diff_text: str, risk_summary: str) -> str:
    lower_diff = diff_text.lower()
    lower_risk = risk_summary.lower()
    if any(is_private_path(path) for path in changed_files):
        return "Risk is high because private files are included in the change-set."
    risky_terms = ("subprocess", "remove-item", "git push", "delete", "approve", "resume")
    found = [term for term in risky_terms if term in lower_diff]
    if found and "no execution" not in lower_risk and "reserved" not in lower_risk:
        return f"Risk needs review because the diff mentions sensitive actions: {', '.join(found)}."
    if "no execution" in lower_risk or "reserved" in lower_risk:
        return "Risk is controlled by explicit no-execution or reserved-action evidence."
    return "No obvious high-risk operation was detected from the supplied change-set evidence."


def critique_change_maintainability(changed_files: list[str], diff_text: str) -> str:
    line_count = len(diff_text.splitlines())
    source_files = [
        path for path in changed_files
        if path.startswith("src/") and Path(path).suffix == ".py"
    ]
    tests = [path for path in changed_files if path.startswith("tests/")]
    if source_files and not tests:
        return "Maintainability risk: source changed without matching test changes."
    if line_count > 800:
        return f"Maintainability risk: diff is large at {line_count} lines; prefer smaller loops."
    if source_files:
        return "Maintainability is acceptable: source changes are paired with tests or bounded diff size."
    return "Maintainability impact is low from the supplied file set."


def critique_change_next_action(test_summary: str, risk_summary: str) -> str:
    combined = f"{test_summary}\n{risk_summary}".lower()
    if "failed" in combined or "error" in combined:
        return "Fix the failing verification or risk finding before starting another loop."
    if "weak" in combined:
        return "Add a narrower verification command before committing the next loop."
    return "Proceed to the next loop after confirming the pushed commit matches the intended scope."


def is_private_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return (
        normalized == "AGENTS.md"
        or normalized == "docs/loop-spec.md"
        or normalized.startswith(".agent/")
        or normalized.startswith("output/")
    )
