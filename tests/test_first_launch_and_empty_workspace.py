"""
Unit tests for first launch onboarding dialog and zero pre-opened folder requirement.
"""
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from database.db_manager import DatabaseManager, get_db
from ui.components.onboarding_dialog import FirstLaunchOnboardingDialog
from ui.components.coding_ide_view import CodingIdeView
from ui.components.general_settings_dialog import GeneralSettingsDialog
from ui.components.settings_view import SettingsView


class TestFirstLaunchAndEmptyWorkspace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = get_db()
        # Save previous values to restore after test
        self._orig_completed = self.db.get_setting("onboarding_completed")
        self._orig_name = self.db.get_setting("user_display_name")
        self._orig_email = self.db.get_setting("user_email")
        self._orig_role = self.db.get_setting("user_role")

    def tearDown(self):
        # Restore db settings
        if self._orig_completed is not None:
            self.db.set_setting("onboarding_completed", self._orig_completed)
        if self._orig_name is not None:
            self.db.set_setting("user_display_name", self._orig_name)
        if self._orig_email is not None:
            self.db.set_setting("user_email", self._orig_email)
        if self._orig_role is not None:
            self.db.set_setting("user_role", self._orig_role)

    def test_onboarding_dialog_starts_empty_without_prefilled_inputs(self):
        """Verify onboarding dialog fields start completely empty with no pre-input."""
        dlg = FirstLaunchOnboardingDialog()

        # Check fields are strictly empty strings
        self.assertEqual(dlg.name_input.text(), "")
        self.assertEqual(dlg.email_input.text(), "")
        self.assertEqual(dlg.role_input.text(), "")

        # Check placeholder texts guide the user
        self.assertTrue(len(dlg.name_input.placeholderText()) > 0)
        self.assertTrue(len(dlg.email_input.placeholderText()) > 0)
        self.assertTrue(len(dlg.role_input.placeholderText()) > 0)

        # Check preferences options are present
        self.assertGreaterEqual(dlg.persona_combo.count(), 4)

        dlg.deleteLater()

    def test_onboarding_validation_and_saving(self):
        """Verify onboarding dialog requires a name and correctly saves preferences to DB."""
        dlg = FirstLaunchOnboardingDialog()

        # Validation: empty name should not complete
        dlg.name_input.setText("   ")
        dlg._save_and_launch()
        self.assertNotEqual(dlg.result(), dlg.DialogCode.Accepted)

        # Fill in valid user details
        test_name = "Alex Vance"
        test_email = "alex.vance@example.org"
        test_role = "AI Engineer"

        dlg.name_input.setText(test_name)
        dlg.email_input.setText(test_email)
        dlg.role_input.setText(test_role)
        dlg.persona_combo.setCurrentIndex(1)  # Architect

        dlg._save_and_launch()
        self.assertEqual(dlg.result(), dlg.DialogCode.Accepted)

        # Check DB settings
        self.assertEqual(self.db.get_setting("user_display_name"), test_name)
        self.assertEqual(self.db.get_setting("user_email"), test_email)
        self.assertEqual(self.db.get_setting("user_role"), test_role)
        self.assertEqual(self.db.get_setting("onboarding_completed"), "true")
        self.assertEqual(self.db.get_setting("user_persona_idx"), "1")

        dlg.deleteLater()

    def test_coding_ide_has_no_preopened_folder_on_startup(self):
        """Verify CodingIdeView has no pre-opened folder on launch and prompts user to open one."""
        ide = CodingIdeView()

        # No folder opened by default
        self.assertIsNone(ide.workspace_path)
        self.assertEqual(ide.open_documents, {})

        # Explorer tree root shows empty message
        root_item = ide.tree_widget.topLevelItem(0)
        self.assertIsNotNone(root_item)
        self.assertIn("No folder opened", root_item.text(0))

        # Action item to open folder exists
        open_item = root_item.child(0)
        self.assertIsNotNone(open_item)
        self.assertIn("Click to Open Folder", open_item.text(0))

        # Breadcrumb shows no folder opened
        self.assertIn("(No folder opened)", ide.breadcrumb_lbl.text())

        # Project dropdown button in top header shows 'Open Folder'
        self.assertIn("Open Folder", ide.project_dropdown.text())

        # Editor text explains no folder is opened
        self.assertIn("No folder or file opened", ide.editor.toPlainText())

        ide.deleteLater()

    def test_general_settings_and_settings_view_no_hardcoded_user(self):
        """Verify settings views load user from DB and don't hardcode Suraj Sharma."""
        # When user_display_name in DB is empty
        self.db.set_setting("user_display_name", "")
        self.db.set_setting("user_email", "")

        gs = GeneralSettingsDialog()
        self.assertEqual(gs.name_edit.text(), "")
        self.assertEqual(gs.email_edit.text(), "")
        gs.deleteLater()

        sv = SettingsView()
        self.assertEqual(sv.name_edit.text(), "")
        self.assertEqual(sv.email_edit.text(), "")
        sv.deleteLater()


if __name__ == "__main__":
    unittest.main()
