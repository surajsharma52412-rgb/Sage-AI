"""
Core Universal AI Auto Router for Sage AI.
Coordinates task detection, global ranking of all 54+ models, execution with cascading fallback,
AST code validation, and telemetry.
"""
import time
import re
import logging
from typing import Optional, List, Dict, Any, Callable

from database.db_manager import get_db
from engine.providers.base_provider import ProviderResponse
from engine.request_analyzer import RequestAnalyzer
from .models import TaskType, ModelSpec, ModelScore, RoutingResult, ModelStatus
from .adapters import ALL_ADAPTERS, BaseAdapter
from .registry import ModelRegistry
from .health_tracker import HealthTracker
from .scoring_engine import ModelScoringEngine
from .response_validator import ResponseValidator

logger = logging.getLogger(__name__)


class AutoRouter:
    """
    Universal AI Auto Router:
    Ranks every individual model globally from BEST (#1) to LOWEST (#N) across all providers.
    Executes top-ranked model with automatic fallback and response validation.
    """

    def __init__(self):
        self.registry = ModelRegistry()
        self.health_tracker = HealthTracker()
        self.scoring_engine = ModelScoringEngine(health_tracker=self.health_tracker)
        self.validator = ResponseValidator()
        self.adapters = ALL_ADAPTERS

    def detect_task(self, prompt: str, force_web: bool = False, **kwargs) -> TaskType:
        """Classifies request into fine-grained TaskType."""
        p_lower = prompt.lower().strip()

        # 1. Image Generation
        if any(k in p_lower for k in (
            "generate image", "generate an image", "create image", "create an image",
            "draw", "render image", "render an image", "generate a picture", "paint a picture",
            "flux", "illustration", "make an image", "generate picture"
        )):
            return TaskType.IMAGE_GEN

        # 2. Vision / Image inspection
        if kwargs.get("has_image") or any(k in p_lower for k in ("look at this image", "describe this image", "analyze this photo", "in this screenshot")):
            return TaskType.VISION

        # 3. Coding / Development
        analysis = RequestAnalyzer.analyze(prompt, force_web=force_web)
        if analysis.get("intent") == "Coding/App":
            return TaskType.CODING

        coding_keywords = (
            "def ", "class ", "function", "write a script", "debug", "refactor",
            "syntaxerror", "python", "javascript", "typescript", "c++", "rust",
            "html", "css", "sql", "pyside6", "algorithm", "unit test", "api endpoint"
        )
        if any(k in p_lower for k in coding_keywords):
            return TaskType.CODING

        # 4. Deep Reasoning / Analysis
        reasoning_keywords = (
            "reason step by step", "think carefully", "mathematical proof", "solve the equation",
            "logical deduction", "analyze the tradeoffs", "pros and cons of", "compare and contrast",
            "why does", "deep research", "evaluate the hypothesis", "calculate"
        )
        if any(k in p_lower for k in reasoning_keywords):
            return TaskType.REASONING

        # 5. Agent / Tool execution
        if any(k in p_lower for k in ("automate", "workflow", "run task", "schedule", "pipeline", "agentic", "subtasks")):
            return TaskType.AGENT

        # 6. Long Context
        if len(prompt.split()) > 1500 or kwargs.get("is_long_doc"):
            return TaskType.LONG_CONTEXT

        # 7. Fast / Lightweight
        if kwargs.get("is_fast") or any(k in p_lower for k in ("quick", "fast", "briefly", "in one line", "short answer", "tldr", "one sentence")):
            return TaskType.FAST_LIGHTWEIGHT

        return TaskType.GENERAL_CHAT

    def get_global_ranking(
        self,
        task: Optional[TaskType] = None,
        prompt: str = "",
        filter_incompatible: bool = False
    ) -> List[ModelScore]:
        """Returns all registered models ranked globally from BEST (#1) to LOWEST (#N)."""
        all_specs = self.registry.get_all_models()
        return self.scoring_engine.rank_models(
            all_specs,
            task=task,
            prompt_len=len(prompt),
            filter_incompatible=filter_incompatible
        )

    def route(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        task_override: Optional[TaskType] = None,
        on_stage_change: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> RoutingResult:
        """
        Executes query through the globally ranked models with cascading fallback.
        """
        # Step 1: Detect Task
        task = task_override or self.detect_task(prompt, **kwargs)
        if on_stage_change:
            on_stage_change(f"🎯 Task Detected: {task.value.upper()}")

        # Step 2: Global Ranking across ALL 54+ models
        ranked_queue = self.get_global_ranking(task=task, prompt=prompt, filter_incompatible=True)
        if not ranked_queue:
            # Emergency fallback
            return self._emergency_fallback(prompt, task, "No models registered.")

        top_model = ranked_queue[0]
        from engine.zero_cost_guard import get_zero_cost_guard
        guard = get_zero_cost_guard()
        if not guard.is_zero_cost(top_model.model.model_id, top_model.model.provider_id):
            if on_stage_change:
                on_stage_change(f"🛡️ Zero-Cost Guard: Intercepted paid model #{top_model.global_rank} ({top_model.model.display_name}). Shifting to top-ranked 100% Free model...")
        elif on_stage_change:
            on_stage_change(f"📊 Global Rank #1: {top_model.model.display_name} ({top_model.model.provider_id.upper()}) [Score: {top_model.overall_score} • 0 Rs Free Tier]")

        attempted: List[str] = []
        fallback_used = False
        fallback_count = 0

        # Step 3: Cascading Execution from #1 Best down to lowest (Zero-Cost 0 Rs strictly enforced)
        for score_item in ranked_queue:
            spec = score_item.model
            provider_id = spec.provider_id
            adapter = self.adapters.get(provider_id)

            # Skip models without an adapter
            if not adapter:
                continue

            # Zero-Cost Guard: If model costs > 0 Rs, NEVER continue with it! Shift to free model
            if not guard.is_zero_cost(spec.model_id, provider_id):
                logger.info("🛡️ Zero-Cost Guard: Bypassing paid model %s (%s) > 0 Rs", spec.model_id, provider_id)
                continue

            # If model is unavailable (no API key and not running locally), skip
            if not adapter.is_available():
                continue

            # If in rate limit / error cooldown, skip unless we're deep in fallback
            if self.health_tracker.is_in_cooldown(spec.model_id) and fallback_count < 3:
                continue

            attempted.append(f"{spec.model_id} (Rank #{score_item.global_rank})")
            if on_stage_change and fallback_used:
                on_stage_change(f"🔄 Trying Rank #{score_item.global_rank}: {spec.display_name} ({spec.provider_id.upper()} • 0 Rs)...")

            start_t = time.time()
            try:
                resp = adapter.execute(
                    model_id=spec.model_id,
                    prompt=prompt,
                    history=history,
                    system_prompt=system_prompt,
                    on_chunk=on_chunk,
                    **kwargs
                )
                latency_ms = round((time.time() - start_t) * 1000.0, 1)

                # Validate response
                is_valid, fail_reason = self.validator.validate(resp, task=task)

                if resp.success and is_valid:
                    # Success!
                    self.health_tracker.record_success(spec.model_id, provider_id, latency_ms)

                    telemetry = (
                        f"Model: Auto | Provider: Auto | Mode: Balanced | Cost: 0 Rs (100% Free Guaranteed)\n"
                        f"Current Model: {spec.display_name} | Provider: {provider_id.title()} | "
                        f"Rank: #{score_item.global_rank} / ALL MODELS | Score: {score_item.overall_score} | "
                        f"Fallback Used: {'Yes (' + str(fallback_count) + ' hops)' if fallback_used else 'No'}"
                    )

                    resp.metadata["routing_telemetry"] = {
                        "model_id": spec.model_id,
                        "display_name": spec.display_name,
                        "provider_id": provider_id,
                        "global_rank": score_item.global_rank,
                        "score": score_item.overall_score,
                        "fallback_used": fallback_used,
                        "fallback_count": fallback_count,
                        "attempted_models": attempted,
                        "task_type": task.value,
                        "telemetry_badge": telemetry,
                    }

                    # Log to SQLite
                    get_db().log_routing_decision({
                        "task_type": task.value,
                        "prompt_snippet": prompt[:100],
                        "selected_model_id": spec.model_id,
                        "provider_id": provider_id,
                        "global_rank": score_item.global_rank,
                        "dynamic_score": score_item.overall_score,
                        "fallback_used": fallback_used,
                        "fallback_count": fallback_count,
                        "attempted_models": attempted,
                        "success": True,
                        "latency_ms": latency_ms,
                        "validation_passed": True
                    })

                    if on_stage_change:
                        on_stage_change(f"✅ Generated via Rank #{score_item.global_rank} ({spec.display_name}) in {latency_ms:.0f}ms")

                    return RoutingResult(
                        response=resp,
                        selected_model=spec,
                        global_rank=score_item.global_rank,
                        score=score_item.overall_score,
                        fallback_used=fallback_used,
                        fallback_count=fallback_count,
                        attempted_models=attempted,
                        task_type=task.value,
                        validation_passed=True,
                        telemetry_badge=telemetry
                    )
                else:
                    # Model execution or validation failed
                    err_msg = fail_reason or resp.error_msg or "Validation rejected output."
                    logger.warning("Model #%d (%s) failed: %s", score_item.global_rank, spec.model_id, err_msg)
                    self.health_tracker.record_failure(spec.model_id, provider_id, err_msg)
                    fallback_used = True
                    fallback_count += 1
            except Exception as ex:
                logger.error("Exception invoking model %s: %s", spec.model_id, ex)
                self.health_tracker.record_failure(spec.model_id, provider_id, str(ex))
                fallback_used = True
                fallback_count += 1

        # Step 4: If all configured models failed, trigger local Ollama fallback
        if on_stage_change:
            on_stage_change("⚡ Cascading to Offline Local Ollama Fallback...")

        ollama_adapter = self.adapters.get("ollama")
        if ollama_adapter and ollama_adapter.is_available():
            try:
                local_model = "qwen2.5-coder:7b" if task == TaskType.CODING else "qwen3:8b"
                resp = ollama_adapter.execute(local_model, prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, **kwargs)
                if resp.success:
                    telemetry = (
                        f"Model: Auto | Provider: Auto | Mode: Balanced\n"
                        f"Current Model: Local Ollama ({local_model}) | Provider: Ollama | "
                        f"Rank: #Offline Fallback | Score: 7.5 | Fallback Used: Yes ({fallback_count} hops)"
                    )
                    resp.metadata["routing_telemetry"] = {"telemetry_badge": telemetry}
                    return RoutingResult(
                        response=resp,
                        selected_model=ModelSpec(model_id=local_model, display_name=f"Ollama {local_model}", provider_id="ollama"),
                        global_rank=999,
                        score=7.5,
                        fallback_used=True,
                        fallback_count=fallback_count,
                        attempted_models=attempted,
                        task_type=task.value,
                        validation_passed=True,
                        telemetry_badge=telemetry
                    )
            except Exception as e:
                logger.warning("Local Ollama fallback failed: %s", e)

        # Step 5: Final safety response
        return self._emergency_fallback(prompt, task, f"All {len(attempted)} ranked models were unreachable.")

    def _emergency_fallback(self, prompt: str, task: TaskType, reason: str) -> RoutingResult:
        """Returns safe, helpful built-in response when zero cloud or local providers respond."""
        from engine.providers.local_facts_provider import LocalFactsProvider
        l_prov = LocalFactsProvider()
        resp = l_prov.generate(prompt)
        
        telemetry = (
            f"Model: Auto | Provider: Auto | Mode: Balanced\n"
            f"Current Model: Sage Built-in Assistant | Provider: Local | "
            f"Rank: #Offline Fallback | Score: 6.0 | Fallback Used: Yes"
        )
        resp.metadata["routing_telemetry"] = {"telemetry_badge": telemetry}
        spec = ModelSpec(model_id="sage-offline-facts", display_name="Sage Built-in Assistant", provider_id="local_facts")
        return RoutingResult(
            response=resp,
            selected_model=spec,
            global_rank=999,
            score=6.0,
            fallback_used=True,
            fallback_count=1,
            attempted_models=["local_facts"],
            task_type=task.value,
            validation_passed=True,
            telemetry_badge=telemetry
        )


# Global singleton helper
_auto_router_instance: Optional[AutoRouter] = None

def get_auto_router() -> AutoRouter:
    global _auto_router_instance
    if _auto_router_instance is None:
        _auto_router_instance = AutoRouter()
    return _auto_router_instance
