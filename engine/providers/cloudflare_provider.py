"""
Cloudflare Workers AI Provider for Sage AI (Lunar Engine).
Serverless edge-accelerated inference across global Cloudflare edge network.
"""
import time
import os
import requests
from typing import List, Dict, Any, Optional, Callable
from .base_provider import BaseProvider, ProviderResponse
from database.db_manager import get_db
from config import DEFAULT_MODELS


class CloudflareWorkersAiProvider(BaseProvider):
    """Cloudflare Workers AI inference provider."""

    def __init__(self, model_name: Optional[str] = None):
        super().__init__("cloudflare", "Cloudflare Workers AI")
        self.model_name = model_name or DEFAULT_MODELS.get("cloudflare_chat", "@cf/meta/llama-3.3-70b-instruct")

    def _get_api_key(self) -> Optional[str]:
        key = get_db().get_setting("cloudflare_api_key")
        if not key:
            key = os.getenv("CLOUDFLARE_API_KEY") or os.getenv("CLOUDFLARE_API_TOKEN")
        return key.strip() if key else None

    def _get_account_id(self, api_key: str) -> Optional[str]:
        account_id = get_db().get_setting("cloudflare_account_id") or os.getenv("CLOUDFLARE_ACCOUNT_ID")
        if account_id and account_id.strip():
            return account_id.strip()

        # Auto-discover account ID using API token if not explicitly configured
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            r = requests.get("https://api.cloudflare.com/client/v4/accounts", headers=headers, timeout=6)
            if r.status_code == 200:
                accounts = r.json().get("result", [])
                if accounts and "id" in accounts[0]:
                    discovered_id = accounts[0]["id"]
                    get_db().set_setting("cloudflare_account_id", discovered_id)
                    return discovered_id
        except Exception:
            pass
        return None

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
                error_msg="Cloudflare Workers AI API token is not configured. Please connect it in 'Add AI Models' in the sidebar."
            )

        account_id = self._get_account_id(api_key)
        if not account_id:
            return ProviderResponse(
                text="",
                model_name=self.model_name,
                provider_id=self.provider_id,
                success=False,
                error_msg="Could not determine Cloudflare Account ID. Please verify your API token has Account Read permissions."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": "You are Sage AI, an intelligent desktop assistant running via Cloudflare Workers AI."
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

        active_model = kwargs.get("model") or get_db().get_setting("cloudflare_model") or self.model_name
        models_to_try = [
            active_model,
            "@cf/meta/llama-3.3-70b-instruct",
            "@cf/meta/llama-3.1-8b-instruct",
            "@cf/mistral/mistral-7b-instruct-v0.1"
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        start_time = time.time()
        last_err = ""

        for model in unique_models:
            endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
            payload = {
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 4096)
            }

            try:
                resp = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=(5, 45)
                )

                if resp.status_code == 200:
                    data = resp.json()
                    # Cloudflare response is in data["result"]["response"]
                    result = data.get("result", {})
                    text_res = result.get("response", "")
                    latency = (time.time() - start_time) * 1000

                    if on_chunk and text_res:
                        on_chunk(text_res)

                    return ProviderResponse(
                        text=text_res,
                        model_name=model,
                        provider_id=self.provider_id,
                        success=True,
                        latency_ms=latency
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
            error_msg=f"Cloudflare Workers AI call failed: {last_err}",
            latency_ms=(time.time() - start_time) * 1000
        )
