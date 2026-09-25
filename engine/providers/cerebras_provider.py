"""
Cerebras Provider for Sage AI.
Ultra-fast wafer-scale engine inference (2000+ tokens/sec on LLaMA 3.1 & 3.3).
"""
import json
import time
import os
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class CerebrasProvider(BaseProvider):
    """Cerebras ultra-fast inference provider using official OpenAI-compatible API."""

    ENDPOINT = "https://api.cerebras.ai/v1/chat/completions"

    def __init__(self, model_name: Optional[str] = None):
        super().__init__("cerebras", "Cerebras")
        self.model_name = model_name or DEFAULT_MODELS.get("cerebras_chat", "llama-3.3-70b")

    def _get_api_key(self) -> Optional[str]:
        key = get_db().get_setting("cerebras_api_key")
        if not key:
            key = os.getenv("CEREBRAS_API_KEY")
        return key.strip() if key else None

    def is_available(self) -> bool:
        return bool(self._get_api_key())

    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        api_key = self._get_api_key()
        if not api_key:
            return ProviderResponse(
                text="",
                model_name=self.model_name,
                provider_id=self.provider_id,
                success=False,
                error_msg="Cerebras API key is not configured. Please connect it in 'Add AI Models' in the sidebar."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": "You are Sage AI, an ultra-fast intelligent desktop assistant running on Cerebras."
            })

        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        active_model = kwargs.get("model") or get_db().get_setting("cerebras_model") or self.model_name
        models_to_try = [
            active_model,
            "llama-3.3-70b",
            "llama3.1-8b"
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        start_time = time.time()
        last_err = ""

        for model in unique_models:
            stream = on_chunk is not None
            payload = {
                "model": model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": stream
            }

            try:
                resp = requests.post(
                    self.ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=(5, 30),
                    stream=stream
                )

                if resp.status_code == 200:
                    if stream:
                        full_text = []
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line_str = line.decode("utf-8", errors="replace")
                            if line_str.startswith("data: "):
                                data_part = line_str[6:].strip()
                                if data_part == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_part)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        full_text.append(delta)
                                        if on_chunk:
                                            on_chunk(delta)
                                except json.JSONDecodeError:
                                    continue

                        text_res = "".join(full_text)
                        latency = (time.time() - start_time) * 1000
                        return ProviderResponse(
                            text=text_res,
                            model_name=model,
                            provider_id=self.provider_id,
                            success=True,
                            latency_ms=latency
                        )
                    else:
                        data = resp.json()
                        text_res = data["choices"][0]["message"]["content"]
                        usage = data.get("usage", {})
                        latency = (time.time() - start_time) * 1000
                        return ProviderResponse(
                            text=text_res,
                            model_name=model,
                            provider_id=self.provider_id,
                            success=True,
                            latency_ms=latency,
                            metadata={
                                "prompt_tokens": usage.get("prompt_tokens", 0),
                                "completion_tokens": usage.get("completion_tokens", 0),
                            }
                        )
                else:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as e:
                last_err = str(e)

        return ProviderResponse(
            text="",
            model_name=self.model_name,
            provider_id=self.provider_id,
            success=False,
            error_msg=f"Cerebras call failed: {last_err}",
            latency_ms=(time.time() - start_time) * 1000
        )
