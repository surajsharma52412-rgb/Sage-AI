"""
Comprehensive Unit Tests for Sage AI Zero-Cost Guard Architecture.
Verifies that:
1. Every model request is checked against the 0 Rs rule.
2. Paid models (> 0 Rs) are intercepted and BLOCKED from execution.
3. Requests are shifted/diverted to 100% Free models (0 Rs).
4. Free waterfall cascade continues shifting through 0 Rs models until successful.
5. AutoRouter, AutoCodingRouter, and FallbackRouter enforce Zero-Cost Guard.
6. Database audit logs record intercepted shifts and cost saved in Rs.
"""

import os
import unittest
from pathlib import Path

from engine.zero_cost_guard import (
    ZeroCostGuard,
    get_zero_cost_guard,
    DEFAULT_USD_TO_INR_RATE,
    MAX_ALLOWED_MODEL_COST_RS,
)
from engine.router import FallbackRouter
from engine.auto_router.coding_router import AutoCodingRouter
from engine.auto_router.core_router import AutoRouter
from database.db_manager import DatabaseManager, get_db


class TestZeroCostGuardArchitecture(unittest.TestCase):
    """Validates the Zero-Cost Guard and automatic free-model shifting."""

    def setUp(self):
        self.guard = get_zero_cost_guard()
        self.db = get_db()

    def test_singleton_guard_instance(self):
        """Ensures ZeroCostGuard is a global singleton."""
        g1 = get_zero_cost_guard()
        g2 = get_zero_cost_guard()
        self.assertIs(g1, g2)
        self.assertTrue(g1.is_enabled)

    def test_free_models_evaluated_as_zero_cost(self):
        """Verifies free tier and offline models evaluate strictly as <= 0 Rs."""
        free_models = [
            ("gemini-1.5-flash", "gemini"),
            ("gemini-2.0-flash", "gemini"),
            ("llama-3.3-70b-versatile", "groq"),
            ("deepseek-r1-distill-llama-70b", "groq"),
            ("qwen/qwen-2.5-coder-32b-instruct:free", "openrouter"),
            ("deepseek/deepseek-r1:free", "openrouter"),
            ("deepseek/deepseek-v4-flash-0731:free", "openrouter"),
            ("deepseek/deepseek-chat:free", "openrouter"),
            ("meta-llama/llama-3.3-70b-instruct:free", "openrouter"),
            ("llama-3.3-70b", "cerebras"),
            ("@cf/meta/llama-3.3-70b-instruct", "cloudflare"),
            ("qwen3:8b", "ollama"),
            ("qwen2.5-coder:7b", "ollama"),
            ("sage-offline-facts", "local_facts"),
        ]

        for m_name, prov in free_models:
            res = self.guard.evaluate_model_cost(m_name, prov)
            self.assertTrue(
                res.is_zero_cost,
                f"Model '{m_name}' on '{prov}' was expected to be 0 Rs free, got {res.cost_in_rs} Rs"
            )
            self.assertEqual(res.cost_in_rs, 0.0)

    def test_paid_models_evaluated_as_above_zero_rs(self):
        """Verifies paid frontier models evaluate strictly as > 0 Rs."""
        paid_models = [
            ("unbiased/pareto", "openrouter"),
            ("Pareto 26.9 (Union Alpha)", "openrouter"),
            ("openrouter/pareto-code", "openrouter"),
            ("anthropic/claude-3.5-sonnet", "openrouter"),
            ("openai/gpt-4o", "openrouter"),
            ("deepseek/deepseek-r1", "openrouter"),                    # Paid version without :free
            ("qwen/qwen-2.5-coder-32b-instruct", "openrouter"),       # Paid version without :free
            ("meta-llama/llama-3.3-70b-instruct", "openrouter"),      # Paid version without :free
        ]

        for m_name, prov in paid_models:
            res = self.guard.evaluate_model_cost(m_name, prov)
            self.assertFalse(
                res.is_zero_cost,
                f"Model '{m_name}' was expected to cost > 0 Rs, but was marked zero cost!"
            )
            self.assertGreater(
                res.cost_in_rs,
                0.0,
                f"Model '{m_name}' cost in Rs must be > 0.0, got {res.cost_in_rs}"
            )
            self.assertIn("Paid", res.tier_type)

    def test_guard_request_blocks_paid_and_shifts_to_free(self):
        """
        Tests that when a paid model (> 0 Rs) is requested:
        1. It does NOT continue with the paid model.
        2. It shifts automatically to a 100% Free model (0 Rs).
        3. Stage notification is triggered.
        4. Interception event is recorded in the database.
        """
        notifications = []
        def on_stage(msg):
            notifications.append(msg)

        was_shifted, eff_model, eff_prov, meta = self.guard.guard_request(
            requested_model="Pareto 26.9 (Union Alpha)",
            provider_id="openrouter",
            task_type="coding",
            on_stage_change=on_stage
        )

        self.assertTrue(was_shifted, "Paid model should have been shifted!")
        self.assertNotEqual(eff_model, "Pareto 26.9 (Union Alpha)")
        # Must shift to a verified 0 Rs free model
        self.assertTrue(self.guard.is_zero_cost(eff_model, eff_prov))
        self.assertEqual(meta["cost_in_rs"], 0.0)
        self.assertGreater(meta["intercepted_cost_rs"], 0.0)

        # Verify notification was sent
        self.assertTrue(any("Zero-Cost Guard" in n for n in notifications))
        self.assertTrue(any("Pareto" in n for n in notifications))

        # Verify database record
        shifts = self.db.get_zero_cost_shifts(limit=5)
        self.assertGreater(len(shifts), 0)
        latest = shifts[0]
        self.assertIn("pareto", latest["original_model"].lower())
        self.assertGreater(latest["cost_saved_rs"], 0.0)

    def test_guard_request_allows_free_model_directly(self):
        """Verifies that an already 0 Rs free model passes through without shifting."""
        was_shifted, eff_model, eff_prov, meta = self.guard.guard_request(
            requested_model="gemini-2.0-flash",
            provider_id="gemini",
            task_type="coding"
        )
        self.assertFalse(was_shifted)
        self.assertEqual(eff_model, "gemini-2.0-flash")
        self.assertEqual(eff_prov, "gemini")
        self.assertEqual(meta["cost_in_rs"], 0.0)

    def test_free_waterfall_queue_contains_only_zero_cost_models(self):
        """Ensures all fallback chains only contain verified 0 Rs free models."""
        for task in ("coding", "reasoning", "general_chat", "vision", "image_gen"):
            queue = self.guard.get_free_waterfall_queue(task_type=task)
            self.assertGreater(len(queue), 0)
            for m_id, p_id, desc in queue:
                eval_res = self.guard.evaluate_model_cost(m_id, p_id)
                self.assertTrue(
                    eval_res.is_zero_cost,
                    f"Model {m_id} in {task} free queue is not 0 Rs! Cost: {eval_res.cost_in_rs}"
                )

    def test_coding_router_shifts_paid_model_to_free(self):
        """Verifies AutoCodingRouter intercepts Pareto 26.9 and shifts to 0 Rs free coding model."""
        router = AutoCodingRouter()
        res = router.select_model_for_execution(
            selected_model="Pareto 26.9 (Union Alpha)",
            prompt="Write a Python script to sort items",
            allow_fallback=True,
            enforce_zero_cost=True
        )

        self.assertEqual(res["mode"], "manual_shifted_free")
        self.assertTrue(res["shifted_from_paid"])
        self.assertIn("Pareto", res["reason"])
        # Selected model must be 0 Rs free
        self.assertTrue(self.guard.is_zero_cost(res["selected_model"], res["provider_id"]))

        # Fallback queue must contain only 0 Rs free models
        for fb_model in res["fallback_queue"]:
            self.assertTrue(
                self.guard.is_zero_cost(fb_model),
                f"Fallback model '{fb_model}' must be 0 Rs free"
            )

    def test_fallback_router_zero_cost_enforcement(self):
        """Verifies FallbackRouter intercepts paid model selection and executes via free model."""
        router = FallbackRouter()
        stages = []
        def on_stage(s):
            stages.append(s)

        # Request paid model Pareto 26.9
        resp = router.route_and_execute(
            prompt="Hello from zero cost test",
            selected_model="Pareto 26.9 (Union Alpha)",
            on_stage_change=on_stage
        )

        self.assertTrue(resp.success)
        # Verify stage notifications reflect Zero-Cost Guard interception
        self.assertTrue(
            any("Zero-Cost Guard" in s for s in stages),
            f"Zero-Cost Guard notification missing from stages: {stages}"
        )
        # Verify the executed model was NOT Pareto 26.9
        self.assertNotIn("pareto", resp.model_name.lower())

    def test_zero_cost_database_stats(self):
        """Verifies statistics calculation for total cost saved in Rs."""
        stats = self.db.get_zero_cost_stats()
        self.assertIn("total_intercepted", stats)
        self.assertIn("total_saved_rs", stats)
        self.assertGreaterEqual(stats["total_intercepted"], 1)
        self.assertGreater(stats["total_saved_rs"], 0.0)


if __name__ == "__main__":
    unittest.main()
