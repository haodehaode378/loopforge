# LoopForge Architecture

## Overview

LoopForge is split into small layers:

```text
Desktop UI / CLI
  |
Agent Orchestrator
  |
Loop Engine
  |
Policy + Tools + Model Providers
  |
Project Store + Run Store
```

## Current Modules

```text
src/ai_agent_loop/
+-- agent.py    Agent facade
+-- autonomous.py Bounded fixture-only autonomous runner
+-- cli.py      CLI entry point
+-- critique.py Dynamic run critique
+-- evidence.py Evidence manifest hashes for replay
+-- goal.py     Goal model
+-- loop.py     Loop primitives
+-- multi_agent.py Read-only parent/child run orchestration
+-- provider.py Provider protocol and deterministic fake provider
+-- project.py  Project registry and metadata
+-- settings.py Project settings models without secret persistence
+-- store.py    Local run persistence
+-- workbench.py Read-only local web workbench
+-- events.py   Structured event records
+-- policy.py   Policy decisions and blocked-state rules
+-- risk.py     Risk metadata
+-- tools/      File and shell tool adapters
```

## Planned Modules

```text
src/ai_agent_loop/
+-- models/
|   +-- base.py
|   +-- openai_compatible.py
|   +-- claude_compatible.py
|   +-- local_http.py
+-- tools/
|   +-- files.py
|   +-- shell.py
|   +-- git.py
|   +-- tests.py
+-- projects/
|   +-- registry.py
|   +-- memory.py
+-- runs/
|   +-- inspect.py
|   +-- resume.py
|   +-- report.py
+-- policy.py
+-- events.py
```

## Desktop App Shape

The desktop app should be the primary product surface. The current implementation ships a read-only local web workbench that reads the same local store as the CLI.

Core screens:

- Run history workbench.
- Run timeline.
- Failed run review.
- Blocked run decision.
- Multi-agent coordination.
- Project report.
- Settings.

The app should support multiple local projects. Each project has isolated runs, memory, provider settings, privacy rules, and automation policy.

Current workbench behavior:

- `loopforge workbench` starts a local HTTP UI.
- `loopforge workbench --snapshot` prints the read-only JSON snapshot.
- The UI shows project list, run history, event timeline, report sections, Git Summary, Automation Summary, Sharp Review, and Multi-Agent Summary.
- The UI shows read-only status charts, failed or blocked reason distribution, provider token and cost placeholders, command output previews, event JSON detail, and report section deep links.
- The UI shows changed files, diff previews, risk decisions, and disabled approval/resume skeleton actions.
- The UI shows approval contract readiness from pure policy evaluation: required approvals, missing approvals, eligible actions, blocked actions, and resume eligibility.
- The UI and `loopforge approval <run_id>` show approval ledger status from `approvals.jsonl`.
- `loopforge approval decide <run_id> ...` only appends a ledger decision or denial after request id and scope validation; it does not execute reserved actions.
- Approval ledger entries carry scope evidence, replay status, and unsigned audit signature placeholders. Only active approvals with matched scope replay are marked execution-ready, but no execution adapter consumes them yet.
- `evidence_manifest.json` records hashes for core run files and referenced artifacts. Scope replay prefers manifest scope when present and falls back to event-derived scope for older runs with a visible `missing manifest` status.
- The UI does not approve, resume, write, call models, log in, or sync.

## Run Store

Each run should be durable and easy to inspect:

```text
.agent/
+-- projects.json
+-- projects/
|   +-- <project_id>/
|       +-- project.json
|       +-- memory.json
|       +-- settings.json
|       +-- policy.json
|       +-- runs/
|           +-- <run_id>/
|               +-- goal.json
|               +-- events.jsonl
|               +-- report.md
|               +-- approvals.jsonl
|               +-- evidence_manifest.json
|               +-- diff.patch
|               +-- commands/
|               |   +-- <step_id>.stdout.txt
|               |   +-- <step_id>.stderr.txt
|               +-- artifacts/
```

Only `projects.json`, `project.json`, `memory.json`, optional `settings.json`, `goal.json`, `events.jsonl`, command artifacts, `approvals.jsonl`, `evidence_manifest.json`, and `report.md` exist today.

## Project Memory

Project memory should be generated automatically after runs and updated as structured facts:

- Project goal.
- User preferences.
- Tech stack.
- Common commands.
- Historical failure causes.
- Files and folders that should not be touched.
- Privacy exclusions.

Memory updates must be visible in the app. Later versions can add manual approval, but the initial product should generate memory automatically.

## Model Provider Boundary

Model providers should not control the loop. They should only answer structured requests:

```text
messages + context + tool results -> model response
```

The loop engine owns:

- Step limits.
- Tool permissions.
- Event logging.
- Verification.
- Report generation.

Provider configuration is user-controlled. The current implementation has a provider settings model, deterministic fake provider, and local fallback metadata. It defines OpenAI-compatible, Claude-compatible, and local HTTP settings shapes without calling external APIs yet.

Runs record provider, model, latency, token usage, and cost fields when available. Settings may store an environment variable name for a key, but must not store the secret value.

## Tool Boundary

Every tool call should produce an event:

```json
{
  "type": "tool_call",
  "tool": "shell",
  "input": "...",
  "status": "done",
  "summary": "..."
}
```

Full outputs can be stored as separate files when large.

Tool classes:

- File read.
- File search.
- Fixture-only autonomous file write.
- File delete. Risk interface only for now.
- Shell command.
- Git status and diff.
- Git commit, allowed only on non-default branches or fixture projects.
- Git push. Risk interface only for now.
- Test runner. Planned.
- Report generator.

Each tool call must include risk metadata.

## Automation Policy

Full automation is allowed, but must be bounded:

- Step limit per run.
- Command logging.
- Allow/deny command policy.
- Verification requirement before reporting success.
- Diff capture for code changes.
- Three consecutive failures on the same objective or step produce `blocked`.
- Risky operations pause for a decision.

Current policy behavior:

- `loopforge run --auto` can read context, write one fixture-scoped file, run verification, adjust once, and report the result.
- Autonomous writes require a `.loopforge-fixture` marker in the project root.
- Git status and diff are recorded as read-only events.
- Git commit is blocked on default branches unless the project is a marked fixture.
- Git commit excludes `.agent`, `AGENTS.md`, and `docs/loop-spec.md` from automatic staging.
- Git push is never executed in the current loop; it records a blocked risk decision.
- High-risk shell commands are blocked before execution.
- Three consecutive failed shell executions append a blocked event.
- `inspect` and `report` show the blocked reason.
- `resume` is reserved as a CLI entry point but does not yet continue execution.

High-risk examples:

- File deletion outside expected generated artifacts.
- Git push to protected or default branches.
- Force push.
- Commands that alter global system state.
- Uploading private project content.
- Exposing secrets to model providers.
- Permission or remote configuration changes.

## Multi-Agent Coordination

Subagents should be generated dynamically from the goal. The current implementation supports read-only child analysis runs and a reviewer child run.

The parent run owns:

- Child run creation.
- Parent/child run metadata.
- Read-only context gathering.
- Conflict detection placeholder.
- Reviewer summary requests.
- Merged report generation.

Child runs cannot write files, commit, push, or delete in the current implementation. If later child runs edit the same file, a reviewer agent must decide the merge strategy and record the decision before merge.

## Privacy Boundary

Before sending context to any model provider, LoopForge must filter:

- `.env` files.
- API keys and secrets.
- Private chat logs.
- Sensitive Git history.
- User-excluded paths.
- Files flagged by secret scanning.

Optional sync must be disabled by default and controlled from settings.
