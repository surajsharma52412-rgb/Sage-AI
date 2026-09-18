import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.sidebar import Sidebar
from ui.components.analytics_view import AnalyticsView
from ui.components.project_view import ProjectAgentView
from engine.router import FallbackRouter
from engine.automation_agent import GmailAutomationService


class TestAutomationsAndProjectFixes(unittest.TestCase):
    def test_sidebar_does_not_contain_explore_or_assistants(self):
        """Verify 'explore' and 'assistants' have been completely removed from sidebar."""
        sidebar = Sidebar()
        item_keys = list(sidebar._nav_buttons.keys())
        self.assertNotIn("explore", item_keys)
        self.assertNotIn("assistants", item_keys)
        sidebar.deleteLater()

    def test_provider_cards_height_and_no_clipping(self):
        """Verify provider health cards in AnalyticsView have minimum height >= 120 and ample vertical space."""
        analytics = AnalyticsView()
        self.assertTrue(len(analytics.provider_widgets) >= 4)
        for p_id, w_dict in analytics.provider_widgets.items():
            box = w_dict["box"]
            self.assertGreaterEqual(box.minimumHeight(), 120)
            # Verify style does not have restrictive inner padding
            qss = box.styleSheet().lower()
            self.assertNotIn("padding: 4px", qss)
        analytics.deleteLater()

    def test_map_model_selection_dropdown_labels(self):
        """Verify _map_model_selection maps UI dropdown strings accurately without bogus models."""
        router = FallbackRouter()
        
        # 1. Groq (Fastest) -> must map to groq and not to 'Fastest'
        p_key, model = router._map_model_selection("Groq — LLaMA 3.3 70B (Fastest)")
        self.assertEqual(p_key, "groq")
        self.assertNotEqual(model, "Fastest")
        self.assertEqual(model, "llama-3.3-70b-versatile")

        # 2. NVIDIA NIM -> must map to nvidia and not to None or broken model
        p_key, model = router._map_model_selection("NVIDIA NIM — LLaMA 3.1 70B")
        self.assertEqual(p_key, "nvidia")
        self.assertEqual(model, "meta/llama-3.1-70b-instruct")

        # 3. Local Ollama (Offline Coder) -> must map to ollama_coder and not to 'Offline Coder'
        p_key, model = router._map_model_selection("Local Ollama (Offline Coder)")
        self.assertEqual(p_key, "ollama_coder")
        self.assertNotEqual(model, "Offline Coder")
        self.assertEqual(model, "qwen3:8b")

    def test_router_route_alias_exists(self):
        """Verify FallbackRouter has .route() alias for backwards compatibility."""
        router = FallbackRouter()
        self.assertTrue(hasattr(router, "route"))
        self.assertTrue(callable(router.route))

    def test_gmail_service_draft_reply_no_attribute_error(self):
        """Verify draft_reply executes without raising AttributeError on router.route."""
        service = GmailAutomationService()
        email_sample = {
            "sender": "partner@test.com",
            "sender_name": "Alex",
            "subject": "Status check",
            "body": "Hi, how is the project going?"
        }
        # Calling draft_reply should not raise AttributeError
        draft = service.draft_reply(email_sample)
        self.assertIsInstance(draft, str)
        self.assertTrue(len(draft) > 10)

    def test_project_view_stop_button(self):
        """Verify ProjectAgentView has a functional stop button."""
        pv = ProjectAgentView()
        self.assertTrue(hasattr(pv, "stop_btn"))
        self.assertEqual(pv.stop_btn.text(), "⏹ Stop Task")
        self.assertFalse(pv.stop_btn.isEnabled())
        pv.deleteLater()


if __name__ == "__main__":
    unittest.main()
