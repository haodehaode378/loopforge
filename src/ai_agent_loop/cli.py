"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from ai_agent_loop.agent import Agent
from ai_agent_loop.store import RunStore
from ai_agent_loop.tools import FileTools, ShellTools


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

    inspect_parser = subparsers.add_parser("inspect", help="List or show runs.")
    inspect_parser.add_argument("run_id", nargs="?", help="Run ID to inspect.")

    report_parser = subparsers.add_parser("report", help="Show a run report.")
    report_parser.add_argument("run_id", help="Run ID to report.")

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

    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_parser().parse_args(normalize_argv(argv))
    if args.command == "run":
        run_goal(args.goal, args.store, args.project, persist=not args.no_persist)
        return

    if args.command == "inspect":
        inspect_runs(args.store, args.project, args.run_id)
        return

    if args.command == "report":
        show_report(args.store, args.project, args.run_id)
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
    commands = {"run", "inspect", "report", "tool"}
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
        return raw_args
    return raw_args


def run_goal(goal: str, store: str, project: str, persist: bool) -> None:
    agent = Agent(store_root=store, project_path=project)
    result = agent.run(goal, persist=persist)
    for step in result.steps:
        print(f"{step.name} [{step.status}]: {step.detail}")

    print(f"run_id: {result.run_id}")
    print(f"project: {result.project}")
    print(f"status: {result.status}")
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
            f"{summary['run_id']}  {summary['status']}  "
            f"{summary['project']}  {summary['event_count']} events  {summary['goal']}"
        )


def show_report(store: str, project: str, run_id: str) -> None:
    sys.stdout.write(RunStore(store, project_path=project).read_report(run_id))


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
    else:
        raise ValueError(f"unknown tool command: {args.tool_command}")

    print(f"run_id: {run_id}")


def create_tool_run(store: str, project: str) -> str:
    agent = Agent(store_root=store, project_path=project)
    result = agent.run("Recorded tool call", persist=True)
    return result.run_id


def print_summary(summary: dict[str, object]) -> None:
    print(f"run_id: {summary['run_id']}")
    print(f"project: {summary['project']}")
    print(f"project_id: {summary['project_id']}")
    print(f"project_path: {summary['project_path']}")
    print(f"status: {summary['status']}")
    print(f"goal: {summary['goal']}")
    print(f"event_count: {summary['event_count']}")
    print(f"report_path: {summary['report_path']}")


if __name__ == "__main__":
    main()
