"""
Coding Model Router for SAGE Coding Agent Architecture (v6).
Intelligently selects the best LLM model and provider for each coding subtask:
- Mistral API (Reasoning / General)
- Gemini API (Complex multi-file reasoning, deep architecture)
- Ollama (Local / Offline code generation)
- OpenRouter (Multi-model: Claude 3.5 Sonnet, DeepSeek-Coder, Qwen-Coder)
- NVIDIA NIM / Groq / Other Models
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CodingModelRouter:
    """Routes coding subagent prompts to optimal models based on task nature."""

    ROLE_MODEL_PREFERENCES = {
        "architect": {
            "preferred_providers": ["gemini", "openrouter", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.5-pro", "gemini-2.0-flash", "anthropic/claude-3.5-sonnet", "mistral-large-latest", "deepseek-ai/deepseek-r1"]
        },
        "backend": {
            "preferred_providers": ["openrouter", "gemini", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["deepseek/deepseek-coder", "gemini-2.0-flash", "qwen/qwen-2.5-coder-32b", "mistral-large-latest"]
        },
        "frontend": {
            "preferred_providers": ["openrouter", "gemini", "nvidia", "mistral", "groq", "ollama", "local_facts"],
            "models": ["anthropic/claude-3.5-sonnet", "gemini-2.0-flash", "meta-llama/llama-3.3-70b-instruct"]
        },
        "devops": {
            "preferred_providers": ["gemini", "mistral", "openrouter", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.0-flash", "mistral-small-latest", "qwen/qwen-2.5-coder-32b"]
        },
        "database": {
            "preferred_providers": ["openrouter", "gemini", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["deepseek/deepseek-coder", "gemini-2.0-flash", "mistral-large-latest"]
        },
        "debugger": {
            "preferred_providers": ["gemini", "openrouter", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.5-pro", "deepseek-ai/deepseek-r1", "anthropic/claude-3.5-sonnet", "mistral-large-latest"]
        },
        "qa": {
            "preferred_providers": ["gemini", "openrouter", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.0-flash", "deepseek/deepseek-coder", "mistral-large-latest"]
        },
        "tester": {
            "preferred_providers": ["gemini", "openrouter", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.0-flash", "deepseek/deepseek-coder", "mistral-large-latest"]
        },
        "security": {
            "preferred_providers": ["gemini", "mistral", "openrouter", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.5-pro", "mistral-large-latest", "anthropic/claude-3.5-sonnet"]
        },
        "reviewer": {
            "preferred_providers": ["gemini", "openrouter", "mistral", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.5-pro", "mistral-large-latest", "anthropic/claude-3.5-sonnet"]
        },
        "documentation": {
            "preferred_providers": ["gemini", "mistral", "openrouter", "nvidia", "groq", "ollama", "local_facts"],
            "models": ["gemini-2.0-flash", "mistral-large-latest", "meta-llama/llama-3.3-70b-instruct"]
        },
    }

    def __init__(self, default_provider_override: Optional[str] = None):
        self.default_provider_override = default_provider_override

    def get_preferred_providers(self, role: str, force_offline: bool = False) -> List[str]:
        """Returns ordered provider list for a given sub-agent role."""
        if force_offline:
            return ["ollama", "local_facts"]

        if self.default_provider_override:
            # Put manual override first, then standard fallback cascade
            return [self.default_provider_override, "openrouter", "gemini", "mistral", "nvidia", "groq", "ollama", "local_facts"]

        prefs = self.ROLE_MODEL_PREFERENCES.get(role.lower(), {})
        return prefs.get("preferred_providers", ["openrouter", "gemini", "mistral", "nvidia", "groq", "ollama", "local_facts"])

    def select_model_for_task(self, role: str, available_models: Optional[List[str]] = None) -> Dict[str, Any]:
        """Chooses best model given role and currently active/available models."""
        prefs = self.ROLE_MODEL_PREFERENCES.get(role.lower(), {})
        desired_models = prefs.get("models", ["gemini-2.0-flash"])

        chosen_model = desired_models[0]
        if available_models:
            for dm in desired_models:
                if any(dm.lower() in am.lower() for am in available_models):
                    chosen_model = dm
                    break

        return {
            "role": role,
            "chosen_model": chosen_model,
            "preferred_providers": self.get_preferred_providers(role)
        }
