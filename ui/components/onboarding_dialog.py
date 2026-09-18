"""
First-Launch Onboarding & Personalization Dialog for Sage AI.
Prompts new users on first launch for:
- Full Name (empty by default, no pre-filled inputs)
- Email Address (empty by default)
- Role / Profession (empty by default)
- Preferred AI Persona
- Workspace Theme
Saves preferences into SQLite database and marks onboarding as completed.
"""
from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QColor

from database.db_manager import get_db


class FirstLaunchOnboardingDialog(QDialog):
    """Modern dark-themed setup modal displayed when Sage AI runs on a new computer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Sage AI • Initial Setup")
        self.resize(520, 580)
        self.setMinimumWidth(480)
        self.setModal(True)
        self.db = get_db()

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #080b16;
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QLabel {
                color: #f8fafc;
            }
            QLineEdit {
                background-color: #0d1527;
                border: 1.5px solid #273449;
                border-radius: 8px;
                color: #f8fafc;
                padding: 9px 12px;
                font-size: 12.5px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
                background-color: #111b33;
            }
            QComboBox {
                background-color: #0d1527;
                border: 1.5px solid #273449;
                border-radius: 8px;
                color: #f8fafc;
                padding: 8px 12px;
                font-size: 12px;
            }
            QComboBox:focus {
                border-color: #00D1FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1527;
                color: #f8fafc;
                border: 1px solid #273449;
                selection-background-color: #1a2744;
                selection-color: #00D1FF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 26)
        layout.setSpacing(14)

        # 1. Header with Logo & Welcome text
        header_box = QVBoxLayout()
        header_box.setSpacing(6)
        header_box.setAlignment(Qt.AlignCenter)

        logo_lbl = QLabel()
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("⚡")
            logo_lbl.setStyleSheet("font-size: 32px; color: #00D1FF;")
        logo_lbl.setAlignment(Qt.AlignCenter)
        header_box.addWidget(logo_lbl)

        welcome_title = QLabel("Welcome to Sage AI")
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #f8fafc; letter-spacing: 0.3px;")
        header_box.addWidget(welcome_title)

        welcome_sub = QLabel("Let's personalize your workspace. Please enter your profile details:")
        welcome_sub.setAlignment(Qt.AlignCenter)
        welcome_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_box.addWidget(welcome_sub)

        layout.addLayout(header_box)

        # Subtle separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.08); margin: 4px 0;")
        layout.addWidget(sep)

        # 2. Form Fields (All empty by default — no pre-filled inputs)
        form_box = QVBoxLayout()
        form_box.setSpacing(10)

        # Name
        name_hdr = QLabel("Your Full Name <span style='color: #00D1FF;'>*</span>")
        name_hdr.setTextFormat(Qt.RichText)
        name_hdr.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cbd5e1;")
        form_box.addWidget(name_hdr)

        self.name_input = QLineEdit()
        self.name_input.setText("")  # Explicitly empty
        self.name_input.setPlaceholderText("Enter your name (e.g. Alex Rivers)")
        form_box.addWidget(self.name_input)

        self.name_warn_lbl = QLabel("⚠️ Please enter your name to continue.")
        self.name_warn_lbl.setStyleSheet("color: #FF5C77; font-size: 11px; font-weight: 600;")
        self.name_warn_lbl.setVisible(False)
        form_box.addWidget(self.name_warn_lbl)

        # Email
        email_hdr = QLabel("Email Address")
        email_hdr.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cbd5e1;")
        form_box.addWidget(email_hdr)

        self.email_input = QLineEdit()
        self.email_input.setText("")  # Explicitly empty
        self.email_input.setPlaceholderText("Enter your email (e.g. alex@example.com)")
        form_box.addWidget(self.email_input)

        # Role / Profession
        role_hdr = QLabel("Role / Profession")
        role_hdr.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cbd5e1;")
        form_box.addWidget(role_hdr)

        self.role_input = QLineEdit()
        self.role_input.setText("")  # Explicitly empty
        self.role_input.setPlaceholderText("e.g. Software Engineer, Student, Data Scientist, Designer")
        form_box.addWidget(self.role_input)

        # Row: AI Persona + Theme
        prefs_row = QHBoxLayout()
        prefs_row.setSpacing(10)

        # AI Persona
        p_col = QVBoxLayout()
        p_col.setSpacing(4)
        persona_hdr = QLabel("Preferred AI Persona")
        persona_hdr.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #cbd5e1;")
        p_col.addWidget(persona_hdr)

        self.persona_combo = QComboBox()
        self.persona_combo.addItem("Expert AI Assistant (Balanced)")
        self.persona_combo.addItem("Senior Software Architect (Technical)")
        self.persona_combo.addItem("Concise & Direct (Speed & Code)")
        self.persona_combo.addItem("Creative Thinker (Ideation)")
        p_col.addWidget(self.persona_combo)
        prefs_row.addLayout(p_col, 1)

        form_box.addLayout(prefs_row)
        layout.addLayout(form_box)

        layout.addStretch()

        # 3. Action Buttons
        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        self.start_btn = QPushButton("🚀 Complete Setup & Launch Sage AI")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D1FF, stop:1 #0FE6B5);
                color: #080b16;
                border: none;
                border-radius: 9px;
                padding: 12px 20px;
                font-size: 13.5px;
                font-weight: 800;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1ae0ff, stop:1 #28f7c6);
            }
        """)
        self.start_btn.clicked.connect(self._save_and_launch)
        btn_box.addWidget(self.start_btn)

        layout.addLayout(btn_box)

    def _save_and_launch(self):
        name = self.name_input.text().strip()
        if not name:
            self.name_warn_lbl.setVisible(True)
            self.name_input.setStyleSheet("""
                background-color: #1a0f16;
                border: 1.5px solid #FF5C77;
                border-radius: 8px;
                color: #f8fafc;
                padding: 9px 12px;
                font-size: 12.5px;
            """)
            self.name_input.setFocus()
            return

        email = self.email_input.text().strip()
        role = self.role_input.text().strip()
        persona_idx = self.persona_combo.currentIndex()

        # Save to database
        self.db.set_setting("user_display_name", name)
        self.db.set_setting("user_email", email)
        self.db.set_setting("user_role", role)
        self.db.set_setting("user_persona_idx", str(persona_idx))
        self.db.set_setting("onboarding_completed", "true")

        self.accept()
