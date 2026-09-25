"""
Dedicated Auto Coding Router for Sage AI.
Computes task-specific dynamic coding rankings (#1 to #N) using the 9-factor coding score formula:
  - Coding Quality: 30%
  - Code Reasoning: 20%
  - Task Capability: 15%
  - Reliability: 10%
  - Context Capability: 5%
  - Latency: 5%
  - Availability: 5%
  - Quota: 5%
  - Cost: 5%
Total: 100%

Supports dynamic task adaptation (Simple Python, Large Project, Debugging, Architecture),
manual model selection with direct fidelity, and automatic next-in-line fallback cascade.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from .models import ModelSpec, TaskType, ModelStatus
from .registry import ModelRegistry, CORE_MODEL_SPECS
from .adapters import ALL_ADAPTERS
from .health_tracker import HealthTracker

logger = logging.getLogger(__name__)


@dataclass
class CodingScoringWeights:
    """9-factor coding weights (Total = 1.00). Configurable per coding subtask."""
    quality: float = 0.30        # Coding Quality (30%)
    reasoning: float = 0.20      # Code Reasoning (20%)
    task_cap: float = 0.15       # Task Capability (15%)
    reliability: float = 0.10    # Reliability (10%)
    context: float = 0.05        # Context Capability (5%)
    latency: float = 0.05        # Latency / Speed (5%)
    availability: float = 0.05   # Availability (5%)
    quota: float = 0.05          # Quota (5%)
    cost: float = 0.05           # Cost (5%)

    @classmethod
    def for_task_type(cls, task_type: str) -> "CodingScoringWeights":
        """
        Dynamically adjusts weights based on detected coding task:
        - Simple Python / Scripts -> prioritize speed & latency
        - Large project -> prioritize context + coding quality
        - Debugging -> prioritize reasoning + coding
        - Architecture -> prioritize reasoning + coding quality
        """
        t = task_type.lower()
        if "simple" in t or "script" in t or "snippet" in t or "speed" in t:
            # Prioritize speed / low latency
            return cls(
                quality=0.25,
                reasoning=0.15,
                task_cap=0.15,
                reliability=0.10,
                context=0.05,
                latency=0.20,  # Boosted for speed
                availability=0.05,
                quota=0.03,
                cost=0.02
            )
        elif "large" in t or "full_project" in t or "multi_file" in t or "repo" in t:
            # Prioritize large context + coding quality
            return cls(
                quality=0.35,  # Boosted quality
                reasoning=0.15,
                task_cap=0.15,
                reliability=0.10,
                context=0.15,  # Boosted context (128k - 2M tokens)
                latency=0.02,
                availability=0.03,
                quota=0.03,
                cost=0.02
            )
        elif "debug" in t or "fix" in t or "error" in t or "diagnos" in t:
            # Prioritize reasoning + coding quality
            return cls(
                quality=0.30,
                reasoning=0.30,  # Boosted reasoning for root-cause diagnosis
                task_cap=0.15,
                reliability=0.10,
                context=0.05,
                latency=0.02,
                availability=0.03,
                quota=0.03,
                cost=0.02
            )
        elif "architect" in t or "design" in t or "plan" in t or "structure" in t:
            # Prioritize reasoning + quality + context
            return cls(
                quality=0.30,
                reasoning=0.25,
                task_cap=0.15,
                reliability=0.10,
                context=0.10,
                latency=0.02,
                availability=0.03,
                quota=0.03,
                cost=0.02
            )
        # Default balanced coding weights
        return cls()


PROVIDER_NAMES = {
    "openrouter": "OpenRouter",
    "gemini": "Google Gemini",
    "mistral": "Mistral AI",
    "groq": "Groq",
    "nvidia": "NVIDIA NIM",
    "ollama": "Local Ollama",
    "huggingface": "HuggingFace",
    "cerebras": "Cerebras",
    "cohere": "Cohere",
    "local_facts": "Local Knowledge"
}


@dataclass
class CodingModelScore:
    """Detailed score evaluation of a coding-capable model."""
    spec: ModelSpec
    total_score: float
    rank: int = 0
    breakdown: Dict[str, float] = field(default_factory=dict)
    is_available: bool = True
    status_label: str = "Active"
    selection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        p_name = PROVIDER_NAMES.get(self.spec.provider_id, self.spec.provider_id.title())
        return {
            "rank": self.rank,
            "model_id": self.spec.model_id,
            "display_name": self.spec.display_name,
            "provider_id": self.spec.provider_id,
            "provider_name": p_name,
            "total_score": round(self.total_score, 2),
            "is_available": self.is_available,
            "status_label": self.status_label,
            "context_length": self.spec.context_length,
            "is_free": self.spec.is_free,
            "selection_reason": self.selection_reason,
            "breakdown": {k: round(v, 2) for k, v in self.breakdown.items()}
        }


class AutoCodingRouter:
    """
    Dedicated Auto Coding Router for Sage AI.
    Executes dynamic coding-specific rankings, model discovery, manual selection,
    and automatic failure fallback.
    """

    CODING_KEYWORDS = (
        "code", "coder", "coding", "program", "script", "python", "javascript",
        "typescript", "html", "css", "rust", "cpp", "c#", "java", "sql",
        "react", "vue", "backend", "frontend", "api", "database", "git",
        "debug", "fix", "refactor", "test", "build", "ast"
    )

    def __init__(self, health_tracker: Optional[HealthTracker] = None, registry: Optional[ModelRegistry] = None):
        self.health_tracker = health_tracker or HealthTracker()
        self.registry = registry or ModelRegistry()

    @staticmethod
    def detect_coding_task_profile(prompt: str, target_file: Optional[str] = None, file_count: int = 1) -> str:
        """Categorizes coding task for adaptive weight configuration."""
        p = prompt.lower()
        if target_file:
            p += f" {target_file.lower()}"

        if any(w in p for w in ("debug", "traceback", "error", "exception", "broken", "why does", "fix bug")):
            return "debugging"
        if any(w in p for w in ("architect", "system design", "pattern", "structure", "schema", "dag")):
            return "architecture"
        if file_count > 5 or any(w in p for w in ("entire project", "whole repo", "full stack", "all files", "workspace")):
            return "large_project"
        if any(w in p for w in ("simple", "quick script", "one liner", "fast", "snippet", "helper function")):
            return "simple_python"
        return "general_coding"

    def get_coding_capable_models(self) -> List[ModelSpec]:
        """
        Discovers all models in the global registry that are capable of coding tasks.
        Includes models with explicit coding capability >= 7.0 or coder in name.
        """
        coding_models = []
        all_specs = self.registry.get_all_models()
        for spec in all_specs:
            coding_cap = spec.get_task_capability(TaskType.CODING)
            name_lower = f"{spec.model_id} {spec.display_name}".lower()
            is_explicit_coder = any(kw in name_lower for kw in ("coder", "codestral", "deepseek-r1", "deepseek-coder", "sonnet", "union", "pareto"))
            
            # Capability threshold for coding tasks
            if coding_cap >= 7.0 or is_explicit_coder:
                coding_models.append(spec)

        return coding_models

    def score_coding_model(
        self,
        spec: ModelSpec,
        weights: CodingScoringWeights,
        task_profile: str = "general_coding"
    ) -> CodingModelScore:
        """
        Computes 9-factor dynamic coding score:
        1. Coding Quality (30%)
        2. Code Reasoning (20%)
        3. Task Capability (15%)
        4. Reliability (10%)
        5. Context Capability (5%)
        6. Latency / Speed (5%)
        7. Availability (5%)
        8. Quota (5%)
        9. Cost (5%)
        """
        provider_id = spec.provider_id
        adapter = ALL_ADAPTERS.get(provider_id)

        # 1. Coding Quality (scaled 1.0 - 10.0)
        # Spec base quality + bonus for recognized top-tier coding models
        base_q = spec.base_quality
        name_lower = f"{spec.model_id} {spec.display_name}".lower()
        if "union" in name_lower or "pareto" in name_lower:
            base_q = max(base_q, 9.9)
        elif "qwen-2.5-coder-32b" in name_lower or "qwen 2.5 coder 32b" in name_lower:
            base_q = max(base_q, 9.9)
        elif "deepseek-chat" in name_lower or "deepseek v3" in name_lower:
            base_q = max(base_q, 9.8)
        elif "deepseek-r1" in name_lower:
            base_q = max(base_q, 9.7)
        elif "codestral" in name_lower:
            base_q = max(base_q, 9.6)
        elif "gemini-2.0-flash" in name_lower:
            base_q = max(base_q, 9.6)
        elif "claude-3.5-sonnet" in name_lower or "claude-3.7-sonnet" in name_lower:
            base_q = max(base_q, 9.5)
        elif "llama-3.3-70b" in name_lower:
            base_q = max(base_q, 9.2)
        coding_quality = max(1.0, min(10.0, base_q))

        # 2. Code Reasoning (scaled 1.0 - 10.0)
        # Models with high reasoning (R1, Qwen 32B Coder, Sonnet, Gemini 2.0 Flash)
        reasoning_cap = spec.get_task_capability(TaskType.REASONING)
        if "union" in name_lower or "pareto" in name_lower:
            code_reasoning = 9.8
        elif "r1" in name_lower or "deepseek-r1" in name_lower:
            code_reasoning = 10.0
        elif "qwen" in name_lower and "32b" in name_lower:
            code_reasoning = 9.8
        elif "sonnet" in name_lower or "gemini-1.5-pro" in name_lower or "gemini-2.0-flash" in name_lower:
            code_reasoning = 9.6
        elif "deepseek-chat" in name_lower or "deepseek v3" in name_lower:
            code_reasoning = 9.5
        elif "codestral" in name_lower:
            code_reasoning = 9.3
        else:
            code_reasoning = max(1.0, min(10.0, reasoning_cap))

        # 3. Task Capability (scaled 1.0 - 10.0)
        task_cap = max(1.0, min(10.0, spec.get_task_capability(TaskType.CODING)))

        # 4. Reliability (scaled 1.0 - 10.0)
        # Check provider health history
        health_stat = self.health_tracker.get_status(spec.model_id, provider_id)
        if health_stat == ModelStatus.AVAILABLE:
            reliability = 9.6
        elif health_stat == ModelStatus.RATE_LIMITED:
            reliability = 2.0
        elif health_stat == ModelStatus.UNAVAILABLE:
            reliability = 4.0
        else:
            reliability = 8.8

        # 5. Context Capability (scaled 1.0 - 10.0)
        ctx = spec.context_length
        if ctx >= 1000000:
            context_factor = 10.0  # 1M - 2M (Gemini)
        elif ctx >= 128000:
            context_factor = 9.4   # 128k (Llama 3.3, Claude)
        elif ctx >= 64000:
            context_factor = 8.8   # 64k
        elif ctx >= 32768:
            context_factor = 8.2   # 32k (Qwen Coder, Codestral)
        elif ctx >= 8192:
            context_factor = 7.0
        else:
            context_factor = 5.5

        # 6. Latency / Speed (scaled 1.0 - 10.0)
        base_speed = spec.speed_score
        rec = self.health_tracker._memory_health.get(spec.model_id)
        if rec and rec.get("avg_latency_ms", 0) > 0:
            lat = rec["avg_latency_ms"]
            if lat < 250:
                measured_spd = 10.0
            elif lat < 600:
                measured_spd = 9.2
            elif lat < 1200:
                measured_spd = 8.4
            else:
                measured_spd = 7.0
            speed_factor = (base_speed * 0.5) + (measured_spd * 0.5)
        else:
            speed_factor = base_speed

        # 7. Availability (scaled 1.0 - 10.0)
        is_avail = adapter.is_available() if adapter else False
        avail_factor = 10.0 if is_avail else (8.0 if spec.is_free else 4.0)

        # 8. Quota (scaled 1.0 - 10.0)
        if is_avail and adapter:
            quota_factor = adapter.get_quota_ratio() * 10.0
        else:
            quota_factor = 7.0 if spec.is_free else 3.0

        # 9. Cost (scaled 1.0 - 10.0)
        if spec.is_free:
            cost_factor = 10.0
        else:
            cost_m = spec.cost_per_m_tokens
            cost_factor = max(4.0, 10.0 - (cost_m * 0.5))

        # Weighted calculation
        total = (
            coding_quality * weights.quality +
            code_reasoning * weights.reasoning +
            task_cap * weights.task_cap +
            reliability * weights.reliability +
            context_factor * weights.context +
            speed_factor * weights.latency +
            avail_factor * weights.availability +
            quota_factor * weights.quota +
            cost_factor * weights.cost
        )

        if not spec.is_free or spec.cost_per_m_tokens > 0.0:
            total *= 0.88

        breakdown = {
            "Coding Quality (30%)": coding_quality,
            "Code Reasoning (20%)": code_reasoning,
            "Task Capability (15%)": task_cap,
            "Reliability (10%)": reliability,
            "Context (5%)": context_factor,
            "Speed / Latency (5%)": speed_factor,
            "Availability (5%)": avail_factor,
            "Quota (5%)": quota_factor,
            "Cost (5%)": cost_factor
        }

        # Status label
        if not is_avail:
            status_label = "Unavailable (No Key)"
        elif health_stat == ModelStatus.AVAILABLE:
            status_label = "Healthy • Ready"
        elif health_stat == ModelStatus.RATE_LIMITED:
            status_label = "Rate Limited"
        else:
            status_label = "Active"

        return CodingModelScore(
            spec=spec,
            total_score=total,
            breakdown=breakdown,
            is_available=is_avail,
            status_label=status_label
        )

    def rank_coding_models(
        self,
        prompt: str = "",
        target_file: Optional[str] = None,
        file_count: int = 1,
        custom_weights: Optional[CodingScoringWeights] = None
    ) -> List[CodingModelScore]:
        """
        Dynamically scores and sorts all coding models from #1 (Best) down to #N.
        """
        task_profile = self.detect_coding_task_profile(prompt, target_file, file_count)
        weights = custom_weights or CodingScoringWeights.for_task_type(task_profile)

        coding_models = self.get_coding_capable_models()
        scored_models: List[CodingModelScore] = []

        for spec in coding_models:
            score_obj = self.score_coding_model(spec, weights, task_profile)
            scored_models.append(score_obj)

        # Sort dynamically by total_score descending
        scored_models.sort(key=lambda m: m.total_score, reverse=True)

        # Assign rank #1 to #N
        for idx, item in enumerate(scored_models, start=1):
            item.rank = idx
            if idx == 1:
                item.selection_reason = f"Top-ranked coding model for {task_profile.replace('_', ' ').title()} ({item.total_score:.1f}/10)"
            elif idx <= 3:
                item.selection_reason = f"Top tier coding performer ({item.total_score:.1f}/10)"
            else:
                item.selection_reason = f"Viable alternative ({item.total_score:.1f}/10)"

        return scored_models

    def select_model_for_execution(
        self,
        selected_model: Optional[str] = None,
        allow_fallback: bool = True,
        prompt: str = "",
        target_file: Optional[str] = None,
        file_count: int = 1,
        enforce_zero_cost: bool = True
    ) -> Dict[str, Any]:
        """
        Resolves model selection according to rules:
        - If 'Auto' / 'Auto Router' / None:
          Selects #1 available free coding model from dynamic coding ranking.
        - If manual model selected (e.g. 'Pareto 26.9 (Union Alpha)'):
          Zero-Cost Guard checks if model costs > 0 Rs.
          If > 0 Rs, request will NOT continue with paid model; automatically shifts to 100% Free model.
          Prepares fallback cascade queue containing only 100% Free models (0 Rs).
        """
        ranked_queue = self.rank_coding_models(prompt, target_file, file_count)
        is_auto = not selected_model or selected_model.strip().lower() in ("auto", "auto router", "auto — best coding model")

        from engine.zero_cost_guard import get_zero_cost_guard
        guard = get_zero_cost_guard()

        if is_auto:
            # Auto Router prioritizes top-ranked available free model (0 Rs)
            chosen = None
            for cand in ranked_queue:
                if cand.is_available and guard.is_zero_cost(cand.spec.model_id, cand.spec.provider_id):
                    chosen = cand
                    break
            # Fallback to any free model if no keys currently registered
            if not chosen and ranked_queue:
                for cand in ranked_queue:
                    if guard.is_zero_cost(cand.spec.model_id, cand.spec.provider_id):
                        chosen = cand
                        break
            if not chosen and ranked_queue:
                chosen = ranked_queue[0]

            p_name = PROVIDER_NAMES.get(chosen.spec.provider_id, chosen.spec.provider_id.title()) if chosen else "Google Gemini"
            avail_fallbacks = [m.spec.model_id for m in ranked_queue if m != chosen and m.is_available and guard.is_zero_cost(m.spec.model_id, m.spec.provider_id)]
            fallback_q = avail_fallbacks if avail_fallbacks else [m.spec.model_id for m in ranked_queue if m != chosen and guard.is_zero_cost(m.spec.model_id, m.spec.provider_id)]

            return {
                "mode": "auto",
                "selected_model": chosen.spec.model_id if chosen else "gemini-2.0-flash",
                "display_name": chosen.spec.display_name if chosen else "Auto Router",
                "provider_id": chosen.spec.provider_id if chosen else "gemini",
                "provider_name": p_name,
                "coding_rank": chosen.rank if chosen else 1,
                "coding_score": round(chosen.total_score, 2) if chosen else 9.5,
                "reason": chosen.selection_reason if chosen else "Optimal 0 Rs Free coding engine",
                "allow_fallback": allow_fallback,
                "fallback_queue": fallback_q if allow_fallback else [],
                "all_rankings": [m.to_dict() for m in ranked_queue]
            }

        # Manual selection: find corresponding model spec
        sel_lower = selected_model.strip().lower()
        matched_item: Optional[CodingModelScore] = None
        for item in ranked_queue:
            if (sel_lower in item.spec.model_id.lower() or
                sel_lower in item.spec.display_name.lower() or
                item.spec.model_id.lower() in sel_lower or
                item.spec.display_name.lower() in sel_lower or
                ("union" in sel_lower and "pareto" in item.spec.model_id.lower())):
                matched_item = item
                break

        if matched_item:
            spec = matched_item.spec
            p_name = PROVIDER_NAMES.get(spec.provider_id, spec.provider_id.title())

            # Zero-Cost Guard: Intercept paid models (> 0 Rs)
            if enforce_zero_cost and not guard.is_zero_cost(spec.model_id, spec.provider_id):
                # The request MUST NOT continue with the paid model!
                # Shift to top free coding model
                free_model_id, free_provider_id, shift_reason = guard.resolve_free_model(
                    requested_model=spec.model_id,
                    task_type="coding"
                )
                free_item = next((it for it in ranked_queue if it.spec.model_id == free_model_id), None)
                if not free_item:
                    free_item = next((it for it in ranked_queue if guard.is_zero_cost(it.spec.model_id, it.spec.provider_id)), ranked_queue[0])

                free_spec = free_item.spec
                free_p_name = PROVIDER_NAMES.get(free_spec.provider_id, free_spec.provider_id.title())
                free_fallbacks = [m.spec.model_id for m in ranked_queue if m != free_item and guard.is_zero_cost(m.spec.model_id, m.spec.provider_id)]

                return {
                    "mode": "manual_shifted_free",
                    "selected_model": free_spec.model_id,
                    "display_name": free_spec.display_name,
                    "provider_id": free_spec.provider_id,
                    "provider_name": free_p_name,
                    "coding_rank": free_item.rank,
                    "coding_score": round(free_item.total_score, 2),
                    "reason": f"🛡️ Zero-Cost Guard: Intercepted paid model '{spec.display_name}' (> 0 Rs). Shifted to 100% Free model.",
                    "shifted_from_paid": True,
                    "original_model": spec.model_id,
                    "cost_saved_rs": round((spec.cost_per_m_tokens or 2.5) * guard.usd_to_inr, 2),
                    "allow_fallback": allow_fallback,
                    "fallback_queue": free_fallbacks if allow_fallback else [],
                    "all_rankings": [m.to_dict() for m in ranked_queue]
                }

            avail_fallbacks = [m.spec.model_id for m in ranked_queue if m != matched_item and m.is_available]
            fallback_q = avail_fallbacks if avail_fallbacks else [m.spec.model_id for m in ranked_queue if m != matched_item]
            return {
                "mode": "manual",
                "selected_model": spec.model_id,
                "display_name": spec.display_name,
                "provider_id": spec.provider_id,
                "provider_name": p_name,
                "coding_rank": matched_item.rank,
                "coding_score": round(matched_item.total_score, 2),
                "reason": "Direct user selection",
                "allow_fallback": allow_fallback,
                "fallback_queue": fallback_q if allow_fallback else [],
                "all_rankings": [m.to_dict() for m in ranked_queue]
            }

        # Fallback for arbitrary model string
        # Zero-Cost Guard check on arbitrary model string
        if enforce_zero_cost and not guard.is_zero_cost(selected_model):
            free_model_id, free_provider_id, shift_reason = guard.resolve_free_model(
                requested_model=selected_model,
                task_type="coding"
            )
            free_fallbacks = [m.spec.model_id for m in ranked_queue if guard.is_zero_cost(m.spec.model_id, m.spec.provider_id)]
            return {
                "mode": "manual_shifted_free",
                "selected_model": free_model_id,
                "display_name": free_model_id,
                "provider_id": free_provider_id,
                "provider_name": free_provider_id.title(),
                "coding_rank": 1,
                "coding_score": 9.5,
                "reason": f"🛡️ Zero-Cost Guard: Intercepted paid model '{selected_model}' (> 0 Rs). Shifted to 100% Free model.",
                "shifted_from_paid": True,
                "original_model": selected_model,
                "cost_saved_rs": 212.5,
                "allow_fallback": allow_fallback,
                "fallback_queue": free_fallbacks if allow_fallback else [],
                "all_rankings": [m.to_dict() for m in ranked_queue]
            }

        avail_fallbacks = [m.spec.model_id for m in ranked_queue if m.is_available]
        fallback_q = avail_fallbacks if avail_fallbacks else [m.spec.model_id for m in ranked_queue]
        return {
            "mode": "manual",
            "selected_model": selected_model,
            "display_name": selected_model,
            "provider_id": "auto",
            "provider_name": "Selected Model",
            "coding_rank": 1,
            "coding_score": 9.0,
            "reason": "User specified model",
            "allow_fallback": allow_fallback,
            "fallback_queue": fallback_q if allow_fallback else [],
            "all_rankings": [m.to_dict() for m in ranked_queue]
        }
