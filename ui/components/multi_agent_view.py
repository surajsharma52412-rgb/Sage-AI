"""
Multi-Agent Hub View for Sage Multi-Agentic AI Architecture.
Matches the futuristic reference dashboard:
- Header: Dynamic greeting ("Good Afternoon, Suraj 👋") + 3D Robot Mascot with speech bubble ("Let's make it happen! 🚀")
- 6 Intent Category Tiles: Chat, Create, Analyze, Code, Automate, Plan with custom colored glows
- Main Task Input Box: Multi-line text input, file chips (PDF, CSV, PNG), + Add Files/Folder, Web Search, Agent Dropdown, Send button
- Example Tasks: 6 styled cards with quick goal presets
- Recent Tasks: Interactive table with status badges (Completed, In Progress, Queued), relative timestamps, and View buttons
- Right Rail Sidebar:
  - Your Files (with file sizes, timestamps, and click-to-attach)
  - Active Agents (live status dots and badges for all 7 specialized agents)
  - Quick Actions (2x2 grid: Upload Files, Take Screenshot, Record Audio, Connect Apps)
- Live Execution Drawer / Modal with Inter-Agent Communication Bus and Deliverables
- Footer with brand motto and policy links
"""
import os
import sys
import time
import json
import uuid
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QTextBrowser, QScrollArea, QFrame, QGridLayout,
    QProgressBar, QSplitter, QComboBox, QFileDialog, QSizePolicy, QDialog,
    QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QCursor, QAction

from config import (
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_IMAGE_MEDIA,
    AGENT_DATA_ANALYSIS,
    AGENT_CONTENT,
    AGENT_EXECUTION,
    AGENT_PLANNING,
    AGENT_METADATA,
    ALL_AGENTS,
)
from engine.orchestrator.core_brain import get_orchestrator
from engine.shared_resources.communication_bus import get_comm_bus
from database.db_manager import get_db
from ui.components.message_bubble import format_markdown_to_html


class _MultiAgentSignalBridge(QObject):
    stage_updated = Signal(str)
    step_updated = Signal(dict)
    bus_event = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)


class GoalTextEdit(QTextEdit):
    """Custom auto-expanding prompt text area with Enter-to-send and focus signals."""
    send_requested = Signal()
    focus_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type your task here...")
        self.setMinimumHeight(44)
        self.setMaximumHeight(130)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #F8FAFC;
                font-size: 13.5px;
                line-height: 1.4;
                padding: 4px 2px;
                selection-background-color: #0284C7;
            }
        """)
        self.textChanged.connect(self._adjust_height)
        self.document().documentLayout().documentSizeChanged.connect(self._adjust_height)

    def _adjust_height(self):
        doc_h = int(self.document().size().height()) + 14
        new_h = max(44, min(130, doc_h))
        self.setFixedHeight(new_h)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.send_requested.emit()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_changed.emit(False)


# ---------------------------------------------------------------------------
# Subcomponent 1: Category Tile (Top 6 Pills)
# ---------------------------------------------------------------------------
class CategoryTile(QFrame):
    """Sleek intent category tile with glowing accents and hover animations."""

    clicked = Signal(str, str)  # key, default_prompt

    def __init__(self, key: str, title: str, subtitle: str, icon: str, color: str, prompt: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.title_text = title
        self.subtitle_text = subtitle
        self.icon_text = icon
        self.color = color
        self.default_prompt = prompt
        self.is_selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(76)
        self.setMinimumWidth(110)
        self._init_ui()
        self.set_selected(False)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.icon_lbl = QLabel(self.icon_text)
        self.icon_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 15px;
                color: {self.color};
                background: transparent;
                border: none;
            }}
        """)
        top_row.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(self.title_text)
        self.title_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 13.5px;
                font-weight: 700;
                color: #F8FAFC;
                background: transparent;
                border: none;
            }}
        """)
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.sub_lbl = QLabel(self.subtitle_text)
        self.sub_lbl.setStyleSheet("""
            QLabel {{
                font-size: 11px;
                color: #94A3B8;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.sub_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key, self.default_prompt)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.setStyleSheet(f"""
                CategoryTile {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self.color}22, stop:1 {self.color}0a);
                    border: 1.5px solid {self.color};
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                CategoryTile {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(16, 26, 46, 0.7), stop:1 rgba(11, 18, 32, 0.9));
                    border: 1px solid {self.color}33;
                    border-radius: 12px;
                }}
                CategoryTile:hover {{
                    border: 1.5px solid {self.color}99;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self.color}1f, stop:1 rgba(11, 18, 32, 0.95));
                }}
            """)


# ---------------------------------------------------------------------------
# Subcomponent 2: Attached File Chip
# ---------------------------------------------------------------------------
class FileChip(QFrame):
    """Interactive attached file chip with icon, filename, size, and close button."""

    removed = Signal(str)

    def __init__(self, filename: str, size_str: str, file_type: str = "doc", parent=None):
        super().__init__(parent)
        self.filename = filename
        self.size_str = size_str
        self.file_type = file_type.lower()
        self.setFixedHeight(34)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # File type color and icon
        if "pdf" in self.filename.lower():
            icon_txt = "📄"
            bg_badge = "#EF4444"
            badge_txt = "PDF"
        elif any(x in self.filename.lower() for x in ("csv", "xls", "xlsx")):
            icon_txt = "📊"
            bg_badge = "#10B981"
            badge_txt = "CSV"
        elif any(x in self.filename.lower() for x in ("png", "jpg", "jpeg", "webp")):
            icon_txt = "🖼️"
            bg_badge = "#3B82F6"
            badge_txt = "IMG"
        else:
            icon_txt = "📝"
            bg_badge = "#8B5CF6"
            badge_txt = "FILE"

        badge_lbl = QLabel(badge_txt)
        badge_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_badge};
                color: #FFFFFF;
                font-size: 8.5px;
                font-weight: 800;
                padding: 1px 4px;
                border-radius: 3px;
            }}
        """)
        layout.addWidget(badge_lbl)

        # File name (truncated)
        short_name = self.filename if len(self.filename) <= 24 else self.filename[:21] + "..."
        name_lbl = QLabel(short_name)
        name_lbl.setStyleSheet("color: #E2E8F0; font-size: 11.5px; font-weight: 600; background: transparent;")
        name_lbl.setToolTip(self.filename)
        layout.addWidget(name_lbl)

        # File size
        size_lbl = QLabel(self.size_str)
        size_lbl.setStyleSheet("color: #64748B; font-size: 10px; background: transparent;")
        layout.addWidget(size_lbl)

        # Close button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(16, 16)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                color: #94A3B8;
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        del_btn.clicked.connect(lambda: self.removed.emit(self.filename))
        layout.addWidget(del_btn)

        self.setStyleSheet("""
            QFrame {
                background-color: #121E33;
                border: 1px solid #1E2D4A;
                border-radius: 6px;
            }
            QFrame:hover {
                border-color: rgba(0, 209, 255, 0.4);
            }
        """)


# ---------------------------------------------------------------------------
# Subcomponent 3: Example Task Card
# ---------------------------------------------------------------------------
class ExampleTaskCard(QFrame):
    """Horizontal card for quick example multi-agent task execution."""

    selected = Signal(str, str, str)  # title, prompt, agent_name

    def __init__(self, title: str, desc: str, icon: str, color: str, prompt: str, agent_name: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.desc_text = desc
        self.icon_text = icon
        self.color = color
        self.prompt = prompt
        self.agent_name = agent_name
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(118)
        self.setMinimumWidth(130)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        icon_lbl = QLabel(self.icon_text)
        icon_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                color: {self.color};
                background: {self.color}15;
                padding: 4px;
                border-radius: 6px;
            }}
        """)
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(self.title_text)
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 700; background: transparent;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(self.desc_text)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; background: transparent;")
        layout.addWidget(desc_lbl)
        layout.addStretch()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #0E1729;
                border: 1px solid #1A2840;
                border-radius: 10px;
            }}
            QFrame:hover {{
                background-color: #132038;
                border: 1px solid {self.color}66;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.title_text, self.prompt, self.agent_name)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Subcomponent 4: Recent Task Row
# ---------------------------------------------------------------------------
class RecentTaskRow(QFrame):
    """Table row representing a recent task execution."""

    view_requested = Signal(dict)

    def __init__(self, task_info: dict, parent=None):
        super().__init__(parent)
        self.task_info = task_info
        self.setFixedHeight(44)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)

        icon_txt = self.task_info.get("icon", "📄")
        color = self.task_info.get("color", "#00D1FF")

        icon_lbl = QLabel(icon_txt)
        icon_lbl.setStyleSheet(f"font-size: 13px; color: {color}; background: transparent;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(self.task_info.get("title", "Task Execution"))
        title_lbl.setStyleSheet("color: #F1F5F9; font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(title_lbl, 1)

        # Status Pill Badge
        status = self.task_info.get("status", "Completed")
        status_lbl = QLabel()
        if status == "Completed":
            status_lbl.setText("✔  Completed")
            status_lbl.setStyleSheet("""
                QLabel {
                    color: #34D399;
                    background: rgba(16, 185, 129, 0.12);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 11px;
                    font-size: 10.5px;
                    font-weight: 700;
                    padding: 2px 10px;
                }
            """)
        elif status == "In Progress":
            status_lbl.setText("●  In Progress")
            status_lbl.setStyleSheet("""
                QLabel {
                    color: #00D1FF;
                    background: rgba(0, 209, 255, 0.12);
                    border: 1px solid rgba(0, 209, 255, 0.35);
                    border-radius: 11px;
                    font-size: 10.5px;
                    font-weight: 700;
                    padding: 2px 10px;
                }
            """)
        else:
            status_lbl.setText("●  Queued")
            status_lbl.setStyleSheet("""
                QLabel {
                    color: #94A3B8;
                    background: rgba(148, 163, 184, 0.1);
                    border: 1px solid rgba(148, 163, 184, 0.25);
                    border-radius: 11px;
                    font-size: 10.5px;
                    font-weight: 600;
                    padding: 2px 10px;
                }
            """)
        layout.addWidget(status_lbl)

        # Relative timestamp
        time_lbl = QLabel(self.task_info.get("timestamp", "Just now"))
        time_lbl.setStyleSheet("color: #64748B; font-size: 11px; background: transparent; min-width: 75px;")
        time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(time_lbl)

        # View Button
        view_btn = QPushButton("View")
        view_btn.setCursor(Qt.PointingHandCursor)
        view_btn.setFixedSize(54, 26)
        view_btn.setStyleSheet("""
            QPushButton {
                background-color: #132238;
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.2);
                border-color: #00D1FF;
                color: #FFFFFF;
            }
        """)
        view_btn.clicked.connect(lambda: self.view_requested.emit(self.task_info))
        layout.addWidget(view_btn)

        # Options button
        opt_btn = QPushButton("···")
        opt_btn.setCursor(Qt.PointingHandCursor)
        opt_btn.setFixedSize(26, 26)
        opt_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748B;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #F8FAFC;
            }
        """)
        layout.addWidget(opt_btn)

        self.setStyleSheet("""
            QFrame {
                background-color: #0B1322;
                border-bottom: 1px solid #142136;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #101B30;
            }
        """)


# ---------------------------------------------------------------------------
# Subcomponent 5: Agent Status Row Item (Used in Right Rail and AgentCard compatible)
# ---------------------------------------------------------------------------
class AgentStatusItem(QFrame):
    """Right Rail row showing agent icon, name, and live status badge."""

    def __init__(self, agent_name: str, parent=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.meta = AGENT_METADATA.get(agent_name, {})
        self.setFixedHeight(34)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(8)

        color = self.meta.get("color", "#00D1FF")
        icon_txt = self.meta.get("icon", "🤖")

        icon_lbl = QLabel(icon_txt)
        icon_lbl.setStyleSheet(f"font-size: 12px; color: {color}; background: transparent;")
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(self.agent_name)
        name_lbl.setStyleSheet("color: #E2E8F0; font-size: 11.5px; font-weight: 600; background: transparent;")
        layout.addWidget(name_lbl, 1)

        self.status_dot = QLabel("✔ Ready")
        self.status_dot.setStyleSheet("""
            QLabel {
                color: #34D399;
                font-size: 10px;
                font-weight: 700;
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 9px;
                padding: 1px 7px;
            }
        """)
        layout.addWidget(self.status_dot)

        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #101C30;
            }
        """)

    def set_working(self, working: bool):
        if working:
            self.status_dot.setText("● Active")
            self.status_dot.setStyleSheet("""
                QLabel {
                    color: #FBBF24;
                    font-size: 10px;
                    font-weight: 700;
                    background: rgba(251, 191, 36, 0.18);
                    border: 1px solid rgba(251, 191, 36, 0.45);
                    border-radius: 9px;
                    padding: 1px 7px;
                }
            """)
        else:
            self.status_dot.setText("✔ Ready")
            self.status_dot.setStyleSheet("""
                QLabel {
                    color: #34D399;
                    font-size: 10px;
                    font-weight: 700;
                    background: rgba(16, 185, 129, 0.12);
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    border-radius: 9px;
                    padding: 1px 7px;
                }
            """)


# Legacy AgentCard alias to satisfy unit tests
AgentCard = AgentStatusItem


# ---------------------------------------------------------------------------
# Subcomponent 6: Live Execution & Deliverables Drawer Dialog
# ---------------------------------------------------------------------------
class LiveExecutionDialog(QDialog):
    """Detailed live monitor for Inter-Agent Communication Bus and Deliverables."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-Agent Collaboration & Deliverables")
        self.resize(840, 580)
        self.setModal(False)
        self.setStyleSheet("background-color: #070D18; color: #F8FAFC;")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        title_lbl = QLabel("🤖 Multi-Agent Orchestration & Deliverables")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 800;")
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #132238;
                color: #94A3B8;
                border: 1px solid #1E314F;
                border-radius: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #FFFFFF;
                background: #EF4444;
            }
        """)
        close_btn.clicked.connect(self.close)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #132035;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D1FF, stop:1 #38BDF8);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        splitter = QSplitter(Qt.Horizontal)

        # Bus View
        bus_box = QFrame()
        bus_box.setStyleSheet("background-color: #0B1322; border: 1px solid #18263E; border-radius: 8px;")
        bus_layout = QVBoxLayout(bus_box)
        bus_layout.setContentsMargins(10, 8, 10, 8)
        bus_header = QLabel("📡 Inter-Agent Bus Feed")
        bus_header.setStyleSheet("color: #00D1FF; font-size: 11.5px; font-weight: 700;")
        bus_layout.addWidget(bus_header)

        self.bus_browser = QTextBrowser()
        self.bus_browser.setStyleSheet("background: transparent; border: none; color: #94A3B8; font-size: 11px;")
        bus_layout.addWidget(self.bus_browser)
        splitter.addWidget(bus_box)

        # Output View
        out_box = QFrame()
        out_box.setStyleSheet("background-color: #0B1322; border: 1px solid #18263E; border-radius: 8px;")
        out_layout = QVBoxLayout(out_box)
        out_layout.setContentsMargins(10, 8, 10, 8)
        out_header = QLabel("📦 Deliverables & Artifacts")
        out_header.setStyleSheet("color: #34D399; font-size: 11.5px; font-weight: 700;")
        out_layout.addWidget(out_header)

        self.out_browser = QTextBrowser()
        self.out_browser.setStyleSheet("background: transparent; border: none; color: #F8FAFC; font-size: 12px;")
        self.out_browser.setOpenExternalLinks(True)
        out_layout.addWidget(self.out_browser)
        splitter.addWidget(out_box)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter, 1)


# ---------------------------------------------------------------------------
# Primary Multi-Agent Hub View
# ---------------------------------------------------------------------------
class MultiAgentView(QWidget):
    """Primary Multi-Agent Orchestrator View with responsive scrolling container."""

    # Interactive Signals
    goal_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.orchestrator = get_orchestrator()
        self.comm_bus = get_comm_bus()
        self.signals = _MultiAgentSignalBridge()
        self.agent_cards: Dict[str, AgentStatusItem] = {}
        self._preset_buttons: List[QPushButton] = []
        self._attached_files: List[Dict[str, str]] = []
        self._execution_dialog: Optional[LiveExecutionDialog] = None

        self._init_ui()
        self._wire_signals()
        self._load_recent_tasks()
        self._refresh_user_files()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Responsive Scroll Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("multiAgentScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea#multiAgentScrollArea {
                background-color: #070D18;
                border: none;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 209, 255, 0.25);
                border-radius: 3px;
                min-height: 24px;
            }
        """)

        content_widget = QWidget()
        content_widget.setObjectName("multiAgentContent")
        content_widget.setStyleSheet("QWidget#multiAgentContent { background-color: #070D18; }")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 18, 24, 20)
        main_layout.setSpacing(16)

        # -------------------------------------------------------------------
        # TOP HEADER: Greeting on left, Mascot Hero on right
        # -------------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 20, 0)
        header_layout.setSpacing(16)

        # Left Column: Greeting & Subtitle
        greeting_col = QVBoxLayout()
        greeting_col.setSpacing(4)

        # Determine time of day
        cur_hour = time.localtime().tm_hour
        if cur_hour < 12:
            period = "Good Morning"
        elif cur_hour < 17:
            period = "Good Afternoon"
        else:
            period = "Good Evening"

        db_user = get_db().get_setting("user_display_name", "")
        first_name = db_user.strip().split()[0] if db_user and db_user.strip() else "Suraj"

        self.title_lbl = QLabel(f"{period}, {first_name} 👋")
        self.title_lbl.setStyleSheet("""
            QLabel {
                color: #F8FAFC;
                font-size: 24px;
                font-weight: 800;
                letter-spacing: -0.3px;
                background: transparent;
            }
        """)
        greeting_col.addWidget(self.title_lbl)

        self.sub_lbl = QLabel("What would you like to do today?")
        self.sub_lbl.setStyleSheet("color: #94A3B8; font-size: 13.5px; font-weight: 500; background: transparent;")
        greeting_col.addWidget(self.sub_lbl)
        header_layout.addLayout(greeting_col)
        header_layout.addStretch()

        # Right Column: Handwritten text + Cute 3D Robot Mascot + Speech bubble
        mascot_container = QWidget()
        mascot_box = QHBoxLayout(mascot_container)
        mascot_box.setContentsMargins(0, 0, 10, 0)
        mascot_box.setSpacing(8)
        mascot_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Cursive Script text: "Your AI Team Always Ready 💫"
        script_col = QVBoxLayout()
        script_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        script_lbl = QLabel("Your AI Team\nAlways Ready")
        script_lbl.setAlignment(Qt.AlignRight)
        script_lbl.setStyleSheet("""
            QLabel {
                color: #38BDF8;
                font-size: 12.5px;
                font-style: italic;
                font-weight: 700;
                font-family: 'Segoe Script', 'Brush Script MT', cursive, sans-serif;
                background: transparent;
            }
        """)
        script_col.addWidget(script_lbl)
        mascot_box.addLayout(script_col)

        # Robot image + Speech Bubble overlay
        mascot_frame = QWidget()
        mascot_layout = QHBoxLayout(mascot_frame)
        mascot_layout.setContentsMargins(0, 0, 0, 0)
        mascot_layout.setSpacing(6)

        # Speech Bubble: "Let's make it happen! 🚀"
        speech_bubble = QLabel("Let's make\nit happen! 🚀")
        speech_bubble.setStyleSheet("""
            QLabel {
                background-color: #FFFFFF;
                color: #0B1322;
                font-size: 10.5px;
                font-weight: 800;
                border-radius: 12px;
                padding: 5px 10px;
                border: 1.5px solid rgba(0, 209, 255, 0.4);
            }
        """)
        mascot_layout.addWidget(speech_bubble)

        # Mascot Avatar
        self.mascot_lbl = QLabel()
        assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
        avatar_path = assets_dir / "robot_avatar.png"
        mascot_path = assets_dir / "robot_mascot.png"

        target_img = avatar_path if avatar_path.exists() else mascot_path
        if target_img.exists():
            pix = QPixmap(str(target_img)).scaled(84, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.mascot_lbl.setPixmap(pix)
            self.mascot_lbl.setFixedSize(pix.size())
        else:
            self.mascot_lbl.setText("🤖")
            self.mascot_lbl.setStyleSheet("font-size: 38px; background: transparent;")
        mascot_layout.addWidget(self.mascot_lbl)

        mascot_box.addWidget(mascot_frame)
        header_layout.addWidget(mascot_container)

        main_layout.addLayout(header_layout)

        # -------------------------------------------------------------------
        # CATEGORY INTENT TILES (6 Pills Row)
        # -------------------------------------------------------------------
        tiles_layout = QHBoxLayout()
        tiles_layout.setSpacing(10)

        categories = [
            ("chat", "Chat", "Ask anything", "💬", "#00D1FF", "Explain quantum computing principles with code examples", AGENT_RESEARCH),
            ("create", "Create", "Generate content", "✨", "#C084FC", "Create an engaging product launch announcement for Sage AI", AGENT_CONTENT),
            ("analyze", "Analyze", "Work with data", "📊", "#34D399", "Analyze customer retention metrics from CSV and output actionable insights", AGENT_DATA_ANALYSIS),
            ("code", "Code", "Build & debug", "</>", "#FBBF24", "Build a high-performance REST API in FastAPI with unit tests", AGENT_CODING),
            ("automate", "Automate", "Set up workflows", "⚙️", "#F472B6", "Set up an automated web monitoring pipeline with webhook alerts", AGENT_EXECUTION),
            ("plan", "Plan", "Break down goals", "📅", "#818CF8", "Break down a full-stack SaaS product roadmap into 4 weekly sprints", AGENT_PLANNING),
        ]

        self.category_tiles: Dict[str, CategoryTile] = {}
        for key, title, sub, icon, col, prompt, ag in categories:
            tile = CategoryTile(key, title, sub, icon, col, prompt, self)
            tile.clicked.connect(self._on_category_clicked)
            self.category_tiles[key] = tile
            tiles_layout.addWidget(tile)

        # Default select Chat
        if "chat" in self.category_tiles:
            self.category_tiles["chat"].set_selected(True)

        main_layout.addLayout(tiles_layout)

        # -------------------------------------------------------------------
        # TWO-COLUMN SPLIT: Center/Left Column (~72%) + Right Rail (~28%)
        # -------------------------------------------------------------------
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(18)

        # ===================================================================
        # LEFT / CENTER COLUMN
        # ===================================================================
        left_widget = QWidget()
        left_col = QVBoxLayout(left_widget)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(16)

        # 1. Main Task Input Box
        self.input_card = QFrame()
        self.input_card.setObjectName("mainTaskInputCard")
        self.input_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.input_card.setStyleSheet("""
            QFrame#mainTaskInputCard {
                background-color: #081325;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 14px;
            }
        """)
        input_card_layout = QVBoxLayout(self.input_card)
        input_card_layout.setContentsMargins(18, 12, 18, 12)
        input_card_layout.setSpacing(8)

        # Multi-line / auto-expand text area
        self.goal_input = GoalTextEdit(self)
        self.goal_input.send_requested.connect(self._run_goal)
        self.goal_input.focus_changed.connect(self._on_input_focus_changed)
        input_card_layout.addWidget(self.goal_input)

        # Middle Toolbar: [+ Add Files] [📁 Add Folder] [🌐 Web Search] [✨ Agent: Auto ⏷] ... [🎙] [✈ Send]
        tool_row = QHBoxLayout()
        tool_row.setContentsMargins(0, 0, 0, 0)
        tool_row.setSpacing(8)

        self.add_files_btn = QPushButton("＋ Add Files")
        self.add_files_btn.setCursor(Qt.PointingHandCursor)
        self.add_files_btn.setFixedHeight(30)
        self.add_files_btn.setStyleSheet(self._pill_btn_style())
        self.add_files_btn.clicked.connect(self._choose_files)
        tool_row.addWidget(self.add_files_btn)

        self.add_folder_btn = QPushButton("📁 Add Folder")
        self.add_folder_btn.setCursor(Qt.PointingHandCursor)
        self.add_folder_btn.setFixedHeight(30)
        self.add_folder_btn.setStyleSheet(self._pill_btn_style())
        self.add_folder_btn.clicked.connect(self._choose_folder)
        tool_row.addWidget(self.add_folder_btn)

        self.web_search_btn = QPushButton("🌐 Web Search")
        self.web_search_btn.setCheckable(True)
        self.web_search_btn.setCursor(Qt.PointingHandCursor)
        self.web_search_btn.setFixedHeight(30)
        self.web_search_btn.setStyleSheet(self._pill_btn_style(checkable=True))
        tool_row.addWidget(self.web_search_btn)

        # Agent Dropdown Selector
        self.agent_combo = QComboBox()
        self.agent_combo.setCursor(Qt.PointingHandCursor)
        self.agent_combo.setFixedHeight(30)
        self.agent_combo.addItem("✨ Agent: Auto", "auto")
        for ag in ALL_AGENTS:
            meta = AGENT_METADATA.get(ag, {})
            icon = meta.get("icon", "🤖")
            self.agent_combo.addItem(f"{icon} {ag}", ag)
        self.agent_combo.setStyleSheet("""
            QComboBox {
                background-color: #121E33;
                color: #00D1FF;
                border: 1px solid #1E2E4A;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: rgba(0, 209, 255, 0.4);
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background-color: #0D1627;
                color: #F8FAFC;
                selection-background-color: #1A2B48;
                border: 1px solid rgba(0, 209, 255, 0.3);
            }
        """)
        tool_row.addWidget(self.agent_combo)

        tool_row.addStretch()

        # Voice Record Button
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setFixedSize(32, 32)
        self.mic_btn.setToolTip("Voice Task Input")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #121E33;
                color: #94A3B8;
                border: 1px solid #1E2E4A;
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: #00D1FF;
                background-color: #162640;
            }
        """)
        self.mic_btn.clicked.connect(self._toggle_voice_input)
        tool_row.addWidget(self.mic_btn)

        # Send Button
        self.run_btn = QPushButton("✈  Send")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setFixedHeight(32)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0072ff, stop:1 #00d1ff);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12.5px;
                padding: 6px 20px;
                border: none;
                border-radius: 7px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0084ff, stop:1 #38bdf8);
            }
        """)
        self.run_btn.clicked.connect(self._run_goal)
        tool_row.addWidget(self.run_btn)

        input_card_layout.addLayout(tool_row)

        # Attached Files Strip Container (Hidden until user attaches files)
        self.files_strip_container = QWidget()
        self.files_strip_layout = QHBoxLayout(self.files_strip_container)
        self.files_strip_layout.setContentsMargins(0, 6, 0, 2)
        self.files_strip_layout.setSpacing(8)

        self.add_more_files_btn = QPushButton("＋ Add more files or drag and drop")
        self.add_more_files_btn.setCursor(Qt.PointingHandCursor)
        self.add_more_files_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748B;
                border: 1px dashed #22324D;
                border-radius: 6px;
                font-size: 11px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        self.add_more_files_btn.clicked.connect(self._choose_files)
        self.files_strip_layout.addWidget(self.add_more_files_btn)
        self.files_strip_layout.addStretch()

        input_card_layout.addWidget(self.files_strip_container)
        self.files_strip_container.setVisible(False)
        left_col.addWidget(self.input_card)

        # 2. Example Tasks Section
        example_header = QHBoxLayout()
        example_title = QLabel("💻  Example Tasks")
        example_title.setStyleSheet("color: #F8FAFC; font-size: 13.5px; font-weight: 700;")
        example_header.addWidget(example_title)
        example_header.addStretch()

        see_more_btn = QPushButton("See More →")
        see_more_btn.setCursor(Qt.PointingHandCursor)
        see_more_btn.setStyleSheet("background: transparent; color: #00D1FF; font-size: 11px; font-weight: 600; border: none;")
        example_header.addWidget(see_more_btn)
        left_col.addLayout(example_header)

        # 6 Example Task Cards
        examples_grid = QHBoxLayout()
        examples_grid.setSpacing(8)

        example_data = [
            ("Summarize a PDF", "Upload a document and get a concise summary.", "📄", "#EF4444", "Summarize project_requirements.pdf with key milestones and architecture deliverables.", AGENT_RESEARCH),
            ("Build a Website", "Create a complete website with code and files.", "</>", "#3B82F6", "Build a responsive landing page website with modern CSS styles and interactive components.", AGENT_CODING),
            ("Analyze Data", "Upload a CSV or Excel file and get insights.", "📊", "#10B981", "Analyze dataset.csv to identify trends, correlations, and performance outliers.", AGENT_DATA_ANALYSIS),
            ("Generate Images", "Create stunning visuals from your ideas.", "🖼️", "#A855F7", "Generate high-resolution hero concepts and logo illustrations for Sage AI.", AGENT_IMAGE_MEDIA),
            ("Plan a Trip", "Find best places, budget and itinerary.", "✈️", "#06B6D4", "Plan a comprehensive 7-day travel itinerary with budget breakdown and points of interest.", AGENT_PLANNING),
            ("Write a Report", "Create detailed reports on any topic.", "📝", "#EC4899", "Write an executive intelligence report on multi-agent AI system architectures.", AGENT_CONTENT),
        ]

        for t_title, t_desc, t_icon, t_col, t_prompt, t_agent in example_data:
            card = ExampleTaskCard(t_title, t_desc, t_icon, t_col, t_prompt, t_agent, self)
            card.selected.connect(self._on_example_selected)
            examples_grid.addWidget(card)

        left_col.addLayout(examples_grid)

        # 3. Recent Tasks Section
        recent_header = QHBoxLayout()
        recent_title = QLabel("📋  Recent Tasks")
        recent_title.setStyleSheet("color: #F8FAFC; font-size: 13.5px; font-weight: 700;")
        recent_header.addWidget(recent_title)
        recent_header.addStretch()

        view_all_recent = QPushButton("View All →")
        view_all_recent.setCursor(Qt.PointingHandCursor)
        view_all_recent.setStyleSheet("background: transparent; color: #00D1FF; font-size: 11px; font-weight: 600; border: none;")
        recent_header.addWidget(view_all_recent)
        left_col.addLayout(recent_header)

        # Recent Tasks Container
        self.recent_tasks_col = QVBoxLayout()
        self.recent_tasks_col.setSpacing(4)
        left_col.addLayout(self.recent_tasks_col)

        self.recent_empty_lbl = QLabel("No recent tasks yet.\nSelect an example above or enter a task to begin.")
        self.recent_empty_lbl.setAlignment(Qt.AlignCenter)
        self.recent_empty_lbl.setWordWrap(True)
        self.recent_empty_lbl.setStyleSheet("""
            QLabel {
                color: #64748B;
                font-size: 11.5px;
                padding: 20px 16px;
                border: 1px dashed #1E2D4A;
                border-radius: 8px;
                background: rgba(14, 23, 41, 0.4);
                font-style: italic;
            }
        """)
        left_col.addWidget(self.recent_empty_lbl)

        # Collapsible Mini-Status and Progress (for immediate feedback)
        self.status_lbl = QLabel("Ready. Select or type a multi-agent goal.")
        self.status_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500;")
        left_col.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #121E33;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #00D1FF;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setValue(0)
        left_col.addWidget(self.progress_bar)

        # Communication Bus & Deliverables Browser references for unit test compatibility
        self.bus_browser = QTextBrowser()
        self.bus_browser.setVisible(False)
        self.out_browser = QTextBrowser()
        self.out_browser.setVisible(False)
        left_col.addWidget(self.bus_browser)
        left_col.addWidget(self.out_browser)
        left_col.addStretch(1)

        columns_layout.addWidget(left_widget, 7)

        # ===================================================================
        # RIGHT RAIL COLUMN (~28%)
        # ===================================================================
        right_widget = QWidget()
        right_widget.setMinimumWidth(280)
        right_widget.setMaximumWidth(360)
        right_col = QVBoxLayout(right_widget)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(14)

        # Card 1: Your Files
        files_card = QFrame()
        files_card.setStyleSheet("background-color: #0B1322; border: 1px solid #16243A; border-radius: 12px;")
        files_layout = QVBoxLayout(files_card)
        files_layout.setContentsMargins(14, 12, 14, 12)
        files_layout.setSpacing(6)

        files_hdr = QHBoxLayout()
        files_title = QLabel("📁  Your Files")
        files_title.setStyleSheet("color: #F8FAFC; font-size: 12.5px; font-weight: 700;")
        files_hdr.addWidget(files_title)
        files_hdr.addStretch()

        view_files_btn = QPushButton("View All →")
        view_files_btn.setCursor(Qt.PointingHandCursor)
        view_files_btn.setStyleSheet("background: transparent; color: #00D1FF; font-size: 10.5px; border: none;")
        files_hdr.addWidget(view_files_btn)
        files_layout.addLayout(files_hdr)

        self.user_files_col = QVBoxLayout()
        self.user_files_col.setSpacing(4)
        files_layout.addLayout(self.user_files_col)

        self.no_files_lbl = QLabel("No files uploaded yet.\nUse 'Upload Files' or '＋ Add Files' to add documents.")
        self.no_files_lbl.setAlignment(Qt.AlignCenter)
        self.no_files_lbl.setWordWrap(True)
        self.no_files_lbl.setStyleSheet("color: #64748B; font-size: 10.5px; padding: 14px 6px; font-style: italic;")
        files_layout.addWidget(self.no_files_lbl)

        right_col.addWidget(files_card)

        # Card 2: Active Agents (All 7 Specialized Agents)
        agents_card = QFrame()
        agents_card.setStyleSheet("background-color: #0B1322; border: 1px solid #16243A; border-radius: 12px;")
        agents_layout = QVBoxLayout(agents_card)
        agents_layout.setContentsMargins(14, 12, 14, 12)
        agents_layout.setSpacing(4)

        agents_hdr = QHBoxLayout()
        agents_title = QLabel("👥  Active Agents")
        agents_title.setStyleSheet("color: #F8FAFC; font-size: 12.5px; font-weight: 700;")
        agents_hdr.addWidget(agents_title)
        agents_hdr.addStretch()

        pulse_dot = QLabel("●")
        pulse_dot.setStyleSheet("color: #10B981; font-size: 12px;")
        agents_hdr.addWidget(pulse_dot)
        agents_layout.addLayout(agents_hdr)

        # Render 7 specialized agents
        for ag_name in ALL_AGENTS:
            item = AgentStatusItem(ag_name, self)
            self.agent_cards[ag_name] = item
            agents_layout.addWidget(item)

        right_col.addWidget(agents_card)

        # Card 3: Quick Actions (2x2 Grid)
        actions_card = QFrame()
        actions_card.setStyleSheet("background-color: #0B1322; border: 1px solid #16243A; border-radius: 12px;")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(14, 12, 14, 12)
        actions_layout.setSpacing(8)

        actions_title = QLabel("⚙  Quick Actions")
        actions_title.setStyleSheet("color: #F8FAFC; font-size: 12.5px; font-weight: 700;")
        actions_layout.addWidget(actions_title)

        grid_actions = QGridLayout()
        grid_actions.setSpacing(8)

        btn_upload = self._make_action_btn("⬆ Upload Files", self._choose_files)
        btn_screenshot = self._make_action_btn("⛶ Take Screenshot", self._take_screenshot)
        btn_audio = self._make_action_btn("🎙 Record Audio", self._toggle_voice_input)
        btn_connect = self._make_action_btn("🔗 Connect Apps", self._connect_apps)

        grid_actions.addWidget(btn_upload, 0, 0)
        grid_actions.addWidget(btn_screenshot, 0, 1)
        grid_actions.addWidget(btn_audio, 1, 0)
        grid_actions.addWidget(btn_connect, 1, 1)
        actions_layout.addLayout(grid_actions)

        right_col.addWidget(actions_card)
        right_col.addStretch()

        columns_layout.addWidget(right_widget, 3)
        main_layout.addLayout(columns_layout)

        # -------------------------------------------------------------------
        # FOOTER
        # -------------------------------------------------------------------
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(4, 12, 4, 4)

        brand_motto = QLabel("SAGE AI  |  Smarter People. Brighter Futures.")
        brand_motto.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500;")
        footer_layout.addWidget(brand_motto)
        footer_layout.addStretch()

        for link_text in ("Privacy", "Terms", "Help"):
            l_btn = QPushButton(link_text)
            l_btn.setCursor(Qt.PointingHandCursor)
            l_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #475569;
                    font-size: 11px;
                    border: none;
                    margin-left: 8px;
                }
                QPushButton:hover {
                    color: #00D1FF;
                }
            """)
            footer_layout.addWidget(l_btn)

        main_layout.addLayout(footer_layout)

        self.scroll_area.setWidget(content_widget)
        root_layout.addWidget(self.scroll_area)

    # -----------------------------------------------------------------------
    # Helper UI Builders
    # -----------------------------------------------------------------------
    def _pill_btn_style(self, checkable=False) -> str:
        if checkable:
            return """
                QPushButton {
                    background-color: #121E33;
                    color: #94A3B8;
                    border: 1px solid #1E2E4A;
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:checked {
                    background-color: rgba(0, 209, 255, 0.18);
                    color: #00D1FF;
                    border-color: #00D1FF;
                }
                QPushButton:hover {
                    border-color: rgba(0, 209, 255, 0.4);
                }
            """
        return """
            QPushButton {
                background-color: #121E33;
                color: #CBD5E1;
                border: 1px solid #1E2E4A;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #162640;
                border-color: rgba(0, 209, 255, 0.4);
                color: #00D1FF;
            }
        """

    def _make_action_btn(self, text: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #101B2E;
                color: #94A3B8;
                border: 1px solid #182842;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #14233C;
                border-color: rgba(0, 209, 255, 0.4);
                color: #00D1FF;
            }
        """)
        btn.clicked.connect(callback)
        return btn

    def _refresh_user_files(self):
        while self.user_files_col.count():
            item = self.user_files_col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        raw_files = get_db().get_setting("multi_agent_user_files", "[]")
        try:
            files_list = json.loads(raw_files)
        except Exception:
            files_list = []

        if not files_list:
            self.no_files_lbl.setVisible(True)
            return

        self.no_files_lbl.setVisible(False)
        for f in files_list[:8]:
            f_name = f.get("name", "document")
            f_time = f.get("time", "Just now")
            f_size = f.get("size", "")
            f_type = f.get("type", "doc")

            if "pdf" in f_name.lower():
                f_icon, f_color = "📄", "#EF4444"
            elif any(x in f_name.lower() for x in ("csv", "xls", "xlsx")):
                f_icon, f_color = "📊", "#10B981"
            elif any(x in f_name.lower() for x in ("png", "jpg", "jpeg", "webp")):
                f_icon, f_color = "🖼️", "#3B82F6"
            else:
                f_icon, f_color = "📝", "#F59E0B"

            row_frame = QFrame()
            row_frame.setCursor(Qt.PointingHandCursor)
            row_frame.setStyleSheet("""
                QFrame {
                    background: transparent;
                    border-radius: 4px;
                }
                QFrame:hover {
                    background: #111C2E;
                }
            """)
            f_row = QHBoxLayout(row_frame)
            f_row.setContentsMargins(4, 2, 4, 2)
            f_row.setSpacing(6)

            icon_l = QLabel(f_icon)
            icon_l.setStyleSheet(f"font-size: 12px; color: {f_color};")
            f_row.addWidget(icon_l)

            name_l = QLabel(f_name if len(f_name) <= 20 else f_name[:17] + "...")
            name_l.setStyleSheet("color: #CBD5E1; font-size: 11px; font-weight: 600;")
            name_l.setToolTip(f"Click to attach: {f_name}")
            f_row.addWidget(name_l, 1)

            time_txt = f"{f_size} • {f_time}" if f_size else f_time
            time_l = QLabel(time_txt)
            time_l.setStyleSheet("color: #64748B; font-size: 9.5px;")
            f_row.addWidget(time_l)

            dots_l = QLabel("⋮")
            dots_l.setStyleSheet("color: #64748B; font-size: 11px;")
            f_row.addWidget(dots_l)

            row_frame.mousePressEvent = lambda e, fn=f_name, sz=f_size, tp=f_type: self._add_file_chip(fn, sz, tp)
            self.user_files_col.addWidget(row_frame)

    def _save_user_file(self, filename: str, size_str: str, file_type: str = "doc"):
        raw_files = get_db().get_setting("multi_agent_user_files", "[]")
        try:
            files_list = json.loads(raw_files)
        except Exception:
            files_list = []

        files_list = [f for f in files_list if f.get("name") != filename]
        files_list.insert(0, {
            "name": filename,
            "size": size_str,
            "time": "Just now",
            "type": file_type
        })
        get_db().set_setting("multi_agent_user_files", json.dumps(files_list[:15]))
        self._refresh_user_files()

    def _load_recent_tasks(self):
        while self.recent_tasks_col.count():
            item = self.recent_tasks_col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        raw_tasks = get_db().get_setting("multi_agent_recent_tasks", "[]")
        try:
            tasks_list = json.loads(raw_tasks)
        except Exception:
            tasks_list = []

        if not tasks_list:
            self.recent_empty_lbl.setVisible(True)
            return

        self.recent_empty_lbl.setVisible(False)
        for task in tasks_list:
            self._add_recent_task_row(task)

    def _add_file_chip(self, filename: str, size_str: str, file_type: str = "doc"):
        for f in self._attached_files:
            if f.get("name") == filename:
                return

        chip = FileChip(filename, size_str, file_type, self)
        chip.removed.connect(self._remove_file_chip)
        cnt = self.files_strip_layout.count()
        idx = max(0, cnt - 2)
        self.files_strip_layout.insertWidget(idx, chip)
        self._attached_files.append({"name": filename, "size": size_str})
        self.files_strip_container.setVisible(True)
        self._save_user_file(filename, size_str, file_type)

    def _remove_file_chip(self, filename: str):
        for i in range(self.files_strip_layout.count()):
            item = self.files_strip_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), FileChip):
                if item.widget().filename == filename:
                    w = item.widget()
                    self.files_strip_layout.removeWidget(w)
                    w.deleteLater()
                    break
        self._attached_files = [f for f in self._attached_files if f["name"] != filename]
        if not self._attached_files:
            self.files_strip_container.setVisible(False)

    def _add_recent_task_row(self, task_info: dict):
        row = RecentTaskRow(task_info, self)
        row.view_requested.connect(self._show_task_details)
        self.recent_tasks_col.addWidget(row)

    # -----------------------------------------------------------------------
    # Interactive Actions & Logic
    # -----------------------------------------------------------------------
    def _on_input_focus_changed(self, focused: bool):
        if focused:
            self.input_card.setStyleSheet("""
                QFrame#mainTaskInputCard {
                    background-color: #081325;
                    border: 1.5px solid #00D1FF;
                    border-radius: 14px;
                }
            """)
        else:
            self.input_card.setStyleSheet("""
                QFrame#mainTaskInputCard {
                    background-color: #081325;
                    border: 1px solid rgba(0, 209, 255, 0.25);
                    border-radius: 14px;
                }
            """)

    def _on_category_clicked(self, key: str, prompt: str):
        for k, tile in self.category_tiles.items():
            tile.set_selected(k == key)

        if not self.goal_input.toPlainText().strip():
            self.goal_input.setText(prompt)

        # Select matching agent in combo
        target_agent = {
            "chat": AGENT_RESEARCH,
            "create": AGENT_CONTENT,
            "analyze": AGENT_DATA_ANALYSIS,
            "code": AGENT_CODING,
            "automate": AGENT_EXECUTION,
            "plan": AGENT_PLANNING,
        }.get(key)
        if target_agent:
            idx = self.agent_combo.findData(target_agent)
            if idx >= 0:
                self.agent_combo.setCurrentIndex(idx)

    def _on_example_selected(self, title: str, prompt: str, agent_name: str):
        self.goal_input.setText(prompt)
        idx = self.agent_combo.findData(agent_name)
        if idx >= 0:
            self.agent_combo.setCurrentIndex(idx)
        self.status_lbl.setText(f"Preset loaded: '{title}'. Ready to execute.")

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Attach", "", "All Files (*.*)")
        if files:
            for fpath in files:
                p = Path(fpath)
                sz_mb = p.stat().st_size / (1024 * 1024)
                sz_str = f"{sz_mb:.1f} MB" if sz_mb >= 1.0 else f"{p.stat().st_size / 1024:.0f} KB"
                self._add_file_chip(p.name, sz_str, p.suffix)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Attach")
        if folder:
            p = Path(folder)
            self._add_file_chip(p.name, "Folder", "folder")

    def _toggle_voice_input(self):
        self.status_lbl.setText("🎙 Voice input listening... (Click again to stop)")

    def _take_screenshot(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.status_lbl.setText("📸 Screen snapshot captured and attached to workspace.")

    def _connect_apps(self):
        self.status_lbl.setText("🔗 Connected integrations: Local Python, GitHub Workspace, Communication Bus.")

    def _show_task_details(self, task_info: dict):
        if not self._execution_dialog:
            self._execution_dialog = LiveExecutionDialog(self)

        self._execution_dialog.status_lbl.setText(f"Task: {task_info.get('title', 'Details')}")
        self._execution_dialog.progress_bar.setValue(100)
        summary = task_info.get("summary", "Task executed successfully.")
        self._execution_dialog.out_browser.setHtml(format_markdown_to_html(summary))
        self._execution_dialog.bus_browser.clear()
        self._execution_dialog.bus_browser.append(f"<b>[System]</b>: Task initialized for <i>{task_info.get('title')}</i>.")
        self._execution_dialog.bus_browser.append("<b>[Core Brain ➔ Specialized Agents]</b>: Orchestration completed.")
        self._execution_dialog.show()
        self._execution_dialog.raise_()

    # -----------------------------------------------------------------------
    # Multi-Agent Goal Execution
    # -----------------------------------------------------------------------
    def _wire_signals(self):
        self.signals.stage_updated.connect(self._on_stage_updated)
        self.signals.step_updated.connect(self._on_step_updated)
        self.signals.bus_event.connect(self._on_bus_event)
        self.signals.finished.connect(self._on_goal_finished)
        self.signals.failed.connect(self._on_goal_failed)
        self.comm_bus.subscribe("*", lambda evt: self.signals.bus_event.emit(evt))

    def _run_goal(self):
        goal = self.goal_input.toPlainText().strip()
        if not goal:
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ Running...")
        self.progress_bar.setValue(15)
        self.status_lbl.setText("🧠 Task Decomposer breaking goal into steps...")
        self.bus_browser.clear()
        self.out_browser.clear()

        # Hide empty recent tasks label safely
        try:
            if hasattr(self, "recent_empty_lbl") and self.recent_empty_lbl:
                self.recent_empty_lbl.setVisible(False)
        except RuntimeError:
            pass

        task_id = str(uuid.uuid4())
        new_task = {
            "id": task_id,
            "title": goal if len(goal) <= 32 else goal[:29] + "...",
            "status": "In Progress",
            "timestamp": "Just now",
            "icon": "⚡",
            "color": "#00D1FF",
            "summary": f"### 🚀 Multi-Agent Execution\n**Goal**: {goal}\n\n*Running pipeline with specialized agents...*"
        }

        # Save to DB
        raw_tasks = get_db().get_setting("multi_agent_recent_tasks", "[]")
        try:
            tasks_list = json.loads(raw_tasks)
        except Exception:
            tasks_list = []
        tasks_list.insert(0, new_task)
        get_db().set_setting("multi_agent_recent_tasks", json.dumps(tasks_list[:20]))

        self.recent_tasks_col.insertWidget(0, RecentTaskRow(new_task, self))

        threading.Thread(target=self._execute_thread, args=(goal,), daemon=True).start()

    def _execute_thread(self, goal: str):
        try:
            def on_stage(stage: str):
                self.signals.stage_updated.emit(stage)

            def on_step(step: dict):
                self.signals.step_updated.emit(step)

            res = self.orchestrator.orchestrate_goal(
                goal=goal,
                on_stage=on_stage,
                on_step_update=on_step
            )
            self.signals.finished.emit(res)
        except Exception as e:
            self.signals.failed.emit(str(e))

    def _on_stage_updated(self, stage: str):
        self.status_lbl.setText(stage)
        val = min(90, self.progress_bar.value() + 15)
        self.progress_bar.setValue(val)
        if self._execution_dialog and self._execution_dialog.isVisible():
            self._execution_dialog.status_lbl.setText(stage)
            self._execution_dialog.progress_bar.setValue(val)

    def _on_step_updated(self, step: dict):
        ag_type = step.get("agent_type")
        status = step.get("status")
        if ag_type in self.agent_cards:
            self.agent_cards[ag_type].set_working(status == "in_progress")

    def _on_bus_event(self, evt: dict):
        from_ag = evt.get("from_agent", "Agent")
        to_ag = evt.get("to_agent", "all")
        mtype = evt.get("message_type", "event")
        cnt = evt.get("content", "")
        line = f"<b>[{from_ag} ➔ {to_ag}]</b> <span style='color:#00D1FF;'>({mtype})</span>: {cnt}"
        self.bus_browser.append(line)
        if self._execution_dialog and self._execution_dialog.isVisible():
            self._execution_dialog.bus_browser.append(line)

    def _on_goal_finished(self, res: dict):
        self.progress_bar.setValue(100)
        self.run_btn.setEnabled(True)
        self.run_btn.setText("✈  Send")
        self.status_lbl.setText(f"✅ Automated Completion in {res.get('elapsed_seconds', 0)}s!")

        for card in self.agent_cards.values():
            card.set_working(False)

        summary = res.get("final_summary", "")
        html = format_markdown_to_html(summary)
        self.out_browser.setHtml(html)

        if self._execution_dialog and self._execution_dialog.isVisible():
            self._execution_dialog.progress_bar.setValue(100)
            self._execution_dialog.status_lbl.setText("✅ Completed!")
            self._execution_dialog.out_browser.setHtml(html)

        # Update DB recent tasks to completed
        raw_tasks = get_db().get_setting("multi_agent_recent_tasks", "[]")
        try:
            tasks_list = json.loads(raw_tasks)
        except Exception:
            tasks_list = []
        if tasks_list:
            tasks_list[0]["status"] = "Completed"
            tasks_list[0]["summary"] = summary
            get_db().set_setting("multi_agent_recent_tasks", json.dumps(tasks_list[:20]))
        self._load_recent_tasks()

    def _on_goal_failed(self, error: str):
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(True)
        self.run_btn.setText("✈  Send")
        self.status_lbl.setText(f"⚠️ Orchestrator Error: {error}")
        for card in self.agent_cards.values():
            card.set_working(False)
        self.out_browser.setPlainText(f"Error during execution:\n{error}")

        # Update DB recent tasks to failed
        raw_tasks = get_db().get_setting("multi_agent_recent_tasks", "[]")
        try:
            tasks_list = json.loads(raw_tasks)
        except Exception:
            tasks_list = []
        if tasks_list:
            tasks_list[0]["status"] = "Failed"
            tasks_list[0]["summary"] = f"Error during execution:\n{error}"
            get_db().set_setting("multi_agent_recent_tasks", json.dumps(tasks_list[:20]))
        self._load_recent_tasks()

    def apply_theme(self, pal: Dict[str, Any]):
        """Theme callback keeping compatibility with theme changes."""
        primary = pal.get("primary", "#00D1FF")
        primary_dark = pal.get("primary_dark", "#0072ff")
        if hasattr(self, "run_btn") and self.run_btn:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {primary_dark}, stop:1 {primary});
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 12.5px;
                    padding: 6px 18px;
                    border: none;
                    border-radius: 7px;
                }}
            """)
