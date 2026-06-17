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
|       +-- cli.py
|       +-- goal.py
|       +-- loop.py
|       +-- project.py
|       +-- store.py
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
```

Inspect run history:

```powershell
loopforge inspect
loopforge inspect <run_id>
loopforge report <run_id>
loopforge critique <run_id>
```

Run recorded tool calls:

```powershell
loopforge --project E:\path\to\project tool read README.md
loopforge --project E:\path\to\project tool search *.py
loopforge --project E:\path\to\project tool shell "python -m unittest discover -s tests"
```

Use a specific project:

```powershell
loopforge --project E:\path\to\project run "Continue development"
loopforge --project E:\path\to\project inspect
```

Run tests:

```powershell
python -m unittest discover -s tests
```

## Next Steps

- Add tool adapters for files, shell, Git, and tests.
- Add model/provider code behind a small interface.
- Add a desktop/web UI for run timelines, approvals, diffs, and verification output.
