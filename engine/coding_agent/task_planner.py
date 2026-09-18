"""
Task Planner & Manager for SAGE Coding Agent Architecture (v6).
Responsibilities:
- Breaks large project goals into granular subtasks
- Constructs a Directed Acyclic Graph (DAG) with clear dependencies
- Prioritizes subtasks topologically and determines parallel vs sequential execution stages
- Assigns subtasks to the 6 specialized coding sub-agents
- Tracks live progress and metrics
- Dynamically adapts the plan when failures or new requirements arise
"""
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class TaskPlannerManager:
    """Orchestrates task decomposition, dependency DAG compilation, and plan adaptation."""

    def __init__(self):
        self.subtasks: Dict[str, Dict[str, Any]] = {}
        self.execution_stages: List[List[str]] = []  # List of stages, each containing task_ids that run in parallel

    def build_plan_from_modules(
        self,
        project_goal: str,
        modules: List[Dict[str, Any]],
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Creates a granular subtask DAG based on project modules and requirements.
        Defines precise dependencies ensuring downstream agents receive necessary inputs.
        """
        self.subtasks.clear()

        # 1. Architecture Task (Root node)
        t_arch = {
            "task_id": "task_arch",
            "name": "System Architecture & API Design",
            "role": "architect",
            "instruction": f"Design complete system architecture, data models, and API specifications for: {project_goal}",
            "depends_on": [],
            "status": "pending",
            "priority": 100,
            "target_files": ["docs/architecture.md", "models.py"]
        }
        self.subtasks["task_arch"] = t_arch

        # 2. Backend Task (Depends on Architecture)
        t_backend = {
            "task_id": "task_backend",
            "name": "Backend APIs, Database & Auth Implementation",
            "role": "backend",
            "instruction": f"Implement backend server, authentication, database persistence, and API handlers according to architecture for: {project_goal}",
            "depends_on": ["task_arch"],
            "status": "pending",
            "priority": 80,
            "target_files": ["backend/server.py", "backend/database.py", "backend/auth.py", "backend/routes.py"]
        }
        self.subtasks["task_backend"] = t_backend

        # 3. Frontend Task (Depends on Architecture; can run in parallel with Backend)
        t_frontend = {
            "task_id": "task_frontend",
            "name": "Frontend UI/UX & Client Integration",
            "role": "frontend",
            "instruction": f"Build responsive modern user interface, dashboard, state management, and API integration for: {project_goal}",
            "depends_on": ["task_arch"],
            "status": "pending",
            "priority": 80,
            "target_files": ["frontend/index.html", "frontend/styles.css", "frontend/app.js"]
        }
        self.subtasks["task_frontend"] = t_frontend

        # 4. DevOps Task (Depends on Backend & Frontend structure)
        t_devops = {
            "task_id": "task_devops",
            "name": "DevOps, Containerization & Deployment Setup",
            "role": "devops",
            "instruction": f"Configure Dockerfile, docker-compose.yml, environment configs (.env.example), and CI workflow for: {project_goal}",
            "depends_on": ["task_backend", "task_frontend"],
            "status": "pending",
            "priority": 60,
            "target_files": ["Dockerfile", "docker-compose.yml", ".env.example"]
        }
        self.subtasks["task_devops"] = t_devops

        # 5. QA Task (Depends on Backend & Frontend code)
        t_qa = {
            "task_id": "task_qa",
            "name": "Automated Testing & Security Validation",
            "role": "qa",
            "instruction": f"Write comprehensive unit and integration tests, verify edge cases, and run security checks for: {project_goal}",
            "depends_on": ["task_backend", "task_frontend"],
            "status": "pending",
            "priority": 50,
            "target_files": ["tests/test_api.py", "tests/test_ui.py"]
        }
        self.subtasks["task_qa"] = t_qa

        # 6. Documentation Task (Depends on all implementations)
        t_docs = {
            "task_id": "task_docs",
            "name": "Documentation & Setup Guides",
            "role": "documentation",
            "instruction": f"Generate production-grade README.md, API documentation, and deployment guides for: {project_goal}",
            "depends_on": ["task_backend", "task_frontend", "task_devops", "task_qa"],
            "status": "pending",
            "priority": 40,
            "target_files": ["README.md", "docs/api_reference.md"]
        }
        self.subtasks["task_docs"] = t_docs

        self.execution_stages = self._compute_execution_stages()

        return {
            "goal": project_goal,
            "total_tasks": len(self.subtasks),
            "subtasks": self.subtasks,
            "stages": self.execution_stages
        }

    def _compute_execution_stages(self) -> List[List[str]]:
        """
        Organizes tasks into topological parallel stages.
        Tasks in Stage N have all dependencies satisfied by Stages < N.
        """
        completed: Set[str] = set()
        remaining = dict(self.subtasks)
        stages = []

        while remaining:
            # Find all tasks whose dependencies are satisfied
            ready = [
                tid for tid, t in remaining.items()
                if all(dep in completed for dep in t.get("depends_on", []))
            ]

            if not ready:
                # Cycle fallback or loose dependencies: take remaining by highest priority
                ready = [max(remaining.keys(), key=lambda k: remaining[k].get("priority", 0))]

            stages.append(ready)
            for tid in ready:
                completed.add(tid)
                del remaining[tid]

        return stages

    def adapt_plan(self, failed_task_id: str, error_details: str) -> Dict[str, Any]:
        """
        Dynamically adapts plan upon subtask failure by injecting a targeted repair subtask.
        """
        failed_task = self.subtasks.get(failed_task_id, {})
        repair_id = f"repair_{failed_task_id}"

        repair_task = {
            "task_id": repair_id,
            "name": f"Auto-Repair: Fix {failed_task.get('name', failed_task_id)}",
            "role": failed_task.get("role", "backend"),
            "instruction": f"Fix identified failure in {failed_task_id}: {error_details}",
            "depends_on": [failed_task_id],
            "status": "pending",
            "priority": failed_task.get("priority", 50) + 5,
            "target_files": failed_task.get("target_files", [])
        }
        self.subtasks[repair_id] = repair_task

        # Re-compute stages
        self.execution_stages = self._compute_execution_stages()
        return repair_task
