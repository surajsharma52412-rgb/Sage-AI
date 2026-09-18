"""
Unit tests verifying that model availability is explicitly shown everywhere across Sage AI:
- In the Coding IDE Agent model dropdown and status badge
- In Project Agent Studio model dropdown and status badge
- In Automations view model dropdown and status badge
- In ModelScanner curated models and provider checks
- In FallbackRouter model label parsing
"""
import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication
import sys

# Ensure single QApplication instance
app = QApplication.instance() or QApplication(sys.argv)

from engine.model_scanner import ModelScanner
from engine.router import FallbackRouter
from ui.components.coding_ide_view import CodingIdeView
from ui.components.project_view import ProjectAgentView
from ui.components.automations_view import AutomationsView


class TestModelAvailabilityEverywhere(unittest.TestCase):
    """Verifies that model availability ([● Available] / [○ Unavailable]) is displayed everywhere."""

    def test_model_scanner_curated_models(self):
        """Checks that all curated models have explicit availability tags."""
        for cat in ("coding", "automation", "project"):
            models = ModelScanner.get_curated_models(cat)
            self.assertGreater(len(models), 0)
            for m in models:
                self.assertIn("clean_id", m)
                self.assertIn("display_label", m)
                self.assertIn("is_available", m)
                self.assertIsInstance(m["is_available"], bool)
                label = m["display_label"]
                self.assertTrue(
                    label.startswith("[● Available]") or label.startswith("[○ Unavailable]"),
                    f"Label '{label}' does not start with an availability tag"
                )

    def test_coding_ide_shows_availability(self):
        """Verifies CodingIdeView model dropdown and status badge show availability."""
        ide = CodingIdeView()
        self.assertTrue(hasattr(ide, "agent_model_combo"))
        self.assertTrue(hasattr(ide, "agent_model_status_badge"))
        self.assertGreater(ide.agent_model_combo.count(), 0)

        # Every model in the dropdown must state whether it is available or not
        for i in range(ide.agent_model_combo.count()):
            text = ide.agent_model_combo.itemText(i)
            self.assertTrue(
                "[● Available]" in text or "[○ Unavailable]" in text,
                f"Coding IDE item '{text}' does not show availability!"
            )

        badge_text = ide.agent_model_status_badge.text()
        self.assertTrue("Available" in badge_text or "Unavailable" in badge_text)

    def test_project_view_shows_availability(self):
        """Verifies ProjectAgentView model dropdown and status badge show availability."""
        pv = ProjectAgentView()
        self.assertTrue(hasattr(pv, "model_combo"))
        self.assertTrue(hasattr(pv, "model_status_chip"))
        self.assertGreater(pv.model_combo.count(), 0)

        # Every model in the dropdown must state whether it is available or not
        for i in range(pv.model_combo.count()):
            text = pv.model_combo.itemText(i)
            self.assertTrue(
                "[● Available]" in text or "[○ Unavailable]" in text,
                f"Project Studio item '{text}' does not show availability!"
            )

        chip_text = pv.model_status_chip.text()
        self.assertTrue("Available" in chip_text or "Unavailable" in chip_text)

    def test_automations_view_shows_availability(self):
        """Verifies AutomationsView model dropdown and status badge show availability."""
        av = AutomationsView()
        self.assertTrue(hasattr(av, "model_combo"))
        self.assertTrue(hasattr(av, "model_status_badge"))
        self.assertGreater(av.model_combo.count(), 0)

        # Every model in the dropdown must state whether it is available or not
        for i in range(av.model_combo.count()):
            text = av.model_combo.itemText(i)
            self.assertTrue(
                "[● Available]" in text or "[○ Unavailable]" in text,
                f"Automations view item '{text}' does not show availability!"
            )

        badge_text = av.model_status_badge.text()
        self.assertTrue("Available" in badge_text or "Unavailable" in badge_text)

    def test_automations_draft_reply_uses_selected_model(self):
        """Verifies that AutomationsView wires selected model into draft_reply."""
        av = AutomationsView()
        test_email = {
            "id": "test_msg_99",
            "sender": "boss@company.com",
            "sender_name": "The Boss",
            "subject": "Status Report",
            "body": "Need the update ASAP."
        }

        # Select a specific model in combo
        av.model_combo.setCurrentIndex(0)
        chosen_clean = av.model_combo.currentData() or "Auto Router"

        with patch.object(av.manager.gmail_service, "draft_reply", return_value="Drafted response") as mock_draft:
            with patch("ui.components.automations_view.PermissionDialog") as MockDlg:
                with patch("ui.components.automations_view.QMessageBox"):
                    mock_dlg_inst = MagicMock()
                    mock_dlg_inst.approved = False
                    MockDlg.return_value = mock_dlg_inst

                    av._handle_email_reply_request(test_email)

                    mock_draft.assert_called_once()
                    call_args, call_kwargs = mock_draft.call_args
                    self.assertEqual(call_args[0], test_email)
                    self.assertEqual(call_kwargs.get("model"), chosen_clean)

    def test_router_strips_availability_tags(self):
        """Checks that FallbackRouter gracefully strips [● Available] tags during mapping."""
        router = FallbackRouter()
        
        # Test with tagged labels
        prov, model = router._map_model_selection("[● Available] ⚡ Auto Router (Best Free Coding Waterfall)")
        self.assertIn(prov, ("groq", "nvidia", "cerebras", "mistral", "openrouter", "gemini", "ollama_chat"))
        
        prov, model = router._map_model_selection("[● Available] 🚀 Mistral Codestral 2501")
        self.assertEqual(prov, "mistral")
        
        prov, model = router._map_model_selection("[○ Unavailable] ✨ Google Gemini 2.0 Flash")
        self.assertEqual(prov, "gemini")


if __name__ == "__main__":
    unittest.main()
