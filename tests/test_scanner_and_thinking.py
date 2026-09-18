"""
Comprehensive Unit Tests for Model Scanner, Provider Quotas, and Live Thinking.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from database.db_manager import DatabaseManager
from engine.model_scanner import ModelScanner
from ui.components.message_bubble import extract_thinking


class TestScannerAndThinking(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_scanner.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_discovered_models_persistence(self):
        models = [
            {
                "model_name": "meta/llama-3.1-70b-instruct",
                "display_name": "llama-3.1-70b-instruct",
                "description": "meta/llama-3.1-70b-instruct",
                "context_length": 128000,
                "is_free": 1
            },
            {
                "model_name": "deepseek-ai/deepseek-r1",
                "display_name": "deepseek-r1",
                "description": "DeepSeek R1 reasoning",
                "context_length": 64000,
                "is_free": 1
            }
        ]
        self.db.save_discovered_models("nvidia", models)
        retrieved = self.db.get_discovered_models("nvidia")
        self.assertEqual(len(retrieved), 2)
        names = [m["model_name"] for m in retrieved]
        self.assertIn("meta/llama-3.1-70b-instruct", names)
        self.assertIn("deepseek-ai/deepseek-r1", names)

        # Clear test
        self.db.clear_discovered_models("nvidia")
        self.assertEqual(len(self.db.get_discovered_models("nvidia")), 0)

    def test_provider_quotas_persistence(self):
        quota = {
            "total_limit": 1000.0,
            "used_amount": 12.0,
            "remaining_amount": 988.0,
            "currency_or_unit": "Credits",
            "is_free_tier": True,
            "details": {"plan": "Starter Free Tier"}
        }
        self.db.save_provider_quota("nvidia", quota)
        retrieved = self.db.get_provider_quota("nvidia")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["total_limit"], 1000.0)
        self.assertEqual(retrieved["remaining_amount"], 988.0)
        self.assertEqual(retrieved["currency_or_unit"], "Credits")
        self.assertEqual(retrieved["details"]["plan"], "Starter Free Tier")

        all_q = self.db.get_all_provider_quotas()
        self.assertIn("nvidia", all_q)

    def test_token_usage_stats_aggregation(self):
        self.db.log_model_usage("nvidia", "meta/llama-3.1-70b-instruct", prompt_tokens=150, completion_tokens=50, latency_ms=500.0)
        self.db.log_model_usage("nvidia", "meta/llama-3.1-70b-instruct", prompt_tokens=200, completion_tokens=100, latency_ms=600.0)
        self.db.log_model_usage("groq", "llama-3.3-70b-versatile", prompt_tokens=80, completion_tokens=40, latency_ms=250.0)

        stats = self.db.get_model_token_usage_stats()
        self.assertIn("meta/llama-3.1-70b-instruct", stats)
        self.assertIn("llama-3.3-70b-versatile", stats)

        nv_stat = stats["meta/llama-3.1-70b-instruct"]
        self.assertEqual(nv_stat["requests"], 2)
        self.assertEqual(nv_stat["prompt_tokens"], 350)
        self.assertEqual(nv_stat["completion_tokens"], 150)
        self.assertEqual(nv_stat["total_tokens"], 500)

    @patch("engine.model_scanner.get_db")
    @patch("engine.model_scanner.requests.get")
    def test_scan_openrouter_mock(self, mock_get, mock_get_db):
        mock_get_db.return_value = self.db

        # Mock auth key response then models response
        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {
            "data": {
                "limit": 10.0,
                "usage": 2.5,
                "limit_remaining": 7.5,
                "is_free_tier": False
            }
        }

        models_resp = MagicMock()
        models_resp.status_code = 200
        models_resp.json.return_value = {
            "data": [
                {
                    "id": "qwen/qwen-2.5-coder-32b-instruct",
                    "name": "Qwen 2.5 Coder 32B",
                    "context_length": 32768,
                    "pricing": {"prompt": "0", "completion": "0"}
                },
                {
                    "id": "deepseek/deepseek-r1:free",
                    "name": "DeepSeek R1 Free",
                    "context_length": 65536,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.side_effect = [auth_resp, models_resp]

        models, quota = ModelScanner.scan_openrouter("fake-sk-or-123")
        self.assertEqual(len(models), 2)
        self.assertIsNotNone(quota)
        self.assertEqual(quota["remaining_amount"], 7.5)
        self.assertEqual(models[1]["is_free"], 1)

    @patch("engine.model_scanner.get_db")
    @patch("engine.model_scanner.requests.get")
    def test_scan_groq_mock(self, mock_get, mock_get_db):
        mock_get_db.return_value = self.db

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": [
                {"id": "llama-3.3-70b-versatile", "active": True, "context_window": 128000},
                {"id": "mixtral-8x7b-32768", "active": True, "context_window": 32768},
                {"id": "whisper-large-v3", "active": True, "context_window": 0}  # Should be skipped
            ]
        }
        mock_get.return_value = resp

        models = ModelScanner.scan_groq("fake-gsk-123")
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["model_name"], "llama-3.3-70b-versatile")
        self.assertEqual(models[0]["context_length"], 128000)

    @patch("engine.model_scanner.get_db")
    @patch("engine.model_scanner.requests.get")
    def test_scan_nvidia_mock(self, mock_get, mock_get_db):
        mock_get_db.return_value = self.db

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": [
                {"id": "meta/llama-3.1-70b-instruct"},
                {"id": "deepseek-ai/deepseek-r1"},
                {"id": "nvidia/nemotron-4-340b-instruct"}
            ]
        }
        mock_get.return_value = resp

        models = ModelScanner.scan_nvidia("fake-nvapi-123")
        self.assertEqual(len(models), 3)
        self.assertEqual(models[0]["display_name"], "llama-3.1-70b-instruct")

    @patch("engine.model_scanner.get_db")
    @patch("engine.model_scanner.requests.get")
    def test_scan_ollama_mock(self, mock_get, mock_get_db):
        mock_get_db.return_value = self.db

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "models": [
                {"name": "llama3.2:latest", "size": 2147483648},
                {"name": "qwen2.5-coder:7b", "size": 4294967296}
            ]
        }
        mock_get.return_value = resp

        models = ModelScanner.scan_ollama("http://127.0.0.1:11434")
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["model_name"], "llama3.2:latest")

    def test_thinking_extraction_edge_cases(self):
        # Nested or unclosed tags
        unclosed = "<think>Analyzing the question thoroughly"
        thinking, final_text = extract_thinking(unclosed)
        self.assertEqual(thinking, "Analyzing the question thoroughly")
        self.assertEqual(final_text, "")

        # Standard clean think block
        closed = "<think>Reasoning step 1\nReasoning step 2</think>This is the final response."
        thinking, final_text = extract_thinking(closed)
        self.assertEqual(thinking, "Reasoning step 1\nReasoning step 2")
        self.assertEqual(final_text, "This is the final response.")


if __name__ == "__main__":
    unittest.main()
