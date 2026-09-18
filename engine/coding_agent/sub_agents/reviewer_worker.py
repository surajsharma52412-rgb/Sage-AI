"""
Code Reviewer Worker for SAGE Coding Agent.
Internal worker specialized in:
- Clean architecture & DRY principle compliance
- Maintainability, function length, and code complexity
- Error handling completeness & exception swallowing checks
- Code review summary & improvement task generation
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .base_sub_agent import BaseSubAgent

logger = logging.getLogger(__name__)


class ReviewerWorker(BaseSubAgent):
    """Specialized internal worker for architectural code review and maintainability auditing."""

    def __init__(self, context_mgr, tools, model_router=None):
        super().__init__(role="reviewer", name="Code Reviewer", context_mgr=context_mgr, tools=tools, model_router=model_router)

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        instruction = task.get("instruction") or task.get("description", "")

        from ..code_reviewer import CodeReviewer
        reviewer = CodeReviewer(self.tools)
        review_res = reviewer.review_codebase()

        review_report = (
            f"# Code Quality & Maintainability Review\n\n"
            f"- **Overall Quality Score**: {review_res.get('quality_score', 100)}/100\n"
            f"- **Review Status**: {'Approved' if review_res.get('passed') else 'Changes Recommended'}\n"
            f"- **Files Reviewed**: {review_res.get('total_files_reviewed', 0)}\n\n"
            f"## Recommendations\n"
        )
        if review_res.get("findings"):
            for f in review_res["findings"]:
                review_report += f"- `{f['file']}:{f['line']}`: {f['issue']} ({f['category'].upper()})\n"
        else:
            review_report += "- Code adheres to clean architecture principles and proper error handling.\n"

        return {
            "success": review_res.get("passed", True),
            "role": self.role,
            "agent_name": self.name,
            "summary": review_report,
            "generated_files": [{
                "language": "markdown",
                "path": "docs/code_review.md",
                "content": review_report
            }],
            "quality_score": review_res.get("quality_score", 100)
        }
