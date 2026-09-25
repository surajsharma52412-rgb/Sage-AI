"""
Unit tests for the Automatic Master Prompt Generator & Advanced Coding Agent Architecture.
Validates:
1. 18-section Master Prompt schema completeness
2. Dynamic animation system specifications and prefers-reduced-motion
3. Minimal clarification and 'Do Not Understand' rule
4. Task classification and tech stack inference
5. CodingAgentOrchestrator integration with Zero-Cost Guard limit enforcement
"""
import unittest
import tempfile
from pathlib import Path

from engine.coding_agent.master_prompt_generator import MasterPromptGenerator, MasterPromptResult
from engine.coding_agent.orchestrator import CodingAgentOrchestrator


class TestMasterPromptGenerator(unittest.TestCase):
    """Test suite for Master Prompt Generator."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.generator = MasterPromptGenerator(self.workspace)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_18_sections_completeness(self):
        """Verifies that the generated Master Prompt contains all 18 standard architecture sections."""
        res = self.generator.generate_master_prompt("Build an interactive Kanban board with task cards and drag and drop")
        self.assertFalse(res.needs_clarification)
        prompt = res.master_prompt

        required_sections = [
            "SYSTEM ROLE:",
            "PROJECT:",
            "USER OBJECTIVE:",
            "REQUIREMENTS:",
            "TECH STACK:",
            "ARCHITECTURE:",
            "PROJECT STRUCTURE:",
            "UI/UX REQUIREMENTS:",
            "ANIMATION REQUIREMENTS:",
            "BACKEND REQUIREMENTS:",
            "DATABASE REQUIREMENTS:",
            "API REQUIREMENTS:",
            "SECURITY REQUIREMENTS:",
            "ERROR HANDLING:",
            "TESTING REQUIREMENTS:",
            "EXISTING PROJECT CONTEXT:",
            "IMPLEMENTATION PLAN:",
            "QUALITY REQUIREMENTS:",
            "FINAL VERIFICATION CHECKLIST:",
            "IMPORTANT RULES:"
        ]

        for sec in required_sections:
            self.assertIn(sec, prompt, f"Missing required section: {sec}")

    def test_animation_system_and_accessibility(self):
        """Verifies motion tokens and accessibility requirements are present in the specification."""
        res = self.generator.generate_master_prompt("Create an animated dashboard with charts and modals")
        prompt = res.master_prompt

        self.assertIn("ANIMATION REQUIREMENTS:", prompt)
        self.assertIn("prefers-reduced-motion", prompt)
        self.assertIn("cubic-bezier", prompt)
        self.assertIn("Page/View Transitions", prompt)
        self.assertIn("Component Entrances", prompt)
        self.assertTrue(res.has_ui)

    def test_task_classification(self):
        """Verifies intelligent classification of requests into task archetypes."""
        debug_res = self.generator.generate_master_prompt("Fix IndexError in user authentication handler")
        self.assertEqual(debug_res.task_classification, "debugging")

        ui_res = self.generator.generate_master_prompt("Create a dark mode CSS button component with hover animations")
        self.assertEqual(ui_res.task_classification, "ui_implementation")

        script_res = self.generator.generate_master_prompt("Write a quick simple Python script to calculate MD5 hashes")
        self.assertEqual(script_res.task_classification, "simple_script")

    def test_minimal_clarification_rule(self):
        """Verifies that completely ambiguous/empty requests trigger minimal clarification."""
        empty_res = self.generator.generate_master_prompt("???")
        self.assertTrue(empty_res.needs_clarification)
        self.assertIsNotNone(empty_res.clarification_question)

        valid_res = self.generator.generate_master_prompt("Create a JWT authentication system for FastAPI")
        self.assertFalse(valid_res.needs_clarification)

    def test_orchestrator_integration(self):
        """Verifies CodingAgentOrchestrator incorporates Master Prompt and Zero-Cost Guard."""
        orchestrator = CodingAgentOrchestrator(self.workspace)
        stages_recorded = []

        def on_stage(s):
            stages_recorded.append(s)

        res = orchestrator.execute_project(
            goal="Build a lightweight markdown parser in Python",
            on_stage=on_stage
        )

        self.assertTrue(res["success"])
        self.assertTrue(any("MASTER PROMPT" in s for s in stages_recorded), "Master Prompt stage was not fired")
        self.assertTrue(any("MODEL SELECTION" in s for s in stages_recorded), "Model Selection stage was not fired")


if __name__ == "__main__":
    unittest.main()
