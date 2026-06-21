# LoopForge

LoopForge is a local-first developer tool for turning agent work into inspectable, replayable, and improvable runs.

```text
Goal -> Context -> Plan -> Act -> Observe -> Adjust -> Verify -> Report
```

The current implementation is dependency-free and intentionally small. Each project gets isolated metadata, memory, and run history under `.agent/projects/<project_id>/`.

## Product Direction

LoopForge is for solo developers, independent builders, and small teams who want agents to work more like an engineering system and less like a black-box chat window.

It will focus on:

- Recording agent work processes.
- Controlling code changes and command execution.
- Reviewing failures and generating project reports.
- Managing multi-agent tasks.
- Running developer automations.
- Supporting multiple model providers, including OpenAI, Claude-compatible providers, and local models.

## Layout

```text
.
+-- AGENTS.md
+-- README.md
+-- pyproject.toml
+-- src/
|   +-- ai_agent_loop/
|       +-- __init__.py
|       +-- agent.py
|       +-- autonomous.py
|       +-- cli.py
|       +-- evidence.py
|       +-- goal.py
|       +-- loop.py
|       +-- multi_agent.py
|       +-- provider.py
|       +-- project.py
|       +-- settings.py
|       +-- store.py
|       +-- workbench.py
+-- tests/
    +-- test_cli.py
    +-- test_loop.py
```

See also:

- [PROJECT.md](PROJECT.md)
- [ROADMAP.md](ROADMAP.md)
- [docs/product.md](docs/product.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/design-system.md](docs/design-system.md)
- [docs/mvp-loops.md](docs/mvp-loops.md)

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
loopforge run "Build a tiny todo app"
```

This creates:

```text
.agent/projects.json
.agent/projects/<project_id>/project.json
.agent/projects/<project_id>/memory.json
.agent/projects/<project_id>/runs/<run_id>/goal.json
.agent/projects/<project_id>/runs/<run_id>/events.jsonl
.agent/projects/<project_id>/runs/<run_id>/report.md
.agent/projects/<project_id>/runs/<run_id>/evidence_manifest.json
```

Inspect run history:

```powershell
loopforge inspect
loopforge inspect <run_id>
loopforge report <run_id>
loopforge critique <run_id>
loopforge critique changes --tests "79 tests OK" --risk "reserved no execution" --smoke "Chrome smoke OK"
```

Run recorded tool calls:

```powershell
loopforge --project E:\path\to\project tool read README.md
loopforge --project E:\path\to\project tool search *.py
loopforge --project E:\path\to\project tool shell "python -m unittest discover -s tests"
loopforge --project E:\path\to\project tool git status
loopforge --project E:\path\to\project tool git diff
loopforge --project E:\path\to\project tool git commit "Save bounded work"
loopforge --project E:\path\to\project tool git push origin main
```

Use a specific project:

```powershell
loopforge --project E:\path\to\project run "Continue development"
loopforge --project E:\path\to\project inspect
```

Optional provider settings live at `.agent/projects/<project_id>/settings.json`. Settings may contain an environment variable name such as `OPENAI_API_KEY`, but must not contain the secret value itself.

Require a configured model provider for a run:

```powershell
loopforge run --require-model "Draft an implementation plan"
```

Run the bounded autonomous fixture loop:

```powershell
loopforge --project E:\path\to\fixture run --auto "Implement one fixture change"
```

Autonomous writes currently require a `.loopforge-fixture` marker in the project root.

Run read-only multi-agent analysis:

```powershell
loopforge --project E:\path\to\project multi "Assess project readiness"
```

Multi-agent children are currently read-only and cannot write, commit, push, or delete.

Start the read-only local workbench:

```powershell
loopforge workbench
```

The workbench opens a local web UI for projects, run history, status charts, blocked or failed reason distribution, event timeline, changed files, diff previews, risk decisions, evidence manifest hashes, integrity status, audit digest status, approval contract readiness, approval ledger timeline, scope replay status, execution gate readiness, execution adapter contract, gate audit events, audit signature placeholders, disabled approval/resume skeleton, command output previews, event JSON detail, report section deep links, Git summary, automation summary, run critique, change-set critique, and multi-agent tree.

Inspect approval readiness and ledger entries without executing approval actions:

```powershell
loopforge approval <run_id>
```

Inspect or record execution gate audit evidence without executing reserved actions:

```powershell
loopforge approval gate <run_id>
loopforge approval gate <run_id> --record
```

Record an approval decision in the ledger without executing the reserved action:

```powershell
loopforge approval decide <run_id> --request-id <id> --decision approve|deny --actor <name> --reason <text> --expires-at <iso>
```

Run tests:

```powershell
python -m unittest discover -s tests
```

## Next Steps

- Expand autonomous writes beyond fixture projects with explicit policy approvals.
- Add policy approvals for git push instead of only recording blocked push risk.
- Expand multi-agent coordination from read-only summaries to approved write scopes.
- Implement real provider adapters behind the provider interface.
- Add audited execution adapters after approval decisions can be replay-checked and signed against current scope.
