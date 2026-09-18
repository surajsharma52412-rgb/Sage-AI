"""
Sage Multi-Agentic AI Architecture Package.
"Plan • Create • Code • Automate • Anything"
"""
from .request_analyzer import RequestAnalyzer
from .router import FallbackRouter
from .orchestrator import (
    AgentOrchestrator,
    get_orchestrator,
    TaskDecomposer,
    AgentRouter,
    WorkflowManager,
    SelfReflection,
    MemoryManager,
)
from .agents import (
    ResearchAgent,
    CodingAgent,
    ImageMediaAgent,
    DataAnalysisAgent,
    ContentAgent,
    ExecutionAgent,
    PlanningAgent,
)

__all__ = [
    "RequestAnalyzer",
    "FallbackRouter",
    "AgentOrchestrator",
    "get_orchestrator",
    "TaskDecomposer",
    "AgentRouter",
    "WorkflowManager",
    "SelfReflection",
    "MemoryManager",
    "ResearchAgent",
    "CodingAgent",
    "ImageMediaAgent",
    "DataAnalysisAgent",
    "ContentAgent",
    "ExecutionAgent",
    "PlanningAgent",
]
