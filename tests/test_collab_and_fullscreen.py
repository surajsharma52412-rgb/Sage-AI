"""
Unit Tests for IDE Whole-Screen Mode and Real-Time Multi-User Multi-File Collaboration.
Tests:
- CollabServer socket lifecycle and clean shutdown
- CollabClient handshake, multi-file synchronization, and independent editing
- CollabManager Qt Signal emission and zero-deadlock session termination
- CodingIdeView multi-file tabs, switching, and collaborative syncing
- CodingIdeView fullscreen state toggling
- MainWindow whole-screen IDE layout switching
"""
import sys
import time
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

# Ensure QApplication exists for GUI tests
app = QApplication.instance() or QApplication(sys.argv)

from engine.collab_service import CollabServer, CollabClient, CollabManager, get_local_ip
from ui.components.coding_ide_view import CodingIdeView
from ui.components.collab_dialog import CollabDialog
from ui.main_window import MainWindow


class TestCollabService(unittest.TestCase):
    """Tests the real-time networking engine."""

    def test_local_ip_detection(self):
        ip = get_local_ip()
        self.assertIsInstance(ip, str)
        self.assertTrue(len(ip) >= 7)  # At least '1.1.1.1' or '127.0.0.1'

    def test_server_client_handshake_and_sync(self):
        server = CollabServer(host="127.0.0.1", port=0, host_name="AliceHost")
        server.update_doc_state("test.py", "Python", "print('Hello from Host')")

        self.assertTrue(server.start(), "Server failed to bind and start")
        test_port = server.port

        received_doc = []
        client = CollabClient(host="127.0.0.1", port=test_port, user_name="BobClient")
        client.on_joined = lambda msg: received_doc.append(msg)

        connected = client.connect()
        self.assertTrue(connected, "Client failed to connect to server")

        # Wait up to 2 seconds for handshake
        timeout = time.time() + 2.0
        while not received_doc and time.time() < timeout:
            time.sleep(0.05)

        self.assertTrue(len(received_doc) > 0, "Client did not receive welcome packet")
        join_payload = received_doc[0]
        self.assertEqual(join_payload.get("host_name"), "AliceHost")
        self.assertIn("files", join_payload)
        self.assertIn("test.py", join_payload["files"])
        self.assertEqual(join_payload["files"]["test.py"]["content"], "print('Hello from Host')")

        # Test bidirectional edit: Bob sends edit -> Server receives
        server_edits = []
        server.on_edit_received = lambda msg: server_edits.append(msg)

        client.send_message({
            "type": "edit",
            "filename": "test.py",
            "content": "print('Hello from Bob')",
            "version": 2
        })

        timeout = time.time() + 2.0
        while not server_edits and time.time() < timeout:
            time.sleep(0.05)

        self.assertTrue(len(server_edits) > 0, "Server did not receive client edit")
        self.assertEqual(server_edits[0]["content"], "print('Hello from Bob')")

        # Clean shutdown without hanging
        start_t = time.time()
        client.disconnect()
        server.stop()
        self.assertLess(time.time() - start_t, 2.0, "Server/Client teardown took too long")

    def test_collab_manager_hosting_and_joining_clean_stop(self):
        host_mgr = CollabManager()
        client_mgr = CollabManager()

        started = host_mgr.start_hosting(
            port=0,
            host_name="HostDev",
            initial_doc={"filename": "app.py", "language": "Python", "content": "x = 42"}
        )
        self.assertTrue(started)
        self.assertTrue(host_mgr.is_active)
        self.assertEqual(host_mgr.role, "host")
        port = host_mgr.server.port

        # Connect client manager
        synced_doc = []
        client_mgr.doc_sync_received.connect(lambda doc: synced_doc.append(doc))

        joined = client_mgr.join_session(host="127.0.0.1", port=port, user_name="PeerDev")
        self.assertTrue(joined)

        timeout = time.time() + 2.0
        while not synced_doc and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(len(synced_doc) > 0, "CollabManager client did not receive doc_sync signal")
        self.assertEqual(synced_doc[0]["content"], "x = 42")

        # Test peer edit propagation
        remote_edits = []
        host_mgr.edit_received.connect(lambda edit: remote_edits.append(edit))

        client_mgr.broadcast_local_edit("x = 100", 7, filename="app.py")

        timeout = time.time() + 2.0
        while not remote_edits and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(len(remote_edits) > 0, "Host manager did not receive edit_received signal")
        self.assertEqual(remote_edits[0]["content"], "x = 100")

        # Verify zero-deadlock teardown
        start_t = time.time()
        client_mgr.stop()
        host_mgr.stop()
        self.assertLess(time.time() - start_t, 2.0, "CollabManager stop() took too long; possible deadlock")

    def test_multi_file_collaboration_and_independent_edits(self):
        host_mgr = CollabManager()
        client_mgr = CollabManager()

        initial_files = {
            "main.py": {"filename": "main.py", "language": "Python", "content": "print('Main')"},
            "utils.py": {"filename": "utils.py", "language": "Python", "content": "def add(a, b): return a + b"}
        }

        started = host_mgr.start_hosting(
            port=0,
            host_name="HostAlice",
            initial_files=initial_files
        )
        self.assertTrue(started)
        port = host_mgr.server.port

        client_synced = []
        client_mgr.session_synced.connect(lambda data: client_synced.append(data))

        joined = client_mgr.join_session(host="127.0.0.1", port=port, user_name="ClientBob")
        self.assertTrue(joined)

        timeout = time.time() + 2.0
        while not client_synced and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(len(client_synced) > 0, "Client did not receive session_synced signal")
        received_files = client_synced[0].get("files", {})
        self.assertIn("main.py", received_files)
        self.assertIn("utils.py", received_files)

        # Independent file edit: Client edits utils.py
        host_received_edits = []
        host_mgr.edit_received.connect(lambda edit: host_received_edits.append(edit))

        client_mgr.broadcast_local_edit("def add(a, b): return a + b + 1", cursor_pos=10, filename="utils.py")

        timeout = time.time() + 2.0
        while not host_received_edits and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(len(host_received_edits) > 0, "Host did not receive edit on utils.py")
        self.assertEqual(host_received_edits[0]["filename"], "utils.py")
        self.assertEqual(host_received_edits[0]["content"], "def add(a, b): return a + b + 1")

        # Test adding a 3rd file to the room dynamically
        client_added_files = []
        client_mgr.file_added.connect(lambda msg: client_added_files.append(msg))

        host_mgr.broadcast_file_add("new_module.py", "Python", "NEW_VAR = 99")

        timeout = time.time() + 2.0
        while not client_added_files and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(len(client_added_files) > 0, "Client did not receive dynamically added file")
        self.assertEqual(client_added_files[0]["filename"], "new_module.py")

        # Clean shutdown
        client_mgr.stop()
        host_mgr.stop()


class TestIdeFullscreenAndTabs(unittest.TestCase):
    """Tests the whole-screen IDE and multi-file tab system."""

    def setUp(self):
        self.ide = CodingIdeView()

    def tearDown(self):
        if hasattr(self, "ide") and self.ide:
            self.ide.collab_manager.stop()
            self.ide.deleteLater()

    def test_coding_ide_has_fullscreen_and_collab_buttons(self):
        self.assertIsNotNone(self.ide.fullscreen_btn)
        self.assertIsNotNone(self.ide.collab_btn)
        # Redundant top banner removed to maximize vertical coding space
        self.assertFalse(hasattr(self.ide, "fullscreen_banner"))
        self.assertIn("⛶", self.ide.fullscreen_btn.text())
        self.assertIn("Collab", self.ide.collab_btn.text())

    def test_multi_document_tabs(self):
        initial_count = self.ide.tab_bar.count()

        # Open doc 1
        self.ide.open_document("app.py", "print('App')", language="Python")
        self.assertEqual(self.ide.tab_bar.count(), initial_count + 1)
        self.assertEqual(self.ide.active_filename, "app.py")
        self.assertEqual(self.ide.editor.toPlainText(), "print('App')")

        # Open doc 2
        self.ide.open_document("style.css", "body { margin: 0; }", language="CSS")
        self.assertEqual(self.ide.tab_bar.count(), initial_count + 2)
        self.assertEqual(self.ide.active_filename, "style.css")
        self.assertEqual(self.ide.editor.toPlainText(), "body { margin: 0; }")

        # Switch back to doc 1
        self.ide.tab_bar.setCurrentIndex(initial_count)
        self.assertEqual(self.ide.active_filename, "app.py")
        self.assertEqual(self.ide.editor.toPlainText(), "print('App')")

        # Close doc 2
        self.ide._on_tab_close_requested(initial_count + 1)
        self.assertEqual(self.ide.tab_bar.count(), initial_count + 1)
        self.assertNotIn("style.css", self.ide.open_documents)

    def test_fullscreen_toggle_in_ide_view(self):
        self.assertFalse(self.ide.is_fullscreen)

        # Toggle on
        self.ide.toggle_fullscreen(True)
        self.assertTrue(self.ide.is_fullscreen)
        self.assertIn("🗗", self.ide.fullscreen_btn.text())

        # Toggle off
        self.ide.toggle_fullscreen(False)
        self.assertFalse(self.ide.is_fullscreen)
        self.assertIn("⛶", self.ide.fullscreen_btn.text())

    def test_main_window_fullscreen_layout(self):
        window = MainWindow()
        window.stack.setCurrentIndex(2)
        ide = window.coding_ide_view

        # Trigger whole-screen IDE mode
        window._toggle_ide_fullscreen(True)
        self.assertFalse(window.sidebar.isVisible())
        self.assertFalse(window.top_bar.isVisible())

        # Exit whole-screen mode
        window._toggle_ide_fullscreen(False)
        self.assertTrue(window.sidebar.isVisible())
        self.assertTrue(window.top_bar.isVisible())

        window.coding_ide_view.collab_manager.stop()
        window.deleteLater()

    def test_collab_dialog_creation(self):
        dialog = CollabDialog(self.ide.collab_manager, default_user_name="Tester", parent=self.ide)
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.tabs.count(), 2)
        dialog.close()
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
