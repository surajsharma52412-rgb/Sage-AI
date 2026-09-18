"""
Ollama Local Provider for Sage AI (Lunar Engine).
Direct REST integration with locally hosted Ollama instances for private offline inference,
with auto-start capability and dynamic model discovery.
"""
import time
import json
import requests
from typing import List, Dict, Any, Optional, Callable, Tuple
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS
from engine.ollama_manager import (
    is_ollama_running, start_ollama_service, get_installed_ollama_models, is_ollama_starting
)


class OllamaProvider(BaseProvider):
    """Local Ollama instance provider with auto-launch and dynamic model selection."""

    def __init__(self, model_name: Optional[str] = None, is_coder: bool = False):
        default_model = DEFAULT_MODELS["ollama_coder"] if is_coder else DEFAULT_MODELS["ollama_chat"]
        super().__init__("ollama_coder" if is_coder else "ollama_chat", "Ollama Local")
        self.configured_model = model_name or default_model
        self.model_name = self.configured_model
        self.is_coder = is_coder

    def _get_base_url(self) -> str:
        url = get_db().get_setting("ollama_base_url")
        if not url:
            url = DEFAULT_MODELS["ollama_base_url"]
        return url.rstrip("/")

    def is_available(self) -> bool:
        """Pings Ollama server to check if running, without auto-starting it."""
        base_url = self._get_base_url()
        return is_ollama_running(base_url)

    def list_models(self) -> List[str]:
        """Returns list of models installed in local Ollama."""
        return get_installed_ollama_models(self._get_base_url())

    def _resolve_model(self, requested: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Determines the best available model.
        Returns: (model_name, error_if_any)
        """
        installed = self.list_models()
        if not installed:
            candidate = requested or self.configured_model
            if candidate:
                return candidate, None
            return None, "Ollama is running, but no models are installed yet. Run `ollama run qwen3:8b` in your terminal to download one."

        # 1. Check explicit requested model
        if requested:
            for m in installed:
                if m == requested or m.startswith(requested.split(":")[0]):
                    return m, None
            # Return requested directly if valid string
            return requested, None

        # 2. Check if configured model matches directly or by prefix
        if self.configured_model:
            conf_prefix = self.configured_model.split(":")[0]
            for m in installed:
                if m == self.configured_model or m.startswith(conf_prefix):
                    return m, None

        # 3. Check for preferred models based on role
        if self.is_coder:
            for m in installed:
                if any(k in m.lower() for k in ["coder", "qwen", "codellama", "deepseek"]):
                    return m, None

        # 4. Fallback to the first installed model
        return installed[0], None

    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        base_url = self._get_base_url()
        
        # Verify Ollama is running
        if not is_ollama_running(base_url):
            return ProviderResponse(
                text="",
                model_name="Ollama (Offline)",
                provider_id=self.provider_id,
                success=False,
                error_msg="Ollama is currently stopped/offline. You can start it on demand inside Sage AI via Settings > Add Models, or run `ollama serve` in your terminal."
            )

        requested_model = kwargs.get("model") or get_db().get_setting("ollama_model")
        target_model, err = self._resolve_model(requested=requested_model)
        if err or not target_model:
            return ProviderResponse(
                text="",
                model_name="Ollama (No Models)",
                provider_id=self.provider_id,
                success=False,
                error_msg=err or "No Ollama models found."
            )

        self.model_name = target_model
        endpoint = f"{base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        elif self.is_coder:
            messages.append({
                "role": "system",
                "content": "You are Sage AI's local coding engine. Write precise, efficient, clean code."
            })
        else:
            messages.append({
                "role": "system",
                "content": "You are Sage AI, a helpful, intelligent desktop AI assistant running locally via Ollama."
            })

        if history:
            for msg in history[-8:]:
                messages.append({
                    "role": "user" if msg.get("role") == "user" else "assistant",
                    "content": msg.get("content", "")
                })

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": bool(on_chunk),
            "options": {
                "temperature": kwargs.get("temperature", 0.3 if self.is_coder else 0.7)
            }
        }

        start_time = time.time()
        try:
            if on_chunk:
                resp = requests.post(endpoint, json=payload, stream=True, timeout=(4, 25))
                if resp.status_code != 200:
                    return ProviderResponse(
                        text="",
                        model_name=target_model,
                        provider_id=self.provider_id,
                        success=False,
                        error_msg=f"Ollama returned HTTP {resp.status_code}: {resp.text}"
                    )

                accumulated = []
                last_chunk = {}
                for line in resp.iter_lines():
                    if line:
                        chunk_obj = json.loads(line.decode("utf-8"))
                        last_chunk = chunk_obj
                        delta = chunk_obj.get("message", {}).get("content", "")
                        if delta:
                            accumulated.append(delta)
                            on_chunk(delta)

                latency = (time.time() - start_time) * 1000
                metadata = {
                    "prompt_tokens": last_chunk.get("prompt_eval_count", 0),
                    "completion_tokens": last_chunk.get("eval_count", 0),
                    "total_tokens": last_chunk.get("prompt_eval_count", 0) + last_chunk.get("eval_count", 0)
                }
                return ProviderResponse(
                    text="".join(accumulated),
                    model_name=f"Ollama ({target_model})",
                    provider_id=self.provider_id,
                    success=True,
                    latency_ms=latency,
                    metadata=metadata
                )
            else:
                resp = requests.post(endpoint, json=payload, timeout=(4, 25))
                latency = (time.time() - start_time) * 1000
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    metadata = {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    }
                    return ProviderResponse(
                        text=content,
                        model_name=f"Ollama ({target_model})",
                        provider_id=self.provider_id,
                        success=True,
                        latency_ms=latency,
                        metadata=metadata
                    )
                else:
                    return ProviderResponse(
                        text="",
                        model_name=target_model,
                        provider_id=self.provider_id,
                        success=False,
                        latency_ms=latency,
                        error_msg=f"Ollama HTTP {resp.status_code}: {resp.text}"
                    )
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start_time) * 1000
            return ProviderResponse(
                text="",
                model_name=target_model,
                provider_id=self.provider_id,
                success=False,
                latency_ms=latency,
                error_msg=f"Ollama connection error: {str(e)}"
            )
