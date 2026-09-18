"""
Unit tests for DatabaseManager in Sage AI.
"""
import unittest
import tempfile
import gc
from pathlib import Path
from database.db_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sage.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        del self.db
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_session_lifecycle(self):
        # Create session
        session = self.db.create_session("Test Chat", model_used="Groq Chat")
        self.assertIsNotNone(session["id"])
        self.assertEqual(session["title"], "Test Chat")

        # Get sessions
        sessions = self.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["id"], session["id"])

        # Update title
        updated = self.db.update_session_title(session["id"], "Renamed Chat")
        self.assertTrue(updated)
        retrieved = self.db.get_session(session["id"])
        self.assertEqual(retrieved["title"], "Renamed Chat")

        # Delete session
        deleted = self.db.delete_session(session["id"])
        self.assertTrue(deleted)
        self.assertEqual(len(self.db.get_sessions()), 0)

    def test_messages_crud_and_cascade(self):
        session = self.db.create_session("Message Session")
        sid = session["id"]

        # Add messages
        msg1 = self.db.add_message(sid, "user", "Hello Sage")
        self.assertEqual(msg1["content"], "Hello Sage")

        sources = [{"title": "Docs", "url": "https://python.org"}]
        meta = {"latency_ms": 120.5}
        msg2 = self.db.add_message(sid, "assistant", "Hello User!", model="Groq", sources=sources, metadata=meta)

        messages = self.db.get_session_messages(sid)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["sources"][0]["title"], "Docs")
        self.assertEqual(messages[1]["metadata"]["latency_ms"], 120.5)

        # Cascading delete
        self.db.delete_session(sid)
        self.assertEqual(len(self.db.get_session_messages(sid)), 0)

    def test_settings_storage(self):
        self.assertIsNone(self.db.get_setting("non_existent"))
        self.assertEqual(self.db.get_setting("non_existent", "default_val"), "default_val")

        self.db.set_setting("groq_api_key", "gsk_test123")
        self.assertEqual(self.db.get_setting("groq_api_key"), "gsk_test123")

        # Overwrite
        self.db.set_setting("groq_api_key", "gsk_test456")
        self.assertEqual(self.db.get_setting("groq_api_key"), "gsk_test456")

        settings = self.db.get_all_settings()
        self.assertIn("groq_api_key", settings)


if __name__ == "__main__":
    unittest.main()
