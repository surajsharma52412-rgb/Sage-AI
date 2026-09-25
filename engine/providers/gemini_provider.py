"""
Google Gemini Provider for Sage AI.
REST integration with Google's Gemini Flash models.
"""
import time
import os
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class GeminiProvider(BaseProvider):
    """Google Gemini REST API provider."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, model_name: Optional[str] = None):
        super().__init__("gemini", "Google Gemini")
        self.model_name = model_name or DEFAULT_MODELS["gemini_chat"]

    def _get_api_key(self) -> Optional[str]:
        key = get_db().get_setting("gemini_api_key")
        if not key:
            key = os.getenv("GEMINI_API_KEY")
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
                error_msg="Gemini API key is not configured. Please connect it in 'Add AI Models' in the sidebar."
            )

        contents = []
        if history:
            for msg in history[-8:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        url = f"{self.BASE_URL}/{self.model_name}:generateContent?key={api_key}"
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.6),
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        active_model = kwargs.get("model") or get_db().get_setting("gemini_model") or self.model_name
        models_to_try = [active_model, self.model_name, "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
        # Remove duplicates preserving order
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        start_time = time.time()
        last_err = ""

        for candidate_model in unique_models:
            url = f"{self.BASE_URL}/{candidate_model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=35)
                latency = (time.time() - start_time) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            content = "".join(p.get("text", "") for p in parts)
                            if on_chunk:
                                on_chunk(content)
                            usage_meta = data.get("usageMetadata", {})
                            metadata = {
                                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                                "total_tokens": usage_meta.get("totalTokenCount", 0),
                                "usageMetadata": usage_meta
                            }
                            return ProviderResponse(
                                text=content,
                                model_name=f"Google Gemini ({candidate_model})",
                                provider_id=self.provider_id,
                                success=True,
                                latency_ms=latency,
                                metadata=metadata
                            )
                        else:
                            last_err = "Empty response from Gemini model."
                    except Exception as parse_err:
                        last_err = f"Failed to parse Gemini response: {str(parse_err)}"
                elif resp.status_code == 404:
                    # Model not found on Google's API, try next candidate
                    last_err = f"Model {candidate_model} not found (404)"
                    continue
                else:
                    err_msg = resp.text
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    last_err = f"Gemini API Error ({resp.status_code}): {err_msg}"
                    # If permission / key error (400, 403), stop retrying
                    if resp.status_code in (400, 401, 403):
                        break
            except requests.exceptions.RequestException as e:
                last_err = f"Gemini connection error: {str(e)}"
                break

        latency = (time.time() - start_time) * 1000
        return ProviderResponse(
            text="",
            model_name=self.model_name,
            provider_id=self.provider_id,
            success=False,
            latency_ms=latency,
            error_msg=last_err or "Gemini API request failed."
        )
