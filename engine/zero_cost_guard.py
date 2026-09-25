"""
Zero-Cost Guard Architecture for Sage AI.
Intercepts EVERY AI model request across all execution paths (chat, auto router,
coding IDE, specialized agents, live-thinking agents).

Core Rule:
If any requested or candidate model costs > 0 Rs (paid model, USD/INR > 0, is_free is False),
the request MUST NOT continue with that paid model.
The architecture automatically intercepts and shifts/diverts the request to a 100% Free
model (<= 0 Rs) and continues cascading through free models until the request completes.
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field

from config import (
    DEFAULT_MODELS,
    INTENT_CODING,
    INTENT_GENERAL_CHAT,
    INTENT_IMAGE,
    INTENT_WEB_SEARCH,
    INTENT_GITHUB,
    INTENT_LOCAL_FACTS,
)

logger = logging.getLogger(__name__)

# Currency conversion reference: 1 USD = 85.0 INR (Rs)
DEFAULT_USD_TO_INR_RATE = float(os.getenv("USD_TO_INR_RATE", "85.0"))
MAX_ALLOWED_MODEL_COST_RS = float(os.getenv("MAX_ALLOWED_MODEL_COST_RS", "0.0"))


@dataclass
class ZeroCostCheckResult:
    """Result of evaluating a model's cost against the Zero-Cost Guard policy."""
    model_name: str
    provider_id: str
    is_zero_cost: bool           # True if cost <= 0.0 Rs (100% Free / Free Tier)
    cost_in_rs: float            # Estimated cost per 1M tokens in INR (Rs)
    cost_in_usd: float           # Cost in USD per 1M tokens
    tier_type: str               # "100% Free Offline", "Free Tier", "Paid (> 0 Rs)"
    reason: str                  # Explanation of cost evaluation
    shifted_to: Optional[str] = None       # Free model shifted to if originally > 0 Rs
    shifted_provider: Optional[str] = None # Provider of shifted free model


class ZeroCostGuard:
    """
    Zero-Cost Guard Architecture:
    Enforces a strict 0 Rs limit across all AI model requests in Sage AI.
    """

    _instance: Optional["ZeroCostGuard"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ZeroCostGuard, cls).__new__(cls)
            cls._instance._init_guard()
        return cls._instance

    def _init_guard(self):
        self.usd_to_inr = DEFAULT_USD_TO_INR_RATE
        self.max_allowed_rs = MAX_ALLOWED_MODEL_COST_RS
        self._enabled = True

        # Curated ordered waterfall chains of 100% FREE (0 Rs) models per task type
        self.FREE_FALLBACK_CHAINS = {
            "coding": [
                ("qwen/qwen-2.5-coder-32b-instruct:free", "openrouter", "OpenRouter Free Tier (0 Rs)"),
                ("gemini-2.0-flash", "gemini", "Google Gemini Free Tier (0 Rs)"),
                ("deepseek-r1-distill-llama-70b", "groq", "Groq Free Tier (0 Rs)"),
                ("deepseek/deepseek-v4-flash-0731:free", "openrouter", "OpenRouter Free Tier (0 Rs)"),
                ("llama-3.3-70b-versatile", "groq", "Groq Free Tier (0 Rs)"),
                ("codestral-latest", "mistral", "Mistral Free Tier (0 Rs)"),
                ("meta-llama/llama-3.3-70b-instruct:free", "openrouter", "OpenRouter Free Tier (0 Rs)"),
                ("qwen2.5-coder:7b", "ollama", "100% Free Offline Ollama (0 Rs)"),
                ("sage-offline-facts", "local_facts", "Sage Local Assistant (0 Rs)"),
            ],
            "reasoning": [
                ("deepseek/deepseek-r1:free", "openrouter", "OpenRouter DeepSeek R1 Free (0 Rs)"),
                ("deepseek-r1-distill-llama-70b", "groq", "Groq DeepSeek R1 Distill Free (0 Rs)"),
                ("gemini-2.0-flash", "gemini", "Google Gemini 2.0 Flash Free Tier (0 Rs)"),
                ("qwen/qwen-2.5-coder-32b-instruct:free", "openrouter", "OpenRouter Qwen 32B Free (0 Rs)"),
                ("deepseek-r1:8b", "ollama", "100% Free Offline Ollama R1 (0 Rs)"),
                ("sage-offline-facts", "local_facts", "Sage Local Assistant (0 Rs)"),
            ],
            "general_chat": [
                ("llama-3.3-70b-versatile", "groq", "Groq Llama 3.3 70B Free (0 Rs)"),
                ("gemini-1.5-flash", "gemini", "Google Gemini 1.5 Flash Free Tier (0 Rs)"),
                ("gemini-2.0-flash", "gemini", "Google Gemini 2.0 Flash Free Tier (0 Rs)"),
                ("llama-3.3-70b", "cerebras", "Cerebras Wafer-Scale Free Tier (0 Rs)"),
                ("deepseek/deepseek-chat:free", "openrouter", "OpenRouter DeepSeek Chat Free (0 Rs)"),
                ("@cf/meta/llama-3.3-70b-instruct", "cloudflare", "Cloudflare Workers AI Free Tier (0 Rs)"),
                ("meta/llama-3.1-70b-instruct", "nvidia", "NVIDIA NIM Free Allowance (0 Rs)"),
                ("qwen3:8b", "ollama", "100% Free Offline Ollama (0 Rs)"),
                ("sage-offline-facts", "local_facts", "Sage Local Assistant (0 Rs)"),
            ],
            "vision": [
                ("gemini-1.5-flash", "gemini", "Google Gemini 1.5 Flash Multimodal Free Tier (0 Rs)"),
                ("gemini-2.0-flash", "gemini", "Google Gemini 2.0 Flash Multimodal Free Tier (0 Rs)"),
                ("meta/llama-3.2-11b-vision-instruct", "nvidia", "NVIDIA NIM Vision Free Allowance (0 Rs)"),
                ("llama-3.2-11b-vision-preview", "groq", "Groq Vision Free Preview (0 Rs)"),
                ("sage-offline-facts", "local_facts", "Sage Local Assistant (0 Rs)"),
            ],
            "image_gen": [
                ("black-forest-labs/FLUX.1-schnell", "image", "Black Forest FLUX.1 Free Allowance (0 Rs)"),
                ("local_canvas", "image", "Local Canvas Renderer (0 Rs)"),
            ],
        }

        # Known strictly paid models that cost > 0 Rs
        self.KNOWN_PAID_PATTERNS = [
            "unbiased/pareto",
            "union-alpha",
            "pareto 26.9",
            "pareto-code",
            "claude-3.5",
            "claude-3.7",
            "claude-3-opus",
            "gpt-4",
            "gpt-4o",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
            "o3-mini",
        ]

    @property
    def is_enabled(self) -> bool:
        """Checks if Zero-Cost Guard is active (enabled by default)."""
        try:
            from database.db_manager import get_db
            val = get_db().get_setting("zero_cost_guard_enabled", "true")
            return str(val).lower() in ("true", "1", "yes")
        except Exception:
            return self._enabled

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        try:
            from database.db_manager import get_db
            get_db().save_setting("zero_cost_guard_enabled", "true" if enabled else "false")
        except Exception as e:
            logger.warning("Could not persist zero_cost_guard_enabled: %s", e)

    def evaluate_model_cost(
        self,
        model_name: str,
        provider_id: Optional[str] = None
    ) -> ZeroCostCheckResult:
        """
        Evaluates whether a model costs > 0 Rs or is 100% Free / Free Tier (<= 0 Rs).
        Returns a complete ZeroCostCheckResult with cost in Rs and tier classification.
        """
        m_raw = str(model_name or "").strip()
        m_lower = m_raw.lower()
        p_raw = str(provider_id or "").strip().lower()

        # 1. 100% Free Offline Providers & Built-in Engine
        if p_raw in ("ollama", "local_facts", "local_canvas") or "ollama" in m_lower:
            return ZeroCostCheckResult(
                model_name=m_raw,
                provider_id=p_raw or "ollama",
                is_zero_cost=True,
                cost_in_rs=0.0,
                cost_in_usd=0.0,
                tier_type="100% Free Offline",
                reason="Local offline execution: 100% free with unlimited local compute (0 Rs)"
            )

        # 2. Check for explicit known paid models (> 0 Rs)
        for pattern in self.KNOWN_PAID_PATTERNS:
            if pattern in m_lower:
                cost_usd = 2.5 if ("pareto" in pattern or "union" in pattern) else 3.0
                cost_rs = round(cost_usd * self.usd_to_inr, 2)
                return ZeroCostCheckResult(
                    model_name=m_raw,
                    provider_id=p_raw or "openrouter",
                    is_zero_cost=False,
                    cost_in_rs=cost_rs,
                    cost_in_usd=cost_usd,
                    tier_type="Paid (> 0 Rs)",
                    reason=f"Model '{m_raw}' is a paid frontier model costing ~${cost_usd:.2f} USD ({cost_rs:.1f} Rs) / 1M tokens (> 0 Rs)"
                )

        # 3. Check OpenRouter models: only ':free' suffix or zero pricing is free
        if p_raw == "openrouter" or "/" in m_raw:
            if m_lower.endswith(":free"):
                return ZeroCostCheckResult(
                    model_name=m_raw,
                    provider_id="openrouter",
                    is_zero_cost=True,
                    cost_in_rs=0.0,
                    cost_in_usd=0.0,
                    tier_type="Free Tier",
                    reason="OpenRouter verified :free tier model (0 Rs)"
                )
            # If on openrouter and does NOT end with :free, check ModelRegistry or known specs
            try:
                from engine.auto_router.registry import ModelRegistry
                registry = ModelRegistry()
                spec = registry.get_model(m_raw)
                if spec:
                    if not spec.is_free or spec.cost_per_m_tokens > 0.0:
                        cost_usd = spec.cost_per_m_tokens or 1.5
                        cost_rs = round(cost_usd * self.usd_to_inr, 2)
                        return ZeroCostCheckResult(
                            model_name=m_raw,
                            provider_id="openrouter",
                            is_zero_cost=False,
                            cost_in_rs=cost_rs,
                            cost_in_usd=cost_usd,
                            tier_type="Paid (> 0 Rs)",
                            reason=f"Registered model '{m_raw}' requires paid credits (~${cost_usd:.2f} USD = {cost_rs:.1f} Rs / 1M tokens)"
                        )
            except Exception:
                pass

            # Known OpenRouter non-free models if without :free suffix
            if p_raw == "openrouter" and not m_lower.endswith(":free") and not any(k in m_lower for k in ("auto", "search", "facts")):
                cost_usd = 1.0
                cost_rs = round(cost_usd * self.usd_to_inr, 2)
                return ZeroCostCheckResult(
                    model_name=m_raw,
                    provider_id="openrouter",
                    is_zero_cost=False,
                    cost_in_rs=cost_rs,
                    cost_in_usd=cost_usd,
                    tier_type="Paid (> 0 Rs)",
                    reason=f"OpenRouter model '{m_raw}' lacks ':free' tier tag and requires credits ({cost_rs:.1f} Rs)"
                )

        # 4. Check Universal Model Registry
        try:
            from engine.auto_router.registry import ModelRegistry
            registry = ModelRegistry()
            spec = registry.get_model(m_raw)
            if spec:
                if not spec.is_free or spec.cost_per_m_tokens > 0.0:
                    cost_usd = spec.cost_per_m_tokens
                    cost_rs = round(cost_usd * self.usd_to_inr, 2)
                    return ZeroCostCheckResult(
                        model_name=m_raw,
                        provider_id=spec.provider_id,
                        is_zero_cost=False,
                        cost_in_rs=cost_rs,
                        cost_in_usd=cost_usd,
                        tier_type="Paid (> 0 Rs)",
                        reason=f"Model '{m_raw}' costs ${cost_usd:.2f} USD ({cost_rs:.1f} Rs) in registry (> 0 Rs)"
                    )
                else:
                    return ZeroCostCheckResult(
                        model_name=m_raw,
                        provider_id=spec.provider_id,
                        is_zero_cost=True,
                        cost_in_rs=0.0,
                        cost_in_usd=0.0,
                        tier_type="Free Tier",
                        reason=f"Model '{spec.display_name}' has verified 0 Rs cost in registry"
                    )
        except Exception:
            pass

        # 5. Check discovered_models in Database
        try:
            from database.db_manager import get_db
            disc_models = get_db().get_discovered_models(provider_id=p_raw or None, free_only=False)
            for dm in disc_models:
                if dm.get("model_name", "").lower() == m_lower or dm.get("display_name", "").lower() == m_lower:
                    is_free_val = bool(dm.get("is_free", 1))
                    if not is_free_val:
                        return ZeroCostCheckResult(
                            model_name=m_raw,
                            provider_id=dm.get("provider_id", p_raw),
                            is_zero_cost=False,
                            cost_in_rs=85.0,
                            cost_in_usd=1.0,
                            tier_type="Paid (> 0 Rs)",
                            reason=f"Database discovered models registers '{m_raw}' as Paid (> 0 Rs)"
                        )
                    else:
                        return ZeroCostCheckResult(
                            model_name=m_raw,
                            provider_id=dm.get("provider_id", p_raw),
                            is_zero_cost=True,
                            cost_in_rs=0.0,
                            cost_in_usd=0.0,
                            tier_type=dm.get("tier_type") or "Free Tier",
                            reason=f"Database confirms '{m_raw}' is Free Tier (0 Rs)"
                        )
        except Exception:
            pass

        # 6. Verified Free Cloud Providers (Groq, Cerebras, Cloudflare, Gemini Free Tier, NVIDIA Free Allowance)
        if p_raw in ("groq", "cerebras", "cloudflare", "gemini", "nvidia", "image"):
            return ZeroCostCheckResult(
                model_name=m_raw,
                provider_id=p_raw,
                is_zero_cost=True,
                cost_in_rs=0.0,
                cost_in_usd=0.0,
                tier_type="Free Tier",
                reason=f"Provider '{p_raw.title()}' operates on verified 100% Free Tier (0 Rs)"
            )

        # Default: if Auto or Unknown and not marked paid, treat as 0 Rs free
        return ZeroCostCheckResult(
            model_name=m_raw,
            provider_id=p_raw or "auto",
            is_zero_cost=True,
            cost_in_rs=0.0,
            cost_in_usd=0.0,
            tier_type="Free Tier",
            reason="Model operating within 0 Rs Free Tier policy"
        )

    def is_zero_cost(self, model_name: str, provider_id: Optional[str] = None) -> bool:
        """Returns True if the model costs 0 Rs / is free."""
        return self.evaluate_model_cost(model_name, provider_id).is_zero_cost

    def get_free_waterfall_queue(
        self,
        task_type: str = "general_chat",
        excluded_models: Optional[List[str]] = None
    ) -> List[Tuple[str, str, str]]:
        """
        Returns an ordered list of (model_id, provider_id, description) for 100% Free models (0 Rs).
        """
        t = task_type.lower()
        if "cod" in t or "script" in t or "debug" in t or "python" in t or "program" in t:
            chain = self.FREE_FALLBACK_CHAINS["coding"]
        elif "reason" in t or "math" in t or "logic" in t:
            chain = self.FREE_FALLBACK_CHAINS["reasoning"]
        elif "vision" in t or "image inspection" in t:
            chain = self.FREE_FALLBACK_CHAINS["vision"]
        elif "image" in t:
            chain = self.FREE_FALLBACK_CHAINS["image_gen"]
        else:
            chain = self.FREE_FALLBACK_CHAINS["general_chat"]

        excluded = set(m.lower() for m in (excluded_models or []))
        result = []
        for m_id, p_id, desc in chain:
            if m_id.lower() not in excluded:
                result.append((m_id, p_id, desc))
        return result

    def resolve_free_model(
        self,
        requested_model: str,
        task_type: str = "general_chat",
        excluded_models: Optional[List[str]] = None
    ) -> Tuple[str, str, str]:
        """
        Finds the best 100% Free (0 Rs) model to replace a paid model.
        Returns: (free_model_id, free_provider_id, shift_reason)
        """
        m_lower = requested_model.lower()
        t = task_type.lower()

        # If it is a coding request or coder model
        is_coding = any(k in m_lower for k in ("coder", "codestral", "pareto", "union", "code")) or ("cod" in t)
        is_reasoning = any(k in m_lower for k in ("r1", "reason", "math")) or ("reason" in t)

        queue = self.get_free_waterfall_queue(
            task_type="coding" if is_coding else ("reasoning" if is_reasoning else "general_chat"),
            excluded_models=excluded_models
        )

        # Check provider availability if possible
        try:
            from engine.auto_router.adapters import ALL_ADAPTERS
            for m_id, p_id, desc in queue:
                adapter = ALL_ADAPTERS.get(p_id)
                if adapter and adapter.is_available():
                    return m_id, p_id, f"Shifted to top available free model '{m_id}' on {p_id.title()} (0 Rs)"
        except Exception:
            pass

        # Return first candidate from free waterfall
        if queue:
            top_m, top_p, desc = queue[0]
            return top_m, top_p, f"Shifted to verified free model '{top_m}' on {top_p.title()} (0 Rs)"

        # Absolute safety fallback: offline facts
        return "sage-offline-facts", "local_facts", "Shifted to Sage Local Assistant (100% Free Offline 0 Rs)"

    def scan_and_resolve_free_model(
        self,
        requested_model: str,
        provider_id: Optional[str] = None,
        task_type: str = "general_chat",
        excluded_models: Optional[List[str]] = None
    ) -> Tuple[str, str, str]:
        """
        Pre-request cost scanning:
        Always scans before sending a request to any model.
        Checks if candidate model is 100% Free (<= 0 Rs).
        If not free (cost > 0 Rs, or paid model), shifts through the free waterfall queue
        until a verified 0 Rs free model is found.
        Returns: (effective_model, effective_provider, reason)
        """
        cost_eval = self.evaluate_model_cost(requested_model, provider_id)
        if cost_eval.is_zero_cost:
            return requested_model, provider_id or cost_eval.provider_id, "Model verified 100% Free (0 Rs)"

        # Candidate is not free: scan free waterfall queue
        free_m, free_p, reason = self.resolve_free_model(
            requested_model=requested_model,
            task_type=task_type,
            excluded_models=excluded_models
        )
        return free_m, free_p, reason

    def guard_request(
        self,
        requested_model: str,
        provider_id: Optional[str] = None,
        task_type: str = "general_chat",
        on_stage_change: Optional[Callable[[str], None]] = None,
        excluded_models: Optional[List[str]] = None
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """
        Intercepts and checks an AI model request against the 0 Rs rule.

        Returns:
            (was_shifted: bool,
             effective_model: str,
             effective_provider: str,
             guard_metadata: Dict[str, Any])
        """
        if not self.is_enabled:
            return False, requested_model, provider_id or "auto", {"guard_active": False}

        cost_eval = self.evaluate_model_cost(requested_model, provider_id)

        # 1. If model is already 0 Rs / Free, allow it directly!
        if cost_eval.is_zero_cost:
            return False, requested_model, provider_id or cost_eval.provider_id, {
                "guard_active": True,
                "was_shifted": False,
                "cost_in_rs": 0.0,
                "tier_type": cost_eval.tier_type,
                "original_model": requested_model,
                "effective_model": requested_model,
                "policy": "ZERO_COST_ENFORCED (0 Rs / Free Tier)"
            }

        # 2. Model costs > 0 Rs! INTERCEPT AND DO NOT PROCEED WITH PAID MODEL!
        logger.warning(
            "🛡️ Zero-Cost Guard Intercepted: Model '%s' costs %s Rs (> 0 Rs). Shifting to 100%% Free model...",
            requested_model, cost_eval.cost_in_rs
        )

        free_model, free_prov, shift_reason = self.resolve_free_model(
            requested_model=requested_model,
            task_type=task_type,
            excluded_models=excluded_models
        )

        stage_msg = (
            f"🛡️ Zero-Cost Guard: Intercepted paid model '{requested_model}' "
            f"(costs {cost_eval.cost_in_rs:.1f} Rs). "
            f"Automatically shifted to 100% Free model '{free_model}' ({free_prov.title()} • 0 Rs)."
        )

        if on_stage_change:
            try:
                on_stage_change(stage_msg)
            except Exception as e:
                logger.debug("Stage callback error in ZeroCostGuard: %s", e)

        # Log zero-cost shift event to database
        self._log_shift_event(
            original_model=requested_model,
            original_provider=provider_id or cost_eval.provider_id,
            shifted_model=free_model,
            shifted_provider=free_prov,
            cost_saved_rs=cost_eval.cost_in_rs,
            reason=cost_eval.reason
        )

        guard_meta = {
            "guard_active": True,
            "was_shifted": True,
            "original_model": requested_model,
            "intercepted_cost_rs": cost_eval.cost_in_rs,
            "effective_model": free_model,
            "effective_provider": free_prov,
            "cost_in_rs": 0.0,
            "cost_saved_rs": cost_eval.cost_in_rs,
            "shift_reason": shift_reason,
            "policy": "ZERO_COST_ENFORCED (Intercepted > 0 Rs -> Shifted to 0 Rs Free Model)"
        }

        return True, free_model, free_prov, guard_meta

    def _log_shift_event(
        self,
        original_model: str,
        original_provider: str,
        shifted_model: str,
        shifted_provider: str,
        cost_saved_rs: float,
        reason: str
    ):
        """Records the intercepted zero-cost shift to database audit log."""
        try:
            from database.db_manager import get_db
            db = get_db()
            db.log_zero_cost_shift({
                "original_model": original_model,
                "original_provider": original_provider,
                "shifted_model": shifted_model,
                "shifted_provider": shifted_provider,
                "cost_saved_rs": cost_saved_rs,
                "reason": reason
            })
        except Exception as e:
            logger.debug("Failed to record zero-cost shift event: %s", e)


# Global singleton instance accessor
_zero_cost_guard_instance: Optional[ZeroCostGuard] = None

def get_zero_cost_guard() -> ZeroCostGuard:
    global _zero_cost_guard_instance
    if _zero_cost_guard_instance is None:
        _zero_cost_guard_instance = ZeroCostGuard()
    return _zero_cost_guard_instance
