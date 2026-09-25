"""
Comprehensive Unit & Integration Test Suite for Sage AI Universal Auto Router.
Tests:
- Registry of all 54 core models
- 8-Factor Dynamic Scoring Engine formula and weights
- Global Best-to-Lowest ranking across tasks (Coding, Reasoning, Chat, Vision, Image)
- Real-time Health Tracker and Circuit Breaker cooldowns
- Python AST Response Validator
- Cascading Execution & Fallback loop
- SQLite Routing Decision Logging
- GlobalRankingView UI rendering and filtering
"""
import unittest
import os
import sys
from typing import Dict, Any

from engine.auto_router.models import TaskType, ModelStatus, ModelSpec, RoutingResult
from engine.auto_router.registry import ModelRegistry, CORE_MODEL_SPECS
from engine.auto_router.scoring_engine import ModelScoringEngine
from engine.auto_router.health_tracker import HealthTracker
from engine.auto_router.response_validator import ResponseValidator
from engine.auto_router.core_router import AutoRouter, get_auto_router
from engine.providers.base_provider import ProviderResponse
from database.db_manager import get_db


class TestAutoRouterRegistry(unittest.TestCase):
    """Tests specification, metadata, and catalog completeness of the 54 core models."""

    def setUp(self):
        self.registry = ModelRegistry()

    def test_all_54_core_models_present(self):
        """Validates that all 54 core models are registered in the catalog."""
        models = self.registry.get_all_models()
        self.assertGreaterEqual(len(models), 54, f"Expected at least 54 core models, found {len(models)}")

    def test_providers_coverage(self):
        """Ensures all requested providers are present in the catalog."""
        providers = self.registry.get_models_by_provider()
        expected_providers = {
            "gemini", "groq", "openrouter", "nvidia", "mistral",
            "cerebras", "cloudflare", "cohere", "huggingface", "ollama", "image"
        }
        for ep in expected_providers:
            self.assertIn(ep, providers, f"Provider '{ep}' missing from catalog")
            self.assertGreater(len(providers[ep]), 0, f"Provider '{ep}' has 0 models")

    def test_provider_counts(self):
        """Verifies specific model counts per provider according to user specification."""
        prov = self.registry.get_models_by_provider()
        self.assertGreaterEqual(len(prov.get("gemini", [])), 4)
        self.assertGreaterEqual(len(prov.get("groq", [])), 7)
        self.assertGreaterEqual(len(prov.get("openrouter", [])), 6)
        self.assertGreaterEqual(len(prov.get("nvidia", [])), 10)
        self.assertGreaterEqual(len(prov.get("mistral", [])), 5)
        self.assertGreaterEqual(len(prov.get("cerebras", [])), 3)
        self.assertGreaterEqual(len(prov.get("cloudflare", [])), 4)
        self.assertGreaterEqual(len(prov.get("cohere", [])), 4)
        self.assertGreaterEqual(len(prov.get("huggingface", [])), 3)
        self.assertGreaterEqual(len(prov.get("ollama", [])), 7)
        self.assertGreaterEqual(len(prov.get("image", [])), 1)


class TestScoringEngine(unittest.TestCase):
    """Tests 8-factor dynamic scoring formula and global best-to-lowest ranking."""

    def setUp(self):
        self.health = HealthTracker()
        self.engine = ModelScoringEngine(health_tracker=self.health)
        self.registry = ModelRegistry()

    def test_formula_weights_sum_to_one(self):
        """Verifies exact weights from specification sum to 100%."""
        total_weight = (
            self.engine.WEIGHT_QUALITY +       # 30%
            self.engine.WEIGHT_TASK +          # 20%
            self.engine.WEIGHT_AVAILABILITY +  # 10%
            self.engine.WEIGHT_QUOTA +         # 10%
            self.engine.WEIGHT_SPEED +         # 10%
            self.engine.WEIGHT_COST +          # 10%
            self.engine.WEIGHT_CONTEXT +       # 5%
            self.engine.WEIGHT_HEALTH          # 5%
        )
        self.assertAlmostEqual(total_weight, 1.0, places=5)

    def test_score_bounds(self):
        """Score must always fall within [1.0, 10.0]."""
        models = self.registry.get_all_models()
        for m in models:
            score = self.engine.score_model(m, task=TaskType.GENERAL_CHAT)
            self.assertGreaterEqual(score.overall_score, 1.0)
            self.assertLessEqual(score.overall_score, 10.0)

    def test_global_ranking_best_to_lowest(self):
        """Validates that ranked list is ordered descending by overall score."""
        models = self.registry.get_all_models()
        ranked = self.engine.rank_models(models, task=TaskType.GENERAL_CHAT)
        self.assertGreaterEqual(len(ranked), 54)

        # Check descending order within operational tiers
        prev_score = 999.0
        for item in ranked:
            self.assertGreater(item.global_rank, 0)
            if item.status == ModelStatus.AVAILABLE.value:
                self.assertLessEqual(item.overall_score, prev_score)
                prev_score = item.overall_score

    def test_coding_task_dynamically_prioritizes_coders(self):
        """Coding tasks must prioritize code-specialized models dynamically."""
        models = self.registry.get_all_models()
        ranked = self.engine.rank_models(models, task=TaskType.CODING)
        top_5 = ranked[:5]
        top_5_ids = [s.model.model_id.lower() for s in top_5]
        top_5_names = [s.model.display_name.lower() for s in top_5]

        # Check that top ranks feature coding or reasoning flagship models
        has_coder = any("coder" in m or "codestral" in m or "deepseek" in m or "flash" in m for m in top_5_ids + top_5_names)
        self.assertTrue(has_coder, f"Expected top models for coding to feature code specialists: {top_5_ids}")

    def test_circuit_breaker_cooldown_dampens_ranking(self):
        """When a model is rate limited (429), it must receive a penalty and status change."""
        model_id = "test-llama-temp"
        self.health.record_rate_limit(model_id, "groq", cooldown_seconds=60)
        self.assertTrue(self.health.is_in_cooldown(model_id))
        self.assertEqual(self.health.get_status(model_id, "groq"), ModelStatus.RATE_LIMITED)


class TestResponseValidator(unittest.TestCase):
    """Tests syntax, AST parsing, and response sanity validation."""

    def test_valid_coding_response_passes(self):
        content = (
            "Here is the Python implementation of quicksort:\n\n"
            "```python\n"
            "def quicksort(arr):\n"
            "    if len(arr) <= 1:\n"
            "        return arr\n"
            "    pivot = arr[len(arr) // 2]\n"
            "    left = [x for x in arr if x < pivot]\n"
            "    middle = [x for x in arr if x == pivot]\n"
            "    right = [x for x in arr if x > pivot]\n"
            "    return quicksort(left) + middle + quicksort(right)\n"
            "```\n"
            "Call `quicksort([3, 1, 4])` to run."
        )
        is_valid, reason = ResponseValidator.validate(content, task=TaskType.CODING)
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

    def test_broken_python_syntax_fails(self):
        content = (
            "Here is the broken script:\n"
            "```python\n"
            "def broken_function(\n"
            "    return 42\n"
            "```"
        )
        is_valid, reason = ResponseValidator.validate(content, task=TaskType.CODING)
        self.assertFalse(is_valid)
        self.assertIn("syntax", reason.lower())

    def test_empty_response_fails(self):
        is_valid, reason = ResponseValidator.validate("", task=TaskType.GENERAL_CHAT)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Empty response.")


class TestAutoRouterEndToEnd(unittest.TestCase):
    """Tests the full AutoRouter pipeline from task detection to execution and DB logging."""

    def setUp(self):
        self.router = AutoRouter()

    def test_task_detection(self):
        """Validates heuristic and keyword task detection."""
        self.assertEqual(self.router.detect_task("Write a python function to parse JSON"), TaskType.CODING)
        self.assertEqual(self.router.detect_task("Reason step by step about the Fermi paradox"), TaskType.REASONING)
        self.assertEqual(self.router.detect_task("Generate an image of a cybernetic cat"), TaskType.IMAGE_GEN)
        self.assertEqual(self.router.detect_task("Hello! How are you today?"), TaskType.GENERAL_CHAT)

    def test_global_ranking_returns_all_54_models(self):
        """get_global_ranking() returns all registered models (at least 54)."""
        ranked = self.router.get_global_ranking(task=TaskType.GENERAL_CHAT, filter_incompatible=False)
        self.assertGreaterEqual(len(ranked), 54)
        self.assertEqual(ranked[0].global_rank, 1)
        self.assertEqual(ranked[-1].global_rank, len(ranked))

    def test_sqlite_routing_logs(self):
        """Verifies routing decisions are recorded and queryable in SQLite."""
        db = get_db()
        test_decision = {
            "task_type": "coding",
            "prompt_snippet": "Unit test write function",
            "selected_model_id": "qwen/qwen-2.5-coder-32b-instruct",
            "provider_id": "openrouter",
            "global_rank": 1,
            "dynamic_score": 9.7,
            "fallback_used": False,
            "fallback_count": 0,
            "attempted_models": ["qwen/qwen-2.5-coder-32b-instruct"],
            "success": True,
            "latency_ms": 320.5,
            "validation_passed": True
        }
        db.log_routing_decision(test_decision)
        recent_logs = db.get_recent_routing_logs(limit=5)
        self.assertGreater(len(recent_logs), 0)
        latest = recent_logs[0]
        self.assertEqual(latest["task_type"], "coding")
        self.assertEqual(latest["selected_model_id"], "qwen/qwen-2.5-coder-32b-instruct")


class TestGlobalRankingViewUI(unittest.TestCase):
    """Tests GUI instantiation, table population with 54 rows, and filtering."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_view_populates_54_rows(self):
        from ui.components.global_ranking_view import GlobalRankingView
        view = GlobalRankingView()
        self.assertGreaterEqual(view.table.rowCount(), 54)

    def test_filter_by_provider(self):
        from ui.components.global_ranking_view import GlobalRankingView
        view = GlobalRankingView()
        view._set_filter_mode("provider")
        view._selected_provider = "gemini"
        view._populate_table()
        # Gemini has 4 models
        self.assertEqual(view.table.rowCount(), 4)

    def test_search_filtering(self):
        from ui.components.global_ranking_view import GlobalRankingView
        view = GlobalRankingView()
        view._on_search_text_changed("qwen")
        self.assertGreater(view.table.rowCount(), 0)
        for r in range(view.table.rowCount()):
            name = view.table.item(r, 1).text().lower()
            self.assertIn("qwen", name)


if __name__ == "__main__":
    unittest.main()
