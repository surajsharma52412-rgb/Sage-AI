"""
Unit tests for Autonomous Project Coding Agent in Sage AI.
"""
import unittest
import tempfile
import json
from pathlib import Path

from engine.project_agent import (
    WorkspaceInspector,
    AgentPlanner,
    AgentExecutor
)
from engine.project_agent.workspace_inspector import WorkspaceSecurityError


class TestProjectAgent(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Scaffold dummy project structure
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("print('hello world')", encoding="utf-8")
        (self.root / "README.md").write_text("# Test Project", encoding="utf-8")
        (self.root / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
        (self.root / "secret.txt").write_text("secret_token_123", encoding="utf-8")

        self.inspector = WorkspaceInspector(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safe_path_resolution(self):
        # Valid path
        safe_path = self.inspector.resolve_safe_path("src/main.py")
        self.assertTrue(safe_path.exists())

        # Path traversal attack detection
        with self.assertRaises(WorkspaceSecurityError):
            self.inspector.resolve_safe_path("../../outside.txt")

        with self.assertRaises(WorkspaceSecurityError):
            self.inspector.resolve_safe_path("../secret.txt")

    def test_workspace_manifest_and_gitignore(self):
        manifest = self.inspector.scan_manifest()
        paths = [item["path"] for item in manifest]

        self.assertIn("src/main.py", paths)
        self.assertIn("README.md", paths)
        # Ignored via .gitignore
        self.assertNotIn("secret.txt", paths)

    def test_plan_parser_and_validator(self):
        planner = AgentPlanner()
        raw_json_str = json.dumps({
            "summary": "Create new module",
            "operations": [
                {"op": "write", "path": "src/utils.py", "content": "def add(a, b): return a + b\n"},
                {"op": "delete", "path": "obsolete.txt", "content": ""}
            ],
            "notes": ["Added basic utils"]
        })

        plan = planner._parse_and_validate_json(raw_json_str, self.inspector)
        self.assertEqual(plan["summary"], "Create new module")
        self.assertEqual(len(plan["operations"]), 2)
        self.assertEqual(plan["operations"][0]["path"], "src/utils.py")

    def test_plan_parser_resilient_escapes(self):
        """Test that invalid escapes from LLM (e.g. CSS colors or regex backslashes) parse without crashing."""
        planner = AgentPlanner()
        # Simulated raw output with invalid escape \# and \s and unescaped \
        bad_escaped_str = '''{
            "summary": "Modernize styles",
            "operations": [
                {"op": "write", "path": "src/styles.css", "content": "color: \\#ffffff; font: 14px \\ sans-serif;"},
            ],
            "notes": ["Fixed styling"]
        }'''
        plan = planner._parse_and_validate_json(bad_escaped_str, self.inspector)
        self.assertEqual(plan["summary"], "Modernize styles")
        self.assertEqual(len(plan["operations"]), 1)
        self.assertEqual(plan["operations"][0]["path"], "src/styles.css")
        self.assertIn("#ffffff", plan["operations"][0]["content"])

    def test_plan_parser_with_thinking_tags_and_fences(self):
        """Test that reasoning models emitting <think>...</think> and markdown code blocks are parsed cleanly."""
        planner = AgentPlanner()
        raw_output = '''<think>
I need to update main.py to say hello autonomous agent.
</think>
```json
{
    "summary": "Update greeting",
    "operations": [
        {"op": "write", "path": "src/main.py", "content": "print('hello autonomous agent')"}
    ]
}
```'''
        plan = planner._parse_and_validate_json(raw_output, self.inspector)
        self.assertEqual(plan["summary"], "Update greeting")
        self.assertEqual(len(plan["operations"]), 1)
        self.assertEqual(plan["operations"][0]["path"], "src/main.py")

    def test_atomic_executor(self):
        executor = AgentExecutor(self.inspector)
        operations = [
            {"op": "write", "path": "src/math_ops.py", "content": "def multiply(x, y): return x * y\n"},
            {"op": "write", "path": "src/main.py", "content": "print('updated main')\n"}
        ]

        diffs_collected = []
        def on_diff(p, d):
            diffs_collected.append((p, d))

        results, diffs = executor._apply_operations(operations, on_diff=on_diff)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "written")
        self.assertEqual(results[1]["status"], "written")

        # Verify file on disk
        target = self.root / "src" / "math_ops.py"
        self.assertTrue(target.exists())
        self.assertIn("def multiply", target.read_text(encoding="utf-8"))

        main_file = self.root / "src" / "main.py"
        self.assertIn("updated main", main_file.read_text(encoding="utf-8"))
        self.assertTrue(len(diffs_collected) > 0)


if __name__ == "__main__":
    unittest.main()
