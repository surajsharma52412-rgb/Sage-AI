"""
Unit Tests for 'Free Tier' Explicit Tagging and Live Limit Reset Time Displays.
Validates:
1. ModelScanner dynamic UTC reset time calculation across daily, monthly, and offline engines.
2. SQLite provider_quotas schema migration and persistence of tier_type and reset_time.
3. CodingIdeView dropdown items explicit 'Free Tier' and 'Resets 00:00 UTC' text.
4. ModelSelectorPopup items and headers explicit 'Free Tier' badges and countdowns.
5. AnalyticsView and UsageDialog tier metadata and limit reset countdown widgets.
"""
import unittest
import os
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure single QApplication instance for Qt widgets
app = QApplication.instance()
if not app:
    app = QApplication([])

from database.db_manager import DatabaseManager, get_db
from engine.model_scanner import ModelScanner
from ui.components.coding_ide_view import CodingIdeView
from ui.components.model_selector_popup import ModelSelectorPopup, ModelItemWidget
from ui.components.analytics_view import AnalyticsView
from ui.components.usage_dialog import QuotaCard, UsageDialog


class TestFreeTierAndResetTime(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sage.db"
        self.db = DatabaseManager(self.db_path)
        self.db.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_model_scanner_reset_info_calculation(self):
        """Verify dynamic countdown calculation for daily, monthly, and local engines."""
        # Daily providers (00:00 UTC)
        for prov in ["gemini", "groq", "cerebras", "cloudflare", "openrouter"]:
            info = ModelScanner.get_provider_reset_info(prov)
            self.assertEqual(info["tier_type"], "Free Tier")
            self.assertTrue(info["is_free_tier"])
            self.assertIn("00:00 UTC", info["reset_schedule"])
            self.assertTrue(info["reset_time"].startswith("in "))
            self.assertIn("(00:00 UTC)", info["reset_time"])

        # Cohere monthly reset
        cohere_info = ModelScanner.get_provider_reset_info("cohere")
        self.assertEqual(cohere_info["tier_type"], "Free Tier")
        self.assertIn("1st of", cohere_info["reset_time"])

        # Ollama local offline
        ollama_info = ModelScanner.get_provider_reset_info("ollama")
        self.assertEqual(ollama_info["tier_type"], "100% Free Offline")
        self.assertIn("Unlimited Local", ollama_info["reset_time"])

    def test_db_provider_quotas_tier_and_reset_time_persistence(self):
        """Verify saving and retrieving tier_type and reset_time from SQLite."""
        self.db.save_provider_quota("gemini", {
            "total_limit": 1500.0,
            "used_amount": 10.0,
            "remaining_amount": 1490.0,
            "currency_or_unit": "Requests/Day",
            "is_free_tier": True,
            "tier_type": "Free Tier",
            "reset_time": "in 7h 45m (00:00 UTC)"
        })

        q = self.db.get_provider_quota("gemini")
        self.assertIsNotNone(q)
        self.assertEqual(q["tier_type"], "Free Tier")
        self.assertEqual(q["reset_time"], "in 7h 45m (00:00 UTC)")

        all_q = self.db.get_all_provider_quotas()
        self.assertIn("gemini", all_q)
        self.assertEqual(all_q["gemini"]["tier_type"], "Free Tier")
        self.assertEqual(all_q["gemini"]["reset_time"], "in 7h 45m (00:00 UTC)")

    def test_coding_ide_dropdown_shows_free_tier_and_reset_time(self):
        """Verify CodingIdeView agent_model_combo explicitly writes Free Tier and reset time."""
        ide = CodingIdeView()
        self.assertGreater(ide.agent_model_combo.count(), 0)

        found_free_tier = False
        found_reset_time = False

        for i in range(ide.agent_model_combo.count()):
            text = ide.agent_model_combo.itemText(i)
            # Must preserve availability tags for all existing test suites
            self.assertTrue("[● Available]" in text or "[○ Unavailable]" in text)

            if "Free Tier" in text:
                found_free_tier = True
            if "Resets" in text and "00:00 UTC" in text:
                found_reset_time = True

        self.assertTrue(found_free_tier, "Expected 'Free Tier' written in coding agent model selector items")
        self.assertTrue(found_reset_time, "Expected limit reset time written in coding agent model selector items")

    def test_model_selector_popup_shows_free_tier_badge_and_reset(self):
        """Verify ModelSelectorPopup shows '🟢 Free Tier' and limit reset countdown."""
        item = ModelItemWidget(
            model_name="gemini: gemini-2.0-flash",
            display_name="Google Gemini 2.0 Flash",
            provider_name="Google Gemini",
            tokens_used=1200,
            is_free=True,
            is_available=True,
            tier_type="Free Tier",
            reset_time="in 6h 30m (00:00 UTC)"
        )

        labels = [w.text() for w in item.findChildren(object) if hasattr(w, "text")]
        combined_text = " ".join(labels)
        self.assertIn("Free Tier", combined_text)
        self.assertIn("Resets in 6h 30m (00:00 UTC)", combined_text)

        # Popup banner test
        popup = ModelSelectorPopup(parent=None)
        banner = popup._create_quota_banner({
            "gemini": {"remaining_amount": 1500, "is_free_tier": 1}
        })
        b_labels = [w.text() for w in banner.findChildren(object) if hasattr(w, "text")]
        b_text = " ".join(b_labels)
        self.assertIn("Free Tier Limits Reset", b_text)
        self.assertIn("00:00 UTC", b_text)

    def test_analytics_view_provider_summary_contains_reset_time(self):
        """Verify AnalyticsView _get_provider_quotas_summary provides tier and reset_time."""
        view = AnalyticsView()
        summary = view._get_provider_quotas_summary()
        self.assertGreater(len(summary), 0)

        gemini_q = next((q for q in summary if q["id"] == "gemini"), None)
        self.assertIsNotNone(gemini_q)
        self.assertEqual(gemini_q["tier_type"], "Free Tier")
        self.assertIn("00:00 UTC", gemini_q["reset_time"])
        self.assertIn("Free Tier", gemini_q["detail"])

    def test_usage_dialog_quota_card_and_table(self):
        """Verify UsageDialog QuotaCard displays Free Tier and Limits Reset."""
        card = QuotaCard("gemini", "Google Gemini", {
            "remaining_amount": 1500,
            "currency_or_unit": "Requests/Day",
            "is_free_tier": True,
            "tier_type": "Free Tier",
            "reset_time": "in 8h 00m (00:00 UTC)"
        })
        labels = [w.text() for w in card.findChildren(object) if hasattr(w, "text")]
        c_text = " ".join(labels)
        self.assertIn("Free Tier", c_text)
        self.assertIn("Limits Reset: in 8h 00m (00:00 UTC)", c_text)


if __name__ == "__main__":
    unittest.main()
