"""
Live Working Panel Component for Sage AI (Lunar Engine).
Displays real-time stage transitions ("Understanding request", "Routing to coding model",
"Calling API", "Synthesizing answer") with animated status indicator.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer


class LiveWorkingPanel(QWidget):
    """Dynamic activity badge displaying backend stage changes in real time."""

    SPINNER_FRAMES = ["✦", "✧", "✶", "✷", "✸", "✹"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame_idx = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_spinner)

        self._init_ui()
        self.setVisible(False)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setAlignment(Qt.AlignLeft)

        self.badge = QFrame()
        self.badge.setObjectName("workingBadge")
        badge_layout = QHBoxLayout(self.badge)
        badge_layout.setContentsMargins(12, 6, 14, 6)
        badge_layout.setSpacing(8)

        self.icon_lbl = QLabel("✦")
        self.icon_lbl.setStyleSheet("color: #00D1FF; font-size: 14px; font-weight: bold;")
        badge_layout.addWidget(self.icon_lbl)

        self.text_lbl = QLabel("Ready")
        self.text_lbl.setObjectName("workingText")
        badge_layout.addWidget(self.text_lbl)

        layout.addWidget(self.badge)

    def set_stage(self, stage_text: str):
        """Sets the active stage text and starts animation."""
        self.text_lbl.setText(stage_text)
        self.setVisible(True)
        if not self.timer.isActive():
            self.timer.start(180)

    def stop(self):
        """Stops animation and hides the badge."""
        self.timer.stop()
        self.setVisible(False)

    def _animate_spinner(self):
        self._frame_idx = (self._frame_idx + 1) % len(self.SPINNER_FRAMES)
        self.icon_lbl.setText(self.SPINNER_FRAMES[self._frame_idx])
