"""
Workflow Manager for Sage Multi-Agentic AI Architecture.
Manages dependencies, execution sequence, inter-agent data piping,
and lifecycle status tracking across multi-agent pipelines.
"""
import logging
from typing import List, Dict, Any, Optional, Callable

from config import (
    TASK_STATUS_PENDING,
    TASK_STATUS_IN_PROGRESS,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)
from database.db_manager import get_db
from .agent_router import AgentRouter

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Coordinates execution sequence and pipes context between specialized agents."""

    def __init__(self, agent_router: Optional[AgentRouter] = None):
        self.router = agent_router or AgentRouter()
        self.db = get_db()

    def execute_workflow(
        self,
        task_id: str,
        goal: str,
        steps: List[Dict[str, Any]],
        on_step_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes decomposed subtasks, piping context and updating status in real-time.
        """
        results_by_step: Dict[str, Dict[str, Any]] = {}
        all_deliverables: List[Dict[str, Any]] = []
        context_accumulator: Dict[str, Any] = {"goal": goal, "task_id": task_id}

        self.db.update_multi_agent_task(task_id, status=TASK_STATUS_IN_PROGRESS, plan_steps=steps)

        for step in steps:
            step_id = step["id"]
            agent_type = step["agent_type"]
            step_name = step["name"]
            instruction = step["instruction"]

            # Update step status to in_progress
            step["status"] = TASK_STATUS_IN_PROGRESS
            if on_step_update:
                on_step_update(step)

            if on_stage:
                on_stage(f"🚀 Running [{step_name}] with {agent_type}...")

            # Gather context from dependencies
            step_context = dict(context_accumulator)
            dep_outputs = []
            for dep_id in step.get("depends_on", []):
                if dep_id in results_by_step:
                    dep_outputs.append(results_by_step[dep_id].get("summary", ""))

            if dep_outputs:
                step_context["dependency_context"] = "\n\n".join(dep_outputs)

            task_input = {
                "instruction": instruction,
                "query": instruction,
                "goal": goal,
                "data": step.get("data")
            }

            try:
                agent = self.router.get_agent_instance(agent_type)
                agent_res = agent.execute(
                    task_input=task_input,
                    context=step_context,
                    on_stage=on_stage,
                    on_chunk=on_chunk
                )

                step["status"] = TASK_STATUS_COMPLETED
                step["result_summary"] = agent_res.get("summary", "")
                results_by_step[step_id] = agent_res

                if "deliverables" in agent_res:
                    all_deliverables.extend(agent_res["deliverables"])

                # Accumulate outputs into context
                context_accumulator[f"output_{step_id}"] = agent_res.get("summary", "")

            except Exception as e:
                logger.error("Step '%s' failed: %s", step_name, e)
                step["status"] = TASK_STATUS_FAILED
                step["error"] = str(e)
                if on_step_update:
                    on_step_update(step)
                self.db.update_multi_agent_task(
                    task_id,
                    status=TASK_STATUS_FAILED,
                    plan_steps=steps,
                    deliverables=all_deliverables
                )
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": f"Workflow halted at step '{step_name}': {str(e)}",
                    "completed_steps": results_by_step,
                    "deliverables": all_deliverables
                }

            if on_step_update:
                on_step_update(step)

        self.db.update_multi_agent_task(
            task_id,
            status=TASK_STATUS_COMPLETED,
            plan_steps=steps,
            deliverables=all_deliverables
        )

        return {
            "success": True,
            "task_id": task_id,
            "steps": steps,
            "results": results_by_step,
            "deliverables": all_deliverables
        }
