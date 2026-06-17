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
    render_automation_summary,
    render_git_summary,
    render_multi_agent_summary,
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
    totals = {"projects": 0, "runs": 0, "blocked": 0, "failed": 0, "done": 0}
    for project in registry.list_projects():
        project_dir = registry.project_dir(project)
        runs = read_project_runs(project_dir)
        totals["runs"] += len(runs)
        for run in runs:
            status = str(run.get("effective_status", "unknown"))
            if status in totals:
                totals[status] += 1
        projects.append(
            {
                "id": project.id,
                "name": project.name,
                "path": project.path,
                "runs": runs,
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
    report = read_dynamic_report(run_dir / "report.md", events)
    metadata = goal_record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "run_id": run_dir.name,
        "goal": goal_record.get("description", ""),
        "status": goal_record.get("status", infer_status(events)),
        "effective_status": infer_status(events),
        "blocked_reason": find_blocked_reason(events),
        "event_count": len(events),
        "metadata": metadata,
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


def read_dynamic_report(path: Path, events: list[dict[str, object]]) -> str:
    if not path.exists():
        return ""
    report = path.read_text(encoding="utf-8")
    report = ensure_summary_headings(report)
    report = replace_status_line(report, infer_status(events))
    report = replace_automation_summary(report, render_automation_summary(events))
    report = replace_git_summary(report, render_git_summary(events))
    report = replace_multi_agent_summary(report, render_multi_agent_summary(events))
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
button, select { font: inherit; }
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
.toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.search { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 9px; background: #fff; }
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
    search: '搜索目标或状态', report: '报告', multi: '多 Agent 树', empty: '暂无数据',
    language: 'English', status: '状态', events: '事件', path: '路径'
  },
  en: {
    projects: 'Projects', runs: 'Run history', timeline: 'Event timeline', detail: 'Run detail',
    search: 'Search goal or status', report: 'Report', multi: 'Multi-agent tree', empty: 'No data',
    language: '中文', status: 'Status', events: 'Events', path: 'Path'
  }
};
let state = { lang: 'zh', project: 0, run: 0, section: 'Overview', query: '' };

function t(key) { return labels[state.lang][key] || key; }
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function project() { return snapshot.projects[state.project] || {runs: []}; }
function runs() {
  const q = state.query.toLowerCase();
  return (project().runs || []).filter(run =>
    !q || `${run.goal} ${run.effective_status} ${run.run_id}`.toLowerCase().includes(q)
  );
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
    <div class="toolbar"><input class="search" placeholder="${t('search')}" value="${esc(state.query)}" oninput="setQuery(this.value)"></div>
    <div class="section-title">${t('runs')}</div>
    ${list.length ? list.map((run, index) => `
      <button class="run ${run === current ? 'active' : ''}" onclick="selectRun(${index})">
        <div><span class="status ${esc(run.effective_status)}">${esc(run.effective_status)}</span>${esc(run.run_id)}</div>
        <div class="run-goal">${esc(run.goal)}</div>
        <div class="run-meta">${run.event_count} ${t('events')}</div>
      </button>`).join('') : `<div class="empty">${t('empty')}</div>`}
    <div class="section-title">${t('timeline')}</div>
    ${current ? renderTimeline(current) : ''}`;
}
function renderTimeline(run) {
  return `<div class="timeline">${(run.events || []).map(event => `
    <div class="event ${esc(event.status)}">
      <div class="event-name">${esc(event.name)} <span class="status ${esc(event.status)}">${esc(event.status)}</span></div>
      <div class="event-detail">${esc(event.detail || '')}</div>
    </div>`).join('')}</div>`;
}
function renderDetail(run) {
  if (!run) return `<div class="empty">${t('empty')}</div>`;
  const sections = run.sections || {};
  if (!sections[state.section]) state.section = sections['Multi-Agent Summary'] ? 'Multi-Agent Summary' : Object.keys(sections)[0] || 'Overview';
  return `
    <div class="section-title">${t('detail')}</div>
    <h2>${esc(run.goal)}</h2>
    <div><span class="status ${esc(run.effective_status)}">${esc(run.effective_status)}</span>${esc(run.run_id)}</div>
    ${renderTree(run)}
    <div class="tabs">${Object.keys(sections).map(name => `
      <button class="tab ${name === state.section ? 'active' : ''}" onclick="selectSection('${escAttr(name)}')">${esc(tabName(name))}</button>`).join('')}</div>
    <div class="report">${esc(sections[state.section] || run.report || '')}</div>`;
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
function selectProject(index) { state.project = index; state.run = 0; state.section = 'Overview'; render(); }
function selectRun(index) { state.run = index; state.section = 'Overview'; render(); }
function selectSection(name) { state.section = name; render(); }
function setQuery(value) { state.query = value; state.run = 0; render(); }
function toggleLang() { state.lang = state.lang === 'zh' ? 'en' : 'zh'; render(); }
render();
"""
