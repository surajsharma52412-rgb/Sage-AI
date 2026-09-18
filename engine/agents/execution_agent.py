"""
Execution Agent for Sage Multi-Agentic AI Architecture.
Capabilities:
- Run commands
- Use tools & APIs
- Manage files/folders
- Automate workflows
- Schedule tasks
- Deploy & monitor
"""
import logging
from typing import Dict, Any, Optional, Callable

from config import AGENT_EXECUTION
from .base_agent import BaseAgent
from engine.execution.process_runner import get_process_runner

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """Specialized in executing terminal commands, running tools, managing workspace files, and deployment."""

    def __init__(self):
        super().__init__(name=AGENT_EXECUTION, role_id="execution")
        self.runner = get_process_runner()

    def execute(
        self,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        on_stage: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        instruction = task_input.get("instruction") or task_input.get("command") or ""
        tool_name = task_input.get("tool_name")
        tool_args = task_input.get("tool_args", {})
        task_id = (context or {}).get("task_id")

        # 1. Execute named tool if specified
        if tool_name:
            if on_stage:
                on_stage(f"⚙️ Execution Agent: Invoking tool '{tool_name}'...")
            self.log(f"Invoking tool {tool_name}", task_id=task_id, details=tool_args)
            tool_res = self.tools.execute_tool(tool_name, **tool_args)
            return {
                "success": tool_res.get("success", False),
                "agent": self.name,
                "summary": f"Executed tool {tool_name}: {tool_res}",
                "result": tool_res,
                "deliverables": [{"type": "tool_execution", "tool": tool_name, "result": tool_res}]
            }

        # 2. Execute Shell Command if command explicitly requested
        if task_input.get("is_command") or instruction.startswith("run ") or instruction.startswith("exec "):
            cmd = instruction
            if cmd.startswith("run ") or cmd.startswith("exec "):
                cmd = cmd.split(" ", 1)[1].strip()

            if on_stage:
                on_stage(f"⚙️ Execution Agent: Executing command '{cmd[:35]}...'")
            self.log(f"Executing command: {cmd}", task_id=task_id)

            run_res = self.runner.run_command(cmd)
            summary_msg = (
                f"Command: `{cmd}`\n"
                f"Exit Code: {run_res['exit_code']}\n\n"
                f"**STDOUT:**\n```\n{run_res['stdout']}\n```\n"
                f"**STDERR:**\n```\n{run_res['stderr']}\n```"
            )

            self.send_bus_message(
                to_agent="all",
                message_type="command_executed",
                content=f"Executed command '{cmd[:30]}...' with exit code {run_res['exit_code']}",
                task_id=task_id
            )

            return {
                "success": run_res["success"],
                "agent": self.name,
                "summary": summary_msg,
                "details": run_res,
                "deliverables": [{"type": "command_result", "command": cmd, "result": run_res}]
            }

        # 3. Formulate automation or deployment instructions with LLM
        if on_stage:
            on_stage("⚙️ Execution Agent: Orchestrating workflow automation steps...")

        system_prompt = (
            "You are Sage AI's Execution Agent. You formulate deployment plans, shell command sequences, "
            "automation scripts, and pipeline orchestration instructions."
        )

        prompt = f"Execution / Deployment Task: {instruction}\nFormulate the exact step-by-step commands and scripts."
        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, on_chunk=on_chunk)
        exec_plan = llm_res.get("text", "")

        return {
            "success": True,
            "agent": self.name,
            "summary": exec_plan,
            "deliverables": [
                {
                    "type": "execution_plan",
                    "title": f"Execution & Deployment Plan: {instruction[:40]}",
                    "content": exec_plan
                }
            ]
        }
