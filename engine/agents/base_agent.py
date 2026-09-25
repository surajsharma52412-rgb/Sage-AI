"""
Base Agent for Sage Multi-Agentic AI Architecture.
Abstract base class for all 7 specialized agents, providing unified access
to shared resources, tools, communication bus, audit logging, and LLM inference.
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List

from config import AGENT_METADATA
from engine.shared_resources.shared_memory import get_shared_memory
from engine.shared_resources.knowledge_base import get_knowledge_base
from engine.shared_resources.vector_db import get_vector_db
from engine.shared_resources.project_workspace import get_project_workspace
from engine.shared_resources.communication_bus import get_comm_bus
from engine.tools.tool_registry import get_tool_registry
from engine.governance.audit_logger import get_audit_logger
from engine.governance.quality_evaluator import get_quality_evaluator
from engine.governance.cost_tracker import get_cost_tracker

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for specialized AI agents."""

    def __init__(self, name: str, role_id: str):
        self.name = name
        self.role_id = role_id
        self.metadata = AGENT_METADATA.get(name, {})
        self.capabilities = self.metadata.get("capabilities", [])

        # Shared Resources Layer
        self.shared_memory = get_shared_memory()
        self.knowledge_base = get_knowledge_base()
        self.vector_db = get_vector_db()
        self.workspace = get_project_workspace()
        self.comm_bus = get_comm_bus()

        # Tools & Governance Layers
        self.tools = get_tool_registry()
        self.audit = get_audit_logger()
        self.evaluator = get_quality_evaluator()
        self.cost_tracker = get_cost_tracker()

    def log(self, action: str, task_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Records agent activity to audit store."""
        self.audit.log_action(self.name, action, task_id=task_id, details=details)

    def send_bus_message(
        self,
        to_agent: str,
        message_type: str,
        content: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatches an inter-agent message over the communication bus."""
        return self.comm_bus.send_message(
            from_agent=self.name,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            task_id=task_id
        )

    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        selected_model: Optional[str] = None,
        preferred_providers: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes unified LLM inference with waterfall fallback, streaming, and cost tracking.
        """
        from engine.providers.groq_provider import GroqProvider
        from engine.providers.nvidia_provider import NvidiaNimProvider
        from engine.providers.gemini_provider import GeminiProvider
        from engine.providers.openrouter_provider import OpenRouterProvider
        from engine.providers.ollama_provider import OllamaProvider
        from engine.providers.local_facts_provider import LocalFactsProvider

        providers = {
            "groq": GroqProvider(),
            "nvidia": NvidiaNimProvider(),
            "gemini": GeminiProvider(),
            "openrouter": OpenRouterProvider(),
            "ollama": OllamaProvider(is_coder="coder" in self.role_id),
            "local_facts": LocalFactsProvider()
        }

        # Append learned directives or persistent memories if provided
        mem_ctx = kwargs.pop("memory_context", None)
        if mem_ctx:
            if system_prompt:
                system_prompt = f"{system_prompt}\n\n[USER INSTRUCTIONS & PERSISTENT MEMORIES]:\n{mem_ctx}"
            else:
                system_prompt = f"[USER INSTRUCTIONS & PERSISTENT MEMORIES]:\n{mem_ctx}"

        # Default waterfall chain
        chain = preferred_providers or ["groq", "nvidia", "gemini", "openrouter", "ollama", "local_facts"]

        from engine.zero_cost_guard import get_zero_cost_guard
        guard = get_zero_cost_guard()

        start_time = time.time()
        for p_key in chain:
            provider = providers.get(p_key)
            if not provider:
                continue

            # Zero-Cost Guard: verify candidate model / provider is strictly 0 Rs
            target_model = kwargs.get("model") or getattr(provider, "default_model", None) or p_key
            if not guard.is_zero_cost(str(target_model), p_key):
                logger.info("🛡️ Zero-Cost Guard: Agent skipping paid candidate %s on %s (> 0 Rs)", target_model, p_key)
                continue

            # Skip if credentials not available unless local_facts
            if not provider.is_available() and p_key != "local_facts":
                continue

            try:
                resp = provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    on_chunk=on_chunk,
                    **kwargs
                )
                if resp.success:
                    latency_ms = round((time.time() - start_time) * 1000.0, 2)
                    self.cost_tracker.record_usage(
                        agent_name=self.name,
                        provider_id=resp.provider_id or p_key,
                        model_name=resp.model_name or "LLM",
                        prompt_text=prompt,
                        completion_text=resp.text or "",
                        latency_ms=latency_ms,
                        success=True
                    )
                    return {
                        "success": True,
                        "text": resp.text,
                        "model_name": resp.model_name,
                        "provider_id": resp.provider_id or p_key,
                        "latency_ms": latency_ms,
                        "citations": resp.citations,
                        "metadata": resp.metadata
                    }
            except Exception as e:
                logger.warning("Provider %s failed for agent %s: %s", p_key, self.name, e)

        # Fallback to local facts
        fallback_resp = providers["local_facts"].generate(prompt, on_chunk=on_chunk, **kwargs)
        return {
            "success": fallback_resp.success,
            "text": fallback_resp.text,
            "model_name": fallback_resp.model_name,
            "provider_id": "local_facts",
            "latency_ms": round((time.time() - start_time) * 1000.0, 2),
            "citations": [],
            "metadata": {}
        }

    @abstractmethod
    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes a task step assigned to this specialized agent.
        Must return a structured dictionary containing status, deliverables, and summary.
        """
        pass
