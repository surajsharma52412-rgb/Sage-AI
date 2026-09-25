"""
Unit Test Suite for the Ultimate Autonomous Coding Agent Architecture.
Validates:
- Request Intelligence Engine (Complexity, Mode, Risk, Ambiguity)
- Project Memory & Context Compression
- Requirement Traceability Matrix & Definition of Done
- Model Benchmark Tracker & Historical Performance Routing
- Multi-Model Review System & Model Disagreement Arbiter
- Safety Approval Gates (Safe autonomous vs user confirmation)
- Master Prompt Generator (20-point Spec & Section 38 Prompt)
- End-to-end Orchestrator execution integration
"""
import shutil
import unittest
from pathlib import Path
from tempfile import mkdtemp

from engine.coding_agent.request_intelligence import (
    RequestIntelligenceEngine,
    ComplexityLevel,
    ProjectMode,
    AmbiguityLevel
)
from engine.coding_agent.project_memory import ProjectMemoryManager
from engine.coding_agent.requirement_traceability import (
    RequirementTraceabilityMatrix,
    RequirementStatus
)
from engine.coding_agent.model_benchmarking import ModelBenchmarkTracker
from engine.coding_agent.multi_model_review import MultiModelReviewSystem
from engine.coding_agent.safety_approval_gates import SafetyApprovalGates, ActionRiskTier
from engine.coding_agent.master_prompt_generator import MasterPromptGenerator
from engine.coding_agent.orchestrator import CodingAgentOrchestrator


class TestUltimateEngineeringSystem(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(mkdtemp(prefix="sage_ultimate_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_request_intelligence_complexity_and_mode(self):
        """Verifies Request Intelligence accurately classifies complexity and mode."""
        engine = RequestIntelligenceEngine(self.test_dir)

        # 1. Trivial snippet
        rep_trivial = engine.analyze_request("format json log")
        self.assertEqual(rep_trivial.complexity, ComplexityLevel.TRIVIAL)

        # 2. Debug existing
        rep_debug = engine.analyze_request("fix traceback in user login")
        self.assertEqual(rep_debug.project_mode, ProjectMode.DEBUG_EXISTING)

        # 3. Enterprise / Complex
        rep_complex = engine.analyze_request("build fullstack saas platform with auth and database")
        self.assertIn(rep_complex.complexity, (ComplexityLevel.COMPLEX, ComplexityLevel.ENTERPRISE))
        self.assertTrue(rep_complex.has_ui)

    def test_request_intelligence_risk_and_ambiguity(self):
        """Verifies destructive risk interception and critical ambiguity detection."""
        engine = RequestIntelligenceEngine(self.test_dir)

        # Destructive action
        rep_destruct = engine.analyze_request("drop table users and format disk")
        self.assertTrue(rep_destruct.risk.has_destructive_ops)
        self.assertTrue(rep_destruct.risk.requires_approval)

        # Safe request
        rep_safe = engine.analyze_request("Build a responsive calculator in vanilla JS")
        self.assertFalse(rep_safe.risk.has_destructive_ops)
        self.assertFalse(rep_safe.risk.requires_approval)
        self.assertEqual(rep_safe.ambiguity_level, AmbiguityLevel.SAFE_ASSUMPTION)

        # Critical ambiguity
        rep_ambig = engine.analyze_request("???")
        self.assertEqual(rep_ambig.ambiguity_level, AmbiguityLevel.CRITICAL)
        self.assertIsNotNone(rep_ambig.clarification_question)

    def test_project_memory_and_context_compression(self):
        """Verifies persistent project memory, context compression, and model handoff."""
        memory_mgr = ProjectMemoryManager(self.test_dir)
        memory_mgr.record_decision("Adopt SQLite", "Zero-config embedded relational store")
        memory_mgr.record_task_completion("Initialize project scaffold")

        # Test persistence
        reloaded = ProjectMemoryManager(self.test_dir)
        self.assertEqual(len(reloaded.memory.important_decisions), 1)
        self.assertEqual(reloaded.memory.important_decisions[0]["title"], "Adopt SQLite")
        self.assertIn("Initialize project scaffold", reloaded.memory.completed_tasks)

        # Test context compression (Section 33)
        comp = memory_mgr.build_compressed_context("Build auth routes", ["auth.py", "models.py"])
        self.assertIn("PROJECT MEMORY CONTEXT:", comp)
        self.assertIn("Adopt SQLite", comp)
        self.assertIn("auth.py", comp)

        # Test model handoff (Section 34)
        handoff = memory_mgr.create_model_handoff(
            target_model="qwen-2.5-coder",
            original_objective="Build auth API",
            master_spec="Spec details...",
            files_changed=["models.py"],
            previous_output="Models created.",
            errors=[],
            remaining_tasks=["auth routes"]
        )
        self.assertEqual(handoff["target_model"], "qwen-2.5-coder")
        self.assertEqual(handoff["project_state"]["files_changed"], ["models.py"])

    def test_requirement_traceability_and_definition_of_done(self):
        """Verifies full requirements traceability matrix and Definition of Done."""
        matrix = RequirementTraceabilityMatrix()
        req1 = matrix.register_requirement("functional", "User registration endpoint")
        req2 = matrix.register_requirement("ui", "Responsive registration modal")

        # Initial state
        rep_init = matrix.get_traceability_report()
        self.assertEqual(rep_init["pending"], 2)

        # Link implementation
        matrix.link_implementation(req1, "src/auth.py")
        matrix.link_test(req1, "tests/test_auth.py")
        matrix.mark_verified(req1, passed=True)

        rep_mid = matrix.get_traceability_report()
        self.assertEqual(rep_mid["verified"], 1)
        self.assertEqual(rep_mid["pending"], 1)

        # Evaluate Definition of Done (Section 30)
        dod = matrix.evaluate_definition_of_done(
            tests_passed=True,
            security_passed=True,
            ui_checked=True,
            docs_updated=True
        )
        self.assertIn("readiness_percentage", dod)
        self.assertIn("gates", dod)

    def test_model_benchmarking_and_archetype_routing(self):
        """Verifies historical telemetry recording and empirical best model recommendation."""
        tracker = ModelBenchmarkTracker(self.test_dir)

        # Record multiple executions
        tracker.record_execution(
            model_name="gemini-2.0-flash",
            provider_id="gemini",
            archetype="ui_implementation",
            latency_s=1.2,
            cost_rs=0.0,
            tokens_used=1200,
            tests_passed=True,
            bugs_detected=0,
            success=True
        )
        tracker.record_execution(
            model_name="gemini-2.0-flash",
            provider_id="gemini",
            archetype="ui_implementation",
            latency_s=1.5,
            cost_rs=0.0,
            tokens_used=1300,
            tests_passed=True,
            bugs_detected=0,
            success=True
        )

        best = tracker.get_best_model_for_archetype(
            "ui_implementation",
            ["gemini-2.0-flash", "llama-3.3-70b-versatile"]
        )
        self.assertEqual(best, "gemini-2.0-flash")

    def test_multi_model_review_and_safety_gates(self):
        """Verifies security auditing, reduced-motion checking, and safety approval gates."""
        # 1. MultiModelReviewSystem
        rev_sys = MultiModelReviewSystem(self.test_dir)
        bad_file = self.test_dir / "bad_code.py"
        bad_file.write_text("api_key = 'sk-12345678901234567890'\neval('2+2')\n", encoding="utf-8")

        css_file = self.test_dir / "style.css"
        css_file.write_text(".btn { transition: all 0.3s ease; }", encoding="utf-8")

        report = rev_sys.execute_multi_review(["bad_code.py", "style.css"], has_ui=True)
        self.assertFalse(report.security_clean)
        self.assertTrue(any(f.category == "security" and f.severity == "CRITICAL" for f in report.findings))
        self.assertTrue(any(f.category == "ui_ux" and "reduced-motion" in f.issue for f in report.findings))

        # Model Disagreement Arbiter (Section 35)
        arb_res = rev_sys.arbitrate_model_disagreement(
            candidate_a={"code": "def run(): return 42"},
            candidate_b={"code": "api_key = 'sk-secret-token-key-123456'"}
        )
        self.assertEqual(arb_res["winner"], "candidate_a")

        # 2. Safety Approval Gates (Section 16 & 36)
        gates = SafetyApprovalGates(self.test_dir)
        res_safe = gates.evaluate_command("python -m unittest tests/test_main.py")
        self.assertTrue(res_safe.is_safe_to_proceed)
        self.assertEqual(res_safe.risk_tier, ActionRiskTier.SAFE_AUTONOMOUS)

        res_danger = gates.evaluate_command("git reset --hard HEAD~1")
        self.assertFalse(res_danger.is_safe_to_proceed)
        self.assertEqual(res_danger.risk_tier, ActionRiskTier.REQUIRES_USER_APPROVAL)
        self.assertIn("Hard reset", res_danger.reason)

    def test_master_prompt_generator_and_orchestrator(self):
        """Verifies 20-point Spec synthesis, Section 38 Prompt, and Orchestrator execution."""
        gen = MasterPromptGenerator(self.test_dir)
        res = gen.generate_master_prompt("Build an animated Kanban board in vanilla JS and CSS")

        # 20-Point Spec validation
        self.assertIn("MASTER ENGINEERING SPECIFICATION", res.engineering_spec)
        self.assertIn("1. PROJECT OBJECTIVE:", res.engineering_spec)
        self.assertIn("15. ANIMATION SYSTEM:", res.engineering_spec)
        self.assertIn("20. ACCEPTANCE CRITERIA:", res.engineering_spec)

        # Section 38 Coding Model Prompt validation
        self.assertIn("You are the implementation engineer for this project.", res.coding_model_prompt)
        self.assertIn("PROJECT OBJECTIVE:", res.coding_model_prompt)
        self.assertIn("IMPLEMENTATION RULES:", res.coding_model_prompt)

        # Section 37 Continuous Improvement categorization
        self.assertIn("Required", res.improvements)
        self.assertIn("Recommended", res.improvements)

        # End-to-end Orchestrator execution
        orchestrator = CodingAgentOrchestrator(workspace_root=self.test_dir)
        exec_res = orchestrator.execute_project("Build a lightweight markdown parser in Python")

        self.assertTrue(exec_res.get("success"))
        self.assertIn("traceability", exec_res)
        self.assertIn("definition_of_done", exec_res)
        self.assertIn("multi_model_review", exec_res)
        self.assertIn("master_engineering_spec", exec_res)
        self.assertIn("coding_model_prompt", exec_res)


if __name__ == "__main__":
    unittest.main()
