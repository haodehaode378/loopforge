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

## MVP 2: Critique Engine

Goal: turn sharp review into a dynamic local rules engine.

- Generate critique from run events.
- Add Scope control, Product alignment, Verification quality, Risk review, and Next action sections.
- Add `loopforge critique <run_id>`.
- Make reports use dynamic critique content.
- Cover done, failed, and blocked runs.

Done means:

- Reports contain event-aware critique, not a static template.
- Blocked and failed runs produce specific next actions.
- Critique requires no model provider.

If not done:

- Keep static sharp review text and avoid using critique as a decision gate.

## MVP 3: Model Providers

Goal: support multiple model backends through one interface.

- Define a `ModelProvider` protocol.
- Add provider config for OpenAI-compatible APIs.
- Add provider config for Claude-compatible APIs.
- Add local model provider via HTTP endpoint.
- Add deterministic fake provider for tests.
- Store model name, latency, and token/cost metadata when available.
- Keep the core loop runnable without a model for testing.
- Reserve settings UI for choosing provider per project.

Done means:

- Users can configure providers without editing source files.
- Runs record model, latency, token usage, and cost when available.
- Missing provider config only blocks model-required runs.
- Provider settings store env var names, not secret values.

If not done:

- Keep deterministic/local loop behavior as the fallback.
- Mark model-dependent runs as `blocked` with a clear setup question.

## MVP 4: Automation Mode

Goal: allow full autonomous execution for developer tasks.

- Add `loopforge run --auto` for fixture-scoped autonomous runs.
- Add bounded step limits: one file target, one verification command, one retry.
- Add command allow/deny policies.
- Add retry and adjustment records.
- Add verification gates.
- Add final project report generation.
- Add risk classification for file deletion, Git push, secret exposure, and external transmission.
- Add automatic project memory updates after each run.

Done means:

- Minimal automation can read context, write fixture files, run shell verification, adjust once, and report evidence.
- High-risk actions pause instead of executing blindly.
- Three repeated failures produce a blocked run with evidence.
- Every run ends as `done`, `failed`, `blocked`, or `cancelled`.
- Real project writes, git push, and delete remain disabled until later policy loops; git commit is gated by branch policy.

If not done:

- Keep automation disabled for high-risk tools.
- Require manual resume for ambiguous or repeated failures.

## MVP 5: Multi-Agent Runs

Goal: coordinate dynamically generated subagents.

- Add parent/child run IDs.
- Generate roles from the goal instead of requiring a fixed role list.
- Support read-only child analysis runs.
- Add child summary artifacts.
- Add conflict detection placeholder for future write scopes.
- Let a reviewer child summarize child outputs.
- Add merged parent report output.

Done means:

- A parent run can spawn multiple child runs.
- Each child run has its own goal, artifacts, and report.
- Child runs record parent_run_id and stay read-only.
- Parent reports show child runs, conflict detection, reviewer decision, and merged summary.
- Reviewer decisions are recorded as events.

If not done:

- Fall back to a single-agent run.
- Keep child outputs separate until the reviewer step succeeds.

## MVP 6: Workbench UI

Goal: make LoopForge feel like software, not just a CLI.

- Ship a local read-only web workbench.
- Show project sidebar and run history.
- Show timeline of loop events.
- Show report sections for Git Summary, Automation Summary, Critique, and Multi-Agent Summary.
- Show status charts, failed or blocked reason distribution, provider metrics, command output previews, event JSON detail, and report section deep links.
- Show changed files, diff viewer, risk decisions, and disabled approval/resume skeleton.
- Show approval contract readiness: required approvals, missing approvals, eligible actions, blocked actions, and resume eligibility.
- Show approval ledger status, active approvals, expired approvals, revoked approvals, denied approvals, and conflict approvals.
- Show approval scope replay status and audit signature placeholders before any execution adapter exists.
- Show evidence manifest hashes for events, reports, approvals, diffs, command artifacts, changed files, risk scope, and command scope.
- Show failures and blocked states.
- Do not approve, retry, skip, resume, write, call models, log in, or sync.
- Add Chinese default UI with English language switch.
- Keep the UI local-first.

Done means:

- A user can inspect common workflows without the CLI.
- The app can switch between Chinese and English.
- Multiple projects can be opened from the local store.
- Reports, failures, and blocked states are visible without reading raw files.
- Raw evidence remains available through reports, timeline events, event JSON, command artifacts, and diff artifacts.

If not done:

- Keep CLI as the source of truth.
- Do not add cloud sync or team features.

## Later

- Reusable workflows.
- Scheduled automations.
- Project health reports.
- Team mode.
- Optional sync controlled from settings.
