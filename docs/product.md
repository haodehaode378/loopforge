# LoopForge Product Spec

## Positioning

LoopForge is a local desktop agent workbench for developers. It helps users run autonomous agents while keeping every project, goal, assumption, action, command, diff, failure, and report visible.

## Audience

Primary users:

- Solo developers.
- Independent builders.
- Small engineering teams.

They care about speed, control, and learning from agent runs. They do not want a heavy enterprise platform at the start.

The default interface language is Chinese. English is available through a language switch.

## Jobs To Be Done

- I want an agent to work on a code task without losing track of what it did.
- I want to inspect why a run failed and decide what to try next.
- I want project reports that summarize progress, risks, and verification.
- I want to reuse workflows that worked well.
- I want multi-agent execution without hidden state.
- I want to manage multiple local projects from one desktop app.
- I want full automation, but high-risk actions should pause before damage.

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

The default home screen should be a run history panel with a sidebar. The sidebar should include projects, run history, agents, automations, reports, and settings.

## Initial Workflow Priority

1. Read an existing codebase and continue development.
2. Read an existing codebase and continue development in autonomous mode.
3. Summarize project progress, risks, verification, and next steps.

New-project creation can exist later, but it should not dominate the first product experience.

## Automation Rules

Allowed automation tools:

- Read files.
- Edit files.
- Run shell commands.
- Delete files.
- Create Git commits.
- Push to Git remotes.

High-risk actions must pause for a decision. This includes destructive deletes, risky Git operations, force push, protected branch push, secret exposure, uploading private content, changing remote permissions, and ambiguous shell commands.

After three consecutive failures on the same objective or step, the run becomes `blocked`.

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
- Calm and professional.
- Playful enough to invite experimentation, but strict about recording actions.

## Terminology

Chinese default terms:

- `run`: 运行记录
- `agent`: 智能体
- `loop`: 工作循环
- `goal`: 目标
- `blocked`: 已阻塞
- `failed`: 失败
- `done`: 完成

English terms should remain available in the language pack and in technical contexts such as command output, code, and provider names.

## UI And Visualization

The app should use a calm developer-tool interface rather than a marketing-style interface. The main product surface is the workbench: project sidebar, run history, run timeline, detail inspector, command output, diff viewer, and report panel.

Charts should explain agent work quality and project progress, not decorate the page. See [design-system.md](design-system.md) for chart rules, visual states, and component guidance.

## Settings

The settings surface should include:

- Model provider configuration.
- Optional Codex or Claude Code integration.
- Local model endpoint configuration.
- Local-only mode.
- Optional sync toggle.
- Privacy rules for excluded files and folders.
- Risk policy for shell, delete, commit, and push actions.

## Privacy Rules

The product must not upload these by default:

- `.env` files.
- API keys and secrets.
- Private chat history.
- Sensitive Git history.
- Files excluded by project privacy rules.
- Any file matched by secret detection.

## Success Metrics

- A user can understand what happened in a run without reading raw logs.
- A failed run produces enough evidence to choose the next action.
- A successful run produces a useful report.
- The same project can accumulate a useful history of agent work.
- High-risk actions do not execute silently.
- Project reports include files changed, commands run, verification, risks, next steps, time, tokens, and cost.
