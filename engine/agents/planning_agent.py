"""
Planning Agent for Sage Multi-Agentic AI Architecture.
Capabilities:
- Plan complex tasks
- Set milestones
- Track progress
- Manage resources
- Adjust strategy
- Ensure completion
"""
import json
import logging
from typing import Dict, Any, Optional, Callable, List

from config import AGENT_PLANNING
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PlanningAgent(BaseAgent):
    """Specialized in strategic decomposition, milestone setting, progress tracking, and resource management."""

    def __init__(self):
        super().__init__(name=AGENT_PLANNING, role_id="planning")

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        goal = task_input.get("goal") or task_input.get("instruction") or ""
        task_id = (context or {}).get("task_id")

        if on_stage:
            on_stage("📅 Planning Agent: Formulating strategic milestones & resource roadmap...")
        self.log("Formulating project roadmap and milestones", task_id=task_id, details={"goal": goal})

        system_prompt = (
            "You are Sage AI's expert Planning Agent. You formulate structured, milestone-driven execution roadmaps. "
            "For every goal, provide:\n"
            "1. Objective & Success Criteria\n"
            "2. Phased Milestones with deliverables\n"
            "3. Assigned Agent Roles (Research, Coding, Image/Media, Data Analysis, Content, Execution)\n"
            "4. Risk Mitigation & Resource Management"
        )

        prompt = (
            f"High-Level Project Goal: {goal}\n\n"
            "Formulate a complete, phased execution roadmap with concrete milestones and agent assignments."
        )

        llm_res = self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            on_chunk=on_chunk,
            preferred_providers=["groq", "nvidia", "gemini", "openrouter", "ollama", "local_facts"]
        )

        plan_text = llm_res.get("text", "")

        # Save active plan to Shared Memory for other agents
        self.shared_memory.set(
            key="current_project_plan",
            value={"goal": goal, "plan": plan_text},
            is_long_term=True,
            memory_type="planning",
            agent_source=self.name
        )

        self.send_bus_message(
            to_agent="all",
            message_type="plan_created",
            content=f"Strategic plan formulated for goal: '{goal[:40]}...'",
            task_id=task_id
        )

        return {
            "success": True,
            "agent": self.name,
            "summary": plan_text,
            "deliverables": [
                {
                    "type": "strategic_plan",
                    "title": f"Master Plan: {goal[:40]}",
                    "content": plan_text
                }
            ]
        }
