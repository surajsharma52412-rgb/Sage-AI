"""
Unit tests for Multi-Provider Architecture Expansion and Bar Chart Label Formatting.
Tests:
- TokenBarChart label formatting & non-overlapping slot bounds
- Initialization and availability checks for Cloudflare, Mistral, Cerebras, Cohere, Hugging Face
- FallbackRouter model selection mapping for new providers
- 10-provider health catalog in AnalyticsView
- ModelScanner discovery methods
"""
import unittest
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtCore import Qt

from ui.components.analytics_view import TokenBarChart, AnalyticsView
from engine.providers.mistral_provider import MistralProvider
from engine.providers.cerebras_provider import CerebrasProvider
from engine.providers.cohere_provider import CohereProvider
from engine.providers.huggingface_provider import HuggingFaceProvider
from engine.providers.cloudflare_provider import CloudflareWorkersAiProvider
from engine.router import FallbackRouter
from engine.model_scanner import ModelScanner
from database.db_manager import get_db


class TestMultiProviderExpansion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_token_bar_chart_label_formatting(self):
        """Verify long verbose model identifiers format to clean, non-colliding labels."""
        cases = [
            ("meta/llama-3.2-11b-vision-instruct", "Llama 3.2"),
            ("llama-3.3-70b-versatile", "Llama 70B"),
            ("Sage Local Fallback", "Fallback"),
            ("Sage Orchestrator (Multi-Agent)", "Orchestrator"),
            ("deepseek-ai/deepseek-r1", "DeepSeek R1"),
            ("Local Knowledge Base", "Local KB"),
            ("codestral-latest", "Codestral"),
            ("mistral-large-latest", "Mistral Lrg"),
            ("command-r-plus-08-2024", "Command R+"),
            ("@cf/meta/llama-3.3-70b-instruct", "Llama 70B"),
            ("Qwen/Qwen2.5-Coder-32B-Instruct", "Qwen Coder"),
        ]
        for raw, expected in cases:
            formatted = TokenBarChart._format_model_label(raw)
            self.assertEqual(formatted, expected, f"Failed formatting for {raw}")

    def test_token_bar_chart_slot_width_elision(self):
        """Verify that elidedText strictly constrains string width within slot bounds."""
        font = QFont("Segoe UI", 8, QFont.Bold)
        fm = QFontMetrics(font)
        slot_w = 48.0
        max_allowed_w = int(slot_w - 6)

        test_labels = [
            "Fallback",
            "Orchestrator",
            "DeepSeek R1",
            "Llama 70B",
            "Local KB",
            "VeryLongUnabbreviatedModelName"
        ]

        for lbl in test_labels:
            elided = fm.elidedText(lbl, Qt.TextElideMode.ElideMiddle, max_allowed_w)
            rendered_w = fm.horizontalAdvance(elided)
            self.assertLessEqual(
                rendered_w,
                max_allowed_w,
                f"Label '{elided}' width {rendered_w}px exceeded max slot width {max_allowed_w}px"
            )

    def test_new_providers_initialization_and_availability(self):
        """Verify all 5 new providers initialize and correctly report availability."""
        providers = [
            MistralProvider(),
            CerebrasProvider(),
            CohereProvider(),
            HuggingFaceProvider(),
            CloudflareWorkersAiProvider()
        ]

        for p in providers:
            self.assertIsNotNone(p.provider_id)
            self.assertIsNotNone(p.name)
            # When no key is provided, generate should safely return error without crashing
            p._get_api_key = lambda: None
            resp = p.generate("Hello world")
            self.assertFalse(resp.success)
            self.assertTrue(any(w in resp.error_msg.lower() for w in ("not configured", "failed", "403", "error", "unauthorized", "refused")))

    def test_router_model_mapping_for_all_providers(self):
        """Verify FallbackRouter cleanly maps dropdown labels to correct provider keys and models."""
        router = FallbackRouter()

        cases = [
            ("Cerebras — LLaMA 3.3 70B (Wafer-Scale)", "cerebras", "llama-3.3-70b"),
            ("Mistral AI — Codestral (Coding Specialist)", "mistral", "codestral-latest"),
            ("Cloudflare Workers AI — LLaMA 3.3 (Edge)", "cloudflare", "@cf/meta/llama-3.3-70b-instruct"),
            ("Hugging Face — Qwen 2.5 Coder 32B", "huggingface", "Qwen/Qwen2.5-Coder-32B-Instruct"),
            ("Cohere — Command R+ (Enterprise)", "cohere", "command-r-plus-08-2024"),
            ("Groq (Fastest)", "groq", "llama-3.3-70b-versatile"),
            ("NVIDIA NIM (Ultra-Dense)", "nvidia", "meta/llama-3.2-11b-vision-instruct"),
        ]

        for label, expected_prov, expected_model in cases:
            prov_key, model_name = router._map_model_selection(label)
            self.assertEqual(prov_key, expected_prov, f"Wrong provider for {label}")
            self.assertEqual(model_name, expected_model, f"Wrong model for {label}")

    def test_analytics_10_providers_health(self):
        """Verify AnalyticsView inspects and displays all 10 multi-provider architecture engines."""
        view = AnalyticsView()
        health = view._get_provider_health()
        self.assertEqual(len(health), 10, "Expected exactly 10 architecture providers in health checks")

        expected_ids = {
            "groq", "cerebras", "nvidia", "cloudflare", "mistral",
            "huggingface", "cohere", "gemini", "openrouter", "ollama"
        }
        actual_ids = {p["id"] for p in health}
        self.assertEqual(actual_ids, expected_ids)

    def test_model_scanner_includes_all_providers(self):
        """Verify ModelScanner.scan_all_configured runs without crashing and covers new providers."""
        results = ModelScanner.scan_all_configured()
        for p_id in ("mistral", "cerebras", "cohere", "huggingface", "cloudflare"):
            self.assertIn(p_id, results)


if __name__ == "__main__":
    unittest.main()
