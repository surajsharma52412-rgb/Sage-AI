"""
Standardized Provider Adapters for Sage Universal AI Auto Router.
Provides uniform execution, error translation, rate limit detection, and health checks.
"""
import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable

from database.db_manager import get_db
from engine.providers.base_provider import ProviderResponse
from engine.providers.gemini_provider import GeminiProvider
from engine.providers.groq_provider import GroqProvider
from engine.providers.openrouter_provider import OpenRouterProvider
from engine.providers.nvidia_provider import NvidiaNimProvider
from engine.providers.mistral_provider import MistralProvider
from engine.providers.cerebras_provider import CerebrasProvider
from engine.providers.cloudflare_provider import CloudflareWorkersAiProvider
from engine.providers.cohere_provider import CohereProvider
from engine.providers.huggingface_provider import HuggingFaceProvider
from engine.providers.ollama_provider import OllamaProvider
from engine.providers.image_provider import ImageProvider

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """Abstract base adapter wrapping a concrete provider for auto-routing."""

    def __init__(self, provider_id: str, name: str, env_key: Optional[str] = None):
        self.provider_id = provider_id
        self.name = name
        self.env_key = env_key

    def get_api_key(self) -> Optional[str]:
        """Retrieves API key prioritizing SQLite database, falling back to environment variable."""
        db_key = get_db().get_setting(f"{self.provider_id}_api_key")
        if db_key and db_key.strip():
            return db_key.strip()
        if self.env_key:
            env_val = os.getenv(self.env_key)
            if env_val and env_val.strip():
                return env_val.strip()
        return None

    def is_available(self) -> bool:
        """Returns True if the provider is configured and available."""
        if self.provider_id == "ollama":
            from engine.ollama_manager import is_ollama_running
            return is_ollama_running()
        return bool(self.get_api_key())

    def get_quota_ratio(self) -> float:
        """Returns quota score ratio between 0.0 (exhausted/empty) and 1.0 (plentiful/free)."""
        if self.provider_id == "ollama":
            return 1.0  # Local models have unlimited quota
        q = get_db().get_provider_quota(self.provider_id)
        if not q:
            return 1.0 if self.is_available() else 0.0
        rem = q.get("remaining_amount", 0.0)
        tot = q.get("total_limit", 0.0)
        if tot > 0:
            return max(0.0, min(1.0, rem / tot))
        return 1.0

    @abstractmethod
    def execute(
        self,
        model_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        """Executes completion for a specific model ID."""
        pass


class GeminiAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("gemini", "Google Gemini", "GEMINI_API_KEY")
        self.provider = GeminiProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class GroqAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("groq", "Groq Cloud", "GROQ_API_KEY")
        self.provider = GroqProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class OpenRouterAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("openrouter", "OpenRouter", "OPENROUTER_API_KEY")
        self.provider = OpenRouterProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class NVIDIAAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("nvidia", "NVIDIA NIM", "NVIDIA_API_KEY")
        self.provider = NvidiaNimProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class MistralAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("mistral", "Mistral AI", "MISTRAL_API_KEY")
        self.provider = MistralProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class CerebrasAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("cerebras", "Cerebras", "CEREBRAS_API_KEY")
        self.provider = CerebrasProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class CloudflareAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("cloudflare", "Cloudflare Workers AI", "CLOUDFLARE_API_KEY")
        self.provider = CloudflareWorkersAiProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class CohereAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("cohere", "Cohere", "COHERE_API_KEY")
        self.provider = CohereProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class HuggingFaceAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("huggingface", "Hugging Face", "HUGGINGFACE_API_KEY")
        self.provider = HuggingFaceProvider()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class OllamaAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("ollama", "Local Ollama", None)
        self.provider_coder = OllamaProvider(is_coder=True)
        self.provider_chat = OllamaProvider(is_coder=False)

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        prov = self.provider_coder if any(k in model_id.lower() for k in ("coder", "code")) else self.provider_chat
        return prov.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


class ImageAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("image", "Image Studio", None)
        self.provider = ImageProvider()

    def is_available(self) -> bool:
        return self.provider.is_available()

    def execute(self, model_id, prompt, history=None, system_prompt=None, on_chunk=None, **kwargs):
        return self.provider.generate(prompt, history=history, system_prompt=system_prompt, on_chunk=on_chunk, model=model_id, **kwargs)


# Global adapter lookup map
ALL_ADAPTERS: Dict[str, BaseAdapter] = {
    "gemini": GeminiAdapter(),
    "groq": GroqAdapter(),
    "openrouter": OpenRouterAdapter(),
    "nvidia": NVIDIAAdapter(),
    "mistral": MistralAdapter(),
    "cerebras": CerebrasAdapter(),
    "cloudflare": CloudflareAdapter(),
    "cohere": CohereAdapter(),
    "huggingface": HuggingFaceAdapter(),
    "ollama": OllamaAdapter(),
    "image": ImageAdapter(),
}
