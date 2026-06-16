# LoopForge Product Spec

## Positioning

LoopForge is an agent workbench for developers. It helps users run autonomous agents while keeping every goal, assumption, action, command, diff, failure, and report visible.

## Audience

Primary users:

- Solo developers.
- Independent builders.
- Small engineering teams.

They care about speed, control, and learning from agent runs. They do not want a heavy enterprise platform at the start.

## Jobs To Be Done

- I want an agent to work on a code task without losing track of what it did.
- I want to inspect why a run failed and decide what to try next.
- I want project reports that summarize progress, risks, and verification.
- I want to reuse workflows that worked well.
- I want multi-agent execution without hidden state.

## Core Experience

The first product loop:

```text
User enters goal
LoopForge creates a run
Agent gathers context
Agent plans
Agent acts through tools
LoopForge records every event
Agent verifies
LoopForge writes a report
User inspects or resumes the run
```

## MVP Commands

```powershell
loopforge run "Fix failing tests"
loopforge inspect
loopforge inspect <run_id>
loopforge report <run_id>
loopforge resume <run_id>
```

The current package still exposes `agent-loop`; the product CLI can be renamed to `loopforge` when the command surface stabilizes.

## Product Personality

- Fast.
- Local.
- Inspectable.
- Developer-native.
- Playful enough to invite experimentation, but strict about recording actions.

## Success Metrics

- A user can understand what happened in a run without reading raw logs.
- A failed run produces enough evidence to choose the next action.
- A successful run produces a useful report.
- The same project can accumulate a useful history of agent work.
