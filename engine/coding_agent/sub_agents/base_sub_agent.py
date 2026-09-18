"""
Base Sub-Agent for SAGE Coding Agent Architecture (v6).
Provides specialized coding sub-agents with:
- Structured prompt compilation
- Provider & Model selection via CodingModelRouter
- Code block and file extraction from markdown
- Access to ToolEcosystem, ContextFileManager, and SafetyController
- Fallback mock responses for deterministic testing and offline capability
"""
import re
import logging
from typing import Dict, Any, List, Optional, Callable

from ..model_router import CodingModelRouter
from ..context_manager import ContextFileManager
from ..tool_ecosystem import ToolEcosystem

logger = logging.getLogger(__name__)


class BaseSubAgent:
    """Base class for the 6 specialized coding sub-agents."""

    def __init__(
        self,
        role: str,
        name: str,
        context_mgr: ContextFileManager,
        tools: ToolEcosystem,
        model_router: Optional[CodingModelRouter] = None
    ):
        self.role = role
        self.name = name
        self.context_mgr = context_mgr
        self.tools = tools
        self.model_router = model_router or CodingModelRouter()

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Sub-agent task execution logic to be overridden by specialized agents."""
        raise NotImplementedError("Subclasses must implement execute()")

    def extract_code_blocks(self, markdown_text: str) -> List[Dict[str, Any]]:
        """Extracts code blocks with language and target filenames from markdown."""
        pattern = r"```([a-zA-Z0-9_\-\+]*)\s*(?:file(?:name)?:\s*([^\n]+))?\n([\s\S]*?)```"
        blocks = []
        for match in re.finditer(pattern, markdown_text):
            lang = match.group(1).strip() if match.group(1) else "text"
            path = match.group(2).strip() if match.group(2) else ""
            content = match.group(3)
            blocks.append({
                "language": lang,
                "path": path,
                "content": content
            })
        return blocks

    def call_llm(
        self,
        prompt: str,
        system_prompt: str,
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None,
        force_offline: bool = False
    ) -> Dict[str, Any]:
        """Invokes LLM via the provided caller or router fallback."""
        if llm_caller_fn:
            preferred = self.model_router.get_preferred_providers(self.role, force_offline=force_offline)
            try:
                return llm_caller_fn(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    preferred_providers=preferred
                )
            except Exception as e:
                logger.warning("Subagent %s LLM call error: %s", self.name, e)

        # Fallback offline deterministic generation
        return self._generate_offline_fallback(prompt)

    def _generate_offline_fallback(self, prompt: str) -> Dict[str, Any]:
        """Provides a robust offline template if no LLM connection is active."""
        return {
            "success": True,
            "text": f"/* SAGE {self.name} Offline Implementation */\n// Generated for: {prompt[:80]}",
            "model_name": "Sage-Offline-Coder",
            "provider_id": "offline"
        }
