# LoopForge Design System

LoopForge is a Chinese-first local desktop developer tool. The design should feel calm, professional, dense enough for repeated work, and transparent about what the agent did.

## Design Goals

- Make agent work visible.
- Keep high-risk actions obvious.
- Help users compare successful, failed, and blocked runs quickly.
- Preserve raw evidence: commands, diffs, logs, reports, costs, and timing.
- Support Chinese as the default language and English as a switchable language pack.

## Main Layout

The desktop app uses a three-pane workbench:

```text
Project sidebar | Run timeline / main workspace | Inspector panel
```

Default screen:

- Left: projects, run history, agents, automations, reports, settings.
- Center: selected run timeline or dashboard.
- Right: details for the selected step, including diff, command output, risk, model usage, and report sections.

The app should not start with a marketing page. It should open directly into the user's work.

## Core Screens

### 运行记录面板

Purpose: show recent runs across projects or within the selected project.

Must show:

- Goal.
- Status.
- Project.
- Start time and duration.
- Changed file count.
- Command count.
- Verification result.
- Model/cost metadata when available.

### 运行时间线

Purpose: show how one run progressed.

Must show:

- 目标.
- 上下文.
- 假设.
- 成功标准.
- 计划.
- 执行.
- 观察.
- 调整.
- 验证.
- 报告.

Each step can expand to reveal tool calls, command output, files, model usage, and risk decisions.

### 失败复盘

Purpose: help the user decide whether to retry, adjust, or roll back.

Must show:

- Failed step.
- Error summary.
- stdout/stderr.
- Changed files.
- Failed verification.
- Retry count.
- Suggested next action.

Primary actions:

- 重试失败步骤.
- 回滚补丁.
- 标记为已阻塞.
- 生成失败报告.

### 阻塞决策

Purpose: pause automation when user input or risk approval is required.

Must show:

- Why the run is blocked.
- Which decision is required.
- What will happen if approved.
- What data or files are involved.
- Resume and cancel actions.

### 多智能体协作

Purpose: show parent and child runs when multiple agents work in parallel.

Must show:

- Parent run goal.
- Generated child agents.
- Child run status.
- File scope.
- Conflict risk.
- Reviewer decision.
- Merged report preview.

## Visual Style

Use a quiet developer-tool style:

- Background: `#F6F8FB`
- Surface: `#FFFFFF`
- Text: `#0F172A`
- Secondary text: `#475569`
- Muted text: `#64748B`
- Border: `#DDE3EA`
- Primary action: `#111827`
- Info: `#2563EB`
- Success: `#16A34A`
- Warning: `#D97706`
- Danger: `#DC2626`

Avoid:

- Decorative gradients.
- Marketing hero sections.
- Large empty cards.
- Overly rounded UI.
- Purple-dominant palettes.
- Chart decoration without a decision purpose.

## Typography

Chinese UI:

- Font: `Noto Sans SC`
- Letter spacing: `0`
- Heading line height: `1.3-1.4`
- Body line height: `1.6-1.8`

English and technical text:

- UI English: `Inter`
- Code, command, and paths: `Consolas` or another monospace font.

Do not use negative letter spacing for Chinese text.

## Status System

Run statuses:

- `完成`: green.
- `失败`: red.
- `已阻塞`: amber.
- `运行中`: blue.
- `已取消`: slate.

Every status color must also have text and icon support. Do not rely on color alone.

## Chart Principles

Charts are for operational insight. Each chart must answer a product question.

Good chart questions:

- Which runs failed most often?
- Which projects consume the most model cost?
- Which verification checks are unstable?
- Which agent roles create the most conflicts?
- Is automation getting more reliable over time?

Avoid charts that only show vanity totals.

## Required Charts

### Run Status Distribution

Question: are recent runs mostly completing, failing, or blocking?

Type: stacked bar or segmented horizontal bar.

Data:

- `done`
- `failed`
- `blocked`
- `cancelled`
- `running`

Use in:

- Project dashboard.
- Reports overview.

### Failure Cause Breakdown

Question: why are runs failing?

Type: horizontal bar chart.

Data categories:

- Test failure.
- Shell command failure.
- Merge conflict.
- Missing provider config.
- Policy/risk block.
- Model/tool error.

Use in:

- Failure review.
- Project progress report.

### Verification Trend

Question: is project verification getting healthier over time?

Type: line chart.

Data:

- Date.
- Passed checks.
- Failed checks.
- Blocked checks.

Use in:

- Project dashboard.
- Weekly report.

### Cost And Token Usage

Question: which runs cost the most?

Type: bar chart with table fallback.

Data:

- Run ID.
- Provider.
- Model.
- Input tokens.
- Output tokens.
- Estimated cost.
- Duration.

Use in:

- Settings.
- Reports.
- Run details.

### Duration Timeline

Question: which runs are slow and where is time spent?

Type: timeline or stacked bar.

Data:

- Context time.
- Model time.
- Tool time.
- Verification time.
- Waiting/blocked time.

Use in:

- Run detail.
- Automation tuning.

### Multi-Agent Conflict Map

Question: which child agents touched the same files?

Type: matrix or file-agent table.

Data:

- Child run ID.
- Agent role.
- File path.
- Action type.
- Conflict status.
- Reviewer decision.

Use in:

- Multi-agent coordination.

## Chart Interaction

Charts should support:

- Click a segment to filter run list.
- Hover to show exact values.
- Open related runs from chart rows.
- Toggle time ranges: 24h, 7d, 30d, all.
- Export chart data in reports as tables.

Every chart must have a table fallback for precise inspection.

## Component Rules

### Buttons

- Primary actions use dark fill.
- Dangerous actions use red only when the action is destructive.
- Buttons should include icons when the icon clarifies the action.

### Cards

Use cards for repeated items and focused panels only:

- Run item.
- Project item.
- Agent child run.
- Failure evidence panel.
- Settings section.

Do not nest cards inside cards.

### Tables

Tables are preferred for:

- Files changed.
- Command history.
- Provider usage.
- Risk decisions.
- Privacy exclusions.

Dense rows are acceptable because this is a developer tool.

### Diff Viewer

The diff viewer should show:

- File path.
- Added and removed lines.
- Risk label.
- Related agent or tool call.

Large diffs should be collapsible.

### Command Output

Command output should show:

- Command.
- Exit code.
- Duration.
- Working directory.
- stdout.
- stderr.

Long output should be searchable and collapsible.

## Empty States

Empty states should be direct:

- No project: prompt to add local project.
- No runs: prompt to start a run.
- No provider: prompt to configure provider or continue deterministic mode.
- No report: prompt to generate report from run history.

Do not use decorative illustrations for empty states.

## Privacy UI

Privacy and risk decisions must be visible:

- Show excluded paths.
- Show secret detection results.
- Show what context is sent to a provider.
- Show when sync is off.
- Show when a high-risk action is waiting.

Default sync state: off.

## OpenPencil Pages

Current design pages should map to implementation like this:

- `中文主界面 / Language Toggle`: default workbench.
- `Failed Run State`: failure review.
- `Blocked Run State`: blocked decision.
- `Multi-Agent Run State`: multi-agent coordination.
- `语言规范 / i18n`: localization rules.
