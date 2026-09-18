"""
Architect Agent for SAGE Coding Agent Architecture (v6).
Responsibilities:
- System design & component boundaries
- High-level architecture specification
- Tech stack selection and library compatibility
- Data schemas and domain models
- Scalability & security planning
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .base_sub_agent import BaseSubAgent

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseSubAgent):
    """Specialized in system architecture, data models, and API blueprints."""

    def __init__(self, context_mgr, tools, model_router=None):
        super().__init__(role="architect", name="Architect Agent", context_mgr=context_mgr, tools=tools, model_router=model_router)

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        instruction = task.get("instruction", "")
        system_prompt = (
            "You are Sage AI's Chief Software Architect. "
            "Design clean, scalable, production-grade system architectures. "
            "Define modular component boundaries, data models, schemas, and API contracts. "
            "Use clear file headers in code blocks, e.g.:\n"
            "```python file:models.py\n# data models\n```\n"
            "```markdown file:docs/architecture.md\n# System Architecture\n```"
        )

        prompt = (
            f"Architecture Task: {instruction}\n\n"
            "Provide the comprehensive system design, database schemas, and API endpoints specification. "
            "Ensure the architecture is modular and ready for parallel implementation by backend, frontend, and devops agents."
        )

        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, llm_caller_fn=llm_caller_fn)
        content_text = llm_res.get("text", "")
        extracted_files = self.extract_code_blocks(content_text)

        # Fallback template if no files extracted
        if not extracted_files:
            arch_doc = (
                f"# System Architecture Blueprint\n\n"
                f"## 1. System Overview\nTarget: {instruction}\n\n"
                f"## 2. Core Modules\n- Backend API Server\n- Database Persistence Layer\n- Responsive Frontend\n- Containerized Deployment\n\n"
                f"## 3. Data Models\n- User (id, email, password_hash, role, created_at)\n- Entity / Resource Models\n"
            )
            extracted_files.append({
                "language": "markdown",
                "path": "docs/architecture.md",
                "content": arch_doc
            })
            model_code = (
                '"""\nCore Data Models and Schemas.\n"""\n'
                'from dataclasses import dataclass, field\n'
                'from typing import Optional, List\n'
                'from datetime import datetime\n\n\n'
                '@dataclass\n'
                'class User:\n'
                '    id: str\n'
                '    email: str\n'
                '    role: str = "user"\n'
                '    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())\n'
            )
            extracted_files.append({
                "language": "python",
                "path": "models.py",
                "content": model_code
            })

        return {
            "success": True,
            "role": self.role,
            "agent_name": self.name,
            "summary": content_text or "Architecture blueprint and data models generated.",
            "generated_files": extracted_files,
            "architecture_spec": {
                "task_id": task.get("task_id"),
                "files_count": len(extracted_files)
            }
        }
