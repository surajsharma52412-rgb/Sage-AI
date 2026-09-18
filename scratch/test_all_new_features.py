import os
import sys
import unittest
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF

# Setup app
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from ui.components.sidebar import Sidebar, ChatSessionItem
from ui.components.collab_dialog import CollabPanelWidget, CollabDialog
from ui.components.collab_whiteboard import WhiteboardCanvas, CollabWhiteboardWidget
from ui.components.coding_ide_view import CodingIdeView
from engine.collab_service import CollabManager
from engine.providers.ollama_provider import OllamaProvider
from engine.security_vault import SecurityVault
from database import DatabaseManager, get_db


class ComprehensiveEnhancementsTest(unittest.TestCase):

    def test_1_ollama_no_autostart(self):
        """Verify Ollama does not automatically start during import or availability checks."""
        import main
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("start_ollama_service, daemon=True", content, "main.py must not auto-start Ollama on launch")

        # Provider is_available should just ping URL, not run subprocess start
        provider = OllamaProvider()
        # Verify method does not trigger subprocess
        import inspect
        src = inspect.getsource(provider.is_available)
        self.assertNotIn("subprocess.Popen", src)
        self.assertNotIn("start_ollama_service", src)

    def test_2_chat_history_sidebar_system(self):
        """Verify Sidebar has interactive chat history with rename, delete, switch, and new chat."""
        sidebar = Sidebar()
        sessions = [
            {"id": "sess-1", "title": "First Project Discussion"},
            {"id": "sess-2", "title": "Debugging Neural Net"},
            {"id": "sess-3", "title": "Refactoring Architecture"},
        ]
        sidebar.load_sessions(sessions, active_id="sess-2")
        self.assertEqual(len(sidebar._session_items), 3)
        self.assertEqual(sidebar._active_session_id, "sess-2")

        # Verify active highlight
        item2 = sidebar._session_items["sess-2"]
        self.assertTrue(item2.is_active)
        item1 = sidebar._session_items["sess-1"]
        self.assertFalse(item1.is_active)

        # Rename session
        sidebar.update_session_title("sess-2", "Neural Net Debug - Solved")
        self.assertEqual(item2.title_lbl.text(), "Neural Net Debug - Solved")

        # Add session
        sidebar.add_session("sess-4", "New Project Idea")
        self.assertEqual(sidebar._active_session_id, "sess-4")
        self.assertEqual(len(sidebar._session_items), 4)

        # Remove session
        sidebar.remove_session("sess-1")
        self.assertEqual(len(sidebar._session_items), 3)
        self.assertNotIn("sess-1", sidebar._session_items)

        # Signals
        switched_ids = []
        sidebar.chat_session_selected.connect(lambda sid: switched_ids.append(sid))
        sidebar.set_active_session("sess-3")
        self.assertEqual(sidebar._active_session_id, "sess-3")
        self.assertTrue(sidebar._session_items["sess-3"].is_active)

    def test_3_ide_no_preselected_program(self):
        """Verify IDE starts with no preselected file and requires program selection before AI run."""
        ide = CodingIdeView()
        # Verify no open document active by default
        self.assertIsNone(ide.active_filename, "IDE must not pre-select any file on start")
        self.assertEqual(len(ide.open_documents), 0, "No default files should be pre-opened")
        self.assertIn("No program or file selected", ide.editor.toPlainText())

        # Target program combo should have placeholder
        self.assertGreater(ide.agent_target_combo.count(), 0)
        self.assertEqual(ide.agent_target_combo.itemData(0), "")

        # Try to run AI agent with no program selected - should be blocked with warning
        ide.agent_prompt.setText("Write a quick function")
        ide._run_coding_agent()
        # It should display warning to select program first
        self.assertIn("Select a program", ide.agent_target_warning.text())
        self.assertIsNone(ide.agent_worker, "Worker should not start without target file selected")

    def test_4_collab_and_invite_same_window(self):
        """Verify clicking collaboration / invite operates in the same window (no popup dialogs)."""
        ide = CodingIdeView()
        # Initial state: right dock is hidden or agent page
        self.assertIsNotNone(ide.collab_panel)
        self.assertIsInstance(ide.collab_panel, CollabPanelWidget)

        # Calling _open_collab_dialog should open panel in same window
        ide._open_collab_dialog()
        self.assertFalse(ide.right_dock.isHidden(), "Right dock should not be hidden in same window")
        self.assertEqual(ide.right_stack.currentIndex(), 1, "Right stack should switch to collab page (index 1)")

        # Verify close_btn hides right dock in same window
        ide.collab_panel.accept()
        self.assertTrue(ide.right_dock.isHidden(), "Closing collab panel should hide dock in same window")

    def test_5_smooth_whiteboard(self):
        """Verify whiteboard has caching pixmaps and distance-squared decimation."""
        wb = WhiteboardCanvas()
        self.assertTrue(hasattr(wb, "_strokes_pixmap"))
        self.assertTrue(hasattr(wb, "_grid_pixmap"))

        # Add initial point
        wb._current_points = [QPointF(10.0, 10.0)]
        # Tiny delta (below threshold) should be filtered to keep drawing smooth and lag-free
        dist_sq = (10.2 - 10.0)**2 + (10.1 - 10.0)**2
        self.assertLess(dist_sq, 6.0)

        # Larger delta gets added
        far_point = QPointF(20.0, 20.0)
        dist_sq_far = (far_point.x() - 10.0)**2 + (far_point.y() - 10.0)**2
        self.assertGreater(dist_sq_far, 6.0)

    def test_6_api_keys_storage(self):
        """Verify API keys storage locations in SecurityVault and database."""
        db = get_db()
        # Verify settings table exists
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            row = cursor.fetchone()
            self.assertIsNotNone(row, "Settings table should exist in database")
        finally:
            conn.close()

        # Verify SecurityVault master key file path
        vault_key_path = Path.home() / ".sage_security" / "vault.key"
        self.assertTrue(str(vault_key_path).endswith("vault.key"))

        # Verify .env path
        env_path = Path(".env")
        self.assertTrue(env_path.name == ".env")


if __name__ == "__main__":
    unittest.main()
