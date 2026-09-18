"""
Agent Orchestrator (Core Brain) for Sage Multi-Agentic AI Architecture.
Plans, routes tasks, assigns agents, manages workflow, monitors progress,
and ensures automated goal completion.
Integrates:
- Task Decomposer
- Agent Router
- Workflow Manager
- Self-Reflection
- Memory Manager
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional, List, Callable

from database.db_manager import get_db
from .task_decomposer import TaskDecomposer
from .agent_router import AgentRouter
from .workflow_manager import WorkflowManager
from .self_reflection import SelfReflection
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """The central orchestrator coordinating multi-agent workflows and single-turn routing."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentOrchestrator, cls).__new__(cls)
            cls._instance._init_orchestrator()
        return cls._instance

    def _init_orchestrator(self):
        self.decomposer = TaskDecomposer()
        self.router = AgentRouter()
        self.workflow = WorkflowManager(agent_router=self.router)
        self.reflection = SelfReflection()
        self.memory = MemoryManager()
        self.db = get_db()

    def orchestrate_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_step_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Full multi-agent pipeline execution matching the architecture blueprint:
        Task Decomposer ➔ Agent Router ➔ Workflow Manager ➔ Specialized Agents ➔ Self-Reflection ➔ Automated Completion.
        """
        start_time = time.time()
        task_id = str(uuid.uuid4())

        if on_stage:
            on_stage("🧠 Agent Orchestrator: Ingesting goal & decomposing into steps...")

        # 1. Retrieve any historical context
        historical_context = self.memory.retrieve_relevant_context(goal)

        # 2. Decompose Goal into Structured Subtasks
        steps = self.decomposer.decompose(goal, context)
        if on_stage:
            on_stage(f"🧠 Agent Orchestrator: Created {len(steps)}-step execution plan across specialized agents.")

        # Create record in DB
        self.db.create_multi_agent_task(goal=goal, plan_steps=steps)

        # 3. Workflow Execution across Specialized Agents
        wf_res = self.workflow.execute_workflow(
            task_id=task_id,
            goal=goal,
            steps=steps,
            on_step_update=on_step_update,
            on_stage=on_stage,
            on_chunk=on_chunk
        )

        deliverables = wf_res.get("deliverables", [])

        # 4. Self-Reflection & Quality Check
        if on_stage:
            on_stage("🔍 Agent Orchestrator: Self-reflection & quality verification...")

        eval_res = self.reflection.evaluate_results(goal=goal, deliverables=deliverables)

        # 5. Store Outcome in Memory Manager
        summary_text = self._synthesize_final_response(goal, steps, deliverables, eval_res)
        self.memory.store_task_outcome(task_id, goal, summary_text)

        elapsed_s = round(time.time() - start_time, 2)
        if on_stage:
            on_stage(f"✅ Automated Completion: Goal accomplished in {elapsed_s}s with {len(deliverables)} deliverable(s)!")

        return {
            "success": wf_res.get("success", True),
            "task_id": task_id,
            "goal": goal,
            "steps": steps,
            "deliverables": deliverables,
            "evaluation": eval_res,
            "final_summary": summary_text,
            "elapsed_seconds": elapsed_s
        }

    def fast_route(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        force_web: bool = False,
        selected_model: Optional[str] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Direct single-turn execution: routes user query to the best specialized agent.
        """
        if on_stage:
            on_stage("🧠 Agent Orchestrator: Classifying intent and selecting specialized agent...")

        # Select specialized agent
        agent_name = self.router.route_query(prompt, force_web=force_web)
        if on_stage:
            on_stage(f"🧠 Routed to {agent_name}...")

        # Retrieve relevant memories, directives, and learned facts
        mem_context = self.memory.retrieve_relevant_context(prompt)

        agent = self.router.get_agent_instance(agent_name)
        task_input = {
            "instruction": prompt,
            "query": prompt,
            "force_web": force_web,
            "selected_model": selected_model
        }

        agent_res = agent.execute(
            task_input=task_input,
            context={"history": history or [], "memory_context": mem_context},
            on_stage=on_stage,
            on_chunk=on_chunk
        )

        return {
            "success": agent_res.get("success", True),
            "agent_name": agent_name,
            "text": agent_res.get("summary", ""),
            "model_name": f"{agent_name} ({selected_model or 'Auto'})",
            "provider_id": "orchestrator",
            "citations": agent_res.get("citations", []),
            "is_image": agent_res.get("is_image", False),
            "image_data": agent_res.get("image_data"),
            "deliverables": agent_res.get("deliverables", []),
            "metadata": agent_res
        }

    def _synthesize_final_response(
        self,
        goal: str,
        steps: List[Dict[str, Any]],
        deliverables: List[Dict[str, Any]],
        eval_res: Dict[str, Any]
    ) -> str:
        """Synthesizes a structured final response summary."""
        parts = [
            f"## 🎯 Goal Accomplished\n> **{goal}**\n\n",
            "### 🤖 Specialized Agents Collaboration:\n"
        ]
        for s in steps:
            st = "✅" if s.get("status") == "completed" else "⚠️"
            parts.append(f"- {st} **{s.get('name')}** (`{s.get('agent_type')}`): {s.get('result_summary', 'Executed')[:120]}...\n")

        parts.append(f"\n### 🔍 Self-Reflection Score: **{eval_res.get('score_percentage', 100)}%**\n")
        if eval_res.get("notes"):
            for n in eval_res["notes"][:3]:
                parts.append(f"- {n}\n")

        # Include main deliverable text
        main_deliverables = [d for d in deliverables if d.get("content")]
        if main_deliverables:
            parts.append("\n---\n\n### 📦 Deliverables:\n\n")
            for d in main_deliverables:
                title = d.get("title", "Deliverable")
                content = d.get("content", "")
                parts.append(f"#### {title}\n\n{content}\n\n")

        return "".join(parts)


def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator()
