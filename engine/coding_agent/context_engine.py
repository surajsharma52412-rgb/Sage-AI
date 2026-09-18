"""
Context Engine for SAGE Autonomous Coding Agent.
Selects the minimum useful context to solve software tasks and prevents token overflow.
Context Priority:
1. Current task & user instructions
2. Target file(s) under modification
3. Relevant functions & classes (extracted by CodebaseIndexer)
4. Direct dependencies & import signatures
5. Related modules & schemas
6. Relevant test suites
7. Project architecture summary
8. Previous task decisions (ADRs) & known fixes
9. General project metadata
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from .codebase_indexer import CodebaseIndexer
from .project_analyzer import ProjectAnalyzer
from .long_context_memory import LongContextMemory

logger = logging.getLogger(__name__)


class ContextEngine:
    """Builds focused, token-budgeted prompt contexts tailored to specific sub-agent tasks."""

    def __init__(
        self,
        indexer: CodebaseIndexer,
        analyzer: ProjectAnalyzer,
        memory: LongContextMemory,
        max_context_tokens: int = 4000
    ):
        self.indexer = indexer
        self.analyzer = analyzer
        self.memory = memory
        self.max_context_tokens = max_context_tokens

    def build_task_context(
        self,
        task_instruction: str,
        target_files: Optional[List[str]] = None,
        dep_context: Optional[Dict[str, Any]] = None,
        recent_errors: Optional[str] = None
    ) -> str:
        """
        Assembles prioritized context within strict token bounds (~4 chars/token).
        """
        budget_chars = self.max_context_tokens * 4
        sections: List[Tuple[int, str]] = []  # (priority, content)

        # Priority 1: Current Task & Recent Diagnostics (Highest Priority)
        task_block = f"## 🎯 Active Task\n{task_instruction}\n"
        if recent_errors:
            task_block += f"\n### ⚠️ Recent Failure Diagnostics:\n{recent_errors}\n"
        sections.append((1, task_block))

        # Priority 2: Target File Content (if specified and exists)
        if target_files:
            file_blocks = []
            for tf in target_files[:3]:
                full = self.indexer.workspace_root / tf
                if full.exists() and full.is_file():
                    try:
                        content = full.read_text(encoding="utf-8", errors="replace")
                        if len(content) > 3000:
                            content = content[:3000] + "\n... [Remaining lines truncated for context budget]"
                        file_blocks.append(f"### Target File: `{tf}`\n```\n{content}\n```")
                    except Exception:
                        pass
            if file_blocks:
                sections.append((2, "## 📄 Target File(s)\n" + "\n\n".join(file_blocks)))

        # Priority 3: Relevant Symbols & Snippets (AST extraction)
        snippets = self.indexer.retrieve_relevant_snippets(task_instruction, max_tokens_approx=1200)
        if snippets:
            sections.append((3, f"## 🔍 Relevant Code Symbols\n{snippets}\n"))

        # Priority 4: Dependency Context (Output from upstream DAG tasks)
        if dep_context:
            dep_blocks = []
            for dep_id, dep_res in dep_context.items():
                summary = dep_res.get("summary", "")
                if summary:
                    dep_blocks.append(f"**From `{dep_id}` ({dep_res.get('role', 'upstream')}):**\n{summary[:800]}")
            if dep_blocks:
                sections.append((4, "## 🔗 Upstream Dependencies\n" + "\n\n".join(dep_blocks)))

        # Priority 5: Architectural Decisions & Previous Fixes (ADRs)
        adrs = self.memory.get_technical_decisions()
        prev_solution = self.memory.find_previous_solution(task_instruction)
        mem_blocks = []
        if adrs:
            for a in adrs[-3:]:
                mem_blocks.append(f"- **{a['title']}**: {a['decision']}")
        if prev_solution:
            mem_blocks.append(f"- **Known Solution Match**: {prev_solution.get('solution_summary')}")
        if mem_blocks:
            sections.append((5, "## 💡 Architectural Decisions & Conventions\n" + "\n".join(mem_blocks)))

        # Priority 6: Project Overview (High-level architecture)
        proj_map = self.analyzer.analyze_project()
        arch_block = (
            f"## 🏗️ Project Architecture Overview\n"
            f"- Project Name: {proj_map.get('project_name')}\n"
            f"- Architecture Type: {proj_map.get('architecture_type')}\n"
            f"- Primary Language: {proj_map.get('primary_language')}\n"
            f"- Frameworks: {', '.join(proj_map.get('frameworks', [])) or 'Standard'}\n"
        )
        sections.append((6, arch_block))

        # Assemble strictly respecting budget
        sections.sort(key=lambda x: x[0])  # Sort by priority 1 -> 6
        final_text = ""
        current_len = 0

        for priority, text in sections:
            if current_len + len(text) > budget_chars:
                # Truncate lower priority section to fit budget
                remaining = budget_chars - current_len
                if remaining > 200:
                    final_text += text[:remaining] + "\n... [Context truncated to respect model window]\n\n"
                break
            final_text += text + "\n\n"
            current_len += len(text)

        return final_text.strip()
