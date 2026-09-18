"""
Redesigned Sidebar Component for SAGE AI.
Features:
- Glowing Crystalline SAGE AI Logo and Branding
- "+ New Chat" Quick Action Button
- Navigation menu items (Home, Chat, Multi-Agent, Coding Agent, Automation, Projects, Knowledge, Tools, Settings, Add Models)
- Interactive Chat History section with real-time session selection, rename (✏), and delete (🗑)
- User Profile Pill with avatar, name, and settings link
- Version Footer
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QCursor


class ChatSessionItem(QFrame):
    """Interactive row representing a chat conversation in the history list."""

    session_clicked = Signal(str)
    rename_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, session_id: str, title: str, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.title = title
        self.is_active = is_active
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self._init_ui()
        self.set_active(is_active)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(6)

        icon_lbl = QLabel("💬")
        icon_lbl.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        self.title_lbl = QLabel(self.title)
        self.title_lbl.setStyleSheet("font-size: 11.5px; font-weight: 500; background: transparent; border: none;")
        self.title_lbl.setToolTip(self.title)
        layout.addWidget(self.title_lbl, 1)

        # Action buttons (Rename & Delete)
        self.rename_btn = QPushButton("✏")
        self.rename_btn.setFixedSize(20, 20)
        self.rename_btn.setCursor(Qt.PointingHandCursor)
        self.rename_btn.setToolTip("Rename conversation")
        self.rename_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748B;
                border: none;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #00D1FF;
                background-color: rgba(0, 209, 255, 0.15);
            }
        """)
        self.rename_btn.clicked.connect(lambda: self.rename_requested.emit(self.session_id))
        layout.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setToolTip("Delete conversation")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748B;
                border: none;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #FF5C77;
                background-color: rgba(255, 92, 119, 0.15);
            }
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.session_id))
        layout.addWidget(self.delete_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.session_clicked.emit(self.session_id)
        super().mousePressEvent(event)

    def set_active(self, is_active: bool):
        self.is_active = is_active
        if is_active:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10263f, stop:1 #0c1b2c);
                    border: 1px solid rgba(0, 209, 255, 0.45);
                    border-radius: 6px;
                }
            """)
            self.title_lbl.setStyleSheet("color: #00D1FF; font-size: 11.5px; font-weight: 700; background: transparent; border: none;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background-color: #111827;
                    border-color: #1f2d42;
                }
            """)
            self.title_lbl.setStyleSheet("color: #94A3B8; font-size: 11.5px; font-weight: 500; background: transparent; border: none;")

    def set_title(self, new_title: str):
        self.title = new_title
        self.title_lbl.setText(new_title)
        self.title_lbl.setToolTip(new_title)


class Sidebar(QWidget):
    """Left navigation sidebar with interactive chat history and navigation items."""

    new_chat_requested = Signal()
    nav_changed = Signal(str)  # 'home', 'chat', 'multi_agent', 'image_gen', 'coding_agent', 'automations', 'knowledge', 'settings', 'api_keys'
    profile_clicked = Signal()
    chat_session_selected = Signal(str)
    chat_session_deleted = Signal(str)
    chat_session_renamed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(260)
        self._active_nav = "home"
        self._active_session_id: Optional[str] = None
        self._nav_buttons: Dict[str, QPushButton] = {}
        self._session_items: Dict[str, ChatSessionItem] = {}

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 18, 14, 14)
        main_layout.setSpacing(10)

        # 1. Top Brand Logo & Title
        brand_box = QVBoxLayout()
        brand_box.setAlignment(Qt.AlignCenter)
        brand_box.setSpacing(4)

        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
        self.logo_lbl = QLabel()
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_lbl.setPixmap(pix)
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        self.logo_lbl.setStyleSheet("background: transparent;")
        brand_box.addWidget(self.logo_lbl)

        brand_text = QLabel("SAGE AI")
        brand_text.setAlignment(Qt.AlignCenter)
        brand_text.setStyleSheet("color: #F8FAFC; font-size: 14px; font-weight: 800; letter-spacing: 2px; background: transparent;")
        brand_box.addWidget(brand_text)

        main_layout.addLayout(brand_box)

        # 2. "+ New Chat" Action Button
        self.new_chat_btn = QPushButton("＋  New Chat")
        self.new_chat_btn.setCursor(Qt.PointingHandCursor)
        self.new_chat_btn.setFixedHeight(36)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f2d4a, stop:1 #0a1f33);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.45);
                border-radius: 8px;
                font-size: 12.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #143d63, stop:1 #0f2c47);
                border-color: #00D1FF;
                color: #ffffff;
            }
        """)
        self.new_chat_btn.clicked.connect(self._on_new_chat_clicked)
        main_layout.addWidget(self.new_chat_btn)

        # 3. Scrollable Navigation Menu & Chat History
        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 209, 255, 0.2);
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00D1FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        self.nav_layout = QVBoxLayout(nav_container)
        self.nav_layout.setContentsMargins(0, 2, 0, 2)
        self.nav_layout.setSpacing(3)

        nav_items = [
            ("home", "🏠  Home"),
            ("chat", "💬  Chat"),
            ("multi_agent", "🤖  Multi-Agent Hub"),
            ("coding_agent", "</>  Coding Agent"),
            ("automations", "⚡  Automation"),
            ("knowledge", "📖  Knowledge Base"),
            ("settings", "⚙  Settings"),
            ("api_keys", "✨  Add Models"),
        ]

        for key, text in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("sidebarNavBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda checked, k=key: self._handle_nav(k))
            self._nav_buttons[key] = btn
            self.nav_layout.addWidget(btn)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #1a2538; max-height: 1px; margin-top: 6px; margin-bottom: 4px;")
        self.nav_layout.addWidget(sep)

        # 4. Chat History Section
        history_header_row = QHBoxLayout()
        history_header_row.setContentsMargins(6, 4, 6, 2)
        
        hist_title = QLabel("Recent Chats")
        hist_title.setStyleSheet("color: #64748B; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; background: transparent;")
        history_header_row.addWidget(hist_title)
        history_header_row.addStretch()

        self.hist_count_lbl = QLabel("0")
        self.hist_count_lbl.setStyleSheet("color: #00D1FF; font-size: 9.5px; font-weight: 700; background: rgba(0, 209, 255, 0.12); padding: 1px 6px; border-radius: 4px;")
        history_header_row.addWidget(self.hist_count_lbl)
        self.nav_layout.addLayout(history_header_row)

        # Container for chat history items
        self.sessions_container = QWidget()
        self.sessions_container.setStyleSheet("background: transparent;")
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setContentsMargins(0, 0, 0, 0)
        self.sessions_layout.setSpacing(2)

        self.empty_history_lbl = QLabel("No past chats yet")
        self.empty_history_lbl.setStyleSheet("color: #475569; font-size: 11px; font-style: italic; padding: 6px 8px; background: transparent;")
        self.sessions_layout.addWidget(self.empty_history_lbl)

        self.nav_layout.addWidget(self.sessions_container)
        self.nav_layout.addStretch(1)

        self.nav_scroll.setWidget(nav_container)
        main_layout.addWidget(self.nav_scroll, 1)

        # 5. User Profile Pill
        profile_pill = QFrame()
        profile_pill.setCursor(Qt.PointingHandCursor)
        profile_pill.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #00D1FF;
                background-color: #162033;
            }
        """)
        p_layout = QHBoxLayout(profile_pill)
        p_layout.setContentsMargins(10, 8, 10, 8)
        p_layout.setSpacing(10)

        self.avatar_lbl = QLabel("SS")
        self.avatar_lbl.setFixedSize(36, 36)
        self.avatar_lbl.setAlignment(Qt.AlignCenter)
        self.avatar_lbl.setStyleSheet("""
            QLabel {
                background-color: #00D1FF;
                color: #0A0F14;
                font-weight: 800;
                font-size: 13px;
                border-radius: 18px;
                border: none;
            }
        """)
        p_layout.addWidget(self.avatar_lbl)

        user_info = QVBoxLayout()
        user_info.setSpacing(1)
        self.name_lbl = QLabel("User")
        self.name_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        user_info.addWidget(self.name_lbl)

        self.email_lbl = QLabel("user@local")
        self.email_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; background: transparent; border: none;")
        user_info.addWidget(self.email_lbl)
        p_layout.addLayout(user_info, 1)

        dots_btn = QLabel("⋮")
        dots_btn.setStyleSheet("color: #94A3B8; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        p_layout.addWidget(dots_btn)

        profile_pill.mousePressEvent = lambda e: self.profile_clicked.emit()
        main_layout.addWidget(profile_pill)

        # 6. Bottom Version Footer
        footer_row = QHBoxLayout()
        v_lbl = QLabel("SAGE AI v1.0.0")
        v_lbl.setStyleSheet("color: #475569; font-size: 10px; font-weight: 600; background: transparent;")
        footer_row.addWidget(v_lbl)
        main_layout.addLayout(footer_row)

        # Set default active
        self._apply_nav_styles("home")

    def _apply_nav_styles(self, active_key: str):
        for key, btn in self._nav_buttons.items():
            is_active = (key == active_key)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f2744, stop:1 #0b1f36);
                        color: #00D1FF;
                        border: 1px solid rgba(0, 209, 255, 0.4);
                        border-radius: 8px;
                        font-size: 12.5px;
                        font-weight: 700;
                        padding-left: 14px;
                        text-align: left;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #94A3B8;
                        border: none;
                        border-radius: 8px;
                        font-size: 12.5px;
                        font-weight: 600;
                        padding-left: 14px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #111827;
                        color: #F8FAFC;
                    }
                """)

    def _handle_nav(self, nav_name: str):
        self._active_nav = nav_name
        self._apply_nav_styles(nav_name)
        self.nav_changed.emit(nav_name)

    def set_active_nav(self, nav_name: str):
        self._active_nav = nav_name
        self._apply_nav_styles(nav_name)

    def _on_new_chat_clicked(self):
        self.new_chat_requested.emit()

    # --- Chat History Management ---

    def load_sessions(self, sessions: List[Dict[str, Any]], active_id: Optional[str] = None):
        """Populates the sidebar chat history list from stored database sessions."""
        if active_id is not None:
            self._active_session_id = active_id
        # Clear existing
        for item in self._session_items.values():
            item.deleteLater()
        self._session_items.clear()

        if not sessions:
            self.empty_history_lbl.setVisible(True)
            self.hist_count_lbl.setText("0")
            return

        self.empty_history_lbl.setVisible(False)
        self.hist_count_lbl.setText(str(len(sessions)))

        for s in sessions:
            s_id = s["id"]
            title = s.get("title", "Untitled Chat")
            self._create_session_item(s_id, title)

        if self._active_session_id and self._active_session_id in self._session_items:
            self._session_items[self._active_session_id].set_active(True)

    def add_session(self, session_id: str, title: str):
        """Adds a newly created chat session to the top of the history list."""
        self.empty_history_lbl.setVisible(False)
        if session_id in self._session_items:
            self._session_items[session_id].set_title(title)
            return

        item = self._create_session_item(session_id, title, insert_at_top=True)
        self.hist_count_lbl.setText(str(len(self._session_items)))
        self.set_active_session(session_id)

    def remove_session(self, session_id: str):
        """Removes a deleted session from the list."""
        if session_id in self._session_items:
            item = self._session_items.pop(session_id)
            item.deleteLater()

        count = len(self._session_items)
        self.hist_count_lbl.setText(str(count))
        if count == 0:
            self.empty_history_lbl.setVisible(True)

    def set_active_session(self, session_id: str):
        """Highlights the active session card and deactivates others."""
        self._active_session_id = session_id
        for sid, item in self._session_items.items():
            item.set_active(sid == session_id)

    def update_session_title(self, session_id: str, title: str):
        """Updates the displayed title of an existing session item."""
        if session_id in self._session_items:
            self._session_items[session_id].set_title(title)

    def _create_session_item(self, session_id: str, title: str, insert_at_top: bool = False) -> ChatSessionItem:
        item = ChatSessionItem(session_id, title, is_active=(session_id == self._active_session_id), parent=self.sessions_container)
        item.session_clicked.connect(self._on_session_clicked)
        item.rename_requested.connect(self._on_rename_session)
        item.delete_requested.connect(self._on_delete_session)

        if insert_at_top:
            self.sessions_layout.insertWidget(0, item)
        else:
            self.sessions_layout.addWidget(item)

        self._session_items[session_id] = item
        return item

    def _on_session_clicked(self, session_id: str):
        self.set_active_session(session_id)
        self.chat_session_selected.emit(session_id)

    def _on_rename_session(self, session_id: str):
        item = self._session_items.get(session_id)
        curr_title = item.title if item else "Chat"
        new_title, ok = QInputDialog.getText(self, "Rename Chat", "Enter new chat title:", text=curr_title)
        if ok and new_title.strip():
            self.update_session_title(session_id, new_title.strip())
            self.chat_session_renamed.emit(session_id, new_title.strip())

    def _on_delete_session(self, session_id: str):
        item = self._session_items.get(session_id)
        title = item.title if item else "this conversation"
        reply = QMessageBox.question(
            self,
            "Delete Chat",
            f"Are you sure you want to delete '{title}'?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.chat_session_deleted.emit(session_id)

    def update_profile(self, name: str, email: str, initials: Optional[str] = None):
        """Dynamically updates the profile pill displayed at bottom of sidebar."""
        if hasattr(self, "name_lbl"):
            self.name_lbl.setText(name)
        if hasattr(self, "email_lbl"):
            self.email_lbl.setText(email)
        if hasattr(self, "avatar_lbl"):
            init = initials
            if not init:
                parts = name.strip().split()
                init = "".join(p[0].upper() for p in parts[:2]) if parts else "U"
            self.avatar_lbl.setText(init)

    def update_theme(self, pal: Dict[str, Any]):
        """No-op for single locked theme, maintains compatibility."""
        pass
