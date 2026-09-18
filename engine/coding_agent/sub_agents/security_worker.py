"""
Security Reviewer Worker for SAGE Coding Agent.
Internal worker specialized in:
- Secret & API key exposure auditing
- SQL injection, eval/exec, and unsafe subprocess detection
- Auth token verification & password hashing auditing
- Network security & CORS policy checks
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .base_sub_agent import BaseSubAgent

logger = logging.getLogger(__name__)


class SecurityWorker(BaseSubAgent):
    """Specialized internal worker for security compliance, vulnerability analysis, and secret prevention."""

    def __init__(self, context_mgr, tools, model_router=None):
        super().__init__(role="security", name="Security Reviewer", context_mgr=context_mgr, tools=tools, model_router=model_router)

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        instruction = task.get("instruction") or task.get("description", "")

        # Perform local security scan via CodeReviewer
        from ..code_reviewer import CodeReviewer
        reviewer = CodeReviewer(self.tools)
        review_res = reviewer.review_codebase()

        findings_text = "\n".join(
            f"- [{f['severity']}] {f['file']}:{f['line']} — {f['issue']}"
            for f in review_res.get("findings", [])
        ) or "No security issues identified."

        audit_report = (
            f"# Security Audit Report\n\n"
            f"- **Status**: {'PASSED' if review_res.get('passed') else 'FAILED'}\n"
            f"- **Security Score**: {review_res.get('quality_score', 100)}/100\n"
            f"- **Files Audited**: {review_res.get('total_files_reviewed', 0)}\n\n"
            f"## Findings\n{findings_text}\n"
        )

        return {
            "success": review_res.get("passed", True),
            "role": self.role,
            "agent_name": self.name,
            "summary": audit_report,
            "generated_files": [{
                "language": "markdown",
                "path": "docs/security_audit.md",
                "content": audit_report
            }],
            "findings": review_res.get("findings", [])
        }
