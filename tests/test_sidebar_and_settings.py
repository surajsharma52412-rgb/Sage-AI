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

    def test_project_agent_view_features(self):
        """Test ProjectAgentView starts with no folder selected until user chooses one."""
        from ui.components.project_view import ProjectAgentView
        pv = ProjectAgentView()
        self.assertIsNone(pv.workspace_path)
        self.assertIn("None Selected", pv.path_lbl.text())
        self.assertIn("Select Folder", pv.change_folder_btn.text())

        # Test explicit folder selection
        from pathlib import Path
        pv.set_workspace(Path.cwd())
        self.assertIsNotNone(pv.workspace_path)
        self.assertTrue(pv.workspace_path.is_dir())
        self.assertIn("New folder", pv.path_lbl.text())
        self.assertEqual(pv.change_folder_btn.text(), "📁 Change Folder")

        # Test model selector options
        self.assertGreaterEqual(pv.model_combo.count(), 4)
        self.assertIn("Auto Router", pv.model_combo.itemText(0))

        # Test quick starter prompt setting
        pv._set_task_prompt("Write unit tests for database module")
        self.assertEqual(pv.task_input.toPlainText(), "Write unit tests for database module")

        # Test step tracker labels
        self.assertEqual(len(pv.step_labels), 4)

        # Test signal existence
        signal_received = []
        pv.manage_models_requested.connect(lambda: signal_received.append(True))
        pv.diag_connect_btn.click()
        self.assertTrue(signal_received)

        pv.deleteLater()

    def test_in_window_navigation_and_graphical_analytics(self):
        """Test MainWindow embeds SettingsView, AddModelsView, and AnalyticsView without dialogs."""
        from ui.main_window import MainWindow
        from ui.components.analytics_view import AnalyticsView, TokenBarChart, ModelDonutChart
        from ui.components.settings_view import SettingsView
        from ui.components.add_models_view import AddModelsView

        win = MainWindow()
        self.assertEqual(win.stack.count(), 9)

        # Test index 6: SettingsView
        self.assertIsInstance(win.stack.widget(6), SettingsView)
        # Test index 7: AddModelsView
        self.assertIsInstance(win.stack.widget(7), AddModelsView)
        # Test index 8: AnalyticsView
        self.assertIsInstance(win.stack.widget(8), AnalyticsView)

        # Test navigation to Settings stays on same window (index 6)
        win._handle_navigation("settings")
        self.assertEqual(win.stack.currentIndex(), 6)

        # Test back to chat
        win.settings_view.back_to_chat_requested.emit()
        self.assertEqual(win.stack.currentIndex(), 0)

        # Test navigation to Add AI Models stays on same window (index 7)
        win._handle_navigation("api_keys")
        self.assertEqual(win.stack.currentIndex(), 7)

        win.add_models_view.back_to_chat_requested.emit()
        self.assertEqual(win.stack.currentIndex(), 0)

        # Test navigation to Graphical Analytics stays on same window (index 8)
        win._handle_navigation("usage")
        self.assertEqual(win.stack.currentIndex(), 8)

        # Test graphical analytics components
        analytics = win.analytics_view
        self.assertIsInstance(analytics.bar_chart, TokenBarChart)
        self.assertIsInstance(analytics.donut_chart, ModelDonutChart)

        win.deleteLater()


if __name__ == "__main__":
    unittest.main()


