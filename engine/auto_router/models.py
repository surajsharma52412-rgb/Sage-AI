"""
Data structures and contracts for Sage Universal AI Auto Router.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from engine.providers.base_provider import ProviderResponse


class TaskType(str, Enum):
    GENERAL_CHAT = "general_chat"
    CODING = "coding"
    REASONING = "reasoning"
    VISION = "vision"
    IMAGE_GEN = "image_gen"
    AGENT = "agent"
    FAST_LIGHTWEIGHT = "fast"
    LONG_CONTEXT = "long_context"


class ModelStatus(str, Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"


@dataclass
class ModelSpec:
    """Complete specification of an individual model in the universal registry."""
    model_id: str
    display_name: str
    provider_id: str
    base_quality: float = 8.0               # Benchmark quality (0.0 - 10.0)
    task_capabilities: Dict[str, float] = field(default_factory=dict) # Score per TaskType
    context_length: int = 32768
    speed_score: float = 8.0                 # 10.0 for Cerebras/Groq, 7-8 for standard, 5-6 for heavy models
    is_free: bool = True
    cost_per_m_tokens: float = 0.0          # USD per million tokens
    description: str = ""
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_tools: bool = True

    def get_task_capability(self, task: TaskType) -> float:
        """Returns task capability score (0.0 - 10.0) for the given task."""
        val = self.task_capabilities.get(task.value if isinstance(task, TaskType) else str(task))
        if val is not None:
            return float(val)
        # Default fallback capability
        return self.base_quality * 0.85


@dataclass
class ModelScore:
    """Computed real-time dynamic score and ranking factor breakdown for a model."""
    model: ModelSpec
    overall_score: float = 0.0
    global_rank: int = 0
    status: str = ModelStatus.AVAILABLE.value
    
    # 8 Core Weighted Scoring Factors (scaled 0.0 - 10.0 each)
    quality_factor: float = 0.0         # Weight: 30%
    task_factor: float = 0.0            # Weight: 20%
    availability_factor: float = 0.0    # Weight: 10%
    quota_factor: float = 0.0           # Weight: 10%
    speed_factor: float = 0.0           # Weight: 10%
    cost_factor: float = 0.0            # Weight: 10%
    context_factor: float = 0.0         # Weight: 5%
    health_factor: float = 0.0          # Weight: 5%

    def formatted_breakdown(self) -> str:
        return (
            f"Quality:{self.quality_factor:.1f}(30%) | "
            f"Task:{self.task_factor:.1f}(20%) | "
            f"Avail:{self.availability_factor:.1f}(10%) | "
            f"Quota:{self.quota_factor:.1f}(10%) | "
            f"Speed:{self.speed_factor:.1f}(10%) | "
            f"Cost:{self.cost_factor:.1f}(10%) | "
            f"Ctx:{self.context_factor:.1f}(5%) | "
            f"Health:{self.health_factor:.1f}(5%)"
        )


@dataclass
class RoutingResult:
    """Result of an auto-routing execution cycle."""
    response: ProviderResponse
    selected_model: ModelSpec
    global_rank: int
    score: float
    fallback_used: bool = False
    fallback_count: int = 0
    attempted_models: List[str] = field(default_factory=list)
    task_type: str = TaskType.GENERAL_CHAT.value
    validation_passed: bool = True
    telemetry_badge: str = ""

    @property
    def success(self) -> bool:
        return self.response.success if self.response else False

    @property
    def text(self) -> str:
        return self.response.text if self.response else ""

    @property
    def model_name(self) -> str:
        return self.response.model_name if self.response else self.selected_model.display_name

    @property
    def provider_id(self) -> str:
        return self.response.provider_id if self.response else self.selected_model.provider_id

    @property
    def latency_ms(self) -> float:
        return self.response.latency_ms if self.response else 0.0

    @property
    def error_msg(self) -> Optional[str]:
        return self.response.error_msg if self.response else None
