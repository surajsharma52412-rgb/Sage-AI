"""
Unit Tests for Real-Time Collaborative Whiteboard in IDE.
Tests:
- WhiteboardCanvas stroke manipulation, vector primitives, undo, and clear
- CollabServer & CollabClient stroke routing, history caching, and welcome packet sync
- CollabManager Qt signals for wb_stroke_received, wb_cleared, wb_undo_received, wb_history_synced
- CodingIdeView whiteboard tab focus, maximize toggling, and UI components
"""
import sys
import time
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

# Ensure QApplication exists for GUI tests
app = QApplication.instance() or QApplication(sys.argv)

from engine.collab_service import CollabServer, CollabClient, CollabManager
from ui.components.collab_whiteboard import WhiteboardCanvas, CollabWhiteboardWidget
from ui.components.coding_ide_view import CodingIdeView


class TestWhiteboardCanvas(unittest.TestCase):
    """Tests the WhiteboardCanvas local drawing, undo, and history logic."""

    def setUp(self):
        self.canvas = WhiteboardCanvas()
        self.canvas.resize(800, 600)

    def tearDown(self):
        self.canvas.deleteLater()

    def test_initial_state(self):
        self.assertEqual(len(self.canvas.strokes), 0)
        self.assertEqual(self.canvas.active_tool, "pen")
        self.assertEqual(self.canvas.active_color, "#0FE6B5")
        self.assertEqual(self.canvas.active_width, 4)

    def test_add_and_undo_stroke(self):
        stroke = {
            "tool": "pen",
            "points": [(10, 10), (20, 20), (30, 30)],
            "color": "#38bdf8",
            "width": 4,
            "peer_name": "Alice"
        }
        self.canvas.add_remote_stroke(stroke)
        self.assertEqual(len(self.canvas.strokes), 1)
        self.assertEqual(self.canvas.strokes[0]["peer_name"], "Alice")

        # Undo
        self.canvas.undo_stroke()
        self.assertEqual(len(self.canvas.strokes), 0)

    def test_clear_canvas(self):
        for i in range(3):
            self.canvas.add_remote_stroke({
                "tool": "line",
                "points": [(i, i), (i + 10, i + 10)],
                "color": "#ffffff",
                "width": 2,
                "peer_name": "Bob"
            })
        self.assertEqual(len(self.canvas.strokes), 3)

        self.canvas.clear_canvas()
        self.assertEqual(len(self.canvas.strokes), 0)

    def test_set_history(self):
        history = [
            {"tool": "rect", "points": [(0, 0), (50, 50)], "color": "#0FE6B5", "width": 2, "peer_name": "Host"},
            {"tool": "circle", "points": [(60, 60), (100, 100)], "color": "#f43f5e", "width": 4, "peer_name": "Host"}
        ]
        self.canvas.set_history(history)
        self.assertEqual(len(self.canvas.strokes), 2)
        self.assertEqual(self.canvas.strokes[1]["tool"], "circle")


class TestCollabWhiteboardNetworking(unittest.TestCase):
    """Tests the real-time networking engine for collaborative whiteboard events."""

    def test_server_history_and_client_sync(self):
        # 1. Start Server
        server = CollabServer(host="127.0.0.1", port=0, host_name="AliceHost")
        self.assertTrue(server.start())
        port = server.port

        # Pre-seed server with a stroke
        sample_stroke = {
            "tool": "pen",
            "points": [(5, 5), (15, 15)],
            "color": "#0FE6B5",
            "width": 4,
            "peer_name": "AliceHost"
        }
        with server._lock:
            server.whiteboard_strokes.append(sample_stroke)

        # 2. Connect client and verify history sync on join
        received_join = []
        client = CollabClient(host="127.0.0.1", port=port, user_name="BobPeer")
        client.on_joined = lambda msg: received_join.append(msg)
        self.assertTrue(client.connect())

        timeout = time.time() + 2.0
        while not received_join and time.time() < timeout:
            time.sleep(0.05)

        self.assertTrue(len(received_join) > 0)
        welcome = received_join[0]
        self.assertIn("whiteboard_strokes", welcome)
        self.assertEqual(len(welcome["whiteboard_strokes"]), 1)
        self.assertEqual(welcome["whiteboard_strokes"][0]["color"], "#0FE6B5")

        # 3. Test Stroke Broadcasting Bob -> Alice
        server_strokes = []
        server.on_wb_stroke = lambda stroke: server_strokes.append(stroke)

        new_stroke = {
            "tool": "rect",
            "points": [(100, 100), (200, 200)],
            "color": "#a855f7",
            "width": 8,
            "peer_name": "BobPeer"
        }
        client.send_whiteboard_stroke(new_stroke)

        timeout = time.time() + 2.0
        while not server_strokes and time.time() < timeout:
            time.sleep(0.05)

        self.assertEqual(len(server_strokes), 1)
        self.assertEqual(server_strokes[0]["tool"], "rect")

        # Verify server cached it
        with server._lock:
            self.assertEqual(len(server.whiteboard_strokes), 2)

        # 4. Test Undo routing
        server_undos = []
        server.on_wb_undo = lambda peer: server_undos.append(peer)
        client.send_whiteboard_undo()

        timeout = time.time() + 2.0
        while not server_undos and time.time() < timeout:
            time.sleep(0.05)

        self.assertEqual(len(server_undos), 1)
        self.assertEqual(server_undos[0], "BobPeer")
        with server._lock:
            self.assertEqual(len(server.whiteboard_strokes), 1)

        # 5. Test Clear routing
        server_clears = []
        server.on_wb_clear = lambda peer: server_clears.append(peer)
        client.send_whiteboard_clear()

        timeout = time.time() + 2.0
        while not server_clears and time.time() < timeout:
            time.sleep(0.05)

        self.assertEqual(len(server_clears), 1)
        self.assertEqual(server_clears[0], "BobPeer")
        with server._lock:
            self.assertEqual(len(server.whiteboard_strokes), 0)

        # Clean shutdown
        client.disconnect()
        server.stop()

    def test_collab_manager_signals(self):
        # Host manager
        host_mgr = CollabManager()
        self.assertTrue(host_mgr.start_hosting(port=0, user_name="HostUser"))
        port = host_mgr.port

        # Client manager
        client_mgr = CollabManager()
        client_strokes = []
        client_clears = []
        client_undos = []
        client_history = []

        client_mgr.wb_stroke_received.connect(lambda s: client_strokes.append(s))
        client_mgr.wb_cleared.connect(lambda p: client_clears.append(p))
        client_mgr.wb_undo_received.connect(lambda p: client_undos.append(p))
        client_mgr.wb_history_synced.connect(lambda h: client_history.append(h))

        self.assertTrue(client_mgr.join_session("127.0.0.1", port, user_name="JoinerUser"))

        # Wait for handshake
        timeout = time.time() + 2.5
        while not client_mgr.is_active and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(client_mgr.is_active)

        # Broadcast stroke from host -> client receives
        test_stroke = {
            "tool": "pen",
            "points": [(1, 1), (2, 2)],
            "color": "#0FE6B5",
            "width": 4,
            "peer_name": "HostUser"
        }
        host_mgr.broadcast_wb_stroke(test_stroke)

        timeout = time.time() + 2.0
        while not client_strokes and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertEqual(len(client_strokes), 1)
        self.assertEqual(client_strokes[0]["color"], "#0FE6B5")

        # Broadcast undo from client -> host receives
        host_undos = []
        host_mgr.wb_undo_received.connect(lambda p: host_undos.append(p))
        client_mgr.broadcast_wb_undo()

        timeout = time.time() + 2.0
        while not host_undos and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertEqual(len(host_undos), 1)

        # Broadcast clear from client -> host receives
        host_clears = []
        host_mgr.wb_cleared.connect(lambda p: host_clears.append(p))
        client_mgr.broadcast_wb_clear()

        timeout = time.time() + 2.0
        while not host_clears and time.time() < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.05)

        self.assertEqual(len(host_clears), 1)

        # Clean teardown
        client_mgr.stop_session()
        host_mgr.stop_session()


class TestIdeWhiteboardIntegration(unittest.TestCase):
    """Tests the CodingIdeView whiteboard integration, button, and splitter behavior."""

    def setUp(self):
        self.ide = CodingIdeView()
        self.ide.resize(1000, 700)

    def tearDown(self):
        self.ide.collab_manager.stop_session()
        self.ide.deleteLater()

    def test_whiteboard_widget_present(self):
        self.assertIsNotNone(self.ide.whiteboard)
        self.assertIsInstance(self.ide.whiteboard, CollabWhiteboardWidget)
        self.assertEqual(self.ide.bottom_tabs.count(), 3)
        self.assertIn("Whiteboard", self.ide.bottom_tabs.tabText(2))

    def test_focus_whiteboard_and_maximize(self):
        self.ide._focus_whiteboard()
        self.assertEqual(self.ide.bottom_tabs.currentWidget(), self.ide.whiteboard)

        # Test maximize toggling: bottom whiteboard expands significantly
        sizes_before = self.ide.v_splitter.sizes()
        self.ide._on_whiteboard_maximize_toggled(True)
        sizes_max = self.ide.v_splitter.sizes()
        self.assertGreater(sizes_max[1], sizes_max[0])
        self.assertGreaterEqual(sizes_max[1], 300)

        # Restore
        self.ide._on_whiteboard_maximize_toggled(False)
        sizes_normal = self.ide.v_splitter.sizes()
        self.assertGreater(sizes_normal[0], sizes_max[0])


if __name__ == "__main__":
    unittest.main()
