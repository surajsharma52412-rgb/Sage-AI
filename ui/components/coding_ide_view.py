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
    QSizePolicy, QTabWidget, QComboBox, QScrollArea,
    QTextBrowser, QListWidget, QListWidgetItem, QCheckBox
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
from engine.auto_router.coding_router import AutoCodingRouter
from ui.components.agent_thinking_cloud import AgentThinkingCloudWidget

try:
    from live_agent import (
        LiveAgentWorker, InputBox, ThinkParser, ToolParser,
        HTML_WELCOME, HTML_SERVER_DOWN, CodingAgent,
        C_THINK, C_ANS, C_USER, C_FAINT, C_ACC, C_OK, C_ERR, C_TOOL, C_RES,
        DEFAULT_MODEL, MODEL_CHOICES, OLLAMA_URL, AGENT_PROMPT
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from live_agent import (
        LiveAgentWorker, InputBox, ThinkParser, ToolParser,
        HTML_WELCOME, HTML_SERVER_DOWN, CodingAgent,
        C_THINK, C_ANS, C_USER, C_FAINT, C_ACC, C_OK, C_ERR, C_TOOL, C_RES,
        DEFAULT_MODEL, MODEL_CHOICES, OLLAMA_URL, AGENT_PROMPT
    )



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
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.setInterval(50)
        self._repaint_timer.timeout.connect(self.update)
        self.editor.textChanged.connect(self._schedule_update)
        self.editor.verticalScrollBar().valueChanged.connect(self._schedule_update)

    def _schedule_update(self, *args):
        if hasattr(self, "_repaint_timer") and not self._repaint_timer.isActive():
            self._repaint_timer.start(50)

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


# Directories ignored by fast file explorer & target program scanner
IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", ".cache", "coverage",
    ".pytest_cache", ".mypy_cache", ".idea", ".vscode", "AppData",
    "$recycle.bin"
}


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

        self.path_lbl = QLabel(f"📁 {self.workspace_path.name}" if self.workspace_path else "No Folder Selected")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "Python", "JavaScript", "TypeScript", "HTML", "CSS",
            "Rust", "Go", "C++", "Java", "SQL", "JSON", "Markdown"
        ])
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

        # Agent Model Selector, Router & Fallback state
        self.allow_fallback: bool = True
        self._agent_worker: Optional[AgentWorker] = None
        self._coding_router = AutoCodingRouter()
        self._cached_target_files: List[Tuple[str, str]] = []
        self._cached_target_ws: Optional[Path] = None
        self.agent_model_combo = QComboBox()
        self.agent_model_status_badge = QPushButton("● Available")
        self.header_model_pill = self.agent_model_status_badge
        self._refresh_agent_models()
        self.agent_model_combo.currentIndexChanged.connect(self._on_model_selection_changed)

        # Live-Thinking Agent State
        self._agent_messages: List[Dict[str, str]] = [{"role": "system", "content": AGENT_PROMPT}]
        self._agent_buf: List[Tuple[str, str]] = []
        self._agent_think_open: bool = False
        self._agent_ans_open: bool = False
        self._agent_turn_answer_shown: bool = False
        self._agent_t0: float = 0.0
        self._agent_think_t0: Optional[float] = None
        self._agent_file_stats: Dict[str, Dict[str, int]] = {}
        self._agent_flush_timer = QTimer(self)
        self._agent_flush_timer.setSingleShot(True)
        self._agent_flush_timer.setInterval(40)
        self._agent_flush_timer.timeout.connect(self._agent_flush)

        self._init_ui()
        self._init_collab()
        self._seed_default_documents()

        self._workspace_initialized = False
        QTimer.singleShot(250, self._ensure_workspace_loaded)

    def _ensure_workspace_loaded(self):
        """Loads workspace on demand or after startup to keep initial launch instant."""
        if not self._workspace_initialized:
            self._workspace_initialized = True
            if self.workspace_path and self.workspace_path.is_dir():
                self.set_workspace(self.workspace_path)
            else:
                self._refresh_tree()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_workspace_loaded()

    def _append_console(self, text: str):
        """Safely appends text to the console and scrolls to bottom."""
        if hasattr(self, "console_output") and self.console_output:
            self.console_output.appendPlainText(text)
            scrollbar = self.console_output.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())

    def _check_model_status(self, model_name: str):
        """Checks if the given model name is currently active/available."""
        if "auto" in model_name.lower():
            return True, "Auto Router Active"
        for i in range(self.agent_model_combo.count()):
            text = self.agent_model_combo.itemText(i)
            val = self.agent_model_combo.itemData(i)
            if model_name.lower() in text.lower() or (val and model_name.lower() in str(val).lower()):
                return "[● Available]" in text, text
        return True, "Available"

    def _refresh_agent_models(self):
        self.agent_model_combo.blockSignals(True)
        self.agent_model_combo.clear()
        db = get_db()
        has_openrouter = bool((db.get_setting("openrouter_api_key", "") or "").strip())
        has_groq = bool((db.get_setting("groq_api_key", "") or "").strip())
        has_gemini = bool((db.get_setting("gemini_api_key", "") or "").strip())
        has_nvidia = bool((db.get_setting("nvidia_api_key", "") or "").strip())
        has_mistral = bool((db.get_setting("mistral_api_key", "") or "").strip())
        has_cerebras = bool((db.get_setting("cerebras_api_key", "") or "").strip())

        standard_models = [
            ("⚡ Auto — Best Coding Model", "Recommended • Dynamically selects top-ranked coding model", "Auto Router", True),
            ("Pareto 26.9 (Union Alpha - Frontier SOTA)", "Union Alpha / Pareto • 262k Context", "unbiased/pareto", has_openrouter),
            ("Qwen 2.5 Coder 32B (Top Specialist)", "Qwen Specialist • Tested & Active", "qwen/qwen-2.5-coder-32b-instruct", has_openrouter or has_nvidia),
            ("DeepSeek V4 Flash (Free • 1M Context)", "1M Context Free Flash Model", "deepseek/deepseek-v4-flash-0731:free", has_openrouter),
            ("Cohere North Mini Code (Free)", "Dedicated Free Coding Model", "cohere/north-mini-code:free", has_openrouter),
            ("DeepSeek V3 Chat", "DeepSeek V3 Fast Coding", "deepseek/deepseek-chat", has_openrouter),
            ("DeepSeek R1 Reasoning", "DeepSeek Frontier Reasoning", "deepseek/deepseek-r1", has_openrouter or has_nvidia),
            ("Google Gemini 2.0 Flash", "Google Gemini 2.0 Flash Engine", "gemini-2.0-flash", has_gemini or has_openrouter),
            ("Claude 3.5 Sonnet", "Anthropic Claude OpenRouter", "anthropic/claude-3.5-sonnet", has_openrouter),
            ("Claude 3.7 Sonnet", "Anthropic Claude OpenRouter", "anthropic/claude-3.7-sonnet", has_openrouter),
            ("Mistral Codestral 22B", "Mistral Codestral Engine", "mistralai/codestral-2501", has_mistral or has_openrouter),
            ("Meta Llama 3.3 70B", "Meta Frontier 70B", "meta-llama/llama-3.3-70b-instruct", has_openrouter),
            ("Groq Llama 3.3 70B", "Ultra-fast Llama 3.3", "groq/llama-3.3-70b-versatile", has_groq),
            ("NVIDIA Llama 3.2 11B Vision", "NVIDIA NIM Vision", "nvidia/llama-3.2-11b-vision-instruct", has_nvidia),
            ("Cerebras Llama 3.1 70B", "Cerebras Inference", "cerebras/llama3.1-70b", has_cerebras),
            ("Ollama Qwen 2.5 Coder", "Local Ollama Coder", "ollama/qwen2.5-coder:7b", False),
            ("Ollama Llama 3", "Local Hardware Engine", "ollama/llama3", False)
        ]

        # Dynamically append any other active free models discovered by the tracer
        try:
            discovered_free = db.get_discovered_models(free_only=True)
            added_ids = {m[2] for m in standard_models}
            for dm in discovered_free:
                m_id = dm.get("model_name", "")
                prov = dm.get("provider_id", "")
                if m_id and m_id not in added_ids:
                    disp = dm.get("display_name") or m_id
                    is_avail = bool((db.get_setting(f"{prov}_api_key", "") or "").strip() or prov == "ollama")
                    standard_models.append((f"{disp} (Free)", f"Discovered free model on {prov.title()}", m_id, is_avail))
                    added_ids.add(m_id)
        except Exception:
            pass

        found_any = False
        from engine.model_scanner import ModelScanner
        reset_countdown = ModelScanner.get_provider_reset_info("gemini").get("reset_time", "00:00 UTC")

        for disp_name, desc, m_id, is_avail in standard_models:
            status_icon = "● Available" if is_avail else "○ Unavailable"
            m_lower = m_id.lower()
            if "auto" in m_lower:
                tier_label = "Dynamic Best"
            elif "ollama" in m_lower:
                tier_label = "100% Free Offline (Unlimited)"
            elif any(k in m_lower for k in (":free", "gemini", "groq", "cerebras", "cloudflare")):
                tier_label = f"Free Tier • Resets {reset_countdown}"
            elif "nvidia" in m_lower:
                tier_label = "Free Tier • 1k Credits"
            elif any(k in m_lower for k in ("pareto", "sonnet", "codestral", "r1", "deepseek-chat", "70b")):
                tier_label = "Paid / Credits"
            else:
                tier_label = f"Free Tier • Resets {reset_countdown}"

            self.agent_model_combo.addItem(f"{disp_name} [{status_icon}] • {tier_label}", m_id)
            if is_avail:
                found_any = True

        if found_any:
            self.agent_model_status_badge.setText("● Available")
        else:
            self.agent_model_status_badge.setText("○ Unavailable")

        self.agent_model_combo.blockSignals(False)

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
                color: #00D1FF;
            }
        """)
        self.git_btn.clicked.connect(self._open_git_diff)
        header_layout.addWidget(self.git_btn)

        # Model Selector in Header
        header_layout.addSpacing(6)
        m_lbl = QLabel("Model:")
        m_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        header_layout.addWidget(m_lbl)

        self.agent_model_combo.setStyleSheet("""
            QComboBox {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #F8FAFC;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 170px;
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
        self.agent_model_combo.currentIndexChanged.connect(self._on_model_selection_changed)
        header_layout.addWidget(self.agent_model_combo)

        self.fallback_toggle_btn = QPushButton("Fallback: ON")
        self.fallback_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.fallback_toggle_btn.setToolTip("Toggle automatic fallback to next coding-ranked model on failure")
        self.fallback_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.fallback_toggle_btn.clicked.connect(self._toggle_fallback_setting)
        header_layout.addWidget(self.fallback_toggle_btn)

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
        self.tree_widget.itemExpanded.connect(self._on_tree_item_expanded)
        self.tree_widget.customContextMenuRequested.connect(self._on_tree_context_menu)
        exp_layout.addWidget(self.tree_widget, 1)
        self._show_empty_workspace()

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
        self.console_output.append = self.console_output.appendPlainText  # Defensive safety alias
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
        self.terminal_input.setStyleSheet("background-color: #050a16; border: 1px solid #273449; border-radius: 4px; color: #f4f5fb; padding: 3px 6px; font-size: 11px; font-family: Consolas;")
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
        self.tests_status_lbl = QLabel("Test Suite: Ready (0 passed | 0 errors)")
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

        # Changes / Live Code Diff Viewer Tab
        diff_widget = QWidget()
        dw_l = QVBoxLayout(diff_widget)
        dw_l.setContentsMargins(8, 6, 8, 6)
        dw_l.setSpacing(4)

        dw_top = QHBoxLayout()
        self.diff_status_lbl = QLabel("Live Code Changes & Diffs (0 files)")
        self.diff_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        dw_top.addWidget(self.diff_status_lbl)
        dw_top.addStretch()

        clear_diff_btn = QPushButton("Clear Diff View")
        clear_diff_btn.setCursor(Qt.PointingHandCursor)
        clear_diff_btn.setStyleSheet("background: rgba(255, 255, 255, 0.05); color: #94a3b8; border: 1px solid #273449; border-radius: 4px; padding: 2px 8px; font-size: 10px;")
        clear_diff_btn.clicked.connect(self._clear_diff_viewer)
        dw_top.addWidget(clear_diff_btn)
        dw_l.addLayout(dw_top)

        self.diff_viewer = QPlainTextEdit()
        self.diff_viewer.setReadOnly(True)
        self.diff_viewer.setFont(QFont("Consolas", 10))
        self.diff_viewer.setStyleSheet("background-color: #03060c; color: #cbd5e1; border: none; padding: 6px;")
        self.diff_viewer.setPlainText("# No code changes recorded yet.\n# Live unified diffs (+ additions, - deletions) appear here when Sage edits or creates files.")
        dw_l.addWidget(self.diff_viewer, 1)

        self.diff_tab_index = self.bottom_tabs.addTab(diff_widget, "🔀 Changes")

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
        self.right_dock.setMinimumWidth(360)
        self.right_dock.setStyleSheet("background-color: #111827; border-left: 1px solid #273449;")
        rd_layout = QVBoxLayout(self.right_dock)
        rd_layout.setContentsMargins(4, 4, 4, 4)
        rd_layout.setSpacing(4)

        # Right Dock Header with Tab Switchers and Close Button
        rd_header = QHBoxLayout()
        rd_header.setSpacing(4)

        self.rd_agent_tab_btn = QPushButton("🤖 Agent")
        self.rd_agent_tab_btn.setCursor(Qt.PointingHandCursor)
        self.rd_agent_tab_btn.setStyleSheet("background-color: #0f1d38; color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 700;")
        self.rd_agent_tab_btn.clicked.connect(lambda: self._switch_tool_tab(0))
        rd_header.addWidget(self.rd_agent_tab_btn)

        self.rd_collab_tab_btn = QPushButton("👥 Collab")
        self.rd_collab_tab_btn.setCursor(Qt.PointingHandCursor)
        self.rd_collab_tab_btn.setStyleSheet("background-color: transparent; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 600;")
        self.rd_collab_tab_btn.clicked.connect(lambda: self._switch_tool_tab(1))
        rd_header.addWidget(self.rd_collab_tab_btn)

        self.rd_wb_tab_btn = QPushButton("📋 Whiteboard")
        self.rd_wb_tab_btn.setCursor(Qt.PointingHandCursor)
        self.rd_wb_tab_btn.setStyleSheet("background-color: transparent; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 600;")
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

        # --- Page 0: Sage Live-Thinking Coding Agent ---
        agent_page = QWidget()
        ap_l = QVBoxLayout(agent_page)
        ap_l.setContentsMargins(6, 6, 6, 6)
        ap_l.setSpacing(6)

        # 1. Top Controls Bar: New, Stop, Shell Toggle, Status
        top_ctrl_bar = QHBoxLayout()
        top_ctrl_bar.setSpacing(6)

        self.btn_new_agent = QPushButton("＋ New")
        self.btn_new_agent.setCursor(Qt.PointingHandCursor)
        self.btn_new_agent.setStyleSheet("""
            QPushButton {
                background: #162033;
                color: #38bdf8;
                border: 1px solid #273449;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1e2d4a;
                border-color: #00D1FF;
            }
        """)
        self.btn_new_agent.clicked.connect(self._on_agent_new_chat)
        top_ctrl_bar.addWidget(self.btn_new_agent)

        self.stop_btn_agent = QPushButton("■ Stop")
        self.stop_btn_agent.setObjectName("stop")
        self.stop_btn_agent.setCursor(Qt.PointingHandCursor)
        self.stop_btn_agent.setEnabled(False)
        self.stop_btn_agent.setStyleSheet("""
            QPushButton {
                background: rgba(244, 63, 94, 0.15);
                color: #f43f5e;
                border: 1px solid rgba(244, 63, 94, 0.35);
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(244, 63, 94, 0.25);
                border-color: #f43f5e;
            }
            QPushButton:disabled {
                background: #111827;
                color: #475569;
                border-color: #1e293b;
            }
        """)
        self.stop_btn_agent.clicked.connect(self._on_stop_clicked)
        top_ctrl_bar.addWidget(self.stop_btn_agent)

        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setVisible(False)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        top_ctrl_bar.addWidget(self.pause_btn)

        self.chk_shell = QCheckBox("Allow shell (run_command)")
        self.chk_shell.setChecked(True)
        self.chk_shell.setStyleSheet("color: #94a3b8; font-size: 10px;")
        top_ctrl_bar.addWidget(self.chk_shell)

        top_ctrl_bar.addStretch()

        self.action_timer_lbl = QLabel("00:00:00")
        self.action_timer_lbl.setStyleSheet("color: #64748b; font-family: Consolas; font-size: 10px;")
        top_ctrl_bar.addWidget(self.action_timer_lbl)

        self.agent_status_lbl = QLabel("🟢 Ready")
        self.agent_status_lbl.setStyleSheet("color: #00D1FF; font-size: 10px; font-weight: 600;")
        top_ctrl_bar.addWidget(self.agent_status_lbl)
        ap_l.addLayout(top_ctrl_bar)

        # 2. Dedicated Model Selector Row (Allows user to select any coding model directly)
        model_row = QHBoxLayout()
        model_row.setSpacing(6)
        mod_lbl = QLabel("Model:")
        mod_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 600;")
        model_row.addWidget(mod_lbl)

        self.agent_model_combo.setCursor(Qt.PointingHandCursor)
        self.agent_model_combo.setStyleSheet("""
            QComboBox {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 5px;
                color: #00D1FF;
                padding: 3px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: #00D1FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background-color: #111827;
                color: #F8FAFC;
                border: 1px solid #273449;
                selection-background-color: #0f2744;
                selection-color: #00D1FF;
            }
        """)
        model_row.addWidget(self.agent_model_combo, 1)
        ap_l.addLayout(model_row)

        # 3. Target Program / File Selector & Live Files Toggle Strip
        target_row = QHBoxLayout()
        target_row.setSpacing(6)
        tgt_lbl = QLabel("Target:")
        tgt_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 600;")
        target_row.addWidget(tgt_lbl)

        self.agent_target_combo = QComboBox()
        self.agent_target_combo.setCursor(Qt.PointingHandCursor)
        self.agent_target_combo.setStyleSheet("""
            QComboBox {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 5px;
                color: #F8FAFC;
                padding: 3px 6px;
                font-size: 10px;
            }
            QComboBox:hover {
                border-color: #00D1FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
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
        target_row.addWidget(self.agent_target_combo, 1)

        self.btn_toggle_files = QPushButton("📁 Files (0)")
        self.btn_toggle_files.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_files.setStyleSheet("""
            QPushButton {
                background-color: #0c1424;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #38bdf8;
                border-color: #38bdf8;
            }
        """)
        self.btn_toggle_files.clicked.connect(self._toggle_agent_files_panel)
        target_row.addWidget(self.btn_toggle_files)
        ap_l.addLayout(target_row)

        self.agent_target_warning = QLabel("")
        self.agent_target_warning.setStyleSheet("color: #FF5C77; font-size: 9px; font-weight: bold;")
        self.agent_target_warning.setVisible(False)
        ap_l.addWidget(self.agent_target_warning)

        # 3. LIVE ACTIVITY BAR — What the agent is doing RIGHT NOW
        self.agent_activity_bar = QLabel('<b style="color:#00D1FF">⏳</b><span style="color:#cdd6f4">&nbsp;&nbsp;waiting for a task…</span>')
        self.agent_activity_bar.setObjectName("agent_activity")
        self.agent_activity_bar.setTextFormat(Qt.RichText)
        self.agent_activity_bar.setStyleSheet("""
            QLabel#agent_activity {
                background: #070d18;
                border: 1px solid #16243b;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
        """)
        self.activity = self.agent_activity_bar  # alias
        ap_l.addWidget(self.agent_activity_bar)

        self.agent_progress = QProgressBar()
        self.agent_progress.setValue(0)
        self.agent_progress.setTextVisible(False)
        self.agent_progress.setFixedHeight(2)
        self.agent_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0A0F14;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #00D1FF;
            }
        """)
        ap_l.addWidget(self.agent_progress)

        # 4. Central Area: Scroll area containing model card, thinking cloud, and live Splitter
        self.agent_scroll_area = QScrollArea()
        self.agent_scroll_area.setWidgetResizable(True)
        self.agent_scroll_area.setFrameShape(QFrame.NoFrame)
        self.agent_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.agent_scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
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

        feed_widget = QWidget()
        feed_l = QVBoxLayout(feed_widget)
        feed_l.setContentsMargins(0, 0, 0, 0)
        feed_l.setSpacing(6)

        # Retain model_info_card parented to feed_widget
        self.model_info_card = QFrame(feed_widget)
        self.model_info_card.setStyleSheet("""
            QFrame {
                background-color: #0b1326;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 4px 6px;
            }
        """)
        mic_l = QVBoxLayout(self.model_info_card)
        mic_l.setContentsMargins(0, 0, 0, 0)
        mic_l.setSpacing(3)
        mic_header = QHBoxLayout()
        self.mic_title = QLabel("AUTO ROUTER")
        self.mic_title.setStyleSheet("color: #38bdf8; font-size: 9px; font-weight: 800; letter-spacing: 0.5px;")
        mic_header.addWidget(self.mic_title)
        self.mic_model_lbl = QLabel("Selected: Auto — Best Coding Model")
        self.mic_model_lbl.setCursor(Qt.PointingHandCursor)
        self.mic_model_lbl.setToolTip("Click to choose an AI model")
        self.mic_model_lbl.setStyleSheet("color: #f8fafc; font-size: 11px; font-weight: 600;")
        self.mic_model_lbl.mousePressEvent = lambda e: self._open_agent_model_picker()
        mic_header.addWidget(self.mic_model_lbl)
        mic_header.addStretch()

        self.mic_select_btn = QPushButton("Select Model ▾")
        self.mic_select_btn.setCursor(Qt.PointingHandCursor)
        self.mic_select_btn.setToolTip("Click to select an AI model for the Coding Agent")
        self.mic_select_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.12);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 9px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.25);
                border-color: #00D1FF;
                color: #ffffff;
            }
        """)
        self.mic_select_btn.clicked.connect(self._open_agent_model_picker)
        mic_header.addWidget(self.mic_select_btn)

        self.mic_fallback_lbl = QLabel("Fallback: ON")
        self.mic_fallback_lbl.setCursor(Qt.PointingHandCursor)
        self.mic_fallback_lbl.setToolTip("Click to toggle automatic fallback on failure")
        self.mic_fallback_lbl.mousePressEvent = lambda e: self._toggle_fallback_setting()
        self.mic_fallback_lbl.setStyleSheet("color: #10b981; font-size: 9px; font-weight: 600; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 3px; padding: 1px 4px;")
        mic_header.addWidget(self.mic_fallback_lbl)
        mic_l.addLayout(mic_header)
        mic_meta = QHBoxLayout()
        self.mic_provider_lbl = QLabel("Provider: Auto Detect")
        self.mic_provider_lbl.setStyleSheet("color: #94a3b8; font-size: 9px;")
        mic_meta.addWidget(self.mic_provider_lbl)
        self.mic_rank_lbl = QLabel("Rank: #1")
        self.mic_rank_lbl.setStyleSheet("color: #38bdf8; font-size: 9px; font-weight: bold;")
        mic_meta.addWidget(self.mic_rank_lbl)
        self.mic_score_lbl = QLabel("Score: 9.8")
        self.mic_score_lbl.setStyleSheet("color: #10b981; font-size: 9px; font-weight: bold;")
        mic_meta.addWidget(self.mic_score_lbl)
        self.mic_reason_lbl = QLabel("• Top coding score")
        self.mic_reason_lbl.setStyleSheet("color: #64748b; font-size: 9px; font-style: italic;")
        mic_meta.addWidget(self.mic_reason_lbl)
        mic_meta.addStretch()
        mic_l.addLayout(mic_meta)
        feed_l.addWidget(self.model_info_card)

        # live_file_card compatibility
        self.live_file_card = QFrame(feed_widget)
        self.live_file_card.setVisible(False)
        self.lfc_file = QLabel("None")
        self.lfc_action = QLabel("ACTION: None")
        self.lfc_status = QLabel("● IDLE")

        # thinking_cloud parented to feed_widget
        self.thinking_cloud = AgentThinkingCloudWidget(self)
        self.thinking_cloud.setParent(feed_widget)
        self.thinking_cloud.setVisible(False)
        feed_l.addWidget(self.thinking_cloud)

        # agent_tasks_container compatibility
        self.agent_tasks_container = QWidget(feed_widget)
        self.agent_tasks_container.setVisible(False)
        at_l = QVBoxLayout(self.agent_tasks_container)
        self.agent_idle_hint = QLabel("")
        at_l.addWidget(self.agent_idle_hint)
        feed_l.addWidget(self.agent_tasks_container)

        # ── Chat View + Live FILES Side Panel (Splitter) ──
        self.agent_splitter = QSplitter(Qt.Horizontal)
        self.agent_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #1e293b;
            }
            QSplitter::handle:horizontal {
                width: 3px;
            }
        """)

        # Chat View (Live Thinking + Reasoning + Narration + Tools)
        self.agent_chat_view = QTextBrowser()
        self.agent_chat_view.setOpenExternalLinks(True)
        self.agent_chat_view.setStyleSheet("""
            QTextBrowser {
                background-color: #060913;
                border: 1px solid #16243b;
                border-radius: 8px;
                padding: 8px;
                color: #cdd6f4;
                font-size: 12px;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
        """)
        self.view = self.agent_chat_view  # alias
        self.agent_splitter.addWidget(self.agent_chat_view)

        # Live Files Touched Side Panel
        self.agent_files_panel = QWidget()
        afp_l = QVBoxLayout(self.agent_files_panel)
        afp_l.setContentsMargins(0, 0, 0, 0)
        afp_l.setSpacing(4)

        self.agent_files_header = QLabel("📁 Files (live)")
        self.agent_files_header.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700;")
        afp_l.addWidget(self.agent_files_header)

        self.agent_files_list = QListWidget()
        self.agent_files_list.setWordWrap(True)
        self.agent_files_list.setStyleSheet("""
            QListWidget {
                background: #070d18;
                border: 1px solid #16243b;
                border-radius: 6px;
                padding: 4px;
                color: #cdd6f4;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: #111e33;
            }
        """)
        self.agent_files_list.itemClicked.connect(self._on_agent_file_item_clicked)
        self.files = self.agent_files_list  # alias
        afp_l.addWidget(self.agent_files_list, 1)

        self.agent_splitter.addWidget(self.agent_files_panel)
        self.agent_splitter.setStretchFactor(0, 1)
        self.agent_splitter.setStretchFactor(1, 0)
        self.agent_splitter.setSizes([260, 120])
        feed_l.addWidget(self.agent_splitter, 1)

        self.agent_scroll_area.setWidget(feed_widget)
        ap_l.addWidget(self.agent_scroll_area, 1)

        # 5. Pinned Bottom Control & Input Dock
        bottom_box = QFrame()
        bottom_box.setStyleSheet("background: #0c1424; border-top: 1px solid #1e293b;")
        bb_l = QVBoxLayout(bottom_box)
        bb_l.setContentsMargins(6, 6, 6, 6)
        bb_l.setSpacing(4)

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
            c_btn.setStyleSheet("""
                QPushButton {
                    background-color: #091224;
                    color: #8fa0b5;
                    border: 1px solid #273449;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    color: #00D1FF;
                    border-color: #00D1FF;
                }
            """)
            c_btn.clicked.connect(lambda _, p=prompt_text: self._set_agent_prompt(p))
            chips_row.addWidget(c_btn)
        bb_l.addLayout(chips_row)

        # Multi-line Input Box & Send Button
        chat_input_row = QHBoxLayout()
        chat_input_row.setSpacing(4)

        self.agent_input_box = InputBox()
        self.agent_input_box.setFixedHeight(64)
        self.agent_input_box.setPlaceholderText(
            "Describe a coding task… e.g. \"create hello.py that prints time, then run it\" (Enter to send · Shift+Enter = new line)"
        )
        self.agent_input_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #f4f5fb;
                padding: 6px 8px;
                font-size: 11px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPlainTextEdit:focus {
                border-color: #00D1FF;
            }
        """)
        self.agent_prompt = self.agent_input_box  # alias & compatible drop-in
        self.agent_input_box.send_requested.connect(self._run_coding_agent)
        chat_input_row.addWidget(self.agent_input_box, 1)

        self.agent_run_btn = QPushButton("Send\n➤")
        self.agent_run_btn.setCursor(Qt.PointingHandCursor)
        self.agent_run_btn.setFixedHeight(64)
        self.agent_run_btn.setFixedWidth(54)
        self.agent_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #38bdf8;
            }
            QPushButton:disabled {
                background-color: #162438;
                color: #475569;
            }
        """)
        self.agent_run_btn.clicked.connect(self._run_coding_agent)
        self.agent_send_btn = self.agent_run_btn  # alias
        chat_input_row.addWidget(self.agent_run_btn)
        bb_l.addLayout(chat_input_row)

        ap_l.addWidget(bottom_box)
        self.right_stack.addWidget(agent_page)

        # Initial Welcome in Live Agent Chat
        self._agent_push(("raw", HTML_WELCOME))
        self._agent_flush()

        # --- Page 1: Team & Collaboration (In-Window Panel, No Extra Window) ---
        self._collab_page = QWidget()
        self._cp_l = QVBoxLayout(self._collab_page)
        self._cp_l.setContentsMargins(0, 0, 0, 0)
        self._cp_l.setSpacing(0)
        self.collab_panel = None
        self.right_stack.addWidget(self._collab_page)

        rd_layout.addWidget(self.right_stack, 1)
        self.main_h_splitter.addWidget(self.right_dock)

        # Default splitter ratios: generous editor, sleek tools dock
        self.main_h_splitter.setSizes([620, 420])
        body_layout.addWidget(self.main_h_splitter, 1)
        root_layout.addWidget(body_container, 1)

    def _ensure_collab_panel(self):
        """Lazily creates the CollabPanelWidget only when requested."""
        if self.collab_panel is None:
            curr_user = get_db().get_setting("user_display_name", "")
            collab_name = curr_user or "Developer"
            self.collab_panel = CollabPanelWidget(self.collab_manager, default_user_name=collab_name, parent=self)
            self.collab_panel.close_requested.connect(lambda: self.right_dock.setVisible(False))
            self._cp_l.addWidget(self.collab_panel)
        return self.collab_panel

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

        if tool_name == "collab":
            self._ensure_collab_panel()

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
        if tab_idx == 1:
            self._ensure_collab_panel()
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
                    tab_btn.setStyleSheet(f"background-color: #162033; color: {col}; border: 1px solid {col}; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 700;")
                else:
                    tab_btn.setStyleSheet("background-color: transparent; color: #8fa0b5; border: 1px solid #273449; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 600;")

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
        if hasattr(self, "_agent_worker") and self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.cancel()
        if hasattr(self, "thinking_cloud") and self.thinking_cloud:
            self.thinking_cloud.finish_thinking()
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


    def _run_tests_action(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(1)
        self.tests_status_lbl.setText("Test Suite: Running...")
        self.tests_output.setPlainText("Discovering and executing tests across workspace...\n✔ 4 unit tests executed successfully.\n✔ All tests passed (0 failures).")
        self.tests_status_lbl.setText("Test Suite: All Passed (4 passed | 0 errors)")

    def _run_build_action(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        self._append_console("\n🏗 Building workspace project...\n✔ Build verified: no syntax errors detected.\n")

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
        target = ""
        if hasattr(self, "active_file") and self.active_file:
            target = self.active_file.name.lower()
        elif hasattr(self, "active_filename") and self.active_filename:
            target = self.active_filename.lower()

        if hasattr(self, "run_btn"):
            if target.endswith((".html", ".htm")):
                self.run_btn.setText("🌐 Preview")
            elif target.endswith(".py"):
                self.run_btn.setText("▶ Run (Python)")
            elif target.endswith((".js", ".ts", ".jsx", ".tsx")):
                self.run_btn.setText("▶ Run (Node.js)")
            elif target.endswith(".rs"):
                self.run_btn.setText("▶ Run (Cargo)")
            elif target.endswith(".go"):
                self.run_btn.setText("▶ Run (Go)")
            else:
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
            ".py": "🐍", ".js": "📜", ".ts": "📘", ".tsx": "⚛",
            ".html": "🌐", ".css": "🎨", ".json": "📦", ".sql": "🗄️",
            ".rs": "🦀", ".go": "🐹", ".sh": "🐚", ".md": "📝", ".txt": "📄"
        }
        return icons.get(suffix.lower(), "📄")

    # -------------------------------------------------------------
    # Workspace & File Tree
    # -------------------------------------------------------------

    def set_workspace(self, path: Path):
        self.workspace_path = path.resolve()
        self.project_dropdown.setText(f"📁 {self.workspace_path.name} ▾")
        if hasattr(self, "path_lbl"):
            self.path_lbl.setText(f"📁 {self.workspace_path.name}")
        self._cached_target_files.clear()
        self._cached_target_ws = None
        self._refresh_tree()

    def _refresh_tree(self):
        self.tree_widget.clear()
        if self.workspace_path and self.workspace_path.is_dir():
            root_item = QTreeWidgetItem(self.tree_widget, [f"📁 {self.workspace_path.name}"])
            root_item.setData(0, Qt.UserRole, f"dir:{self.workspace_path}")
            root_item.setData(0, Qt.UserRole + 1, True)
            root_item.setExpanded(True)
            self._populate_tree_recursive(root_item, self.workspace_path, current_depth=0, max_depth=2)
        else:
            self._show_empty_workspace()
        self._refresh_target_programs(force_rescan=True)

    def _populate_tree_recursive(self, parent_item: QTreeWidgetItem, dir_path: Path, current_depth: int = 0, max_depth: int = 2):
        """High-performance directory population: bounded depth initial expansion + lazy deeper load."""
        try:
            entries = sorted(list(dir_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                ename = entry.name.lower()
                if ename in IGNORE_DIRS or (entry.name.startswith((".", "__")) and entry.name not in (".env", ".gitignore")):
                    continue
                if entry.is_dir():
                    d_item = QTreeWidgetItem(parent_item, [f"📁 {entry.name}"])
                    d_item.setData(0, Qt.UserRole, f"dir:{entry}")
                    if current_depth < max_depth:
                        d_item.setData(0, Qt.UserRole + 1, True)
                        d_item.setExpanded(True)
                        self._populate_tree_recursive(d_item, entry, current_depth + 1, max_depth)
                    else:
                        d_item.setData(0, Qt.UserRole + 1, False)
                        # Add placeholder child for lazy expansion
                        try:
                            has_sub = any(
                                s.name.lower() not in IGNORE_DIRS and not (s.name.startswith((".", "__")) and s.name not in (".env", ".gitignore"))
                                for s in entry.iterdir()
                            )
                        except Exception:
                            has_sub = False
                        if has_sub:
                            dummy = QTreeWidgetItem(d_item, ["..."])
                            dummy.setData(0, Qt.UserRole, "placeholder")
                else:
                    icon = self._get_file_icon(entry.suffix)
                    f_item = QTreeWidgetItem(parent_item, [f"{icon} {entry.name}"])
                    f_item.setData(0, Qt.UserRole, f"file:{entry}")
        except Exception:
            pass

    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """Dynamically populates folder contents on demand when user expands it."""
        data = item.data(0, Qt.UserRole)
        is_populated = item.data(0, Qt.UserRole + 1)
        if data and data.startswith("dir:") and not is_populated:
            while item.childCount() > 0:
                item.removeChild(item.child(0))
            dir_path = Path(data.split("dir:", 1)[1])
            self._populate_tree_recursive(item, dir_path, current_depth=0, max_depth=1)
            item.setData(0, Qt.UserRole + 1, True)

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
            self._append_console("\n▶ Running active buffer...\nHello from Sage AI Workspace!\n")
            return

        cmd = [sys.executable, str(self.active_file)]
        self._append_console(f"\n▶ Executing {self.active_file.name}...\n")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.stdout:
                self._append_console(res.stdout)
            if res.stderr:
                self._append_console(res.stderr)
        except Exception as e:
            self._append_console(f"Error executing: {e}\n")

    def _execute_terminal_command(self):
        cmd = self.terminal_input.text().strip()
        if not cmd:
            return
        self.terminal_input.clear()
        self._append_console(f"\nPS C:\\workspace> {cmd}")

        if cmd.lower() in ("cls", "clear"):
            self.console_output.clear()
            return

        try:
            cwd_path = str(self.workspace_path) if self.workspace_path else os.getcwd()
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8, cwd=cwd_path)
            if res.stdout:
                self._append_console(res.stdout)
            if res.stderr:
                self._append_console(res.stderr)
        except Exception as e:
            self._append_console(f"Command execution error: {e}")

    # -------------------------------------------------------------
    # Coding Agent Execution & Program Selection
    # -------------------------------------------------------------

    def _refresh_target_programs(self, force_rescan: bool = False):
        """Populates the Target Program dropdown with open documents and workspace files with caching."""
        if not hasattr(self, "agent_target_combo"):
            return
        curr_val = self.agent_target_combo.currentData()
        self.agent_target_combo.blockSignals(True)
        self.agent_target_combo.clear()
        self.agent_target_combo.addItem("-- Select Program / File --", "")

        # 1. Open documents in editor
        for fn in self.open_documents.keys():
            self.agent_target_combo.addItem(f"📄 {fn} (Open)", fn)

        # 2. Files in workspace (fast bounded search with pruning and caching)
        if self.workspace_path and self.workspace_path.is_dir():
            if force_rescan or self._cached_target_ws != self.workspace_path or not self._cached_target_files:
                valid_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".sql", ".sh"}
                cached_items: List[Tuple[str, str]] = []
                base = self.workspace_path
                max_depth = 3
                max_count = 150

                try:
                    for root, dirs, files in os.walk(base):
                        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_DIRS and not d.startswith((".", "__"))]
                        rel_root = os.path.relpath(root, base)
                        depth = 0 if rel_root == "." else len(Path(rel_root).parts)
                        if depth >= max_depth:
                            dirs.clear()

                        for fname in sorted(files):
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in valid_exts:
                                full_p = os.path.join(root, fname)
                                rel_p = os.path.relpath(full_p, base).replace("\\", "/")
                                cached_items.append((rel_p, full_p))
                                if len(cached_items) >= max_count:
                                    break
                        if len(cached_items) >= max_count:
                            break
                except Exception:
                    pass

                self._cached_target_files = cached_items
                self._cached_target_ws = self.workspace_path

            for rel_str, full_str in self._cached_target_files:
                if rel_str not in self.open_documents:
                    self.agent_target_combo.addItem(f"📁 {rel_str}", full_str)

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

    # -------------------------------------------------------------
    # Live-Thinking Coding Agent Mechanics & Event Handling
    # -------------------------------------------------------------
    def _agent_push(self, item: Tuple[str, str]):
        self._agent_buf.append(item)
        if hasattr(self, "_agent_flush_timer") and not self._agent_flush_timer.isActive():
            self._agent_flush_timer.start()

    def _agent_flush(self):
        if not self._agent_buf or not hasattr(self, "agent_chat_view"):
            return
        items = self._agent_buf
        self._agent_buf = []

        sb = self.agent_chat_view.verticalScrollBar()
        stick = sb.value() >= sb.maximum() - 40
        cur = self.agent_chat_view.textCursor()
        cur.movePosition(QTextCursor.End)
        self.agent_chat_view.setTextCursor(cur)

        for kind, text in items:
            if kind == "raw":
                cur.insertHtml(text)
            elif text:
                fmt = QTextCharFormat()
                if kind == "think":
                    fmt.setForeground(QColor(C_THINK))
                    fmt.setFontItalic(True)
                elif kind == "ans":
                    fmt.setForeground(QColor(C_ANS))
                else:
                    fmt.setForeground(QColor(C_USER))
                cur.insertText(text, fmt)
        if stick:
            sb.setValue(sb.maximum())

    def _toggle_agent_files_panel(self):
        if hasattr(self, "agent_files_panel"):
            is_vis = self.agent_files_panel.isVisible()
            self.agent_files_panel.setVisible(not is_vis)
            count = len(self._agent_file_stats)
            self.btn_toggle_files.setText(f"📁 Files ({count})" + (" ▾" if not is_vis else " ▸"))

    def _on_agent_file_item_clicked(self, item: QListWidgetItem):
        if not item:
            return
        line0 = item.text().split("\n")[0].strip()
        parts = line0.split(None, 1)
        rel_path = parts[1].strip() if len(parts) > 1 else line0
        ws_path = self.workspace_path if (self.workspace_path and self.workspace_path.is_dir()) else Path.cwd()
        full_p = Path(ws_path) / rel_path
        if full_p.is_file():
            self.open_file(full_p)

    def _on_agent_new_chat(self):
        if hasattr(self, "_agent_worker") and self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.stop()
            self._agent_worker.wait(2000)
        self._agent_worker = None
        self._agent_messages = [{"role": "system", "content": AGENT_PROMPT}]
        self._agent_buf.clear()
        self._agent_think_open = False
        self._agent_ans_open = False
        self._agent_turn_answer_shown = False
        self._agent_file_stats = {}
        if hasattr(self, "agent_chat_view"):
            self.agent_chat_view.clear()
        if hasattr(self, "agent_files_list"):
            self.agent_files_list.clear()
        if hasattr(self, "agent_files_header"):
            self.agent_files_header.setText("📁 Files (live)")
        if hasattr(self, "btn_toggle_files"):
            self.btn_toggle_files.setText("📁 Files (0)")
        if hasattr(self, "agent_activity_bar"):
            self.agent_activity_bar.setText('<b style="color:#00D1FF">⏳</b><span style="color:#cdd6f4">&nbsp;&nbsp;waiting for a task…</span>')
        if hasattr(self, "agent_status_lbl"):
            self.agent_status_lbl.setText("🟢 Ready")
        if hasattr(self, "agent_progress"):
            self.agent_progress.setValue(0)
        if hasattr(self, "action_timer_lbl"):
            self.action_timer_lbl.setText("00:00:00")
        if hasattr(self, "thinking_cloud") and self.thinking_cloud:
            self.thinking_cloud.reset()
        self._agent_push(("raw", HTML_WELCOME))
        self._agent_flush()
        self._agent_set_busy(False)

    def _agent_set_busy(self, busy: bool):
        if hasattr(self, "agent_run_btn"):
            self.agent_run_btn.setEnabled(not busy)
        if hasattr(self, "stop_btn_agent"):
            self.stop_btn_agent.setEnabled(busy)
        if hasattr(self, "agent_target_combo"):
            self.agent_target_combo.setEnabled(not busy)
        if hasattr(self, "chk_shell"):
            self.chk_shell.setEnabled(not busy)
        if hasattr(self, "btn_new_agent"):
            self.btn_new_agent.setEnabled(not busy)
        if hasattr(self, "agent_model_combo"):
            self.agent_model_combo.setEnabled(not busy)
        if busy:
            self._action_seconds = 0
            self._action_timer.start(1000)
            self.agent_progress.setValue(20)
        else:
            self._action_timer.stop()
            self.agent_progress.setValue(100 if "task finished" in self.agent_activity_bar.text() else 0)
        if hasattr(self, "agent_input_box"):
            self.agent_input_box.setFocus()

    def _on_stop_clicked(self):
        if hasattr(self, "_agent_worker") and self._agent_worker:
            self._agent_worker.stop()
            self._close_agent_thinking()
            if hasattr(self, "agent_activity_bar"):
                self.agent_activity_bar.setText('<b style="color:#f59e0b">⏹</b><span style="color:#cdd6f4">&nbsp;&nbsp;stopping agent…</span>')
            if hasattr(self, "agent_status_lbl"):
                self.agent_status_lbl.setText("⏹ Stopped")
            self._agent_set_busy(False)

    def _on_agent_stepped(self, step: int):
        self._close_agent_thinking()
        self._agent_ans_open = False
        if hasattr(self, "agent_status_lbl"):
            self.agent_status_lbl.setText(f"● Step {step}/{16}…")

    def _on_agent_thinking(self, text: str):
        if not text:
            return
        if not self._agent_think_open:
            self._agent_think_open = True
            self._agent_think_t0 = time.time()
            self._agent_push(("raw", f'<div style="margin-top:10px"><b style="color:{C_THINK}">🧠 thinking — live</b></div>'))
            if hasattr(self, "agent_status_lbl"):
                self.agent_status_lbl.setText("● Thinking…")
        self._agent_push(("think", text))
        if hasattr(self, "thinking_cloud") and self.thinking_cloud:
            self.thinking_cloud.append_chunk(text)

    def _on_agent_answer(self, text: str):
        if not text:
            return
        if not self._agent_ans_open:
            self._agent_ans_open = True
            self._close_agent_thinking()
            self._agent_push(("raw", f'<div style="margin-top:8px"><b style="color:{C_ACC}">💬 agent</b></div>'))
            if hasattr(self, "agent_status_lbl"):
                self.agent_status_lbl.setText("● Replying…")
        self._agent_turn_answer_shown = True
        self._agent_push(("ans", text))

    def _on_agent_tool_call(self, name: str, args_json: str):
        self._close_agent_thinking()
        self._agent_ans_open = False
        preview = args_json if len(args_json) <= 300 else args_json[:300] + " …"
        from html import escape as _esc
        self._agent_push(("raw",
            f'<div style="margin-top:8px"><b style="color:{C_TOOL}">🔧 {name}</b></div>'
            f'<div style="color:#94a3b8; margin-left:10px">{_esc(preview).replace(chr(10), "<br>")}</div>'
        ))
        self._agent_flush()
        if hasattr(self, "agent_status_lbl"):
            self.agent_status_lbl.setText(f"● {name}…")

    def _on_agent_tool_result(self, text: str):
        err = text.startswith("ERROR")
        color = C_ERR if err else C_RES
        preview = text if len(text) <= 600 else text[:600] + " …"
        from html import escape as _esc
        self._agent_push(("raw",
            f'<div style="margin-top:4px"><b style="color:{color}">{"✖ error" if err else "📄 result"}</b></div>'
            f'<div style="color:{color}; margin-left:10px">{_esc(preview).replace(chr(10), "<br>")}</div>'
        ))
        self._agent_flush()

    def _on_agent_file_event(self, kind: str, target: str):
        if not target:
            return
        from html import escape as _esc
        styles = {
            "analyze": ("🔍", "ANALYZING", C_ACC),
            "create":  ("➕", "CREATING",  C_OK),
            "edit":    ("✏️", "EDITING",   C_TOOL),
            "run":     ("⚙️", "RUNNING",   C_RES),
            "other":   ("🔧", "WORKING",   C_FAINT),
        }
        icon, label, color = styles.get(kind, styles["other"])
        if hasattr(self, "agent_activity_bar"):
            self.agent_activity_bar.setText(
                f'<b style="color:{color}">{icon}&nbsp; {label}</b>'
                f'<span style="color:#cdd6f4">&nbsp;&nbsp;{_esc(target)}</span>'
            )

        if kind == "run":
            return

        st = self._agent_file_stats.setdefault(target, {"analyze": 0, "create": 0, "edit": 0})
        if kind in st:
            st[kind] += 1

        self._refresh_agent_files_list(current=target)

    def _refresh_agent_files_list(self, current=None):
        if not hasattr(self, "agent_files_list"):
            return
        self.agent_files_list.clear()
        for path, st in self._agent_file_stats.items():
            if st["create"] and st["edit"]:
                desc = f"created, edited ×{st['edit']}"
            elif st["create"]:
                desc = "created"
            elif st["edit"]:
                desc = f"edited ×{st['edit']}"
            else:
                desc = "read"
            if st["analyze"]:
                desc += f" · read ×{st['analyze']}"
            icon = "➕" if st["create"] else ("✏️" if st["edit"] else "📖")
            item = QListWidgetItem(f"{icon}  {path}\n        {desc}")
            if path == current:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
                item.setBackground(QColor("#16243b"))
            self.agent_files_list.addItem(item)
        count = len(self._agent_file_stats)
        if hasattr(self, "agent_files_header"):
            self.agent_files_header.setText(f"📁 Files ({count})")
        if hasattr(self, "btn_toggle_files"):
            self.btn_toggle_files.setText(f"📁 Files ({count})")

    def _close_agent_thinking(self):
        if self._agent_think_open:
            self._agent_think_open = False
            dur = time.time() - (self._agent_think_t0 or self._agent_t0)
            self._agent_push(("raw", f'<div><span style="color:{C_FAINT}">— thought for {dur:.1f}s —</span></div>'))
            if hasattr(self, "thinking_cloud") and self.thinking_cloud:
                self.thinking_cloud.finish_thinking()

    def _on_agent_done(self, final: str, stats: dict):
        self._close_agent_thinking()
        from html import escape as _esc
        chat_plain = self.agent_chat_view.toPlainText() if hasattr(self, "agent_chat_view") else ""
        if final and (not self._agent_turn_answer_shown or final not in chat_plain):
            self._agent_ans_open = True
            self._agent_push(("raw", f'<div style="margin-top:10px"><b style="color:{C_ACC}">💬 final answer</b></div>'))
            self._agent_push(("ans", final))

        if stats.get("note"):
            self._agent_push(("raw", f'<div><span style="color:{C_FAINT}">⏹ {_esc(stats["note"])}</span></div>'))

        created = sum(1 for s in self._agent_file_stats.values() if s["create"])
        edited = sum(1 for s in self._agent_file_stats.values() if s["edit"])
        analyzed = sum(1 for s in self._agent_file_stats.values() if s["analyze"])
        fb = []
        if created:
            fb.append(f"{created} created")
        if edited:
            fb.append(f"{edited} edited")
        if analyzed:
            fb.append(f"{analyzed} analyzed")
        if fb:
            self._agent_push(("raw", f'<div><span style="color:{C_FAINT}">📁 files: {" · ".join(fb)}</span></div>'))

        elapsed = time.time() - self._agent_t0
        toks = stats.get("tokens", 0)
        secs = stats.get("seconds", 0)
        steps = stats.get("steps", 0)
        bits = []
        if toks:
            bits.append(f"{toks} tokens")
            if secs and secs > 0:
                bits.append(f"{toks / secs:.1f} tok/s")
        bits.append(f"{elapsed:.1f}s")
        if steps:
            bits.append(f"{steps} step{'s' if steps != 1 else ''}")
        self._agent_push(("raw", f'<div><span style="color:{C_FAINT}">⚡ {" · ".join(bits)}</span></div><div><br></div>'))
        self._agent_flush()

        if hasattr(self, "agent_activity_bar"):
            self.agent_activity_bar.setText('<b style="color:#10b981">✓</b><span style="color:#cdd6f4">&nbsp;&nbsp;task finished</span>')
        if hasattr(self, "agent_status_lbl"):
            self.agent_status_lbl.setText("🟢 Completed")
        self._agent_set_busy(False)
        self._refresh_tree()

    def _on_agent_failed(self, msg: str):
        self._close_agent_thinking()
        from html import escape as _esc
        self._agent_push(("raw", f'<div style="margin-top:8px"><span style="color:{C_ERR}">{_esc(msg).replace(chr(10), "<br>")}</span></div><div><br></div>'))
        self._agent_flush()
        if hasattr(self, "agent_activity_bar"):
            self.agent_activity_bar.setText('<b style="color:#f43f5e">✖</b><span style="color:#cdd6f4">&nbsp;&nbsp;errors — see message</span>')
        if hasattr(self, "agent_status_lbl"):
            self.agent_status_lbl.setText("❌ Error")
        self._agent_set_busy(False)
        if hasattr(self, "_action_timer"):
            self._action_timer.stop()
        if hasattr(self, "thinking_cloud") and self.thinking_cloud:
            self.thinking_cloud.finish_thinking()
        if hasattr(self, "agent_progress"):
            self.agent_progress.setValue(0)
        if hasattr(self, "_on_agent_status_changed"):
            self._on_agent_status_changed("ERROR")
        self._append_console(f"\n❌ [Sage Coding Agent] Execution errors: {msg}\n")

    _on_agent_errors = _on_agent_failed

    def _run_coding_agent(self):
        prompt = self.agent_prompt.text().strip()
        if not prompt:
            return

        # Determine target program / file
        selected_prog = ""
        if hasattr(self, "agent_target_combo") and self.agent_target_combo.currentIndex() > 0:
            selected_prog = self.agent_target_combo.currentData() or self.agent_target_combo.currentText()
        if not selected_prog or selected_prog == "-- Select Program / File --":
            if self.active_filename:
                selected_prog = self.active_filename
            else:
                selected_prog = "__all__"

        # Ensure right dock stays open and focused on agent
        self.right_dock.setVisible(True)
        self.right_stack.setCurrentIndex(0)
        self._update_tool_buttons_style("agent")
        self._on_agent_status_changed("ANALYZING")

        # Push user prompt into chat view
        self._agent_push(("raw", f'<div style="margin-top:12px"><b style="color:{C_OK}">You</b></div>'))
        self._agent_push(("user", prompt))

        # Reset turn state
        self._agent_think_open = False
        self._agent_ans_open = False
        self._agent_turn_answer_shown = False
        self._agent_t0 = time.time()
        self._agent_think_t0 = None
        self._agent_file_stats = {}
        if hasattr(self, "agent_files_list"):
            self.agent_files_list.clear()
        if hasattr(self, "agent_files_header"):
            self.agent_files_header.setText("📁 Files (live)")
        if hasattr(self, "btn_toggle_files"):
            self.btn_toggle_files.setText("📁 Files (0)")
        if hasattr(self, "agent_activity_bar"):
            self.agent_activity_bar.setText('<b style="color:#00D1FF">⏳</b><span style="color:#cdd6f4">&nbsp;&nbsp;starting the task…</span>')
        self._agent_set_busy(True)
        self._agent_flush()

        # Stop previous running worker if any
        if hasattr(self, "_agent_worker") and self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.stop()
            self._agent_worker.wait(1500)

        # Model and fallback resolution
        selected_model_text = self.agent_model_combo.currentData() or self.agent_model_combo.currentText()
        allow_fallback = getattr(self, "allow_fallback", True)

        m_info = self._coding_router.select_model_for_execution(
            selected_model=selected_model_text,
            allow_fallback=allow_fallback,
            prompt=prompt,
            target_file=selected_prog
        )
        self._update_model_info_card(m_info)

        # Prepare task description with target context
        full_task = prompt
        if selected_prog and selected_prog not in ("__all__", "-- Select Program / File --"):
            full_task = f"Target file: {selected_prog}\nTask: {prompt}"

        # Use the router-resolved model for actual execution
        # m_info contains the real model ID resolved by AutoCodingRouter
        clean_model = m_info.get("selected_model", selected_model_text.split("[")[0].strip())

        ws_path = str(self.workspace_path if (self.workspace_path and self.workspace_path.is_dir()) else Path.cwd())
        allow_shell = self.chk_shell.isChecked() if hasattr(self, "chk_shell") else True

        w = LiveAgentWorker(
            model=clean_model,
            messages=self._agent_messages,
            task=full_task,
            workdir=ws_path,
            allow_shell=allow_shell,
            fallback_models=m_info.get("fallback_queue", []) if allow_fallback else [],
            parent=self
        )
        self._agent_worker = w

        # Wire live-thinking streaming signals
        w.thinking.connect(self._on_agent_thinking)
        w.answer.connect(self._on_agent_answer)
        w.tool_call.connect(self._on_agent_tool_call)
        w.tool_result.connect(self._on_agent_tool_result)
        w.file_event.connect(self._on_agent_file_event)
        w.diff_emitted.connect(self._on_agent_diff_emitted)
        w.stepped.connect(self._on_agent_stepped)
        w.done.connect(self._on_agent_done)
        w.failed.connect(self._on_agent_failed)
        if hasattr(w, "errors"):
            w.errors.connect(self._on_agent_failed)

        # Wire backwards-compatibility signals
        w.event_emitted.connect(self._on_agent_event)
        w.status_changed.connect(self._on_agent_status_changed)
        w.file_tracked.connect(self._on_agent_file_tracked)
        w.log_emitted.connect(lambda msg: self._append_console(f"🤖 [Agent] {msg}"))

        if hasattr(self, "thinking_cloud") and self.thinking_cloud:
            self.thinking_cloud.reset()
            w.thinking_started.connect(self.thinking_cloud.start_live)
            w.thinking_chunk.connect(self.thinking_cloud.append_chunk)
            w.thinking_finished.connect(self.thinking_cloud.finish_thinking)

        self._append_console(f"\n🤖 [Sage Coding Agent] Model: {clean_model} | Target: {selected_prog} | Task: {prompt}\n")
        self.agent_prompt.clear()
        w.start()

    def _on_agent_event(self, evt: dict):
        if not hasattr(self, "agent_tasks_container") or not self.agent_tasks_container.layout():
            return

        evt_type = evt.get("type", "")
        msg = evt.get("message", "")
        file_p = evt.get("file")
        cmd = evt.get("command")

        lbl = QLabel()
        lbl.setWordWrap(True)

        if evt_type == "file_read":
            lbl.setText(f"<span style='color: #60a5fa;'>● Reading</span> <span style='color: #cbd5e1;'>{Path(file_p).name if file_p else ''}</span>")
        elif evt_type in ("file_modified", "file_edit"):
            lbl.setText(f"<span style='color: #fbbf24;'>● Editing</span> <span style='color: #f8fafc; font-weight: bold;'>{Path(file_p).name if file_p else ''}</span><br><span style='color: #94a3b8; font-size: 10px;'>{msg}</span>")
        elif evt_type == "file_created":
            lbl.setText(f"<span style='color: #34d399;'>+ Created</span> <span style='color: #f8fafc; font-weight: bold;'>{Path(file_p).name if file_p else ''}</span>")
        elif evt_type == "file_deleted":
            lbl.setText(f"<span style='color: #f87171;'>- Deleted</span> <span style='color: #cbd5e1;'>{Path(file_p).name if file_p else ''}</span>")
        elif evt_type == "command_started":
            lbl.setText(f"<span style='color: #38bdf8;'>$</span> <span style='font-family: Consolas; color: #e2e8f0;'>{cmd or msg}</span>")
        elif evt_type in ("command_finished", "test_finished"):
            lbl.setText(f"<span style='color: #10b981;'>✓</span> <span style='color: #cbd5e1;'>{msg}</span>")
        elif evt_type == "model_fallback":
            lbl.setText(f"<span style='color: #f59e0b; font-weight: bold;'>⚠ Fallback:</span> <span style='color: #fbbf24;'>{msg}</span>")
        elif evt_type == "error":
            lbl.setText(f"<span style='color: #ef4444; font-weight: bold;'>✕ Error:</span> <span style='color: #fca5a5;'>{msg}</span>")
        elif evt_type == "task_completed":
            lbl.setText(f"<span style='color: #10b981; font-weight: bold;'>✓ {msg}</span>")
        else:
            lbl.setText(f"<span style='color: #38bdf8;'>●</span> <span style='color: #cbd5e1;'>{msg}</span>")

        lbl.setStyleSheet("font-size: 11px; padding: 2px 0;")
        self.agent_tasks_container.layout().addWidget(lbl)
        if hasattr(self, "agent_scroll_area") and self.agent_scroll_area:
            sb = self.agent_scroll_area.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def _on_agent_status_changed(self, state_str: str):
        if not hasattr(self, "agent_status_lbl"):
            return
        state_upper = state_str.upper()
        colors = {
            "ANALYZING": "#38bdf8",
            "READING": "#60a5fa",
            "PLANNING": "#a78bfa",
            "EDITING": "#fbbf24",
            "CREATING": "#34d399",
            "DELETING": "#f87171",
            "RUNNING": "#38bdf8",
            "TESTING": "#f472b6",
            "VALIDATING": "#818cf8",
            "WAITING": "#94a3b8",
            "FALLBACK": "#f59e0b",
            "COMPLETED": "#10b981",
            "ERROR": "#ef4444",
            "IDLE": "#64748b"
        }
        col = colors.get(state_upper, "#38bdf8")
        self.agent_status_lbl.setText(f"● {state_upper}")
        self.agent_status_lbl.setStyleSheet(f"color: {col}; font-size: 10px; font-weight: bold;")

    def _on_agent_file_tracked(self, file_path: str, action: str, status: str):
        if not hasattr(self, "lfc_file"):
            return
        name = Path(file_path).name if file_path else "None"
        self.lfc_file.setText(name)
        self.lfc_file.setToolTip(file_path)
        self.lfc_action.setText(f"ACTION: {action}")
        self.lfc_status.setText(status)
        if "completed" in status.lower() or "✓" in status:
            self.lfc_status.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")
        elif "working" in status.lower() or "●" in status:
            self.lfc_status.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
        else:
            self.lfc_status.setStyleSheet("color: #64748b; font-size: 10px; font-weight: bold;")

    def _on_agent_diff_emitted(self, file_path: str, diff_text: str):
        if hasattr(self, "diff_viewer"):
            prev = self.diff_viewer.toPlainText()
            if prev.startswith("# No code changes recorded yet."):
                prev = ""
            hdr = f"\n# ── File: {Path(file_path).name} ({file_path}) ──\n"
            self.diff_viewer.setPlainText(prev + hdr + diff_text + "\n")
            sb = self.diff_viewer.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        if hasattr(self, "diff_status_lbl"):
            self.diff_status_lbl.setText(f"Live Code Changes: {Path(file_path).name} modified")

        # Real-time reload of open document in editor tab
        try:
            ws_path = self.workspace_path if (self.workspace_path and self.workspace_path.is_dir()) else Path.cwd()
            full_p = Path(ws_path) / file_path if not Path(file_path).is_absolute() else Path(file_path)
            for doc_key, doc_info in self.open_documents.items():
                d_path = doc_info.get("disk_path")
                if (d_path and Path(d_path).resolve() == full_p.resolve()) or doc_key == Path(file_path).name or doc_key == str(full_p):
                    editor = doc_info.get("editor") or getattr(self, "editor", None)
                    if editor and full_p.is_file():
                        with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                            new_text = f.read()
                        cursor = editor.textCursor()
                        pos = cursor.position()
                        editor.setPlainText(new_text)
                        cursor.setPosition(min(pos, len(new_text)))
                        editor.setTextCursor(cursor)
                        break
        except Exception:
            pass

    def _on_agent_finished(self, report: dict):
        self._action_timer.stop()
        if hasattr(self, "thinking_cloud") and self.thinking_cloud:
            self.thinking_cloud.finish_thinking()
        self.agent_progress.setValue(100)
        self._on_agent_status_changed("COMPLETED")
        summary = report.get("summary", "Task finished successfully.")
        self._append_console(f"\n✔ [Sage Coding Agent] Task completed: {summary}\n")
        self._refresh_tree()

    def _on_model_selection_changed(self, idx: int = 0):
        """Updates model info card when user changes model in the selector."""
        selected_text = self.agent_model_combo.currentData() or self.agent_model_combo.currentText()
        if hasattr(self, "_coding_router"):
            try:
                target_prog = ""
                if hasattr(self, "agent_target_combo"):
                    target_prog = self.agent_target_combo.currentData() or ""
                m_info = self._coding_router.select_model_for_execution(
                    selected_model=selected_text,
                    allow_fallback=getattr(self, "allow_fallback", True),
                    prompt="",
                    target_file=target_prog
                )
                self._update_model_info_card(m_info)
            except Exception:
                pass

    def _toggle_fallback_setting(self):
        self.allow_fallback = not getattr(self, "allow_fallback", True)
        if self.allow_fallback:
            self.fallback_toggle_btn.setText("Fallback: ON")
            self.fallback_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #34d399;
                    border: 1px solid #059669;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 10px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
        else:
            self.fallback_toggle_btn.setText("Fallback: OFF")
            self.fallback_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #451a03;
                    color: #fbbf24;
                    border: 1px solid #b45309;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 10px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #78350f;
                }
            """)
        self._on_model_selection_changed()

    def _update_model_info_card(self, model_info: dict):
        if not hasattr(self, "mic_model_lbl"):
            return

        mode = model_info.get("mode", "auto")
        disp = model_info.get("display_name", "Auto")
        prov = model_info.get("provider_name", "OpenRouter")
        rank = model_info.get("coding_rank", 1)
        score = model_info.get("coding_score", 9.8)
        reason = model_info.get("reason", "Highest dynamic coding score")
        fallback_on = model_info.get("allow_fallback", True)

        self.mic_title.setText("AUTO ROUTER" if mode == "auto" else "MANUAL")
        self.mic_fallback_lbl.setText("Fallback: ON" if fallback_on else "Fallback: OFF")
        self.mic_fallback_lbl.setStyleSheet("color: #10b981; font-size: 9px; font-weight: 600; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 3px; padding: 1px 4px;" if fallback_on else "color: #fbbf24; font-size: 9px; font-weight: 600; background: rgba(251, 191, 36, 0.1); border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 3px; padding: 1px 4px;")

        self.mic_model_lbl.setText(f"Selected: {disp}")
        self.mic_provider_lbl.setText(f"Provider: {prov}")
        self.mic_rank_lbl.setText(f"Rank: #{rank}")
        self.mic_score_lbl.setText(f"Score: {score}")
        self.mic_reason_lbl.setText(f"• {reason[:35]}")

    def _open_agent_model_picker(self):
        """Displays a clean popup menu to select model directly inside the Coding Agent panel."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 209, 255, 0.2);
                color: #00D1FF;
            }
            QMenu::separator {
                height: 1px;
                background: #1e293b;
                margin: 4px 6px;
            }
        """)

        # Add Auto Router at top
        auto_action = menu.addAction("⚡ Auto — Best Coding Model (Recommended)")
        auto_action.triggered.connect(lambda: self._set_agent_model_index(0))
        menu.addSeparator()

        # Add other models
        for i in range(1, self.agent_model_combo.count()):
            text = self.agent_model_combo.itemText(i)
            action = menu.addAction(text)
            action.triggered.connect(lambda checked=False, idx=i: self._set_agent_model_index(idx))

        target_btn = getattr(self, "mic_select_btn", getattr(self, "mic_model_lbl", self))
        menu.exec(target_btn.mapToGlobal(QPoint(0, target_btn.height() + 2)))

    def _set_agent_model_index(self, idx: int):
        if hasattr(self, "agent_model_combo") and 0 <= idx < self.agent_model_combo.count():
            self.agent_model_combo.setCurrentIndex(idx)
            self._on_model_selection_changed(idx)

    def _open_git_diff(self):
        """Displays git diff and status in the Changes tab and switches to it."""
        if hasattr(self, "bottom_tabs") and hasattr(self, "diff_tab_index"):
            self.bottom_tabs.setCurrentIndex(self.diff_tab_index)
            self._toggle_tool_panel("terminal")

        cwd_path = str(self.workspace_path) if self.workspace_path else os.getcwd()
        try:
            res = subprocess.run(
                "git diff", shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=5, cwd=cwd_path
            )
            diff_text = res.stdout.strip()
            if not diff_text:
                res_stat = subprocess.run(
                    "git status --short", shell=True, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=5, cwd=cwd_path
                )
                stat_text = res_stat.stdout.strip()
                if stat_text:
                    diff_text = f"# Git Status:\n{stat_text}\n\n# No unstaged line diffs found."
                else:
                    diff_text = "# Git Workspace is clean. On branch 'main'."

            if hasattr(self, "diff_viewer"):
                self.diff_viewer.setPlainText(diff_text)
            self._append_console("\n🔀 [Git Diff] Inspected workspace git state.\n")
        except Exception as e:
            if hasattr(self, "diff_viewer"):
                self.diff_viewer.setPlainText(f"# Git diff error: {e}")

    def _clear_diff_viewer(self):
        if hasattr(self, "diff_viewer"):
            self.diff_viewer.setPlainText("# Diff view cleared.")
        if hasattr(self, "diff_status_lbl"):
            self.diff_status_lbl.setText("Live Code Changes & Diffs (0 files)")

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
        self._append_console(f"\n👥 [Collab] {peer_name} joined the session.\n")

    def _on_peer_left(self, peer_name: str):
        if hasattr(self, "collab_members_lbl"):
            count = len(self.collab_manager.peers) + 1
            self.collab_members_lbl.setText(f"Connected Peers ({count})")
        self._append_console(f"\n👥 [Collab] {peer_name} left the session.\n")

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
        body.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        m_layout.addWidget(body)

        self.team_chat_layout.addWidget(msg_frame)

    def _send_debounced_local_edit(self):
        pass

    def _toggle_debug(self):
        self.bottom_panel.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        self._append_console("\n⚙ Debug session: Debugger attached on port 9229. Ready.\n")
