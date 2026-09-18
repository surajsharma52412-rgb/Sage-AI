import unittest
import os
import sys
import tempfile
import shutil
from PySide6.QtWidgets import QApplication, QPushButton

# Ensure QApplication instance exists for Qt widget tests
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from database.db_manager import DatabaseManager, get_db
from engine.automation_agent import GmailAutomationService, AutomationManager, MOCK_SANDBOX_EMAILS
from ui.components.input_bar import MessageInputBar, AttachmentChip
from ui.components.message_bubble import MessageBubble
from ui.components.permission_dialog import PermissionDialog


class TestAutomationsAndAttachments(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_automations.db")
        self.db = DatabaseManager(self.db_path)
        
        # Create a sample test code file
        self.sample_code_file = os.path.join(self.test_dir, "test.py")
        with open(self.sample_code_file, "w", encoding="utf-8") as f:
            f.write("# Sample test code\nprint('Hello from test.py')\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. File Attachments Tests
    # -------------------------------------------------------------
    def test_attachment_chip_creation_and_removal(self):
        """Test AttachmentChip formatting and remove signal."""
        removed_paths = []
        chip = AttachmentChip(self.sample_code_file, "test.py", 42, False)
        chip.removed.connect(lambda p: removed_paths.append(p))
        
        self.assertEqual(chip.file_path, self.sample_code_file)
        
        # Simulate user clicking remove (X) button
        chip.findChild(QPushButton).click()
        self.assertEqual(len(removed_paths), 1)
        self.assertEqual(removed_paths[0], self.sample_code_file)

    def test_input_bar_attachment_flow(self):
        """Test adding, listing, and clearing file attachments in MessageInputBar."""
        bar = MessageInputBar()
        self.assertEqual(len(bar.attached_files), 0)
        self.assertTrue(bar.attachments_widget.isHidden())
        
        # Add sample file
        bar.add_attachment(self.sample_code_file)
        self.assertEqual(len(bar.attached_files), 1)
        self.assertEqual(bar.attached_files[0]["path"], self.sample_code_file)
        self.assertEqual(bar.attached_files[0]["name"], "test.py")
        self.assertFalse(bar.attachments_widget.isHidden())
        
        # Duplicate should not be added twice
        bar.add_attachment(self.sample_code_file)
        self.assertEqual(len(bar.attached_files), 1)
        
        # Remove attachment
        bar.remove_attachment(self.sample_code_file)
        self.assertEqual(len(bar.attached_files), 0)
        self.assertTrue(bar.attachments_widget.isHidden())

    def test_message_bubble_renders_attachments(self):
        """Test that MessageBubble displays attachment chips for user messages."""
        attachments = [
            {"path": self.sample_code_file, "name": "test.py", "size": 42}
        ]
        bubble = MessageBubble(
            role="user",
            content="Please review this file",
            attachments=attachments
        )
        self.assertTrue(hasattr(bubble, "attachments_box"))
        self.assertIsNotNone(bubble.attachments_box)

    # -------------------------------------------------------------
    # 2. AI Automations & Permission Gate Tests
    # -------------------------------------------------------------
    def test_gmail_service_sandbox_fetch(self):
        """Test that GmailAutomationService correctly fetches unread emails in sandbox mode."""
        service = GmailAutomationService()
        self.assertTrue(service.is_sandbox_mode())
        
        emails = service.fetch_unread_emails(max_count=5)
        self.assertGreaterEqual(len(emails), 1)
        # Verify email structure
        first = emails[0]
        self.assertIn("sender", first)
        self.assertIn("subject", first)
        self.assertIn("body", first)

    def test_permission_gate_denied_flow(self):
        """Test that when permission is denied, email is strictly NOT sent."""
        service = GmailAutomationService()
        email_data = {
            "id": "test_msg_999",
            "sender": "boss@enterprise.com",
            "sender_name": "Big Boss",
            "subject": "Quarterly Budget Approval",
            "body": "Is the Q4 budget finalized?",
            "is_read": False
        }
        
        # Mock permission checker that simulates user clicking "Deny / Discard"
        def mock_deny_checker(action, recipient, subject, body):
            return False
            
        result = service.execute_send_reply(
            email_data=email_data,
            reply_body="Yes, approved.",
            permission_checker=mock_deny_checker
        )
        
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "DENIED")
        self.assertIn("denied permission", result["message"])

    def test_permission_gate_approved_flow(self):
        """Test that when permission is granted, email is successfully transmitted in sandbox."""
        service = GmailAutomationService()
        email_data = {
            "id": "mock_msg_101",
            "sender": "sarah.connor@cyberdyne-systems.com",
            "sender_name": "Sarah Connor",
            "subject": "Urgent: Project timeline",
            "body": "Can you send the schedule?",
            "is_read": False
        }
        
        # Mock permission checker that simulates user clicking "Authorize & Send"
        def mock_approve_checker(action, recipient, subject, body):
            return True
            
        result = service.execute_send_reply(
            email_data=email_data,
            reply_body="Hi Sarah, the deployment schedule is on track for 3:00 PM.",
            permission_checker=mock_approve_checker
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "SENT_SANDBOX")
        self.assertIn("delivered", result["message"])

    def test_automation_manager_audit_logging(self):
        """Test recording and retrieving security compliance audit trail."""
        manager = AutomationManager()
        
        manager.record_audit_event(
            action_type="📧 Send Email Reply",
            target="client@domain.com",
            decision="APPROVED",
            status="SUCCESS",
            details="Sent reply regarding contract terms."
        )
        manager.record_audit_event(
            action_type="📂 Modify System File",
            target="/etc/hosts",
            decision="DENIED",
            status="CANCELLED",
            details="User rejected unauthorized file overwrite."
        )
        
        history = manager.get_audit_history()
        self.assertEqual(len(history), 2)
        # Most recent first
        self.assertEqual(history[0]["action_type"], "📂 Modify System File")
        self.assertEqual(history[0]["decision"], "DENIED")
        self.assertEqual(history[1]["action_type"], "📧 Send Email Reply")
        self.assertEqual(history[1]["decision"], "APPROVED")

    # -------------------------------------------------------------
    # 3. Settings Dialog & Database Storage Tests
    # -------------------------------------------------------------
    def test_db_settings_storage_for_automations(self):
        """Test storing and retrieving Gmail and automation settings in SQLite."""
        self.db.set_setting("gmail_address", "engineer@example.com")
        self.db.set_setting("gmail_app_password", "abcd-efgh-ijkl-mnop")
        self.db.set_setting("gmail_sandbox_mode", "false")
        self.db.set_setting("gmail_imap_host", "imap.gmail.com")
        self.db.set_setting("gmail_smtp_host", "smtp.gmail.com")
        
        self.assertEqual(self.db.get_setting("gmail_address"), "engineer@example.com")
        self.assertEqual(self.db.get_setting("gmail_app_password"), "abcd-efgh-ijkl-mnop")
        self.assertEqual(self.db.get_setting("gmail_sandbox_mode"), "false")
        self.assertEqual(self.db.get_setting("gmail_imap_host"), "imap.gmail.com")
        self.assertEqual(self.db.get_setting("gmail_smtp_host"), "smtp.gmail.com")


if __name__ == "__main__":
    unittest.main()
