"""
Fallback Router for Sage AI (Lunar Engine).
Orchestrates intent classification, multi-provider waterfall fallback,
web evidence synthesis, and real-time stage event notifications.
"""
import logging
from typing import List, Dict, Any, Optional, Callable

from config import (
    INTENT_CODING,
    INTENT_WEB_SEARCH,
    INTENT_GITHUB,
    INTENT_IMAGE,
    INTENT_LOCAL_FACTS,
    INTENT_GENERAL_CHAT,
)
from .request_analyzer import RequestAnalyzer
from .providers.base_provider import ProviderResponse
from .providers.openrouter_provider import OpenRouterProvider
from .providers.groq_provider import GroqProvider
from .providers.nvidia_provider import NvidiaNimProvider
from .providers.gemini_provider import GeminiProvider
from .providers.ollama_provider import OllamaProvider
from .providers.mistral_provider import MistralProvider
from .providers.cerebras_provider import CerebrasProvider
from .providers.cohere_provider import CohereProvider
from .providers.huggingface_provider import HuggingFaceProvider
from .providers.cloudflare_provider import CloudflareWorkersAiProvider
from .providers.search_provider import SearchProvider
from .providers.image_provider import ImageProvider
from .providers.local_facts_provider import LocalFactsProvider
from engine.orchestrator.core_brain import get_orchestrator

logger = logging.getLogger(__name__)


class FallbackRouter:
    """Multi-provider waterfall fallback orchestrator."""

    def __init__(self):
        self.orchestrator = get_orchestrator()
        # Initialize providers
        self.providers = {
            "openrouter": OpenRouterProvider(),
            "groq": GroqProvider(),
            "cerebras": CerebrasProvider(),
            "nvidia": NvidiaNimProvider(),
            "mistral": MistralProvider(),
            "cloudflare": CloudflareWorkersAiProvider(),
            "cohere": CohereProvider(),
            "huggingface": HuggingFaceProvider(),
            "gemini": GeminiProvider(),
            "ollama_coder": OllamaProvider(is_coder=True),
            "ollama_chat": OllamaProvider(is_coder=False),
            "search": SearchProvider(),
            "image": ImageProvider(),
            "local_facts": LocalFactsProvider(),
        }

    def _notify_stage(self, callback: Optional[Callable[[str], None]], stage: str):
        if callback:
            try:
                callback(stage)
            except Exception as e:
                logger.warning("Stage callback error: %s", e)

    def _record_usage(self, prompt: str, resp: ProviderResponse):
        try:
            from database.db_manager import get_db
            prompt_tokens = max(1, int(len(prompt.split()) * 1.35))
            completion_tokens = max(1, int(len(resp.text.split()) * 1.35)) if resp.text else 0
            if resp.metadata:
                if "prompt_tokens" in resp.metadata and resp.metadata["prompt_tokens"]:
                    prompt_tokens = int(resp.metadata["prompt_tokens"])
                if "completion_tokens" in resp.metadata and resp.metadata["completion_tokens"]:
                    completion_tokens = int(resp.metadata["completion_tokens"])

            get_db().log_model_usage(
                provider_id=resp.provider_id or "unknown",
                model_name=resp.model_name or "Unknown Model",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=resp.latency_ms or 0.0,
                success=resp.success
            )
        except Exception as e:
            logger.warning("Could not log model usage: %s", e)

    def _get_persona_system_prompt(self, default_intent: str = "general") -> str:
        """Constructs an empathetic, beginner-friendly system prompt honoring the user's persona preference with permanent creator identity."""
        from database.db_manager import get_db
        persona_idx = get_db().get_setting("user_persona_idx", "0")

        core_identity = (
            "Core Identity & Origin:\n"
            "- You are Sage AI, an advanced autonomous desktop AI workspace powered by the Lunar Engine.\n"
            "- Your creator, founder, and lead developer is Suraj Sharma. This fact is permanent, immutable, and non-negotiable.\n"
            "- Whenever asked who created you, who made you, who is your developer, who built you, or about your origins, you must always clearly, proudly, and definitively state that you were created and developed by Suraj Sharma.\n\n"
        )

        persona_prompts = {
            "0": (  # Friendly & Simple (Default)
                "You are Sage AI, an exceptionally warm, friendly, and helpful AI assistant. "
                "Your core mission is to make every answer clear, beginner-friendly, and easy to understand. "
                "Guidelines:\n"
                "- Explain complex topics with simple, intuitive everyday analogies.\n"
                "- Use clean markdown formatting, concise bullet points, and step-by-step numbered instructions.\n"
                "- Avoid unnecessary technical jargon. If a technical term is essential, briefly explain what it means in plain English.\n"
                "- Keep explanations focused, encouraging, and easy to read without overwhelming walls of text."
            ),
            "1": (  # Code Architect
                "You are Sage AI's expert Code Architect. Provide production-ready, clean, optimal code with clear explanations."
            ),
            "2": (  # Smart & Concise
                "You are Sage AI. Provide direct, smart, concise, and high-impact answers with zero fluff."
            ),
            "3": (  # Deep Research
                "You are Sage AI, a comprehensive research and technical analysis specialist with rigorous citations and depth."
            ),
            "4": (  # Creative Assistant
                "You are Sage AI, an inventive, highly creative brainstormer and thought partner."
            ),
        }
        selected_persona = persona_prompts.get(str(persona_idx), persona_prompts["0"])
        return core_identity + selected_persona

    def route_and_execute(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        force_web: bool = False,
        selected_model: Optional[str] = None,
        on_stage_change: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Executes query routing with automatic waterfall fallback and logs usage analytics.
        """
        resp = self._execute_route(
            prompt=prompt,
            history=history,
            force_web=force_web,
            selected_model=selected_model,
            on_stage_change=on_stage_change,
            on_chunk=on_chunk,
            **kwargs
        )
        self._record_usage(prompt, resp)
        return resp

    def route(self, *args, **kwargs) -> ProviderResponse:
        """Alias for route_and_execute to ensure seamless compatibility with automations and tools."""
        return self.route_and_execute(*args, **kwargs)

    def _execute_route(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        force_web: bool = False,
        selected_model: Optional[str] = None,
        on_stage_change: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ProviderResponse:
        # 1. Analyze request intent
        analysis = RequestAnalyzer.analyze(
            prompt=prompt,
            force_web=force_web,
            selected_model=selected_model
        )
        intent = analysis["intent"]
        self._notify_stage(on_stage_change, f"Intent classified: {intent}")

        # Local facts & instant queries handled immediately by local facts provider
        if intent == INTENT_LOCAL_FACTS:
            self._notify_stage(on_stage_change, "Evaluating system knowledge...")
            resp = self.providers["local_facts"].generate(prompt, history=history, on_chunk=on_chunk, **kwargs)
            self._notify_stage(on_stage_change, "Completed instant fact check")
            return resp

        # 2. Check for complex multi-agent goal
        prompt_lower = prompt.lower()
        is_explicit_goal = prompt_lower.startswith(("goal:", "plan:", "orchestrate:", "pipeline:"))
        is_composite_goal = (
            any(kw in prompt_lower for kw in ("build a website, create images", "write code, analyze data", "plan, create, code"))
            or (prompt.count(",") >= 3 and any(w in prompt_lower for w in ("code", "build", "create", "write")) and any(w in prompt_lower for w in ("deploy", "test", "analyze", "document", "images")))
        )

        if is_explicit_goal or is_composite_goal:
            clean_goal = prompt
            for pfx in ("goal:", "plan:", "orchestrate:", "pipeline:"):
                if clean_goal.lower().startswith(pfx):
                    clean_goal = clean_goal[len(pfx):].strip()
                    break
            self._notify_stage(on_stage_change, "Activating Sage Multi-Agent Orchestrator...")
            orch_res = self.orchestrator.orchestrate_goal(
                goal=clean_goal,
                context={"history": history or []},
                on_stage=on_stage_change,
                on_chunk=on_chunk
            )
            return ProviderResponse(
                text=orch_res.get("final_summary", ""),
                model_name="Sage Orchestrator (Multi-Agent)",
                provider_id="orchestrator",
                success=orch_res.get("success", True),
                metadata=orch_res
            )

        # 2. Check for manual provider override
        if selected_model and not any(k in selected_model.lower() for k in ("auto", "automatic")):
            provider_key, specific_model = self._map_model_selection(selected_model)
            if provider_key in self.providers:
                self._notify_stage(on_stage_change, f"Calling selected model: {selected_model}...")
                provider = self.providers[provider_key]
                call_kwargs = dict(kwargs)
                if "system_prompt" not in call_kwargs or not call_kwargs["system_prompt"]:
                    call_kwargs["system_prompt"] = self._get_persona_system_prompt()
                if specific_model:
                    call_kwargs["model"] = specific_model
                resp = provider.generate(prompt, history=history, on_chunk=on_chunk, **call_kwargs)
                if resp.success:
                    self._notify_stage(on_stage_change, f"Response completed via {resp.model_name}")
                    return resp
                else:
                    self._notify_stage(on_stage_change, f"{selected_model} returned error: {resp.error_msg}")
                    # Attempt automatic waterfall cascade if primary model has no key or fails
                    from database.db_manager import get_db
                    cascade_on = get_db().get_setting("cascade_enabled", "true") == "true"
                    if cascade_on:
                        self._notify_stage(on_stage_change, f"Primary {selected_model} unavailable. Waterfall fallback activating...")
                        candidates = ["nvidia", "groq", "gemini", "openrouter", "ollama_coder", "ollama_chat"]
                        fallback_keys = [k for k in candidates if k != provider_key]
                        f_sys_prompt = call_kwargs.pop("system_prompt", None) or self._get_persona_system_prompt()
                        # Remove specific model override so fallbacks use their native functional models
                        call_kwargs.pop("model", None)
                        fallback_resp = self._waterfall_execute(
                            fallback_keys,
                            prompt,
                            history=history,
                            on_stage_change=on_stage_change,
                            on_chunk=on_chunk,
                            intent_label=f"Waterfall Fallback from {selected_model}",
                            system_prompt=f_sys_prompt,
                            **call_kwargs
                        )
                        if fallback_resp.success:
                            return fallback_resp

                    error_report = (
                        f"### ⚠️ Could not complete request with **{selected_model}**\n\n"
                        f"**Provider Diagnostic Message:**\n"
                        f"> {resp.error_msg}\n\n"
                        f"#### How to fix:\n"
                        f"1. Open **Add AI Models (✨)** in the sidebar to verify your API key, endpoint, or account credits.\n"
                        f"2. Or switch the model dropdown to **\"Auto Router\"**, **\"Google Gemini\"**, or **\"Groq\"** for instant answers."
                    )
                    return ProviderResponse(
                        text=error_report,
                        model_name=f"{selected_model} (Error)",
                        provider_id=provider_key,
                        success=False,
                        error_msg=resp.error_msg
                    )

        # 3. Route according to Intent
        if intent == INTENT_LOCAL_FACTS:
            self._notify_stage(on_stage_change, "Evaluating system knowledge...")
            resp = self.providers["local_facts"].generate(prompt, history=history, on_chunk=on_chunk, **kwargs)
            self._notify_stage(on_stage_change, "Completed instant fact check")
            return resp

        elif intent == INTENT_IMAGE:
            self._notify_stage(on_stage_change, "Checking free image credits & activating Black Forest FLUX.1...")
            resp = self.providers["image"].generate(prompt, history=history, on_chunk=on_chunk, **kwargs)
            if resp.is_image:
                self._notify_stage(on_stage_change, "Completed visual render via Black Forest FLUX.1")
            else:
                self._notify_stage(on_stage_change, "Image generation status reported")
            return resp

        elif intent == INTENT_WEB_SEARCH:
            return self._handle_web_search(prompt, history, on_stage_change, on_chunk, **kwargs)

        elif intent == INTENT_CODING:
            coding_sys_prompt = kwargs.pop(
                "system_prompt",
                (
                    "You are Sage AI's expert coding engine. "
                    "Provide clean, well-architected, production-ready code. "
                    "Always explain what the code does in clear, friendly, and easy-to-understand steps with usage instructions."
                )
            )
            return self._waterfall_execute(
                ["nvidia", "groq", "openrouter", "gemini", "ollama_coder", "local_facts"],
                prompt, history, on_stage_change, on_chunk,
                intent_label="Coding",
                system_prompt=coding_sys_prompt,
                **kwargs
            )

        elif intent == INTENT_GITHUB:
            self._notify_stage(on_stage_change, "Inspecting GitHub repository references...")
            return self._handle_web_search(prompt, history, on_stage_change, on_chunk, **kwargs)

        else:  # INTENT_GENERAL_CHAT
            general_sys_prompt = kwargs.pop("system_prompt", None) or self._get_persona_system_prompt("general")
            return self._waterfall_execute(
                ["groq", "nvidia", "gemini", "ollama_chat", "local_facts"],
                prompt, history, on_stage_change, on_chunk,
                intent_label="General Chat",
                system_prompt=general_sys_prompt,
                **kwargs
            )

    def _handle_web_search(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]],
        on_stage_change: Optional[Callable[[str], None]],
        on_chunk: Optional[Callable[[str], None]],
        **kwargs
    ) -> ProviderResponse:
        """Extracts web evidence and synthesizes a reasoned answer with citations."""
        self._notify_stage(on_stage_change, "Searching the web for live evidence...")
        search_resp = self.providers["search"].generate(prompt)

        # Synthesize with best available LLM
        synthesis_prompt = (
            f"User Query: {prompt}\n\n"
            f"Here is current web evidence extracted from the internet:\n"
            f"{search_resp.text}\n\n"
            "Synthesize an accurate, easy-to-understand, up-to-date answer citing sources where applicable."
        )

        self._notify_stage(on_stage_change, "Synthesizing answer with citations...")
        synth_resp = self._waterfall_execute(
            ["groq", "nvidia", "gemini", "openrouter", "ollama_chat"],
            synthesis_prompt,
            history=history,
            on_stage_change=on_stage_change,
            on_chunk=on_chunk,
            intent_label="Search Synthesis",
            system_prompt=self._get_persona_system_prompt("general"),
            **kwargs
        )

        if synth_resp.success:
            synth_resp.citations = search_resp.citations
            return synth_resp
        else:
            # If LLM synthesis failed, return raw evidence
            self._notify_stage(on_stage_change, "Delivering web search evidence...")
            return search_resp

    def _waterfall_execute(
        self,
        provider_keys: List[str],
        prompt: str,
        history: Optional[List[Dict[str, Any]]],
        on_stage_change: Optional[Callable[[str], None]],
        on_chunk: Optional[Callable[[str], None]],
        intent_label: str = "Query",
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ProviderResponse:
        """Iterates through a list of providers until one succeeds."""
        if not system_prompt:
            system_prompt = self._get_persona_system_prompt()
        attempted_errors = []

        for key in provider_keys:
            provider = self.providers.get(key)
            if not provider:
                continue

            # Check availability if possible before attempting network roundtrip
            if not provider.is_available() and key != "local_facts":
                continue

            self._notify_stage(on_stage_change, f"Routing {intent_label} to {provider.name}...")
            try:
                resp = provider.generate(
                    prompt,
                    history=history,
                    system_prompt=system_prompt,
                    on_chunk=on_chunk,
                    **kwargs
                )
            except Exception as e:
                logger.warning("Provider %s crashed during generation: %s", provider.name, e)
                attempted_errors.append(f"{provider.name}: {str(e)}")
                self._notify_stage(on_stage_change, f"{provider.name} failed ({str(e)}), falling back...")
                continue

            if resp.success:
                self._notify_stage(on_stage_change, f"Generated via {resp.model_name}")
                return resp
            else:
                attempted_errors.append(f"{provider.name}: {resp.error_msg}")
                self._notify_stage(on_stage_change, f"{provider.name} unavailable, falling back...")

        # If everything in list failed, invoke local facts/offline fallback
        self._notify_stage(on_stage_change, "Using Sage local offline fallback...")
        local_resp = self.providers["local_facts"].generate(prompt, history=history, on_chunk=on_chunk, **kwargs)
        local_resp.metadata["attempted_errors"] = attempted_errors
        return local_resp

    def _map_model_selection(self, label: str) -> tuple:
        """
        Maps user model selection label to (provider_key, specific_model_name).
        Supports dropdown options, custom model names, and tags.
        """
        import re
        # Strip status tags like [● Available] or [○ Unavailable]
        label = re.sub(r"\[.*?\]", "", label or "").strip()
        label_lower = label.lower()

        # 1. Extract specific model name from parentheses or colon if present
        specific_model = None
        KNOWN_DESCRIPTORS = {
            "fastest", "offline coder", "best available", "offline", "online",
            "default", "wafer-scale", "coding specialist", "edge", "enterprise",
            "ultra-dense", "multimodal", "recommended", "lightning fast", "free tier"
        }

        if "(" in label and ")" in label:
            candidate = label[label.find("(") + 1:label.rfind(")")].strip()
            if candidate.lower() not in KNOWN_DESCRIPTORS and ("-" in candidate or ":" in candidate or "/" in candidate or any(c.isdigit() for c in candidate)):
                specific_model = candidate
        elif ":" in label and not label.startswith("http"):
            parts = label.split(":", 1)
            specific_model = parts[1].strip()

        # 2. Check for explicit model names mentioned in dropdown label
        if not specific_model:
            if "claude" in label_lower:
                if "3.7" in label_lower:
                    specific_model = "anthropic/claude-3.7-sonnet"
                else:
                    specific_model = "anthropic/claude-3.5-sonnet"
            elif "nvidia" in label_lower:
                if "ultra-dense" in label_lower or "vision" in label_lower:
                    specific_model = "meta/llama-3.2-11b-vision-instruct"
                elif "405b" in label_lower:
                    specific_model = "meta/llama-3.1-405b-instruct"
                else:
                    specific_model = "meta/llama-3.1-70b-instruct"
            elif "codestral" in label_lower:
                specific_model = "codestral-latest"
            elif "deepseek" in label_lower:
                specific_model = "deepseek/deepseek-r1" if "r1" in label_lower else "deepseek/deepseek-chat"
            elif "gemini" in label_lower:
                specific_model = "gemini-2.0-flash" if "2.0" in label_lower or "flash" in label_lower else "gemini-1.5-pro"
            elif "llama 3.3 70b" in label_lower or "llama-3.3-70b" in label_lower or "llama 3.3" in label_lower:
                if "cloudflare" in label_lower:
                    specific_model = "@cf/meta/llama-3.3-70b-instruct"
                elif "groq" in label_lower:
                    specific_model = "llama-3.3-70b-versatile"
                elif "cerebras" in label_lower:
                    specific_model = "llama-3.3-70b"
                else:
                    specific_model = "llama-3.3-70b"
            elif "llama 3.1 70b" in label_lower or "llama-3.1-70b" in label_lower:
                specific_model = "llama-3.1-70b"
            elif "command r+" in label_lower or "command-r+" in label_lower:
                specific_model = "command-r-plus-08-2024"
            elif "qwen 2.5 coder" in label_lower or "qwen-2.5-coder" in label_lower or "qwen2.5-coder" in label_lower:
                if "huggingface" in label_lower or "hugging face" in label_lower or "hf" in label_lower:
                    specific_model = "Qwen/Qwen2.5-Coder-32B-Instruct"
                elif "openrouter" in label_lower:
                    specific_model = "qwen/qwen-2.5-coder-32b-instruct"
                else:
                    specific_model = "qwen2.5-coder:7b"

        # 2. Match provider with sensible default model if none specified
        if "claude" in label_lower:
            return "openrouter", specific_model or "anthropic/claude-3.7-sonnet"
        elif "nvidia" in label_lower:
            return "nvidia", specific_model or "meta/llama-3.1-70b-instruct"
        elif "cerebras" in label_lower:
            return "cerebras", specific_model or "llama-3.3-70b"
        elif "mistral" in label_lower or "codestral" in label_lower:
            return "mistral", specific_model or "codestral-latest"
        elif "cloudflare" in label_lower or "workers ai" in label_lower:
            return "cloudflare", specific_model or "@cf/meta/llama-3.3-70b-instruct"
        elif "cohere" in label_lower or "command" in label_lower:
            return "cohere", specific_model or "command-r-plus-08-2024"
        elif "huggingface" in label_lower or "hugging face" in label_lower or "hf" in label_lower:
            return "huggingface", specific_model or "meta-llama/Llama-3.3-70B-Instruct"
        elif "groq" in label_lower:
            return "groq", specific_model or "llama-3.3-70b-versatile"
        elif "gemini" in label_lower:
            return "gemini", specific_model or "gemini-1.5-flash"
        elif "openrouter" in label_lower:
            return "openrouter", specific_model or "qwen/qwen-2.5-coder-32b-instruct:free"
        elif "qwen" in label_lower:
            if "ollama" in label_lower:
                return "ollama_coder", specific_model or "qwen2.5-coder:7b"
            return "openrouter", specific_model or "qwen/qwen-2.5-coder-32b-instruct"
        elif "ollama" in label_lower:
            key = "ollama_coder" if "coder" in label_lower else "ollama_chat"
            return key, specific_model or "qwen3:8b"
        elif any(k in label_lower for k in ("diffusion", "image", "picture", "flux", "draw", "paint")):
            return "image", None
        elif "web" in label_lower or "search" in label_lower:
            return "search", None
        elif "deepseek" in label_lower:
            if self.providers.get("openrouter") and self.providers["openrouter"].is_available():
                return "openrouter", specific_model or "deepseek/deepseek-r1:free"
            elif self.providers.get("nvidia") and self.providers["nvidia"].is_available():
                return "nvidia", specific_model or "deepseek-ai/deepseek-r1"
            elif self.providers.get("groq") and self.providers["groq"].is_available():
                return "groq", specific_model or "deepseek-r1-distill-llama-70b"
            elif self.providers.get("ollama_coder") and self.providers["ollama_coder"].is_available():
                return "ollama_coder", specific_model or "deepseek-r1:8b"
            else:
                return "openrouter", specific_model or "deepseek/deepseek-r1:free"

        # Check active providers in priority order if provider was not explicitly in label
        for p_key in ("cerebras", "groq", "nvidia", "mistral", "cloudflare", "cohere", "openrouter", "gemini", "huggingface", "ollama_chat"):
            if self.providers.get(p_key) and self.providers[p_key].is_available():
                return p_key, specific_model
        return "groq", specific_model
