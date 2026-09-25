"""
Agent Thinking Cloud Component for Sage AI Coding IDE.
Provides a Claude/DeepSeek-inspired live thinking cloud visualization:
- Real-time token and chain-of-thought streaming
- Pulsating live thinking header with live elapsed timer (100ms precision)
- Collapsible glassmorphism dark container with Cascadia/Consolas monospace typography
- Quick copy-to-clipboard button with visual feedback
- Safe QTimer lifecycle management (no leaks on widget destruction or tab switches)
"""
import time
from typing import Optional
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QApplication, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor, QFont


class AgentThinkingCloudWidget(QFrame):
    """Collapsible live thinking cloud widget for the Coding Agent."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.is_expanded: bool = True
        self.is_live: bool = False
        self.latency_s: Optional[float] = None
        self._start_time: Optional[float] = None
        self._thinking_text: str = ""
        self._live_timer: Optional[QTimer] = None
        self._chunk_count: int = 0

        self._init_ui()
        self.destroyed.connect(self._cleanup_timer)

    def _cleanup_timer(self):
        """Safely stops and cleans up the live timer."""
        if self._live_timer:
            try:
                if self._live_timer.isActive():
                    self._live_timer.stop()
            except Exception:
                pass
            self._live_timer = None

    def closeEvent(self, event):
        self._cleanup_timer()
        super().closeEvent(event)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(3)

        # ── Header Cloud Pill ──────────────────────────────────────────
        self.header_frame = QFrame()
        self.header_frame.setCursor(Qt.PointingHandCursor)
        hf_layout = QHBoxLayout(self.header_frame)
        hf_layout.setContentsMargins(6, 4, 6, 4)
        hf_layout.setSpacing(6)

        # Cloud Icon & Title
        self.cloud_icon_lbl = QLabel("☁️")
        self.cloud_icon_lbl.setStyleSheet("font-size: 13px;")
        hf_layout.addWidget(self.cloud_icon_lbl)

        self.title_lbl = QLabel("Thought Process")
        self.title_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #94A3B8;")
        hf_layout.addWidget(self.title_lbl)

        hf_layout.addStretch()

        # Copy Button (Does not toggle collapse)
        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setFocusPolicy(Qt.NoFocus)
        self.copy_btn.setToolTip("Copy thinking process to clipboard")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
                border-color: rgba(0, 209, 255, 0.4);
            }
        """)
        self.copy_btn.clicked.connect(self._copy_thinking)
        hf_layout.addWidget(self.copy_btn)

        # Toggle Chevron
        self.chevron_lbl = QLabel("▾")
        self.chevron_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-weight: bold;")
        hf_layout.addWidget(self.chevron_lbl)

        self._apply_header_style()
        main_layout.addWidget(self.header_frame)

        # Click on header toggles expansion
        self.header_frame.mousePressEvent = self._on_header_clicked

        # ── Collapsible Content Container ──────────────────────────────
        self.content_frame = QFrame()
        self.content_frame.setVisible(self.is_expanded)
        self.content_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(11, 19, 38, 0.95), stop:1 rgba(6, 11, 22, 0.95));
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 6px;
                padding: 4px;
            }
        """)
        cf_layout = QVBoxLayout(self.content_frame)
        cf_layout.setContentsMargins(8, 6, 8, 6)
        cf_layout.setSpacing(4)

        # Sub-header inside cloud: status badge
        sub_header = QHBoxLayout()
        sub_header.setSpacing(6)

        self.cloud_tag = QLabel("COGNITIVE CHAIN-OF-THOUGHT")
        self.cloud_tag.setStyleSheet("color: #38BDF8; font-size: 9px; font-weight: 800; letter-spacing: 0.5px;")
        sub_header.addWidget(self.cloud_tag)

        sub_header.addStretch()

        self.live_badge = QLabel("● IDLE")
        self.live_badge.setStyleSheet("color: #64748B; font-size: 9px; font-weight: 700;")
        sub_header.addWidget(self.live_badge)
        cf_layout.addLayout(sub_header)

        # Text Browser for Reasoning Stream
        self.text_browser = QTextBrowser()
        self.text_browser.setPlainText("Waiting for agent instructions...")
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                color: #CBD5E1;
                font-family: 'Cascadia Code', 'Consolas', 'JetBrains Mono', 'Segoe UI Mono', monospace;
                font-size: 11px;
                line-height: 1.45;
                padding: 2px 0;
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.6);
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(56, 189, 248, 0.35);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 209, 255, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.text_browser.setMaximumHeight(180)
        self.text_browser.setMinimumHeight(50)
        cf_layout.addWidget(self.text_browser)

        main_layout.addWidget(self.content_frame)

    def _apply_header_style(self):
        if self.is_live:
            self.header_frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 209, 255, 0.18), stop:1 rgba(99, 102, 241, 0.18));
                    border: 1px solid #00D1FF;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 209, 255, 0.24), stop:1 rgba(99, 102, 241, 0.24));
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #00D1FF;")
            self.chevron_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: bold;")
        else:
            self.header_frame.setStyleSheet("""
                QFrame {
                    background: rgba(11, 19, 38, 0.7);
                    border: 1px solid rgba(0, 209, 255, 0.2);
                    border-radius: 6px;
                }
                QFrame:hover {
                    background: rgba(14, 25, 50, 0.85);
                    border-color: rgba(0, 209, 255, 0.4);
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #94A3B8;")
            self.chevron_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-weight: bold;")

    def _on_header_clicked(self, event):
        # Ignore clicks originating on the copy button
        if self.copy_btn.geometry().contains(event.pos()):
            return
        self.toggle_expand()

    def toggle_expand(self):
        """Toggles between expanded and collapsed state."""
        self.is_expanded = not self.is_expanded
        self.content_frame.setVisible(self.is_expanded)
        self.chevron_lbl.setText("▾" if self.is_expanded else "▸")

    def reset(self):
        """Resets the thinking cloud for a new task execution."""
        self._cleanup_timer()
        self.is_live = False
        self._thinking_text = ""
        self._chunk_count = 0
        self.latency_s = None
        self.text_browser.clear()
        self.title_lbl.setText("☁️ Live Thinking (0.0s)... ◌")
        self.live_badge.setText("● READY")
        self.live_badge.setStyleSheet("color: #38BDF8; font-size: 9px; font-weight: 700;")
        self._apply_header_style()

    def start_live(self):
        """Activates live streaming mode with real-time timer updates."""
        self.is_live = True
        self.is_expanded = True
        self.content_frame.setVisible(True)
        self.chevron_lbl.setText("▾")
        self._start_time = time.time()
        self._thinking_text = ""
        self._chunk_count = 0
        self.text_browser.clear()
        self._apply_header_style()

        self.live_badge.setText("● STREAMING LIVE")
        self.live_badge.setStyleSheet("color: #00D1FF; font-size: 9px; font-weight: 700;")

        if self._live_timer is None:
            self._live_timer = QTimer(self)
            self._live_timer.timeout.connect(self._update_live_timer)
        if not self._live_timer.isActive():
            self._live_timer.start(100)

    def _update_live_timer(self):
        try:
            if not self.isVisible() or not hasattr(self, "title_lbl"):
                self._cleanup_timer()
                return
            if self._start_time:
                elapsed = time.time() - self._start_time
                self.title_lbl.setText(f"☁️ Thinking live ({elapsed:.1f}s)... ◌")
        except Exception:
            self._cleanup_timer()

    def append_chunk(self, chunk: str):
        """Appends a chunk of reasoning text to the live cloud incrementally with zero UI stutter."""
        if not chunk:
            return
        try:
            # If not yet live, automatically activate live state
            if not self.is_live:
                self.start_live()

            self._thinking_text += chunk
            self._chunk_count += 1

            # High-performance incremental text insertion (O(len(chunk)) instead of O(total_doc))
            cursor = self.text_browser.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(chunk)
            self.text_browser.setTextCursor(cursor)

            # Throttle word counter calculation to prevent event loop lag
            if self._chunk_count <= 5 or self._chunk_count % 15 == 0:
                words = len(self._thinking_text.split())
                self.live_badge.setText(f"● LIVE ({words} words)")
        except Exception:
            pass

    def finish_thinking(self, duration_s: Optional[float] = None):
        """Concludes live thinking and displays final duration."""
        self._cleanup_timer()
        self.is_live = False

        if duration_s is not None and duration_s > 0:
            self.latency_s = duration_s
        elif self._start_time:
            self.latency_s = time.time() - self._start_time
        else:
            self.latency_s = 0.0

        dur_text = f"{self.latency_s:.1f}s"
        self.title_lbl.setText(f"✦ Thought for {dur_text}")
        words = len(self._thinking_text.split()) if self._thinking_text else 0
        if words > 0:
            self.live_badge.setText(f"✓ CONCLUDED ({words} words)")
        else:
            self.live_badge.setText("✓ CONCLUDED")
        self.live_badge.setStyleSheet("color: #10B981; font-size: 9px; font-weight: 700;")
        self._apply_header_style()

    def _copy_thinking(self):
        """Copies reasoning chain-of-thought to the clipboard."""
        content = self._thinking_text.strip() or self.text_browser.toPlainText().strip()
        if not content:
            return
        try:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(content)
                self.copy_btn.setText("✓ Copied")
                self.copy_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(16, 185, 129, 0.2);
                        color: #10B981;
                        border: 1px solid #10B981;
                        border-radius: 4px;
                        padding: 2px 7px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """)
                QTimer.singleShot(1500, self._restore_copy_btn)
        except Exception:
            pass

    def _restore_copy_btn(self):
        try:
            self.copy_btn.setText("📋 Copy")
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    color: #94A3B8;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-size: 10px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: rgba(0, 209, 255, 0.15);
                    color: #00D1FF;
                    border-color: rgba(0, 209, 255, 0.4);
                }
            """)
        except Exception:
            pass

    def get_thinking_text(self) -> str:
        """Returns the accumulated thinking text."""
        return self._thinking_text
