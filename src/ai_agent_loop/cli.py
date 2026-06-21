"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from ai_agent_loop.agent import Agent
from ai_agent_loop.approval import evaluate_approval_contract
from ai_agent_loop.evidence import (
    read_evidence_manifest,
    scope_evidence_from_manifest_or_events,
    scope_from_manifest_or_events,
    write_evidence_manifest,
)
from ai_agent_loop.execution_adapter import evaluate_execution_adapter_contract
from ai_agent_loop.execution_gate import build_execution_gate_event, evaluate_execution_gates
from ai_agent_loop.critique import render_critique
from ai_agent_loop.ledger import (
    append_approval_ledger,
    approval_requests_with_ids,
    build_ledger_decision_record,
    build_ledger_revocation_record,
    read_approval_ledger,
    summarize_ledger,
    validate_decision_record,
)
from ai_agent_loop.multi_agent import MultiAgentRunner
from ai_agent_loop.store import RunStore
from ai_agent_loop.tools import FileTools, GitTools, ShellTools
from ai_agent_loop.workbench import build_workbench_snapshot, serve_workbench


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local agent work loop.")
    parser.add_argument(
        "--store",
        default=".agent",
        help="Directory used to save run artifacts.",
    )
    parser.add_argument(
        "--project",
        default=".",
        help="Project directory used to isolate run history.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Create a new run.")
    run_parser.add_argument("goal", help="Goal for the agent to process.")
    run_parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Print the loop trace without saving artifacts.",
    )
    run_parser.add_argument(
        "--require-model",
        action="store_true",
        help="Block the run if no model provider is configured.",
    )
    run_parser.add_argument(
        "--auto",
        action="store_true",
        help="Run the bounded autonomous development loop.",
    )
    run_parser.add_argument(
        "--test-command",
        default="",
        help="Verification command for --auto runs.",
    )

    inspect_parser = subparsers.add_parser("inspect", help="List or show runs.")
    inspect_parser.add_argument("run_id", nargs="?", help="Run ID to inspect.")

    report_parser = subparsers.add_parser("report", help="Show a run report.")
    report_parser.add_argument("run_id", help="Run ID to report.")

    critique_parser = subparsers.add_parser("critique", help="Show dynamic run critique.")
    critique_parser.add_argument("run_id", help="Run ID to critique.")

    execution_parser = subparsers.add_parser("execution", help="Show reserved execution adapter contract.")
    execution_parser.add_argument("run_id", help="Run ID to inspect for execution adapter readiness.")

    approval_parser = subparsers.add_parser("approval", help="Show or record approval ledger decisions.")
    approval_subparsers = approval_parser.add_subparsers(dest="approval_command", required=True)
    show_parser = approval_subparsers.add_parser("show", help="Show approval contract and ledger.")
    show_parser.add_argument("run_id", help="Run ID to inspect for approval readiness.")
    gate_parser = approval_subparsers.add_parser("gate", help="Show or record execution gate audit evidence.")
    gate_parser.add_argument("run_id", help="Run ID to inspect for execution gate readiness.")
    gate_parser.add_argument(
        "--record",
        action="store_true",
        help="Append a read-only execution gate audit event to the run history.",
    )
    decide_parser = approval_subparsers.add_parser("decide", help="Record an approval ledger decision only.")
    decide_parser.add_argument("run_id", help="Run ID to record a decision for.")
    decide_parser.add_argument("--request-id", required=True)
    decide_parser.add_argument("--decision", choices=["approve", "deny"], required=True)
    decide_parser.add_argument("--actor", required=True)
    decide_parser.add_argument("--reason", required=True)
    decide_parser.add_argument("--expires-at", required=True)
    revoke_parser = approval_subparsers.add_parser("revoke", help="Record an approval ledger revocation only.")
    revoke_parser.add_argument("run_id", help="Run ID to record a revocation for.")
    revoke_parser.add_argument("--decision-id", required=True)
    revoke_parser.add_argument("--actor", required=True)
    revoke_parser.add_argument("--reason", required=True)

    multi_parser = subparsers.add_parser("multi", help="Run read-only multi-agent analysis.")
    multi_parser.add_argument("goal", help="Goal for the multi-agent run.")

    workbench_parser = subparsers.add_parser("workbench", help="Start the read-only local workbench.")
    workbench_parser.add_argument("--host", default="127.0.0.1")
    workbench_parser.add_argument("--port", type=int, default=8765)
    workbench_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Print workbench snapshot JSON instead of starting a server.",
    )

    resume_parser = subparsers.add_parser("resume", help="Reserved resume entry point.")
    resume_parser.add_argument("run_id", help="Run ID to resume.")

    tool_parser = subparsers.add_parser("tool", help="Run a recorded tool call.")
    tool_parser.add_argument(
        "--run-id",
        help="Existing run ID to append the tool event to.",
    )
    tool_subparsers = tool_parser.add_subparsers(dest="tool_command", required=True)

    read_parser = tool_subparsers.add_parser("read", help="Read a project file.")
    read_parser.add_argument("path", help="Project-relative file path.")

    search_parser = tool_subparsers.add_parser("search", help="Search project files.")
    search_parser.add_argument("pattern", help="Glob pattern, such as *.py.")
    search_parser.add_argument("--limit", type=int, default=50)

    shell_parser = tool_subparsers.add_parser("shell", help="Run a shell command.")
    shell_parser.add_argument("shell_command", help="Command to run.")
    shell_parser.add_argument("--timeout", type=int, default=60)

    git_parser = tool_subparsers.add_parser("git", help="Run a recorded git tool.")
    git_subparsers = git_parser.add_subparsers(dest="git_command", required=True)

    git_subparsers.add_parser("status", help="Record git status.")
    git_subparsers.add_parser("diff", help="Record git diff.")

    commit_parser = git_subparsers.add_parser("commit", help="Create a gated git commit.")
    commit_parser.add_argument("message", help="Commit message.")

    push_parser = git_subparsers.add_parser("push", help="Record blocked git push risk.")
    push_parser.add_argument("remote", nargs="?", default="origin")
    push_parser.add_argument("branch", nargs="?", default="")

    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_parser().parse_args(normalize_argv(argv))
    if args.command == "run":
        run_goal(
            args.goal,
            args.store,
            args.project,
            persist=not args.no_persist,
            require_model=args.require_model,
            auto=args.auto,
            test_command=args.test_command,
        )
        return

    if args.command == "inspect":
        inspect_runs(args.store, args.project, args.run_id)
        return

    if args.command == "report":
        show_report(args.store, args.project, args.run_id)
        return

    if args.command == "critique":
        show_critique(args.store, args.project, args.run_id)
        return

    if args.command == "execution":
        show_execution_adapter(args.store, args.project, args.run_id)
        return

    if args.command == "approval":
        if args.approval_command == "decide":
            record_approval_decision(args)
        elif args.approval_command == "revoke":
            record_approval_revocation(args)
        elif args.approval_command == "gate":
            show_execution_gate(args.store, args.project, args.run_id, args.record)
        else:
            show_approval(args.store, args.project, args.run_id)
        return

    if args.command == "multi":
        run_multi(args.goal, args.store, args.project)
        return

    if args.command == "workbench":
        run_workbench(args.store, args.host, args.port, args.snapshot)
        return

    if args.command == "resume":
        reserve_resume(args.store, args.project, args.run_id)
        return

    if args.command == "tool":
        run_tool(args)
        return

    build_parser().error("command or goal is required")


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize_argv(argv: list[str] | None) -> list[str]:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    commands = {
        "run",
        "inspect",
        "report",
        "critique",
        "execution",
        "approval",
        "multi",
        "workbench",
        "resume",
        "tool",
    }
    options_with_values = {"--store", "--project"}
    skip_next = False
    for index, value in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if value in options_with_values:
            skip_next = True
            continue
        if value.startswith("-"):
            continue
        if value not in commands:
            return raw_args[:index] + ["run"] + raw_args[index:]
        if value == "approval":
            return normalize_approval_argv(raw_args, index)
        return raw_args
    return raw_args


def normalize_approval_argv(raw_args: list[str], approval_index: int) -> list[str]:
    next_index = approval_index + 1
    if next_index >= len(raw_args):
        return raw_args
    next_value = raw_args[next_index]
    if next_value in {"show", "decide", "gate", "revoke"}:
        return raw_args
    if next_value.startswith("-"):
        return raw_args
    return raw_args[:next_index] + ["show"] + raw_args[next_index:]


def run_goal(
    goal: str,
    store: str,
    project: str,
    persist: bool,
    require_model: bool = False,
    auto: bool = False,
    test_command: str = "",
) -> None:
    agent = Agent(store_root=store, project_path=project)
    result = agent.run(
        goal,
        persist=persist,
        require_model=require_model,
        auto=auto,
        test_command=test_command,
    )
    for step in result.steps:
        print(f"{step.name} [{step.status}]: {step.detail}")

    status = result.status
    if persist:
        status = RunStore(store, project_path=project).read_summary(result.run_id)["effective_status"]

    print(f"run_id: {result.run_id}")
    print(f"project: {result.project}")
    print(f"status: {status}")
    print(f"provider: {result.metadata.get('provider')}")
    print(f"model: {result.metadata.get('model')}")
    if persist:
        print(f"artifacts: {store}/projects/{result.project_id}/runs/{result.run_id}")


def inspect_runs(store: str, project: str, run_id: str | None) -> None:
    run_store = RunStore(store, project_path=project)
    if run_id:
        summary = run_store.read_summary(run_id)
        events = run_store.read_events(run_id)
        print_summary(summary)
        print("events:")
        for event in events:
            print(
                f"- {event.get('name', 'unknown')}"
                f" [{event.get('status', 'unknown')}]: {event.get('detail', '')}"
            )
        return

    runs = run_store.list_runs()
    if not runs:
        print("No runs found.")
        return

    for summary in runs:
        print(
            f"{summary['run_id']}  {summary['effective_status']}  "
            f"{summary['project']}  {summary['event_count']} events  {summary['goal']}"
        )


def show_report(store: str, project: str, run_id: str) -> None:
    sys.stdout.write(RunStore(store, project_path=project).read_report(run_id))


def show_critique(store: str, project: str, run_id: str) -> None:
    events = RunStore(store, project_path=project).read_events(run_id)
    sys.stdout.write(render_critique(events) + "\n")


def show_execution_adapter(store: str, project: str, run_id: str) -> None:
    run_store = RunStore(store, project_path=project)
    events = run_store.read_events(run_id)
    contract = evaluate_approval_contract(events).to_dict()
    manifest = read_evidence_manifest(run_store.run_dir(run_id))
    scope = scope_from_manifest_or_events(manifest, events)
    ledger = summarize_ledger(read_approval_ledger(run_store.run_dir(run_id)), scope)
    gates = evaluate_execution_gates(contract, ledger, manifest)
    adapters = evaluate_execution_adapter_contract(gates)
    print(f"run_id: {run_id}")
    print("execution_adapter_contract:")
    print_json_lines(adapters)
    print("No approval, resume, write, commit, push, or delete action was executed.")


def show_approval(store: str, project: str, run_id: str) -> None:
    run_store = RunStore(store, project_path=project)
    events = run_store.read_events(run_id)
    contract_model = evaluate_approval_contract(events)
    contract = contract_model.to_dict()
    manifest = read_evidence_manifest(run_store.run_dir(run_id))
    scope = scope_from_manifest_or_events(manifest, events)
    requests = approval_requests_with_ids(run_id, contract_model, scope)
    ledger = summarize_ledger(read_approval_ledger(run_store.run_dir(run_id)), scope)
    evidence = scope_evidence_from_manifest_or_events(manifest, events)
    gates = evaluate_execution_gates(contract, ledger, manifest)
    print(f"run_id: {run_id}")
    print(f"mode: {contract['mode']}")
    print("evidence_manifest:")
    print_json_lines(manifest)
    print(f"scope_hash: {evidence['scope_hash']}")
    print("scope_evidence:")
    print_json_lines(evidence)
    print("required_approvals:")
    print_json_lines(requests)
    print("missing_approvals:")
    print_json_lines(contract["missing_approvals"])
    print("eligible_actions:")
    for action in contract["eligible_actions"]:
        print(f"- {action}")
    print("blocked_actions:")
    print_json_lines(contract["blocked_actions"])
    print(f"resume_eligibility: {contract['resume_eligibility']}")
    print(f"ledger_status: {ledger['status']}")
    print("active_approvals:")
    print_json_lines(ledger["active_approvals"])
    print("expired_approvals:")
    print_json_lines(ledger["expired_approvals"])
    print("revoked_approvals:")
    print_json_lines(ledger["revoked_approvals"])
    print("denied_approvals:")
    print_json_lines(ledger["denied_approvals"])
    print("conflict_approvals:")
    print_json_lines(ledger["conflict_approvals"])
    print("scope_replay:")
    print_json_lines(ledger["scope_replay"])
    print("execution_ready_approvals:")
    print_json_lines(ledger["execution_ready_approvals"])
    print("execution_gate:")
    print_json_lines(gates)


def show_execution_gate(store: str, project: str, run_id: str, record: bool = False) -> None:
    run_store = RunStore(store, project_path=project)
    events = run_store.read_events(run_id)
    contract = evaluate_approval_contract(events).to_dict()
    manifest = read_evidence_manifest(run_store.run_dir(run_id))
    scope = scope_from_manifest_or_events(manifest, events)
    ledger = summarize_ledger(read_approval_ledger(run_store.run_dir(run_id)), scope)
    gates = evaluate_execution_gates(contract, ledger, manifest)
    print(f"run_id: {run_id}")
    print("execution_gate:")
    print_json_lines(gates)
    if not record:
        print("gate_event_recorded: false")
        print("No approval, resume, write, commit, push, or delete action was executed.")
        return

    event = build_execution_gate_event(run_id, gates, manifest)
    run_store.append_event(run_id, event)
    print("gate_event_recorded: true")
    print(f"event_name: {event['name']}")
    print("No approval, resume, write, commit, push, or delete action was executed.")


def record_approval_decision(args: argparse.Namespace) -> None:
    run_store = RunStore(args.store, project_path=args.project)
    events = run_store.read_events(args.run_id)
    contract = evaluate_approval_contract(events)
    manifest = read_evidence_manifest(run_store.run_dir(args.run_id))
    scope = scope_from_manifest_or_events(manifest, events)
    entries = read_approval_ledger(run_store.run_dir(args.run_id))
    request, error = validate_decision_record(
        args.run_id,
        contract,
        scope,
        entries,
        args.request_id,
    )
    if error:
        print(f"decision_recorded: false")
        print(error)
        return
    if request is None:
        print("decision_recorded: false")
        print("request-id is not part of the current approval contract.")
        return
    try:
        parse_cli_time(args.expires_at)
    except ValueError as error:
        print("decision_recorded: false")
        print(f"invalid expires-at: {error}")
        return
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ledger_decision = "approved" if args.decision == "approve" else "denied"
    entry = build_ledger_decision_record(
        args.run_id,
        request,
        actor=args.actor,
        created_at=created_at,
        expires_at=args.expires_at,
        scope=scope,
        decision=ledger_decision,
        reason=args.reason,
    )
    append_approval_ledger(run_store.run_dir(args.run_id), entry)
    write_evidence_manifest(run_store.run_dir(args.run_id), events)
    print("decision_recorded: true")
    print(f"request_id: {entry['request_id']}")
    print(f"decision_id: {entry['decision_id']}")
    print(f"decision: {entry['decision']}")
    print("No approval, resume, write, commit, push, or delete action was executed.")


def record_approval_revocation(args: argparse.Namespace) -> None:
    run_store = RunStore(args.store, project_path=args.project)
    run_dir = run_store.run_dir(args.run_id)
    entries = read_approval_ledger(run_dir)
    decision_ids = {
        str(entry.get("decision_id"))
        for entry in entries
        if entry.get("entry_type") != "revocation"
    }
    revoked_ids = {
        str(entry.get("decision_id"))
        for entry in entries
        if entry.get("entry_type") == "revocation"
    }
    if args.decision_id not in decision_ids:
        print("revocation_recorded: false")
        print("decision-id is not part of the current approval ledger.")
        return
    if args.decision_id in revoked_ids:
        print("revocation_recorded: false")
        print("conflict: decision-id is already revoked.")
        return

    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = build_ledger_revocation_record(
        args.decision_id,
        actor=args.actor,
        created_at=created_at,
        reason=args.reason,
    )
    append_approval_ledger(run_dir, entry)
    write_evidence_manifest(run_dir, run_store.read_events(args.run_id))
    print("revocation_recorded: true")
    print(f"decision_id: {entry['decision_id']}")
    print(f"actor: {entry['actor']}")
    print("No approval, resume, write, commit, push, or delete action was executed.")


def parse_cli_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def print_json_lines(items: object) -> None:
    if isinstance(items, dict):
        print(f"- {json.dumps(items, ensure_ascii=False, sort_keys=True)}")
        return
    if not isinstance(items, list) or not items:
        print("- none")
        return
    for item in items:
        print("- " + json.dumps(item, ensure_ascii=False, sort_keys=True))


def run_multi(goal: str, store: str, project: str) -> None:
    result = MultiAgentRunner(store_root=store, project_path=project).run(goal)
    print(f"parent_run_id: {result.parent_run_id}")
    print(f"child_run_ids: {', '.join(result.child_run_ids)}")
    print(f"reviewer_run_id: {result.reviewer_run_id}")


def run_workbench(store: str, host: str, port: int, snapshot: bool) -> None:
    if snapshot:
        print(json.dumps(build_workbench_snapshot(store), ensure_ascii=False, indent=2))
        return
    serve_workbench(root=store, host=host, port=port)


def reserve_resume(store: str, project: str, run_id: str) -> None:
    summary = RunStore(store, project_path=project).read_summary(run_id)
    print(f"resume_reserved: {run_id}")
    print(f"status: {summary['effective_status']}")
    if summary.get("blocked_reason"):
        print(f"blocked_reason: {summary['blocked_reason']}")
    print("Resume execution is reserved for a later loop.")


def run_tool(args: argparse.Namespace) -> None:
    run_id = args.run_id or create_tool_run(args.store, args.project)
    store = RunStore(args.store, project_path=args.project)

    if args.tool_command == "read":
        content = FileTools(store, run_id).read_file(args.path)
        sys.stdout.write(content)
    elif args.tool_command == "search":
        matches = FileTools(store, run_id).search_files(args.pattern, args.limit)
        for match in matches:
            print(match)
    elif args.tool_command == "shell":
        result = ShellTools(store, run_id).run(args.shell_command, args.timeout)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        print(f"exit_code: {result.exit_code}")
    elif args.tool_command == "git":
        run_git_tool(args, store, run_id)
    else:
        raise ValueError(f"unknown tool command: {args.tool_command}")

    print(f"run_id: {run_id}")


def create_tool_run(store: str, project: str) -> str:
    agent = Agent(store_root=store, project_path=project)
    result = agent.run("Recorded tool call", persist=True)
    return result.run_id


def run_git_tool(args: argparse.Namespace, store: RunStore, run_id: str) -> None:
    tools = GitTools(store, run_id)
    if args.git_command == "status":
        result = tools.status()
    elif args.git_command == "diff":
        result = tools.diff()
    elif args.git_command == "commit":
        result = tools.commit(args.message)
    elif args.git_command == "push":
        result = tools.push(args.remote, args.branch)
    else:
        raise ValueError(f"unknown git command: {args.git_command}")

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    print(f"exit_code: {result.exit_code}")
    print(f"branch: {result.branch}")
    if result.commit_sha:
        print(f"commit_sha: {result.commit_sha}")


def print_summary(summary: dict[str, object]) -> None:
    print(f"run_id: {summary['run_id']}")
    print(f"project: {summary['project']}")
    print(f"project_id: {summary['project_id']}")
    print(f"project_path: {summary['project_path']}")
    print(f"status: {summary['effective_status']}")
    if summary.get("blocked_reason"):
        print(f"blocked_reason: {summary['blocked_reason']}")
    metadata = summary.get("metadata", {})
    if isinstance(metadata, dict):
        print(f"provider: {metadata.get('provider')}")
        print(f"model: {metadata.get('model')}")
    print(f"goal: {summary['goal']}")
    print(f"event_count: {summary['event_count']}")
    print(f"report_path: {summary['report_path']}")


if __name__ == "__main__":
    main()
