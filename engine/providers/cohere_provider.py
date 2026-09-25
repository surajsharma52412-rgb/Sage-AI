"""
Cohere Provider for Sage AI.
Enterprise Command R+ models and RAG-optimized inference.
"""
import time
import os
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class CohereProvider(BaseProvider):
    """Cohere inference provider using official v2 chat API with fallback to OpenAI compatibility."""

    ENDPOINT_V2 = "https://api.cohere.com/v2/chat"
    ENDPOINT_COMPAT = "https://api.cohere.ai/v1/chat/completions"

    def __init__(self, model_name: Optional[str] = None):
        super().__init__("cohere", "Cohere")
        self.model_name = model_name or DEFAULT_MODELS.get("cohere_chat", "command-r-plus-08-2024")

    def _get_api_key(self) -> Optional[str]:
        key = get_db().get_setting("cohere_api_key")
        if not key:
            key = os.getenv("COHERE_API_KEY")
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
                error_msg="Cohere API key is not configured. Please connect it in 'Add AI Models' in the sidebar."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": "You are Sage AI, an intelligent desktop assistant running via Cohere."
            })

        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        active_model = kwargs.get("model") or get_db().get_setting("cohere_model") or self.model_name
        models_to_try = [
            active_model,
            "command-r-plus-08-2024",
            "command-r-08-2024",
            "command-r"
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        start_time = time.time()
        last_err = ""

        # First attempt via official Cohere v2 chat API
        for model in unique_models:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
            }

            try:
                resp = requests.post(
                    self.ENDPOINT_V2,
                    headers=headers,
                    json=payload,
                    timeout=(5, 40)
                )

                if resp.status_code == 200:
                    data = resp.json()
                    # Cohere v2 format: data["message"]["content"][0]["text"]
                    text_parts = []
                    msg_obj = data.get("message", {})
                    content_list = msg_obj.get("content", [])
                    if isinstance(content_list, list):
                        for c in content_list:
                            if isinstance(c, dict) and "text" in c:
                                text_parts.append(c["text"])
                            elif isinstance(c, str):
                                text_parts.append(c)
                    elif isinstance(content_list, str):
                        text_parts.append(content_list)

                    text_res = "".join(text_parts) if text_parts else msg_obj.get("text", "")
                    usage = data.get("usage", {}).get("tokens", {})
                    latency = (time.time() - start_time) * 1000

                    if on_chunk and text_res:
                        on_chunk(text_res)

                    return ProviderResponse(
                        text=text_res,
                        model_name=model,
                        provider_id=self.provider_id,
                        success=True,
                        latency_ms=latency,
                        metadata={
                            "prompt_tokens": usage.get("input_tokens", 0),
                            "completion_tokens": usage.get("output_tokens", 0),
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
            error_msg=f"Cohere call failed: {last_err}",
            latency_ms=(time.time() - start_time) * 1000
        )
