# LoopForge Architecture

## Overview

LoopForge is split into small layers:

```text
CLI / UI
  |
Agent Orchestrator
  |
Loop Engine
  |
Tools + Model Providers
  |
Run Store
```

## Current Modules

```text
src/ai_agent_loop/
+-- agent.py    Agent facade
+-- cli.py      CLI entry point
+-- goal.py     Goal model
+-- loop.py     Loop primitives
+-- store.py    Local run persistence
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
+-- runs/
|   +-- inspect.py
|   +-- resume.py
|   +-- report.py
+-- policy.py
+-- events.py
```

## Run Store

Each run should be durable and easy to inspect:

```text
.agent/runs/<run_id>/
+-- goal.json
+-- events.jsonl
+-- report.md
+-- diff.patch
+-- commands/
|   +-- <step_id>.stdout.txt
|   +-- <step_id>.stderr.txt
+-- artifacts/
```

Only `goal.json`, `events.jsonl`, and `report.md` exist today.

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

## Automation Policy

Full automation is allowed, but should still be bounded:

- Step limit per run.
- Command logging.
- Optional allow/deny command policy.
- Verification requirement before reporting success.
- Diff capture for code changes.
