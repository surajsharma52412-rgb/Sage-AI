"""
Comprehensive Test Suite for SAGE Autonomous Automation Agent.
Verifies the full 7-step autonomous automation loop:
1. UNDERSTAND THE GOAL: Restating task and defining explicit 'done' criteria.
2. PLAN: Decomposing into steps, mapping tools, tagging is_risky and is_idempotent.
3. CONFIRM BEFORE RISKY STEPS: Context-aware authorization before side-effecting operations.
4. EXECUTE ONE STEP AT A TIME: Atomic step execution and output validation.
5. HANDLE FAILURES CAREFULLY: Idempotent retries vs non-idempotent immediate halts.
6. LOG STATE: SQLite persistence of done vs pending steps and safe resumption.
7. VERIFY THE OUTCOME: Validating actual outcomes against original criteria.
"""
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Any

from engine.automation.state_store import AutomationStateStore
from engine.automation.automation_tools import AutomationToolRegistry, AutomationTool
from engine.automation.autonomous_automation_agent import AutonomousAutomationAgent
from engine.automation_agent import AutomationManager


class TestAutonomousAutomationAgent(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ws = Path(self.test_dir).resolve()
        self.db_path = self.ws / "test_automation.db"
        self.store = AutomationStateStore(self.db_path)
        self.tools = AutomationToolRegistry(self.ws)
        self.agent = AutonomousAutomationAgent(
            workspace_root=self.ws,
            state_store=self.store,
            tools=self.tools
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ── 1. UNDERSTAND THE GOAL ────────────────────────────────────────

    def test_understand_goal_formulates_done_criteria(self):
        """Checks that understand_goal defines explicit, observable done criteria."""
        res = self.agent.understand_goal("Run workspace cleanup and test health check")
        self.assertIn("goal", res)
        self.assertIn("done_criteria", res)
        self.assertIn("constraints", res)
        self.assertTrue(len(res["done_criteria"]) > 5)
        self.assertIn("pycache", res["done_criteria"].lower())

    def test_understand_goal_email_briefing_recipe(self):
        """Checks recipe detection for email briefing tasks."""
        res = self.agent.understand_goal("Prepare email briefing and digest")
        self.assertIn("briefing", res["goal"].lower())
        self.assertTrue(len(res["constraints"]) >= 1)

    # ── 2. PLAN ───────────────────────────────────────────────────────

    def test_plan_task_tags_risk_and_idempotency(self):
        """Verifies that plan_task correctly flags risky and idempotent steps."""
        goal_data = self.agent.understand_goal("Run workspace cleanup and test health check")
        steps = self.agent.plan_task(goal_data)

        self.assertGreaterEqual(len(steps), 2)
        # Verify step attributes
        for s in steps:
            self.assertIn("step_id", s)
            self.assertIn("tool_name", s)
            self.assertIn("is_risky", s)
            self.assertIn("is_idempotent", s)
            self.assertIn("expected_outcome", s)

        # clean_workspace_cache should be flagged as risky
        clean_step = next((s for s in steps if s["tool_name"] == "clean_workspace_cache"), None)
        self.assertIsNotNone(clean_step)
        self.assertTrue(clean_step["is_risky"])
        self.assertTrue(clean_step["is_idempotent"])

    # ── 3. CONFIRM BEFORE RISKY STEPS ─────────────────────────────────

    def test_confirm_before_risky_step_approved(self):
        """Asserts that approved confirmation allows risky step to execute."""
        confirmed_actions = []

        def mock_confirm(action, target, subject, body):
            confirmed_actions.append((action, target))
            return True

        res = self.agent.start_automation(
            task_prompt="Run workspace cleanup and test health check",
            confirm_callback=mock_confirm
        )
        self.assertTrue(res["success"])
        self.assertGreaterEqual(len(confirmed_actions), 1)

        # Verify audit event in state store
        audits = self.store.get_audit_history(res["run_id"])
        self.assertGreaterEqual(len(audits), 1)
        self.assertEqual(audits[0]["decision"], "APPROVED")

    def test_confirm_before_risky_step_denied_halts_safely(self):
        """Asserts that user denial safely halts execution and prevents mutations."""
        res = self.agent.start_automation(
            task_prompt="Run workspace cleanup and test health check",
            confirm_callback=lambda *a: False
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "ABORTED")

        # Verify audit event recorded denial
        audits = self.store.get_audit_history(res["run_id"])
        self.assertGreaterEqual(len(audits), 1)
        self.assertEqual(audits[0]["decision"], "DENIED")

        # Verify run record in DB
        run = self.store.get_run(res["run_id"])
        self.assertEqual(run["status"], "ABORTED")

    # ── 4. EXECUTE ONE STEP AT A TIME & 5. FAILURES ────────────────────

    def test_execute_one_step_at_a_time(self):
        """Verifies steps transition sequentially through the loop."""
        step_events = []

        def on_step(evt, data):
            step_events.append((evt, data.get("step", {}).get("name", "")))

        res = self.agent.start_automation(
            task_prompt="Run workspace cleanup and test health check",
            confirm_callback=lambda *a: True,
            on_step_change=on_step
        )
        self.assertTrue(res["success"])
        event_types = [e[0] for e in step_events]
        self.assertIn("UNDERSTAND", event_types)
        self.assertIn("PLAN", event_types)
        self.assertIn("RUNNING", event_types)
        self.assertIn("DONE", event_types)
        self.assertIn("VERIFIED", event_types)

    def test_non_idempotent_failure_halts_immediately(self):
        """Asserts non-idempotent tool failure halts without retrying."""
        # Register a failing non-idempotent tool
        fail_tool = AutomationTool(
            name="failing_non_idempotent",
            category="system",
            description="Simulated failing tool",
            handler=lambda **kw: {"success": False, "error": "Disk write failed"},
            is_risky=True,
            is_idempotent=False
        )
        self.tools.register(fail_tool)

        # Create a run with this tool
        run_id = "test_fail_halt"
        self.store.create_run(run_id, "Test fail", "Should halt")
        self.store.save_steps(run_id, [
            {
                "step_id": "s1",
                "name": "Failing Step",
                "tool_name": "failing_non_idempotent",
                "tool_args": {},
                "is_risky": True,
                "is_idempotent": False,
                "status": "PENDING"
            }
        ])

        res = self.agent.resume_automation(run_id, confirm_callback=lambda *a: True)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(res["failed_step"], "Failing Step")

    # ── 6. LOG STATE & RESUME ─────────────────────────────────────────

    def test_log_state_and_safe_resumption(self):
        """Verifies state persistence across interruptions and clean resume."""
        run_id = "test_interrupted_run"
        self.store.create_run(run_id, "Multi-step workflow", "All steps finished")
        steps = [
            {"step_id": "step_1", "name": "Step 1", "tool_name": "inspect_system_health", "tool_args": {}, "is_risky": False, "is_idempotent": True, "status": "DONE", "result_payload": {"success": True}},
            {"step_id": "step_2", "name": "Step 2", "tool_name": "inspect_system_health", "tool_args": {}, "is_risky": False, "is_idempotent": True, "status": "PENDING"}
        ]
        self.store.save_steps(run_id, steps)
        self.store.update_step_status(run_id, 0, "DONE", result_payload={"success": True})

        executed = []
        def on_step(evt, data):
            if evt == "RUNNING":
                executed.append(data["step"]["step_id"])

        res = self.agent.resume_automation(run_id, on_step_change=on_step)
        self.assertTrue(res["success"])
        self.assertNotIn("step_1", executed, "Step 1 was already DONE and must not be repeated!")
        self.assertIn("step_2", executed, "Step 2 was PENDING and must be executed!")

    # ── 7. VERIFY THE OUTCOME ─────────────────────────────────────────

    def test_verify_outcome_against_goal_criteria(self):
        """Verifies outcome validation assesses final system state against initial goal."""
        res = self.agent.start_automation(
            task_prompt="Run workspace cleanup and test health check",
            confirm_callback=lambda *a: True
        )
        outcome = res["outcome"]
        self.assertIn("achieved", outcome)
        self.assertTrue(outcome["achieved"])
        self.assertIn("done_criteria", outcome)
        self.assertGreater(len(outcome["evidence"]), 0)
        self.assertIn("summary", outcome)

    # ── 8. MANAGER INTEGRATION ────────────────────────────────────────

    def test_automation_manager_autonomous_pipeline(self):
        """Verifies AutomationManager wires through to the autonomous pipeline."""
        mgr = AutomationManager(workspace_root=self.ws)
        res = mgr.run_autonomous_task(
            task_prompt="Run workspace cleanup and test health check",
            confirm_callback=lambda *a: True
        )
        self.assertTrue(res["success"])
        self.assertIn("run_id", res)
        history = mgr.get_audit_history()
        self.assertGreaterEqual(len(history), 1)


if __name__ == "__main__":
    unittest.main()
