"""
Health and Cooldown Tracker for Sage AI Auto Router.
Implements circuit breaking, cooldown management, and health scoring.
"""
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from database.db_manager import get_db
from .models import ModelStatus
from .adapters import ALL_ADAPTERS

logger = logging.getLogger(__name__)


class HealthTracker:
    """Monitors real-time health, circuit-breaker cooldowns, and error rates per model."""

    COOLDOWN_SECONDS_DEFAULT: float = 60.0  # 60s cooldown on 429 or 500 errors

    def __init__(self):
        self._memory_health: Dict[str, Dict[str, Any]] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            db = get_db()
            db_health = db.get_model_health_all()
            for mid, rec in db_health.items():
                self._memory_health[mid] = rec
        except Exception as e:
            logger.warning("Could not pre-load model health: %s", e)

    def is_in_cooldown(self, model_id: str) -> bool:
        """Returns True if the model is currently under a rate-limit or error cooldown."""
        rec = self._memory_health.get(model_id)
        if not rec:
            return False
        cd_until = rec.get("cooldown_until")
        if not cd_until:
            return False
        try:
            exp_time = datetime.fromisoformat(cd_until)
            return datetime.now() < exp_time
        except Exception:
            return False

    def get_status(self, model_id: str, provider_id: str) -> ModelStatus:
        """Determines the real-time operational status of a model."""
        # 1. Check cooldown state
        if self.is_in_cooldown(model_id):
            return ModelStatus.RATE_LIMITED

        # 2. Check provider availability (API key or local running daemon)
        adapter = ALL_ADAPTERS.get(provider_id)
        if not adapter or not adapter.is_available():
            return ModelStatus.UNAVAILABLE

        return ModelStatus.AVAILABLE

    def get_health_score(self, model_id: str, provider_id: str) -> float:
        """
        Calculates health factor score between 0.0 and 10.0 (5% weight in dynamic formula).
        Penalizes models in cooldown or with repeated failures.
        """
        adapter = ALL_ADAPTERS.get(provider_id)
        if not adapter or not adapter.is_available():
            return 0.0

        if self.is_in_cooldown(model_id):
            return 1.5  # Heavy penalty during cooldown

        rec = self._memory_health.get(model_id)
        if not rec:
            return 9.8  # Clean baseline

        consec_fails = rec.get("consecutive_failures", 0)
        tot = rec.get("total_requests", 0)
        succ = rec.get("successful_requests", 0)

        if tot == 0:
            return 9.8

        succ_rate = succ / max(1, tot)
        score = (succ_rate * 8.0) + 2.0 - (consec_fails * 1.5)
        return max(1.0, min(10.0, score))

    def record_success(self, model_id: str, provider_id: str, latency_ms: float):
        """Records successful execution, resetting consecutive failures and updating latency."""
        now = datetime.now().isoformat()
        rec = self._memory_health.get(model_id, {
            "model_id": model_id,
            "provider_id": provider_id,
            "status": "available",
            "consecutive_failures": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "avg_latency_ms": latency_ms,
            "cooldown_until": None,
            "last_error_code": None,
            "last_error_msg": None,
        })

        rec["total_requests"] += 1
        rec["successful_requests"] += 1
        rec["consecutive_failures"] = 0
        rec["status"] = "available"
        rec["cooldown_until"] = None
        # Exponential moving average for latency
        prev_lat = rec.get("avg_latency_ms", latency_ms)
        rec["avg_latency_ms"] = round((prev_lat * 0.7) + (latency_ms * 0.3), 1)

        self._memory_health[model_id] = rec
        try:
            get_db().upsert_model_health(rec)
        except Exception:
            pass

    def record_failure(self, model_id: str, provider_id: str, error_msg: str, error_code: Optional[str] = None):
        """Records an execution error and activates cooldown for rate limits or server errors."""
        now = datetime.now()
        rec = self._memory_health.get(model_id, {
            "model_id": model_id,
            "provider_id": provider_id,
            "status": "available",
            "consecutive_failures": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "avg_latency_ms": 0.0,
            "cooldown_until": None,
            "last_error_code": None,
            "last_error_msg": None,
        })

        rec["total_requests"] += 1
        rec["consecutive_failures"] += 1
        rec["last_error_msg"] = error_msg[:200]
        rec["last_error_code"] = error_code or "ERROR"

        # Determine cooldown duration (exponential backoff up to 300s)
        err_lower = error_msg.lower()
        is_rate_limit = "429" in err_lower or "rate" in err_lower or "quota" in err_lower
        is_server_err = any(c in err_lower for c in ("500", "502", "503", "timeout", "timed out"))

        if is_rate_limit:
            backoff = min(300.0, self.COOLDOWN_SECONDS_DEFAULT * (rec["consecutive_failures"]))
            rec["cooldown_until"] = (now + timedelta(seconds=backoff)).isoformat()
            rec["status"] = "rate_limited"
        elif is_server_err:
            backoff = min(180.0, 30.0 * (rec["consecutive_failures"]))
            rec["cooldown_until"] = (now + timedelta(seconds=backoff)).isoformat()
            rec["status"] = "rate_limited"
        else:
            rec["status"] = "degraded"

        self._memory_health[model_id] = rec
        try:
            get_db().upsert_model_health(rec)
        except Exception:
            pass

    def record_rate_limit(self, model_id: str, provider_id: str, cooldown_seconds: float = 60.0):
        """Manually triggers a rate-limit cooldown for a model."""
        now = datetime.now()
        rec = self._memory_health.get(model_id, {
            "model_id": model_id,
            "provider_id": provider_id,
            "status": "rate_limited",
            "consecutive_failures": 1,
            "total_requests": 1,
            "successful_requests": 0,
            "avg_latency_ms": 0.0,
            "cooldown_until": (now + timedelta(seconds=cooldown_seconds)).isoformat(),
            "last_error_code": "429",
            "last_error_msg": "Rate limit exceeded (HTTP 429)",
        })
        rec["status"] = "rate_limited"
        rec["cooldown_until"] = (now + timedelta(seconds=cooldown_seconds)).isoformat()
        self._memory_health[model_id] = rec
        try:
            get_db().upsert_model_health(rec)
        except Exception:
            pass
