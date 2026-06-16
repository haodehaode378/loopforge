# LoopForge Roadmap

## Release Rule

Every completed loop must be committed and pushed to GitHub after verification. If verification fails or the loop is incomplete, do not push a success commit; record the failure or blocked state first.

## MVP 0: Run Ledger

Status: in progress.

Goal: make every agent run inspectable on disk.

- Define `Goal`, `AgentStep`, and `LoopResult`.
- Persist `goal.json`, `events.jsonl`, and `report.md`.
- Add `loopforge inspect` to list recent runs and show one run.
- Add `loopforge report <run_id>` to print or open a report.
- Add tests for run persistence and inspection.
- Add project identity so runs belong to a specific local project.

Done means:

- A run can be created, listed, inspected, and reported from disk.
- A failed or blocked run is visible in history.
- The run store is stable enough for the desktop app to read.

If not done:

- Do not start provider integration.
- Fix persistence, inspection, and report readability first.

## MVP 1: Developer Tools

Goal: let the agent safely work inside a codebase.

- Add file search and file read tools.
- Add file edit and file delete tools with risk metadata.
- Add shell command tool with command logging.
- Add test runner detection for common projects.
- Add Git diff capture before and after a run.
- Add Git commit and Git push tools with policy checks.
- Store tool calls in `events.jsonl`.
- Add failure summaries when a command or check fails.
- Move a run to `blocked` after three consecutive failures on the same objective or step.

Done means:

- Reading, editing, deleting, shell, commit, and push actions are recorded.
- High-risk actions can be paused before execution.
- Failed commands keep stdout/stderr artifacts.
- A run cannot claim success without a verification event.

If not done:

- Disable `--auto` for write operations.
- Keep the run in inspect-only mode until the missing tool boundary is implemented.

## MVP 2: Model Providers

Goal: support multiple model backends through one interface.

- Define a `ModelProvider` protocol.
- Add provider config for OpenAI-compatible APIs.
- Add provider config for Claude Code style workflows or Claude-compatible APIs.
- Add provider config for Codex style workflows when available.
- Add local model provider via HTTP endpoint.
- Store model name, prompt hash, and token/cost metadata when available.
- Keep the core loop runnable without a model for testing.
- Add settings UI for choosing provider per project.

Done means:

- Users can configure providers without editing source files.
- Runs record model, latency, token usage, and cost when available.
- Blocked private content is excluded from model payloads.

If not done:

- Keep deterministic/local loop behavior as the fallback.
- Mark model-dependent runs as `blocked` with a clear setup question.

## MVP 3: Automation Mode

Goal: allow full autonomous execution for developer tasks.

- Add `loopforge run --auto`.
- Add bounded step limits.
- Add command allow/deny policies.
- Add retry and adjustment records.
- Add verification gates.
- Add final project report generation.
- Add risk classification for file deletion, Git push, secret exposure, and external transmission.
- Add automatic project memory updates after each run.

Done means:

- Full automation can read, write, run shell, commit, push, and delete within policy.
- High-risk actions pause instead of executing blindly.
- Three repeated failures produce a blocked run with evidence.
- Every run ends as `done`, `failed`, `blocked`, or `cancelled`.

If not done:

- Keep automation disabled for high-risk tools.
- Require manual resume for ambiguous or repeated failures.

## MVP 4: Multi-Agent Runs

Goal: coordinate dynamically generated subagents.

- Add parent/child run IDs.
- Generate roles from the goal instead of requiring a fixed role list.
- Support parallel child runs when their file/tool scopes do not conflict.
- Add shared context handoff files.
- Add conflict detection for overlapping file edits.
- Let a reviewer agent decide merge strategy for conflicting child outputs.
- Add merged report output.

Done means:

- A parent run can spawn multiple child runs.
- Each child run has its own goal, artifacts, and report.
- Conflicts are detected before merge.
- Reviewer decisions are recorded as events.

If not done:

- Fall back to a single-agent run.
- Keep child outputs separate until the reviewer step succeeds.

## MVP 5: Workbench UI

Goal: make LoopForge feel like software, not just a CLI.

- Ship a local desktop app.
- Show project sidebar and run history.
- Show timeline of loop events.
- Show file diffs and command output.
- Show failures and retries.
- Add dashboard charts for run status, verification, cost, duration, and failure causes.
- Let users approve, retry, skip, or resume steps.
- Add Chinese default UI with English language switch.
- Add settings for local-only mode, optional sync, provider config, and privacy rules.
- Keep the UI local-first.

Done means:

- A user can operate the common workflows without the CLI.
- The app can switch between Chinese and English.
- Multiple projects can be opened and managed.
- Reports, failures, and blocked states are visible without reading raw files.
- Charts are tied to concrete run data and never replace raw evidence.

If not done:

- Keep CLI as the source of truth.
- Do not add cloud sync or team features.

## Later

- Reusable workflows.
- Scheduled automations.
- Project health reports.
- Team mode.
- Optional sync controlled from settings.
