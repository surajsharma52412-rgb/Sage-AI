"""
Coding Agent for Sage Multi-Agentic AI Architecture (v6).
Upgraded to SAGE Coding Agent Architecture (v6) For Large & Complex Projects:
- Core Orchestrator: Understands ➔ Plans ➔ Delegates ➔ Tracks ➔ Merges ➔ Verifies ➔ Delivers
- Project Understanding (Static Codebase Discovery & Requirements Analysis)
- Task Planner & Scheduler (DAG Task Decomposition & Parallel Multi-Agent Execution)
- 6 Specialized Coding Sub-Agents (Architect, Backend, Frontend, DevOps, QA, Documentation)
- Pipeline Flow (Code Integration, Automated Validation, Self-Healing Feedback Loop, Final Packaging)
- Long-Context Memory & Scalable Infrastructure
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from config import AGENT_CODING
from .base_agent import BaseAgent
from engine.coding_agent import CodingAgentOrchestrator

logger = logging.getLogger(__name__)


class CodingAgent(BaseAgent):
    """
    SAGE Coding Agent (v6) specialized in engineering large & complex software projects.
    Coordinates 6 specialized sub-agents, automated DAG scheduling, self-healing iteration,
    and end-to-end project packaging.
    """

    def __init__(self):
        super().__init__(name=AGENT_CODING, role_id="coder")
        workspace_path = getattr(self.workspace, "root", Path.cwd())
        self.v6_orchestrator = CodingAgentOrchestrator(workspace_root=workspace_path)

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        instruction = task_input.get("instruction") or task_input.get("query") or task_input.get("goal") or ""
        task_id = (context or {}).get("task_id")

        if on_stage:
            on_stage("⚡ Coding Agent (v6): Ingesting software task into autonomous pipeline...")
        self.log("Executing v6 Coding Agent Architecture", task_id=task_id, details={"instruction": instruction})

        # Sync workspace root if changed
        ws_root = getattr(self.workspace, "root_path", None) or getattr(self.workspace, "root", None)
        if ws_root:
            Path(ws_root).mkdir(parents=True, exist_ok=True)
            self.v6_orchestrator.set_workspace(ws_root)

        # Check for shared research memory context
        shared_research = self.shared_memory.get_all(memory_type="research")
        context_dict = dict(context or {})
        if shared_research:
            context_dict["shared_research"] = shared_research

        # Define LLM caller adapter that uses BaseAgent's configured LLM infrastructure
        def _llm_caller(prompt: str, system_prompt: str, preferred_providers: Optional[List[str]] = None) -> Dict[str, Any]:
            return self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                on_chunk=on_chunk,
                preferred_providers=preferred_providers or ["openrouter", "nvidia", "groq", "gemini", "ollama", "local_facts"]
            )

        def _on_log(msg: str):
            self.log(msg, task_id=task_id)

        # Execute project through the 7-stage v6 Orchestrator
        res = self.v6_orchestrator.execute_project(
            goal=instruction,
            context=context_dict,
            llm_caller_fn=_llm_caller,
            on_stage=on_stage,
            on_log=_on_log
        )

        self.send_bus_message(
            to_agent="all",
            message_type="code_generated",
            content=f"Completed v6 coding execution for: '{instruction[:40]}...'",
            task_id=task_id
        )

        return {
            "success": res.get("success", True),
            "agent": self.name,
            "architecture_version": "v6",
            "summary": res.get("summary", ""),
            "tree": res.get("tree", ""),
            "written_files": res.get("written_files", []),
            "timeline": res.get("timeline", []),
            "evaluation": res.get("validation", {}),
            "deliverables": res.get("deliverables", [])
        }
