"""
Model Scanner and Quota Discovery Service for Sage AI.
Discovers live available models for configured API keys (OpenRouter, Groq, NVIDIA, Gemini, Ollama)
and tracks remaining quota/credit allowances.
"""
import time
import logging
import threading
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from database.db_manager import get_db
from config import DEFAULT_MODELS, PROVIDER_PRESET_MODELS

logger = logging.getLogger(__name__)


class ModelScanner:
    """Discovers authorized models and quota limits across cloud and local providers."""

    _scan_cache: Dict[str, Tuple[float, Any]] = {}
    _last_trace_diffs: Dict[str, Dict[str, Any]] = {}
    _cache_lock = threading.Lock()
    CACHE_TTL: float = 300.0  # 5-minute memory cache to prevent blocking network scans

    @classmethod
    def trace_provider_models(
        cls,
        provider_id: str,
        current_models: List[Dict[str, Any]],
        sync_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Diffs live provider models against previously recorded models in SQLite.
        Detects:
          - Newly added free models ('added_free')
          - Newly added paid models ('added_paid')
          - Removed or decommissioned models ('removed')
          - Parameter, context, or free/paid status changes ('changed')
        Persists all audit events into model_audit_log and updates discovered_models.
        """
        db = get_db()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        existing_list = db.get_discovered_models(provider_id=provider_id, free_only=False)
        existing_map = {m["model_name"]: m for m in existing_list if m.get("model_name")}
        current_map = {m["model_name"]: m for m in current_models if m.get("model_name")}

        events: List[Dict[str, Any]] = []
        added_free: List[Dict[str, Any]] = []
        added_paid: List[Dict[str, Any]] = []
        removed: List[Dict[str, Any]] = []
        changed: List[Dict[str, Any]] = []

        is_initial_baseline = len(existing_map) == 0

        # 1. Detect Additions
        for m_name, m_data in current_map.items():
            if m_name not in existing_map:
                is_free = bool(m_data.get("is_free", 0))
                ev_type = "added_free" if is_free else "added_paid"
                disp = m_data.get("display_name") or m_name
                ctx = m_data.get("context_length", 0)
                summary = (
                    f"New FREE model discovered on {provider_id.title()}: {disp}"
                    if is_free else
                    f"New model available on {provider_id.title()}: {disp}"
                )
                ev = {
                    "timestamp": now,
                    "provider_id": provider_id,
                    "event_type": ev_type,
                    "model_name": m_name,
                    "display_name": disp,
                    "is_free": 1 if is_free else 0,
                    "change_summary": summary,
                    "details": {"context_length": ctx, "is_baseline": is_initial_baseline}
                }
                events.append(ev)
                if is_free:
                    added_free.append(ev)
                else:
                    added_paid.append(ev)

        # 2. Detect Removals (only if we had existing models recorded)
        if not is_initial_baseline:
            for m_name, m_data in existing_map.items():
                if m_name not in current_map:
                    disp = m_data.get("display_name") or m_name
                    was_free = bool(m_data.get("is_free", 0))
                    summary = f"Model removed / discontinued on {provider_id.title()}: {disp}"
                    ev = {
                        "timestamp": now,
                        "provider_id": provider_id,
                        "event_type": "removed",
                        "model_name": m_name,
                        "display_name": disp,
                        "is_free": 1 if was_free else 0,
                        "change_summary": summary,
                        "details": {"previous_context": m_data.get("context_length", 0)}
                    }
                    events.append(ev)
                    removed.append(ev)

        # 3. Detect Changes
        if not is_initial_baseline:
            for m_name, m_data in current_map.items():
                if m_name in existing_map:
                    old_data = existing_map[m_name]
                    old_free = bool(old_data.get("is_free", 0))
                    new_free = bool(m_data.get("is_free", 0))
                    old_ctx = old_data.get("context_length", 0) or 0
                    new_ctx = m_data.get("context_length", 0) or 0

                    diffs = []
                    if old_free != new_free:
                        diffs.append(f"pricing shifted from {'FREE' if old_free else 'PAID'} to {'FREE' if new_free else 'PAID'}")
                    if old_ctx and new_ctx and abs(old_ctx - new_ctx) > 100:
                        diffs.append(f"context length changed from {old_ctx:,} to {new_ctx:,} tokens")

                    if diffs:
                        disp = m_data.get("display_name") or m_name
                        summary = f"Model changed on {provider_id.title()}: {disp} ({'; '.join(diffs)})"
                        ev = {
                            "timestamp": now,
                            "provider_id": provider_id,
                            "event_type": "changed",
                            "model_name": m_name,
                            "display_name": disp,
                            "is_free": 1 if new_free else 0,
                            "change_summary": summary,
                            "details": {"changes": diffs, "old_free": old_free, "new_free": new_free, "old_ctx": old_ctx, "new_ctx": new_ctx}
                        }
                        events.append(ev)
                        changed.append(ev)

        # 4. Save events to audit log
        if events:
            db.log_model_trace_events(events)

        # 5. Clean up removed models from discovered_models
        if removed:
            db.remove_discovered_models(provider_id, [r["model_name"] for r in removed])

        # 6. Save/update discovered models in DB with explicit tier and reset metadata
        if sync_to_db and current_models:
            reset_info = cls.get_provider_reset_info(provider_id)
            for m in current_models:
                is_free_val = bool(m.get("is_free"))
                if not m.get("tier_type"):
                    if provider_id == "ollama":
                        m["tier_type"] = "100% Free Offline"
                        m["reset_time"] = "Never (Unlimited Local)"
                    elif is_free_val:
                        m["tier_type"] = "Free Tier"
                        m["reset_time"] = reset_info.get("reset_time", "")
                    else:
                        m["tier_type"] = "Paid / Credits"
                        m["reset_time"] = ""
            db.save_discovered_models(provider_id, current_models)

        diff_summary = {
            "provider_id": provider_id,
            "timestamp": now,
            "events_count": len(events),
            "added_free": added_free,
            "added_paid": added_paid,
            "removed": removed,
            "changed": changed,
            "total_active": len(current_models)
        }
        cls._last_trace_diffs[provider_id] = diff_summary
        return diff_summary

    @classmethod
    def get_provider_reset_info(cls, provider_id: str) -> Dict[str, Any]:
        """
        Computes dynamic limit reset information and human-readable countdowns
        for Free Tier and allowance-based providers.
        """
        now_utc = datetime.now(timezone.utc)
        # Midnight UTC of next day (daily resets)
        tomorrow_utc = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        delta_daily = tomorrow_utc - now_utc
        total_seconds = int(delta_daily.total_seconds())
        hours = max(0, total_seconds // 3600)
        minutes = max(0, (total_seconds % 3600) // 60)

        daily_countdown = f"in {hours}h {minutes}m (00:00 UTC)"
        daily_schedule = "Daily at 00:00 UTC"

        # 1st of next month (monthly resets)
        if now_utc.month == 12:
            next_month = now_utc.replace(year=now_utc.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now_utc.replace(month=now_utc.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        days_to_month = max(0, (next_month - now_utc).days)
        monthly_countdown = f"in {days_to_month}d (1st of month, 00:00 UTC)"
        monthly_schedule = "1st of each month (00:00 UTC)"

        pid = (provider_id or "").lower()
        if pid == "ollama":
            return {
                "tier_type": "100% Free Offline",
                "reset_schedule": "Never (Unlimited Local)",
                "reset_time": "Never (Unlimited Local)",
                "is_free_tier": True,
                "badge": "100% Free Offline"
            }
        elif pid in ("gemini", "google"):
            return {
                "tier_type": "Free Tier",
                "reset_schedule": daily_schedule,
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid == "groq":
            return {
                "tier_type": "Free Tier",
                "reset_schedule": daily_schedule,
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid == "cerebras":
            return {
                "tier_type": "Free Tier",
                "reset_schedule": daily_schedule,
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid in ("cloudflare", "cloudflare_ai"):
            return {
                "tier_type": "Free Tier",
                "reset_schedule": daily_schedule,
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid == "mistral":
            return {
                "tier_type": "Free Tier",
                "reset_schedule": "Every 60s (1 RPS) / Daily 00:00 UTC",
                "reset_time": f"Every 60s • Daily {daily_countdown}",
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid == "cohere":
            return {
                "tier_type": "Free Tier",
                "reset_schedule": monthly_schedule,
                "reset_time": monthly_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid in ("huggingface", "hf"):
            return {
                "tier_type": "Free Tier",
                "reset_schedule": "Hourly / Daily 00:00 UTC",
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid == "nvidia":
            return {
                "tier_type": "Free Tier",
                "reset_schedule": "Developer Allowance (1,000 Credits)",
                "reset_time": "Allowance: 1,000 Credits",
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        elif pid == "openrouter":
            return {
                "tier_type": "Free Tier",
                "reset_schedule": daily_schedule,
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }
        else:
            return {
                "tier_type": "Free Tier",
                "reset_schedule": daily_schedule,
                "reset_time": daily_countdown,
                "is_free_tier": True,
                "badge": "Free Tier"
            }

    @classmethod
    def scan_openrouter(cls, api_key: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Scans OpenRouter models and checks remaining key quota."""
        db = get_db()
        key = api_key or db.get_setting("openrouter_api_key")
        if not key:
            return [], None

        models: List[Dict[str, Any]] = []
        quota_data: Optional[Dict[str, Any]] = None
        headers = {"Authorization": f"Bearer {key}", "HTTP-Referer": "https://github.com/sage-ai"}

        # 1. Fetch Key Quota & Balance
        try:
            r_auth = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=10)
            if r_auth.status_code == 200:
                data = r_auth.json().get("data", {})
                limit = data.get("limit") or 0.0
                usage = data.get("usage") or 0.0
                limit_rem = data.get("limit_remaining")
                if limit_rem is None and limit > 0:
                    limit_rem = max(0.0, limit - usage)
                elif limit_rem is None:
                    limit_rem = 0.0

                is_free_tier = bool(data.get("is_free_tier", False))
                reset_info = cls.get_provider_reset_info("openrouter")
                quota_data = {
                    "total_limit": limit,
                    "used_amount": usage,
                    "remaining_amount": limit_rem,
                    "currency_or_unit": "USD" if not is_free_tier else "Free Requests",
                    "is_free_tier": is_free_tier,
                    "tier_type": "Free Tier" if is_free_tier else "Paid / Credits",
                    "reset_time": reset_info["reset_time"] if is_free_tier else "",
                    "details": data
                }
                db.save_provider_quota("openrouter", quota_data)
        except Exception as e:
            logger.warning("Failed to check OpenRouter quota: %s", e)

        # 2. Fetch Available Models
        try:
            r_models = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=12)
            if r_models.status_code == 200:
                data = r_models.json().get("data", [])
                for item in data:
                    m_id = item.get("id", "")
                    if not m_id:
                        continue
                    name = item.get("name") or m_id
                    ctx = item.get("context_length", 0)
                    pricing = item.get("pricing", {})
                    is_free = 1 if ":free" in m_id or (pricing.get("prompt") == "0" and pricing.get("completion") == "0") else 0
                    desc = item.get("description") or f"Context: {ctx:,} tokens"

                    models.append({
                        "model_name": m_id,
                        "display_name": name,
                        "description": desc,
                        "context_length": ctx,
                        "is_free": is_free
                    })
                if models:
                    cls.trace_provider_models("openrouter", models)
        except Exception as e:
            logger.warning("Failed to fetch OpenRouter models: %s", e)

        return models, quota_data

    @classmethod
    def scan_groq(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans active models on Groq."""
        db = get_db()
        key = api_key or db.get_setting("groq_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                for item in data:
                    m_id = item.get("id", "")
                    if not m_id or not item.get("active", True):
                        continue
                    # Skip audio transcription models for chat dropdown
                    if "whisper" in m_id.lower():
                        continue
                    ctx = item.get("context_window", 8192)
                    models.append({
                        "model_name": m_id,
                        "display_name": m_id,
                        "description": f"Ultra-low latency • Context {ctx:,}",
                        "context_length": ctx,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("groq", models)

                # Groq has a free tier with high rate limits
                reset_info = cls.get_provider_reset_info("groq")
                db.save_provider_quota("groq", {
                    "total_limit": 14400,
                    "used_amount": 0,
                    "remaining_amount": 14400,
                    "currency_or_unit": "Requests/Day",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Free Community Tier", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Groq models: %s", e)

        return models

    @classmethod
    def scan_nvidia(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans available models on NVIDIA NIM."""
        db = get_db()
        key = api_key or db.get_setting("nvidia_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://integrate.api.nvidia.com/v1/models", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                for item in data:
                    m_id = item.get("id", "")
                    if not m_id:
                        continue
                    clean_name = m_id.split("/")[-1] if "/" in m_id else m_id
                    models.append({
                        "model_name": m_id,
                        "display_name": clean_name,
                        "description": m_id,
                        "context_length": 128000 if "llama-3" in m_id else 32768,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("nvidia", models)

                # Calculate estimated remaining free credits based on SQLite usage
                usage_summary = db.get_model_usage_summary()
                nvidia_requests = sum(
                    m["requests"] for m in usage_summary.get("by_model", [])
                    if m.get("provider_id") == "nvidia"
                )
                remaining_credits = max(0, 1000 - nvidia_requests)
                reset_info = cls.get_provider_reset_info("nvidia")
                db.save_provider_quota("nvidia", {
                    "total_limit": 1000.0,
                    "used_amount": float(nvidia_requests),
                    "remaining_amount": float(remaining_credits),
                    "currency_or_unit": "Credits",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"standard_free_allowance": 1000, "tier": "Free Developer Allowance"}
                })
        except Exception as e:
            logger.warning("Failed to scan NVIDIA models: %s", e)

        return models

    @classmethod
    def scan_gemini(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans available models for Google Gemini API key."""
        db = get_db()
        key = api_key or db.get_setting("gemini_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=10)
            if r.status_code == 200:
                data = r.json().get("models", [])
                for item in data:
                    m_id = item.get("name", "")
                    if m_id.startswith("models/"):
                        m_id = m_id[7:]
                    if not m_id or "embedding" in m_id.lower() or "aqa" in m_id.lower():
                        continue
                    disp = item.get("displayName") or m_id
                    desc = item.get("description") or "Google DeepMind generative model"
                    ctx = item.get("inputTokenLimit", 1048576)
                    models.append({
                        "model_name": m_id,
                        "display_name": disp,
                        "description": desc,
                        "context_length": ctx,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("gemini", models)

                reset_info = cls.get_provider_reset_info("gemini")
                db.save_provider_quota("gemini", {
                    "total_limit": 1500.0,
                    "used_amount": 0.0,
                    "remaining_amount": 1500.0,
                    "currency_or_unit": "Requests/Day",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Gemini Developer Free Tier (15 RPM / 1500 RPD)", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Gemini models: %s", e)

        return models

    @classmethod
    def scan_ollama(cls, base_url: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans locally installed models in Ollama."""
        db = get_db()
        url = base_url or db.get_setting("ollama_base_url") or DEFAULT_MODELS.get("ollama_base_url", "http://127.0.0.1:11434")
        url = url.rstrip("/")
        models: List[Dict[str, Any]] = []

        try:
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json().get("models", [])
                for item in data:
                    name = item.get("name", "")
                    if not name:
                        continue
                    size_gb = round(item.get("size", 0) / (1024 ** 3), 1)
                    desc = f"Local Offline • {size_gb} GB" if size_gb > 0 else "Local Offline Model"
                    models.append({
                        "model_name": name,
                        "display_name": name,
                        "description": desc,
                        "context_length": 32768,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("ollama", models)

                reset_info = cls.get_provider_reset_info("ollama")
                db.save_provider_quota("ollama", {
                    "total_limit": 0.0,
                    "used_amount": 0.0,
                    "remaining_amount": 999999.0,
                    "currency_or_unit": "Tokens (Unlimited Local)",
                    "is_free_tier": True,
                    "tier_type": "100% Free Offline",
                    "reset_time": reset_info["reset_time"],
                    "details": {"type": "Local Private Engine"}
                })
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.debug("Ollama server not reachable at http://127.0.0.1:11434 (offline).")
        except Exception as e:
            logger.debug("Failed to scan Ollama models: %s", e)

        return models

    @classmethod
    def scan_mistral(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans active models on Mistral AI."""
        db = get_db()
        key = api_key or db.get_setting("mistral_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://api.mistral.ai/v1/models", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                for item in data:
                    m_id = item.get("id", "")
                    if not m_id:
                        continue
                    models.append({
                        "model_name": m_id,
                        "display_name": m_id,
                        "description": "European Frontier Model",
                        "context_length": 32768,
                        "is_free": 0
                    })
                if models:
                    cls.trace_provider_models("mistral", models)
                reset_info = cls.get_provider_reset_info("mistral")
                db.save_provider_quota("mistral", {
                    "total_limit": 500000.0,
                    "used_amount": 0.0,
                    "remaining_amount": 500000.0,
                    "currency_or_unit": "Tokens",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Mistral Free Experimentation Tier (1 RPS)", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Mistral models: %s", e)
        return models

    @classmethod
    def scan_cerebras(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans active models on Cerebras."""
        db = get_db()
        key = api_key or db.get_setting("cerebras_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://api.cerebras.ai/v1/models", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                for item in data:
                    m_id = item.get("id", "")
                    if not m_id:
                        continue
                    models.append({
                        "model_name": m_id,
                        "display_name": m_id,
                        "description": "Wafer-Scale Fast Inference",
                        "context_length": 8192,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("cerebras", models)
                reset_info = cls.get_provider_reset_info("cerebras")
                db.save_provider_quota("cerebras", {
                    "total_limit": 14400.0,
                    "used_amount": 0.0,
                    "remaining_amount": 14400.0,
                    "currency_or_unit": "Requests/Day",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Cerebras Free Developer Tier (30 RPM / 14.4k RPD)", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Cerebras models: %s", e)
        return models

    @classmethod
    def scan_cohere(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans active models on Cohere."""
        db = get_db()
        key = api_key or db.get_setting("cohere_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://api.cohere.com/v1/models", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json().get("models", [])
                for item in data:
                    m_id = item.get("name", "")
                    if not m_id:
                        continue
                    ctx = item.get("context_length", 128000)
                    models.append({
                        "model_name": m_id,
                        "display_name": m_id,
                        "description": f"Command Enterprise • Context: {ctx:,}",
                        "context_length": ctx,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("cohere", models)
                reset_info = cls.get_provider_reset_info("cohere")
                db.save_provider_quota("cohere", {
                    "total_limit": 1000.0,
                    "used_amount": 0.0,
                    "remaining_amount": 1000.0,
                    "currency_or_unit": "Monthly Calls",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Cohere Free Trial Key (1,000 calls/month)", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Cohere models: %s", e)
        return models

    @classmethod
    def scan_huggingface(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Validates Hugging Face API key and returns supported serverless models."""
        db = get_db()
        key = api_key or db.get_setting("huggingface_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://huggingface.co/api/whoami-v2", headers=headers, timeout=8)
            if r.status_code == 200:
                for m_id in PROVIDER_PRESET_MODELS.get("huggingface", []):
                    models.append({
                        "model_name": m_id,
                        "display_name": m_id,
                        "description": "Serverless Router Model",
                        "context_length": 32768,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("huggingface", models)
                reset_info = cls.get_provider_reset_info("huggingface")
                db.save_provider_quota("huggingface", {
                    "total_limit": 1000.0,
                    "used_amount": 0.0,
                    "remaining_amount": 1000.0,
                    "currency_or_unit": "Serverless Req",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Hugging Face Free Serverless API", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Hugging Face: %s", e)
        return models

    @classmethod
    def scan_cloudflare(cls, api_key: Optional[str] = None, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Validates Cloudflare API token and returns Workers AI models."""
        db = get_db()
        key = api_key or db.get_setting("cloudflare_api_key")
        if not key:
            return []

        models: List[Dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=headers, timeout=8)
            if r.status_code == 200 and r.json().get("success"):
                for m_id in PROVIDER_PRESET_MODELS.get("cloudflare", []):
                    models.append({
                        "model_name": m_id,
                        "display_name": m_id,
                        "description": "Cloudflare Edge Model",
                        "context_length": 8192,
                        "is_free": 1
                    })
                if models:
                    cls.trace_provider_models("cloudflare", models)
                reset_info = cls.get_provider_reset_info("cloudflare")
                db.save_provider_quota("cloudflare", {
                    "total_limit": 10000.0,
                    "used_amount": 0.0,
                    "remaining_amount": 10000.0,
                    "currency_or_unit": "Daily Neurons",
                    "is_free_tier": True,
                    "tier_type": "Free Tier",
                    "reset_time": reset_info["reset_time"],
                    "details": {"tier": "Cloudflare Workers AI Free Tier (10k Neurons/Day)", "reset": reset_info["reset_schedule"]}
                })
        except Exception as e:
            logger.warning("Failed to scan Cloudflare: %s", e)
        return models

    @classmethod
    def scan_all_configured(cls, force_refresh: bool = False) -> Dict[str, Any]:
        """Scans all providers that have keys or endpoints saved in SQLite."""
        if not force_refresh:
            with cls._cache_lock:
                if "scan_all" in cls._scan_cache:
                    cached_time, cached_res = cls._scan_cache["scan_all"]
                    if time.time() - cached_time < cls.CACHE_TTL:
                        return cached_res

        results = {}
        results["openrouter"] = cls.scan_openrouter()[0]
        results["groq"] = cls.scan_groq()
        results["nvidia"] = cls.scan_nvidia()
        results["gemini"] = cls.scan_gemini()
        results["ollama"] = cls.scan_ollama()
        results["mistral"] = cls.scan_mistral()
        results["cerebras"] = cls.scan_cerebras()
        results["cohere"] = cls.scan_cohere()
        results["huggingface"] = cls.scan_huggingface()
        results["cloudflare"] = cls.scan_cloudflare()

        with cls._cache_lock:
            cls._scan_cache["scan_all"] = (time.time(), results)

        return results

    @classmethod
    def trace_and_sync_all_configured_providers(cls) -> Dict[str, Any]:
        """
        Runs live model trace across all configured API keys on startup.
        Tracks additions (especially free models), removals, and parameter changes.
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        aggregate: Dict[str, Any] = {
            "timestamp": now,
            "added_free": [],
            "added_paid": [],
            "removed": [],
            "changed": [],
            "scanned_providers": [],
            "total_models": 0
        }

        # Invalidate scan cache for fresh startup verification
        with cls._cache_lock:
            cls._scan_cache.clear()

        scanners = [
            ("openrouter", lambda: cls.scan_openrouter()[0]),
            ("groq", cls.scan_groq),
            ("nvidia", cls.scan_nvidia),
            ("gemini", cls.scan_gemini),
            ("mistral", cls.scan_mistral),
            ("cerebras", cls.scan_cerebras),
            ("cohere", cls.scan_cohere),
            ("huggingface", cls.scan_huggingface),
            ("cloudflare", cls.scan_cloudflare),
            ("ollama", cls.scan_ollama),
        ]

        for prov_id, scan_fn in scanners:
            if not cls.is_provider_available(prov_id):
                continue
            try:
                models = scan_fn()
                aggregate["scanned_providers"].append(prov_id)
                aggregate["total_models"] += len(models) if models else 0
                diff = cls._last_trace_diffs.get(prov_id, {})
                aggregate["added_free"].extend(diff.get("added_free", []))
                aggregate["added_paid"].extend(diff.get("added_paid", []))
                aggregate["removed"].extend(diff.get("removed", []))
                aggregate["changed"].extend(diff.get("changed", []))
            except Exception as e:
                logger.warning("Failed tracing provider %s on startup: %s", prov_id, e)

        return aggregate

    @classmethod
    def get_available_models(cls) -> List[Dict[str, Any]]:
        """Returns list of active models across currently configured and available providers."""
        db = get_db()
        available: List[Dict[str, Any]] = []

        provider_map = [
            ("groq", ["groq/llama-3.3-70b-versatile"]),
            ("cerebras", ["cerebras/llama3.1-70b"]),
            ("nvidia", ["nvidia/llama-3.2-11b-vision-instruct"]),
            ("gemini", ["google/gemini-2.0-flash"]),
            ("openrouter", ["openrouter/auto"]),
            ("mistral", ["mistral/codestral-2501"]),
            ("cloudflare", ["cloudflare/@cf/meta/llama-3.1-8b-instruct"]),
            ("huggingface", ["huggingface/meta-llama/Llama-3.3-70B-Instruct"]),
        ]

        for prov, default_models in provider_map:
            if cls.is_provider_available(prov):
                scanned = db.get_discovered_models(prov)
                if scanned:
                    for s in scanned:
                        available.append({
                            "id": s.get("model_name", ""),
                            "name": s.get("display_name", "") or s.get("model_name", ""),
                            "provider": prov
                        })
                else:
                    presets = PROVIDER_PRESET_MODELS.get(prov, default_models)
                    for m_name in presets:
                        available.append({
                            "id": m_name,
                            "name": m_name,
                            "provider": prov
                        })

        if cls.is_provider_available("ollama"):
            available.append({
                "id": "ollama/llama3",
                "name": "Local Ollama Llama 3",
                "provider": "ollama"
            })

        if not available:
            # Fallback to system presets when no provider keys are configured
            for prov, models in PROVIDER_PRESET_MODELS.items():
                for m_name in models:
                    if isinstance(m_name, str):
                        full_id = f"{prov}/{m_name}" if "/" not in m_name else m_name
                        available.append({
                            "id": full_id,
                            "name": m_name,
                            "provider": prov
                        })

        return available

    @classmethod
    def get_categorized_models(cls, free_only: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns all models categorized by provider for UI display.
        Enforces 100% free models when free_only=True (default).
        """
        db = get_db()
        categorized: Dict[str, List[Dict[str, Any]]] = {}
        token_stats = db.get_model_token_usage_stats()

        providers = [
            ("groq", "Groq Cloud"),
            ("cerebras", "Cerebras"),
            ("nvidia", "NVIDIA NIM"),
            ("mistral", "Mistral AI"),
            ("cloudflare", "Cloudflare Workers AI"),
            ("cohere", "Cohere"),
            ("huggingface", "Hugging Face"),
            ("gemini", "Google Gemini"),
            ("openrouter", "OpenRouter"),
            ("ollama", "Local Ollama")
        ]

        for prov_id, display_label in providers:
            scanned = db.get_discovered_models(prov_id, free_only=free_only)
            model_items = []

            if scanned:
                for s in scanned:
                    m_name = s["model_name"]
                    is_free = bool(s.get("is_free", 0))
                    if free_only and not is_free:
                        continue
                    stats = token_stats.get(m_name, {})
                    tokens_used = stats.get("total_tokens", 0)
                    model_items.append({
                        "model_name": m_name,
                        "display_name": s["display_name"] or m_name,
                        "description": s.get("description", ""),
                        "provider_id": prov_id,
                        "is_free": True,
                        "tokens_used": tokens_used,
                        "requests": stats.get("requests", 0),
                        "context_length": s.get("context_length", 0)
                    })
            else:
                # Fallback to predefined presets in config
                presets = PROVIDER_PRESET_MODELS.get(prov_id, [])
                for m_name in presets:
                    stats = token_stats.get(m_name, {})
                    tokens_used = stats.get("total_tokens", 0)
                    model_items.append({
                        "model_name": m_name,
                        "display_name": m_name,
                        "description": f"Free {display_label} Model",
                        "provider_id": prov_id,
                        "is_free": True,
                        "tokens_used": tokens_used,
                        "requests": stats.get("requests", 0),
                        "context_length": 0
                    })

            if model_items:
                categorized[display_label] = model_items

        return categorized

    @classmethod
    def is_provider_available(cls, provider_id: str) -> bool:
        """Checks if a provider has a valid key configured or local service running."""
        db = get_db()
        p = (provider_id or "").lower().strip()

        if p in ("auto", "auto_router", "autorouter"):
            return any(cls.is_provider_available(prov) for prov in (
                "openrouter", "groq", "nvidia", "gemini", "mistral", "cerebras", "huggingface"
            ))

        if p == "ollama":
            try:
                from engine.ollama_manager import is_ollama_running
                return is_ollama_running()
            except Exception:
                return False

        key_map = {
            "openrouter": "openrouter_api_key",
            "groq": "groq_api_key",
            "nvidia": "nvidia_api_key",
            "gemini": "gemini_api_key",
            "mistral": "mistral_api_key",
            "cerebras": "cerebras_api_key",
            "cloudflare": "cloudflare_api_key",
            "cohere": "cohere_api_key",
            "huggingface": "huggingface_api_key",
        }
        setting_key = key_map.get(p)
        if setting_key:
            val = db.get_setting(setting_key, "") or ""
            return len(val.strip()) > 5
        return False

    @classmethod
    def is_model_available(cls, model_str: str) -> Tuple[bool, str]:
        """Determines if a model string is currently available and ready to respond."""
        m_lower = (model_str or "").lower()

        if "auto router" in m_lower or "auto" in m_lower:
            if cls.is_provider_available("auto"):
                return True, "Available (Waterfall Ready)"
            return True, "Available (Local Intelligent Fallback)"

        if "ollama" in m_lower or "offline" in m_lower:
            if cls.is_provider_available("ollama"):
                return True, "Available (Local Ollama Running)"
            return False, "Unavailable (Start Ollama Engine)"

        if "union" in m_lower or "pareto" in m_lower:
            avail = cls.is_provider_available("openrouter")
            return (avail, "Available (OpenRouter Connected)" if avail else "Unavailable (Needs OpenRouter Key)")

        if "deepseek" in m_lower and "groq" in m_lower:
            avail = cls.is_provider_available("groq")
            return (avail, "Available (Groq Key Connected)" if avail else "Unavailable (Needs Groq Key)")

        if "deepseek" in m_lower and "nvidia" in m_lower:
            avail = cls.is_provider_available("nvidia")
            return (avail, "Available (NVIDIA Key Connected)" if avail else "Unavailable (Needs NVIDIA Key)")

        if "deepseek" in m_lower:
            avail = cls.is_provider_available("openrouter") or cls.is_provider_available("nvidia") or cls.is_provider_available("groq")
            return (avail, "Available (Key Connected)" if avail else "Unavailable (Needs OpenRouter or NVIDIA Key)")

        if "qwen" in m_lower:
            avail = cls.is_provider_available("openrouter") or cls.is_provider_available("huggingface") or cls.is_provider_available("nvidia")
            return (avail, "Available (Key Connected)" if avail else "Unavailable (Needs OpenRouter Key)")

        if "codestral" in m_lower or "mistral" in m_lower:
            avail = cls.is_provider_available("mistral") or cls.is_provider_available("openrouter")
            return (avail, "Available (Mistral Key Connected)" if avail else "Unavailable (Needs Mistral Key)")

        if "gemini" in m_lower or "google" in m_lower:
            avail = cls.is_provider_available("gemini") or cls.is_provider_available("openrouter")
            return (avail, "Available (Gemini Key Connected)" if avail else "Unavailable (Needs Gemini Key)")

        if "groq" in m_lower:
            avail = cls.is_provider_available("groq")
            return (avail, "Available (Groq Key Connected)" if avail else "Unavailable (Needs Groq Key)")

        if "cerebras" in m_lower:
            avail = cls.is_provider_available("cerebras")
            return (avail, "Available (Cerebras Key Connected)" if avail else "Unavailable (Needs Cerebras Key)")

        if "nvidia" in m_lower:
            avail = cls.is_provider_available("nvidia")
            return (avail, "Available (NVIDIA Key Connected)" if avail else "Unavailable (Needs NVIDIA Key)")

        if "openrouter" in m_lower or "claude" in m_lower:
            avail = cls.is_provider_available("openrouter")
            return (avail, "Available (OpenRouter Connected)" if avail else "Unavailable (Needs OpenRouter Key)")

        return True, "Available"

    @classmethod
    def get_curated_models(cls, category: str = "coding") -> List[Dict[str, Any]]:
        """Returns list of curated models with title, clean_id, and live availability tag."""
        if category in ("coding", "project"):
            definitions = [
                ("Auto Router", "⚡ Auto Router (Best Free Coding Waterfall)"),
                ("Pareto 26.9 (Union Alpha)", "🔥 Pareto 26.9 (Union Alpha • 262k Context Frontier SOTA)"),
                ("DeepSeek R1", "👑 DeepSeek R1 Reasoning (Free • Rivals Claude 3.7 & o1)"),
                ("Qwen 2.5 Coder 32B", "💻 Qwen 2.5 Coder 32B (Free • #1 Open Coder, Near Claude)"),
                ("Groq DeepSeek R1 Distill 70B", "⚡ Groq DeepSeek R1 Distill 70B (Free • 500 tok/s Ultra-Fast)"),
                ("Mistral Codestral 2501", "🚀 Mistral Codestral 2501 (Free Tier • 80+ Languages)"),
                ("Google Gemini 2.0 Flash", "✨ Google Gemini 2.0 Flash (Free Tier • 1M Context & Fast)"),
                ("NVIDIA DeepSeek R1", "🧠 NVIDIA DeepSeek R1 & 70B (Free Credits • Enterprise)"),
                ("Cerebras LLaMA 3.3 70B", "⚡ Cerebras LLaMA 3.3 70B (Free • Lightning Fast CS-3)"),
                ("Local Ollama", "🔒 Local Ollama (qwen2.5-coder:7b • 100% Free Offline)"),
            ]
        else:  # automation / general
            definitions = [
                ("Auto Router", "⚡ Auto Router (Best Free Intelligent Waterfall)"),
                ("DeepSeek R1", "👑 DeepSeek R1 Reasoning (Free • SOTA Reasoning & Logic)"),
                ("Google Gemini 2.0 Flash", "✨ Google Gemini 2.0 Flash (Free Tier • Fast & Smart)"),
                ("Groq LLaMA 3.3 70B", "⚡ Groq LLaMA 3.3 70B (Free • 500 tok/s Lightning Speed)"),
                ("Mistral Large Latest", "🚀 Mistral Large Latest (Free Tier • European Flagship)"),
                ("NVIDIA LLaMA 3.3 70B", "🧠 NVIDIA LLaMA 3.3 70B (Free Credits • Enterprise Grade)"),
                ("Cerebras LLaMA 3.3 70B", "⚡ Cerebras LLaMA 3.3 70B (Free • Ultra-Low Latency)"),
                ("Local Ollama", "🔒 Local Ollama (qwen3:8b • 100% Free Offline & Private)"),
            ]

        results = []
        for clean_id, desc in definitions:
            is_avail, status_msg = cls.is_model_available(clean_id)
            tag = "● Available" if is_avail else "○ Unavailable"
            formatted_label = f"[{tag}] {desc}"
            results.append({
                "clean_id": clean_id,
                "display_label": formatted_label,
                "base_label": desc,
                "is_available": is_avail,
                "status_desc": status_msg
            })
        return results
