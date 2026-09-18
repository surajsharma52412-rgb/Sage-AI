"""
Model Scanner and Quota Discovery Service for Sage AI (Lunar Engine).
Discovers live available models for configured API keys (OpenRouter, Groq, NVIDIA, Gemini, Ollama)
and tracks remaining quota/credit allowances.
"""
import time
import logging
import threading
import requests
from typing import List, Dict, Any, Optional, Tuple
from database.db_manager import get_db
from config import DEFAULT_MODELS, PROVIDER_PRESET_MODELS

logger = logging.getLogger(__name__)


class ModelScanner:
    """Discovers authorized models and quota limits across cloud and local providers."""

    _scan_cache: Dict[str, Tuple[float, Any]] = {}
    _cache_lock = threading.Lock()
    CACHE_TTL: float = 300.0  # 5-minute memory cache to prevent blocking network scans

    @staticmethod
    def scan_openrouter(api_key: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
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

                quota_data = {
                    "total_limit": limit,
                    "used_amount": usage,
                    "remaining_amount": limit_rem,
                    "currency_or_unit": "USD",
                    "is_free_tier": data.get("is_free_tier", False),
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
                    if not is_free:
                        continue
                    desc = item.get("description") or f"Context: {ctx:,} tokens"

                    models.append({
                        "model_name": m_id,
                        "display_name": name,
                        "description": desc,
                        "context_length": ctx,
                        "is_free": 1
                    })
                if models:
                    db.save_discovered_models("openrouter", models)
        except Exception as e:
            logger.warning("Failed to fetch OpenRouter models: %s", e)

        return models, quota_data

    @staticmethod
    def scan_groq(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("groq", models)

                # Groq has a free tier with high rate limits
                db.save_provider_quota("groq", {
                    "total_limit": 14400,
                    "used_amount": 0,
                    "remaining_amount": 14400,
                    "currency_or_unit": "Requests/Day",
                    "is_free_tier": True,
                    "details": {"tier": "Free Community Tier"}
                })
        except Exception as e:
            logger.warning("Failed to scan Groq models: %s", e)

        return models

    @staticmethod
    def scan_nvidia(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("nvidia", models)

                # Calculate estimated remaining free credits based on SQLite usage
                usage_summary = db.get_model_usage_summary()
                nvidia_requests = sum(
                    m["requests"] for m in usage_summary.get("by_model", [])
                    if m.get("provider_id") == "nvidia"
                )
                remaining_credits = max(0, 1000 - nvidia_requests)
                db.save_provider_quota("nvidia", {
                    "total_limit": 1000.0,
                    "used_amount": float(nvidia_requests),
                    "remaining_amount": float(remaining_credits),
                    "currency_or_unit": "Credits",
                    "is_free_tier": True,
                    "details": {"standard_free_allowance": 1000}
                })
        except Exception as e:
            logger.warning("Failed to scan NVIDIA models: %s", e)

        return models

    @staticmethod
    def scan_gemini(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("gemini", models)

                db.save_provider_quota("gemini", {
                    "total_limit": 1500.0,
                    "used_amount": 0.0,
                    "remaining_amount": 1500.0,
                    "currency_or_unit": "Requests/Day",
                    "is_free_tier": True,
                    "details": {"tier": "Gemini Developer Free Tier (15 RPM / 1500 RPD)"}
                })
        except Exception as e:
            logger.warning("Failed to scan Gemini models: %s", e)

        return models

    @staticmethod
    def scan_ollama(base_url: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("ollama", models)

                db.save_provider_quota("ollama", {
                    "total_limit": 0.0,
                    "used_amount": 0.0,
                    "remaining_amount": 999999.0,
                    "currency_or_unit": "Tokens (Unlimited Local)",
                    "is_free_tier": True,
                    "details": {"type": "Local Private Engine"}
                })
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.debug("Ollama server not reachable at http://127.0.0.1:11434 (offline).")
        except Exception as e:
            logger.debug("Failed to scan Ollama models: %s", e)

        return models

    @staticmethod
    def scan_mistral(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("mistral", models)
        except Exception as e:
            logger.warning("Failed to scan Mistral models: %s", e)
        return models

    @staticmethod
    def scan_cerebras(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                        "is_free": 0
                    })
                if models:
                    db.save_discovered_models("cerebras", models)
        except Exception as e:
            logger.warning("Failed to scan Cerebras models: %s", e)
        return models

    @staticmethod
    def scan_cohere(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                        "is_free": 0
                    })
                if models:
                    db.save_discovered_models("cohere", models)
        except Exception as e:
            logger.warning("Failed to scan Cohere models: %s", e)
        return models

    @staticmethod
    def scan_huggingface(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("huggingface", models)
        except Exception as e:
            logger.warning("Failed to scan Hugging Face: %s", e)
        return models

    @staticmethod
    def scan_cloudflare(api_key: Optional[str] = None, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    db.save_discovered_models("cloudflare", models)
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
