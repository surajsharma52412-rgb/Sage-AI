"""
Content Agent for Sage Multi-Agentic AI Architecture.
Capabilities:
- Write articles
- Create documentation
- Generate presentations
- Prepare emails
- Summarize content
- Multi-language support
"""
import logging
from typing import Dict, Any, Optional, Callable

from config import AGENT_CONTENT
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ContentAgent(BaseAgent):
    """Specialized in prose composition, technical documentation, presentations, emails, and translations."""

    def __init__(self):
        super().__init__(name=AGENT_CONTENT, role_id="content")

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        instruction = task_input.get("instruction") or task_input.get("query") or ""
        content_type = task_input.get("content_type", "general")  # "doc", "email", "article", "slides"
        task_id = (context or {}).get("task_id")

        if on_stage:
            on_stage("📑 Content Agent: Crafting high-quality documentation & content...")
        self.log("Crafting written content/documentation", task_id=task_id, details={"instruction": instruction})

        # Inject context from other agents if available in Shared Memory
        shared_memory_snapshot = self.shared_memory.get_all()
        supporting_context = ""
        for k, v in list(shared_memory_snapshot.items())[:3]:
            if isinstance(v, dict) and "summary" in v:
                supporting_context += f"\nReference Context ({k}):\n{str(v['summary'])[:400]}\n"

        system_prompt = (
            "You are Sage AI's expert Content Agent. You write clear, compelling, polished content. "
            "Whether producing comprehensive documentation, executive briefs, slide outlines, emails, "
            "or articles, ensure tone is professional, formatting is clean with markdown headings, "
            "and information is organized logically."
        )

        prompt = (
            f"Content Request: {instruction}\n"
            f"Format Category: {content_type}\n"
            f"{supporting_context}\n"
            "Write the complete, publication-ready text."
        )

        llm_res = self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            on_chunk=on_chunk,
            preferred_providers=["groq", "gemini", "nvidia", "openrouter", "ollama", "local_facts"]
        )

        final_text = llm_res.get("text", "")

        self.send_bus_message(
            to_agent="all",
            message_type="content_drafted",
            content=f"Drafted {content_type} for: '{instruction[:40]}...'",
            task_id=task_id
        )

        return {
            "success": True,
            "agent": self.name,
            "summary": final_text,
            "content_type": content_type,
            "deliverables": [
                {
                    "type": "written_content",
                    "title": f"Content Document: {instruction[:40]}",
                    "content": final_text
                }
            ]
        }
