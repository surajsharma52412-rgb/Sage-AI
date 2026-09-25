"""
Live Working Panel Component for Sage AI.
Displays real-time stage transitions ("Understanding request", "Routing to coding model",
"Calling API", "Synthesizing answer") with animated status indicator.
"""
import math
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer


class LiveWorkingPanel(QWidget):
    """Dynamic activity badge displaying backend stage changes in real time with animated micro-effects."""

    SPINNER_FRAMES = ["✦", "✧", "✶", "✷", "✸", "✹"]
    SHIELD_FRAMES = ["🛡️", "✨", "🛡️", "⚡"]
    IMAGE_FRAMES = ["🎨", "✨", "🖌️", "🪄", "🔮", "🌌"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame_idx = 0
        self._pulse_step = 0.0
        self._is_guard_stage = False
        self._is_image_stage = False

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
        self._apply_badge_style(0.3)

    def set_stage(self, stage_text: str):
        """Sets the active stage text and starts animation."""
        self.text_lbl.setText(stage_text)
        self.setVisible(True)

        low = stage_text.lower()
        self._is_guard_stage = any(k in low for k in ("zero-cost", "0 rs", "shifted to 100% free", "blocked"))
        self._is_image_stage = any(k in low for k in ("image", "flux", "draw", "photo", "art", "diffusion", "latent"))
        if not self.timer.isActive():
            self.timer.start(150)
        self._update_display()

    def stop(self):
        """Stops animation and hides the badge."""
        self.timer.stop()
        self.setVisible(False)

    def _animate_spinner(self):
        self._pulse_step += 0.12
        if self._is_guard_stage:
            self._frame_idx = (self._frame_idx + 1) % len(self.SHIELD_FRAMES)
            self.icon_lbl.setText(self.SHIELD_FRAMES[self._frame_idx])
        elif self._is_image_stage:
            self._frame_idx = (self._frame_idx + 1) % len(self.IMAGE_FRAMES)
            self.icon_lbl.setText(self.IMAGE_FRAMES[self._frame_idx])
        else:
            self._frame_idx = (self._frame_idx + 1) % len(self.SPINNER_FRAMES)
            self.icon_lbl.setText(self.SPINNER_FRAMES[self._frame_idx])

        alpha = 0.25 + 0.35 * (0.5 * (1 + math.sin(self._pulse_step)))
        self._apply_badge_style(alpha)

    def _update_display(self):
        self._animate_spinner()

    def _apply_badge_style(self, alpha: float):
        if self._is_guard_stage:
            self.badge.setStyleSheet(f"""
                QFrame#workingBadge {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(16, 185, 129, 0.28),
                        stop:1 rgba(245, 158, 11, 0.18));
                    border: 1px solid rgba(16, 185, 129, {alpha:.2f});
                    border-radius: 10px;
                }}
            """)
            self.icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")
            self.text_lbl.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 700; background: transparent;")
        elif self._is_image_stage:
            self.badge.setStyleSheet(f"""
                QFrame#workingBadge {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(168, 85, 247, 0.28),
                        stop:1 rgba(0, 209, 255, 0.20));
                    border: 1px solid rgba(168, 85, 247, {alpha:.2f});
                    border-radius: 10px;
                }}
            """)
            self.icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")
            self.text_lbl.setStyleSheet("color: #c084fc; font-size: 12px; font-weight: 700; background: transparent;")
        else:
            self.badge.setStyleSheet(f"""
                QFrame#workingBadge {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(0, 209, 255, 0.16),
                        stop:1 rgba(15, 230, 181, 0.08));
                    border: 1px solid rgba(0, 209, 255, {alpha:.2f});
                    border-radius: 10px;
                }}
            """)
            self.icon_lbl.setStyleSheet("color: #00D1FF; font-size: 14px; font-weight: bold; background: transparent;")
            self.text_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 600; background: transparent;")
