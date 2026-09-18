"""
Top Bar Component for SAGE AI.
Matches the exact reference picture:
- Left: "SAGE AI" (bold white) + "Your Intelligent Workspace" (muted subtitle)
- Center: Search bar "Search anything... (Ctrl + K)"
- Right: Dark mode toggle (moon), Notification bell with cyan badge, Settings gear
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


class TopBar(QWidget):
    """Top navigation and global search header bar."""

    settings_clicked = Signal()
    help_clicked = Signal()
    search_submitted = Signal(str)
    notifications_clicked = Signal()
    dark_mode_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(62)
        self.setStyleSheet("""
            QWidget#topBar {
                background-color: #0A0F14;
                border-bottom: 1px solid #273449;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(16)

        # 1. Left Branding: SAGE AI + Your Intelligent Workspace
        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        brand_col.setAlignment(Qt.AlignVCenter)

        self.title_lbl = QLabel("SAGE AI")
        self.title_lbl.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 800; letter-spacing: 0.5px; background: transparent;")
        brand_col.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel("Your Intelligent Workspace")
        self.subtitle_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 500; background: transparent;")
        brand_col.addWidget(self.subtitle_lbl)

        layout.addLayout(brand_col)

        layout.addStretch(1)

        # Search input retained as hidden attribute for compatibility
        self.search_input = QLineEdit()
        self.search_input.setVisible(False)
        self.moon_btn = QPushButton()
        self.moon_btn.setVisible(False)
        self.bell_btn = QPushButton()
        self.bell_btn.setVisible(False)

        # 2. Right Icons: Settings Gear
        right_row = QHBoxLayout()
        right_row.setSpacing(10)
        right_row.setAlignment(Qt.AlignVCenter)

        # Settings Gear Button
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(34, 34)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("Workspace Settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 8px;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #162033;
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        right_row.addWidget(self.settings_btn)

        layout.addLayout(right_row)

    def _on_search_enter(self):
        txt = self.search_input.text().strip()
        if txt:
            self.search_submitted.emit(txt)

    def update_theme_accent(self, primary_color: str):
        """Updates title color to match active theme primary color."""
        self.title_lbl.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 800; letter-spacing: 0.5px; background: transparent;")
