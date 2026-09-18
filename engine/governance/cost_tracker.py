"""
Usage & Cost Tracker for Sage Multi-Agentic AI Architecture.
Monitors token consumption, latency benchmarks, and cost governance per agent.
"""
import logging
from typing import Dict, Any, Optional

from database.db_manager import get_db

logger = logging.getLogger(__name__)


class CostTracker:
    """Monitors token usage, latency, and model metrics across all agents."""

    def __init__(self):
        self._db = get_db()

    def record_usage(
        self,
        agent_name: str,
        provider_id: str,
        model_name: str,
        prompt_text: str,
        completion_text: str,
        latency_ms: float = 0.0,
        task_id: Optional[str] = None,
        success: bool = True
    ) -> int:
        """Estimates and logs token usage for an agent LLM call."""
        prompt_tokens = max(1, int(len(prompt_text.split()) * 1.35))
        completion_tokens = max(1, int(len(completion_text.split()) * 1.35)) if completion_text else 0

        try:
            return self._db.log_model_usage(
                provider_id=provider_id,
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                session_id=task_id,
                success=success
            )
        except Exception as e:
            logger.debug("Failed to record usage in CostTracker: %s", e)
            return -1

    def get_summary(self) -> Dict[str, Any]:
        """Retrieves global usage summary from database."""
        try:
            return self._db.get_model_usage_summary()
        except Exception:
            return {}


_cost_tracker_instance: Optional[CostTracker] = None

def get_cost_tracker() -> CostTracker:
    global _cost_tracker_instance
    if _cost_tracker_instance is None:
        _cost_tracker_instance = CostTracker()
    return _cost_tracker_instance
