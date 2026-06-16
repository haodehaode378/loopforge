# LoopForge Project Brief

## One-Liner

LoopForge is a local-first desktop agent workbench for developers who want autonomous coding agents with visible runs, durable history, failure review, multi-project context, and project reports.

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
- Multi-project support is a first-class product surface.
- Model providers are user-configured and should support OpenAI-compatible APIs, Claude Code style integrations, Codex-style integrations, and local providers over time.
- Multi-agent workflows are generated dynamically from the goal, run in parallel when possible, and stay explicit through parent/child run records.
- Efficiency and playfulness matter more than enterprise ceremony in the early product.
- Chinese is the default UI language; English is a switchable language pack.

## Product Shape

The first product should be a local desktop app. The default screen is a run history workbench with a sidebar for projects, runs, agents, automations, and settings.

LoopForge should manage multiple code projects. Each project owns its run history, memory, permissions, model settings, and reports.

## Automation Boundaries

The product should allow full automation for:

- Reading files.
- Editing files.
- Running shell commands.
- Creating Git commits.
- Pushing to Git remotes.
- Deleting files.

High-risk actions must pause for confirmation or policy approval. Examples include destructive deletes, credential exposure, pushing to protected branches, force pushes, publishing secrets, changing remote permissions, and any action that would upload blocked private content to a model provider.

After three consecutive failed attempts on the same objective or step, the run enters `blocked` and asks for a decision.

## Primary Workflows

The first version should optimize for:

- Reading an existing codebase and continuing development.
- Running autonomous implementation loops on an existing project.
- Summarizing project progress, risks, verification, and next steps.

Every successful run should answer:

- What changed?
- Why did it change?
- Which files changed?
- Which commands ran?
- Which tests/checks passed or failed?
- What risks remain?
- What should happen next?
- How much time, token usage, and cost were spent?

## Initial Scope

LoopForge starts as a CLI and local project format:

```text
.agent/runs/<run_id>/
+-- goal.json
+-- events.jsonl
+-- report.md
```

The first useful version should let a developer run, inspect, and compare agent work without depending on a cloud service.

The desktop app should sit on top of the same local run store, not replace it.

## Non-Goals For Now

- No hosted SaaS dashboard.
- No heavy workflow engine.
- No enterprise RBAC.
- No speculative plugin marketplace.
- No broad non-developer task management features.
- No default cloud sync. Sync can exist later as an explicit setting.
