"""
Dynamic Scoring Engine for Sage AI Auto Router.
Evaluates all individual models globally across the 8 core weighted factors.
"""
import logging
from typing import List, Dict, Any, Optional

from .models import ModelSpec, ModelScore, TaskType, ModelStatus
from .adapters import ALL_ADAPTERS
from .health_tracker import HealthTracker

logger = logging.getLogger(__name__)


class ModelScoringEngine:
    """
    Computes real-time dynamic scores for all models per request:
      - Quality: 30%
      - Task Capability: 20%
      - Availability: 10%
      - API Quota / Rate Limit: 10%
      - Latency / Speed: 10%
      - Cost (Free / Paid): 10%
      - Context Window: 5%
      - Provider Health: 5%
    """

    # Exact weights matching the specification
    WEIGHT_QUALITY = 0.30
    WEIGHT_TASK = 0.20
    WEIGHT_AVAILABILITY = 0.10
    WEIGHT_QUOTA = 0.10
    WEIGHT_SPEED = 0.10
    WEIGHT_COST = 0.10
    WEIGHT_CONTEXT = 0.05
    WEIGHT_HEALTH = 0.05

    def __init__(self, health_tracker: Optional[HealthTracker] = None):
        self.health_tracker = health_tracker or HealthTracker()

    def score_model(
        self,
        spec: ModelSpec,
        task: TaskType = TaskType.GENERAL_CHAT,
        prompt_len: int = 0
    ) -> ModelScore:
        """Calculates dynamic score for an individual model."""
        provider_id = spec.provider_id
        adapter = ALL_ADAPTERS.get(provider_id)

        # 1. Quality Factor (30%)
        quality = max(1.0, min(10.0, spec.base_quality))

        # 2. Task Capability Factor (20%)
        task_cap = max(1.0, min(10.0, spec.get_task_capability(task)))

        # 3. Availability Factor (10%)
        is_avail = adapter.is_available() if adapter else False
        avail_factor = 10.0 if is_avail else 0.0

        # 4. Quota Factor (10%)
        if is_avail and adapter:
            quota_factor = adapter.get_quota_ratio() * 10.0
        else:
            quota_factor = 0.0

        # 5. Speed / Latency Factor (10%)
        base_speed = spec.speed_score
        # Check measured health latency if available
        rec = self.health_tracker._memory_health.get(spec.model_id)
        if rec and rec.get("avg_latency_ms", 0) > 0:
            lat = rec["avg_latency_ms"]
            if lat < 300:
                measured_speed = 10.0
            elif lat < 600:
                measured_speed = 9.2
            elif lat < 1200:
                measured_speed = 8.4
            elif lat < 2500:
                measured_speed = 7.2
            else:
                measured_speed = 6.0
            speed_factor = (base_speed * 0.5) + (measured_speed * 0.5)
        else:
            speed_factor = base_speed

        # 6. Cost Factor (10%)
        if spec.is_free:
            cost_factor = 10.0
        else:
            cost_m = spec.cost_per_m_tokens
            cost_factor = max(4.0, 10.0 - (cost_m * 0.5))

        # 7. Context Window Factor (5%)
        ctx = spec.context_length
        if ctx >= 1000000:
            context_factor = 10.0  # 1M - 2M (Gemini)
        elif ctx >= 128000:
            context_factor = 9.2   # 128k (Llama 3.3, NVIDIA, Cohere)
        elif ctx >= 64000:
            context_factor = 8.6   # 64k (DeepSeek V3)
        elif ctx >= 32768:
            context_factor = 8.0   # 32k (Qwen, Mistral)
        elif ctx >= 8192:
            context_factor = 7.0   # 8k (Cerebras, Gemma)
        else:
            context_factor = 6.0   # 4k

        # 8. Provider Health Factor (5%)
        health_factor = self.health_tracker.get_health_score(spec.model_id, provider_id)

        # Real-time status
        status = self.health_tracker.get_status(spec.model_id, provider_id)

        # Compute dynamic weighted sum (scaled 0.0 - 10.0)
        raw_score = (
            quality * self.WEIGHT_QUALITY +
            task_cap * self.WEIGHT_TASK +
            avail_factor * self.WEIGHT_AVAILABILITY +
            quota_factor * self.WEIGHT_QUOTA +
            speed_factor * self.WEIGHT_SPEED +
            cost_factor * self.WEIGHT_COST +
            context_factor * self.WEIGHT_CONTEXT +
            health_factor * self.WEIGHT_HEALTH
        )

        # Apply cooldown damper if rate-limited
        if status == ModelStatus.RATE_LIMITED:
            raw_score *= 0.65
        elif status == ModelStatus.UNAVAILABLE:
            # Unavailable models keep their potential score but are marked unavailable
            # for sorting to ensure configured models always take priority
            pass

        final_score = round(max(1.0, min(10.0, raw_score)), 1)

        return ModelScore(
            model=spec,
            overall_score=final_score,
            global_rank=0,
            status=status.value,
            quality_factor=round(quality, 1),
            task_factor=round(task_cap, 1),
            availability_factor=round(avail_factor, 1),
            quota_factor=round(quota_factor, 1),
            speed_factor=round(speed_factor, 1),
            cost_factor=round(cost_factor, 1),
            context_factor=round(context_factor, 1),
            health_factor=round(health_factor, 1)
        )

    def rank_models(
        self,
        models: List[ModelSpec],
        task: Optional[TaskType] = TaskType.GENERAL_CHAT,
        prompt_len: int = 0,
        filter_incompatible: bool = False
    ) -> List[ModelScore]:
        """
        Ranks ALL models globally from BEST (#1) to LOWEST (#N).
        Available models strictly precede unavailable models; within each group,
        ordered descending by dynamic overall score, breaking ties by task capability and base quality.
        """
        effective_task = task or TaskType.GENERAL_CHAT
        scored_list: List[ModelScore] = []
        for spec in models:
            if filter_incompatible:
                # Filter image models for non-image tasks, and non-image models for image tasks
                if effective_task == TaskType.IMAGE_GEN and spec.provider_id != "image":
                    continue
                if effective_task != TaskType.IMAGE_GEN and spec.provider_id == "image":
                    continue

            score_obj = self.score_model(spec, task=effective_task, prompt_len=prompt_len)
            scored_list.append(score_obj)

        # Sort criteria:
        # 1. Operational status priority: Available (0) > Rate Limited (1) > Unavailable (2)
        # 2. Overall score descending
        # 3. Task capability descending
        # 4. Base quality descending
        def sort_key(s: ModelScore):
            status_order = {
                ModelStatus.AVAILABLE.value: 0,
                ModelStatus.RATE_LIMITED.value: 1,
                ModelStatus.UNAVAILABLE.value: 2
            }.get(s.status, 2)
            return (status_order, -s.overall_score, -s.task_factor, -s.quality_factor)

        scored_list.sort(key=sort_key)

        # Assign 1-indexed global rank
        for idx, item in enumerate(scored_list, 1):
            item.global_rank = idx

        return scored_list
