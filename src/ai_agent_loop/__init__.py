"""Minimal agent loop package."""

from ai_agent_loop.agent import Agent
from ai_agent_loop.approval import (
    ApprovalContract,
    ApprovalDecision,
    ApprovalRequest,
    ResumeEligibility,
    evaluate_approval_contract,
)
from ai_agent_loop.autonomous import AutonomousRunner
from ai_agent_loop.critique import build_change_set_critique, build_critique, render_change_set_critique, render_critique
from ai_agent_loop.goal import Goal
from ai_agent_loop.ledger import read_approval_ledger, summarize_ledger
from ai_agent_loop.loop import AgentStep, LoopResult, run_loop
from ai_agent_loop.multi_agent import MultiAgentResult, MultiAgentRunner
from ai_agent_loop.policy import PolicyDecision
from ai_agent_loop.provider import DeterministicFakeProvider, resolve_provider
from ai_agent_loop.project import Project, ProjectRegistry
from ai_agent_loop.risk import RiskAssessment
from ai_agent_loop.settings import LoopSettings, ProviderSettings, load_settings
from ai_agent_loop.store import RunStore, render_report
from ai_agent_loop.workbench import build_workbench_snapshot, render_workbench_html

__all__ = [
    "Agent",
    "AgentStep",
    "ApprovalContract",
    "ApprovalDecision",
    "ApprovalRequest",
    "AutonomousRunner",
    "build_critique",
    "build_change_set_critique",
    "build_workbench_snapshot",
    "DeterministicFakeProvider",
    "Goal",
    "load_settings",
    "LoopResult",
    "LoopSettings",
    "MultiAgentResult",
    "MultiAgentRunner",
    "PolicyDecision",
    "Project",
    "ProjectRegistry",
    "ProviderSettings",
    "read_approval_ledger",
    "RiskAssessment",
    "RunStore",
    "render_report",
    "render_change_set_critique",
    "render_critique",
    "render_workbench_html",
    "ResumeEligibility",
    "evaluate_approval_contract",
    "resolve_provider",
    "run_loop",
    "summarize_ledger",
]
