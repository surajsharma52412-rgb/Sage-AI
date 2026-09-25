"""
NVIDIA NIM Provider for Sage AI.
High-performance accelerated inference on NVIDIA infrastructure.
"""
import json
import time
import os
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class NvidiaNimProvider(BaseProvider):
    """NVIDIA NIM inference provider using OpenAI-compatible API."""

    ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"

    def __init__(self, model_name: Optional[str] = None):
        super().__init__("nvidia", "NVIDIA NIM")
        self.model_name = model_name or DEFAULT_MODELS["nvidia_chat"]

    def _get_api_key(self) -> Optional[str]:
        key = get_db().get_setting("nvidia_api_key")
        if not key:
            key = os.getenv("NVIDIA_API_KEY")
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
                error_msg="NVIDIA NIM API key is not configured. Please connect it in 'Add AI Models' in the sidebar."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": "You are Sage AI, an intelligent desktop assistant running via NVIDIA NIM."
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

        active_model = kwargs.get("model") or get_db().get_setting("nvidia_model") or self.model_name
        models_to_try = [
            active_model,
            "meta/llama-3.2-11b-vision-instruct",
            self.model_name
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        start_time = time.time()
        last_err = ""

        for candidate_model in unique_models:
            payload = {
                "model": candidate_model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.5),
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": True,
            }
            try:
                resp = requests.post(self.ENDPOINT, headers=headers, json=payload, stream=True, timeout=(15, 90))
                if resp.status_code == 200:
                    accumulated = []
                    usage_info = {}
                    in_reasoning = False
                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8", errors="replace")
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
                                            accumulated.append(delta)
                                            if on_chunk:
                                                on_chunk(delta)

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
                        "total_tokens": usage_info.get("total_tokens", est_p + est_c),
                        "usage": usage_info
                    }
                    return ProviderResponse(
                        text=text_out,
                        model_name=f"NVIDIA NIM ({candidate_model})",
                        provider_id=self.provider_id,
                        success=True,
                        latency_ms=latency,
                        metadata=metadata
                    )
                elif resp.status_code in (404, 410):
                    # Model not found or sunset, try next candidate
                    last_err = f"Model {candidate_model} is no longer available on NVIDIA NIM ({resp.status_code})"
                    continue
                elif resp.status_code == 403:
                    last_err = "NVIDIA NIM Authorization Failed (403 Forbidden). Your NVIDIA API key may be inactive, invalid, or out of NGC credits. Verify your key at https://build.nvidia.com"
                    break
                elif resp.status_code == 401:
                    last_err = "NVIDIA NIM Invalid API Key (401 Unauthorized). Please re-enter your key in 'Add AI Models' in the sidebar."
                    break
                else:
                    last_err = f"NVIDIA NIM Error ({resp.status_code}): {resp.text}"
            except requests.exceptions.RequestException as e:
                last_err = f"NVIDIA NIM connection error on {candidate_model}: {str(e)}"
                continue

        latency = (time.time() - start_time) * 1000
        return ProviderResponse(
            text="",
            model_name=self.model_name,
            provider_id=self.provider_id,
            success=False,
            latency_ms=latency,
            error_msg=last_err or "NVIDIA NIM request failed."
        )
