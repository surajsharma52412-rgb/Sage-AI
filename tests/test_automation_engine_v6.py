"""
Unit & Integration Test Suite for SAGE AI Visual Automation Engine v6.
"""
import unittest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from engine.automation.workflow_models import (
    Workflow, WorkflowNode, WorkflowEdge, NodeType, NodeCategory, StepStatus, StepResult
)
from engine.automation.workflow_executor import WorkflowExecutor, VariableContext
from engine.automation.ai_workflow_generator import AIWorkflowGenerator
from database.db_manager import get_db


class TestAutomationEngineV6(unittest.TestCase):

    def setUp(self):
        self.db = get_db()
        self.db.init_db()

    def test_workflow_node_and_edge_serialization(self):
        node = WorkflowNode(
            node_id="n1",
            title="Fetch Unread Emails",
            node_type=NodeType.ACTION,
            category=NodeCategory.EMAIL,
            action="fetch_emails",
            params={"count": 5},
            requires_approval=True,
            retry_count=2
        )
        d = node.to_dict()
        self.assertEqual(d["id"], "n1")
        self.assertEqual(d["type"], "action")
        self.assertEqual(d["category"], "email")
        self.assertTrue(d["requires_approval"])

        restored = WorkflowNode.from_dict(d)
        self.assertEqual(restored.title, "Fetch Unread Emails")
        self.assertEqual(restored.retry_count, 2)

        edge = WorkflowEdge(source_id="n1", target_id="n2", source_port="output")
        ed = edge.to_dict()
        self.assertEqual(ed["source_id"], "n1")
        self.assertEqual(ed["target_id"], "n2")

    def test_variable_context_interpolation(self):
        ctx = VariableContext(initial_vars={"recipient": "boss@company.com", "urgent": True})
        ctx.set_node_output("ai_step", {"summary": "Server latency is high."})

        self.assertEqual(ctx.resolve("{{recipient}}"), "boss@company.com")
        self.assertEqual(ctx.resolve("{{nodes.ai_step.summary}}"), "Server latency is high.")

        msg = ctx.resolve("Alert: {{nodes.ai_step.summary}} Sent to {{recipient}}")
        self.assertEqual(msg, "Alert: Server latency is high. Sent to boss@company.com")

        payload = {"to": "{{recipient}}", "body": "{{nodes.ai_step.summary}}"}
        res = ctx.resolve(payload)
        self.assertEqual(res["to"], "boss@company.com")
        self.assertEqual(res["body"], "Server latency is high.")

    def test_natural_language_workflow_generator(self):
        wf_email = AIWorkflowGenerator.generate_from_prompt("Read my morning emails and summarize my agenda")
        self.assertEqual(wf_email.category, NodeCategory.EMAIL.value)
        self.assertGreaterEqual(len(wf_email.nodes), 4)

        wf_shop = AIWorkflowGenerator.generate_from_prompt("Track GPU prices and alert me with approval")
        self.assertEqual(wf_shop.category, NodeCategory.SHOPPING.value)

        wf_gh = AIWorkflowGenerator.generate_from_prompt("When a github issue is opened run coding agent to fix it")
        self.assertEqual(wf_gh.category, NodeCategory.GITHUB.value)

        wf_db = AIWorkflowGenerator.generate_from_prompt("Optimize sqlite database and vacuum tables")
        self.assertEqual(wf_db.category, NodeCategory.DATABASE.value)

    def test_built_in_templates_gallery(self):
        templates = AIWorkflowGenerator.get_all_templates()
        self.assertGreaterEqual(len(templates), 6)
        names = [t.name for t in templates]
        self.assertTrue(any("Morning" in n for n in names))
        self.assertTrue(any("GitHub" in n for n in names))
        self.assertTrue(any("Price" in n or "Buy" in n for n in names))
        self.assertTrue(any("File" in n for n in names))
        self.assertTrue(any("Code" in n or "Audit" in n for n in names))
        self.assertTrue(any("Database" in n for n in names))

    def test_executor_linear_dag(self):
        n1 = WorkflowNode(node_id="start", title="Trigger", node_type=NodeType.TRIGGER, position={"x": 50, "y": 50})
        n2 = WorkflowNode(node_id="ai_step", title="AI Gen", node_type=NodeType.AI, params={"prompt": "Hello"}, position={"x": 250, "y": 50})
        n3 = WorkflowNode(node_id="notify", title="Notify", node_type=NodeType.NOTIFICATION, params={"message": "Done"}, position={"x": 450, "y": 50})

        wf = Workflow(
            name="Test Linear",
            nodes=[n1, n2, n3],
            edges=[
                WorkflowEdge(source_id="start", target_id="ai_step"),
                WorkflowEdge(source_id="ai_step", target_id="notify")
            ]
        )

        executor = WorkflowExecutor(wf, is_dry_run=True)
        res = executor.execute()
        self.assertEqual(res["status"], "completed")
        self.assertEqual(len(res["step_results"]), 3)
        self.assertEqual(res["step_results"]["notify"]["status"], "completed")

    def test_executor_conditional_branching(self):
        n_trig = WorkflowNode(node_id="trig", title="Start", node_type=NodeType.TRIGGER)
        n_cond = WorkflowNode(
            node_id="cond",
            title="Check Condition",
            node_type=NodeType.CONDITION,
            condition_expression="{{score}} >= 80"
        )
        n_pass = WorkflowNode(node_id="pass_branch", title="Passed", node_type=NodeType.NOTIFICATION, params={"message": "Pass"})
        n_fail = WorkflowNode(node_id="fail_branch", title="Failed", node_type=NodeType.NOTIFICATION, params={"message": "Fail"})

        wf = Workflow(
            name="Test Condition",
            variables={"score": 95},
            nodes=[n_trig, n_cond, n_pass, n_fail],
            edges=[
                WorkflowEdge(source_id="trig", target_id="cond"),
                WorkflowEdge(source_id="cond", target_id="pass_branch", source_port="true"),
                WorkflowEdge(source_id="cond", target_id="fail_branch", source_port="false")
            ]
        )

        executor = WorkflowExecutor(wf, is_dry_run=True)
        res = executor.execute()
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["step_results"]["pass_branch"]["status"], "completed")
        self.assertEqual(res["step_results"]["fail_branch"]["status"], "skipped")

    def test_dry_run_safety_simulation(self):
        risky_node = WorkflowNode(
            node_id="buy",
            title="Place Purchase Order",
            node_type=NodeType.ACTION,
            category=NodeCategory.SHOPPING,
            action="place_order",
            params={"item": "GPU", "price": 499},
            requires_approval=True
        )
        wf = Workflow(name="Dry Run Shopping", nodes=[risky_node], edges=[])
        executor = WorkflowExecutor(wf, is_dry_run=True)
        res = executor.execute()
        self.assertEqual(res["status"], "completed")
        step_out = res["step_results"]["buy"]["output_data"]
        self.assertTrue(step_out.get("simulated"))

    def test_approval_gate_resolution(self):
        n_trig = WorkflowNode(node_id="t1", title="Start", node_type=NodeType.TRIGGER)
        n_app = WorkflowNode(
            node_id="app1",
            title="External Deploy",
            node_type=NodeType.ACTION,
            action="deploy",
            requires_approval=True
        )
        wf = Workflow(name="Approval Test", nodes=[n_trig, n_app], edges=[WorkflowEdge(source_id="t1", target_id="app1")])

        executor = WorkflowExecutor(wf, is_dry_run=False)

        def auto_approve():
            time.sleep(0.2)
            approvals = self.db.get_pending_approvals()
            for a in approvals:
                self.db.resolve_workflow_approval(a["id"], status="approved")

        import threading
        t = threading.Thread(target=auto_approve, daemon=True)
        t.start()

        res = executor.execute()
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["step_results"]["app1"]["status"], "completed")

    def test_workflow_database_crud(self):
        wf = AIWorkflowGenerator.get_morning_briefing_template()
        wid = self.db.save_workflow(wf.to_dict())
        self.assertIsNotNone(wid)

        loaded = self.db.get_workflow(wid)
        self.assertEqual(loaded["name"], wf.name)
        self.assertEqual(len(loaded["nodes"]), len(wf.nodes))

        loaded["name"] = "Updated Morning Routine"
        self.db.save_workflow(loaded)
        reloaded = self.db.get_workflow(wid)
        self.assertEqual(reloaded["name"], "Updated Morning Routine")

        deleted = self.db.delete_workflow(wid)
        self.assertTrue(deleted)
        self.assertIsNone(self.db.get_workflow(wid))


if __name__ == "__main__":
    unittest.main()
