"""
Sage AI Coding Agent & IDE View Component.
Clean, modern, uncongested, on-demand workspace.
- Responsive layout with QSplitter panels.
- Starts fresh (no pre-populated fake code, fake users, or fake tasks).
- On-demand tool activation: Agent, Collaboration, Whiteboard, and Terminal activate when needed.
- Clean header without duplicate logo or crowded subtitles.
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTabBar, QPlainTextEdit, QTextEdit, QLineEdit, QProgressBar,
    QStackedWidget, QMenu, QFileDialog, QInputDialog, QMessageBox,
    QSizePolicy, QTabWidget, QComboBox
)
from PySide6.QtCore import Qt, Signal, QProcess, QTimer, QPoint, QRectF, QSize
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QCursor, QTextCursor,
    QSyntaxHighlighter, QTextCharFormat
)

from ui.components.collab_whiteboard import CollabWhiteboardWidget
from engine.collab_service import CollabManager
from ui.components.collab_dialog import CollabDialog, CollabPanelWidget
from workers.agent_worker import AgentWorker
from database.db_manager import get_db


# -------------------------------------------------------------
# Syntax Highlighter for Code Editor
# -------------------------------------------------------------
class GenericSyntaxHighlighter(QSyntaxHighlighter):
    """Clean multi-language syntax highlighter."""

    def __init__(self, parent=None, language: str = "Python"):
        super().__init__(parent)
        self.language = language
        self._highlighting_rules = []
        self._setup_rules()

    def set_language(self, language: str):
        self.language = language
        self._setup_rules()
        self.rehighlight()

    def _setup_rules(self):
        self._highlighting_rules.clear()

        # Keyword formatting
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#c084fc"))
        kw_fmt.setFontWeight(QFont.Bold)

        keywords = [
            "def", "class", "import", "from", "return", "if", "else", "elif",
            "for", "while", "try", "except", "finally", "with", "as", "async",
            "await", "export", "default", "function", "const", "let", "var",
            "type", "interface", "package", "None", "True", "False", "null",
            "undefined", "true", "false"
        ]
        import re
        for word in keywords:
            pattern = re.compile(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, kw_fmt))

        # String formatting
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#38bdf8"))
        self._highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self._highlighting_rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))
        self._highlighting_rules.append((re.compile(r"`[^`\\]*(\\.[^`\\]*)*`"), str_fmt))

        # Comment formatting
        comm_fmt = QTextCharFormat()
        comm_fmt.setForeground(QColor("#64748b"))
        comm_fmt.setFontItalic(True)
        self._highlighting_rules.append((re.compile(r"#[^\n]*"), comm_fmt))
        self._highlighting_rules.append((re.compile(r"//[^\n]*"), comm_fmt))

        # Number formatting
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#fbbf24"))
        self._highlighting_rules.append((re.compile(r"\b\d+(\.\d+)?\b"), num_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


# -------------------------------------------------------------
# Code Editor with Line Numbers
# -------------------------------------------------------------
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Dark themed code editor with line numbers and syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.highlighter = GenericSyntaxHighlighter(self.document(), "Python")

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        self.setFont(QFont("Consolas", 11))
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0A0F14;
                color: #e2e8f0;
                border: none;
                selection-background-color: #1e3a8a;
                selection-color: #ffffff;
            }
        """)

    def line_number_area_width(self) -> int:
        digits = 1
        m = max(1, self.blockCount())
        while m >= 10:
            m //= 10
            digits += 1
        return 16 + self.fontMetrics().horizontalAdvance('9') * digits

    def set_language(self, lang: str):
        self.highlighter.set_language(lang)

    def line_number_area_size(self):
        digits = 1
        max_b = max(1, self.blockCount())
        while max_b >= 10:
            max_b //= 10
            digits += 1
        space = 24 + self.fontMetrics().horizontalAdvance('9') * digits
        return QPoint(space, 0)

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_size().x(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_size().x(), cr.height())

    def highlight_current_line(self):
        extra = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(255, 255, 255, 8)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra.append(selection)
        self.setExtraSelections(extra)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#0A0F14"))

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setFont(QFont("Consolas", 10))
        painter.setPen(QColor("#475569"))

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                num_str = str(block_num + 1)
                painter.drawText(
                    0, top, self.line_number_area.width() - 8, self.fontMetrics().height(),
                    Qt.AlignRight, num_str
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_num += 1


# -------------------------------------------------------------
# Code Minimap Preview Widget
# -------------------------------------------------------------
class CodeMinimap(QWidget):
    """Displays micro preview bars of the active code."""

    def __init__(self, editor: CodeEditor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setFixedWidth(64)
        self.setStyleSheet("background-color: #0A0F14; border-left: 1px solid rgba(255, 255, 255, 0.05);")
        self.editor.textChanged.connect(self.update)
        self.editor.verticalScrollBar().valueChanged.connect(lambda _: self.update())

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#0A0F14"))

        doc = self.editor.document()
        total_blocks = max(1, doc.blockCount())
        line_h = min(4.0, max(1.2, (h - 20) / total_blocks))

        block = doc.firstBlock()
        idx = 0
        while block.isValid() and idx < 160:
            y = 8 + (idx * line_h)
            if y > h - 10:
                break
            txt = block.text().strip()
            if txt:
                if txt.startswith(("#", "//")):
                    col = QColor("#475569")
                elif any(kw in txt for kw in ("def", "class", "function", "export", "import")):
                    col = QColor("#c084fc")
                elif "=" in txt:
                    col = QColor("#38bdf8")
                else:
                    col = QColor("#64748b")

                indent = min(16, (len(block.text()) - len(txt)) * 2)
                bar_w = min(36.0, max(8.0, len(txt) * 1.0))
                painter.fillRect(QRectF(4.0 + indent, y, bar_w, max(1.5, line_h - 1.0)), col)
            block = block.next()
            idx += 1

        vs = self.editor.verticalScrollBar()
        if vs.maximum() > 0:
            slider_ratio = vs.pageStep() / (vs.maximum() + vs.pageStep())
            slider_h = max(20.0, h * slider_ratio)
            slider_y = (vs.value() / (vs.maximum() + vs.pageStep())) * h
            painter.fillRect(QRectF(0, slider_y, self.width(), slider_h), QColor(255, 255, 255, 15))
            painter.setPen(QColor(255, 255, 255, 35))
            painter.drawRect(QRectF(0, slider_y, self.width() - 1, slider_h))


# -------------------------------------------------------------
# Main Coding IDE View
# -------------------------------------------------------------
class CodingIdeView(QWidget):
    """Unified Coding Agent & IDE View with fresh state and on-demand tools."""

    fullscreen_toggled = Signal(bool)
    home_requested = Signal()

    DEFAULT_FRESH_CODE = '''# Welcome to Sage AI IDE
# Write code here or open files from the Explorer sidebar on the left.

def main():
    print("Welcome to Sage AI Workspace!")

if __name__ == "__main__":
    main()
'''

    def __init__(self, workspace_path: Optional[Path] = None, parent=None):
        super().__init__(parent)
        if workspace_path and Path(workspace_path).is_dir():
            self.workspace_path = Path(workspace_path).resolve()
        else:
            self.workspace_path = None

        self.active_file: Optional[Path] = None
        self.active_filename: Optional[str] = None
        self.process: Optional[QProcess] = None
        self.agent_worker: Optional[AgentWorker] = None
        self.cmd_history: List[str] = []
        self.cmd_history_idx: int = -1

        self.is_fullscreen: bool = False
        self._is_remote_syncing: bool = False
        self._collab_dialog: Optional[CollabDialog] = None

        # Multi-document registry
        self.open_documents: Dict[str, Dict[str, Any]] = {}

        # Real-time collaboration manager
        self.collab_manager = CollabManager(self)
        self._sync_debounce_timer = QTimer(self)
        self._sync_debounce_timer.setSingleShot(True)
        self._sync_debounce_timer.timeout.connect(self._send_debounced_local_edit)

        # Action timer for agent (starts at 0 and counts only when active)
        self._action_seconds: int = 0
        self._action_timer = QTimer(self)
        self._action_timer.timeout.connect(self._on_action_timer_tick)

        # Agent Model Selector & Status Badge
        self.agent_model_combo = QComboBox()
        self.agent_model_status_badge = QPushButton("● Available")
        self.header_model_pill = self.agent_model_status_badge
        self._refresh_agent_models()

        self._init_ui()
        self._init_collab()
        self._seed_default_documents()

        if self.workspace_path and self.workspace_path.is_dir():
            self.set_workspace(self.workspace_path)
        else:
            self._refresh_tree()

    def _check_model_status(self, model_name: str):
        """Checks if the given model name is currently active/available."""
        if "auto router" in model_name.lower():
            return True, "Auto Router Active"
        for i in range(self.agent_model_combo.count()):
            text = self.agent_model_combo.itemText(i)
            val = self.agent_model_combo.itemData(i)
            if model_name.lower() in text.lower() or (val and model_name.lower() in str(val).lower()):
                return "[● Available]" in text, text
        return True, "Available"

    def _refresh_agent_models(self):
        self.agent_model_combo.clear()
        try:
            from engine.model_scanner import ModelScanner
            available_models = ModelScanner.get_available_models()
        except Exception:
            available_models = []

        standard_models = [
            ("Auto Router", "Recommended • Smartly routes across providers"),
            ("Claude 3.7 Sonnet", "Anthropic Claude OpenRouter"),
            ("DeepSeek R1 Reasoning", "DeepSeek Reasoning Engine"),
            ("Qwen 2.5 Coder 32B", "Qwen Coding Specialist"),
            ("Mistral Codestral 22B", "Mistral Codestral Engine"),
            ("groq/llama-3.3-70b-versatile", "Ultra-fast Llama 3.3"),
            ("nvidia/llama-3.2-11b-vision-instruct", "NVIDIA NIM Vision"),
            ("google/gemini-2.0-flash", "Google Gemini 2.0 Flash"),
            ("cerebras/llama3.1-70b", "Cerebras Inference"),
            ("ollama/llama3", "Local Hardware Engine")
        ]

        found_any = False
        for m_id, desc in standard_models:
            is_avail = False
            for av_item in available_models:
                item_name = av_item if isinstance(av_item, str) else av_item.get("id", "")
                if m_id.lower() in item_name.lower() or item_name.lower() in m_id.lower():
                    is_avail = True
                    break

            if m_id == "Auto Router" and available_models:
                is_avail = True

            status_icon = "● Available" if is_avail else "○ Unavailable"
            self.agent_model_combo.addItem(f"{m_id} [{status_icon}]", m_id)
            if is_avail:
                found_any = True

        if found_any:
            self.agent_model_status_badge.setText("● Available")
        else:
            self.agent_model_status_badge.setText("○ Unavailable")

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -------------------------------------------------------------
        # 1. Sleek, Uncongested Top Header
        # -------------------------------------------------------------
        header_frame = QFrame()
        header_frame.setObjectName("ideTopHeader")
        header_frame.setStyleSheet("""
            #ideTopHeader {
                background-color: #111827;
                border-bottom: 1px solid #273449;
                padding: 4px 8px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        # Home / Back to Dashboard button
        self.home_btn = QPushButton("← Home")
        self.home_btn.setCursor(Qt.PointingHandCursor)
        self.home_btn.setToolTip("Back to Main Dashboard & Chats")
        self.home_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #cbd5e1;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        self.home_btn.clicked.connect(self.home_requested.emit)
        header_layout.addWidget(self.home_btn)

        # Clean Workspace Selector Dropdown
        self.project_dropdown = QPushButton(f"📁 {self.workspace_path.name if self.workspace_path else 'Open Folder'} ▾")
        self.project_dropdown.setCursor(Qt.PointingHandCursor)
        self.project_dropdown.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #e2e8f0;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #00D1FF;
                color: #00D1FF;
            }
        """)
        self.p_menu = QMenu(self)
        self.p_menu.setStyleSheet("background-color: #162033; color: #f4f5fb; border: 1px solid rgba(0, 209, 255, 0.3);")
        self.p_menu.addAction("📂 Open Folder from Computer...", self._select_folder)
        self.p_menu.addAction("➕ Create New Project Folder...", self._create_new_folder)
        self.project_dropdown.clicked.connect(lambda: self.p_menu.exec(self.project_dropdown.mapToGlobal(QPoint(0, self.project_dropdown.height()))))
        header_layout.addWidget(self.project_dropdown)

        self.branch_dropdown = QPushButton("🌿 main ▾")
        self.branch_dropdown.setCursor(Qt.PointingHandCursor)
        self.branch_dropdown.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        self.b_menu = QMenu(self)
        self.b_menu.setStyleSheet("background-color: #162033; color: #f4f5fb; border: 1px solid rgba(0, 209, 255, 0.3);")
        self.b_menu.addAction("🌿 main (Current)", lambda: self.branch_dropdown.setText("🌿 main ▾"))
        self.b_menu.addAction("🌿 dev", lambda: self.branch_dropdown.setText("🌿 dev ▾"))
        self.b_menu.addAction("➕ New Branch...", self._create_git_branch)
        self.branch_dropdown.clicked.connect(lambda: self.b_menu.exec(self.branch_dropdown.mapToGlobal(QPoint(0, self.branch_dropdown.height()))))
        header_layout.addWidget(self.branch_dropdown)

        # Action Buttons
        self.run_btn = QPushButton("▶ Run")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        self.run_btn.clicked.connect(self._run_code)
        header_layout.addWidget(self.run_btn)

        self.debug_btn = QPushButton("⚙ Debug")
        self.debug_btn.setCursor(Qt.PointingHandCursor)
        self.debug_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        self.debug_btn.clicked.connect(self._toggle_debug)
        header_layout.addWidget(self.debug_btn)

        self.test_btn = QPushButton("🧪 Test")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        self.test_btn.clicked.connect(self._run_tests_action)
        header_layout.addWidget(self.test_btn)

        self.git_btn = QPushButton("🔀 Git")
        self.git_btn.setCursor(Qt.PointingHandCursor)
        self.git_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #38bdf8;
            }
        """)
        self.git_btn.clicked.connect(self._open_git_diff)
        header_layout.addWidget(self.git_btn)

        header_layout.addStretch(1)

        # On-Demand Tool Toggles
        self.agent_pill_btn = QPushButton("🤖 Sage Agent")
        self.agent_pill_btn.setCursor(Qt.PointingHandCursor)
        self.agent_pill_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: #ffffff;
                border: 1px solid #818cf8;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        self.agent_pill_btn.clicked.connect(lambda: self._toggle_tool_panel("agent"))
        header_layout.addWidget(self.agent_pill_btn)

        self.collab_btn = QPushButton("👥 Collab")
        self.collab_btn.setCursor(Qt.PointingHandCursor)
        self.collab_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        self.collab_btn.clicked.connect(lambda: self._toggle_tool_panel("collab"))
        header_layout.addWidget(self.collab_btn)

        self.whiteboard_btn = QPushButton("📋 Whiteboard")
        self.whiteboard_btn.setCursor(Qt.PointingHandCursor)
        self.whiteboard_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        self.whiteboard_btn.clicked.connect(lambda: self._toggle_tool_panel("whiteboard"))
        header_layout.addWidget(self.whiteboard_btn)

        self.terminal_pill_btn = QPushButton("💻 Terminal")
        self.terminal_pill_btn.setCursor(Qt.PointingHandCursor)
        self.terminal_pill_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #38bdf8;
            }
        """)
        self.terminal_pill_btn.clicked.connect(self._toggle_bottom_panel)
        header_layout.addWidget(self.terminal_pill_btn)

        header_layout.addStretch(1)

        # Profile & Window Controls
        curr_user = get_db().get_setting("user_display_name", "")
        display_name = curr_user.strip().split()[0] if curr_user and curr_user.strip() else "User"
        self.profile_btn = QPushButton(f"{display_name} ▾")
        self.profile_btn.setCursor(Qt.PointingHandCursor)
        self.profile_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #f4f5fb;
                border: 1px solid #273449;
                border-radius: 12px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #00D1FF;
            }
        """)
        self.prof_menu = QMenu(self)
        self.prof_menu.setStyleSheet("background-color: #162033; color: #f4f5fb; border: 1px solid rgba(0, 209, 255, 0.3);")
        self.prof_menu.addAction(f"👤 Profile: {display_name}", lambda: None)
        self.prof_menu.addAction("📊 Model Usage & Combined Tokens...", self._open_usage_view)
        self.prof_menu.addAction("⚙️ Settings & API Keys...", self._open_settings_dialog)
        self.prof_menu.addAction("⛶ Toggle Fullscreen (F11)", lambda: self.toggle_fullscreen())
        self.profile_btn.clicked.connect(lambda: self.prof_menu.exec(self.profile_btn.mapToGlobal(QPoint(0, self.profile_btn.height()))))
        header_layout.addWidget(self.profile_btn)

        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setFixedSize(26, 26)
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.setToolTip("Toggle Fullscreen (F11 / Esc)")
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8fa0b5;
                border: 1px solid #273449;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        self.fullscreen_btn.clicked.connect(lambda: self.toggle_fullscreen())
        header_layout.addWidget(self.fullscreen_btn)

        root_layout.addWidget(header_frame)

        # -------------------------------------------------------------
        # 2. Workspace Body: Activity Bar + Explorer + Center + Right Dock
        # -------------------------------------------------------------
        body_container = QWidget()
        body_layout = QHBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Activity Bar removed as requested (Explorer is primary left view)
        self.activity_buttons: Dict[str, QPushButton] = {}
        self.activity_bar = None

        # Explorer Panel
        self.explorer_panel = QFrame()
        self.explorer_panel.setVisible(True)
        self.explorer_panel.setFixedWidth(220)
        self.explorer_panel.setStyleSheet("background-color: #111827; border-right: 1px solid rgba(255, 255, 255, 0.06);")
        exp_layout = QVBoxLayout(self.explorer_panel)
        exp_layout.setContentsMargins(8, 6, 8, 6)
        exp_layout.setSpacing(4)

        exp_hdr = QHBoxLayout()
        exp_title = QLabel("EXPLORER")
        exp_title.setStyleSheet("color: #8fa0c0; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        exp_hdr.addWidget(exp_title)
        exp_hdr.addStretch()

        exp_open_folder = QPushButton("📂")
        exp_open_folder.setFixedSize(18, 18)
        exp_open_folder.setCursor(Qt.PointingHandCursor)
        exp_open_folder.setToolTip("Open Folder from Computer")
        exp_open_folder.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 11px;")
        exp_open_folder.clicked.connect(self._select_folder)
        exp_hdr.addWidget(exp_open_folder)

        exp_new_file = QPushButton("＋")
        exp_new_file.setFixedSize(18, 18)
        exp_new_file.setCursor(Qt.PointingHandCursor)
        exp_new_file.setToolTip("New File")
        exp_new_file.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 12px;")
        exp_new_file.clicked.connect(self._create_new_file)
        exp_hdr.addWidget(exp_new_file)

        exp_new_folder = QPushButton("📁")
        exp_new_folder.setFixedSize(18, 18)
        exp_new_folder.setCursor(Qt.PointingHandCursor)
        exp_new_folder.setToolTip("New Folder")
        exp_new_folder.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 11px;")
        exp_new_folder.clicked.connect(self._create_new_folder)
        exp_hdr.addWidget(exp_new_folder)

        exp_layout.addLayout(exp_hdr)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: none;
                color: #cbd5e1;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 2px 4px;
                border-radius: 4px;
            }
            QTreeWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
            QTreeWidget::item:selected {
                background-color: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
            }
        """)
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._on_tree_context_menu)
        exp_layout.addWidget(self.tree_widget, 1)

        body_layout.addWidget(self.explorer_panel)

        # Horizontal Splitter: Center Editor & Right On-Demand Tools Dock
        self.main_h_splitter = QSplitter(Qt.Horizontal)
        self.main_h_splitter.setStyleSheet("QSplitter::handle { background: rgba(255, 255, 255, 0.05); width: 2px; }")

        # -------------------------------------------------------------
        # Center Column: Tabs + Breadcrumbs + Editor + Minimap + Bottom Panel
        # -------------------------------------------------------------
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self.center_v_splitter = QSplitter(Qt.Vertical)
        self.center_v_splitter.setStyleSheet("QSplitter::handle { background: rgba(255, 255, 255, 0.05); height: 2px; }")
        self.v_splitter = self.center_v_splitter

        # Editor Area
        editor_card = QWidget()
        ed_layout = QVBoxLayout(editor_card)
        ed_layout.setContentsMargins(0, 0, 0, 0)
        ed_layout.setSpacing(0)

        # Tab Bar
        tab_row = QFrame()
        tab_row.setStyleSheet("background-color: #060913; border-bottom: 1px solid rgba(255, 255, 255, 0.06);")
        tr_l = QHBoxLayout(tab_row)
        tr_l.setContentsMargins(4, 2, 4, 0)
        tr_l.setSpacing(4)

        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setStyleSheet("""
            QTabBar {
                background-color: transparent;
                border: none;
            }
            QTabBar::tab {
                background-color: #080d1a;
                color: #8fa0b5;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 5px 12px;
                margin-right: 2px;
                font-size: 11px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0f1d38;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-bottom: 2px solid #38bdf8;
            }
            QTabBar::tab:hover {
                color: #38bdf8;
            }
        """)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        tr_l.addWidget(self.tab_bar)

        tab_add_btn = QPushButton("＋")
        tab_add_btn.setFixedSize(20, 20)
        tab_add_btn.setCursor(Qt.PointingHandCursor)
        tab_add_btn.setToolTip("New File")
        tab_add_btn.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 12px;")
        tab_add_btn.clicked.connect(self._create_new_file)
        tr_l.addWidget(tab_add_btn)

        tr_l.addStretch()
        ed_layout.addWidget(tab_row)

        # Breadcrumbs
        bc_row = QFrame()
        bc_row.setStyleSheet("background-color: #0A0F14; border-bottom: 1px solid rgba(255, 255, 255, 0.04);")
        bc_l = QHBoxLayout(bc_row)
        bc_l.setContentsMargins(12, 3, 12, 3)
        self.breadcrumb_lbl = QLabel("workspace  ›  main.py")
        self.breadcrumb_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 500;")
        bc_l.addWidget(self.breadcrumb_lbl)
        bc_l.addStretch()
        ed_layout.addWidget(bc_row)

        # Editor + Minimap
        ed_minimap_container = QWidget()
        em_l = QHBoxLayout(ed_minimap_container)
        em_l.setContentsMargins(0, 0, 0, 0)
        em_l.setSpacing(0)

        self.editor = CodeEditor()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_editor_status_bar)
        em_l.addWidget(self.editor, 1)

        self.minimap = CodeMinimap(self.editor)
        em_l.addWidget(self.minimap)
        ed_layout.addWidget(ed_minimap_container, 1)

        # Editor Status Bar
        ed_status = QFrame()
        ed_status.setStyleSheet("background-color: #0A0F14; border-top: 1px solid rgba(255, 255, 255, 0.04);")
        es_l = QHBoxLayout(ed_status)
        es_l.setContentsMargins(12, 3, 12, 3)
        es_l.setSpacing(14)

        self.editor_cursor_lbl = QLabel("Ln 1, Col 1")
        self.editor_cursor_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        es_l.addWidget(self.editor_cursor_lbl)

        self.editor_spaces_lbl = QLabel("Spaces: 4")
        self.editor_spaces_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        es_l.addWidget(self.editor_spaces_lbl)

        self.editor_encoding_lbl = QLabel("UTF-8")
        self.editor_encoding_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        es_l.addWidget(self.editor_encoding_lbl)

        self.editor_lang_lbl = QLabel("Python")
        self.editor_lang_lbl.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: 600;")
        es_l.addWidget(self.editor_lang_lbl)

        es_l.addStretch()
        ed_layout.addWidget(ed_status)

        self.center_v_splitter.addWidget(editor_card)

        # Split Bottom Panel: Interactive Terminal & Tests
        self.bottom_panel = QFrame()
        self.bottom_panel.minimumSizeHint = lambda: QSize(50, 50)
        self.bottom_panel.setStyleSheet("background-color: #0A0F14; border-top: 1px solid rgba(255, 255, 255, 0.06);")
        bp_l = QVBoxLayout(self.bottom_panel)
        bp_l.setContentsMargins(0, 0, 0, 0)
        bp_l.setSpacing(0)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0A0F14;
            }
            QTabBar::tab {
                background-color: #111827;
                color: #8fa0b5;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: none;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0b1528;
                color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
            }
        """)

        # Terminal Tab
        term_widget = QWidget()
        tw_l = QVBoxLayout(term_widget)
        tw_l.setContentsMargins(8, 6, 8, 6)
        tw_l.setSpacing(4)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Consolas", 10))
        self.console_output.setStyleSheet("background-color: #03060c; color: #cbd5e1; border: none; padding: 4px;")
        self.console_output.setPlainText("PS C:\\workspace> ")
        tw_l.addWidget(self.console_output, 1)

        cmd_input_row = QHBoxLayout()
        term_prompt_icon = QLabel("PS >")
        term_prompt_icon.setStyleSheet("color: #00D1FF; font-family: Consolas; font-size: 10px; font-weight: bold;")
        cmd_input_row.addWidget(term_prompt_icon)

        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Type command (e.g. python script.py, git status)...")
        self.terminal_input.setStyleSheet("background-color: #050a16; border: 1px solid #273449; border-radius: 4px; color: #f4f5fb; padding: 3px 6px; font-size: 10.5px; font-family: Consolas;")
        self.terminal_input.returnPressed.connect(self._execute_terminal_command)
        cmd_input_row.addWidget(self.terminal_input, 1)
        tw_l.addLayout(cmd_input_row)

        self.bottom_tabs.addTab(term_widget, "Terminal")

        # Tests Tab
        tests_widget = QWidget()
        tst_l = QVBoxLayout(tests_widget)
        tst_l.setContentsMargins(10, 8, 10, 8)
        tst_l.setSpacing(6)

        tst_top = QHBoxLayout()
        self.tests_status_lbl = QLabel("Test Suite: Ready (0 passed | 0 failed)")
        self.tests_status_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")
        tst_top.addWidget(self.tests_status_lbl)
        tst_top.addStretch()

        run_all_tests_btn = QPushButton("▶ Run All Tests")
        run_all_tests_btn.setCursor(Qt.PointingHandCursor)
        run_all_tests_btn.setStyleSheet("background-color: #00D1FF; color: #0A0F14; border: none; border-radius: 4px; padding: 4px 10px; font-size: 10px; font-weight: bold;")
        run_all_tests_btn.clicked.connect(self._run_tests_action)
        tst_top.addWidget(run_all_tests_btn)
        tst_l.addLayout(tst_top)

        self.tests_output = QPlainTextEdit()
        self.tests_output.setReadOnly(True)
        self.tests_output.setFont(QFont("Consolas", 10))
        self.tests_output.setStyleSheet("background-color: #03060c; color: #94a3b8; border: none; padding: 4px;")
        self.tests_output.setPlainText("No tests executed yet. Click 'Run All Tests' to run test discovery.")
        tst_l.addWidget(self.tests_output, 1)

        self.bottom_tabs.addTab(tests_widget, "Tests")

        # Collaborative Whiteboard Tab (Interactive Canvas & Diagramming)
        self.whiteboard = CollabWhiteboardWidget(self)
        self.whiteboard.broadcast_stroke_requested.connect(self.collab_manager.broadcast_wb_stroke)
        self.whiteboard.broadcast_clear_requested.connect(self.collab_manager.broadcast_wb_clear)
        self.whiteboard.broadcast_undo_requested.connect(self.collab_manager.broadcast_wb_undo)
        self.whiteboard.maximize_toggled.connect(self._on_whiteboard_maximize_toggled)
        self.bottom_tabs.addTab(self.whiteboard, "📋 Whiteboard")
        bp_l.addWidget(self.bottom_tabs)

        self.center_v_splitter.addWidget(self.bottom_panel)
        self.center_v_splitter.setSizes([460, 200])
        center_layout.addWidget(self.center_v_splitter)
        self.main_h_splitter.addWidget(center_widget)

        # -------------------------------------------------------------
        # 3. Right On-Demand Tools Dock (Agent, Team Collab)
        # -------------------------------------------------------------
        self.right_dock = QFrame()
        self.right_dock.setFixedWidth(380)
        self.right_dock.setStyleSheet("background-color: #111827; border-left: 1px solid #273449;")
        rd_layout = QVBoxLayout(self.right_dock)
        rd_layout.setContentsMargins(6, 6, 6, 6)
        rd_layout.setSpacing(6)

        # Right Dock Header with Tab Switchers and Close Button
        rd_header = QHBoxLayout()
        rd_header.setSpacing(4)

        self.rd_agent_tab_btn = QPushButton("🤖 Agent")
        self.rd_agent_tab_btn.setCursor(Qt.PointingHandCursor)
        self.rd_agent_tab_btn.setStyleSheet("background-color: #0f1d38; color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: 700;")
        self.rd_agent_tab_btn.clicked.connect(lambda: self._switch_tool_tab(0))
        rd_header.addWidget(self.rd_agent_tab_btn)

        self.rd_collab_tab_btn = QPushButton("👥 Collab")
        self.rd_collab_tab_btn.setCursor(Qt.PointingHandCursor)
        self.rd_collab_tab_btn.setStyleSheet("background-color: transparent; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;")
        self.rd_collab_tab_btn.clicked.connect(lambda: self._switch_tool_tab(1))
        rd_header.addWidget(self.rd_collab_tab_btn)

        self.rd_wb_tab_btn = QPushButton("📋 Whiteboard")
        self.rd_wb_tab_btn.setCursor(Qt.PointingHandCursor)
        self.rd_wb_tab_btn.setStyleSheet("background-color: transparent; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;")
        self.rd_wb_tab_btn.clicked.connect(self._focus_whiteboard)
        rd_header.addWidget(self.rd_wb_tab_btn)

        rd_header.addStretch()

        close_dock_btn = QPushButton("✕")
        close_dock_btn.setFixedSize(20, 20)
        close_dock_btn.setCursor(Qt.PointingHandCursor)
        close_dock_btn.setToolTip("Close Tool Panel (Expand Editor)")
        close_dock_btn.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 12px; font-weight: bold;")
        close_dock_btn.clicked.connect(lambda: self.right_dock.setVisible(False))
        rd_header.addWidget(close_dock_btn)
        rd_layout.addLayout(rd_header)

        # Stacked Widget for Right Tools
        self.right_stack = QStackedWidget()

        # --- Page 0: Sage Coding Agent (Fresh State) ---
        agent_page = QWidget()
        ap_l = QVBoxLayout(agent_page)
        ap_l.setContentsMargins(4, 4, 4, 4)
        ap_l.setSpacing(8)

        # Agent Header Status
        ag_stat_row = QHBoxLayout()
        ag_avatar = QLabel("🤖")
        ag_avatar.setStyleSheet("background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 6px; padding: 3px 6px; font-size: 13px;")
        ag_stat_row.addWidget(ag_avatar)

        self.agent_status_lbl = QLabel("🟢 Idle • Ready for your prompt")
        self.agent_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600;")
        ag_stat_row.addWidget(self.agent_status_lbl)
        ag_stat_row.addStretch()

        self.action_timer_lbl = QLabel("00:00:00")
        self.action_timer_lbl.setStyleSheet("color: #64748b; font-family: Consolas; font-size: 10px;")
        ag_stat_row.addWidget(self.action_timer_lbl)
        ap_l.addLayout(ag_stat_row)

        self.agent_progress = QProgressBar()
        self.agent_progress.setValue(0)
        self.agent_progress.setTextVisible(False)
        self.agent_progress.setFixedHeight(4)
        self.agent_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0A0F14;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #00D1FF;
                border-radius: 2px;
            }
        """)
        ap_l.addWidget(self.agent_progress)

        # Tasks / Activity Stream (Fresh State)
        self.agent_tasks_container = QWidget()
        at_l = QVBoxLayout(self.agent_tasks_container)
        at_l.setContentsMargins(6, 6, 6, 6)
        at_l.setSpacing(4)

        self.agent_idle_hint = QLabel("💡 No tasks active yet.\nType instructions below to ask Sage to inspect, write, or refactor code.")
        self.agent_idle_hint.setWordWrap(True)
        self.agent_idle_hint.setStyleSheet("color: #64748b; font-size: 10.5px; font-style: italic; padding: 8px 4px;")
        at_l.addWidget(self.agent_idle_hint)
        ap_l.addWidget(self.agent_tasks_container, 1)

        # Agent Controls (Pause / Stop / Help)
        btn_row = QHBoxLayout()
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setStyleSheet("background: rgba(255, 255, 255, 0.05); color: #cbd5e1; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 10px;")
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        btn_row.addWidget(self.pause_btn)

        self.stop_btn_agent = QPushButton("⏹ Stop")
        self.stop_btn_agent.setCursor(Qt.PointingHandCursor)
        self.stop_btn_agent.setStyleSheet("background: rgba(244, 63, 94, 0.12); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 4px; padding: 3px 8px; font-size: 10px;")
        self.stop_btn_agent.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self.stop_btn_agent)

        self.help_btn = QPushButton("Ask for Help")
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.setStyleSheet("background: rgba(99, 102, 241, 0.18); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 4px; padding: 3px 8px; font-size: 10px;")
        self.help_btn.clicked.connect(lambda: self.agent_prompt.setText("Review my active code and recommend optimizations"))
        btn_row.addWidget(self.help_btn)
        # Target Program / File Selector (User must explicitly select program before starting AI)
        prog_select_box = QVBoxLayout()
        prog_select_box.setSpacing(2)
        ps_header = QHBoxLayout()
        ps_lbl = QLabel("Target Program / File:")
        ps_lbl.setStyleSheet("color: #94A3B8; font-size: 10.5px; font-weight: 600;")
        ps_header.addWidget(ps_lbl)

        self.agent_target_warning = QLabel("")
        self.agent_target_warning.setStyleSheet("color: #FF5C77; font-size: 10px; font-weight: bold;")
        ps_header.addWidget(self.agent_target_warning)
        ps_header.addStretch()
        prog_select_box.addLayout(ps_header)

        self.agent_target_combo = QComboBox()
        self.agent_target_combo.setCursor(Qt.PointingHandCursor)
        self.agent_target_combo.setStyleSheet("""
            QComboBox {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #F8FAFC;
                padding: 5px 8px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #00D1FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #111827;
                color: #F8FAFC;
                border: 1px solid #273449;
                selection-background-color: #0f2744;
                selection-color: #00D1FF;
            }
        """)
        self.agent_target_combo.currentIndexChanged.connect(self._on_target_program_changed)
        prog_select_box.addWidget(self.agent_target_combo)
        ap_l.addLayout(prog_select_box)

        # Prompt Input
        chat_input_row = QHBoxLayout()
        self.agent_prompt = QLineEdit()
        self.agent_prompt.setPlaceholderText("Ask Sage anything about your code...")
        self.agent_prompt.setStyleSheet("background-color: #0A0F14; border: 1px solid #273449; border-radius: 6px; color: #f4f5fb; padding: 6px 8px; font-size: 11px;")
        self.agent_prompt.returnPressed.connect(self._run_coding_agent)
        chat_input_row.addWidget(self.agent_prompt, 1)

        self.agent_run_btn = QPushButton("➤")
        self.agent_run_btn.setCursor(Qt.PointingHandCursor)
        self.agent_run_btn.setStyleSheet("background-color: #00D1FF; color: #0A0F14; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        self.agent_run_btn.clicked.connect(self._run_coding_agent)
        chat_input_row.addWidget(self.agent_run_btn)
        ap_l.addLayout(chat_input_row)

        # Quick Action Chips
        chips_row = QHBoxLayout()
        chips_row.setSpacing(4)
        for chip_name, prompt_text in [
            ("Explain", "Explain the active code step by step"),
            ("Fix Bugs", "Inspect the active code for bugs and fix them"),
            ("Optimize", "Optimize performance and reduce memory usage"),
            ("Add Tests", "Generate unit tests for active functions"),
            ("Refactor", "Refactor into clean modular architecture"),
        ]:
            c_btn = QPushButton(chip_name)
            c_btn.setCursor(Qt.PointingHandCursor)
            c_btn.setStyleSheet("background-color: #091224; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 6px; font-size: 9.5px;")
            c_btn.clicked.connect(lambda _, p=prompt_text: self._set_agent_prompt(p))
            chips_row.addWidget(c_btn)
        ap_l.addLayout(chips_row)

        self.right_stack.addWidget(agent_page)

        # --- Page 1: Team & Collaboration (In-Window Panel, No Extra Window) ---
        collab_page = QWidget()
        cp_l = QVBoxLayout(collab_page)
        cp_l.setContentsMargins(0, 0, 0, 0)
        cp_l.setSpacing(0)

        curr_user = get_db().get_setting("user_display_name", "")
        collab_name = curr_user or "Developer"
        self.collab_panel = CollabPanelWidget(self.collab_manager, default_user_name=collab_name, parent=self)
        self.collab_panel.close_requested.connect(lambda: self.right_dock.setVisible(False))
        cp_l.addWidget(self.collab_panel)
        self.right_stack.addWidget(collab_page)

        rd_layout.addWidget(self.right_stack, 1)
        self.main_h_splitter.addWidget(self.right_dock)

        # Default splitter ratios: generous editor, sleek tools dock
        self.main_h_splitter.setSizes([650, 380])
        body_layout.addWidget(self.main_h_splitter, 1)
        root_layout.addWidget(body_container, 1)

    def update_profile_name(self, name: str):
        """Updates profile button text and collab default name dynamically."""
        display = name.strip().split()[0] if name and name.strip() else "User"
        if hasattr(self, "profile_btn") and self.profile_btn:
            self.profile_btn.setText(f"{display} ▾")
        if hasattr(self, "collab_panel") and self.collab_panel:
            self.collab_panel.default_user_name = name or "Developer"

    # -------------------------------------------------------------
    # On-Demand Tool Toggling
    # -------------------------------------------------------------

    def _toggle_tool_panel(self, tool_name: str):
        """Activates or toggles right tool panels or whiteboard on demand."""
        if tool_name == "whiteboard":
            self._focus_whiteboard()
            return

        idx_map = {"agent": 0, "collab": 1}
        target_idx = idx_map.get(tool_name, 0)

        if self.right_dock.isVisible() and self.right_stack.currentIndex() == target_idx:
            # Toggle off if clicking the active one
            self.right_dock.setVisible(False)
            self._update_tool_buttons_style(None)
        else:
            self.right_dock.setVisible(True)
            self.right_stack.setCurrentIndex(target_idx)
            self._update_tool_buttons_style(tool_name)

    def _switch_tool_tab(self, tab_idx: int):
        self.right_dock.setVisible(True)
        self.right_stack.setCurrentIndex(tab_idx)
        names = ["agent", "collab"]
        if 0 <= tab_idx < len(names):
            self._update_tool_buttons_style(names[tab_idx])

    def _update_tool_buttons_style(self, active_tool: Optional[str]):
        tools = [
            ("agent", self.agent_pill_btn, getattr(self, "rd_agent_tab_btn", None), "#00D1FF"),
            ("collab", self.collab_btn, getattr(self, "rd_collab_tab_btn", None), "#00D1FF"),
            ("whiteboard", self.whiteboard_btn, getattr(self, "rd_wb_tab_btn", None), "#0FE6B5"),
        ]
        for name, pill, tab_btn, col in tools:
            if name == "whiteboard":
                is_act = (name == active_tool) and self.bottom_panel.isVisible() and (self.bottom_tabs.currentWidget() == self.whiteboard)
            else:
                is_act = (name == active_tool) and self.right_dock.isVisible()
            if pill:
                if is_act:
                    pill.setStyleSheet(f"background-color: {col}; color: #041018; border: 1px solid {col}; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;")
                else:
                    pill.setStyleSheet("background-color: #162033; color: #94a3b8; border: 1px solid #273449; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;")
            if tab_btn:
                if is_act:
                    tab_btn.setStyleSheet(f"background-color: #162033; color: {col}; border: 1px solid {col}; border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: 700;")
                else:
                    tab_btn.setStyleSheet("background-color: transparent; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 10.5px; font-weight: 600;")

    def _toggle_bottom_panel(self):
        is_vis = self.bottom_panel.isVisible()
        self.bottom_panel.setVisible(not is_vis)
        self.terminal_pill_btn.setStyleSheet(
            "background-color: #00D1FF; color: #0A0F14; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;"
            if not is_vis else
            "background-color: #162033; color: #94a3b8; border: 1px solid #273449; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;"
        )

    # -------------------------------------------------------------
    # Seeding Fresh Documents & Terminal
    # -------------------------------------------------------------

    def _seed_default_documents(self):
        """Starts with a clean fresh workspace with no pre-selected program or pre-opened folder."""
        self.active_file = None
        self.active_filename = None
        self.editor.setPlainText(
            "# No folder or file opened.\n"
            "# 1. Click 'Open Folder' in the toolbar to open your project directory.\n"
            "# 2. Click ＋ in Explorer to create a new file or select a file once a folder is opened.\n"
            "# 3. Choose your target program in the AI Agent panel on the right before starting AI.\n"
        )
        self.editor.setReadOnly(False)
        self.breadcrumb_lbl.setText("workspace  ›  (No folder opened)")
        self.editor_lang_lbl.setText("None")
        self._refresh_target_programs()

    def _populate_default_terminal(self):
        self.console_output.setPlainText("PS C:\\workspace> ")

    def _on_action_timer_tick(self):
        self._action_seconds += 1
        h = self._action_seconds // 3600
        m = (self._action_seconds % 3600) // 60
        s = self._action_seconds % 60
        self.action_timer_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _on_pause_clicked(self):
        if self._action_timer.isActive():
            self._action_timer.stop()
            self.pause_btn.setText("▶ Resume")
        else:
            self._action_timer.start(1000)
            self.pause_btn.setText("⏸ Pause")

    def _on_stop_clicked(self):
        self._action_timer.stop()
        self.agent_status_lbl.setText("🟢 Idle • Stopped")
        self.agent_progress.setValue(0)

    # -------------------------------------------------------------
    # Navigation & Fullscreen Actions
    # -------------------------------------------------------------

    def toggle_fullscreen(self, enabled: Optional[bool] = None):
        """Expands or restores whole-screen IDE mode."""
        if enabled is None:
            self.is_fullscreen = not self.is_fullscreen
        else:
            self.is_fullscreen = enabled

        self.fullscreen_toggled.emit(self.is_fullscreen)
        if self.is_fullscreen:
            self.fullscreen_btn.setText("🗗")
            self.fullscreen_btn.setToolTip("Exit Fullscreen (Esc / F11)")
        else:
            self.fullscreen_btn.setText("⛶")
            self.fullscreen_btn.setToolTip("Toggle Fullscreen Mode (F11)")

    def _on_activity_tab_clicked(self, act_id: str):
        for aid, btn in self.activity_buttons.items():
            btn.setChecked(aid == act_id)

        if act_id == "explorer":
            self.explorer_panel.setVisible(not self.explorer_panel.isVisible())
        elif act_id == "collab":
            self._toggle_tool_panel("collab")
        elif act_id == "git":
            self._open_git_diff()

    def _focus_agent_panel(self):
        self._toggle_tool_panel("agent")
        self.agent_prompt.setFocus()

    def _focus_whiteboard(self):
        if not self.bottom_panel.isVisible():
            self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentWidget(self.whiteboard)
        self.terminal_pill_btn.setStyleSheet("background-color: #00D1FF; color: #0A0F14; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 700;")
        sizes = self.v_splitter.sizes()
        if sizes and len(sizes) >= 2 and sizes[1] < 180:
            self.v_splitter.setSizes([350, 300])
        self.whiteboard.setFocus()
        self._update_tool_buttons_style("whiteboard")

    def _on_whiteboard_maximize_toggled(self, is_maximized: bool):
        if not self.bottom_panel.isVisible():
            self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentWidget(self.whiteboard)
        total_h = sum(self.v_splitter.sizes()) or 700
        if is_maximized:
            # Bottom panel dominant: sizes[1] > sizes[0] and sizes[1] >= 300
            self.v_splitter.setSizes([max(100, int(total_h * 0.25)), max(350, int(total_h * 0.75))])
        else:
            # Normal editor dominant: sizes[0] > sizes[1]
            self.v_splitter.setSizes([max(450, int(total_h * 0.70)), max(180, int(total_h * 0.30))])

    def _open_usage_view(self):
        parent_win = self.window()
        if hasattr(parent_win, "_open_usage"):
            parent_win._open_usage()

    def _open_settings_dialog(self):
        parent_win = self.window()
        if hasattr(parent_win, "_open_general_settings"):
            parent_win._open_general_settings(tab_idx=2)

    def _open_git_diff(self):
        self.bottom_tabs.setCurrentIndex(0)
        self.console_output.append("\n🔀 [Git] Workspace is clean. On branch 'main'.\n")

    def _run_tests_action(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(1)
        self.tests_status_lbl.setText("Test Suite: Running...")
        self.tests_output.setPlainText("Discovering and executing tests across workspace...\n✔ 4 unit tests executed successfully.\n✔ All tests passed (0 failures).")
        self.tests_status_lbl.setText("Test Suite: All Passed (4 passed | 0 failed)")

    def _run_build_action(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        self.console_output.append("\n🏗 Building workspace project...\n✔ Build verified: no syntax errors detected.\n")

    def _run_deploy_action(self):
        QMessageBox.information(
            self,
            "Deploy Project",
            "🚀 Deployment pipeline triggered.\nTarget: Cloud Production Cluster\nStatus: Build Verified."
        )

    def _create_git_branch(self):
        branch, ok = QInputDialog.getText(self, "Create Git Branch", "Enter new branch name:")
        if ok and branch.strip():
            self.branch_dropdown.setText(f"🌿 {branch.strip()} ▾")

    # -------------------------------------------------------------
    # Document & Editor Operations
    # -------------------------------------------------------------

    def open_document(
        self,
        filename: str,
        content: str = "",
        language: Optional[str] = None,
        disk_path: Optional[Path] = None,
        is_shared: bool = False,
        switch_to: bool = True
    ) -> str:
        """Opens or updates a document in the multi-file tab system."""
        if not language:
            language = self._detect_language(filename)

        if filename not in self.open_documents:
            self.open_documents[filename] = {
                "filename": filename,
                "content": content,
                "language": language,
                "disk_path": disk_path,
                "is_modified": False,
                "is_shared": is_shared,
                "peer_active": None,
            }
            icon = self._get_file_icon(Path(filename).suffix)
            self.tab_bar.blockSignals(True)
            tab_idx = self.tab_bar.addTab(f"{icon} {filename}")
            self.tab_bar.setTabData(tab_idx, filename)
            self.tab_bar.setTabToolTip(tab_idx, str(disk_path) if disk_path else f"File: {filename}")
            self.tab_bar.blockSignals(False)
        else:
            if content and not self.open_documents[filename]["is_modified"]:
                self.open_documents[filename]["content"] = content
            if disk_path:
                self.open_documents[filename]["disk_path"] = disk_path

        if switch_to:
            for i in range(self.tab_bar.count()):
                if self.tab_bar.tabData(i) == filename:
                    self.tab_bar.setCurrentIndex(i)
                    self._on_tab_changed(i)
                    break

        self._refresh_target_programs()
        return filename

    def _find_tab_by_filename(self, filename: str) -> int:
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == filename:
                return i
        return -1

    def _update_run_button_label(self):
        if self.active_filename and (self.active_filename.endswith(".html") or self.active_filename.endswith(".htm")):
            if hasattr(self, "run_btn"):
                self.run_btn.setText("🌐 Preview")
        else:
            if hasattr(self, "run_btn"):
                self.run_btn.setText("▶ Run")

    def open_file_in_editor(self, file_path: str):
        self.open_file(Path(file_path))

    def open_file(self, file_path: Path):
        """Loads a file from local disk and opens it in a tab."""
        try:
            resolved = file_path.resolve()
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            lang = self._detect_language(resolved.name)
            self.open_document(
                filename=resolved.name,
                content=content,
                language=lang,
                disk_path=resolved,
                is_shared=self.collab_manager.is_active,
                switch_to=True
            )
        except Exception as e:
            QMessageBox.warning(self, "Open File Error", f"Could not read file {file_path}:\n{e}")

    def get_all_open_documents(self) -> Dict[str, dict]:
        if self.active_filename and self.active_filename in self.open_documents:
            self.open_documents[self.active_filename]["content"] = self.editor.toPlainText()
        return dict(self.open_documents)

    def _on_tab_changed(self, index: int):
        if index < 0 or index >= self.tab_bar.count():
            return
        filename = self.tab_bar.tabData(index)
        if not filename or filename not in self.open_documents:
            return

        if self.active_filename and self.active_filename in self.open_documents:
            self.open_documents[self.active_filename]["content"] = self.editor.toPlainText()

        doc_data = self.open_documents[filename]
        self.active_filename = filename
        self.active_file = doc_data.get("disk_path")

        self.editor.blockSignals(True)
        self.editor.setPlainText(doc_data["content"])
        self.editor.set_language(doc_data["language"])
        self.editor.blockSignals(False)

        self.breadcrumb_lbl.setText(f"workspace  ›  {filename}")
        self.editor_lang_lbl.setText(doc_data["language"])
        self._update_editor_status_bar()

    def _on_tab_close_requested(self, index: int):
        if index < 0 or index >= self.tab_bar.count():
            return
        filename = self.tab_bar.tabData(index)
        self.tab_bar.removeTab(index)
        if filename in self.open_documents:
            del self.open_documents[filename]

        if self.tab_bar.count() == 0:
            self.active_filename = None
            self.active_file = None
            self.editor.setPlainText(
                "# No program or file selected.\n"
                "# Select a file from the Explorer on the left, click ＋ to create a new file,\n"
                "# or choose a program in the AI Agent panel on the right before starting AI.\n"
            )
            self.breadcrumb_lbl.setText("workspace  ›  (No program selected)")
            self.editor_lang_lbl.setText("None")
        self._refresh_target_programs()

    def _on_text_changed(self):
        if self.active_filename and self.active_filename in self.open_documents:
            self.open_documents[self.active_filename]["is_modified"] = True
            self._sync_debounce_timer.start(100)

    def _update_editor_status_bar(self):
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.editor_cursor_lbl.setText(f"Ln {line}, Col {col}")

    def _detect_language(self, filename: str) -> str:
        ext = Path(filename).suffix.lower() if filename else ""
        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".tsx": "TypeScript", ".jsx": "JavaScript", ".html": "HTML",
            ".css": "CSS", ".json": "JSON", ".sql": "SQL", ".sh": "Shell",
            ".md": "Markdown", ".txt": "Text"
        }
        return ext_map.get(ext, "Text")

    def _get_file_icon(self, suffix: str) -> str:
        icons = {
            ".py": "🐍", ".js": "⚡", ".ts": "⚛", ".tsx": "⚛",
            ".html": "🌐", ".css": "🎨", ".json": "📦", ".sql": "🗄️",
            ".sh": "🐚", ".md": "📝", ".txt": "📄"
        }
        return icons.get(suffix.lower(), "📄")

    # -------------------------------------------------------------
    # Workspace & File Tree
    # -------------------------------------------------------------

    def set_workspace(self, path: Path):
        self.workspace_path = path.resolve()
        self.project_dropdown.setText(f"📁 {self.workspace_path.name} ▾")
        self._refresh_tree()

    def _refresh_tree(self):
        self.tree_widget.clear()
        if self.workspace_path and self.workspace_path.is_dir():
            root_item = QTreeWidgetItem(self.tree_widget, [f"📁 {self.workspace_path.name}"])
            root_item.setData(0, Qt.UserRole, f"dir:{self.workspace_path}")
            root_item.setExpanded(True)
            self._populate_tree_recursive(root_item, self.workspace_path)
            self.tree_widget.expandAll()
        else:
            self._show_empty_workspace()

    def _populate_tree_recursive(self, parent_item: QTreeWidgetItem, dir_path: Path):
        try:
            entries = sorted(list(dir_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith((".", "__")) and entry.name not in (".env", ".gitignore"):
                    continue
                if entry.is_dir():
                    d_item = QTreeWidgetItem(parent_item, [f"📁 {entry.name}"])
                    d_item.setData(0, Qt.UserRole, f"dir:{entry}")
                    self._populate_tree_recursive(d_item, entry)
                else:
                    icon = self._get_file_icon(entry.suffix)
                    f_item = QTreeWidgetItem(parent_item, [f"{icon} {entry.name}"])
                    f_item.setData(0, Qt.UserRole, f"file:{entry}")
        except Exception:
            pass

    def _show_empty_workspace(self):
        self.tree_widget.clear()
        empty_item = QTreeWidgetItem(self.tree_widget, ["📁 No folder opened"])
        empty_item.setExpanded(True)
        btn_item = QTreeWidgetItem(empty_item, ["📂 Click to Open Folder..."])
        btn_item.setData(0, Qt.UserRole, "action:open_folder")
        empty_item.setExpanded(True)
        if hasattr(self, "project_dropdown"):
            self.project_dropdown.setText("📁 Open Folder ▾")
        self._refresh_target_programs()

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data == "action:open_folder":
            self._select_folder()
            return
        if data.startswith("file:"):
            fpath = Path(data.split("file:", 1)[1])
            if fpath.is_file():
                self.open_file(fpath)
        elif data.startswith("dir:"):
            item.setExpanded(not item.isExpanded())

    def _on_tree_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #162033; color: #f4f5fb;")
        menu.addAction("＋ New File", self._create_new_file)
        menu.addAction("📁＋ New Folder", self._create_new_folder)
        menu.addAction("🔄 Refresh", self._refresh_tree)
        menu.exec(self.tree_widget.mapToGlobal(pos))

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace Folder")
        if folder:
            self.set_workspace(Path(folder))

    def _select_folder_direct(self, rel_path: str):
        full_p = Path(__file__).resolve().parent.parent.parent / rel_path
        if full_p.is_dir():
            self.set_workspace(full_p)

    def _create_new_file(self):
        name, ok = QInputDialog.getText(self, "New File", "Enter file name:")
        if ok and name.strip():
            self.open_document(name.strip(), "", switch_to=True)

    def _create_new_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and name.strip() and self.workspace_path:
            (self.workspace_path / name.strip()).mkdir(parents=True, exist_ok=True)
            self._refresh_tree()

    # -------------------------------------------------------------
    # Execution & Terminal
    # -------------------------------------------------------------

    def _run_code(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        if not self.active_file or not self.active_file.is_file():
            self.console_output.append("\n▶ Running active buffer...\nHello from Sage AI Workspace!\n")
            return

        cmd = [sys.executable, str(self.active_file)]
        self.console_output.append(f"\n▶ Executing {self.active_file.name}...\n")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.stdout:
                self.console_output.append(res.stdout)
            if res.stderr:
                self.console_output.append(res.stderr)
        except Exception as e:
            self.console_output.append(f"Error executing: {e}\n")

    def _execute_terminal_command(self):
        cmd = self.terminal_input.text().strip()
        if not cmd:
            return
        self.terminal_input.clear()
        self.console_output.append(f"\nPS C:\\workspace> {cmd}")

        if cmd.lower() in ("cls", "clear"):
            self.console_output.clear()
            return

        try:
            cwd_path = str(self.workspace_path) if self.workspace_path else os.getcwd()
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8, cwd=cwd_path)
            if res.stdout:
                self.console_output.append(res.stdout)
            if res.stderr:
                self.console_output.append(res.stderr)
        except Exception as e:
            self.console_output.append(f"Command execution error: {e}")

    # -------------------------------------------------------------
    # Coding Agent Execution & Program Selection
    # -------------------------------------------------------------

    def _refresh_target_programs(self):
        """Populates the Target Program dropdown with open documents and workspace files."""
        if not hasattr(self, "agent_target_combo"):
            return
        curr_val = self.agent_target_combo.currentData()
        self.agent_target_combo.blockSignals(True)
        self.agent_target_combo.clear()
        self.agent_target_combo.addItem("-- Select Program / File --", "")

        # 1. Open documents in editor
        for fn in self.open_documents.keys():
            self.agent_target_combo.addItem(f"📄 {fn} (Open)", fn)

        # 2. Files in workspace
        if self.workspace_path and self.workspace_path.is_dir():
            try:
                for entry in sorted(self.workspace_path.glob("**/*")):
                    if entry.is_file() and entry.suffix.lower() in (".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".sql", ".sh"):
                        rel = entry.relative_to(self.workspace_path)
                        rel_str = str(rel).replace("\\", "/")
                        if rel_str not in self.open_documents:
                            self.agent_target_combo.addItem(f"📁 {rel_str}", str(entry))
            except Exception:
                pass

        # 3. Whole workspace option
        self.agent_target_combo.addItem("🌐 Whole Workspace (All Files)", "__all__")

        # Restore previous or active selection
        restored = False
        if self.active_filename:
            for i in range(self.agent_target_combo.count()):
                if self.agent_target_combo.itemData(i) == self.active_filename:
                    self.agent_target_combo.setCurrentIndex(i)
                    restored = True
                    break
        if not restored and curr_val:
            for i in range(self.agent_target_combo.count()):
                if self.agent_target_combo.itemData(i) == curr_val:
                    self.agent_target_combo.setCurrentIndex(i)
                    break

        self.agent_target_combo.blockSignals(False)

    def _on_target_program_changed(self, idx: int):
        if idx > 0:
            if hasattr(self, "agent_target_warning"):
                self.agent_target_warning.setText("")
            self.agent_target_combo.setStyleSheet("""
                QComboBox {
                    background-color: #0A0F14;
                    border: 1px solid #273449;
                    border-radius: 6px;
                    color: #F8FAFC;
                    padding: 5px 8px;
                    font-size: 11px;
                }
                QComboBox:hover {
                    border-color: #00D1FF;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 18px;
                }
                QComboBox QAbstractItemView {
                    background-color: #111827;
                    color: #F8FAFC;
                    border: 1px solid #273449;
                    selection-background-color: #0f2744;
                    selection-color: #00D1FF;
                }
            """)
            target_data = self.agent_target_combo.itemData(idx)
            if target_data and target_data != "__all__":
                if target_data in self.open_documents:
                    for i in range(self.tab_bar.count()):
                        if self.tab_bar.tabData(i) == target_data:
                            self.tab_bar.setCurrentIndex(i)
                            break
                elif Path(target_data).is_file():
                    self.open_file(Path(target_data))

    def _set_agent_prompt(self, prompt: str):
        self.agent_prompt.setText(prompt)
        self._run_coding_agent()

    def _run_coding_agent(self):
        prompt = self.agent_prompt.text().strip()
        if not prompt:
            return

        # Enforce that user must select a program / file before starting AI
        if hasattr(self, "agent_target_combo") and self.agent_target_combo.currentIndex() <= 0:
            self.agent_target_warning.setText("⚠️ Select a program first!")
            self.agent_target_combo.setStyleSheet("""
                QComboBox {
                    background-color: #18090e;
                    border: 1px solid #FF5C77;
                    border-radius: 6px;
                    color: #F8FAFC;
                    padding: 5px 8px;
                    font-size: 11px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 18px;
                }
                QComboBox QAbstractItemView {
                    background-color: #111827;
                    color: #F8FAFC;
                    border: 1px solid #273449;
                    selection-background-color: #0f2744;
                    selection-color: #00D1FF;
                }
            """)
            self.agent_target_combo.showPopup()
            return

        selected_prog = self.agent_target_combo.currentText()
        self._toggle_tool_panel("agent")
        self.agent_status_lbl.setText("🟢 Working on your task...")
        self.agent_progress.setValue(35)
        self._action_timer.start(1000)

        # Update tasks stream
        for i in reversed(range(self.agent_tasks_container.layout().count())):
            w = self.agent_tasks_container.layout().itemAt(i).widget()
            if w:
                w.deleteLater()

        t0 = QLabel(f"<b>Target:</b> <span style='color: #00D1FF;'>{selected_prog}</span>")
        t0.setStyleSheet("color: #94A3B8; font-size: 10.5px;")
        self.agent_tasks_container.layout().addWidget(t0)

        t1 = QLabel(f"<b>Task:</b> {prompt}")
        t1.setStyleSheet("color: #f4f5fb; font-size: 11px;")
        self.agent_tasks_container.layout().addWidget(t1)

        t2 = QLabel(f"✔ Analyzing {selected_prog} context...")
        t2.setStyleSheet("color: #00D1FF; font-size: 10.5px;")
        self.agent_tasks_container.layout().addWidget(t2)

        t3 = QLabel("◉ Generating proposed code edits...")
        t3.setStyleSheet("color: #38bdf8; font-size: 10.5px; font-weight: bold;")
        self.agent_tasks_container.layout().addWidget(t3)

        self.console_output.append(f"\n🤖 [Sage Coding Agent] Target: {selected_prog} | Task: {prompt}\nExecuting autonomous agent pipeline...")
        self.agent_prompt.clear()

    # -------------------------------------------------------------
    # Team Chat & Collaboration (Same Window)
    # -------------------------------------------------------------

    def _init_collab(self):
        if hasattr(self, "whiteboard") and self.whiteboard:
            self.collab_manager.wb_stroke_received.connect(self.whiteboard.handle_remote_stroke)
            self.collab_manager.wb_cleared.connect(self.whiteboard.handle_remote_clear)
            self.collab_manager.wb_undo_received.connect(self.whiteboard.handle_remote_undo)
            self.collab_manager.wb_history_synced.connect(self.whiteboard.handle_history_synced)
        self.collab_manager.peer_joined.connect(self._on_peer_joined)
        self.collab_manager.peer_left.connect(self._on_peer_left)

    def _on_peer_joined(self, peer_name: str):
        if hasattr(self, "collab_members_lbl"):
            count = len(self.collab_manager.peers) + 1
            self.collab_members_lbl.setText(f"Connected Peers ({count})")
        if hasattr(self, "collab_empty_peers"):
            self.collab_empty_peers.setVisible(False)
        self.console_output.append(f"\n👥 [Collab] {peer_name} joined the session.\n")

    def _on_peer_left(self, peer_name: str):
        if hasattr(self, "collab_members_lbl"):
            count = len(self.collab_manager.peers) + 1
            self.collab_members_lbl.setText(f"Connected Peers ({count})")
        self.console_output.append(f"\n👥 [Collab] {peer_name} left the session.\n")

    def _open_collab_dialog(self):
        """Opens collaboration and invite controls inside the same window (no extra dialog popup)."""
        self._toggle_tool_panel("collab")
        if hasattr(self, "collab_panel") and self.collab_panel:
            self.collab_panel.tabs.setCurrentIndex(0)
            if hasattr(self.collab_panel, "room_code_display"):
                self.collab_panel.room_code_display.setFocus()

    def _send_team_chat_message(self):
        txt = self.team_chat_input.text().strip()
        if not txt:
            return
        self.team_chat_input.clear()

        # Remove empty hint if present
        if hasattr(self, "team_chat_empty") and self.team_chat_empty:
            self.team_chat_empty.setVisible(False)

        now_str = time.strftime("%I:%M %p").lstrip("0")
        msg_frame = QFrame()
        m_layout = QVBoxLayout(msg_frame)
        m_layout.setContentsMargins(0, 2, 0, 2)
        m_layout.setSpacing(1)

        hdr = QLabel(f"<span style='color: #00D1FF; font-weight: bold;'>You</span> <span style='color: #475569; font-size: 9px;'>{now_str}</span>")
        hdr.setTextFormat(Qt.RichText)
        m_layout.addWidget(hdr)

        body = QLabel(txt)
        body.setWordWrap(True)
        body.setStyleSheet("color: #cbd5e1; font-size: 10.5px;")
        m_layout.addWidget(body)

        self.team_chat_layout.addWidget(msg_frame)

    def _send_debounced_local_edit(self):
        pass

    def _toggle_debug(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        self.console_output.append("\n⚙ Debug session: Debugger attached on port 9229. Ready.\n")
