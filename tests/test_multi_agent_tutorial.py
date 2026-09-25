"""
Unit tests for MultiAgentTutorialDialog and Tutorial integration in MultiAgentView.
"""
import unittest
import sys
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QApplication, QDialog, QTabWidget
from PySide6.QtCore import Qt

# Ensure single QApplication instance
app = QApplication.instance() or QApplication(sys.argv)

from ui.components.multi_agent_view import (
    MultiAgentView,
    MultiAgentTutorialDialog,
)
from config import (
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_DATA_ANALYSIS,
    AGENT_PLANNING,
    AGENT_IMAGE_MEDIA,
)


class TestMultiAgentTutorial(unittest.TestCase):
    """Test MultiAgentTutorialDialog structure, tabs, example loaders, and view triggers."""

    def setUp(self):
        self.view = MultiAgentView()

    def tearDown(self):
        self.view.deleteLater()

    def test_tutorial_dialog_tabs_and_structure(self):
        """Verify MultiAgentTutorialDialog instantiates with 5 informative tabs."""
        dlg = MultiAgentTutorialDialog(self.view)
        self.assertIsInstance(dlg, QDialog)
        self.assertIsInstance(dlg.tabs, QTabWidget)
        self.assertEqual(dlg.tabs.count(), 5)

        tab_titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
        self.assertIn("🚀 Quickstart", tab_titles)
        self.assertIn("👥 7 Specialized Agents", tab_titles)
        self.assertIn("🚌 Communication Bus", tab_titles)
        self.assertIn("🛠️ Pro Features", tab_titles)
        self.assertIn("💡 Interactive Examples", tab_titles)
        dlg.deleteLater()

    def test_tutorial_example_loaded_signal(self):
        """Verify _load_example emits example_loaded signal and closes dialog."""
        dlg = MultiAgentTutorialDialog(self.view)
        received = []

        dlg.example_loaded.connect(lambda p, a: received.append((p, a)))
        test_prompt = "Build a responsive web application with dark mode"
        test_agent = AGENT_CODING

        dlg._load_example(test_prompt, test_agent)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], (test_prompt, test_agent))
        dlg.deleteLater()

    def test_hub_view_tutorial_buttons_exist(self):
        """Verify MultiAgentView contains header and quick action tutorial buttons."""
        self.assertTrue(hasattr(self.view, "tutorial_btn"))
        self.assertIn("Hub Tutorial", self.view.tutorial_btn.text())

        self.assertTrue(hasattr(self.view, "tutorial_action_btn"))
        self.assertIn("Interactive Hub Guide", self.view.tutorial_action_btn.text())

    def test_hub_on_tutorial_example_loaded(self):
        """Verify _on_tutorial_example_loaded updates goal_input and agent_combo."""
        test_prompt = "Analyze sales retention dataset and compute metrics"
        test_agent = AGENT_DATA_ANALYSIS

        self.view._on_tutorial_example_loaded(test_prompt, test_agent)

        self.assertEqual(self.view.goal_input.toPlainText(), test_prompt)
        self.assertEqual(self.view.agent_combo.currentData(), test_agent)
        self.assertIn("Data Analysis Agent", self.view.status_lbl.text())

    @patch.object(QDialog, "exec")
    def test_show_tutorial_dialog_invoked(self, mock_exec):
        """Verify _show_tutorial_dialog launches the dialog and wires signal."""
        mock_exec.return_value = QDialog.Accepted
        self.view._show_tutorial_dialog()
        self.assertTrue(mock_exec.called)


if __name__ == "__main__":
    unittest.main()
