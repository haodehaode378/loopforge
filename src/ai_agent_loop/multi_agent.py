"""Read-only multi-agent run orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from ai_agent_loop.agent import Agent
from ai_agent_loop.events import EventRecord
from ai_agent_loop.store import RunStore
from ai_agent_loop.tools import FileTools


@dataclass(frozen=True)
class ChildSpec:
    role: str
    goal: str
    pattern: str


@dataclass(frozen=True)
class MultiAgentResult:
    parent_run_id: str
    child_run_ids: list[str]
    reviewer_run_id: str


class MultiAgentRunner:
    def __init__(self, store_root: str = ".agent", project_path: str = ".") -> None:
        self.store_root = store_root
        self.project_path = project_path

    def run(self, goal: str) -> MultiAgentResult:
        parent = Agent(store_root=self.store_root, project_path=self.project_path).run(
            f"Multi-agent parent: {goal}",
            persist=True,
        )
        parent_store = RunStore(self.store_root, project_path=self.project_path)
        parent_store.append_event(
            parent.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.parent_started",
                detail="Started read-only multi-agent coordination.",
                status="done",
                metadata={"goal": goal, "mode": "readonly_parallel_analysis"},
            ).to_dict(),
        )
        specs = child_specs(goal)
        parent_store.append_event(
            parent.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.parallel_plan",
                detail="Prepared read-only child roles for parallel-safe analysis.",
                status="done",
                metadata={"roles": [spec.role for spec in specs], "write_scopes": []},
            ).to_dict(),
        )

        child_records = []
        for spec in specs:
            child_records.append(self.run_child(parent.run_id, spec))

        reviewer = self.run_reviewer(parent.run_id, goal, child_records)
        child_run_ids = [record["child_run_id"] for record in child_records]
        parent_store.update_goal_metadata(
            parent.run_id,
            {
                "multi_agent": True,
                "child_run_ids": child_run_ids,
                "reviewer_run_id": reviewer["child_run_id"],
            },
        )
        parent_store.append_event(
            parent.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.conflict_detection",
                detail="No write scopes were assigned; conflict detection is a placeholder with no conflicts.",
                status="done",
                metadata={"conflicts": [], "write_scopes": []},
            ).to_dict(),
        )
        parent_store.append_event(
            parent.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.reviewer_decision",
                detail=reviewer["summary"],
                status="done",
                metadata={"reviewer_run_id": reviewer["child_run_id"], "decision": "merge_readonly_summaries"},
            ).to_dict(),
        )
        parent_store.append_event(
            parent.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.merged_summary",
                detail=merged_summary(goal, child_records),
                status="done",
                metadata={"child_run_ids": child_run_ids},
            ).to_dict(),
        )
        return MultiAgentResult(
            parent_run_id=parent.run_id,
            child_run_ids=child_run_ids,
            reviewer_run_id=reviewer["child_run_id"],
        )

    def run_child(self, parent_run_id: str, spec: ChildSpec) -> dict[str, str]:
        child = Agent(store_root=self.store_root, project_path=self.project_path).run(
            f"{spec.role}: {spec.goal}",
            persist=True,
        )
        child_store = RunStore(self.store_root, project_path=self.project_path)
        child_store.update_goal_metadata(
            child.run_id,
            {
                "parent_run_id": parent_run_id,
                "role": spec.role,
                "readonly": True,
            },
        )
        child_store.append_event(
            child.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.child_started",
                detail=f"Started read-only child role: {spec.role}",
                status="done",
                metadata={"parent_run_id": parent_run_id, "role": spec.role},
            ).to_dict(),
        )
        files = FileTools(child_store, child.run_id).search_files(spec.pattern, limit=5)
        snippets = []
        for path in files[:2]:
            try:
                snippets.append(FileTools(child_store, child.run_id).read_file(path)[:160])
            except UnicodeDecodeError:
                snippets.append("<binary or non-utf8 file skipped>")
        summary = child_summary(spec, files, snippets)
        artifact = child_store.write_artifact(child.run_id, "multi", "summary.md", summary)
        child_store.append_event(
            child.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.child_summary",
                detail=summary,
                status="done",
                metadata={"role": spec.role, "files": files, "readonly": True},
                artifacts={"summary": str(artifact)},
            ).to_dict(),
        )

        parent_store = RunStore(self.store_root, project_path=self.project_path)
        parent_store.append_event(
            parent_run_id,
            EventRecord(
                type="multi_agent",
                name="multi.child_created",
                detail=f"Created child run {child.run_id} for {spec.role}.",
                status="done",
                metadata={
                    "child_run_id": child.run_id,
                    "role": spec.role,
                    "goal": spec.goal,
                    "readonly": True,
                },
            ).to_dict(),
        )
        return {"child_run_id": child.run_id, "role": spec.role, "summary": summary}

    def run_reviewer(
        self,
        parent_run_id: str,
        goal: str,
        child_records: list[dict[str, str]],
    ) -> dict[str, str]:
        reviewer = Agent(store_root=self.store_root, project_path=self.project_path).run(
            f"reviewer: summarize child analysis for {goal}",
            persist=True,
        )
        reviewer_store = RunStore(self.store_root, project_path=self.project_path)
        reviewer_store.update_goal_metadata(
            reviewer.run_id,
            {
                "parent_run_id": parent_run_id,
                "role": "reviewer",
                "readonly": True,
            },
        )
        summary = reviewer_summary(child_records)
        artifact = reviewer_store.write_artifact(reviewer.run_id, "multi", "review.md", summary)
        reviewer_store.append_event(
            reviewer.run_id,
            EventRecord(
                type="multi_agent",
                name="multi.reviewer_summary",
                detail=summary,
                status="done",
                metadata={
                    "parent_run_id": parent_run_id,
                    "role": "reviewer",
                    "child_run_ids": [record["child_run_id"] for record in child_records],
                },
                artifacts={"review": str(artifact)},
            ).to_dict(),
        )
        parent_store = RunStore(self.store_root, project_path=self.project_path)
        parent_store.append_event(
            parent_run_id,
            EventRecord(
                type="multi_agent",
                name="multi.child_created",
                detail=f"Created reviewer child run {reviewer.run_id}.",
                status="done",
                metadata={
                    "child_run_id": reviewer.run_id,
                    "role": "reviewer",
                    "goal": f"Summarize child analysis for {goal}",
                    "readonly": True,
                },
            ).to_dict(),
        )
        return {"child_run_id": reviewer.run_id, "role": "reviewer", "summary": summary}


def child_specs(goal: str) -> list[ChildSpec]:
    return [
        ChildSpec("context-agent", f"Find relevant project context for {goal}", "*.md"),
        ChildSpec("risk-agent", f"Identify likely risks for {goal}", "*.py"),
        ChildSpec("verification-agent", f"Find verification entry points for {goal}", "test_*.py"),
    ]


def child_summary(spec: ChildSpec, files: list[str], snippets: list[str]) -> str:
    file_text = ", ".join(files) if files else "no files matched"
    snippet_count = len([snippet for snippet in snippets if snippet])
    return (
        f"{spec.role} completed read-only analysis. "
        f"Matched files: {file_text}. "
        f"Captured {snippet_count} snippet(s)."
    )


def reviewer_summary(child_records: list[dict[str, str]]) -> str:
    roles = ", ".join(record["role"] for record in child_records)
    return f"Reviewer accepted read-only child summaries from: {roles}."


def merged_summary(goal: str, child_records: list[dict[str, str]]) -> str:
    return (
        f"Merged read-only analysis for '{goal}' from "
        f"{len(child_records)} child run(s). No write conflicts were possible."
    )
