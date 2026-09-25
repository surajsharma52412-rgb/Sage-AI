"""
SAGE Autonomous Software Engineering Coding Agent Architecture.
UNDERSTAND ➔ ANALYZE ➔ PLAN ➔ IMPLEMENT ➔ EXECUTE ➔ TEST ➔ DEBUG ➔ REVIEW ➔ VERIFY ➔ CHECKPOINT ➔ DELIVER
"""
from .orchestrator import CodingAgentOrchestrator
from .project_analyzer import ProjectAnalyzer
from .project_understanding import ProjectUnderstandingEngine
from .codebase_indexer import CodebaseIndexer
from .context_manager import ContextFileManager
from .context_engine import ContextEngine
from .long_context_memory import LongContextMemory
from .persistent_task_manager import PersistentTaskManager
from .task_planner import TaskPlannerManager
from .task_scheduler import TaskScheduler
from .tool_ecosystem import ToolEcosystem
from .tool_system import ToolSystem
from .sandbox_runner import SandboxRunner
from .test_debug_fix_loop import TestDebugFixLoop
from .code_reviewer import CodeReviewer
from .checkpoint_manager import CheckpointManager
from .model_router import CodingModelRouter
from .safety_controller import SafetyController
from .infrastructure import ScalableInfrastructure
from .sub_agents import (
    BaseSubAgent,
    ArchitectAgent,
    BackendAgent,
    FrontendAgent,
    DatabaseWorker,
    DebuggerWorker,
    QAAgent,
    SecurityWorker,
    ReviewerWorker,
    DevOpsAgent,
    DocumentationAgent,
)
from .pipeline import (
    CodeIntegrator,
    AutomatedValidator,
    SelfHealingLoop,
    FinalPackager,
)
from .master_prompt_generator import MasterPromptGenerator, MasterPromptResult
from .request_intelligence import (
    RequestIntelligenceEngine,
    RequestIntelligenceReport,
    ComplexityLevel,
    ProjectMode,
    AmbiguityLevel,
    StructuredRequirements,
    RiskAssessment
)
from .project_memory import ProjectMemoryManager, StructuredProjectMemory
from .requirement_traceability import (
    RequirementTraceabilityMatrix,
    RequirementStatus,
    TraceableRequirement
)
from .model_benchmarking import (
    ModelBenchmarkTracker,
    ModelBenchmarkStats,
    ModelExecutionRecord
)
from .multi_model_review import (
    MultiModelReviewSystem,
    MultiModelReviewReport,
    ReviewFinding
)
from .safety_approval_gates import (
    SafetyApprovalGates,
    ActionRiskTier,
    GateEvaluationResult
)

__all__ = [
    "CodingAgentOrchestrator",
    "MasterPromptGenerator",
    "MasterPromptResult",
    "RequestIntelligenceEngine",
    "RequestIntelligenceReport",
    "ComplexityLevel",
    "ProjectMode",
    "AmbiguityLevel",
    "StructuredRequirements",
    "RiskAssessment",
    "ProjectMemoryManager",
    "StructuredProjectMemory",
    "RequirementTraceabilityMatrix",
    "RequirementStatus",
    "TraceableRequirement",
    "ModelBenchmarkTracker",
    "ModelBenchmarkStats",
    "ModelExecutionRecord",
    "MultiModelReviewSystem",
    "MultiModelReviewReport",
    "ReviewFinding",
    "SafetyApprovalGates",
    "ActionRiskTier",
    "GateEvaluationResult",
    "ProjectAnalyzer",
    "ProjectUnderstandingEngine",
    "CodebaseIndexer",
    "ContextFileManager",
    "ContextEngine",
    "LongContextMemory",
    "PersistentTaskManager",
    "TaskPlannerManager",
    "TaskScheduler",
    "ToolEcosystem",
    "ToolSystem",
    "SandboxRunner",
    "TestDebugFixLoop",
    "CodeReviewer",
    "CheckpointManager",
    "CodingModelRouter",
    "SafetyController",
    "ScalableInfrastructure",
    "BaseSubAgent",
    "ArchitectAgent",
    "BackendAgent",
    "FrontendAgent",
    "DatabaseWorker",
    "DebuggerWorker",
    "QAAgent",
    "SecurityWorker",
    "ReviewerWorker",
    "DevOpsAgent",
    "DocumentationAgent",
    "CodeIntegrator",
    "AutomatedValidator",
    "SelfHealingLoop",
    "FinalPackager",
]
