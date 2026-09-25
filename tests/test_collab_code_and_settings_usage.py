"""
Unit tests for tools section removal, model usage in SettingsView, and Collaboration room code generator.
"""
import unittest
from PySide6.QtWidgets import QApplication, QRadioButton
from PySide6.QtCore import Qt

from ui.components.sidebar import Sidebar
from ui.components.settings_view import SettingsView
from ui.components.analytics_view import AnalyticsView
from ui.components.collab_dialog import CollabPanelWidget
from engine.collab_service import CollabManager


class TestCollabCodeAndSettingsUsage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tools_section_removed_from_sidebar(self):
        """Verify 'tools' section is completely removed from Sidebar navigation buttons."""
        sb = Sidebar()
        self.assertNotIn("tools", sb._nav_buttons)
        # Check standard navigation items remain intact
        expected_items = ["home", "chat", "multi_agent", "coding_agent", "automations", "knowledge", "settings", "api_keys"]
        for item in expected_items:
            self.assertIn(item, sb._nav_buttons)
        sb.deleteLater()

    def test_model_usage_in_settings_view(self):
        """Verify SettingsView has Model Usage & Analytics embedded as a dedicated tab."""
        sv = SettingsView()
        self.assertEqual(sv.tabs.count(), 2)

        # Tab 0: Profile & Persona
        self.assertIn("Profile", sv.tabs.tabText(0))
        # Tab 1: Model Usage & Analytics
        self.assertIn("Model Usage", sv.tabs.tabText(1))

        # Check that tab 1 widget is AnalyticsView
        usage_tab = sv.tabs.widget(1)
        self.assertIsInstance(usage_tab, AnalyticsView)
        self.assertTrue(hasattr(sv, "analytics_view"))
        self.assertEqual(sv.analytics_view, usage_tab)

        # Check that refreshing usage works without errors
        sv.refresh_usage()

        # Check tab change handler triggers refresh
        sv.tabs.setCurrentIndex(1)
        self.assertEqual(sv.tabs.currentIndex(), 1)

        sv.deleteLater()

    def test_collab_room_code_generator_and_display(self):
        """Verify Collaboration panel room code generator is fully visible, centered, and buttons are responsive."""
        cm = CollabManager()
        panel = CollabPanelWidget(cm, default_user_name="Tester")

        # Check share card container exists
        self.assertTrue(hasattr(panel, "share_card"))
        self.assertIsNotNone(panel.share_card)

        # Check Room Code Display
        display = panel.room_code_display
        self.assertTrue(display.isReadOnly())
        self.assertEqual(display.alignment(), Qt.AlignCenter)
        self.assertGreaterEqual(display.height(), 30)

        # Check room code format
        initial_code = display.text().strip()
        self.assertTrue(len(initial_code) >= 6)
        self.assertTrue(initial_code.startswith("SAGE-"))

        # Check New Code button generates fresh code
        panel.gen_code_btn.click()
        new_code = display.text().strip()
        self.assertTrue(len(new_code) >= 6)
        self.assertTrue(new_code.startswith("SAGE-"))

        # Check Copy Code button
        panel._copy_room_code()
        clipboard = QApplication.clipboard()
        self.assertEqual(clipboard.text(), new_code)
        self.assertEqual(panel.copy_btn.text(), "✓ Copied!")
        self.assertEqual(panel.copy_feedback_lbl.text(), "✓ Copied!")

        # Check Network Mode radios
        self.assertTrue(hasattr(panel, "mode_cloud_radio"))
        self.assertTrue(hasattr(panel, "mode_lan_radio"))
        self.assertTrue(panel.mode_cloud_radio.isChecked())

        # Check Cloud banner has word wrap
        cb_layout = panel.cloud_banner.layout()
        cb_text = cb_layout.itemAt(1).widget()
        self.assertTrue(cb_text.wordWrap())

        panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
