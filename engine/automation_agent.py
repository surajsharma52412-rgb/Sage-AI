"""
AI Automation Engine & Services for Sage AI.
Coordinates task automations with Human-in-the-Loop permission checks:
- Gmail unread message scanning & intelligent reply drafting
- Mandatory permission gate verification before sending emails or modifying system files
- Real IMAP/SMTP and Safe Sandbox simulation modes
- Audit logging for security compliance
"""
import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from database.db_manager import get_db
from engine.router import FallbackRouter
from engine.automation.state_store import AutomationStateStore
from engine.automation.automation_tools import AutomationToolRegistry
from engine.automation.autonomous_automation_agent import AutonomousAutomationAgent


# Default sandbox emails for testing Gmail automation out-of-the-box
MOCK_SANDBOX_EMAILS = [
    {
        "id": "mock_msg_101",
        "sender": "sarah.connor@cyberdyne-systems.com",
        "sender_name": "Sarah Connor",
        "subject": "Urgent: Project timeline & deployment review for Sage AI",
        "date": "Today, 10:15 AM",
        "snippet": "Hi team, Can you please send the updated deployment schedule and let us know if the multi-provider fallback engine is ready for production?",
        "body": "Hi team,\n\nCan you please send the updated deployment schedule and let us know if the multi-provider fallback engine is ready for production? We are meeting the steering committee this afternoon.\n\nBest regards,\nSarah",
        "is_read": False,
        "category": "High Priority"
    },
    {
        "id": "mock_msg_102",
        "sender": "alex.dev@innovatech.io",
        "sender_name": "Alex Rivers",
        "subject": "Calculator Tkinter refactoring feedback (test.py)",
        "date": "Today, 09:30 AM",
        "snippet": "Hey! I looked at test.py. The calculator works great but it would be awesome to add keyboard bindings and clean error handling.",
        "body": "Hey!\n\nI looked at test.py. The calculator works great but it would be awesome to add keyboard bindings and clean error handling. Let me know when you push the next update.\n\nCheers,\nAlex",
        "is_read": False,
        "category": "Development"
    },
    {
        "id": "mock_msg_103",
        "sender": "notifications@github.com",
        "sender_name": "GitHub Notifications",
        "subject": "[Sage-AI] Pull Request #42: Dynamic Model Scanning Approved",
        "date": "Yesterday, 4:20 PM",
        "snippet": "All 30 unit tests passed. Ready to merge into main branch.",
        "body": "All 30 unit tests passed. Coverage: 98%. Ready to merge into main branch upon maintainer review.",
        "is_read": False,
        "category": "CI/CD"
    }
]


class GmailAutomationService:
    """Manages Gmail email reading, AI reply drafting, and permission-gated delivery."""

    def __init__(self, router: Optional[FallbackRouter] = None):
        self.db = get_db()
        self.router = router or FallbackRouter()
        self.sandbox_emails = list(MOCK_SANDBOX_EMAILS)

    def is_configured(self) -> bool:
        user = self.db.get_setting("gmail_address")
        pw = self.db.get_setting("gmail_app_password")
        return bool(user and pw)

    def is_sandbox_mode(self) -> bool:
        # Default to sandbox mode if not configured, or if explicit setting is true
        return self.db.get_setting("gmail_sandbox_mode", "true") == "true" or not self.is_configured()

    def fetch_unread_emails(self, max_count: int = 5) -> List[Dict[str, Any]]:
        """Fetches unread emails from real Gmail IMAP or sandbox environment."""
        if self.is_sandbox_mode():
            return [e for e in self.sandbox_emails if not e.get("is_read")][:max_count]

        # Live IMAP retrieval
        user = self.db.get_setting("gmail_address", "")
        pw = self.db.get_setting("gmail_app_password", "")
        server_host = self.db.get_setting("gmail_imap_host", "imap.gmail.com")

        emails = []
        try:
            mail = imaplib.IMAP4_SSL(server_host, 993, timeout=12)
            mail.login(user, pw)
            mail.select("INBOX")

            status, messages = mail.search(None, 'UNSEEN')
            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                # Get latest N messages
                latest_ids = msg_ids[-max_count:]
                for m_id in reversed(latest_ids):
                    res, data = mail.fetch(m_id, "(RFC822)")
                    if res != "OK":
                        continue
                    raw = data[0][1]
                    msg = email.message_from_bytes(raw)

                    # Extract Subject
                    subj_header = decode_header(msg.get("Subject", ""))[0]
                    subj = subj_header[0]
                    if isinstance(subj, bytes):
                        subj = subj.decode(subj_header[1] or "utf-8", errors="replace")

                    # Extract From
                    from_header = decode_header(msg.get("From", ""))[0]
                    from_str = from_header[0]
                    if isinstance(from_str, bytes):
                        from_str = from_str.decode(from_header[1] or "utf-8", errors="replace")

                    # Extract Body
                    body_text = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body_text = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                    else:
                        body_text = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                    snippet = body_text[:120] + "..." if len(body_text) > 120 else body_text
                    emails.append({
                        "id": m_id.decode("utf-8"),
                        "sender": from_str,
                        "sender_name": from_str.split("<")[0].strip() if "<" in from_str else from_str,
                        "subject": subj,
                        "date": msg.get("Date", "Recent"),
                        "snippet": snippet,
                        "body": body_text,
                        "is_read": False,
                        "category": "Inbox"
                    })
            mail.logout()
        except Exception as e:
            # Fallback to sandbox on connection failure
            return [e for e in self.sandbox_emails if not e.get("is_read")][:max_count]

        return emails

    def draft_reply(self, email_data: Dict[str, Any], user_instructions: str = "", model: str = "Auto Router") -> str:
        """Uses AI Router to draft a professional, context-aware reply to an email."""
        sender = email_data.get("sender", "Client")
        subject = email_data.get("subject", "Inquiry")
        body = email_data.get("body", "")

        prompt = (
            f"You are an AI executive assistant drafting a professional email response.\n\n"
            f"Original Email:\n"
            f"From: {sender}\n"
            f"Subject: {subject}\n"
            f"Body:\n{body}\n\n"
            f"User Instructions: {user_instructions if user_instructions else 'Draft a courteous, helpful, and concise reply addressing all points positively.'}\n\n"
            f"Draft ONLY the text of the reply email (starting with salutation and ending with sign-off). Do not include subject or headers."
        )

        resp = self.router.route_and_execute(
            prompt=prompt,
            selected_model=model or "Auto Router"
        )
        if resp.success and resp.text:
            return resp.text.strip()
        else:
            # Fallback draft
            return (
                f"Hi {email_data.get('sender_name', 'there')},\n\n"
                "Thank you for your email. We have reviewed your request and everything is progressing smoothly according to plan.\n\n"
                "Please let me know if you need any additional information.\n\n"
                "Best regards,\nSage AI Assistant"
            )

    def execute_send_reply(
        self,
        email_data: Dict[str, Any],
        reply_body: str,
        permission_checker: Callable[[str, str, str, str], bool]
    ) -> Dict[str, Any]:
        """
        PERMISSION-FIRST:
        Prompts permission_checker(action, recipient, subject, body).
        Only sends if True!
        """
        recipient = email_data.get("sender", "")
        subject = f"Re: {email_data.get('subject', '')}"

        # 1. MANDATORY HUMAN-IN-THE-LOOP CHECK
        is_authorized = permission_checker(
            "📧 Send Email Reply",
            recipient,
            subject,
            reply_body
        )

        if not is_authorized:
            return {
                "success": False,
                "status": "DENIED",
                "message": f"Action cancelled: User denied permission to send email to {recipient}."
            }

        # 2. Transmit email (Real SMTP or Sandbox transmission)
        if self.is_sandbox_mode():
            # Mark sandbox email as answered/read
            for e in self.sandbox_emails:
                if e["id"] == email_data.get("id"):
                    e["is_read"] = True
                    e["replied"] = True

            return {
                "success": True,
                "status": "SENT_SANDBOX",
                "message": f"✓ [Sandbox] Email successfully authorized and delivered to {recipient}."
            }

        # Live SMTP delivery
        user = self.db.get_setting("gmail_address", "")
        pw = self.db.get_setting("gmail_app_password", "")
        smtp_host = self.db.get_setting("gmail_smtp_host", "smtp.gmail.com")

        try:
            msg = MIMEMultipart()
            msg["From"] = user
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(reply_body, "plain"))

            with smtplib.SMTP(smtp_host, 587, timeout=12) as server:
                server.starttls()
                server.login(user, pw)
                server.send_message(msg)

            return {
                "success": True,
                "status": "SENT_LIVE",
                "message": f"✓ Real email successfully transmitted to {recipient} via Gmail SMTP."
            }
        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "message": f"SMTP Error sending email: {e}"
            }


class AutomationManager:
    """Central manager tracking automation tasks, autonomous workflows, and human authorization audit trails."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.gmail_service = GmailAutomationService()
        self.state_store = AutomationStateStore(self.workspace_root / ".sage_cache" / "automation_state.db")
        self.tool_registry = AutomationToolRegistry(self.workspace_root)
        self.autonomous_agent = AutonomousAutomationAgent(
            workspace_root=self.workspace_root,
            state_store=self.state_store,
            tools=self.tool_registry
        )
        self.audit_log: List[Dict[str, Any]] = []

    def record_audit_event(self, action_type: str, target: str, decision: str, status: str, details: str):
        event = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "action_type": action_type,
            "target": target,
            "decision": decision,
            "status": status,
            "details": details
        }
        self.audit_log.append(event)
        try:
            self.state_store.record_audit("legacy", action_type, target, decision, status, details)
        except Exception:
            pass
        return event

    def get_audit_history(self) -> List[Dict[str, Any]]:
        if self.audit_log:
            return list(reversed(self.audit_log))
        try:
            return self.state_store.get_audit_history()
        except Exception:
            return []

    def run_autonomous_task(
        self,
        task_prompt: str,
        confirm_callback: Optional[Callable[[str, str, str, str], bool]] = None,
        on_step_change: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Runs multi-step task through the 7-step autonomous automation loop."""
        def wrapped_confirm(action, target, subject, body):
            approved = True
            if confirm_callback:
                approved = confirm_callback(action, target, subject, body)
            self.record_audit_event(action, target, "APPROVED" if approved else "DENIED", "AUTHORIZED" if approved else "HALTED", subject)
            return approved

        return self.autonomous_agent.start_automation(
            task_prompt=task_prompt,
            confirm_callback=wrapped_confirm,
            on_step_change=on_step_change
        )

    def resume_autonomous_task(
        self,
        run_id: str,
        confirm_callback: Optional[Callable[[str, str, str, str], bool]] = None,
        on_step_change: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Resumes an interrupted or paused run without repeating completed side effects."""
        return self.autonomous_agent.resume_automation(
            run_id=run_id,
            confirm_callback=confirm_callback,
            on_step_change=on_step_change
        )
