"""Local persistence for agent loop runs."""

from __future__ import annotations

import json
from pathlib import Path

from ai_agent_loop.approval import evaluate_approval_contract
from ai_agent_loop.evidence import (
    read_evidence_manifest,
    scope_evidence_from_manifest_or_events,
    scope_from_manifest_or_events,
    write_evidence_manifest,
)
from ai_agent_loop.execution_adapter import evaluate_execution_adapter_contract
from ai_agent_loop.execution_gate import collect_execution_gate_events, evaluate_execution_gates
from ai_agent_loop.goal import Goal
from ai_agent_loop.critique import render_change_set_critique, render_critique
from ai_agent_loop.ledger import read_approval_ledger, summarize_ledger
from ai_agent_loop.loop import AgentStep, LoopResult
from ai_agent_loop.project import Project, ProjectRegistry
from ai_agent_loop.reviewer_handoff import render_reviewer_handoff_summary


class RunStore:
    def __init__(
        self,
        root: Path | str = ".agent",
        project: Project | None = None,
        project_path: Path | str | None = None,
    ) -> None:
        self.root = Path(root)
        self.registry = ProjectRegistry(self.root)
        self.project = project or self.registry.ensure_project(project_path)
        self.registry.ensure_project_files(self.project)

    def save(self, result: LoopResult) -> Path:
        run_dir = self.run_dir(result.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(run_dir / "goal.json", goal_to_record(result))
        self._write_events(run_dir / "events.jsonl", result)
        (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")
        write_evidence_manifest(run_dir, [step.to_dict() for step in result.steps])

        return run_dir

    def list_runs(self) -> list[dict[str, object]]:
        runs_dir = self.runs_dir()
        if not runs_dir.exists():
            return []

        records = []
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            try:
                records.append(self.read_summary(run_dir.name))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return records

    def read_summary(self, run_id: str) -> dict[str, object]:
        run_dir = self.run_dir(run_id)
        goal_path = run_dir / "goal.json"
        if not goal_path.exists():
            raise ValueError(f"run not found: {run_id}")

        goal_record = json.loads(goal_path.read_text(encoding="utf-8"))
        events = self.read_events(run_id)
        blocked_reason = find_blocked_reason(events)
        return {
            "run_id": run_id,
            "project": goal_record.get("project", "unknown"),
            "project_id": goal_record.get("project_id", self.project.id),
            "project_path": goal_record.get("project_path", self.project.path),
            "status": goal_record.get("status", infer_status(events)),
            "effective_status": infer_status(events),
            "blocked_reason": blocked_reason,
            "goal": goal_record.get("description", ""),
            "metadata": goal_record.get("metadata", {}),
            "event_count": len(events),
            "report_path": str(run_dir / "report.md"),
        }

    def update_goal_metadata(self, run_id: str, metadata: dict[str, object]) -> None:
        goal_path = self.run_dir(run_id) / "goal.json"
        if not goal_path.exists():
            raise ValueError(f"run not found: {run_id}")
        goal_record = json.loads(goal_path.read_text(encoding="utf-8"))
        current = goal_record.get("metadata", {})
        if not isinstance(current, dict):
            current = {}
        current.update(metadata)
        goal_record["metadata"] = current
        self._write_json(goal_path, goal_record)

    def read_events(self, run_id: str) -> list[dict[str, object]]:
        events_path = self.run_dir(run_id) / "events.jsonl"
        if not events_path.exists():
            return []
        events = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def read_report(self, run_id: str) -> str:
        report_path = self.run_dir(run_id) / "report.md"
        if not report_path.exists():
            raise ValueError(f"report not found: {run_id}")
        report = report_path.read_text(encoding="utf-8")
        events = self.read_events(run_id)
        effective_status = infer_status(events)
        report = ensure_summary_headings(report)
        report = replace_status_line(report, effective_status)
        report = replace_automation_summary(report, render_automation_summary(events))
        report = replace_git_summary(report, render_git_summary(events))
        report = replace_multi_agent_summary(report, render_multi_agent_summary(events))
        ledger = read_approval_ledger(self.run_dir(run_id))
        manifest = read_evidence_manifest(self.run_dir(run_id))
        report = replace_approval_readiness(report, render_approval_readiness(events, ledger, manifest))
        report = replace_evidence_bundle(report, render_evidence_bundle_summary(self.run_dir(run_id)))
        report = replace_reviewer_handoff(report, render_reviewer_handoff_summary(self.run_dir(run_id)))
        report = replace_change_set_critique(report, render_change_set_critique_for_events(events))
        report = replace_sharp_review(report, render_critique(events))
        blocked_reason = find_blocked_reason(events)
        if blocked_reason and "## Blocked Reason" not in report:
            report += f"\n## Blocked Reason\n\n{blocked_reason}\n"
        return report

    def append_event(self, run_id: str, event: dict[str, object]) -> None:
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        events_path = run_dir / "events.jsonl"
        with events_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        write_evidence_manifest(run_dir, self.read_events(run_id))

    def write_artifact(
        self,
        run_id: str,
        group: str,
        name: str,
        content: str,
    ) -> Path:
        artifact_dir = self.run_dir(run_id) / group
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        path.write_text(content, encoding="utf-8")
        write_evidence_manifest(self.run_dir(run_id), self.read_events(run_id))
        return path

    def next_artifact_id(self, run_id: str, prefix: str) -> str:
        artifact_dir = self.run_dir(run_id) / "commands"
        existing = len(list(artifact_dir.glob(f"{prefix}-*.stdout.txt"))) if artifact_dir.exists() else 0
        return f"{prefix}-{existing + 1:04d}"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir() / run_id

    def runs_dir(self) -> Path:
        return self.registry.project_dir(self.project) / "runs"

    @staticmethod
    def _write_json(path: Path, data: dict[str, object]) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_events(path: Path, result: LoopResult) -> None:
        lines = [
            json.dumps(step.to_dict(), ensure_ascii=False)
            for step in result.steps
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(result: LoopResult) -> str:
    criteria = "\n".join(
        f"- {item}" for item in result.goal.success_criteria
    )
    assumptions = "\n".join(
        f"- {item}" for item in result.goal.assumptions
    )
    steps = "\n".join(
        f"- {step.name}: {step.detail}" for step in result.steps
    )
    critique = render_critique([step.to_dict() for step in result.steps])
    change_critique = render_change_set_critique_for_events([step.to_dict() for step in result.steps])
    metadata = render_metadata(result.metadata)

    return (
        f"# Agent Run {result.run_id}\n\n"
        f"Status: {result.status}\n\n"
        f"Project: {result.project}\n\n"
        f"Project ID: {result.project_id}\n\n"
        f"Project Path: {result.project_path}\n\n"
        f"## Run Metadata\n\n{metadata}\n\n"
        f"## Goal\n\n{result.goal.description}\n\n"
        f"## Assumptions\n\n{assumptions}\n\n"
        f"## Success Criteria\n\n{criteria}\n\n"
        f"## Automation Summary\n\nNo autonomous actions recorded.\n\n"
        f"## Git Summary\n\nNo git actions recorded.\n\n"
        f"## Multi-Agent Summary\n\nNo multi-agent coordination recorded.\n\n"
        f"## Approval Readiness\n\n{render_approval_readiness([step.to_dict() for step in result.steps])}\n\n"
        f"## Evidence Bundle\n\n{render_evidence_bundle_summary(Path(result.run_id))}\n\n"
        f"## Reviewer Handoff\n\n{render_reviewer_handoff_summary(Path(result.run_id))}\n\n"
        f"## Change-set Critique\n\n{change_critique}\n\n"
        f"## Sharp Review\n\n{critique}\n\n"
        f"## Loop Trace\n\n{steps}\n"
    )


def goal_to_record(result: LoopResult) -> dict[str, object]:
    record = result.goal.to_dict()
    record["run_id"] = result.run_id
    record["project"] = result.project
    record["project_id"] = result.project_id
    record["project_path"] = result.project_path
    record["status"] = result.status
    record["metadata"] = result.metadata
    return record


def render_metadata(metadata: dict[str, object]) -> str:
    if not metadata:
        return "- provider: unknown"
    keys = [
        "provider",
        "provider_kind",
        "model",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    ]
    return "\n".join(f"- {key}: {metadata.get(key)}" for key in keys)


def render_automation_summary(events: list[dict[str, object]]) -> str:
    writes = [event for event in events if event.get("name") == "file.write"]
    commands = [event for event in events if event.get("name") == "shell.run"]
    verifications = [event for event in events if event.get("name") == "automation.verify"]
    next_steps = [event for event in events if event.get("name") == "automation.next_steps"]
    risk_events = [event for event in events if event.get("risk")]
    if not writes and not commands and not verifications:
        return "No autonomous actions recorded."

    return "\n\n".join(
        [
            "Changed files:\n" + render_event_paths(writes),
            "Commands:\n" + render_event_commands(commands),
            "Verification:\n" + render_event_details(verifications),
            "Risks:\n" + render_event_risks(risk_events),
            "Next steps:\n" + render_event_details(next_steps),
        ]
    )


def render_change_set_critique_for_events(events: list[dict[str, object]]) -> str:
    changed_files = collect_changed_files(events)
    test_summary = render_event_details(
        [event for event in events if event.get("name") in {"verify", "automation.verify"}]
    )
    risk_summary = render_event_risks([event for event in events if event.get("risk")])
    smoke_summary = "snapshot evidence present" if any(
        event.get("name") in {"workbench.snapshot", "execution.gate.evaluated"}
        for event in events
    ) else ""
    return render_change_set_critique(
        changed_files,
        test_summary=test_summary,
        risk_summary=risk_summary,
        smoke_summary=smoke_summary,
    )


def render_event_paths(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        metadata = event.get("metadata", {})
        lines.append(f"- {metadata.get('relative_path') or metadata.get('path')}")
    return "\n".join(lines)


def render_event_commands(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        metadata = event.get("metadata", {})
        lines.append(f"- {metadata.get('command')} -> exit {metadata.get('exit_code')}")
    return "\n".join(lines)


def render_event_details(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    return "\n".join(f"- {event.get('detail', '')}" for event in events)


def render_event_risks(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        risk = event.get("risk", {})
        lines.append(f"- {event.get('name')}: {risk.get('level')} - {risk.get('reason')}")
    return "\n".join(lines)


def render_git_summary(events: list[dict[str, object]]) -> str:
    git_events = [
        event for event in events
        if str(event.get("name", "")).startswith("git.")
    ]
    if not git_events:
        return "No git actions recorded."

    commits = [event for event in git_events if event.get("name") == "git.commit"]
    pushes = [event for event in git_events if event.get("name") == "git.push.blocked"]
    return "\n\n".join(
        [
            "Commit SHA:\n" + render_git_commits(commits),
            "Branch:\n" + render_git_branches(git_events),
            "Remote target:\n" + render_git_remote_targets(pushes),
            "Changed files:\n" + render_git_changed_files(git_events),
            "Commands:\n" + render_git_commands(git_events),
            "Risk decision:\n" + render_git_risk_decisions(git_events),
        ]
    )


def render_git_commits(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    return "\n".join(f"- {event.get('metadata', {}).get('commit_sha') or 'none'}" for event in events)


def render_git_branches(events: list[dict[str, object]]) -> str:
    branches = [
        str(event.get("metadata", {}).get("branch"))
        for event in events
        if event.get("metadata", {}).get("branch")
    ]
    if not branches:
        return "- unknown"
    return "\n".join(f"- {branch}" for branch in sorted(set(branches)))


def render_git_remote_targets(events: list[dict[str, object]]) -> str:
    targets = [
        str(event.get("metadata", {}).get("remote_target"))
        for event in events
        if event.get("metadata", {}).get("remote_target")
    ]
    if not targets:
        return "- none"
    return "\n".join(f"- {target}" for target in targets)


def render_git_changed_files(events: list[dict[str, object]]) -> str:
    files: list[str] = []
    for event in events:
        changed = event.get("metadata", {}).get("changed_files", [])
        if isinstance(changed, list):
            files.extend(str(item) for item in changed)
    if not files:
        return "- none"
    return "\n".join(f"- {path}" for path in sorted(set(files)))


def render_git_commands(events: list[dict[str, object]]) -> str:
    commands = [
        str(event.get("metadata", {}).get("command"))
        for event in events
        if event.get("metadata", {}).get("command")
    ]
    if not commands:
        return "- none"
    return "\n".join(f"- {command}" for command in commands)


def render_git_risk_decisions(events: list[dict[str, object]]) -> str:
    lines = []
    for event in events:
        risk = event.get("risk", {})
        lines.append(
            f"- {event.get('name')}: {event.get('status')} - "
            f"{risk.get('level')} - {event.get('detail')}"
        )
    return "\n".join(lines) if lines else "- none"


def render_approval_readiness(
    events: list[dict[str, object]],
    ledger_entries: list[dict[str, object]] | None = None,
    manifest: dict[str, object] | None = None,
) -> str:
    contract = evaluate_approval_contract(events)
    contract_data = contract.to_dict()
    evidence_manifest = manifest or {
        "status": "missing manifest",
        "manifest_file": "evidence_manifest.json",
        "scope_replay_source": "events",
    }
    scope = scope_from_manifest_or_events(evidence_manifest, events)
    evidence = scope_evidence_from_manifest_or_events(evidence_manifest, events)
    ledger = summarize_ledger(ledger_entries or [], scope)
    gates = evaluate_execution_gates(contract_data, ledger, evidence_manifest)
    adapters = evaluate_execution_adapter_contract(gates)
    changed_files = collect_changed_files(events)
    diff_events = [
        event for event in events
        if event.get("name") == "git.diff"
        or (
            isinstance(event.get("artifacts"), dict)
            and event.get("artifacts", {}).get("diff")
        )
    ]
    return "\n\n".join(
        [
            f"Mode:\n- {contract.mode}",
            "Executable actions:\n- none",
            "Reserved actions:\n- approve\n- resume\n- write\n- commit\n- push\n- delete",
            "Eligible actions:\n" + render_action_list(contract_data["eligible_actions"]),
            "Required approvals:\n" + render_approval_requests(contract_data["required_approvals"]),
            "Missing approvals:\n" + render_approval_requests(contract_data["missing_approvals"]),
            "Blocked actions:\n" + render_approval_decisions(contract_data["blocked_actions"]),
            "Resume eligibility:\n" + render_resume_eligibility(contract_data["resume_eligibility"]),
            "Evidence manifest:\n" + render_evidence_manifest(evidence_manifest),
            "Scope evidence:\n" + render_scope_evidence(evidence),
            "Ledger status:\n" + render_ledger_status(ledger),
            "Ledger integrity:\n" + render_ledger_integrity(ledger.get("integrity", {})),
            "Active approvals:\n" + render_ledger_entries(ledger["active_approvals"]),
            "Expired approvals:\n" + render_ledger_entries(ledger["expired_approvals"]),
            "Revoked approvals:\n" + render_ledger_entries(ledger["revoked_approvals"]),
            "Denied approvals:\n" + render_ledger_entries(ledger["denied_approvals"]),
            "Conflict approvals:\n" + render_ledger_entries(ledger["conflict_approvals"]),
            "Scope replay:\n" + render_scope_replay(ledger["scope_replay"]),
            "Execution readiness:\n" + render_execution_ready(ledger["execution_ready_approvals"]),
            "Execution gate:\n" + render_execution_gate(gates),
            "Execution adapter contract:\n" + render_execution_adapter_contract(adapters),
            "Gate audit:\n" + render_gate_audit(collect_execution_gate_events(events)),
            "Changed files:\n" + render_changed_files(changed_files),
            "Diff evidence:\n" + (f"- {len(diff_events)} diff artifact(s)" if diff_events else "- none"),
        ]
    )


def render_execution_gate(gates: dict[str, object]) -> str:
    records = gates.get("gates", [])
    if not isinstance(records, list) or not records:
        return "- none"
    lines = [f"- executable_actions: {len(gates.get('executable_actions', []))}"]
    for record in records:
        if not isinstance(record, dict):
            continue
        state = "ready" if record.get("ready_for_execution_adapter") else "blocked"
        lines.append(
            f"- {record.get('action')}: {state}; executable={record.get('executable')} - {record.get('reason')}"
        )
    return "\n".join(lines)


def render_execution_adapter_contract(adapters: dict[str, object]) -> str:
    records = adapters.get("adapters", [])
    if not isinstance(records, list) or not records:
        return "- none"
    lines = [
        f"- mode: {adapters.get('mode')}",
        f"- dry_run_only: {adapters.get('dry_run_only')}",
        f"- executable_actions: {len(adapters.get('executable_actions', []))}",
        f"- ready_adapter_count: {adapters.get('ready_adapter_count', 0)}",
        f"- blocked_adapter_count: {adapters.get('blocked_adapter_count', 0)}",
    ]
    for record in records:
        if not isinstance(record, dict):
            continue
        lines.append(
            f"- {record.get('adapter')}: {record.get('status')}; "
            f"execute_supported={record.get('execute_supported')} - {record.get('reason')}"
        )
    return "\n".join(lines)


def render_gate_audit(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        lines.append(
            f"- {metadata.get('created_at', '')}: "
            f"{metadata.get('manifest_integrity', 'unknown')} integrity, "
            f"{len(metadata.get('ready_actions', []))} ready, "
            f"{metadata.get('blocked_action_count', 0)} blocked, "
            f"{len(metadata.get('executable_actions', []))} executable"
        )
    return "\n".join(lines)


def render_evidence_manifest(manifest: dict[str, object]) -> str:
    core = manifest.get("core_hashes", {})
    artifacts = manifest.get("artifact_hashes", {})
    audit_chain = manifest.get("audit_chain", {})
    if not isinstance(core, dict):
        core = {}
    if not isinstance(artifacts, dict):
        artifacts = {}
    if not isinstance(audit_chain, dict):
        audit_chain = {}
    return "\n".join(
        [
            f"- status: {manifest.get('status', 'missing manifest')}",
            f"- integrity: {manifest.get('integrity_status', manifest.get('status', 'missing manifest'))}",
            f"- audit_status: {manifest.get('audit_status', 'missing audit digest')}",
            f"- audit_digest: {manifest.get('audit_digest', '') or 'missing'}",
            f"- audit_chain_head: {audit_chain.get('head', '') or 'missing'}",
            f"- audit_event_count: {audit_chain.get('event_count', 0)}",
            f"- file: {manifest.get('manifest_file', 'evidence_manifest.json')}",
            f"- replay_source: {manifest.get('scope_replay_source', 'events')}",
            f"- events.jsonl: {core.get('events.jsonl', '') or 'missing'}",
            f"- report.md: {core.get('report.md', '') or 'missing'}",
            f"- approvals.jsonl: {core.get('approvals.jsonl', '') or 'missing'}",
            f"- artifacts: {len(artifacts)}",
            f"- integrity_issues: {len(manifest.get('integrity_issues', []))}",
        ]
    )


def render_evidence_bundle_summary(run_dir: Path) -> str:
    bundle_root = run_dir / "evidence_bundle"
    if not bundle_root.exists():
        return "- none"
    manifests = sorted(bundle_root.glob("*/bundle_manifest.json"), reverse=True)
    if not manifests:
        return "- none"
    latest_path = manifests[0]
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return f"- bundle_count: {len(manifests)}\n- latest: unreadable"
    zip_path = run_dir / f"evidence_bundle-{latest.get('bundle_id')}.zip"
    return "\n".join(
        [
            f"- bundle_count: {len(manifests)}",
            f"- latest_bundle_id: {latest.get('bundle_id', '')}",
            f"- latest_bundle_hash: {latest.get('bundle_hash', '')}",
            f"- latest_file_count: {len(latest.get('files', []))}",
            f"- latest_zip: {zip_path}",
        ]
    )


def render_scope_evidence(evidence: dict[str, object]) -> str:
    lines = [
        f"- scope_hash: {evidence.get('scope_hash')}",
        f"- manifest_status: {evidence.get('manifest_status')}",
        f"- integrity_status: {evidence.get('integrity_status')}",
        f"- scope_replay_source: {evidence.get('scope_replay_source')}",
        f"- has_evidence: {evidence.get('has_evidence')}",
        f"- changed_files: {len(evidence.get('changed_files', []))}",
        f"- diff_hashes: {len(evidence.get('diff_hashes', []))}",
        f"- risk_scope: {len(evidence.get('risk_scope', []))}",
        f"- command_scope: {len(evidence.get('command_scope', []))}",
    ]
    return "\n".join(lines)


def render_scope_replay(records: object) -> str:
    if not isinstance(records, list) or not records:
        return "- none"
    lines = []
    for record in records:
        if not isinstance(record, dict):
            continue
        lines.append(
            f"- {record.get('decision_id')}: {record.get('replay_status')} "
            f"(signature: {record.get('signature_status')}, execution_ready: {record.get('execution_ready')})"
        )
    return "\n".join(lines) if lines else "- none"


def render_execution_ready(entries: object) -> str:
    if not isinstance(entries, list) or not entries:
        return "- none"
    return "\n".join(
        f"- {entry.get('decision_id')}: {entry.get('request_id')}"
        for entry in entries
        if isinstance(entry, dict)
    )


def render_ledger_status(ledger: dict[str, object]) -> str:
    return (
        f"- {ledger.get('status')} "
        f"({ledger.get('entry_count')} entries in {ledger.get('ledger_file')})"
    )


def render_ledger_integrity(integrity: object) -> str:
    if not isinstance(integrity, dict) or not integrity:
        return "- none"
    counts = integrity.get("status_counts", {})
    if not isinstance(counts, dict):
        counts = {}
    latest = integrity.get("latest_entry", {})
    if not isinstance(latest, dict):
        latest = {}
    lines = [
        "- counts: "
        + ", ".join(
            f"{name}={counts.get(name, 0)}"
            for name in ("active", "expired", "revoked", "denied", "conflict", "inactive")
        ),
        f"- execution_ready_count: {integrity.get('execution_ready_count', 0)}",
        "- latest: "
        + (
            f"{latest.get('decision_id')} {latest.get('entry_type')} {latest.get('status')} "
            f"by {latest.get('actor')} - {latest.get('reason')}"
            if latest else "none"
        ),
    ]
    chains = integrity.get("revocation_chains", [])
    if isinstance(chains, list) and chains:
        lines.append("  revocation_chains:")
        for chain in chains:
            if isinstance(chain, dict):
                lines.append(
                    f"  - {chain.get('decision_id')}: {chain.get('original_decision')} "
                    f"by {chain.get('original_actor')} revoked by {chain.get('revoked_by')} "
                    f"- {chain.get('reason')}"
                )
    reasons = integrity.get("execution_not_ready_reasons", [])
    if isinstance(reasons, list) and reasons:
        lines.append("  execution_not_ready:")
        for reason in reasons:
            if isinstance(reason, dict):
                lines.append(
                    f"  - {reason.get('decision_id')}: {reason.get('reason')}"
                )
    return "\n".join(lines)


def render_ledger_entries(entries: object) -> str:
    if not isinstance(entries, list) or not entries:
        return "- none"
    lines = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        lines.append(
            f"- {entry.get('decision_id')}: {entry.get('decision')} by {entry.get('actor')} "
            f"({entry.get('actor_id', 'unknown')}, {entry.get('actor_kind', 'unknown')}) "
            f"until {entry.get('expires_at') or 'never'} "
            f"[replay: {entry.get('replay_status')}, signature: {entry.get('signature_status')}, "
            f"algorithm: {entry.get('signature_algorithm', 'placeholder-local-audit-v1')}, "
            f"payload: {entry.get('signature_payload_hash', '') or 'missing'}] "
            f"- {entry.get('reason')}"
        )
    return "\n".join(lines) if lines else "- none"


def render_action_list(actions: object) -> str:
    if not isinstance(actions, list) or not actions:
        return "- none"
    return "\n".join(f"- {action}" for action in actions)


def render_approval_requests(requests: object) -> str:
    if not isinstance(requests, list) or not requests:
        return "- none"
    return "\n".join(
        f"- {item.get('action')}: {item.get('required_approval')} "
        f"({item.get('risk_level')}) - {item.get('reason')}"
        for item in requests
        if isinstance(item, dict)
    )


def render_approval_decisions(decisions: object) -> str:
    if not isinstance(decisions, list) or not decisions:
        return "- none"
    return "\n".join(
        f"- {item.get('action')}: {'allowed' if item.get('allowed') else 'denied'} - "
        f"{item.get('reason')}"
        for item in decisions
        if isinstance(item, dict)
    )


def render_resume_eligibility(resume: object) -> str:
    if not isinstance(resume, dict):
        return "- unknown"
    state = "eligible" if resume.get("eligible") else "not eligible"
    return f"- {state}: {resume.get('reason')}"


def collect_changed_files(events: list[dict[str, object]]) -> list[str]:
    files: list[str] = []
    for event in events:
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        changed = metadata.get("changed_files", [])
        if isinstance(changed, list):
            files.extend(str(item) for item in changed)
        if event.get("name") == "file.write":
            path = metadata.get("relative_path") or metadata.get("path")
            if path:
                files.append(str(path))
    return sorted(set(files))


def render_changed_files(files: list[str]) -> str:
    if not files:
        return "- none"
    return "\n".join(f"- {path}" for path in files)


def render_multi_agent_summary(events: list[dict[str, object]]) -> str:
    child_events = [event for event in events if event.get("name") == "multi.child_created"]
    reviewer_events = [event for event in events if event.get("name") == "multi.reviewer_decision"]
    conflict_events = [event for event in events if event.get("name") == "multi.conflict_detection"]
    merged_events = [event for event in events if event.get("name") == "multi.merged_summary"]
    if not child_events and not reviewer_events:
        return "No multi-agent coordination recorded."

    return "\n\n".join(
        [
            "Child runs:\n" + render_child_runs(child_events),
            "Conflict detection:\n" + render_event_details(conflict_events),
            "Reviewer decision:\n" + render_event_details(reviewer_events),
            "Merged summary:\n" + render_event_details(merged_events),
        ]
    )


def render_child_runs(events: list[dict[str, object]]) -> str:
    if not events:
        return "- none"
    lines = []
    for event in events:
        metadata = event.get("metadata", {})
        lines.append(
            f"- {metadata.get('role')}: {metadata.get('child_run_id')} "
            f"({metadata.get('goal')})"
        )
    return "\n".join(lines)


def infer_status(events: list[dict[str, object]]) -> str:
    statuses = {str(event.get("status", "")) for event in events}
    if "blocked" in statuses:
        return "blocked"
    automation_verifications = [
        event for event in events
        if event.get("name") == "automation.verify"
    ]
    if automation_verifications:
        return str(automation_verifications[-1].get("status", "unknown"))
    if "failed" in statuses:
        return "failed"
    if "cancelled" in statuses:
        return "cancelled"
    return "done" if events else "unknown"


def find_blocked_reason(events: list[dict[str, object]]) -> str:
    for event in reversed(events):
        if event.get("status") == "blocked":
            return str(event.get("detail") or event.get("metadata", {}).get("reason") or "")
    return ""


def replace_status_line(report: str, status: str) -> str:
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Status: "):
            lines[index] = f"Status: {status}"
            return "\n".join(lines) + ("\n" if report.endswith("\n") else "")
    return report


def ensure_summary_headings(report: str) -> str:
    if "## Sharp Review" not in report:
        return report
    additions = []
    if "## Automation Summary" not in report:
        additions.append("## Automation Summary\n\nNo autonomous actions recorded.\n")
    if "## Git Summary" not in report:
        additions.append("## Git Summary\n\nNo git actions recorded.\n")
    if "## Multi-Agent Summary" not in report:
        additions.append("## Multi-Agent Summary\n\nNo multi-agent coordination recorded.\n")
    if "## Approval Readiness" not in report:
        additions.append("## Approval Readiness\n\n" + render_approval_readiness([]) + "\n")
    if "## Evidence Bundle" not in report:
        additions.append("## Evidence Bundle\n\n- none\n")
    if "## Reviewer Handoff" not in report:
        additions.append("## Reviewer Handoff\n\n- none\n")
    if "## Change-set Critique" not in report:
        additions.append("## Change-set Critique\n\n" + render_change_set_critique_for_events([]) + "\n")
    if not additions:
        return report
    before, after = report.split("## Sharp Review", 1)
    inserted = "\n".join(additions)
    return f"{before}{inserted}\n## Sharp Review{after}"


def replace_sharp_review(report: str, critique: str) -> str:
    heading = "## Sharp Review"
    next_heading = "\n## Loop Trace"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{critique}\n{next_heading}{after}"


def replace_change_set_critique(report: str, critique: str) -> str:
    heading = "## Change-set Critique"
    next_heading = "\n## Sharp Review"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{critique}\n\n{next_heading}{after}"


def replace_evidence_bundle(report: str, summary: str) -> str:
    heading = "## Evidence Bundle"
    next_heading = "\n## Reviewer Handoff"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"


def replace_reviewer_handoff(report: str, summary: str) -> str:
    heading = "## Reviewer Handoff"
    next_heading = "\n## Change-set Critique"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"


def replace_automation_summary(report: str, summary: str) -> str:
    heading = "## Automation Summary"
    next_heading = "\n## Git Summary"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"


def replace_git_summary(report: str, summary: str) -> str:
    heading = "## Git Summary"
    next_heading = "\n## Multi-Agent Summary"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"


def replace_multi_agent_summary(report: str, summary: str) -> str:
    heading = "## Multi-Agent Summary"
    next_heading = "\n## Approval Readiness"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"


def replace_approval_readiness(report: str, summary: str) -> str:
    heading = "## Approval Readiness"
    next_heading = "\n## Evidence Bundle"
    if heading not in report or next_heading not in report:
        return report
    before, rest = report.split(heading, 1)
    _, after = rest.split(next_heading, 1)
    return f"{before}{heading}\n\n{summary}\n\n{next_heading}{after}"
