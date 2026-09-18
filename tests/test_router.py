"""
Unit tests for FallbackRouter in Sage AI.
"""
import unittest
from engine.router import FallbackRouter


class TestFallbackRouter(unittest.TestCase):

    def setUp(self):
        self.router = FallbackRouter()

    def test_local_fact_routing(self):
        stages = []
        def on_stage(s):
            stages.append(s)

        resp = self.router.route_and_execute(
            prompt="What time is it?",
            on_stage_change=on_stage
        )
        self.assertTrue(resp.success)
        self.assertIn("Current Time", resp.text)
        self.assertEqual(resp.provider_id, "local_facts")
        self.assertTrue(len(stages) > 0)

    def test_local_math_routing(self):
        resp = self.router.route_and_execute(
            prompt="calculate 12 * 8 + 4"
        )
        self.assertTrue(resp.success)
        self.assertIn("100", resp.text)
        self.assertEqual(resp.provider_id, "local_facts")

    def test_local_knowledge_base_match(self):
        resp = self.router.route_and_execute(
            prompt="who are you"
        )
        self.assertTrue(resp.success)
        self.assertIn("Sage AI", resp.text)
        self.assertEqual(resp.provider_id, "local_facts")

    def test_waterfall_fallback_offline(self):
        """When cloud keys and Ollama are off, gracefully routes to local offline fallback."""
        orig_avails = {}
        for key in ["groq", "gemini", "nvidia", "openrouter", "ollama_chat", "ollama_coder"]:
            if key in self.router.providers:
                orig_avails[key] = self.router.providers[key].is_available
                self.router.providers[key].is_available = lambda: False

        try:
            resp = self.router.route_and_execute(
                prompt="Help me draft an email to my colleague"
            )
            self.assertTrue(resp.success)
            self.assertIsNotNone(resp.text)
            self.assertIn("Sage", resp.text)
        finally:
            for key, orig_func in orig_avails.items():
                self.router.providers[key].is_available = orig_func

    def test_cheatsheet_catalog_routing(self):
        resp = self.router.route_and_execute("Show me the Sage AI local knowledge base and cheatsheets.")
        self.assertTrue(resp.success)
        self.assertIn("Cheatsheets", resp.text)
        self.assertEqual(resp.provider_id, "local_facts")

    def test_greetings_routing(self):
        resp = self.router.route_and_execute("Yoooo")
        self.assertTrue(resp.success)
        self.assertIn("Hello! Welcome to Sage AI", resp.text)
        self.assertEqual(resp.provider_id, "local_facts")

    def test_python_cheatsheet_routing(self):
        resp = self.router.route_and_execute("Python cheatsheet")
        self.assertTrue(resp.success)
        self.assertIn("Python", resp.text)
        self.assertEqual(resp.provider_id, "local_facts")


if __name__ == "__main__":
    unittest.main()
