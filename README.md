# LoopForge

LoopForge is a local-first developer tool for turning agent work into inspectable, replayable, and improvable runs.

```text
Goal -> Context -> Plan -> Act -> Observe -> Adjust -> Verify -> Report
```

The current implementation is dependency-free and intentionally small. Each run persists its goal, event trace, and report under `.agent/runs/`.

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
|       +-- store.py
+-- tests/
    +-- test_loop.py
```

See also:

- [PROJECT.md](PROJECT.md)
- [ROADMAP.md](ROADMAP.md)
- [docs/product.md](docs/product.md)
- [docs/architecture.md](docs/architecture.md)

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
agent-loop "Build a tiny todo app"
```

This creates:

```text
.agent/runs/<run_id>/goal.json
.agent/runs/<run_id>/events.jsonl
.agent/runs/<run_id>/report.md
```

Run tests:

```powershell
python -m unittest discover -s tests
```

## Next Steps

- Add `loopforge inspect` for browsing run history.
- Add tool adapters for files, shell, Git, and tests.
- Add model/provider code behind a small interface.
- Add a desktop/web UI for run timelines, approvals, diffs, and verification output.
