"""
Settings View Component for Sage AI (Lunar Engine).
In-window settings page (replaces popup dialog) providing:
- Profile & AI Persona Configuration
- Theme Select & Font Scaling
- Seamless 'Back to Chat' navigation within the same window
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QFrame, QScrollArea,
    QGridLayout, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from database.db_manager import get_db
from .analytics_view import AnalyticsView


class SettingsView(QWidget):
    """Integrated in-window settings page with Profile and Model Usage & Analytics."""

    profile_updated = Signal(str, str)
    back_to_chat_requested = Signal()
    request_add_models = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = get_db()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Bar with 'Back to Chat'
        header = QHBoxLayout()
        header.setSpacing(14)

        back_btn = QPushButton("← Back to Chat")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
                border-color: #00D1FF;
            }
        """)
        back_btn.clicked.connect(self.back_to_chat_requested.emit)
        header.addWidget(back_btn)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("⚙️ Application Settings")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 18px; font-weight: 800; letter-spacing: 0.3px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Personalize your profile, AI assistant persona, and workspace configuration")
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 11.5px;")
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()
        main_layout.addLayout(header)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("inWindowSettingsTabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #273449;
                background-color: #111827;
                border-radius: 12px;
                padding: 16px;
            }
            QTabBar::tab {
                background-color: #162033;
                color: #94A3B8;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 22px;
                margin-right: 4px;
                font-size: 12.5px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #111827;
                color: #00D1FF;
                border-color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
                font-weight: 700;
            }
        """)

        # Tab 0: Profile & Persona
        self.tabs.addTab(self._create_profile_tab(), "👤  Profile && Persona")

        # Tab 1: Model Usage & Analytics
        self.analytics_view = AnalyticsView(parent=self)
        self.analytics_view.back_to_chat_requested.connect(self.back_to_chat_requested.emit)
        self.analytics_view.request_add_models.connect(self.request_add_models.emit)
        self.tabs.addTab(self.analytics_view, "📊  Model Usage && Analytics")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs, 1)

    def _on_tab_changed(self, index: int):
        """Automatically refreshes live model token metrics when switching to Model Usage tab."""
        if index == 1 and hasattr(self, "analytics_view") and self.analytics_view:
            self.analytics_view.refresh_data()

    def refresh_usage(self):
        """Forces a refresh of model token usage and chart analytics."""
        if hasattr(self, "analytics_view") and self.analytics_view:
            self.analytics_view.refresh_data()

    # --- Profile Tab ---
    def _create_profile_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(18)

        # Avatar Preview Card
        avatar_card = QFrame()
        avatar_card.setObjectName("avatarCard")
        avatar_card.setStyleSheet("""
            QFrame#avatarCard {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        ac_layout = QHBoxLayout(avatar_card)
        ac_layout.setContentsMargins(20, 16, 20, 16)
        curr_name = self.db.get_setting("user_display_name", "")
        curr_email = self.db.get_setting("user_email", "")
        initials = "".join([part[0].upper() for part in (curr_name.strip().split() if curr_name else [])])[:2] or "U"
        self.preview_avatar = QLabel(initials)
        self.preview_avatar.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D1FF, stop:1 #008bb3);
                color: #0A0F14;
                font-weight: 900;
                font-size: 22px;
                border-radius: 30px;
                border: none;
                qproperty-alignment: AlignCenter;
            }
        """)
        self.preview_avatar.setFixedSize(60, 60)
        ac_layout.addWidget(self.preview_avatar)

        ac_info = QVBoxLayout()
        ac_info.setSpacing(4)

        self.preview_name_lbl = QLabel(curr_name or "Your Name")
        self.preview_name_lbl.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 700; border: none; background: transparent;")
        ac_info.addWidget(self.preview_name_lbl)

        self.preview_email_lbl = QLabel(curr_email or "your.email@example.com")
        self.preview_email_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; border: none; background: transparent;")
        ac_info.addWidget(self.preview_email_lbl)

        status_lbl = QLabel("● Online • SAGE AI Connected")
        status_lbl.setStyleSheet("color: #22C55E; font-size: 11px; border: none; background: transparent;")
        ac_info.addWidget(status_lbl)
        ac_layout.addLayout(ac_info, 1)

        layout.addWidget(avatar_card)

        # Form Inputs
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(16)
        form_grid.setVerticalSpacing(14)

        # Name
        name_title = QLabel("Full Display Name")
        name_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(name_title, 0, 0)

        curr_name = self.db.get_setting("user_display_name", "")
        self.name_edit = QLineEdit(curr_name)
        self.name_edit.setPlaceholderText("Enter your name")
        self.name_edit.setStyleSheet(self._input_style())
        self.name_edit.textChanged.connect(self._on_name_text_changed)
        form_grid.addWidget(self.name_edit, 1, 0)

        # Email
        email_title = QLabel("Email Address")
        email_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(email_title, 0, 1)

        curr_email = self.db.get_setting("user_email", "")
        self.email_edit = QLineEdit(curr_email)
        self.email_edit.setPlaceholderText("Enter your email")
        self.email_edit.setStyleSheet(self._input_style())
        self.email_edit.textChanged.connect(self._on_email_text_changed)
        form_grid.addWidget(self.email_edit, 1, 1)

        # Role
        role_title = QLabel("Developer Role / Bio")
        role_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(role_title, 2, 0)

        curr_role = self.db.get_setting("user_role", "")
        self.role_edit = QLineEdit(curr_role)
        self.role_edit.setPlaceholderText("e.g. Senior Software Engineer, Student")
        self.role_edit.setStyleSheet(self._input_style())
        form_grid.addWidget(self.role_edit, 3, 0)

        # AI Persona
        persona_title = QLabel("Preferred AI Assistant Persona")
        persona_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(persona_title, 2, 1)

        self.persona_combo = QComboBox()
        self.persona_combo.addItems([
            "🌟 Friendly & Simple (Easy to understand, beginner-friendly)",
            "⚡ Code Architect (Clean, optimal, typed code)",
            "💡 Smart & Concise (Short, fast, direct answers)",
            "🔬 Deep Research (Comprehensive explanations & theory)",
            "🎨 Creative Assistant (Brainstorming & exploration)"
        ])
        curr_persona = self.db.get_setting("user_persona_idx", "0")
        try:
            self.persona_combo.setCurrentIndex(int(curr_persona))
        except Exception:
            pass
        self.persona_combo.setStyleSheet(self._combo_style())
        form_grid.addWidget(self.persona_combo, 3, 1)

        layout.addLayout(form_grid)
        layout.addStretch()

        # Save Button Row
        action_row = QHBoxLayout()
        self.profile_status = QLabel("")
        self.profile_status.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        action_row.addWidget(self.profile_status)
        action_row.addStretch()

        save_btn = QPushButton("✓  Save Profile Changes")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 800;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        save_btn.clicked.connect(self._save_profile)
        action_row.addWidget(save_btn)

        layout.addLayout(action_row)

        scroll.setWidget(tab)
        return scroll

    def _on_name_text_changed(self, text: str):
        self.preview_name_lbl.setText(text or "Your Name")
        parts = text.strip().split()
        initials = "".join(p[0].upper() for p in parts[:2]) if parts else "U"
        self.preview_avatar.setText(initials)

    def _on_email_text_changed(self, text: str):
        self.preview_email_lbl.setText(text or "your.email@example.com")

    def _save_profile(self):
        name = self.name_edit.text().strip() or "User"
        email = self.email_edit.text().strip()
        role = self.role_edit.text().strip()
        persona_idx = str(self.persona_combo.currentIndex())

        self.db.set_setting("user_display_name", name)
        self.db.set_setting("user_email", email)
        self.db.set_setting("user_role", role)
        self.db.set_setting("user_persona_idx", persona_idx)

        self.profile_status.setText("✓ Profile successfully updated!")
        self.profile_updated.emit(name, email)

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #060913;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #f4f5fb;
                font-size: 13px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: #0FE6B5;
            }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #060913;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #f4f5fb;
                font-size: 12px;
                padding: 8px 12px;
            }
            QComboBox:focus {
                border-color: #0FE6B5;
            }
            QComboBox QAbstractItemView {
                background-color: #0a1120;
                color: #f4f5fb;
                selection-background-color: rgba(15, 230, 181, 0.2);
                selection-color: #0FE6B5;
                border: 1px solid rgba(15, 230, 181, 0.3);
            }
        """
