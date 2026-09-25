"""
Structured Project Memory & Context Compression for SAGE Autonomous Coding Agent.
Implements Sections 6, 33, and 34 of the Ultimate Master Architecture:
- Structured Project Memory (architecture, schema, decisions, conventions, UI system, bugs, tasks)
- Persistent project memory stored in .sage/project_memory.json
- Context Compression (token-efficient summaries for model prompts)
- Model Handoff Protocol (seamless transfer of execution state between models)
"""
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StructuredProjectMemory:
    """Persistent structured representation of a project's evolution and state."""
    project_name: str = "Unnamed Project"
    purpose: str = ""
    architecture: str = "Modular Architecture"
    tech_stack: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    database_schema: Dict[str, Any] = field(default_factory=dict)
    api_contracts: List[Dict[str, Any]] = field(default_factory=list)
    important_decisions: List[Dict[str, str]] = field(default_factory=list)
    coding_conventions: List[str] = field(default_factory=list)
    ui_design_system: Dict[str, Any] = field(default_factory=dict)
    known_bugs: List[Dict[str, Any]] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    environment_config: Dict[str, str] = field(default_factory=dict)
    last_updated: float = 0.0


class ProjectMemoryManager:
    """
    Manages persistent structured project memory across tasks and sessions.
    Prevents repeated rediscovery of the project, saves tokens via compression,
    and supports zero-loss model handoffs.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.storage_dir = self.workspace_root / ".sage"
        self.memory_file = self.storage_dir / "project_memory.json"
        self.memory: StructuredProjectMemory = self.load_memory()

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.storage_dir = self.workspace_root / ".sage"
        self.memory_file = self.storage_dir / "project_memory.json"
        self.memory = self.load_memory()

    def load_memory(self) -> StructuredProjectMemory:
        """Loads existing project memory from disk, or initializes default."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return StructuredProjectMemory(**data)
            except Exception as e:
                logger.warning("Could not parse %s, initializing fresh memory: %s", self.memory_file, e)

        # Default initialization based on workspace
        mem = StructuredProjectMemory(
            project_name=self.workspace_root.name,
            purpose=f"Software engineering workspace for {self.workspace_root.name}",
            coding_conventions=[
                "PEP 8 standard formatting for Python, ESLint for JS/TS",
                "Explicit return type annotations on public functions",
                "Separation of concerns between business logic, UI, and data storage",
                "Zero hardcoded secrets; use environment variables"
            ],
            ui_design_system={
                "color_palette": "Modern Dark Glassmorphic (Cyan / Indigo / Slate)",
                "motion_fast_ms": 150,
                "motion_med_ms": 240,
                "motion_slow_ms": 360,
                "easing": "cubic-bezier(0.16, 1, 0.3, 1)",
                "reduced_motion": True
            }
        )
        return mem

    def save_memory(self):
        """Persists project memory to .sage/project_memory.json."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.memory), f, indent=2)
        except Exception as e:
            logger.warning("Failed to save project memory: %s", e)

    def record_decision(self, title: str, decision: str, rationale: str = ""):
        """Records an architectural decision record (ADR)."""
        self.memory.important_decisions.append({
            "title": title,
            "decision": decision,
            "rationale": rationale
        })
        self.save_memory()

    def record_task_completion(self, task_desc: str):
        """Marks a task as completed in project memory."""
        if task_desc not in self.memory.completed_tasks:
            self.memory.completed_tasks.append(task_desc)
        if task_desc in self.memory.pending_tasks:
            self.memory.pending_tasks.remove(task_desc)
        self.save_memory()

    def record_pending_tasks(self, tasks: List[str]):
        """Updates pending tasks in memory."""
        for t in tasks:
            if t not in self.memory.pending_tasks and t not in self.memory.completed_tasks:
                self.memory.pending_tasks.append(t)
        self.save_memory()

    def update_tech_stack(self, stack: Dict[str, str]):
        """Updates detected tech stack."""
        self.memory.tech_stack.update(stack)
        self.save_memory()

    def build_compressed_context(
        self,
        current_task: str,
        relevant_files: Optional[List[str]] = None,
        max_tokens: int = 1500
    ) -> str:
        """
        Implements Section 33: Context Compression.
        Maintains a compact project summary to save tokens and focus coding models.
        """
        files_str = ", ".join(relevant_files[:8]) if relevant_files else "None explicitly specified"
        recent_decisions = [
            f"- {d['title']}: {d['decision']}"
            for d in self.memory.important_decisions[-3:]
        ]
        decisions_str = "\n".join(recent_decisions) if recent_decisions else "- Follow standard project conventions"

        compressed = f"""PROJECT MEMORY CONTEXT:
- Project: {self.memory.project_name} ({self.memory.purpose or 'Active application'})
- Architecture: {self.memory.architecture}
- Tech Stack: {json.dumps(self.memory.tech_stack) if self.memory.tech_stack else 'Standard'}
- Relevant Files: {files_str}
- Key Decisions:
{decisions_str}
- Completed Milestones: {len(self.memory.completed_tasks)} tasks
- Conventions: {', '.join(self.memory.coding_conventions[:2])}
"""
        return compressed

    def create_model_handoff(
        self,
        target_model: str,
        original_objective: str,
        master_spec: str,
        files_changed: List[str],
        previous_output: str,
        errors: List[str],
        remaining_tasks: List[str]
    ) -> Dict[str, Any]:
        """
        Implements Section 34: Model Handoff Protocol.
        When switching models or falling back, provides the next model with complete
        coherent context so work continues smoothly without restarting.
        """
        return {
            "target_model": target_model,
            "original_objective": original_objective,
            "master_specification_summary": master_spec[:500] + "...",
            "project_state": {
                "project_name": self.memory.project_name,
                "tech_stack": self.memory.tech_stack,
                "files_changed": files_changed,
                "total_completed": len(self.memory.completed_tasks)
            },
            "previous_model_output_excerpt": previous_output[-600:] if previous_output else "",
            "active_errors": errors,
            "remaining_tasks": remaining_tasks,
            "instruction": "Continue implementation from the current state. Do not rewrite already completed files unless fixing an active error."
        }
