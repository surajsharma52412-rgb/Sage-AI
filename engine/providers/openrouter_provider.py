"""
OpenRouter API Provider for Sage AI.
Primarily routes coding queries to high-capability coding models.
"""
import json
import time
import os
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider supporting modern coding models (Qwen, Claude, DeepSeek)."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model_name: Optional[str] = None):
        super().__init__("openrouter", "OpenRouter Coder")
        self.model_name = model_name or DEFAULT_MODELS["openrouter_coder"]

    def _get_api_key(self) -> Optional[str]:
        key = get_db().get_setting("openrouter_api_key")
        if not key:
            key = os.getenv("OPENROUTER_API_KEY")
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
                error_msg="OpenRouter API key is not configured. Please connect it in 'Add AI Models' in the sidebar."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": "You are Sage AI's expert coding engine. Write clean, idiomatic, well-documented, production-ready code."
            })

        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/sage-ai",
            "X-Title": "Sage AI Desktop",
            "Content-Type": "application/json"
        }

        active_model = kwargs.get("model") or get_db().get_setting("openrouter_model") or self.model_name
        payload = {
            "model": active_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        start_time = time.time()
        try:
            if on_chunk:
                payload["stream"] = True
                resp = requests.post(self.ENDPOINT, headers=headers, json=payload, stream=True, timeout=50)
                if resp.status_code != 200:
                    error_info = resp.text
                    try:
                        err_json = resp.json()
                        error_info = err_json.get("error", {}).get("message", error_info)
                    except Exception:
                        pass
                    return ProviderResponse(
                        text="",
                        model_name=active_model,
                        provider_id=self.provider_id,
                        success=False,
                        error_msg=f"OpenRouter Error ({resp.status_code}): {error_info}"
                    )

                accumulated = []
                usage_info = {}
                in_reasoning = False
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8")
                        if line_str.startswith("data: "):
                            data_str = line_str[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices") or []
                                if choices:
                                    delta_obj = choices[0].get("delta") or {}
                                    delta = delta_obj.get("content") or ""
                                    reasoning = delta_obj.get("reasoning") or delta_obj.get("reasoning_content") or ""
                                    if reasoning:
                                        if not in_reasoning:
                                            in_reasoning = True
                                            if on_chunk:
                                                on_chunk("<think>")
                                            accumulated.append("<think>")
                                        if on_chunk:
                                            on_chunk(reasoning)
                                        accumulated.append(reasoning)
                                    elif delta:
                                        if in_reasoning:
                                            in_reasoning = False
                                            if on_chunk:
                                                on_chunk("</think>")
                                            accumulated.append("</think>")
                                        if on_chunk:
                                            on_chunk(delta)
                                        accumulated.append(delta)

                                if chunk.get("usage"):
                                    usage_info = chunk["usage"]
                            except Exception:
                                pass

                if in_reasoning:
                    if on_chunk:
                        on_chunk("</think>")
                    accumulated.append("</think>")

                latency = (time.time() - start_time) * 1000
                text_out = "".join(accumulated)
                est_p = int(len(prompt.split()) * 1.35)
                est_c = int(len(text_out.split()) * 1.35)
                metadata = {
                    "prompt_tokens": usage_info.get("prompt_tokens", est_p),
                    "completion_tokens": usage_info.get("completion_tokens", est_c),
                    "total_tokens": usage_info.get("total_tokens", est_p + est_c)
                }
                return ProviderResponse(
                    text=text_out,
                    model_name=active_model,
                    provider_id=self.provider_id,
                    success=True,
                    latency_ms=latency,
                    metadata=metadata
                )

            resp = requests.post(self.ENDPOINT, headers=headers, json=payload, timeout=45)
            latency = (time.time() - start_time) * 1000

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                msg_obj = choices[0].get("message") or {} if choices else {}
                content = msg_obj.get("content") or ""
                reasoning = msg_obj.get("reasoning") or msg_obj.get("reasoning_content") or ""
                if reasoning:
                    content = f"<think>\n{reasoning}\n</think>\n\n{content}"
                usage = data.get("usage", {})
                metadata = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "usage": usage
                }
                return ProviderResponse(
                    text=content,
                    model_name=active_model,
                    provider_id=self.provider_id,
                    success=True,
                    latency_ms=latency,
                    metadata=metadata
                )
            else:
                error_info = resp.text
                try:
                    err_json = resp.json()
                    error_info = err_json.get("error", {}).get("message", error_info)
                except Exception:
                    pass
                return ProviderResponse(
                    text="",
                    model_name=self.model_name,
                    provider_id=self.provider_id,
                    success=False,
                    latency_ms=latency,
                    error_msg=f"OpenRouter Error ({resp.status_code}): {error_info}"
                )
        except requests.exceptions.RequestException as e:
            latency = (time.time() - start_time) * 1000
            return ProviderResponse(
                text="",
                model_name=self.model_name,
                provider_id=self.provider_id,
                success=False,
                latency_ms=latency,
                error_msg=f"OpenRouter network connection error: {str(e)}"
            )
