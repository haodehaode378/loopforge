"""Read-only local workbench web UI."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ai_agent_loop.project import ProjectRegistry
from ai_agent_loop.store import (
    find_blocked_reason,
    ensure_summary_headings,
    infer_status,
    render_approval_readiness,
    render_automation_summary,
    render_git_summary,
    render_multi_agent_summary,
    replace_approval_readiness,
    replace_automation_summary,
    replace_git_summary,
    replace_multi_agent_summary,
    replace_sharp_review,
    replace_status_line,
)
from ai_agent_loop.critique import render_critique


def build_workbench_snapshot(root: Path | str = ".agent") -> dict[str, object]:
    store_root = Path(root)
    registry = ProjectRegistry(store_root)
    projects = []
    totals = {
        "projects": 0,
        "runs": 0,
        "blocked": 0,
        "failed": 0,
        "done": 0,
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }
    for project in registry.list_projects():
        project_dir = registry.project_dir(project)
        runs = read_project_runs(project_dir)
        totals["runs"] += len(runs)
        for run in runs:
            status = str(run.get("effective_status", "unknown"))
            if status in totals:
                totals[status] += 1
            provider = run.get("provider", {})
            if isinstance(provider, dict):
                totals["latency_ms"] += int(provider.get("latency_ms") or 0)
                totals["input_tokens"] += int(provider.get("input_tokens") or 0)
                totals["output_tokens"] += int(provider.get("output_tokens") or 0)
                totals["cost_usd"] += float(provider.get("cost_usd") or 0.0)
        projects.append(
            {
                "id": project.id,
                "name": project.name,
                "path": project.path,
                "runs": runs,
                "analytics": build_project_analytics(runs),
            }
        )
    totals["projects"] = len(projects)
    return {"totals": totals, "projects": projects}


def read_project_runs(project_dir: Path) -> list[dict[str, object]]:
    runs_dir = project_dir / "runs"
    if not runs_dir.exists():
        return []
    runs = []
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            runs.append(read_run(run_dir))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return runs


def read_run(run_dir: Path) -> dict[str, object]:
    goal_record = json.loads((run_dir / "goal.json").read_text(encoding="utf-8"))
    events = read_events(run_dir / "events.jsonl")
    events = enrich_events_with_artifacts(events, run_dir)
    report = read_dynamic_report(run_dir / "report.md", events)
    metadata = goal_record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    provider = extract_provider_metrics(metadata)
    changed_files = collect_changed_files(events)
    risk_decisions = collect_risk_decisions(events)
    diff = read_diff_preview(run_dir, events)
    return {
        "run_id": run_dir.name,
        "goal": goal_record.get("description", ""),
        "status": goal_record.get("status", infer_status(events)),
        "effective_status": infer_status(events),
        "blocked_reason": find_blocked_reason(events),
        "event_count": len(events),
        "metadata": metadata,
        "provider": provider,
        "command_outputs": collect_command_outputs(events),
        "changed_files": changed_files,
        "risk_decisions": risk_decisions,
        "diff": diff,
        "approval": build_approval_readiness(changed_files, risk_decisions, diff),
        "parent_run_id": metadata.get("parent_run_id", ""),
        "child_run_ids": metadata.get("child_run_ids", []),
        "reviewer_run_id": metadata.get("reviewer_run_id", ""),
        "events": events,
        "report": report,
        "sections": extract_sections(report),
    }


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def enrich_events_with_artifacts(
    events: list[dict[str, object]],
    run_dir: Path,
) -> list[dict[str, object]]:
    enriched = []
    for event in events:
        event_copy = dict(event)
        artifacts = event.get("artifacts", {})
        previews = {}
        if isinstance(artifacts, dict):
            for name, artifact_path in artifacts.items():
                previews[str(name)] = read_artifact_preview(artifact_path, run_dir)
        event_copy["artifact_previews"] = previews
        enriched.append(event_copy)
    return enriched


def read_artifact_preview(path_value: object, run_dir: Path, limit: int = 4000) -> dict[str, object]:
    path = Path(str(path_value))
    preview = {"path": str(path), "content": "", "truncated": False, "missing": True}
    try:
        resolved_path = path.resolve()
        resolved_run_dir = run_dir.resolve()
        if not resolved_path.is_relative_to(resolved_run_dir):
            preview["content"] = "Artifact path is outside this run directory."
            return preview
        if not resolved_path.exists() or not resolved_path.is_file():
            return preview
        content = resolved_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return preview
    preview["missing"] = False
    preview["truncated"] = len(content) > limit
    preview["content"] = content[:limit]
    return preview


def collect_command_outputs(events: list[dict[str, object]]) -> list[dict[str, object]]:
    commands = []
    for event in events:
        if event.get("name") != "shell.run":
            continue
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        previews = event.get("artifact_previews", {})
        commands.append(
            {
                "command": metadata.get("command", ""),
                "exit_code": metadata.get("exit_code"),
                "status": event.get("status", ""),
                "stdout": previews.get("stdout", {}),
                "stderr": previews.get("stderr", {}),
            }
        )
    return commands


def collect_changed_files(events: list[dict[str, object]]) -> list[str]:
    files: list[str] = []
    for event in events:
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        changed = metadata.get("changed_files", [])
        if isinstance(changed, list):
            files.extend(str(item) for item in changed)
        if event.get("name") == "file.write":
            path = metadata.get("relative_path") or metadata.get("path")
            if path:
                files.append(str(path))
    return sorted(set(files))


def collect_risk_decisions(events: list[dict[str, object]]) -> list[dict[str, object]]:
    decisions = []
    for event in events:
        risk = event.get("risk", {})
        if not risk and event.get("status") != "blocked":
            continue
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        if not isinstance(risk, dict):
            risk = {}
        decisions.append(
            {
                "name": event.get("name", ""),
                "status": event.get("status", ""),
                "level": risk.get("level", "unknown"),
                "reason": risk.get("reason", event.get("detail", "")),
                "detail": event.get("detail", ""),
                "command": metadata.get("command", ""),
            }
        )
    return decisions


def read_diff_preview(run_dir: Path, events: list[dict[str, object]], limit: int = 12000) -> dict[str, object]:
    candidates = [run_dir / "diff.patch", run_dir / "git" / "diff.patch"]
    for event in events:
        artifacts = event.get("artifacts", {})
        if isinstance(artifacts, dict) and artifacts.get("diff"):
            candidates.append(Path(str(artifacts["diff"])))
    for candidate in candidates:
        preview = read_artifact_preview(candidate, run_dir, limit=limit)
        if not preview.get("missing"):
            return preview
    return {"path": "", "content": "", "truncated": False, "missing": True}


def build_approval_readiness(
    changed_files: list[str],
    risk_decisions: list[dict[str, object]],
    diff: dict[str, object],
) -> dict[str, object]:
    return {
        "mode": "read-only approval skeleton",
        "status": "reserved",
        "executable_actions": [],
        "reserved_actions": ["approve", "resume", "write", "commit", "push", "delete"],
        "changed_file_count": len(changed_files),
        "risk_decision_count": len(risk_decisions),
        "has_diff": not bool(diff.get("missing", True)),
        "ready_for_review": bool(changed_files or risk_decisions or not diff.get("missing", True)),
    }


def extract_provider_metrics(metadata: dict[str, object]) -> dict[str, object]:
    return {
        "provider": metadata.get("provider") or "unknown",
        "provider_kind": metadata.get("provider_kind") or "unknown",
        "model": metadata.get("model") or "unknown",
        "latency_ms": int(metadata.get("latency_ms") or 0),
        "input_tokens": int(metadata.get("input_tokens") or 0),
        "output_tokens": int(metadata.get("output_tokens") or 0),
        "cost_usd": float(metadata.get("cost_usd") or 0.0),
    }


def build_project_analytics(runs: list[dict[str, object]]) -> dict[str, object]:
    statuses = {"done": 0, "failed": 0, "blocked": 0, "unknown": 0}
    reasons: dict[str, int] = {}
    providers: dict[str, int] = {}
    totals = {"latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    command_count = 0
    for run in runs:
        status = str(run.get("effective_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        if status in {"failed", "blocked"}:
            reason = failure_or_blocked_reason(run)
            reasons[reason] = reasons.get(reason, 0) + 1
        provider = run.get("provider", {})
        if isinstance(provider, dict):
            provider_name = str(provider.get("provider") or "unknown")
            providers[provider_name] = providers.get(provider_name, 0) + 1
            totals["latency_ms"] += int(provider.get("latency_ms") or 0)
            totals["input_tokens"] += int(provider.get("input_tokens") or 0)
            totals["output_tokens"] += int(provider.get("output_tokens") or 0)
            totals["cost_usd"] += float(provider.get("cost_usd") or 0.0)
        command_outputs = run.get("command_outputs", [])
        if isinstance(command_outputs, list):
            command_count += len(command_outputs)
    return {
        "status_counts": statuses,
        "reason_counts": reasons,
        "provider_counts": providers,
        "provider_totals": totals,
        "command_count": command_count,
    }


def failure_or_blocked_reason(run: dict[str, object]) -> str:
    blocked_reason = str(run.get("blocked_reason") or "").strip()
    if blocked_reason:
        return blocked_reason
    events = run.get("events", [])
    if isinstance(events, list):
        for event in reversed(events):
            if event.get("status") in {"failed", "blocked"}:
                return str(event.get("detail") or event.get("name") or "unknown")
    return "unknown"


def read_dynamic_report(path: Path, events: list[dict[str, object]]) -> str:
    if not path.exists():
        return ""
    report = path.read_text(encoding="utf-8")
    report = ensure_summary_headings(report)
    report = replace_status_line(report, infer_status(events))
    report = replace_automation_summary(report, render_automation_summary(events))
    report = replace_git_summary(report, render_git_summary(events))
    report = replace_multi_agent_summary(report, render_multi_agent_summary(events))
    report = replace_approval_readiness(report, render_approval_readiness(events))
    report = replace_sharp_review(report, render_critique(events))
    blocked_reason = find_blocked_reason(events)
    if blocked_reason and "## Blocked Reason" not in report:
        report += f"\n## Blocked Reason\n\n{blocked_reason}\n"
    return report


def extract_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "Overview"
    sections[current] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def render_workbench_html(snapshot: dict[str, object]) -> str:
    data = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LoopForge Workbench</title>
  <style>{CSS}</style>
</head>
<body>
  <div id="app"></div>
  <script id="snapshot" type="application/json">{data}</script>
  <script>{JS}</script>
</body>
</html>
"""


def serve_workbench(root: str = ".agent", host: str = "127.0.0.1", port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/snapshot.json":
                self.respond_json(build_workbench_snapshot(root))
                return
            if parsed.path in {"/", "/index.html"}:
                self.respond_html(render_workbench_html(build_workbench_snapshot(root)))
                return
            self.send_error(404)

        def respond_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def respond_json(self, data: dict[str, object]) -> None:
            payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"LoopForge workbench: http://{host}:{server.server_port}")
    server.serve_forever()


CSS = r"""
:root {
  color-scheme: light;
  --bg: #f6f7f4;
  --panel: #ffffff;
  --line: #d9ded6;
  --text: #1e2521;
  --muted: #647067;
  --accent: #2f6f5e;
  --warn: #a86b19;
  --danger: #a73535;
  --ok: #2f7a42;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
}
button, select, input { font: inherit; }
.shell {
  height: 100dvh;
  display: grid;
  grid-template-columns: 280px minmax(360px, 1fr) minmax(420px, 1.05fr);
  grid-template-rows: 56px 1fr;
}
.topbar {
  grid-column: 1 / -1;
  border-bottom: 1px solid var(--line);
  background: #fbfcfa;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
}
.brand { font-weight: 700; letter-spacing: 0; }
.metrics { display: flex; gap: 10px; color: var(--muted); font-size: 13px; }
.metric { border: 1px solid var(--line); padding: 5px 8px; background: #fff; border-radius: 6px; }
.pane { min-width: 0; overflow: auto; border-right: 1px solid var(--line); }
.sidebar { background: #fbfcfa; padding: 14px; }
.main { background: #f9faf7; padding: 14px; }
.detail { background: #fff; padding: 14px; border-right: 0; }
.section-title { color: var(--muted); font-size: 12px; margin: 12px 0 8px; text-transform: uppercase; }
.project, .run {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  padding: 9px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text);
}
.project:hover, .run:hover, .project.active, .run.active { background: #eef2ec; border-color: var(--line); }
.project-name, .run-goal { font-weight: 650; overflow-wrap: anywhere; }
.path, .run-meta { color: var(--muted); font-size: 12px; margin-top: 4px; overflow-wrap: anywhere; }
.toolbar { display: grid; grid-template-columns: 1fr 140px; gap: 8px; align-items: center; margin-bottom: 12px; }
.search { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 9px; background: #fff; }
.filter { border: 1px solid var(--line); border-radius: 6px; padding: 9px; background: #fff; color: var(--text); }
.status {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 12px;
  border: 1px solid var(--line);
  margin-right: 6px;
}
.status.done { color: var(--ok); background: #edf7ef; }
.status.failed { color: var(--danger); background: #fbefef; }
.status.blocked { color: var(--warn); background: #fff5e4; }
.timeline { display: grid; gap: 8px; }
.event {
  border-left: 3px solid var(--line);
  background: var(--panel);
  padding: 9px 10px;
  border-radius: 0 6px 6px 0;
  cursor: pointer;
}
.event.done { border-left-color: var(--ok); }
.event.failed { border-left-color: var(--danger); }
.event.blocked { border-left-color: var(--warn); }
.event-name { font-weight: 650; }
.event-detail { color: var(--muted); font-size: 13px; margin-top: 4px; overflow-wrap: anywhere; }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.tab {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--text);
  border-radius: 6px;
  padding: 6px 9px;
  cursor: pointer;
}
.tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.report {
  white-space: pre-wrap;
  background: #fbfcfa;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  line-height: 1.5;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.chart-panel, .evidence, .provider-grid {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  padding: 10px;
  margin-bottom: 12px;
}
.approval-panel {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  padding: 10px;
  margin: 12px 0;
}
.approval-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.disabled-action {
  border: 1px solid var(--line);
  background: #eef0eb;
  color: var(--muted);
  border-radius: 6px;
  padding: 6px 9px;
  cursor: not-allowed;
}
.file-list, .risk-list { display: grid; gap: 6px; margin: 8px 0; }
.file-item, .risk-item {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 7px 8px;
  background: #fbfcfa;
  overflow-wrap: anywhere;
  font-size: 12px;
}
.diff-viewer { max-height: 280px; overflow: auto; }
.diff-line { display: block; white-space: pre; font-family: "Cascadia Mono", Consolas, monospace; font-size: 12px; }
.diff-line.add { color: var(--ok); background: #edf7ef; }
.diff-line.del { color: var(--danger); background: #fbefef; }
.diff-line.meta { color: var(--accent); background: #eef2ec; }
.chart-row {
  display: grid;
  grid-template-columns: 92px 1fr 34px;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  margin: 7px 0;
}
.bar-track { height: 8px; background: #edf0ea; border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 999px; }
.bar-fill.failed { background: var(--danger); }
.bar-fill.blocked { background: var(--warn); }
.bar-fill.done { background: var(--ok); }
.provider-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.provider-card { border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #fbfcfa; min-width: 0; }
.provider-label { color: var(--muted); font-size: 11px; text-transform: uppercase; }
.provider-value { font-weight: 650; overflow-wrap: anywhere; margin-top: 4px; }
.evidence-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
.code {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 12px;
  background: #f6f7f4;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px;
  max-height: 220px;
  overflow: auto;
}
.deep-link { color: var(--muted); font-size: 12px; margin-top: 5px; overflow-wrap: anywhere; }
.tree { border: 1px solid var(--line); border-radius: 6px; padding: 10px; background: #fbfcfa; margin-bottom: 10px; }
.tree-row { padding: 5px 0; font-size: 13px; }
.empty { color: var(--muted); padding: 24px; text-align: center; border: 1px dashed var(--line); border-radius: 6px; }
@media (max-width: 1100px) {
  .shell { grid-template-columns: 240px 1fr; grid-template-rows: 56px minmax(360px, 1fr) minmax(360px, 1fr); }
  .detail { grid-column: 1 / -1; border-top: 1px solid var(--line); }
}
"""


JS = r"""
const snapshot = JSON.parse(document.getElementById('snapshot').textContent);
const labels = {
  zh: {
    projects: '项目', runs: '运行历史', timeline: '事件时间线', detail: '运行详情',
    search: '搜索目标、状态、run id', report: '报告', multi: '多 Agent 树', empty: '暂无数据',
    language: 'English', status: '状态', events: '事件', path: '路径', charts: '图表',
    reasons: '失败 / Blocked 原因', provider: 'Provider 指标', commands: '命令输出',
    eventJson: '事件 JSON', all: '全部状态', sectionLink: 'section 深链',
    approval: '审批骨架', changedFiles: '变更文件', riskDecision: '风险决策',
    diffViewer: 'Diff 查看器', reservedOnly: '仅预留，不执行', noExecutable: '无可执行动作'
  },
  en: {
    projects: 'Projects', runs: 'Run history', timeline: 'Event timeline', detail: 'Run detail',
    search: 'Search goal, status, run id', report: 'Report', multi: 'Multi-agent tree', empty: 'No data',
    language: '中文', status: 'Status', events: 'Events', path: 'Path', charts: 'Charts',
    reasons: 'Failed / blocked reasons', provider: 'Provider metrics', commands: 'Command output',
    eventJson: 'Event JSON', all: 'All statuses', sectionLink: 'Section deep link',
    approval: 'Approval skeleton', changedFiles: 'Changed files', riskDecision: 'Risk decision',
    diffViewer: 'Diff viewer', reservedOnly: 'Reserved only, no execution', noExecutable: 'No executable actions'
  }
};
let state = { lang: 'zh', project: 0, run: 0, section: 'Overview', query: '', status: 'all', event: 0 };
hydrateFromHash();

function t(key) { return labels[state.lang][key] || key; }
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function project() { return snapshot.projects[state.project] || {runs: [], analytics: {}}; }
function runs() {
  const q = state.query.toLowerCase();
  return (project().runs || []).filter(run => {
    const text = `${run.goal} ${run.effective_status} ${run.run_id}`.toLowerCase();
    const statusMatch = state.status === 'all' || run.effective_status === state.status;
    return statusMatch && (!q || text.includes(q));
  });
}
function selectedRun() { return runs()[state.run] || runs()[0] || null; }

function render() {
  const run = selectedRun();
  const totals = snapshot.totals || {};
  document.getElementById('app').innerHTML = `
    <div class="shell">
      <header class="topbar">
        <div class="brand">LoopForge Workbench</div>
        <div class="metrics">
          <span class="metric">${t('projects')}: ${totals.projects || 0}</span>
          <span class="metric">${t('runs')}: ${totals.runs || 0}</span>
          <span class="metric">blocked: ${totals.blocked || 0}</span>
          <span class="metric">$${Number(totals.cost_usd || 0).toFixed(4)}</span>
          <button class="tab" onclick="toggleLang()">${t('language')}</button>
        </div>
      </header>
      <aside class="pane sidebar">${renderProjects()}</aside>
      <main class="pane main">${renderRuns(run)}</main>
      <section class="pane detail">${renderDetail(run)}</section>
    </div>`;
}
function renderProjects() {
  if (!snapshot.projects.length) return `<div class="empty">${t('empty')}</div>`;
  return `<div class="section-title">${t('projects')}</div>` + snapshot.projects.map((p, index) => `
    <button class="project ${index === state.project ? 'active' : ''}" onclick="selectProject(${index})">
      <div class="project-name">${esc(p.name)}</div>
      <div class="path">${esc(p.path)}</div>
      <div class="run-meta">${(p.runs || []).length} runs</div>
    </button>`).join('');
}
function renderRuns(current) {
  const list = runs();
  return `
    ${renderCharts(project().analytics || {})}
    <div class="toolbar">
      <input class="search" placeholder="${t('search')}" value="${esc(state.query)}" oninput="setQuery(this.value)">
      <select class="filter" onchange="setStatus(this.value)">
        ${['all', 'done', 'failed', 'blocked', 'unknown'].map(value =>
          `<option value="${value}" ${state.status === value ? 'selected' : ''}>${value === 'all' ? t('all') : value}</option>`
        ).join('')}
      </select>
    </div>
    <div class="section-title">${t('runs')}</div>
    ${list.length ? list.map((run, index) => `
      <button class="run ${run === current ? 'active' : ''}" onclick="selectRun(${index})">
        <div><span class="status ${esc(run.effective_status)}">${esc(run.effective_status)}</span>${esc(run.run_id)}</div>
        <div class="run-goal">${esc(run.goal)}</div>
        <div class="run-meta">${run.event_count} ${t('events')} · ${esc((run.provider || {}).provider)} / ${esc((run.provider || {}).model)}</div>
      </button>`).join('') : `<div class="empty">${t('empty')}</div>`}
    <div class="section-title">${t('timeline')}</div>
    ${current ? renderTimeline(current) : ''}`;
}
function renderCharts(analytics) {
  return `<div class="chart-panel">
    <div class="section-title">${t('charts')}</div>
    ${renderBarChart(analytics.status_counts || {}, ['done', 'failed', 'blocked', 'unknown'])}
    <div class="section-title">${t('reasons')}</div>
    ${renderReasonChart(analytics.reason_counts || {})}
  </div>`;
}
function renderBarChart(counts, order) {
  const max = Math.max(1, ...Object.values(counts).map(Number));
  return order.map(name => chartRow(name, counts[name] || 0, max, name)).join('');
}
function renderReasonChart(counts) {
  const entries = Object.entries(counts);
  if (!entries.length) return `<div class="run-meta">${t('empty')}</div>`;
  const max = Math.max(1, ...entries.map(([, count]) => Number(count)));
  return entries.map(([name, count]) => chartRow(name, count, max, 'blocked')).join('');
}
function chartRow(name, count, max, tone) {
  const width = Math.round((Number(count) / max) * 100);
  return `<div class="chart-row">
    <div>${esc(name)}</div><div class="bar-track"><div class="bar-fill ${esc(tone)}" style="width:${width}%"></div></div><div>${esc(count)}</div>
  </div>`;
}
function renderTimeline(run) {
  return `<div class="timeline">${(run.events || []).map((event, index) => `
    <div class="event ${esc(event.status)}" onclick="selectEvent(${index})">
      <div class="event-name">${esc(event.name)} <span class="status ${esc(event.status)}">${esc(event.status)}</span></div>
      <div class="event-detail">${esc(event.detail || '')}</div>
    </div>`).join('')}</div>`;
}
function renderDetail(run) {
  if (!run) return `<div class="empty">${t('empty')}</div>`;
  const sections = run.sections || {};
  if (!sections[state.section]) state.section = sections['Multi-Agent Summary'] ? 'Multi-Agent Summary' : Object.keys(sections)[0] || 'Overview';
  syncHash(run);
  return `
    <div class="section-title">${t('detail')}</div>
    <h2>${esc(run.goal)}</h2>
    <div><span class="status ${esc(run.effective_status)}">${esc(run.effective_status)}</span>${esc(run.run_id)}</div>
    ${renderProvider(run.provider || {})}
    ${renderApproval(run)}
    ${renderTree(run)}
    <div class="tabs">${Object.keys(sections).map(name => `
      <button class="tab ${name === state.section ? 'active' : ''}" onclick="selectSection('${escAttr(name)}')">${esc(tabName(name))}</button>`).join('')}</div>
    <div class="deep-link">${t('sectionLink')}: #run=${esc(run.run_id)}&section=${esc(encodeURIComponent(state.section))}</div>
    <div class="report">${esc(sections[state.section] || run.report || '')}</div>
    ${renderEvidence(run)}`;
}
function renderProvider(provider) {
  return `<div class="section-title">${t('provider')}</div>
  <div class="provider-grid">
      ${providerCard('provider', provider.provider)}
      ${providerCard('model', provider.model)}
      ${providerCard('latency_ms', provider.latency_ms)}
      ${providerCard('tokens/cost', `${Number(provider.input_tokens || 0) + Number(provider.output_tokens || 0)} / $${Number(provider.cost_usd || 0).toFixed(4)}`)}
    </div>`;
}
function providerCard(label, value) {
  return `<div class="provider-card"><div class="provider-label">${esc(label)}</div><div class="provider-value">${esc(value)}</div></div>`;
}
function renderApproval(run) {
  const approval = run.approval || {};
  const actions = approval.reserved_actions || ['approve', 'resume', 'write', 'commit', 'push', 'delete'];
  return `<div class="approval-panel">
    <div class="section-title">${t('approval')}</div>
    <div class="run-meta">${esc(approval.mode || 'read-only approval skeleton')} · ${t('reservedOnly')} · ${t('noExecutable')}</div>
    <div class="approval-actions">${actions.map(action => `<button class="disabled-action" disabled>${esc(action)} reserved</button>`).join('')}</div>
    <div class="section-title">${t('changedFiles')}</div>
    ${renderChangedFiles(run.changed_files || [])}
    <div class="section-title">${t('riskDecision')}</div>
    ${renderRiskDecisions(run.risk_decisions || [])}
    <div class="section-title">${t('diffViewer')}</div>
    ${renderDiff(run.diff || {})}
  </div>`;
}
function renderChangedFiles(files) {
  if (!files.length) return `<div class="run-meta">${t('empty')}</div>`;
  return `<div class="file-list">${files.map(file => `<div class="file-item">${esc(file)}</div>`).join('')}</div>`;
}
function renderRiskDecisions(decisions) {
  if (!decisions.length) return `<div class="run-meta">${t('empty')}</div>`;
  return `<div class="risk-list">${decisions.map(decision => `
    <div class="risk-item">
      <span class="status ${esc(decision.status)}">${esc(decision.status)}</span>
      ${esc(decision.name)} · ${esc(decision.level)} · ${esc(decision.reason)}
    </div>`).join('')}</div>`;
}
function renderDiff(diff) {
  if (diff.missing || !diff.content) return `<div class="run-meta">${t('empty')}</div>`;
  return `<div class="code diff-viewer">${String(diff.content).split('\n').map(renderDiffLine).join('')}</div>`;
}
function renderDiffLine(line) {
  let tone = '';
  if (line.startsWith('+') && !line.startsWith('+++')) tone = 'add';
  if (line.startsWith('-') && !line.startsWith('---')) tone = 'del';
  if (line.startsWith('diff ') || line.startsWith('@@') || line.startsWith('+++') || line.startsWith('---')) tone = 'meta';
  return `<span class="diff-line ${tone}">${esc(line || ' ')}</span>`;
}
function renderEvidence(run) {
  const event = (run.events || [])[state.event] || (run.events || [])[0] || {};
  return `<div class="evidence">
    <div class="section-title">${t('commands')}</div>
    ${renderCommandOutputs(run.command_outputs || [])}
    <div class="section-title">${t('eventJson')}</div>
    <div class="code">${esc(JSON.stringify(event, null, 2))}</div>
  </div>`;
}
function renderCommandOutputs(commands) {
  if (!commands.length) return `<div class="run-meta">${t('empty')}</div>`;
  return commands.map(command => `
    <details open>
      <summary>${esc(command.command)} -> exit ${esc(command.exit_code)}</summary>
      <div class="evidence-grid">
        <div><div class="run-meta">stdout</div><div class="code">${esc((command.stdout || {}).content || '')}</div></div>
        <div><div class="run-meta">stderr</div><div class="code">${esc((command.stderr || {}).content || '')}</div></div>
      </div>
    </details>`).join('');
}
function renderTree(run) {
  const children = Array.isArray(run.child_run_ids) ? run.child_run_ids : [];
  if (!children.length && !run.parent_run_id) return '';
  return `<div class="tree">
    <div class="section-title">${t('multi')}</div>
    ${run.parent_run_id ? `<div class="tree-row">parent: ${esc(run.parent_run_id)}</div>` : ''}
    ${children.map(id => `<div class="tree-row">child: ${esc(id)}</div>`).join('')}
    ${run.reviewer_run_id ? `<div class="tree-row">reviewer: ${esc(run.reviewer_run_id)}</div>` : ''}
  </div>`;
}
function tabName(name) {
  const map = {
    'Automation Summary': 'Automation',
    'Git Summary': 'Git',
    'Multi-Agent Summary': 'Multi-Agent',
    'Sharp Review': 'Critique'
  };
  return map[name] || name;
}
function escAttr(value) { return String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'"); }
function selectProject(index) { state.project = index; state.run = 0; state.event = 0; state.section = 'Overview'; render(); }
function selectRun(index) { state.run = index; state.event = 0; state.section = 'Overview'; render(); }
function selectSection(name) { state.section = name; render(); }
function selectEvent(index) { state.event = index; render(); }
function setQuery(value) { state.query = value; state.run = 0; state.event = 0; render(); }
function setStatus(value) { state.status = value; state.run = 0; state.event = 0; render(); }
function toggleLang() { state.lang = state.lang === 'zh' ? 'en' : 'zh'; render(); }
function hydrateFromHash() {
  const params = new URLSearchParams(location.hash.replace(/^#/, ''));
  const runId = params.get('run');
  const section = params.get('section');
  if (runId) {
    snapshot.projects.some((project, projectIndex) => {
      const runIndex = (project.runs || []).findIndex(run => run.run_id === runId);
      if (runIndex < 0) return false;
      state.project = projectIndex;
      state.run = runIndex;
      return true;
    });
  }
  if (section) state.section = section;
}
function syncHash(run) {
  const hash = `run=${encodeURIComponent(run.run_id)}&section=${encodeURIComponent(state.section)}`;
  if (location.hash.replace(/^#/, '') !== hash) history.replaceState(null, '', `#${hash}`);
}
render();
"""
