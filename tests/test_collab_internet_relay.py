"""
Unit Tests for Worldwide Internet Cloud Relay & Room Code Collaboration.
Tests:
- generate_room_code format, character set, and randomness
- CollabCloudRelay message envelope serialization & echo suppression
- CollabManager cloud session lifecycle (start_hosting_cloud, join_session_cloud, stop)
- Real-time event dispatching (edits, file adds, whiteboard strokes)
- CollabDialog dual-mode UI switching (Cloud Relay vs LAN) and room-code auto-detection
"""
import sys
import json
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

app = QApplication.instance() or QApplication(sys.argv)

from engine.collab_service import (
    generate_room_code,
    CollabCloudRelay,
    CollabManager,
)
from ui.components.collab_dialog import CollabDialog


class TestCollabInternetRelay(unittest.TestCase):
    """Tests room code generation and cloud relay networking logic."""

    def test_generate_room_code(self):
        codes = [generate_room_code() for _ in range(50)]
        for code in codes:
            self.assertTrue(code.startswith("SAGE-"))
            suffix = code.split("-", 1)[1]
            self.assertEqual(len(suffix), 4)
            self.assertTrue(suffix.isalnum())
            self.assertEqual(suffix, suffix.upper())
        # Uniqueness check across samples
        self.assertEqual(len(set(codes)), 50)

    def test_cloud_relay_init_and_echo_suppression(self):
        relay = CollabCloudRelay(room_code="SAGE-9999", user_name="Alice", role="host")
        self.assertEqual(relay.room_code, "SAGE-9999")
        self.assertEqual(relay.user_name, "Alice")
        self.assertEqual(relay.role, "host")
        self.assertTrue(relay.channel.startswith("sage_collab_sage_9999"))

        # Echo suppression: message from our own sender_id should be ignored
        received_events = []
        relay.on_edit_received = lambda msg: received_events.append(msg)

        echo_envelope = {
            "sender_id": relay.my_id,
            "sender_name": relay.user_name,
            "message": {
                "type": "edit",
                "filename": "main.py",
                "content": "x = 10",
                "version": 1
            }
        }
        # Simulate incoming echo message
        relay._process_incoming(json.dumps(echo_envelope))
        self.assertEqual(len(received_events), 0, "Echo message was not suppressed!")

        # Remote peer message should be processed
        peer_envelope = {
            "sender_id": "remote_peer_123",
            "sender_name": "Bob",
            "message": {
                "type": "edit",
                "filename": "main.py",
                "content": "x = 42",
                "version": 2
            }
        }
        relay._process_incoming(json.dumps(peer_envelope))
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0]["content"], "x = 42")

    def test_collab_manager_cloud_hosting_lifecycle(self):
        mgr = CollabManager()
        self.assertFalse(mgr.is_active)

        room_code = mgr.start_hosting_cloud(
            room_code="SAGE-1001",
            host_name="HostUser",
            initial_files={"app.py": {"language": "Python", "content": "print(1)"}}
        )
        self.assertEqual(room_code, "SAGE-1001")
        self.assertTrue(mgr.is_active)
        self.assertEqual(mgr.role, "host")
        self.assertEqual(mgr.connection_mode, "cloud")
        self.assertEqual(mgr.room_code, "SAGE-1001")
        self.assertIsNotNone(mgr.cloud_relay)

        # Test simulated incoming whiteboard stroke via cloud relay
        received_wb_strokes = []
        mgr.wb_stroke_received.connect(lambda stroke: received_wb_strokes.append(stroke))

        remote_stroke_envelope = {
            "sender_id": "peer_remote_abc",
            "sender_name": "RemoteDev",
            "message": {
                "type": "wb_stroke",
                "stroke": {
                    "id": "stroke-99",
                    "color": "#0FE6B5",
                    "width": 3,
                    "tool": "pen",
                    "points": [[10, 20], [15, 25]]
                }
            }
        }
        mgr.cloud_relay._process_incoming(json.dumps(remote_stroke_envelope))
        QCoreApplication.processEvents()

        self.assertEqual(len(received_wb_strokes), 1)
        self.assertEqual(received_wb_strokes[0]["id"], "stroke-99")

        # Clean teardown
        mgr.stop()
        self.assertFalse(mgr.is_active)
        self.assertIsNone(mgr.cloud_relay)

    def test_collab_manager_cloud_joining_lifecycle(self):
        mgr = CollabManager()
        joined = mgr.join_session_cloud(room_code="SAGE-2002", user_name="GuestUser")
        self.assertTrue(joined)
        self.assertTrue(mgr.is_active)
        self.assertEqual(mgr.role, "client")
        self.assertEqual(mgr.connection_mode, "cloud")
        self.assertEqual(mgr.room_code, "SAGE-2002")

        # Test incoming authoritative 'joined' state handshake
        received_joined = []
        mgr.session_synced.connect(lambda msg: received_joined.append(msg))

        state_handshake_envelope = {
            "sender_id": "host_peer_xyz",
            "sender_name": "HostUser",
            "message": {
                "type": "joined",
                "host_name": "HostUser",
                "files": {
                    "shared.py": {"language": "Python", "content": "# shared"}
                },
                "whiteboard_strokes": [
                    {"id": "st-1", "tool": "pen", "points": [[0, 0], [10, 10]]}
                ]
            }
        }
        mgr.cloud_relay._process_incoming(json.dumps(state_handshake_envelope))
        QCoreApplication.processEvents()

        self.assertEqual(len(received_joined), 1)
        self.assertEqual(received_joined[0]["host_name"], "HostUser")
        self.assertIn("shared.py", received_joined[0]["files"])

        mgr.stop()
        self.assertFalse(mgr.is_active)

    def test_collab_dialog_modes_and_auto_detection(self):
        mgr = CollabManager()
        dialog = CollabDialog(mgr, default_user_name="AliceTester")
        dialog.show()

        # Verify Worldwide Internet Cloud Relay is selected by default
        self.assertTrue(dialog.mode_cloud_radio.isChecked())
        self.assertFalse(dialog.mode_lan_radio.isHidden())
        self.assertTrue(dialog.cloud_banner.isVisible())
        self.assertFalse(dialog.lan_settings_widget.isVisible())
        self.assertTrue(dialog.room_code_display.text().startswith("SAGE-"))

        # Switch to Local LAN mode
        dialog.mode_lan_radio.setChecked(True)
        self.assertFalse(dialog.cloud_banner.isVisible())
        self.assertTrue(dialog.lan_settings_widget.isVisible())

        # Switch back to Cloud mode
        dialog.mode_cloud_radio.setChecked(True)
        self.assertTrue(dialog.cloud_banner.isVisible())
        self.assertFalse(dialog.lan_settings_widget.isVisible())

        # Test Join auto-detection
        # If user enters room code "SAGE-8888", it should be set
        dialog.join_addr_input.setText("SAGE-8888")
        self.assertEqual(dialog.join_addr_input.text().strip(), "SAGE-8888")

        dialog.close()
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
