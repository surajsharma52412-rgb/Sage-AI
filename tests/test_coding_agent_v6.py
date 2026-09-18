"""
Comprehensive Unit Test Suite for SAGE Autonomous Coding Agent Architecture.
Tests all modules across the 9 implementation phases:
1. Master Orchestrator (11-stage autonomous engineering execution loop)
2. Project Analyzer & Cached Map
3. Codebase Indexer (AST symbol parsing, incremental hashing)
4. Context Engine (Priority selection & token budgeting)
5. Persistent Task Manager & DAG (Resumable sessions)
6. Standardized 24-Tool System & Sandbox Runner
7. Test ➔ Debug ➔ Fix Loop (Smart Test Selection & evidence-based repair)
8. Code Reviewer & Security Auditor (Secrets detection, AST checks)
9. Checkpoint Manager & Existing User Changes Guardian
10. All 10 Specialized Internal Workers:
    Architect, Backend, Frontend, Database, Debugger, Tester, Security, Reviewer, DevOps, Documentation
"""
import unittest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import patch

from engine.coding_agent import (
    CodingAgentOrchestrator,
    ProjectAnalyzer,
    CodebaseIndexer,
    ContextEngine,
    PersistentTaskManager,
    TaskScheduler,
    CodingModelRouter,
    ContextFileManager,
    LongContextMemory,
    ToolEcosystem,
    ToolSystem,
    SandboxRunner,
    TestDebugFixLoop,
    CodeReviewer,
    CheckpointManager,
    SafetyController,
    ScalableInfrastructure,
    ArchitectAgent,
    BackendAgent,
    FrontendAgent,
    DatabaseWorker,
    DebuggerWorker,
    QAAgent,
    SecurityWorker,
    ReviewerWorker,
    DevOpsAgent,
    DocumentationAgent,
    CodeIntegrator,
    AutomatedValidator,
    SelfHealingLoop,
    FinalPackager,
)
from engine.coding_agent.safety_controller import SecurityViolation
from engine.agents.coding_agent import CodingAgent
from engine.agents.base_agent import BaseAgent


class TestSageAutonomousCodingAgent(unittest.TestCase):
    """Verifies all components of the SAGE Autonomous Coding Agent."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()

        self.safety = SafetyController(self.workspace)
        self.context_mgr = ContextFileManager(self.workspace, self.safety)
        self.tools = ToolEcosystem(self.workspace, self.context_mgr, self.safety)
        self.memory = LongContextMemory(db_path=self.workspace / ".memory.db")
        self.model_router = CodingModelRouter()

        self.analyzer = ProjectAnalyzer(self.workspace)
        self.indexer = CodebaseIndexer(self.workspace)
        self.context_engine = ContextEngine(self.indexer, self.analyzer, self.memory)
        self.sandbox = SandboxRunner(self.workspace)
        self.tool_sys = ToolSystem(self.workspace, self.safety, self.sandbox, self.analyzer, self.indexer)
        self.checkpoint_mgr = CheckpointManager(self.tool_sys)
        self.task_mgr = PersistentTaskManager(db_path=self.workspace / ".tasks.db")

        # Mock online LLM calls for deterministic offline unit testing
        self._llm_patcher = patch.object(
            BaseAgent,
            "call_llm",
            return_value={
                "success": True,
                "text": (
                    "```python file:backend/server.py\n"
                    "import json\n"
                    "def app(): return {'status': 'ok'}\n"
                    "```\n"
                    "```markdown file:README.md\n"
                    "# Project\nProduction ready.\n"
                    "```\n"
                    "```python file:models.py\n"
                    "class Item: pass\n"
                    "```\n"
                    "```dockerfile file:Dockerfile\n"
                    "FROM python:3.11\n"
                    "```\n"
                ),
                "model_name": "Sage-Mock-V6",
                "provider_id": "test_mock"
            }
        )
        self._llm_patcher.start()

    def tearDown(self):
        self._llm_patcher.stop()
        self.temp_dir.cleanup()

    # ── 1. Phase 1: Project Analyzer & Codebase Indexer Tests ───────────

    def test_project_analyzer_detection_and_cache(self):
        """Verify project analyzer detects frameworks and caches the project map."""
        (self.workspace / "requirements.txt").write_text("fastapi==0.100.0\nuvicorn\n", encoding="utf-8")
        (self.workspace / "main.py").write_text("import fastapi\n", encoding="utf-8")

        proj_map = self.analyzer.analyze_project()
        self.assertIn("FastAPI", proj_map["frameworks"])
        self.assertIn("main.py", proj_map["entry_points"])
        self.assertEqual(proj_map["primary_language"], "python")

        # Verify cached retrieval
        cached = self.analyzer.analyze_project(force_refresh=False)
        self.assertEqual(cached["project_name"], proj_map["project_name"])

    def test_codebase_indexer_symbols_and_incremental_update(self):
        """Verify AST symbol extraction and incremental indexing based on file hashes."""
        py_code = (
            "class UserService:\n"
            "    def authenticate(self, email: str):\n"
            "        return True\n\n"
            "def global_helper():\n"
            "    return 'sage'\n"
        )
        (self.workspace / "service.py").write_text(py_code, encoding="utf-8")

        report = self.indexer.update_index()
        self.assertGreaterEqual(report["total_symbols"], 2)

        symbols = self.indexer.find_symbol("UserService")
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0]["kind"], "class")

        snippets = self.indexer.retrieve_relevant_snippets("authenticate user")
        self.assertIn("UserService", snippets)

        # Incremental check: re-indexing without modifications does 0 re-indexes
        second_report = self.indexer.update_index()
        self.assertEqual(second_report["reindexed_count"], 0)

    def test_context_engine_prioritized_budgeting(self):
        """Verify context engine respects priority order and token budgets."""
        ctx = self.context_engine.build_task_context(
            task_instruction="Implement JWT verification",
            target_files=["models.py"]
        )
        self.assertIn("Active Task", ctx)
        self.assertIn("Implement JWT verification", ctx)
        self.assertIn("Project Architecture Overview", ctx)

    # ── 2. Phase 2: Persistent Task Manager & DAG Tests ─────────────────

    def test_persistent_task_manager_dag_and_resume(self):
        """Verify task DAG compilation and SQLite state persistence for resume."""
        session_id = "sess_001"
        plan = self.task_mgr.create_plan_dag(
            session_id=session_id,
            goal="Build payment gateway integration",
            project_root=str(self.workspace)
        )
        self.assertGreaterEqual(plan["total_tasks"], 5)
        self.assertIn("TASK-001", plan["tasks"])

        # Update a task status
        self.task_mgr.update_task_status("TASK-001", "completed", {"result": "Architecture approved"})

        # Retrieve and verify resume capability
        resumed = self.task_mgr.get_session_state(session_id)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed["tasks"]["TASK-001"]["status"], "completed")

    # ── 3. Phase 3: Standardized Tool System & Sandbox Tests ────────────

    def test_tool_system_structured_return_payload(self):
        """Verify tools return the strict schema: {success, tool, exit_code, stdout, stderr, duration}."""
        # 1. File write
        w_res = self.tool_sys.write_file("test.txt", "Hello Tool System")
        self.assertTrue(w_res["success"])
        self.assertEqual(w_res["tool"], "write_file")
        self.assertEqual(w_res["exit_code"], 0)
        self.assertIn("duration", w_res)

        # 2. File read
        r_res = self.tool_sys.read_file("test.txt")
        self.assertTrue(r_res["success"])
        self.assertEqual(r_res["stdout"], "Hello Tool System")

        # 3. Code tool (Python sandbox)
        py_res = self.tool_sys.run_python("print('SANDBOX_OK')")
        self.assertTrue(py_res["success"])
        self.assertIn("SANDBOX_OK", py_res["stdout"])

    def test_safety_and_security_blocks(self):
        """Verify directory traversal and destructive commands are blocked."""
        with self.assertRaises(SecurityViolation):
            self.safety.validate_safe_path("../../outside.txt")

        blocked_res = self.tool_sys.execute_command("rm -rf /")
        self.assertFalse(blocked_res["success"])
        self.assertIn("Blocked", blocked_res["stderr"])

    # ── 4. Phase 4: Test ➔ Debug ➔ Fix Loop Tests ───────────────────────

    def test_smart_test_selection_and_diagnosis(self):
        """Verify test loop selects affected test files and diagnoses stack traces."""
        (self.workspace / "tests").mkdir(parents=True, exist_ok=True)
        (self.workspace / "tests" / "test_auth.py").write_text("import unittest\n", encoding="utf-8")

        test_loop = TestDebugFixLoop(self.tool_sys, self.indexer)
        selected = test_loop.select_affected_tests(["backend/auth.py"])
        self.assertTrue(any("test_auth.py" in s for s in selected))

        raw_error = (
            'Traceback (most recent call last):\n'
            '  File "backend/auth.py", line 42, in verify_token\n'
            '    raise ValueError("Invalid signature")\n'
            'ValueError: Invalid signature\n'
        )
        diag = test_loop.diagnose_failure(raw_error)
        self.assertEqual(diag["line_no"], 42)
        self.assertIn("ValueError", diag["root_cause"])

    # ── 5. Phase 5: Code Reviewer & Security Auditor Tests ──────────────

    def test_code_reviewer_detects_secrets_and_eval(self):
        """Verify code reviewer flags secrets and dangerous eval/exec calls."""
        insecure_file = self.workspace / "insecure.py"
        insecure_file.write_text(
            'api_key = "sk-1234567890abcdef1234567890abcdef"\n'
            'def run(cmd):\n'
            '    eval(cmd)\n',
            encoding="utf-8"
        )
        reviewer = CodeReviewer(self.tool_sys)
        report = reviewer.review_codebase(files_to_review=["insecure.py"])

        self.assertFalse(report["passed"])
        findings = [f["issue"] for f in report["findings"]]
        self.assertTrue(any("secret" in str(f).lower() or "key" in str(f).lower() for f in findings))
        self.assertTrue(any("eval" in str(f).lower() for f in findings))

    # ── 6. Phase 6: Checkpoint Manager & User Changes Guardian ──────────

    def test_checkpoint_manager_rollback(self):
        """Verify snapshot creation and safe transactional rollback."""
        file_a = self.workspace / "module.py"
        file_a.write_text("v1_original", encoding="utf-8")

        chk = self.checkpoint_mgr.create_checkpoint("T-1", "Pre-edit", ["module.py"])
        self.assertEqual(chk["snapshot"]["module.py"], "v1_original")

        # Corrupt file
        file_a.write_text("v2_corrupted", encoding="utf-8")
        self.assertEqual(file_a.read_text(encoding="utf-8"), "v2_corrupted")

        # Rollback
        rb_res = self.checkpoint_mgr.rollback_to_checkpoint(chk["checkpoint_id"])
        self.assertTrue(rb_res["success"])
        self.assertEqual(file_a.read_text(encoding="utf-8"), "v1_original")

    # ── 7. Phase 7: All 10 Specialized Internal Workers Tests ───────────

    def test_all_10_specialized_internal_workers(self):
        """Verify execution across all 10 specialized internal worker roles."""
        workers = {
            "architect": ArchitectAgent(self.context_mgr, self.tools, self.model_router),
            "backend": BackendAgent(self.context_mgr, self.tools, self.model_router),
            "frontend": FrontendAgent(self.context_mgr, self.tools, self.model_router),
            "database": DatabaseWorker(self.context_mgr, self.tools, self.model_router),
            "debugger": DebuggerWorker(self.context_mgr, self.tools, self.model_router),
            "tester": QAAgent(self.context_mgr, self.tools, self.model_router),
            "security": SecurityWorker(self.context_mgr, self.tools, self.model_router),
            "reviewer": ReviewerWorker(self.context_mgr, self.tools, self.model_router),
            "devops": DevOpsAgent(self.context_mgr, self.tools, self.model_router),
            "documentation": DocumentationAgent(self.context_mgr, self.tools, self.model_router)
        }

        self.assertEqual(len(workers), 10)
        for role, worker in workers.items():
            res = worker.execute({"instruction": f"Run worker task for {role}"}, {})
            self.assertTrue(res["success"], f"Worker {role} execution failed")

    # ── 8. Master 11-Stage End-to-End Orchestrator Test ─────────────────

    def test_master_11_stage_orchestrator_execution(self):
        """Verify the full 11-stage autonomous engineering lifecycle."""
        orchestrator = CodingAgentOrchestrator(workspace_root=self.workspace)

        stages_seen = []
        def on_stage(msg):
            stages_seen.append(msg)

        res = orchestrator.execute_project(
            goal="Build a production-grade course enrollment system with database, auth, and Docker",
            on_stage=on_stage
        )

        self.assertTrue(res["success"])
        self.assertGreaterEqual(len(stages_seen), 10)
        self.assertIn("structured_state", res)
        self.assertEqual(res["structured_state"]["status"], "completed")
        self.assertEqual(res["structured_state"]["progress"], 100)
        self.assertTrue(res["structured_state"]["checklist"]["requirements_understood"])
        self.assertTrue(res["structured_state"]["checklist"]["build_succeeds"])

    # ── 9. Seamless BaseAgent Integration Test ──────────────────────────

    def test_coding_agent_base_agent_wrapper(self):
        """Verify CodingAgent integrates seamlessly as a BaseAgent for Sage Orchestrator."""
        agent = CodingAgent()
        agent.workspace.root_path = self.workspace

        res = agent.execute(
            task_input={"instruction": "Build full stack analytics dashboard with API"},
            context={"task_id": "turn_101"}
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["architecture_version"], "v6")
        self.assertGreaterEqual(len(res["written_files"]), 2)
        self.assertGreaterEqual(len(res["deliverables"]), 1)


if __name__ == "__main__":
    unittest.main()
