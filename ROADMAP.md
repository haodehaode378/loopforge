# LoopForge Roadmap

## MVP 0: Run Ledger

Status: in progress.

Goal: make every agent run inspectable on disk.

- Define `Goal`, `AgentStep`, and `LoopResult`.
- Persist `goal.json`, `events.jsonl`, and `report.md`.
- Add `loopforge inspect` to list recent runs and show one run.
- Add `loopforge report <run_id>` to print or open a report.
- Add tests for run persistence and inspection.

## MVP 1: Developer Tools

Goal: let the agent safely work inside a codebase.

- Add file search and file read tools.
- Add shell command tool with command logging.
- Add test runner detection for common projects.
- Add Git diff capture before and after a run.
- Store tool calls in `events.jsonl`.
- Add failure summaries when a command or check fails.

## MVP 2: Model Providers

Goal: support multiple model backends through one interface.

- Define a `ModelProvider` protocol.
- Add provider config for OpenAI-compatible APIs.
- Add provider config for Claude-compatible APIs.
- Add local model provider via HTTP endpoint.
- Store model name, prompt hash, and token/cost metadata when available.
- Keep the core loop runnable without a model for testing.

## MVP 3: Automation Mode

Goal: allow full autonomous execution for developer tasks.

- Add `loopforge run --auto`.
- Add bounded step limits.
- Add command allow/deny policies.
- Add retry and adjustment records.
- Add verification gates.
- Add final project report generation.

## MVP 4: Multi-Agent Runs

Goal: coordinate specialized subagents.

- Add parent/child run IDs.
- Add roles such as planner, implementer, reviewer, tester, and reporter.
- Add shared context handoff files.
- Add conflict detection for overlapping file edits.
- Add merged report output.

## MVP 5: Workbench UI

Goal: make LoopForge feel like software, not just a CLI.

- Show run history.
- Show timeline of loop events.
- Show file diffs and command output.
- Show failures and retries.
- Let users approve, retry, skip, or resume steps.
- Keep the UI local-first.

## Later

- Reusable workflows.
- Scheduled automations.
- Project health reports.
- Team mode.
- Hosted sync.
