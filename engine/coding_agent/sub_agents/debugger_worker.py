"""
Debugger Worker for SAGE Coding Agent.
Internal worker specialized in:
- Stack trace parsing & traceback diagnosis
- Isolating exact bug locations & root causes
- Generating targeted, minimal code patches
- Regression prevention
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .base_sub_agent import BaseSubAgent

logger = logging.getLogger(__name__)


class DebuggerWorker(BaseSubAgent):
    """Specialized internal worker for diagnosing failures and writing minimal bug fixes."""

    def __init__(self, context_mgr, tools, model_router=None):
        super().__init__(role="debugger", name="Debugger", context_mgr=context_mgr, tools=tools, model_router=model_router)

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        instruction = task.get("instruction") or task.get("description", "")
        error_context = task.get("error_context") or task.get("error_state", "")

        system_prompt = (
            "You are Sage AI's Expert Debugger. "
            "Analyze the failure diagnostic, locate the root cause in the affected file, "
            "and output a minimal, robust patch. Avoid unnecessary rewrites. "
            "Specify the file path clearly in markdown code fences, e.g.:\n"
            "```python file:path/to/file.py\n# fixed code\n```"
        )

        prompt = (
            f"Bug Fix Request: {instruction}\n\n"
            f"Error & Traceback:\n{error_context or 'Runtime error reported during testing.'}\n\n"
            "Provide the complete, corrected file content that resolves the failure."
        )

        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, llm_caller_fn=llm_caller_fn)
        content_text = llm_res.get("text", "")
        extracted_files = self.extract_code_blocks(content_text)

        return {
            "success": True,
            "role": self.role,
            "agent_name": self.name,
            "summary": content_text or "Bug diagnosed and patch generated.",
            "generated_files": extracted_files
        }
