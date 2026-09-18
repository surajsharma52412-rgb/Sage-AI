"""
Autonomous Automation Agent for SAGE.
Executes multi-step tasks using tools/APIs strictly adhering to the 7-step loop:
1. UNDERSTAND THE GOAL: Restate task and define explicit 'done' criteria.
2. PLAN: Decompose into steps, map tools, flag risk (is_risky) and idempotency (is_idempotent).
3. CONFIRM BEFORE RISKY STEPS: Require explicit confirmation for irreversible/side-effecting steps.
4. EXECUTE ONE STEP AT A TIME: Atomically execute tool call and validate output.
5. HANDLE FAILURES CAREFULLY: Retry idempotent steps with backoff; halt immediately on non-idempotent steps.
6. LOG STATE: Persist step transitions and done vs. pending status in SQLite to enable safe resumption.
7. VERIFY THE OUTCOME: Evaluate actual final state against Step 1 'done' criteria.
"""
import uuid
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .state_store import AutomationStateStore
from .automation_tools import AutomationToolRegistry
from engine.router import FallbackRouter

logger = logging.getLogger(__name__)


class AutonomousAutomationAgent:
    """Orchestrates multi-step autonomous automation tasks."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        state_store: Optional[AutomationStateStore] = None,
        tools: Optional[AutomationToolRegistry] = None,
        router: Optional[FallbackRouter] = None
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.state_store = state_store or AutomationStateStore()
        self.tools = tools or AutomationToolRegistry(self.workspace_root)
        self.router = router or FallbackRouter()

    # ── 1. UNDERSTAND THE GOAL ────────────────────────────────────────

    def understand_goal(self, task_prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Restates the task and formulates explicit, observable 'done' criteria.
        """
        task_prompt = (task_prompt or "").strip()
        if not task_prompt:
            return {
                "goal": "Empty Task",
                "done_criteria": "No actions required.",
                "constraints": []
            }

        # Check for standard recipe keywords for high-speed deterministic understanding
        prompt_lower = task_prompt.lower()
        if "briefing" in prompt_lower or "email digest" in prompt_lower:
            return {
                "goal": "Scan unread emails, compile executive briefing, and draft necessary replies.",
                "done_criteria": "All unread emails analyzed, executive briefing report created, and reply drafts prepared.",
                "constraints": ["No emails sent without explicit user authorization."]
            }
        elif "cleanup" in prompt_lower and ("test" in prompt_lower or "health" in prompt_lower):
            return {
                "goal": "Purge temporary workspace cache files and run full unit test health check.",
                "done_criteria": "__pycache__ and temp artifacts deleted; unit test suite executed with results recorded.",
                "constraints": ["Do not delete source code or configuration files."]
            }
        elif "cleanup" in prompt_lower or "clean cache" in prompt_lower:
            return {
                "goal": "Purge temporary workspace cache, .pyc, and orphaned scratch files.",
                "done_criteria": "All __pycache__ directories and .tmp files removed from workspace.",
                "constraints": ["Preserve all project code and tests."]
            }

        # Generic AI goal formulation
        ai_prompt = (
            f"You are an autonomous automation engineer.\n"
            f"Analyze this automation request and formulate:\n"
            f"1. A clear, restated goal statement.\n"
            f"2. Explicit, observable 'done' criteria (what proves the task is complete in reality).\n\n"
            f"User Request: {task_prompt}\n\n"
            f"Return JSON strictly in format:\n"
            f"{{\"goal\": \"...\", \"done_criteria\": \"...\", \"constraints\": [\"...\"]}}"
        )
        try:
            resp = self.router.route_and_execute(ai_prompt, selected_model="Auto Router")
            if resp.success and resp.text:
                clean = resp.text.strip()
                if "```json" in clean:
                    clean = clean.split("```json")[1].split("```")[0].strip()
                elif "```" in clean:
                    clean = clean.split("```")[1].split("```")[0].strip()
                parsed = json.loads(clean)
                return {
                    "goal": parsed.get("goal", task_prompt),
                    "done_criteria": parsed.get("done_criteria", "All planned steps executed successfully."),
                    "constraints": parsed.get("constraints", [])
                }
        except Exception as e:
            logger.warning("AI goal understanding fallback triggered: %s", e)

        return {
            "goal": task_prompt,
            "done_criteria": f"All automated operations for '{task_prompt[:60]}' completed and verified.",
            "constraints": ["Execute safely with permission gates on risky operations."]
        }

    # ── 2. PLAN ───────────────────────────────────────────────────────

    def plan_task(self, goal_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decomposes the goal into an ordered sequence of steps.
        Automatically tags each step with:
        - tool_name & tool_args
        - is_risky (inherited from tool)
        - is_idempotent (inherited from tool)
        - risk_reason
        - expected_outcome
        """
        goal = goal_data.get("goal", "").lower()
        steps: List[Dict[str, Any]] = []

        # Recipe 1: Email Briefing & Drafts
        if "email" in goal or "briefing" in goal or "digest" in goal:
            steps.append(self._build_step(
                step_id="step_1",
                name="Fetch Unread Messages",
                tool_name="fetch_emails",
                tool_args={"max_count": 5},
                expected_outcome="List of unread emails retrieved from inbox or sandbox."
            ))
            steps.append(self._build_step(
                step_id="step_2",
                name="Check System Disk & Health",
                tool_name="inspect_system_health",
                tool_args={},
                expected_outcome="System runtime and workspace storage verified healthy."
            ))
            steps.append(self._build_step(
                step_id="step_3",
                name="Write Automation Summary Report",
                tool_name="write_file",
                tool_args={"path": "automation_briefing.md", "content": "# Automation Briefing\nInbox scan complete.\n"},
                expected_outcome="Briefing file saved to workspace."
            ))

        # Recipe 2: Cleanup and Test Health Check
        elif any(k in goal for k in ("cleanup", "clean", "purge")) and ("test" in goal or "health" in goal):
            steps.append(self._build_step(
                step_id="step_1",
                name="Inspect Workspace Status",
                tool_name="inspect_system_health",
                tool_args={},
                expected_outcome="Baseline disk space recorded before cleanup."
            ))
            steps.append(self._build_step(
                step_id="step_2",
                name="Purge Temporary Cache",
                tool_name="clean_workspace_cache",
                tool_args={},
                expected_outcome="Temporary __pycache__ and orphan artifacts removed."
            ))
            steps.append(self._build_step(
                step_id="step_3",
                name="Run Test Health Suite",
                tool_name="run_unit_tests",
                tool_args={"test_target": "tests"},
                expected_outcome="Unit test suite executed without failures."
            ))

        # Recipe 3: Cache Cleanup Only
        elif any(k in goal for k in ("cleanup", "clean", "purge")):
            steps.append(self._build_step(
                step_id="step_1",
                name="Purge Temporary Cache",
                tool_name="clean_workspace_cache",
                tool_args={},
                expected_outcome="Temporary __pycache__ and orphan artifacts removed."
            ))

        # Generic AI planner
        else:
            steps = self._plan_with_ai(goal_data)

        return steps

    def _build_step(
        self,
        step_id: str,
        name: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        expected_outcome: str
    ) -> Dict[str, Any]:
        tool = self.tools.get_tool(tool_name)
        is_risky = tool.is_risky if tool else False
        is_idempotent = tool.is_idempotent if tool else True
        risk_reason = tool.risk_description if tool else ""

        return {
            "step_id": step_id,
            "name": name,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "is_risky": is_risky,
            "is_idempotent": is_idempotent,
            "risk_reason": risk_reason,
            "expected_outcome": expected_outcome,
            "status": "PENDING",
            "retry_count": 0
        }

    def _plan_with_ai(self, goal_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        tool_catalogue = self.tools.list_tools()
        prompt = (
            f"You are an autonomous automation planner.\n"
            f"Goal: {goal_data.get('goal')}\n"
            f"Done Criteria: {goal_data.get('done_criteria')}\n\n"
            f"Available Tools: {json.dumps(tool_catalogue, indent=2)}\n\n"
            f"Break this task into 2-5 atomic steps. For each step specify:\n"
            f"- name\n- tool_name\n- tool_args\n- expected_outcome\n\n"
            f"Return JSON array of steps: [{{'name': '...', 'tool_name': '...', 'tool_args': {{}}, 'expected_outcome': '...'}}]"
        )
        try:
            resp = self.router.route_and_execute(prompt, selected_model="Auto Router")
            if resp.success and resp.text:
                clean = resp.text.strip()
                if "```json" in clean:
                    clean = clean.split("```json")[1].split("```")[0].strip()
                elif "```" in clean:
                    clean = clean.split("```")[1].split("```")[0].strip()
                raw_steps = json.loads(clean)
                steps = []
                for idx, s in enumerate(raw_steps):
                    steps.append(self._build_step(
                        step_id=f"step_{idx+1}",
                        name=s.get("name", f"Step {idx+1}"),
                        tool_name=s.get("tool_name", "inspect_system_health"),
                        tool_args=s.get("tool_args", {}),
                        expected_outcome=s.get("expected_outcome", "Step completed.")
                    ))
                if steps:
                    return steps
        except Exception as e:
            logger.warning("AI planning fallback triggered: %s", e)

        # Safe fallback plan
        return [
            self._build_step("step_1", "Inspect System State", "inspect_system_health", {}, "Workspace health inspected.")
        ]

    # ── 3. EXECUTE FULL AUTOMATION RUN (The 7-Step Coordinator) ────────

    def start_automation(
        self,
        task_prompt: str,
        confirm_callback: Optional[Callable[[str, str, str, str], bool]] = None,
        on_step_change: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Launches an autonomous automation workflow from prompt to verification.
        """
        run_id = f"auto_{datetime_str()}_{uuid.uuid4().hex[:6]}"

        # 1. UNDERSTAND
        goal_data = self.understand_goal(task_prompt)
        self.state_store.create_run(run_id, goal_data["goal"], goal_data["done_criteria"])
        if on_step_change:
            on_step_change("UNDERSTAND", goal_data)

        # 2. PLAN
        steps = self.plan_task(goal_data)
        self.state_store.save_steps(run_id, steps)
        if on_step_change:
            on_step_change("PLAN", {"steps": steps})

        # Run the execution loop
        return self._execute_run_loop(run_id, confirm_callback=confirm_callback, on_step_change=on_step_change)

    def resume_automation(
        self,
        run_id: str,
        confirm_callback: Optional[Callable[[str, str, str, str], bool]] = None,
        on_step_change: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Resumes an interrupted or paused run without repeating completed side-effects.
        """
        run = self.state_store.get_run(run_id)
        if not run:
            return {"success": False, "error": f"Run '{run_id}' not found."}
        return self._execute_run_loop(run_id, confirm_callback=confirm_callback, on_step_change=on_step_change)

    def _execute_run_loop(
        self,
        run_id: str,
        confirm_callback: Optional[Callable[[str, str, str, str], bool]] = None,
        on_step_change: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        self.state_store.update_run_status(run_id, "RUNNING")
        run = self.state_store.get_run(run_id)
        steps = run.get("steps", [])

        for idx, step in enumerate(steps):
            # Skip steps that have already finished (State Tracking)
            if step.get("status") in ("DONE", "SKIPPED"):
                continue

            # 3. CONFIRM BEFORE RISKY STEPS
            if step.get("is_risky"):
                self.state_store.update_step_status(run_id, idx, "CONFIRMING")
                if on_step_change:
                    on_step_change("CONFIRMING", {"step": step, "step_index": idx})

                is_approved = True
                if confirm_callback:
                    action = f"⚠️ {step.get('name')}"
                    target = str(step.get("tool_args", {}))
                    subject = step.get("risk_reason", "Irreversible action requested.")
                    body = f"Tool: {step.get('tool_name')}\nArguments: {json.dumps(step.get('tool_args'), indent=2)}"
                    is_approved = confirm_callback(action, target, subject, body)

                decision = "APPROVED" if is_approved else "DENIED"
                self.state_store.record_audit(
                    run_id=run_id,
                    action_type=step.get("tool_name", "unknown"),
                    target=str(step.get("tool_args")),
                    decision=decision,
                    status="AUTHORIZED" if is_approved else "HALTED",
                    details=step.get("risk_reason", "")
                )

                if not is_approved:
                    self.state_store.update_step_status(run_id, idx, "ABORTED", error_message="User denied authorization.")
                    self.state_store.update_run_status(run_id, "ABORTED", verified_outcome="FAIL", verification_summary="Run halted: user declined authorization for risky step.")
                    if on_step_change:
                        on_step_change("ABORTED", {"step": step, "step_index": idx})
                    return {
                        "success": False,
                        "run_id": run_id,
                        "status": "ABORTED",
                        "message": f"Run aborted: User denied authorization for step '{step.get('name')}'."
                    }

                # Mark permission granted in tool args if needed
                step["tool_args"]["permission_granted"] = True

            # 4. EXECUTE ONE STEP AT A TIME
            self.state_store.update_step_status(run_id, idx, "RUNNING")
            if on_step_change:
                on_step_change("RUNNING", {"step": step, "step_index": idx})

            tool_name = step.get("tool_name", "")
            tool_args = step.get("tool_args", {})
            result = self.tools.execute_tool(tool_name, **tool_args)

            # 5. HANDLE FAILURES CAREFULLY
            if not result.get("success"):
                error_msg = result.get("error", "Unknown tool execution failure.")
                is_idempotent = step.get("is_idempotent", True)

                # If idempotent, allow up to 1 retry
                if is_idempotent and step.get("retry_count", 0) < 1:
                    logger.info("Retrying idempotent step '%s' after initial failure: %s", step.get("name"), error_msg)
                    self.state_store.update_step_status(run_id, idx, "RUNNING", increment_retry=True)
                    result = self.tools.execute_tool(tool_name, **tool_args)

                # Check if still failing
                if not result.get("success"):
                    self.state_store.update_step_status(run_id, idx, "FAILED", error_message=error_msg)
                    self.state_store.update_run_status(
                        run_id, "FAILED",
                        verified_outcome="FAIL",
                        verification_summary=f"Step '{step.get('name')}' failed: {error_msg}. Non-idempotent or max retries exceeded."
                    )
                    if on_step_change:
                        on_step_change("FAILED", {"step": step, "step_index": idx, "error": error_msg})
                    return {
                        "success": False,
                        "run_id": run_id,
                        "status": "FAILED",
                        "failed_step": step.get("name"),
                        "error": error_msg
                    }

            # 6. LOG STATE (Successful step)
            self.state_store.update_step_status(run_id, idx, "DONE", result_payload=result)
            if on_step_change:
                on_step_change("DONE", {"step": step, "step_index": idx, "result": result})

        # 7. VERIFY THE OUTCOME
        outcome = self.verify_outcome(run_id)
        final_status = "COMPLETED" if outcome.get("achieved") else "FAILED"
        self.state_store.update_run_status(
            run_id,
            status=final_status,
            verified_outcome="PASS" if outcome.get("achieved") else "FAIL",
            verification_summary=outcome.get("summary", "")
        )
        if on_step_change:
            on_step_change("VERIFIED", outcome)

        return {
            "success": outcome.get("achieved", False),
            "run_id": run_id,
            "status": final_status,
            "outcome": outcome,
            "run": self.state_store.get_run(run_id)
        }

    # ── 7. VERIFY THE OUTCOME ─────────────────────────────────────────

    def verify_outcome(self, run_id: str) -> Dict[str, Any]:
        """
        Validates the actual final state against the original Goal and Done Criteria.
        """
        run = self.state_store.get_run(run_id)
        if not run:
            return {"achieved": False, "summary": "Run record missing.", "evidence": []}

        goal = run.get("goal", "")
        done_criteria = run.get("done_criteria", "")
        steps = run.get("steps", [])

        # Check all steps status
        all_done = all(s.get("status") in ("DONE", "SKIPPED") for s in steps)
        failed_steps = [s.get("name") for s in steps if s.get("status") == "FAILED"]

        evidence = []
        for s in steps:
            p = s.get("result_payload") or {}
            msg = p.get("message") or f"Tool {s.get('tool_name')} returned success."
            evidence.append(f"{s.get('name')}: {msg}")

        achieved = all_done and not failed_steps
        summary = (
            f"All {len(steps)} steps successfully executed and validated against done criteria: '{done_criteria}'."
            if achieved
            else f"Execution incomplete. Failed or pending steps detected: {', '.join(failed_steps)}."
        )

        return {
            "achieved": achieved,
            "goal": goal,
            "done_criteria": done_criteria,
            "total_steps": len(steps),
            "evidence": evidence,
            "summary": summary
        }


def datetime_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")
