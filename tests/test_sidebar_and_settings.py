"""
Tests for redesigned Sidebar layout, General Settings Dialog, and DeepSeek crash fixes.
"""
import unittest
import sys
from PySide6.QtWidgets import QApplication

from engine.router import FallbackRouter
from ui.components.message_bubble import extract_thinking, ThinkingSection
from ui.components.sidebar import Sidebar
from ui.components.general_settings_dialog import GeneralSettingsDialog
from database.db_manager import get_db

# Ensure single QApplication instance
app = QApplication.instance() or QApplication(sys.argv)


class TestSidebarAndSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router = FallbackRouter()
        cls.db = get_db()

    def test_deepseek_model_mapping_no_crash(self):
        """Test that deepseek v4 pro and other deepseek labels map safely without crash."""
        prov, model = self.router._map_model_selection("deepseek v4 pro")
        self.assertIn(prov, ["openrouter", "nvidia", "groq", "ollama_coder"])
        self.assertTrue(bool(model))

        prov2, model2 = self.router._map_model_selection("deepseek: deepseek-v4-pro")
        self.assertIn(prov2, ["openrouter", "nvidia", "groq", "ollama_coder"])
        self.assertIn("deepseek", model2.lower())

    def test_extract_thinking_none_safety(self):
        """Test extract_thinking with None and empty content does not raise TypeError."""
        t1, c1 = extract_thinking(None)
        self.assertIsNone(t1)
        self.assertEqual(c1, "")

        t2, c2 = extract_thinking("")
        self.assertIsNone(t2)
        self.assertEqual(c2, "")

        t3, c3 = extract_thinking("<think>Reasoning here</think>Output text")
        self.assertEqual(t3, "Reasoning here")
        self.assertEqual(c3, "Output text")

    def test_thinking_section_timer_cleanup(self):
        """Test ThinkingSection timer stops cleanly and does not cause segfault."""
        section = ThinkingSection("Draft thinking", is_live=True)
        self.assertTrue(section.is_live)
        self.assertIsNotNone(section._live_timer)
        self.assertTrue(section._live_timer.isActive())

        section.finish_live(2.5)
        self.assertFalse(section.is_live)
        self.assertIsNone(section._live_timer)

    def test_sidebar_layout_and_nav_items(self):
        """Test sidebar includes api_keys and settings nav buttons, and updates profile."""
        sidebar = Sidebar()
        self.assertIn("api_keys", sidebar._nav_buttons)
        self.assertIn("settings", sidebar._nav_buttons)
        self.assertIn("home", sidebar._nav_buttons)

        # Test profile pill dynamic update
        sidebar.update_profile("Alex Rivera", "alex@example.com")
        self.assertEqual(sidebar.name_lbl.text(), "Alex Rivera")
        self.assertEqual(sidebar.email_lbl.text(), "alex@example.com")
        self.assertEqual(sidebar.avatar_lbl.text(), "AR")

        sidebar.deleteLater()

    def test_general_settings_dialog_tabs(self):
        """Test GeneralSettingsDialog initializes tabs: Profile and Analyse."""
        dialog = GeneralSettingsDialog()
        self.assertEqual(dialog.tabs.count(), 2)
        self.assertIn("Profile", dialog.tabs.tabText(0))
        self.assertIn("Analyse", dialog.tabs.tabText(1))

        # Test window title clean without duplication
        self.assertEqual(dialog.windowTitle(), "Application Settings")

        dialog.deleteLater()

    def test_in_window_navigation_and_graphical_analytics(self):
        """Test MainWindow embeds SettingsView, AddModelsView, and AnalyticsView without dialogs."""
        from ui.main_window import MainWindow
        from ui.components.analytics_view import AnalyticsView, TokenBarChart, ModelDonutChart
        from ui.components.settings_view import SettingsView
        from ui.components.add_models_view import AddModelsView

        win = MainWindow()
        self.assertEqual(win.stack.count(), 8)

        # Test embedded views exist and are registered
        self.assertIsInstance(win.settings_view, SettingsView)
        self.assertIsInstance(win.add_models_view, AddModelsView)
        self.assertIsInstance(win.analytics_view, AnalyticsView)
        self.assertIs(win.stack.widget(7), win.analytics_view)

        # Test navigation to Settings stays on same window
        win._handle_navigation("settings")
        self.assertIs(win.stack.currentWidget(), win.settings_view)

        # Test back to chat
        win.settings_view.back_to_chat_requested.emit()
        self.assertIs(win.stack.currentWidget(), win.home_container)

        # Test navigation to Add AI Models stays on same window
        win._handle_navigation("api_keys")
        self.assertIs(win.stack.currentWidget(), win.add_models_view)

        win.add_models_view.back_to_chat_requested.emit()
        self.assertIs(win.stack.currentWidget(), win.home_container)

        # Test navigation to Graphical Analytics stays on same window
        win._handle_navigation("usage")
        self.assertIs(win.stack.currentWidget(), win.analytics_view)

        # Test graphical analytics components
        analytics = win.analytics_view
        self.assertIsInstance(analytics.bar_chart, TokenBarChart)
        self.assertIsInstance(analytics.donut_chart, ModelDonutChart)

        win.deleteLater()


if __name__ == "__main__":
    unittest.main()


