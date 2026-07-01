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
- Real project writes remain blocked unless the project is a marked fixture.

Verification:

- Use a small fixture project.
- Assert files changed.
- Assert tests pass after the run.
- Assert report includes changed files, commands, verification, risks, next steps, time, tokens, and cost when available.
- Assert non-fixture auto writes become blocked.

If incomplete:

- Keep the run as `failed` or `blocked`.
- Preserve all artifacts for review.
- Do not auto-commit.

## Loop 8: Git Commit And Push

Goal: let automation publish code when policy allows.

Must complete:

- Commit tool.
- Push risk interface without execution.
- Branch policy.
- Protected/default branch detection where possible.
- Report includes commit SHA and remote target.

Verification:

- Tests use a local Git repository.
- Push records a blocked policy decision and remote target.
- Commit message and diff are recorded.

If incomplete:

- Stop after local diff and report.
- Do not push.

## Loop 9: Dynamic Multi-Agent

Goal: split larger work into dynamically generated child runs.

Must complete:

- Parent run creates child goals.
- Child runs perform read-only analysis only.
- Parent and child runs record `parent_run_id` and `child_run_ids`.
- Conflict detection placeholder exists.
- Reviewer child run summarizes child results.
- Parent report summarizes child results.

Verification:

- Tests create parent and child runs.
- Tests assert child runs have independent reports and artifacts.
- Tests assert child runs do not write files, commit, push, delete, or run shell commands.
- Parent report includes child runs, conflict detection, reviewer decision, and merged summary.

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
- Git Summary, Automation Summary, and Critique sections.
- No approve, resume, write, model call, login, or sync actions.

Verification:

- UI can read real run store data.
- Desktop smoke test opens a project and views a run.
- Language switch changes UI text.
- Browser screenshot verifies the workbench renders.
- Text does not overflow at common desktop sizes.

If incomplete:

- Keep CLI as the reliable product surface.
- Do not add sync or team features.

## Loop 11: Project Progress Report

Goal: make the read-only workbench useful for deciding what happened without opening raw files.

Must complete:

- Add run status charts.
- Add failed and blocked reason distribution.
- Show provider, model, latency, token, and cost placeholders.
- Show command stdout and stderr artifact previews.
- Show event JSON detail.
- Add report section deep links.
- Add run search and status filtering.
- Keep the workbench read-only.

Verification:

- UI can read existing `.agent` store data.
- UI shows command output from stored artifacts.
- UI can filter runs by text and status.
- Browser smoke test captures the rendered workbench.
- No approve, resume, write, model call, login, or sync action is added.

If incomplete:

- Keep Loop 10 workbench behavior as the reliable baseline.
- Mark missing sections clearly.

## Loop 12: Diff Viewer And Approval Skeleton

Goal: prepare the workbench for controlled agent changes without enabling write actions.

Must complete:

- Add diff viewer from existing `diff.patch` or git diff artifacts.
- Add changed files panel from git and file events.
- Add risk decision panel from recorded risk metadata.
- Add disabled approval, resume, write, commit, push, and delete skeleton buttons.
- Add Approval Readiness section to reports.
- Keep all controls reserved only and non-executable.

Verification:

- Snapshot can read diff artifacts from the existing run store.
- Workbench renders changed files, risk decisions, and diff content.
- Approval buttons are disabled and have no execution handler.
- Report includes Approval Readiness.
- Browser smoke test captures the rendered workbench.

If incomplete:

- Keep Loop 11 evidence viewer as the reliable baseline.
- Do not enable approve, resume, write, commit, push, or delete.

## Loop 13: Approval Policy Contract

Goal: define the policy contract before any real approval or resume execution exists.

Must complete:

- Add `approval.py` with pure approval request, decision, contract, and resume eligibility helpers.
- Map risk levels to required approval kinds.
- Evaluate reserved actions as allowed or denied with reasons.
- Define approval event record shape.
- Keep approval, resume, write, commit, push, and delete non-executable.
- Show required approvals, eligible actions, blocked actions, missing approvals, and resume eligibility in Approval Readiness.

Verification:

- Unit tests cover risk-to-approval mapping, missing approvals, approval event shape, and resume eligibility.
- Report includes the Approval Readiness contract fields.
- Workbench snapshot and UI expose the contract fields.
- Browser smoke test captures the rendered workbench.

If incomplete:

- Keep Loop 12 disabled skeleton as the reliable baseline.
- Do not add execution adapters.

## Loop 14: Persisted Approval Ledger

Goal: make approval evidence inspectable before any approval action can execute.

Must complete:

- Define read-only `approvals.jsonl` ledger structure.
- Define request id, decision id, actor, created_at, expires_at, scope hash, decision reason, and revocation event fields.
- Add ledger status helpers for active, expired, and revoked approvals.
- Add `loopforge approval <run_id>` read-only command.
- Show approval ledger timeline in the workbench.
- Show ledger status, expired approvals, revoked approvals, and active approvals in Approval Readiness.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover request id, decision id, scope hash, active approval, expired approval, revoked approval, and ledger file reading.
- CLI approval command prints approval contract and ledger entries.
- Report includes ledger status and approval groups.
- Workbench snapshot and UI expose ledger timeline.
- Browser smoke test captures the rendered workbench.

If incomplete:

- Keep Loop 13 approval contract as the reliable baseline.
- Do not add approval write commands or execution adapters.

## Loop 15: Approval Decision Recorder

Goal: allow a human decision to be recorded without executing the reserved action.

Must complete:

- Add `loopforge approval decide <run_id> --request-id <id> --decision approve|deny --actor <name> --reason <text> --expires-at <iso>`.
- Validate request id against the current approval contract.
- Validate scope hash against the current changed files, diff, and risk scope.
- Append only approval decision or denial records to `approvals.jsonl`.
- Detect duplicate active decisions as conflicts.
- Ensure revoked or expired approvals are not counted as active.
- Keep the workbench read-only and without clickable approval buttons.
- Show active, expired, revoked, denied, and conflict approval states in reports.

Verification:

- Unit tests cover decision recording, request-id validation, duplicate conflict, denied approvals, expired approvals, and revoked approvals.
- CLI decision recorder appends ledger entries and prints that no reserved action executed.
- Workbench still only reads and displays ledger timeline.
- Browser smoke test captures the rendered workbench.

If incomplete:

- Keep Loop 14 read-only ledger as the reliable baseline.
- Do not add resume/write/commit/push/delete execution adapters.

## Loop 16: Scope Replay And Audit Signature

Goal: prove recorded approval decisions still match the current evidence before any future execution adapter can use them.

Must complete:

- Bind approval decisions to changed files, diff evidence hash, risk scope, and command scope.
- Add scope replay statuses: matched, changed, missing evidence, expired, revoked, denied, and conflict.
- Add audit signature placeholder fields: actor_signature and signature_status.
- Mark execution-ready only when an approval is active and scope replay is matched.
- Show scope evidence, replay status, signature status, and execution readiness in reports.
- Show the same replay and signature fields in `loopforge approval <run_id>`.
- Show the same replay and signature fields in the read-only workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover matched, changed, missing evidence, denied, expired, revoked, conflict, and unsigned signature states.
- CLI approval output includes scope evidence, scope replay, and execution-ready approvals.
- Report Approval Readiness includes scope replay and execution readiness.
- Workbench snapshot and browser smoke test show replay and signature sections.

If incomplete:

- Keep Loop 15 decision recording as the reliable baseline.
- Do not add execution adapters or clickable approval buttons.

## Loop 17: Immutable Evidence Manifest

Goal: make approval replay depend on a stable evidence manifest instead of only re-reading current event files.

Must complete:

- Generate `evidence_manifest.json` for each run.
- Record hashes for `events.jsonl`, `report.md`, `approvals.jsonl`, diff artifacts, command stdout/stderr artifacts, and other referenced artifacts.
- Record changed files, diff hashes, risk scope, command scope, created_at, scope parts, and scope hash.
- Make approval scope replay prefer manifest scope when the manifest exists.
- Keep older runs compatible by falling back to event-derived scope while showing `missing manifest`.
- Show manifest status, evidence hashes, and replay source in report, CLI approval output, and Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover manifest generation, hash capture, manifest-first scope replay, and missing manifest fallback.
- Run persistence creates `evidence_manifest.json`.
- CLI approval output includes manifest status and replay source.
- Workbench snapshot and browser smoke test show manifest status and hashes.

If incomplete:

- Keep Loop 16 scope replay as the reliable baseline.
- Do not add execution adapters or clickable approval buttons.

## Loop 18: Manifest Integrity And Tamper Check

Goal: detect when persisted run evidence no longer matches the evidence manifest.

Must complete:

- Verify `events.jsonl`, `report.md`, `approvals.jsonl`, diff artifacts, and command artifacts against `evidence_manifest.json`.
- Add manifest integrity states: verified, tampered, missing manifest, and invalid manifest.
- Record structured integrity issues with kind, path, expected hash, current hash, and reason.
- Make scope replay prefer manifest scope only when the manifest is not tampered.
- Show integrity status and issue count in report, CLI approval output, and Workbench.
- Keep older runs compatible by showing missing manifest instead of failing.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover verified manifests, core file tampering, artifact tampering, and tampered-scope fallback.
- CLI approval output includes integrity status.
- Workbench snapshot and browser smoke test show integrity status and issue count.

If incomplete:

- Keep Loop 17 manifest generation as the reliable baseline.
- Do not add execution adapters or clickable approval buttons.

## Loop 19: Execution Gate Readiness

Goal: centralize the future execution preflight decision before any reserved action can run.

Must complete:

- Add a pure read-only execution gate over approval contract, approval ledger replay, and evidence manifest integrity.
- Evaluate approve, resume, write, commit, push, and delete readiness.
- Gate requires verified manifest integrity, no denied/conflict/revoked/expired approvals, no missing approval for the action, and at least one active matched approval for write-like actions.
- Keep `executable_actions` empty and every button disabled.
- Show gate readiness in report, CLI approval output, and Workbench.

Verification:

- Unit tests cover ready-but-not-executable, tampered manifest blocking, denied approval blocking, and missing approval blocking.
- CLI approval output includes execution gate records.
- Workbench snapshot and browser smoke test show execution gate readiness.

If incomplete:

- Keep Loop 18 manifest integrity as the reliable baseline.
- Do not add execution adapters or clickable approval buttons.

## Loop 20: Gate Audit Event Trail

Goal: make execution gate checks durable and reviewable without executing reserved actions.

Must complete:

- Add a structured `execution.gate.evaluated` audit event.
- Add `loopforge approval gate <run_id>` for read-only gate inspection.
- Add `loopforge approval gate <run_id> --record` to append only the gate audit event.
- Show gate audit history in Approval Readiness and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover the gate audit event shape.
- CLI tests prove `approval gate --record` appends one audit event and prints the no-execution guarantee.
- Report includes Gate audit after recording.
- Workbench snapshot and browser smoke test show Gate audit.

If incomplete:

- Keep Loop 19 execution gate readiness as the reliable baseline.
- Do not add execution adapters, clickable approval buttons, or automatic action execution.

## Loop 21: Audit Digest And Event Chain

Goal: make run evidence checks replayable as a digest instead of only individual file hashes.

Must complete:

- Add an event-chain head over `events.jsonl`.
- Add an `audit_digest` over core hashes, artifact hashes, scope hash, event count, and event-chain head.
- Recompute audit status as verified, tampered, or missing audit digest.
- Keep legacy manifests readable without marking them tampered only because they lack audit fields.
- Show audit status, digest, chain head, and event count in reports and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover event-chain generation, digest recomputation, tamper detection, and legacy manifest compatibility.
- Report Approval Readiness includes audit digest fields.
- Workbench snapshot and browser smoke test show audit digest fields.

If incomplete:

- Keep Loop 20 gate audit events as the reliable baseline.
- Do not add cryptographic signatures, execution adapters, or clickable approval buttons.

## Loop 22: Actor Identity And Signature Skeleton

Goal: make approval ledger decisions identify who made the decision and what payload would be signed later.

Must complete:

- Add actor identity fields for ledger entries: actor id and actor kind.
- Add a deterministic signature payload hash for approval and revocation entries.
- Add a placeholder signature algorithm and status evaluation: unsigned, placeholder-valid, or invalid.
- Keep placeholder signatures explicitly non-cryptographic.
- Show actor id, actor kind, signature payload hash, algorithm, and status in reports and the Workbench.
- Keep execution readiness independent from signature status until a real signing policy exists.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover actor identity, payload hash, unsigned signatures, placeholder-valid signatures, and invalid signatures.
- CLI approval output includes actor and signature skeleton fields.
- Workbench snapshot and browser smoke test show actor and signature skeleton fields.

If incomplete:

- Keep Loop 21 audit digest as the reliable baseline.
- Do not add real cryptographic keys, key storage, execution adapters, or clickable approval buttons.

## Loop 23: Approval Revocation Recorder

Goal: let users revoke a recorded approval decision without executing any reserved action.

Must complete:

- Add `loopforge approval revoke <run_id> --decision-id <id> --actor <name> --reason <text>`.
- Validate that the decision id exists in the current approval ledger.
- Reject duplicate revocations as conflicts.
- Append only a revocation ledger entry with actor identity and signature payload skeleton fields.
- Refresh evidence manifest after the ledger append.
- Show revoked approvals in CLI approval output, reports, and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover revocation entry shape, successful CLI revocation, duplicate revocation rejection, and report output.
- CLI smoke records a decision, revokes it, and shows revoked state.
- Workbench snapshot shows the revoked approval group.

If incomplete:

- Keep Loop 22 actor signature skeleton as the reliable baseline.
- Do not add resume/write/commit/push/delete execution adapters.

## Loop 24: Approval Ledger Integrity View

Goal: make approval ledger state easier to inspect before any execution adapter exists.

Must complete:

- Add a ledger integrity summary with counts for active, expired, revoked, denied, conflict, and inactive entries.
- Show the latest ledger entry.
- Show revocation chains from original approval decision to revocation entry.
- Explain why each non-ready ledger entry is not execution-ready.
- Show the integrity view in reports, CLI-generated approval readiness, and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover integrity counts, latest entry, revocation chains, and not-ready reasons.
- CLI revocation flow updates the report with ledger integrity.
- Workbench snapshot and smoke checks show ledger integrity fields.

If incomplete:

- Keep Loop 23 approval revocation as the reliable baseline.
- Do not add resume/write/commit/push/delete execution adapters.

## Loop 25: Reserved Execution Adapter Contract

Goal: define the shape of future execution adapters without executing any reserved action.

Must complete:

- Add a pure execution adapter contract derived from execution gate readiness.
- Include adapter name, action, ready/blocked status, dry-run support, execute support, blockers, and executable state.
- Keep every adapter `execute_supported=false` and `executable=false`.
- Add `loopforge execution <run_id>` to show the adapter contract.
- Show the adapter contract in reports and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover ready and blocked adapter records.
- CLI tests prove the execution command only displays the contract.
- Workbench snapshot and smoke checks show the execution adapter contract.

If incomplete:

- Keep Loop 24 ledger integrity as the reliable baseline.
- Do not add adapter execution, approval buttons, resume, write, commit, push, or delete behavior.

## Loop 26: Change-set Critique

Goal: upgrade sharp review from run-event critique to change-set critique that can review the current code diff.

Must complete:

- Add change-set critique sections: Scope control, Product alignment, Verification quality, Risk review, Maintainability, and Next action.
- Read current git changed files and diff for `loopforge critique changes`.
- Accept test, risk, and smoke summaries as explicit CLI evidence.
- Add `Change-set Critique` to reports and the Workbench.
- Keep legacy `loopforge critique <run_id>` behavior working through a compatibility path.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover normal change-set critique and private-file risk detection.
- CLI tests cover `critique changes` against a temporary git diff.
- Report and Workbench tests show the new `Change-set Critique` section.

If incomplete:

- Keep Loop 25 execution adapter contract as the reliable baseline.
- Do not use change-set critique as an automatic approval, resume, or execution gate.

## Loop 27: Evidence Bundle Export

Goal: export a read-only run evidence package for audit, reviewer agent handoff, and failure replay.

Must complete:

- Add an evidence bundle exporter that copies existing run evidence into a new timestamped bundle directory.
- Include `goal.json`, `events.jsonl`, `report.md`, `evidence_manifest.json`, `approvals.jsonl`, and referenced artifact files when present.
- Generate `bundle_manifest.json` with file hashes, source integrity status, audit status, and no-execution guarantee.
- Generate a zip archive for handoff without deleting previous bundle exports.
- Add `loopforge evidence bundle <run_id>` and `loopforge evidence show <run_id>`.
- Show evidence bundle status in reports and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover bundle file copying, manifest generation, and zip contents.
- CLI tests cover bundle export and listing.
- Workbench/report tests show bundle count and latest bundle hash.

If incomplete:

- Keep Loop 26 change-set critique as the reliable baseline.
- Do not use evidence bundles as approval, resume, or execution authority.

## Loop 28: Reviewer Handoff

Goal: turn evidence bundles into read-only reviewer-agent input packages.

Must complete:

- Add `reviewer_handoff.py`.
- Add `loopforge reviewer handoff <run_id>` and `loopforge reviewer show <run_id>`.
- Generate `reviewer_input.json`, `reviewer_prompt.md`, and `reviewer_manifest.json`.
- Include run goal and status, evidence bundle path and hash, report summary, approval readiness, evidence manifest integrity, change-set critique, risk summary, and reviewer questions.
- Show reviewer handoff status in reports and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover handoff file generation and no-execution prompt text.
- CLI tests cover handoff export and listing.
- Workbench/report tests show handoff count and latest handoff hash.

If incomplete:

- Keep Loop 27 evidence bundle export as the reliable baseline.
- Do not use reviewer handoff output as approval, resume, or execution authority.

## Loop 29: Reviewer Decision Import

Goal: let reviewer output become auditable run evidence without turning it into approval or execution authority.

Must complete:

- Add `reviewer_decision.py`.
- Add `loopforge reviewer decide <run_id> --handoff-id <id> --decision approve|request-changes|block --actor <name> --reason <text>`.
- Add `loopforge reviewer decisions <run_id>`.
- Validate that the handoff id exists in the current run's reviewer handoff set.
- Append reviewer decisions to `reviewer_decisions.jsonl` only.
- Mark duplicate decisions for the same handoff as `conflict` instead of overwriting old records.
- Show reviewer decisions in reports and the Workbench.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover valid records, missing handoff rejection, and duplicate conflict records.
- CLI tests cover reviewer decision record/show flows and no-execution output.
- Workbench/report tests show reviewer decision counts, latest decision, and the new report section.

If incomplete:

- Keep Loop 28 reviewer handoff as the reliable baseline.
- Do not treat reviewer decisions as approval ledger entries or execution gates.

## Loop 30: Reviewer Status

Goal: turn reviewer decision records into an advisory status that can guide the next loop without granting execution authority.

Must complete:

- Add reviewer status evaluation for no decision, approved, requested changes, blocked, and conflict states.
- Add `loopforge reviewer status <run_id>`.
- Show reviewer status in reports and the Workbench.
- Include next-action guidance and explicit `execution_authority: false`.
- Keep approve, resume, write, commit, push, and delete non-executable.

Verification:

- Unit tests cover reviewer status mapping.
- CLI tests cover reviewer status output and no-execution text.
- Workbench/report tests show reviewer status and next-loop readiness.

If incomplete:

- Keep Loop 29 reviewer decision records as the reliable baseline.
- Do not use reviewer status as an approval ledger, execution gate, or automatic continuation trigger.
