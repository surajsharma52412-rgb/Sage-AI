"""
Tests for Thinking Section parsing, Model Usage tracking, and Provider Model Selection.
"""
import unittest
import tempfile
import os
import shutil
from database.db_manager import DatabaseManager
from ui.components.message_bubble import extract_thinking
from engine.router import FallbackRouter


class TestNewFeatures(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_usage.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_thinking_with_tags(self):
        raw = "<think>Analyzing user code for syntax issues.\nChecking imports.</think>Here is the corrected solution:\n```python\nprint('hello')\n```"
        thinking, final_text = extract_thinking(raw)
        self.assertIsNotNone(thinking)
        self.assertIn("Analyzing user code", thinking)
        self.assertIn("Here is the corrected solution", final_text)
        self.assertNotIn("<think>", final_text)
        self.assertNotIn("</think>", final_text)

    def test_extract_thinking_without_tags(self):
        raw = "Direct response without any chain-of-thought."
        thinking, final_text = extract_thinking(raw)
        self.assertIsNone(thinking)
        self.assertEqual(final_text, raw)

    def test_model_usage_logging_and_summary(self):
        # Log several queries
        self.db.log_model_usage("groq", "llama-3.3-70b-versatile", prompt_tokens=120, completion_tokens=85, latency_ms=420.0, success=True)
        self.db.log_model_usage("groq", "llama-3.3-70b-versatile", prompt_tokens=80, completion_tokens=60, latency_ms=380.0, success=True)
        self.db.log_model_usage("nvidia", "meta/llama-3.1-70b-instruct", prompt_tokens=200, completion_tokens=150, latency_ms=850.0, success=True)
        self.db.log_model_usage("openrouter", "deepseek/deepseek-r1", prompt_tokens=300, completion_tokens=250, latency_ms=1200.0, success=False)

        summary = self.db.get_model_usage_summary()
        self.assertEqual(summary["total_requests"], 4)
        self.assertEqual(summary["total_tokens"], (120+85) + (80+60) + (200+150) + (300+250))
        self.assertGreater(summary["avg_latency_ms"], 0)
        self.assertTrue(any(p["provider_id"] == "groq" for p in summary["by_provider"]))

        by_model = summary["by_model"]
        self.assertEqual(len(by_model), 3)

        # Reset check
        self.db.reset_model_usage()
        reset_summary = self.db.get_model_usage_summary()
        self.assertEqual(reset_summary["total_requests"], 0)
        self.assertEqual(reset_summary["total_tokens"], 0)

    def test_router_map_model_selection(self):
        router = FallbackRouter()
        
        # Test parenthesized model format
        prov, model = router._map_model_selection("NVIDIA NIM (meta/llama-3.1-70b-instruct)")
        self.assertEqual(prov, "nvidia")
        self.assertEqual(model, "meta/llama-3.1-70b-instruct")

        prov, model = router._map_model_selection("Groq (llama-3.3-70b-versatile)")
        self.assertEqual(prov, "groq")
        self.assertEqual(model, "llama-3.3-70b-versatile")

        prov, model = router._map_model_selection("Google Gemini (gemini-2.0-flash)")
        self.assertEqual(prov, "gemini")
        self.assertEqual(model, "gemini-2.0-flash")

        prov, model = router._map_model_selection("OpenRouter (deepseek/deepseek-r1)")
        self.assertEqual(prov, "openrouter")
        self.assertEqual(model, "deepseek/deepseek-r1")

        prov, model = router._map_model_selection("Ollama Local (qwen2.5-coder:7b)")
        self.assertEqual(prov, "ollama_coder")
        self.assertEqual(model, "qwen2.5-coder:7b")

        prov, model = router._map_model_selection("Ollama Local (llama3.2:latest)")
        self.assertEqual(prov, "ollama_chat")
        self.assertEqual(model, "llama3.2:latest")


if __name__ == "__main__":
    unittest.main()
