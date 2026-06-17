# LoopForge MVP Loops

This document defines what each development loop should complete and what happens when it does not complete. It is meant to keep implementation aligned with the product direction.

## Product Assumptions

- LoopForge is a local desktop developer tool.
- The default language is Chinese, with English as a switchable language pack.
- The first screen is a run history workbench with a sidebar.
- LoopForge manages multiple local projects.
- Full automation is allowed, but risky operations pause.
- Three repeated failures on the same objective or step produce `blocked`.
- Multi-agent roles are generated dynamically and can run in parallel.
- Reviewer agents decide merge conflicts between child runs.
- Model providers are user-configured.
- Token usage, cost, and elapsed time should be recorded when available.

## Loop Completion Rule

Every completed loop must end with a Git checkpoint.

Required close-out:

- Run the verification commands defined by that loop.
- Add a sharp review before the final report. The review must judge scope control, product alignment, verification quality, and remaining risk.
- Confirm private files remain ignored, especially `AGENTS.md`, `docs/loop-spec.md`, `.agent/`, and generated caches.
- Commit only the intended public source, tests, and documentation.
- Push the commit to GitHub.
- Report the commit SHA, pushed branch, and verification result.

If a loop is incomplete:

- Do not claim the loop is done.
- Do not push a success commit.
- Leave the run as `failed` or `blocked` with evidence and next steps.

## Loop 0: Product Lock

Goal: lock product direction before expanding implementation.

Must complete:

- Public product brief reflects desktop, Chinese-first, multi-project direction.
- Roadmap defines MVP order and stop conditions.
- Architecture defines stores, providers, tools, policy, memory, and privacy.
- OpenPencil has Chinese-first workbench and state designs.

Verification:

- Read `PROJECT.md`, `ROADMAP.md`, `docs/product.md`, and `docs/architecture.md`.
- Confirm no public docs expose private thinking files.
- Confirm tests still pass.

If incomplete:

- Do not add model providers or automation.
- Ask product questions or update docs until direction is unambiguous.

## Loop 1: Run History Foundation

Goal: make runs inspectable and stable enough for the desktop app.

Must complete:

- `loopforge run <goal>` creates a run.
- `loopforge inspect` lists recent runs.
- `loopforge inspect <run_id>` shows one run.
- `loopforge report <run_id>` displays a report.
- Runs have `done`, `failed`, `blocked`, or `cancelled` status.
- Runs belong to a project.

Verification:

- Unit tests cover run creation, listing, inspection, and report rendering.
- Manual CLI smoke test creates and inspects a run.
- Run artifacts are ignored from Git.

If incomplete:

- Keep UI work in design/prototype only.
- Do not implement tool execution yet.

## Loop 2: Project Registry

Goal: support multiple local projects.

Must complete:

- Add project registry.
- Add project metadata.
- Add per-project run storage.
- Add project selection in CLI and desktop app plan.
- Add project memory skeleton.

Verification:

- Two test projects can create separate run histories.
- Inspecting one project does not show the other project's runs.

If incomplete:

- Disable multi-project UI actions.
- Keep the app scoped to the current workspace.

## Loop 3: Safe Tool Layer

Goal: let the agent work in code while recording every action.

Must complete:

- File read tool.
- File search tool.
- Shell tool with stdout/stderr capture.
- Tool event recording in `events.jsonl`.
- Risk metadata for file read, file search, and shell execution.
- Risk interfaces for file delete and Git push without executable delete/push behavior.
- CLI smoke entry for recorded file and shell tool calls.

Verification:

- Tests cover each tool's event output.
- Shell output is saved as artifacts.
- Risk metadata exists for read, search, shell, delete, and push.
- File read rejects paths outside the selected project.

If incomplete:

- Disable `--auto` for write, delete, commit, and push.
- Allow inspect-only or dry-run mode.

## Loop 4: Policy And Blocked State

Goal: prevent dangerous automation from executing silently.

Must complete:

- Risk classifier for tool calls.
- Pause decision model for high-risk actions.
- Three-failure counter.
- `blocked` run status with reason and required decision.
- Reserved `resume` CLI entry point without full recovery execution.

Verification:

- Tests simulate three repeated failures and assert `blocked`.
- Tests simulate high-risk shell commands requiring approval.
- Reports explain why a run was blocked.
- Inspect shows blocked reason.

If incomplete:

- Do not enable full automation.
- Require manual confirmation for all write actions.

## Loop 5: Critique Engine

Goal: make sharp review a dynamic local engine instead of a fixed template.

Must complete:

- Add `critique.py`.
- Generate critique from run events.
- Add `loopforge critique <run_id>`.
- Make reports include dynamic Scope control, Product alignment, Verification quality, Risk review, and Next action.
- Cover successful, failed, and blocked runs in tests.

Verification:

- Successful run critique mentions verification.
- Blocked run critique mentions blocked decision and risk handling.
- Failed run critique mentions failed events and next action.
- Report automatically includes dynamic critique sections.

If incomplete:

- Keep static sharp review text and do not use critique output as a quality gate.

## Loop 6: Provider Settings

Goal: let users configure models without changing source code.

Must complete:

- Provider config model.
- OpenAI-compatible provider settings.
- Claude Code or Claude-compatible integration plan.
- Local HTTP provider settings.
- Deterministic fake provider for tests.
- `loopforge run --require-model` setup gate.
- Token, cost, and elapsed-time fields in run metadata.

Verification:

- A run can execute with deterministic fake provider in tests.
- Missing provider config produces a blocked setup decision.
- Provider settings avoid storing secrets in public files.
- Ordinary non-model runs continue with deterministic local fallback.

If incomplete:

- Keep deterministic local loop as fallback.
- Do not require a provider for non-model CLI commands.

## Loop 7: Autonomous Development Run

Goal: complete the first end-to-end autonomous code task.

Must complete:

- Agent can read project context.
- Agent can plan a bounded task.
- Agent can edit files.
- Agent can run tests.
- Agent can adjust after a failed check.
- Agent can write a final report.

Verification:

- Use a small fixture project.
- Assert files changed.
- Assert tests pass after the run.
- Assert report includes changed files, commands, verification, risks, next steps, time, tokens, and cost when available.

If incomplete:

- Keep the run as `failed` or `blocked`.
- Preserve all artifacts for review.
- Do not auto-commit.

## Loop 8: Git Commit And Push

Goal: let automation publish code when policy allows.

Must complete:

- Commit tool.
- Push tool.
- Branch policy.
- Protected/default branch detection where possible.
- Report includes commit SHA and remote target.

Verification:

- Tests use a local bare Git remote.
- Push requires policy approval when risky.
- Commit message and diff are recorded.

If incomplete:

- Stop after local diff and report.
- Do not push.

## Loop 9: Dynamic Multi-Agent

Goal: split larger work into dynamically generated child runs.

Must complete:

- Parent run creates child goals.
- Child runs execute in parallel when scopes do not overlap.
- Shared handoff context exists.
- Overlapping file edits are detected.
- Reviewer agent decides merge strategy.
- Parent report summarizes child results.

Verification:

- Tests create parent and child runs.
- Simulated conflict triggers reviewer decision.
- Reviewer failure blocks parent run.

If incomplete:

- Fall back to single-agent execution.
- Keep child outputs separate.

## Loop 10: Desktop Workbench

Goal: ship the first usable local desktop interface.

Must complete:

- Chinese default UI.
- English language switch.
- Project sidebar.
- Run history panel.
- Run timeline.
- Failed run review.
- Blocked decision panel.
- Multi-agent coordination view.
- Settings for provider, privacy, local-only mode, optional sync, and risk policy.

Verification:

- UI can read real run store data.
- Desktop smoke test opens a project and views a run.
- Language switch changes UI text.
- Text does not overflow at common desktop sizes.

If incomplete:

- Keep CLI as the reliable product surface.
- Do not add sync or team features.

## Loop 11: Project Progress Report

Goal: make LoopForge useful even when no code is changed.

Must complete:

- Summarize project state.
- Summarize recent runs.
- Summarize open risks.
- Summarize verification status.
- Suggest next steps.
- Export report as Markdown.

Verification:

- Report works on a project with multiple runs.
- Report includes failures and blocked decisions.
- Report does not include private excluded content.

If incomplete:

- Generate a minimal report from run metadata only.
- Mark missing sections clearly.
