"""
Comprehensive Unit Test Suite for Sage Multi-Agentic AI Architecture.
Tests:
- Task Decomposer (Goal DAG decomposition)
- Agent Router (Intent and agent selection)
- Workflow Manager (Pipeline execution and status transitions)
- Self-Reflection (Deliverable quality assessment and AST validation)
- Memory Manager & Shared Memory (Short-term & long-term sync)
- Communication Bus (Inter-agent pub/sub messaging)
- Vector Database (Pure-Python cosine similarity semantic search)
- Secure Sandbox & Quality Evaluator (Safety and syntax verification)
- Specialized AI Agents (Research, Coding, Image/Media, Data Analysis, Content, Execution, Planning)
"""
import unittest
from pathlib import Path

from config import (
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_IMAGE_MEDIA,
    AGENT_DATA_ANALYSIS,
    AGENT_CONTENT,
    AGENT_EXECUTION,
    AGENT_PLANNING,
    TASK_STATUS_COMPLETED,
)
from engine.orchestrator import (
    TaskDecomposer,
    AgentRouter,
    WorkflowManager,
    SelfReflection,
    MemoryManager,
    AgentOrchestrator,
)
from engine.shared_resources import (
    SharedMemory,
    KnowledgeBase,
    VectorDatabase,
    ProjectWorkspace,
    CommunicationBus,
)
from engine.execution import SecureSandbox, ProcessRunner
from engine.governance import QualityEvaluator, CostTracker, AuditLogger
from engine.agents import (
    BaseAgent,
    ResearchAgent,
    CodingAgent,
    ImageMediaAgent,
    DataAnalysisAgent,
    ContentAgent,
    ExecutionAgent,
    PlanningAgent,
)


from unittest.mock import patch


class TestSageMultiAgentArchitecture(unittest.TestCase):
    """Verifies all components of the Sage Multi-Agentic AI Architecture."""

    def setUp(self):
        self.decomposer = TaskDecomposer()
        self.router = AgentRouter()
        self.workflow = WorkflowManager(agent_router=self.router)
        self.reflection = SelfReflection()
        self.memory = MemoryManager()
        self.orchestrator = AgentOrchestrator()

        self._llm_patcher = patch.object(
            BaseAgent,
            "call_llm",
            return_value={
                "success": True,
                "text": (
                    "```python\ndef celsius_to_fahrenheit(c: float) -> float:\n    return (c * 9.0 / 5.0) + 32.0\n```\n"
                    "Comprehensive solution and documentation."
                ),
                "model_name": "Sage Mock Core",
                "provider_id": "test_mock",
                "citations": []
            }
        )
        self._llm_patcher.start()

    def tearDown(self):
        self._llm_patcher.stop()

    # --- 1. Task Decomposer Tests ---

    def test_composite_goal_decomposition(self):
        """Verify complex goal decomposes into appropriate specialized agent steps."""
        goal = "Build a website, create images, write code, analyze data and deploy it"
        steps = self.decomposer.decompose(goal)

        self.assertGreaterEqual(len(steps), 3)
        agent_types = [s["agent_type"] for s in steps]

        # Verify specialized agents assigned
        self.assertIn(AGENT_CODING, agent_types)
        self.assertIn(AGENT_IMAGE_MEDIA, agent_types)
        self.assertIn(AGENT_DATA_ANALYSIS, agent_types)

        # Verify dependency chaining
        for i in range(1, len(steps)):
            self.assertIn(steps[i-1]["id"], steps[i]["depends_on"])

    def test_single_agent_goal_decomposition(self):
        """Single intent query produces focused single-agent step."""
        steps = self.decomposer.decompose("Write a quick Python merge sort algorithm")
        self.assertGreaterEqual(len(steps), 1)
        self.assertEqual(steps[0]["agent_type"], AGENT_CODING)

    # --- 2. Agent Router Tests ---

    def test_agent_query_routing(self):
        """Test query routing matches the 7 specialized agent roles."""
        self.assertEqual(self.router.route_query("Search latest news on quantum computing"), AGENT_RESEARCH)
        self.assertEqual(self.router.route_query("Write a PySide6 table widget class"), AGENT_CODING)
        self.assertEqual(self.router.route_query("Generate image of a neon cybernetic city"), AGENT_IMAGE_MEDIA)
        self.assertEqual(self.router.route_query("Analyze data metrics from CSV"), AGENT_DATA_ANALYSIS)
        self.assertEqual(self.router.route_query("Draft a documentation guide for developers"), AGENT_CONTENT)
        self.assertEqual(self.router.route_query("run pytest tests/"), AGENT_EXECUTION)
        self.assertEqual(self.router.route_query("Plan a project roadmap and milestones"), AGENT_PLANNING)

    def test_agent_instantiation(self):
        """Verify router can instantiate all 7 agents with their correct names."""
        for role in (AGENT_RESEARCH, AGENT_CODING, AGENT_IMAGE_MEDIA, AGENT_DATA_ANALYSIS,
                     AGENT_CONTENT, AGENT_EXECUTION, AGENT_PLANNING):
            agent = self.router.get_agent_instance(role)
            self.assertEqual(agent.name, role)

    # --- 3. Shared Memory & Communication Bus Tests ---

    def test_shared_memory_read_write(self):
        """Tests short-term and persistent shared memory operations."""
        mem = SharedMemory()
        mem.set("test_key_temp", {"val": 42}, is_long_term=False, memory_type="testing")
        self.assertEqual(mem.get("test_key_temp"), {"val": 42})

        mem.set("test_key_persist", "persistent_value", is_long_term=True, memory_type="config")
        self.assertEqual(mem.get("test_key_persist"), "persistent_value")

        mem.clear_short_term()
        # Short term was cleared
        self.assertIsNone(mem.get("test_key_temp"))
        # Persistent survives short-term clear
        self.assertEqual(mem.get("test_key_persist"), "persistent_value")

    def test_communication_bus_messaging(self):
        """Tests inter-agent message passing and event broadcast."""
        bus = CommunicationBus()
        received = []

        def on_msg(evt):
            received.append(evt)

        bus.subscribe("Coding Agent", on_msg)
        bus.send_message(
            from_agent="Research Agent",
            to_agent="Coding Agent",
            message_type="research_brief",
            content="Use React 19 and Vite for the frontend."
        )

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["from_agent"], "Research Agent")
        self.assertEqual(received[0]["to_agent"], "Coding Agent")
        self.assertIn("React 19", received[0]["content"])

    # --- 4. Vector Database Tests ---

    def test_vector_db_embedding_and_search(self):
        """Tests TF-IDF normalized embedding generation and cosine similarity search."""
        vdb = VectorDatabase()
        doc_id = "test_doc_python"
        vdb.add_document(
            doc_id=doc_id,
            title="Python Asyncio Event Loop",
            content="Asyncio is a library to write concurrent code using the async/await syntax in Python."
        )

        results = vdb.search("concurrent async await python", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], doc_id)
        self.assertGreater(results[0]["score"], 0.1)

    # --- 5. Secure Sandbox & Quality Evaluator Tests ---

    def test_sandbox_syntax_validation(self):
        """Tests static AST parsing and error detection in sandbox."""
        sandbox = SecureSandbox()
        valid_code = "def hello():\n    return 'world'\n"
        invalid_code = "def hello(\n    broken syntax"

        self.assertTrue(sandbox.validate_syntax(valid_code)["valid"])
        self.assertFalse(sandbox.validate_syntax(invalid_code)["valid"])

    def test_sandbox_safe_execution(self):
        """Tests isolated code execution in sandbox."""
        sandbox = SecureSandbox()
        code = "print('SAGE_SANDBOX_SUCCESS')"
        res = sandbox.execute_code(code)
        self.assertTrue(res["success"])
        self.assertIn("SAGE_SANDBOX_SUCCESS", res["stdout"])

    def test_quality_evaluator(self):
        """Tests deliverable quality evaluation."""
        evaluator = QualityEvaluator()
        good_code = "import os\n\ndef get_path():\n    return os.getcwd()\n"
        bad_code = "def broken():"

        self.assertTrue(evaluator.evaluate_code(good_code)["passed"])
        self.assertFalse(evaluator.evaluate_code(bad_code)["passed"])

    # --- 6. Self-Reflection & Auto-Repair Tests ---

    def test_self_reflection_evaluation(self):
        """Tests self-reflection score on valid deliverables."""
        deliverables = [
            {
                "type": "code_solution",
                "title": "Calculator",
                "content": "def add(a, b):\n    return a + b\n"
            },
            {
                "type": "written_content",
                "title": "Documentation",
                "content": "This is a complete architectural overview of the calculator service with detailed explanations."
            }
        ]
        res = self.reflection.evaluate_results("Build calculator with documentation", deliverables)
        self.assertTrue(res["passed"])
        self.assertGreaterEqual(res["score"], 0.7)

    # --- 7. Project Workspace Tests ---

    def test_workspace_safe_operations(self):
        """Tests path traversal blocking and sandboxed workspace file IO."""
        ws = ProjectWorkspace()
        # Safe write & read
        ws.write_file("test_artifact.txt", "Sage Multi-Agent Architecture")
        content = ws.read_file("test_artifact.txt")
        self.assertEqual(content, "Sage Multi-Agent Architecture")

        # Traversal attempt blocked
        with self.assertRaises(PermissionError):
            ws.resolve_safe_path("../../../../../windows/system32/cmd.exe")

        # Cleanup
        ws.delete_file("test_artifact.txt")

    # --- 8. Specialized Agents Direct Execution Tests ---

    def test_data_analysis_agent(self):
        """Tests Data Analysis Agent statistical calculations."""
        agent = DataAnalysisAgent()
        csv_data = "item,sales\nA,100\nB,200\nC,300"
        res = agent.execute({"instruction": "Calculate sales statistics", "data": csv_data})
        self.assertTrue(res["success"])
        self.assertEqual(res["agent"], AGENT_DATA_ANALYSIS)
        metrics = res.get("metrics", {}).get("numeric_stats", {}).get("sales", {})
        self.assertEqual(metrics.get("mean"), 200.0)

    def test_execution_agent_command(self):
        """Tests Execution Agent command processing."""
        agent = ExecutionAgent()
        res = agent.execute({"instruction": "echo SAGE_EXECUTION_TEST", "is_command": True})
        self.assertTrue(res["success"])
        self.assertEqual(res["agent"], AGENT_EXECUTION)
        self.assertIn("SAGE_EXECUTION_TEST", res["summary"])

    # --- 9. Full End-to-End Orchestrator Goal Test ---

    def test_orchestrator_goal_execution(self):
        """Tests end-to-end multi-agent orchestration pipeline with deterministic offline mock."""
        goal = "Plan, write code, and draft documentation for a Python temperature converter"
        stages = []
        steps_seen = []

        def on_stage(st):
            stages.append(st)

        def on_step(st):
            steps_seen.append(st)

        res = self.orchestrator.orchestrate_goal(
            goal=goal,
            on_stage=on_stage,
            on_step_update=on_step
        )

        self.assertTrue(res["success"])
        self.assertGreaterEqual(len(res["steps"]), 2)
        self.assertGreaterEqual(len(res["deliverables"]), 1)
        self.assertIn("🎯 Goal Accomplished", res["final_summary"])
        self.assertTrue(len(stages) > 0)


if __name__ == "__main__":
    unittest.main()
