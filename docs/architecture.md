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
+-- goal.py     Goal model
+-- loop.py     Loop primitives
+-- provider.py Provider protocol and deterministic fake provider
+-- project.py  Project registry and metadata
+-- settings.py Project settings models without secret persistence
+-- store.py    Local run persistence
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

The desktop app should be the primary product surface. It reads and writes the same local store as the CLI.

Core screens:

- Run history workbench.
- Run timeline.
- Failed run review.
- Blocked run decision.
- Multi-agent coordination.
- Project report.
- Settings.

The app should support multiple local projects. Each project has isolated runs, memory, provider settings, privacy rules, and automation policy.

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
|               +-- diff.patch
|               +-- commands/
|               |   +-- <step_id>.stdout.txt
|               |   +-- <step_id>.stderr.txt
|               +-- artifacts/
```

Only `projects.json`, `project.json`, `memory.json`, optional `settings.json`, `goal.json`, `events.jsonl`, command artifacts, and `report.md` exist today.

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
- Git diff. Planned.
- Git commit. Planned.
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

Subagents should be generated dynamically from the goal. They can run in parallel when their scopes do not overlap.

The parent run owns:

- Child run creation.
- Shared context.
- Conflict detection.
- Reviewer decision requests.
- Merged report generation.

If child runs edit the same file, a reviewer agent decides the merge strategy and records the decision. If reviewer resolution fails, the parent run becomes `blocked`.

## Privacy Boundary

Before sending context to any model provider, LoopForge must filter:

- `.env` files.
- API keys and secrets.
- Private chat logs.
- Sensitive Git history.
- User-excluded paths.
- Files flagged by secret scanning.

Optional sync must be disabled by default and controlled from settings.
