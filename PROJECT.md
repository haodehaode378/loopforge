# LoopForge Project Brief

## One-Liner

LoopForge is a local-first agent workbench for developers who want autonomous coding agents with visible loops, durable run history, failure review, and project reports.

## Target Users

- Solo developers building personal tools or side projects.
- Independent developers who use AI heavily and want stronger control.
- Small teams that need agent output to be inspectable before it touches shared code.

## Core Problem

AI agents can already plan, edit code, run commands, and produce useful work, but the process is often hard to inspect:

- What goal did the agent actually optimize for?
- What context did it read?
- What assumptions did it make?
- What files and commands did it touch?
- Why did a run fail?
- Can a useful workflow be reused?

LoopForge turns those steps into structured run artifacts.

## Product Principles

- Local-first by default.
- Full automation is allowed, but every action must be recorded.
- Developer workflows come first: code, shell, tests, Git, reports.
- Multi-model support should sit behind a small provider interface.
- Multi-agent workflows should be explicit, not hidden behind magic.
- Efficiency and playfulness matter more than enterprise ceremony in the early product.

## Initial Scope

LoopForge starts as a CLI and local project format:

```text
.agent/runs/<run_id>/
+-- goal.json
+-- events.jsonl
+-- report.md
```

The first useful version should let a developer run, inspect, and compare agent work without depending on a cloud service.

## Non-Goals For Now

- No hosted SaaS dashboard.
- No heavy workflow engine.
- No enterprise RBAC.
- No speculative plugin marketplace.
- No broad non-developer task management features.
