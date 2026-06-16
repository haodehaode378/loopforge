"""Command-line entry point."""

from __future__ import annotations

import argparse

from ai_agent_loop.agent import Agent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local agent work loop.")
    parser.add_argument("goal", nargs="?", help="Goal for the agent to process.")
    parser.add_argument(
        "--store",
        default=".agent",
        help="Directory used to save run artifacts.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Print the loop trace without saving artifacts.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.goal:
        build_parser().error("goal is required")

    agent = Agent(store_root=args.store)
    result = agent.run(args.goal, persist=not args.no_persist)

    for step in result.steps:
        print(f"{step.name} [{step.status}]: {step.detail}")

    print(f"run_id: {result.run_id}")
    print(f"status: {result.status}")
    if not args.no_persist:
        print(f"artifacts: {args.store}/runs/{result.run_id}")


if __name__ == "__main__":
    main()
