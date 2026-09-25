"""
Universal AI Auto Router for Sage AI.
"""
from .models import TaskType, ModelStatus, ModelSpec, ModelScore, RoutingResult
from .adapters import (
    BaseAdapter,
    GeminiAdapter,
    GroqAdapter,
    OpenRouterAdapter,
    NVIDIAAdapter,
    MistralAdapter,
    CerebrasAdapter,
    CloudflareAdapter,
    CohereAdapter,
    HuggingFaceAdapter,
    OllamaAdapter,
    ImageAdapter,
    ALL_ADAPTERS,
)
from .registry import ModelRegistry, CORE_MODEL_SPECS
from .health_tracker import HealthTracker
from .scoring_engine import ModelScoringEngine
from .response_validator import ResponseValidator
from .core_router import AutoRouter, get_auto_router
from .coding_router import AutoCodingRouter, CodingScoringWeights, CodingModelScore

__all__ = [
    "TaskType",
    "ModelStatus",
    "ModelSpec",
    "ModelScore",
    "RoutingResult",
    "BaseAdapter",
    "GeminiAdapter",
    "GroqAdapter",
    "OpenRouterAdapter",
    "NVIDIAAdapter",
    "MistralAdapter",
    "CerebrasAdapter",
    "CloudflareAdapter",
    "CohereAdapter",
    "HuggingFaceAdapter",
    "OllamaAdapter",
    "ImageAdapter",
    "ALL_ADAPTERS",
    "ModelRegistry",
    "CORE_MODEL_SPECS",
    "HealthTracker",
    "ModelScoringEngine",
    "ResponseValidator",
    "AutoRouter",
    "get_auto_router",
    "AutoCodingRouter",
    "CodingScoringWeights",
    "CodingModelScore",
]
