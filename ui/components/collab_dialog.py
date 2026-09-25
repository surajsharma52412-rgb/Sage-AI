"""
Live Collaboration Dialog for Sage AI.
Allows users to host or join real-time collaborative coding sessions in the IDE.
"""
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTabWidget, QWidget, QTextEdit, QListWidget,
    QListWidgetItem, QMessageBox, QApplication, QRadioButton,
    QButtonGroup, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor

from engine.collab_service import CollabManager, get_local_ip, generate_room_code


class CollabPanelWidget(QWidget):
    """Modern Cyberpunk Dark Emerald Widget for Hosting and Joining Collaborative Coding Sessions in the same window."""

    close_requested = Signal()

    def __init__(self, manager: CollabManager, default_user_name: str = "Developer", parent=None):
        super().__init__(parent)
        self.manager = manager
        self.default_user_name = default_user_name

        self._init_ui()
        self._wire_signals()
        self._refresh_state()

    def _init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #080b16;
                color: #f4f5fb;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QLabel {
                color: #f4f5fb;
            }
            QLineEdit {
                background-color: #0A0F14;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 6px;
                color: #f4f5fb;
                padding: 7px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
            QTabWidget::pane {
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 8px;
                background-color: #0c1220;
                padding: 12px;
            }
            QTabBar::tab {
                background: #090e1a;
                color: #8fa0b5;
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #0c1220;
                color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
            }
            QTabBar::tab:hover {
                color: #00D1FF;
            }
            QListWidget {
                background-color: #0A0F14;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px;
                color: #e2e8f0;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #0e1a2e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Title
        hdr_row = QHBoxLayout()
        icon_lbl = QLabel("👥")
        icon_lbl.setStyleSheet("font-size: 22px;")
        hdr_row.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Live Collaborative Coding & Multi-File Pairing")
        title_lbl.setStyleSheet("color: #f4f5fb; font-size: 16px; font-weight: 700;")
        title_col.addWidget(title_lbl)

        sub_lbl = QLabel("Bidirectional pair programming with simultaneous multi-file editing over LAN / IP")
        sub_lbl.setStyleSheet("color: #626c85; font-size: 11px;")
        title_col.addWidget(sub_lbl)
        hdr_row.addLayout(title_col)
        hdr_row.addStretch()

        layout.addLayout(hdr_row)

        # Tabs: Host Session / Join Session
        self.tabs = QTabWidget()

        # --- Tab 1: Host ---
        host_tab = QWidget()
        host_layout = QVBoxLayout(host_tab)
        host_layout.setSpacing(10)
        # Mode Selection: Worldwide Internet vs Local LAN
        mode_box = QVBoxLayout()
        mode_box.setSpacing(4)
        mode_lbl = QLabel("NETWORK MODE")
        mode_lbl.setStyleSheet("color: #8fa0c0; font-size: 10px; font-weight: 700; letter-spacing: 0.6px;")
        mode_box.addWidget(mode_lbl)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)

        self.mode_cloud_radio = QRadioButton("🌐 Worldwide (Cloud Relay)")
        self.mode_cloud_radio.setChecked(True)
        self.mode_cloud_radio.setCursor(Qt.PointingHandCursor)
        self.mode_cloud_radio.setToolTip("Collaborate across different Wi-Fi networks, home, or office with a shareable Room Code!")
        self.mode_cloud_radio.setStyleSheet("color: #00D1FF; font-weight: 700; font-size: 11px;")
        self.mode_cloud_radio.toggled.connect(self._on_host_mode_changed)
        mode_row.addWidget(self.mode_cloud_radio)

        self.mode_lan_radio = QRadioButton("🏠 Local (LAN)")
        self.mode_lan_radio.setCursor(Qt.PointingHandCursor)
        self.mode_lan_radio.setToolTip("Direct TCP socket on the same local Wi-Fi or LAN.")
        self.mode_lan_radio.setStyleSheet("color: #a0aec0; font-size: 11px;")
        mode_row.addWidget(self.mode_lan_radio)
        mode_row.addStretch()
        mode_box.addLayout(mode_row)
        host_layout.addLayout(mode_box)

        # Cloud Mode Info Banner
        self.cloud_banner = QFrame()
        self.cloud_banner.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 209, 255, 0.08);
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        cb_layout = QHBoxLayout(self.cloud_banner)
        cb_layout.setContentsMargins(6, 4, 6, 4)
        cb_icon = QLabel("✨")
        cb_layout.addWidget(cb_icon)
        cb_text = QLabel("No same Wi-Fi needed! Share the Room Code with anyone worldwide.")
        cb_text.setWordWrap(True)
        cb_text.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600;")
        cb_layout.addWidget(cb_text, 1)
        host_layout.addWidget(self.cloud_banner)

        # LAN IP & Port (Visible only in LAN mode)
        self.lan_settings_widget = QWidget()
        lan_layout = QHBoxLayout(self.lan_settings_widget)
        lan_layout.setContentsMargins(0, 0, 0, 0)
        lan_layout.setSpacing(8)

        local_ip = get_local_ip()
        ip_lbl = QLabel("Your LAN IP:")
        ip_lbl.setStyleSheet("color: #a0aec0; font-size: 11px; min-width: 90px;")
        lan_layout.addWidget(ip_lbl)

        self.host_ip_display = QLineEdit(local_ip)
        self.host_ip_display.setReadOnly(True)
        self.host_ip_display.setStyleSheet("background-color: #070d1a; color: #00D1FF; font-weight: bold;")
        lan_layout.addWidget(self.host_ip_display, 1)

        port_lbl = QLabel("Port:")
        port_lbl.setStyleSheet("color: #a0aec0; font-size: 11px;")
        lan_layout.addWidget(port_lbl)

        self.host_port_input = QLineEdit("8989")
        self.host_port_input.setFixedWidth(65)
        lan_layout.addWidget(self.host_port_input)
        host_layout.addWidget(self.lan_settings_widget)
        self.lan_settings_widget.setVisible(False)

        # Host Name
        name_row = QHBoxLayout()
        name_lbl = QLabel("Your Nickname:")
        name_lbl.setStyleSheet("color: #a0aec0; font-size: 11px; min-width: 90px;")
        name_row.addWidget(name_lbl)

        self.host_name_input = QLineEdit(self.default_user_name)
        name_row.addWidget(self.host_name_input, 1)
        host_layout.addLayout(name_row)

        # Host Button
        self.host_action_btn = QPushButton("▶ Start Worldwide Live Session")
        self.host_action_btn.setCursor(Qt.PointingHandCursor)
        self.host_action_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #00D1FF, stop: 1 #0CC99D);
                color: #080b16;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #3bfdd5;
            }
        """)
        self.host_action_btn.clicked.connect(self._toggle_host)
        host_layout.addWidget(self.host_action_btn)

        # Share Code Box (Dedicated card with ample room for code and clear buttons)
        self.share_card = QFrame()
        self.share_card.setObjectName("shareCard")
        self.share_card.setStyleSheet("""
            QFrame#shareCard {
                background-color: #0c1424;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 8px;
            }
        """)
        share_layout = QVBoxLayout(self.share_card)
        share_layout.setContentsMargins(10, 8, 10, 8)
        share_layout.setSpacing(6)

        hdr_row = QHBoxLayout()
        self.room_code_label = QLabel("ROOM CODE (SHARE TO COLLABORATE)")
        self.room_code_label.setStyleSheet("color: #8fa0c0; font-size: 10px; font-weight: 700; letter-spacing: 0.6px;")
        hdr_row.addWidget(self.room_code_label)
        hdr_row.addStretch()

        self.copy_feedback_lbl = QLabel("")
        self.copy_feedback_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 700;")
        hdr_row.addWidget(self.copy_feedback_lbl)
        share_layout.addLayout(hdr_row)

        code_row = QHBoxLayout()
        code_row.setSpacing(6)

        self.room_code_display = QLineEdit(generate_room_code())
        self.room_code_display.setReadOnly(True)
        self.room_code_display.setAlignment(Qt.AlignCenter)
        self.room_code_display.setFixedHeight(34)
        self.room_code_display.setStyleSheet("""
            QLineEdit {
                background-color: #050a14;
                color: #00D1FF;
                border: 1.5px solid rgba(0, 209, 255, 0.5);
                border-radius: 6px;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 1.2px;
                padding: 4px 8px;
            }
        """)
        code_row.addWidget(self.room_code_display, 1)

        self.gen_code_btn = QPushButton("🔀 New")
        self.gen_code_btn.setCursor(Qt.PointingHandCursor)
        self.gen_code_btn.setToolTip("Generate a new Room Code")
        self.gen_code_btn.setFixedHeight(34)
        self.gen_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #cbd5e1;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: #00D1FF;
                background-color: rgba(0, 209, 255, 0.12);
            }
        """)
        self.gen_code_btn.clicked.connect(self._generate_new_room_code)
        code_row.addWidget(self.gen_code_btn)

        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setToolTip("Copy Room Code to clipboard")
        self.copy_btn.setFixedHeight(34)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #041018;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #3bfdd5;
            }
        """)
        self.copy_btn.clicked.connect(self._copy_room_code)
        code_row.addWidget(self.copy_btn)

        share_layout.addLayout(code_row)
        host_layout.addWidget(self.share_card)

        # Connected Peers List
        peers_row = QHBoxLayout()
        peers_lbl = QLabel("Connected Collaborators:")
        peers_lbl.setStyleSheet("color: #8fa0b5; font-size: 11px; font-weight: 600; margin-top: 4px;")
        peers_row.addWidget(peers_lbl)
        peers_row.addStretch()

        self.host_files_lbl = QLabel("📁 0 Files in Room")
        self.host_files_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600;")
        peers_row.addWidget(self.host_files_lbl)
        host_layout.addLayout(peers_row)

        self.host_peers_list = QListWidget()
        self.host_peers_list.setFixedHeight(85)
        host_layout.addWidget(self.host_peers_list)

        self.tabs.addTab(host_tab, "🌐 Host Session")

        # --- Tab 2: Join ---
        join_tab = QWidget()
        join_layout = QVBoxLayout(join_tab)
        join_layout.setSpacing(10)

        addr_row = QHBoxLayout()
        addr_lbl = QLabel("Room Code / IP:")
        addr_lbl.setStyleSheet("color: #a0aec0; font-size: 11px; min-width: 90px; font-weight: 600;")
        addr_row.addWidget(addr_lbl)

        self.join_addr_input = QLineEdit()
        self.join_addr_input.setPlaceholderText("Enter Room Code (e.g. SAGE-4829) or IP:port (e.g. 192.168.1.5:8989)")
        addr_row.addWidget(self.join_addr_input, 1)
        join_layout.addLayout(addr_row)

        join_name_row = QHBoxLayout()
        j_name_lbl = QLabel("Your Nickname:")
        j_name_lbl.setStyleSheet("color: #a0aec0; font-size: 11px; min-width: 90px;")
        join_name_row.addWidget(j_name_lbl)

        self.join_name_input = QLineEdit(self.default_user_name)
        join_name_row.addWidget(self.join_name_input, 1)
        join_layout.addLayout(join_name_row)

        self.join_action_btn = QPushButton("🔗 Connect to Session")
        self.join_action_btn.setCursor(Qt.PointingHandCursor)
        self.join_action_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #00D1FF, stop: 1 #0CC99D);
                color: #080b16;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #3bfdd5;
            }
        """)
        self.join_action_btn.clicked.connect(self._toggle_join)
        join_layout.addWidget(self.join_action_btn)

        join_peers_row = QHBoxLayout()
        join_peers_lbl = QLabel("Session Members:")
        join_peers_lbl.setStyleSheet("color: #8fa0b5; font-size: 11px; font-weight: 600; margin-top: 4px;")
        join_peers_row.addWidget(join_peers_lbl)
        join_peers_row.addStretch()

        self.join_files_lbl = QLabel("📁 0 Files in Room")
        self.join_files_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600;")
        join_peers_row.addWidget(self.join_files_lbl)
        join_layout.addLayout(join_peers_row)

        self.join_peers_list = QListWidget()
        self.join_peers_list.setFixedHeight(115)
        join_layout.addWidget(self.join_peers_list)

        self.tabs.addTab(join_tab, "🔗 Join Session")
        layout.addWidget(self.tabs)

        # Event Log Window
        log_lbl = QLabel("ACTIVITY & SYNC LOG")
        log_lbl.setStyleSheet("color: #626c85; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
        layout.addWidget(log_lbl)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(85)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #040711;
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 6px;
                color: #8fa0b5;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.log_view)

        # Footer row with status badge & close button
        footer_row = QHBoxLayout()
        self.status_badge = QLabel("⚪ Offline")
        self.status_badge.setStyleSheet("color: #626c85; font-size: 12px; font-weight: 600;")
        footer_row.addWidget(self.status_badge)

        footer_row.addStretch()

        close_btn = QPushButton("Done")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #a0a8be;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        close_btn.clicked.connect(self.accept)
        footer_row.addWidget(close_btn)

        layout.addLayout(footer_row)

    def _wire_signals(self):
        self.manager.status_changed.connect(self._on_status_changed)
        self.manager.peer_list_updated.connect(self._on_peers_updated)
        self.manager.files_list_updated.connect(self._on_files_updated)
        self.manager.log_emitted.connect(self._on_log)

    def _disconnect_signals(self):
        if getattr(self, "_signals_disconnected", False):
            return
        self._signals_disconnected = True
        try:
            self.manager.status_changed.disconnect(self._on_status_changed)
        except Exception:
            pass
        try:
            self.manager.peer_list_updated.disconnect(self._on_peers_updated)
        except Exception:
            pass
        try:
            self.manager.files_list_updated.disconnect(self._on_files_updated)
        except Exception:
            pass
        try:
            self.manager.log_emitted.disconnect(self._on_log)
        except Exception:
            pass

    def accept(self):
        self._disconnect_signals()
        self.close_requested.emit()
        parent = self.parent()
        if hasattr(parent, "accept") and callable(parent.accept):
            parent.accept()
        elif hasattr(parent, "close") and callable(parent.close):
            parent.close()
        else:
            self.hide()

    def reject(self):
        self._disconnect_signals()
        self.close_requested.emit()
        parent = self.parent()
        if hasattr(parent, "reject") and callable(parent.reject):
            parent.reject()
        elif hasattr(parent, "close") and callable(parent.close):
            parent.close()
        else:
            self.hide()

    def done(self, r=0):
        self._disconnect_signals()
        self.close_requested.emit()
        parent = self.parent()
        if hasattr(parent, "done") and callable(parent.done):
            parent.done(r)
        elif hasattr(parent, "close") and callable(parent.close):
            parent.close()
        else:
            self.hide()

    def closeEvent(self, event):
        self._disconnect_signals()
        self.close_requested.emit()
        super().closeEvent(event)

    def _on_host_mode_changed(self):
        is_cloud = self.mode_cloud_radio.isChecked()
        self.cloud_banner.setVisible(is_cloud)
        self.lan_settings_widget.setVisible(not is_cloud)
        self.gen_code_btn.setVisible(is_cloud)
        if not self.manager.is_active:
            if is_cloud:
                if not self.room_code_display.text().strip().startswith("SAGE-"):
                    self.room_code_display.setText(generate_room_code())
                self.host_action_btn.setText("▶ Start Worldwide Live Session")
            else:
                local_ip = get_local_ip()
                port = self.host_port_input.text().strip() or "8989"
                self.room_code_display.setText(f"{local_ip}:{port}")
                self.host_action_btn.setText("▶ Start Local LAN Session")

    def _generate_new_room_code(self):
        self.room_code_display.setText(generate_room_code())

    def _refresh_state(self):
        is_active = self.manager.is_active
        role = self.manager.role
        mode = getattr(self.manager, "connection_mode", "cloud")

        if is_active and role == "host":
            self.tabs.setCurrentIndex(0)
            self.host_action_btn.setText("⏹ Stop Hosting Session")
            self.host_action_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(244, 63, 94, 0.18);
                    color: #f43f5e;
                    border: 1px solid #f43f5e;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(244, 63, 94, 0.3);
                }
            """)
            self.mode_cloud_radio.setEnabled(False)
            self.mode_lan_radio.setEnabled(False)
            self.gen_code_btn.setEnabled(False)
            self.host_port_input.setEnabled(False)
            self.host_name_input.setEnabled(False)
            mode_desc = "Worldwide Cloud" if mode == "cloud" else "Local LAN"
            self.status_badge.setText(f"🟢 Hosting ({mode_desc})")
            self.status_badge.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 700;")
            if self.manager.room_code:
                self.room_code_display.setText(self.manager.room_code)
        elif is_active and role == "client":
            self.tabs.setCurrentIndex(1)
            self.join_action_btn.setText("🔌 Disconnect from Session")
            self.join_action_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(244, 63, 94, 0.18);
                    color: #f43f5e;
                    border: 1px solid #f43f5e;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(244, 63, 94, 0.3);
                }
            """)
            self.join_addr_input.setEnabled(False)
            self.join_name_input.setEnabled(False)
            mode_desc = "Worldwide Cloud" if mode == "cloud" else "Local LAN"
            self.status_badge.setText(f"🟢 Connected ({mode_desc})")
            self.status_badge.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 700;")
        else:
            is_cloud = self.mode_cloud_radio.isChecked()
            self.host_action_btn.setText("▶ Start Worldwide Live Session" if is_cloud else "▶ Start Local LAN Session")
            self.host_action_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #00D1FF, stop: 1 #0CC99D);
                    color: #080b16;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 700;
                }
                QPushButton:hover { background: #3bfdd5; }
            """)
            self.join_action_btn.setText("🔗 Connect to Session")
            self.join_action_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #00D1FF, stop: 1 #0CC99D);
                    color: #080b16;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 700;
                }
                QPushButton:hover { background: #3bfdd5; }
            """)
            self.mode_cloud_radio.setEnabled(True)
            self.mode_lan_radio.setEnabled(True)
            self.gen_code_btn.setEnabled(True)
            self.host_port_input.setEnabled(True)
            self.host_name_input.setEnabled(True)
            self.join_addr_input.setEnabled(True)
            self.join_name_input.setEnabled(True)
            self.status_badge.setText("⚪ Offline")
            self.status_badge.setStyleSheet("color: #626c85; font-size: 12px; font-weight: 600;")
            self._on_host_mode_changed()

        self._on_peers_updated(self.manager.active_peers)
        self._on_files_updated(list(self.manager.shared_files.keys()))

    def _toggle_host(self):
        if self.manager.is_active and self.manager.role == "host":
            self.manager.stop()
            self._refresh_state()
            return

        host_name = self.host_name_input.text().strip() or "Host"
        # Pull all open documents from parent IDE if available
        parent_ide = self.parent()
        initial_files: Dict[str, dict] = {}
        if parent_ide and hasattr(parent_ide, "get_all_open_documents"):
            initial_files = parent_ide.get_all_open_documents()
        elif parent_ide and hasattr(parent_ide, "editor") and hasattr(parent_ide, "active_file"):
            f_name = parent_ide.active_file.name if parent_ide.active_file else "untitled.py"
            initial_files = {
                f_name: {
                    "filename": f_name,
                    "language": getattr(parent_ide.editor, "language", "Python"),
                    "content": parent_ide.editor.toPlainText()
                }
            }

        if self.mode_cloud_radio.isChecked():
            code = self.room_code_display.text().strip() or generate_room_code()
            assigned_code = self.manager.start_hosting_cloud(
                room_code=code,
                host_name=host_name,
                initial_files=initial_files
            )
            if assigned_code:
                self.room_code_display.setText(assigned_code)
            else:
                QMessageBox.critical(self, "Cloud Host Error", "Could not connect to Worldwide Cloud Relay.\nPlease check internet connectivity.")
        else:
            port_str = self.host_port_input.text().strip()
            try:
                port = int(port_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Port", "Please enter a valid numeric port (e.g. 8989).")
                return

            ok = self.manager.start_hosting(port=port, host_name=host_name, initial_files=initial_files)
            if ok:
                local_ip = get_local_ip()
                active_port = self.manager.server.port if self.manager.server else port
                self.room_code_display.setText(f"{local_ip}:{active_port}")
            else:
                QMessageBox.critical(self, "Host Error", f"Could not bind to port {port}. It may be in use.")

        self._refresh_state()

    def _toggle_join(self):
        if self.manager.is_active and self.manager.role == "client":
            self.manager.stop()
            self._refresh_state()
            return

        target_raw = self.join_addr_input.text().strip()
        if not target_raw:
            QMessageBox.warning(self, "Input Required", "Please enter a Room Code (e.g. SAGE-4829) or Host IP:port (e.g. 192.168.1.5:8989).")
            return

        nickname = self.join_name_input.text().strip() or "Developer"

        if ":" in target_raw and any(c.isdigit() for c in target_raw.split(":")[0]):
            host_part, port_part = target_raw.split(":", 1)
            try:
                port = int(port_part)
            except ValueError:
                port = 8989
            ok = self.manager.join_session(host=host_part.strip(), port=port, user_name=nickname)
            if not ok:
                QMessageBox.warning(self, "Connection Errors", f"Could not reach host at {host_part}:{port}.\nVerify IP address and ensure host is active.")
        else:
            ok = self.manager.join_session_cloud(room_code=target_raw, user_name=nickname)
            if not ok:
                QMessageBox.warning(self, "Connection Errors", f"Could not connect to Cloud Room '{target_raw}'.\nVerify room code and check internet connection.")

        self._refresh_state()

    def _copy_room_code(self):
        code = self.room_code_display.text().strip()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(code)
            self.copy_btn.setText("✓ Copied!")
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #10b981;
                    color: #041018;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            if hasattr(self, "copy_feedback_lbl") and self.copy_feedback_lbl:
                self.copy_feedback_lbl.setText("✓ Copied!")
            QTimer.singleShot(1800, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.copy_btn.setText("📋 Copy")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #041018;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #3bfdd5;
            }
        """)
        if hasattr(self, "copy_feedback_lbl") and self.copy_feedback_lbl:
            self.copy_feedback_lbl.setText("")

    def _on_status_changed(self, text: str, is_active: bool):
        self._refresh_state()

    def _on_peers_updated(self, peers: list):
        self.host_peers_list.clear()
        self.join_peers_list.clear()
        for p in peers:
            icon = "👑 " if "(Host)" in p else "💻 "
            item1 = QListWidgetItem(f"{icon}{p}")
            self.host_peers_list.addItem(item1)
            item2 = QListWidgetItem(f"{icon}{p}")
            self.join_peers_list.addItem(item2)

    def _on_files_updated(self, files: list):
        count_text = f"📁 {len(files)} Shared Files in Room"
        self.host_files_lbl.setText(count_text)
        self.join_files_lbl.setText(count_text)

    def _on_log(self, msg: str):
        self.log_view.append(msg)


class CollabDialog(QDialog):
    """Backwards-compatible modal dialog wrapping CollabPanelWidget."""

    def __init__(self, manager: CollabManager, default_user_name: str = "Developer", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sage AI • Live Collaborative Pair Programming")
        self.resize(580, 590)
        self.setMinimumWidth(570)
        self.setModal(True)
        self.panel = CollabPanelWidget(manager, default_user_name, parent=self)
        self.panel.close_requested.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)

    def __getattr__(self, name):
        return getattr(self.panel, name)

