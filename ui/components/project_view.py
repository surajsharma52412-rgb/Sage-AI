"""
Project Agent View Component for Sage AI (Lunar Engine).
Autonomous Project Coding Agent Studio interface:
- Auto-detected workspace with language detection badges & live file search filter
- 6 Large Guided Goal Cards for 1-click execution (Tests, Docs, Refactor, Features, Security, Performance)
- Custom Prompt Mode with advanced controls
- Coding model selector
- Real-time 4-stage visual execution progress tracker
- Interactive file diff inspector and atomic operation logs
- Actionable diagnostics with 1-click model connection
"""
from pathlib import Path
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter, QFrame, QTabWidget, QComboBox, QLineEdit,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal

from engine.project_agent import WorkspaceInspector
from engine.model_scanner import ModelScanner
from workers.agent_worker import AgentWorker


GOAL_PRESETS = [
    {
        "id": "tests",
        "icon": "🧪",
        "title": "Write Unit Tests",
        "desc": "Generate automated unit tests with mocks, fixtures, and assertions to verify core logic.",
        "prompt": "Create comprehensive automated unit tests for core modules in this workspace with mock data, edge cases, and assertions."
    },
    {
        "id": "docs",
        "icon": "📝",
        "title": "Project Documentation",
        "desc": "Build a modern README.md, module docstrings, architecture overview, and setup instructions.",
        "prompt": "Generate a clean, modern README.md documenting the project architecture, setup instructions, key features, and API reference."
    },
    {
        "id": "refactor",
        "icon": "🧹",
        "title": "Clean & Refactor",
        "desc": "Clean up code architecture, add type annotations, improve readability, and remove redundancy.",
        "prompt": "Refactor workspace code for clean architecture, type annotations, structured error handling, clean imports, and PEP8 compliance."
    },
    {
        "id": "feature",
        "icon": "✨",
        "title": "Add Feature Module",
        "desc": "Create a new modular helper or utility component with clean functions and docstrings.",
        "prompt": "Implement a new modular utility helper in the project with clean functions, docstrings, and robust error handling."
    },
    {
        "id": "security",
        "icon": "🛡️",
        "title": "Security & Bug Audit",
        "desc": "Scan for vulnerabilities, missing error handling, and unhandled exceptions, then apply fixes.",
        "prompt": "Audit the workspace files for potential runtime exceptions, edge cases, and security vulnerabilities, and apply fixes."
    },
    {
        "id": "perf",
        "icon": "⚡",
        "title": "Optimize Performance",
        "desc": "Identify computation bottlenecks, optimize data structures, and accelerate slow paths.",
        "prompt": "Analyze the codebase for performance bottlenecks, optimize heavy loops and database queries, and reduce memory overhead."
    },
]


class ProjectAgentView(QWidget):
    """Visual Studio interface for the Autonomous Project Coding Agent."""

    task_started = Signal()
    task_finished = Signal(dict)
    manage_models_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace_path: Optional[Path] = None
        self.worker: Optional[AgentWorker] = None
        self.selected_goal_id: str = "tests"
        self.goal_cards: Dict[str, QFrame] = {}

        self._init_ui()
        self._update_model_status_chip()
        self._show_empty_workspace()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # 1. Header Bar: Spacious title, model dropdown & folder pill
        header_bar = QHBoxLayout()
        header_bar.setSpacing(14)

        proj_icon = QLabel("⚡")
        proj_icon.setStyleSheet("color: #00D1FF; font-size: 22px;")
        header_bar.addWidget(proj_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Autonomous Project Studio")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 17px; font-weight: 800; letter-spacing: 0.3px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Self-planning, atomic file edits, automated tests & self-repair")
        sub_lbl.setStyleSheet("color: #717d98; font-size: 11.5px;")
        title_box.addWidget(sub_lbl)
        header_bar.addLayout(title_box)

        header_bar.addStretch()

        # Coding Model Dropdown
        m_lbl = QLabel("Coding Model:")
        m_lbl.setStyleSheet("color: #8fa0c0; font-size: 11.5px; font-weight: 600;")
        header_bar.addWidget(m_lbl)

        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(360)
        self._refresh_models()
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.3);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11.5px;
                font-weight: 600;
            }
            QComboBox QAbstractItemView {
                background-color: #162033;
                color: #F8FAFC;
                selection-background-color: rgba(0, 209, 255, 0.2);
                selection-color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.3);
            }
        """)
        self.model_combo.currentTextChanged.connect(self._update_model_status_chip)
        header_bar.addWidget(self.model_combo)

        # Model Activation Status Badge
        self.model_status_chip = QPushButton("● Active")
        self.model_status_chip.setCursor(Qt.PointingHandCursor)
        self.model_status_chip.setToolTip("Model Status — Click to configure API keys")
        self.model_status_chip.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.25);
            }
        """)
        self.model_status_chip.clicked.connect(self._open_settings_dialog)
        header_bar.addWidget(self.model_status_chip)

        # Folder Pill
        self.path_lbl = QLabel("📁 Workspace: None Selected")
        self.path_lbl.setStyleSheet("""
            background-color: #162033;
            color: #d1d8e6;
            border: 1px solid #273449;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 11.5px;
            font-weight: 600;
        """)
        header_bar.addWidget(self.path_lbl)

        self.change_folder_btn = QPushButton("📂 Select Folder")
        self.change_folder_btn.setCursor(Qt.PointingHandCursor)
        self.change_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
            }
        """)
        self.change_folder_btn.clicked.connect(self._select_folder)
        header_bar.addWidget(self.change_folder_btn)

        main_layout.addLayout(header_bar)

        # 2. Main Splitter: Left = Project Explorer, Right = Studio Actions & Output
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: rgba(0, 209, 255, 0.12); width: 2px; }")

        # --- LEFT COLUMN: File Explorer with Search Filter ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        # Summary Bar (File Count & Language Badges)
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("summaryFrame")
        self.summary_frame.setStyleSheet("""
            QFrame#summaryFrame {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 6px 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        sf_layout = QHBoxLayout(self.summary_frame)
        sf_layout.setContentsMargins(4, 2, 4, 2)
        sf_layout.setSpacing(6)

        self.stats_lbl = QLabel("📂 Scanning project...")
        self.stats_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: bold;")
        sf_layout.addWidget(self.stats_lbl)
        sf_layout.addStretch()

        left_layout.addWidget(self.summary_frame)

        # Quick Filter Search Input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Filter files...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #F8FAFC;
                font-size: 11.5px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_tree)
        left_layout.addWidget(self.search_edit)

        # Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["File / Directory", "Size"])
        self.tree_widget.setColumnWidth(0, 180)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: #0A0F14;
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 8px;
                color: #d1d8e6;
                font-size: 11.5px;
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #162033;
            }
            QTreeWidget::item:selected {
                background-color: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
            }
            QHeaderView::section {
                background-color: #162033;
                color: #717d98;
                font-size: 11px;
                font-weight: bold;
                border: none;
                padding: 4px 6px;
            }
        """)
        left_layout.addWidget(self.tree_widget)

        self.refresh_btn = QPushButton("🔄 Refresh Files")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #8da0be;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: rgba(0, 209, 255, 0.3);
            }
        """)
        self.refresh_btn.clicked.connect(self._refresh_tree)
        left_layout.addWidget(self.refresh_btn)

        splitter.addWidget(left_widget)

        # --- RIGHT COLUMN: Task Studio Area ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        # Mode Tabs: Guided Goals vs. Custom Prompt
        self.mode_tabs = QTabWidget()
        self.mode_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(0, 209, 255, 0.18);
                background-color: #0A0F14;
                border-radius: 10px;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #0A0F14;
                color: #717d98;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 20px;
                margin-right: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0A0F14;
                color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
                font-weight: 700;
            }
        """)

        # Tab 1: 🌟 Guided Goal Cards
        self.mode_tabs.addTab(self._create_guided_tab(), "🌟 Guided Goal Cards (1-Click)")

        # Tab 2: ✍️ Custom Task Prompt
        self.mode_tabs.addTab(self._create_custom_tab(), "✍️ Custom Task Prompt")

        right_layout.addWidget(self.mode_tabs)

        # 4-Step Progress Tracker
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("progressTracker")
        self.progress_frame.setStyleSheet("""
            QFrame#progressTracker {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        p_layout = QHBoxLayout(self.progress_frame)
        p_layout.setContentsMargins(12, 8, 12, 8)
        p_layout.setSpacing(6)

        self.step_labels: List[QLabel] = []
        steps = ["1. Inspect Files", "2. Plan Operations", "3. Apply Code Diffs", "4. Verify & Repair"]
        for idx, s in enumerate(steps):
            lbl = QLabel(f"○ {s}")
            lbl.setStyleSheet("color: #55607a; font-size: 11px; font-weight: 600;")
            self.step_labels.append(lbl)
            p_layout.addWidget(lbl)
            if idx < len(steps) - 1:
                arrow = QLabel("➔")
                arrow.setStyleSheet("color: #3b455b; font-size: 10px;")
                p_layout.addWidget(arrow)

        p_layout.addStretch()
        right_layout.addWidget(self.progress_frame)

        # Action Button Row
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("🚀 Execute Autonomous Task")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D1FF, stop:1 #008BB3);
                color: #0A0F14;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #00BBE6;
            }
            QPushButton:disabled {
                background-color: #162033;
                color: #55607a;
            }
        """)
        self.run_btn.clicked.connect(self._run_current_task)
        btn_row.addWidget(self.run_btn)

        self.stop_btn = QPushButton("⏹ Stop Task")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(244, 63, 94, 0.12);
                color: #f43f5e;
                border: 1px solid rgba(244, 63, 94, 0.35);
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(244, 63, 94, 0.25);
            }
            QPushButton:disabled {
                opacity: 0.35;
                color: #55607a;
                border-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.stop_btn.clicked.connect(self._stop_current_task)
        btn_row.addWidget(self.stop_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        btn_row.addWidget(self.status_lbl)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        # Diagnostic Guidance Banner (Hidden by default)
        self.diag_banner = QFrame()
        self.diag_banner.setObjectName("diagBanner")
        self.diag_banner.setStyleSheet("""
            QFrame#diagBanner {
                background-color: rgba(255, 92, 119, 0.08);
                border: 1px solid rgba(255, 92, 119, 0.35);
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        diag_layout = QHBoxLayout(self.diag_banner)
        diag_layout.setContentsMargins(12, 8, 12, 8)
        diag_layout.setSpacing(10)

        self.diag_msg = QLabel("")
        self.diag_msg.setWordWrap(True)
        self.diag_msg.setStyleSheet("color: #ff94a4; font-size: 11.5px;")
        diag_layout.addWidget(self.diag_msg, 1)

        self.diag_btn = QPushButton("✨ Connect AI Models")
        self.diag_btn.setCursor(Qt.PointingHandCursor)
        self.diag_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        self.diag_btn.clicked.connect(self.manage_models_requested.emit)
        diag_layout.addWidget(self.diag_btn)
        self.diag_connect_btn = self.diag_btn

        self.diag_banner.setVisible(False)
        right_layout.addWidget(self.diag_banner)

        # Output Tabs: Activity Log & Code Diffs
        self.output_tabs = QTabWidget()
        self.output_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(0, 209, 255, 0.15);
                background-color: #0A0F14;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #0A0F14;
                color: #717d98;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 16px;
                margin-right: 4px;
                font-size: 11.5px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0A0F14;
                color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
                font-weight: 700;
            }
        """)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #0A0F14; color: #d0d7e5; font-family: 'Consolas', monospace; font-size: 11.5px; border: none; padding: 8px;")
        self.output_tabs.addTab(self.log_view, "📋 Activity Log")

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setStyleSheet("background-color: #0A0F14; color: #00D1FF; font-family: 'Consolas', monospace; font-size: 11.5px; border: none; padding: 8px;")
        self.output_tabs.addTab(self.diff_view, "📝 Code Diffs")

        right_layout.addWidget(self.output_tabs, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([260, 680])
        main_layout.addWidget(splitter, 1)

    # --- Guided Goals Mode ---
    def _create_guided_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        # 6 Large Visual Goal Cards Grid (2 rows of 3)
        grid = QGridLayout()
        grid.setSpacing(10)

        for i, preset in enumerate(GOAL_PRESETS):
            card = QFrame()
            p_id = preset["id"]
            card.setObjectName(f"goalCard_{p_id}")
            is_selected = (p_id == self.selected_goal_id)

            border_col = "#00D1FF" if is_selected else "#273449"
            bg_col = "#162033" if is_selected else "#162033"
            card.setStyleSheet(f"""
                QFrame#goalCard_{p_id} {{
                    background-color: {bg_col};
                    border: 1.5px solid {border_col};
                    border-radius: 8px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            card.setCursor(Qt.PointingHandCursor)

            c_l = QVBoxLayout(card)
            c_l.setContentsMargins(10, 8, 10, 8)
            c_l.setSpacing(3)

            top_h = QHBoxLayout()
            icon_lbl = QLabel(preset["icon"])
            icon_lbl.setStyleSheet("font-size: 16px;")
            top_h.addWidget(icon_lbl)

            t_lbl = QLabel(preset["title"])
            t_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 700;")
            top_h.addWidget(t_lbl)
            top_h.addStretch()
            c_l.addLayout(top_h)

            d_lbl = QLabel(preset["desc"])
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet("color: #7a88a4; font-size: 10px; line-height: 1.3;")
            c_l.addWidget(d_lbl)

            card.mousePressEvent = lambda e, pid=p_id: self._select_goal(pid)
            self.goal_cards[p_id] = card
            grid.addWidget(card, i // 3, i % 3)

        layout.addLayout(grid)

        # Explanation Box for selected goal
        self.goal_explainer = QLabel("")
        self.goal_explainer.setWordWrap(True)
        self.goal_explainer.setStyleSheet("""
            background-color: #0A0F14;
            color: #b0bfdc;
            border: 1px solid rgba(0, 209, 255, 0.15);
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 11.5px;
        """)
        layout.addWidget(self.goal_explainer)

        self._update_goal_explainer()
        return widget

    def _select_goal(self, goal_id: str):
        self.selected_goal_id = goal_id
        for pid, card in self.goal_cards.items():
            is_sel = (pid == goal_id)
            border_col = "#00D1FF" if is_sel else "#273449"
            bg_col = "#162033" if is_sel else "#162033"
            card.setStyleSheet(f"""
                QFrame#goalCard_{pid} {{
                    background-color: {bg_col};
                    border: 1.5px solid {border_col};
                    border-radius: 8px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
        self._update_goal_explainer()

    @property
    def task_input(self):
        return self.custom_input

    def _set_task_prompt(self, prompt_text: str):
        self.custom_input.setPlainText(prompt_text)
        self.mode_tabs.setCurrentIndex(1)

    def _update_goal_explainer(self):
        preset = next((p for p in GOAL_PRESETS if p["id"] == self.selected_goal_id), GOAL_PRESETS[0])
        self.goal_explainer.setText(f"🎯 <b>Selected Goal:</b> {preset['title']}<br><span style='color: #717d98;'>Prompt: \"{preset['prompt']}\"</span>")

    # --- Custom Prompt Mode ---
    def _create_custom_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(6)

        c_lbl = QLabel("Enter custom prompt instructions for the autonomous coding agent:")
        c_lbl.setStyleSheet("color: #8fa0c0; font-size: 11.5px;")
        layout.addWidget(c_lbl)

        self.custom_input = QTextEdit()
        self.custom_input.setPlaceholderText(
            "Describe the task for the autonomous agent in detail... e.g.:\n"
            "'Add a SQLite caching layer to the database manager with an expiry mechanism and unit tests.'"
        )
        self.custom_input.setStyleSheet("""
            QTextEdit {
                background-color: #0A0F14;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 8px;
                color: #F8FAFC;
                font-size: 12px;
                padding: 8px 10px;
            }
            QTextEdit:focus {
                border-color: #00D1FF;
            }
        """)
        self.custom_input.setFixedHeight(90)
        layout.addWidget(self.custom_input)
        return widget

    def _show_empty_workspace(self):
        self.workspace_path = None
        self.path_lbl.setText("📁 Workspace: None Selected")
        self.path_lbl.setToolTip("No folder selected. Click 'Select Folder' to choose a project directory.")
        self.change_folder_btn.setText("📂 Select Folder")
        self.stats_lbl.setText("📁 No folder selected • Click 'Select Folder' to load project")
        self.tree_widget.clear()
        empty_item = QTreeWidgetItem(self.tree_widget, ["📁 No Project Selected", ""])
        empty_item.setDisabled(True)
        sub_hint = QTreeWidgetItem(empty_item, ["👉 Click '📂 Select Folder' above to open a project directory", ""])
        sub_hint.setDisabled(True)
        empty_item.setExpanded(True)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Workspace Directory")
        if folder:
            self.set_workspace(Path(folder))

    def set_workspace(self, path: Path):
        self.workspace_path = path.resolve()
        folder_name = self.workspace_path.name or str(self.workspace_path)
        self.path_lbl.setText(f"📁 Workspace: {folder_name}")
        self.path_lbl.setToolTip(str(self.workspace_path))
        self.change_folder_btn.setText("📁 Change Folder")
        self._refresh_tree()
        self.log_view.append(f"📁 Workspace connected: {self.workspace_path}")

    def _refresh_tree(self):
        if not self.workspace_path or not self.workspace_path.is_dir():
            self._show_empty_workspace()
            return

        self.tree_widget.clear()
        try:
            inspector = WorkspaceInspector(self.workspace_path)
            manifest = inspector.scan_manifest(max_files=250)

            # Language breakdown calculation
            ext_counts = {}
            for item in manifest:
                ext = Path(item["path"]).suffix.lower() or "other"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

            py_c = ext_counts.get(".py", 0)
            md_c = ext_counts.get(".md", 0)
            json_c = ext_counts.get(".json", 0)
            self.stats_lbl.setText(f"📂 {len(manifest)} files • 🐍 Python ({py_c}) • 📄 Docs ({md_c})")

            root_item = QTreeWidgetItem(self.tree_widget, [self.workspace_path.name, ""])
            root_item.setExpanded(True)

            dirs: Dict[str, QTreeWidgetItem] = {}
            for item in manifest:
                parts = item["path"].split("/")
                current_parent = root_item

                for i, part in enumerate(parts[:-1]):
                    sub_path = "/".join(parts[:i+1])
                    if sub_path not in dirs:
                        dir_item = QTreeWidgetItem(current_parent, [f"📁 {part}", ""])
                        dir_item.setExpanded(True)
                        dirs[sub_path] = dir_item
                    current_parent = dirs[sub_path]

                size_str = f"{item['size']} B" if item['size'] < 1024 else f"{item['size']//1024} KB"
                file_icon = "📄 " if not item["is_binary"] else "📦 "
                QTreeWidgetItem(current_parent, [file_icon + parts[-1], size_str])

        except Exception as e:
            self.stats_lbl.setText("📁 Workspace scanned (0 files)")
            self.log_view.append(f"Error inspecting file tree: {str(e)}")

    def _filter_tree(self, text: str):
        query = text.strip().lower()

        def filter_item(item: QTreeWidgetItem) -> bool:
            name = item.text(0).lower()
            match = query in name if query else True
            child_matched = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    child_matched = True
            should_show = match or child_matched
            item.setHidden(not should_show)
            if should_show and query:
                item.setExpanded(True)
            return should_show

        for i in range(self.tree_widget.topLevelItemCount()):
            filter_item(self.tree_widget.topLevelItem(i))

    def _update_step(self, step_idx: int):
        for i, lbl in enumerate(self.step_labels):
            step_text = lbl.text().split(" ", 1)[-1]
            if i < step_idx:
                lbl.setText(f"✓ {step_text}")
                lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700;")
            elif i == step_idx:
                lbl.setText(f"◉ {step_text}")
                lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 800;")
            else:
                lbl.setText(f"○ {step_text}")
                lbl.setStyleSheet("color: #55607a; font-size: 11px; font-weight: 600;")

    def _run_current_task(self):
        if not self.workspace_path:
            self._select_folder()
            if not self.workspace_path:
                self.status_lbl.setText("⚠️ Select a project folder")
                self.log_view.append("⚠️ Cannot run agent: Please select a project workspace directory first.")
                return

        # Determine task prompt based on active tab
        if self.mode_tabs.currentIndex() == 0:
            preset = next((p for p in GOAL_PRESETS if p["id"] == self.selected_goal_id), GOAL_PRESETS[0])
            instruction = preset["prompt"]
        else:
            instruction = self.custom_input.toPlainText().strip()
            if not instruction:
                self.log_view.append("⚠️ Please enter a custom task instruction or switch to Guided Goals.")
                return

        self.diag_banner.setVisible(False)
        self.log_view.clear()
        self.diff_view.clear()
        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ Running Agent...")
        self.stop_btn.setEnabled(True)
        self.status_lbl.setText("Executing...")
        self.output_tabs.setCurrentIndex(0)

        self._update_step(0)
        selected_model = self.model_combo.currentData() or self.model_combo.currentText()
        if "Auto Router" in str(selected_model):
            selected_model = "Auto Router"

        self.worker = AgentWorker(
            workspace_path=self.workspace_path,
            task_instruction=instruction,
            selected_model=selected_model
        )
        self.worker.log_emitted.connect(self._on_log)
        self.worker.diff_emitted.connect(self._on_diff)
        self.worker.finished.connect(self._on_task_finished)
        self.worker.failed.connect(self._on_task_failed)
        self.worker.start()
        self.task_started.emit()

    def _on_log(self, msg: str):
        self.log_view.append(msg)
        if "Generating implementation plan" in msg:
            self._update_step(1)
        elif "Applying" in msg or "file operations" in msg:
            self._update_step(2)
        elif "Running automated test suite" in msg or "Self-Repair" in msg:
            self._update_step(3)

    def _on_diff(self, path: str, diff_text: str):
        self.diff_view.append(f"=== File: {path} ===\n{diff_text}\n\n")

    def _stop_current_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(500)
            self.worker = None
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🚀 Execute Autonomous Task")
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("⏹ Task Cancelled")
        self.log_view.append("\n⏹ Task cancelled by user.")

    def _on_task_finished(self, report: dict):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🚀 Execute Autonomous Task")
        self.stop_btn.setEnabled(False)
        self._refresh_tree()

        is_success = report.get("success", False)
        ops_count = len(report.get("operations", []))

        if is_success:
            self._update_step(4)
            self.status_lbl.setText(f"✅ Succeeded! ({ops_count} files changed)")
            self.log_view.append(f"\n✨ Task execution completed successfully with {ops_count} operations.")
            if ops_count > 0:
                self.output_tabs.setCurrentIndex(1)
        else:
            self.status_lbl.setText("⚠️ Needs Attention")
            err_reason = report.get("error") or report.get("summary") or "No file operations could be generated."
            self.log_view.append(f"\n⚠️ Task stopped: {err_reason}")

            self.diag_msg.setText(
                f"<b>Could not complete coding plan:</b> {err_reason}<br>"
                "👉 <i>Tip: Make sure you have connected an AI model in '✨ Add AI Models' with an active API key, or switch the model dropdown above.</i>"
            )
            self.diag_banner.setVisible(True)

        self.task_finished.emit(report)

    def _on_task_failed(self, error_msg: str):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🚀 Execute Autonomous Task")
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("❌ Failed")
        self.log_view.append(f"\n❌ Execution Error: {error_msg}")
        self.diag_msg.setText(f"<b>Execution Error:</b> {error_msg}")
        self.diag_banner.setVisible(True)

    def _open_settings_dialog(self):
        """Opens settings dialog or general settings tab."""
        top = self.window()
        if hasattr(top, "_open_general_settings"):
            top._open_general_settings(tab_idx=1)
        elif hasattr(top, "_open_api_key_settings"):
            top._open_api_key_settings()
        else:
            try:
                from ui.components.settings_dialog import SettingsDialog
                dlg = SettingsDialog(self)
                dlg.exec()
            except Exception:
                pass
        self._refresh_models()

    def _refresh_models(self):
        """Populates model dropdown with live availability indicators ([● Available] / [○ Unavailable])."""
        if not hasattr(self, "model_combo"):
            return
        prev_data = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        curated = ModelScanner.get_curated_models("coding")
        select_idx = 0
        for i, item in enumerate(curated):
            self.model_combo.addItem(item["display_label"], userData=item["clean_id"])
            if prev_data and item["clean_id"] == prev_data:
                select_idx = i
        self.model_combo.setCurrentIndex(select_idx)
        self.model_combo.blockSignals(False)
        self._update_model_status_chip()

    def _update_model_status_chip(self):
        """Updates activation status chip next to the model selector."""
        if not hasattr(self, "model_combo") or not hasattr(self, "model_status_chip"):
            return
        curr_text = self.model_combo.currentText().strip()
        curr_model = self.model_combo.currentData() or curr_text
        is_active, status_desc = self._check_model_status(str(curr_model))

        if is_active:
            self.model_status_chip.setText("● Available")
            self.model_status_chip.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 209, 255, 0.15);
                    color: #00D1FF;
                    border: 1px solid #00D1FF;
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(0, 209, 255, 0.28);
                }
            """)
            self.model_status_chip.setToolTip(f"Status: {status_desc} — Model is connected & ready")
        else:
            self.model_status_chip.setText("○ Unavailable • Setup Key")
            self.model_status_chip.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 184, 77, 0.15);
                    color: #ffb84d;
                    border: 1px solid rgba(255, 184, 77, 0.6);
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(255, 184, 77, 0.28);
                }
            """)
            self.model_status_chip.setToolTip(f"Status: {status_desc} — Click to connect API key in Settings")

    def _check_model_status(self, model_name: str) -> tuple:
        """Returns (is_available: bool, status_desc: str) for the model via ModelScanner."""
        return ModelScanner.is_model_available(model_name)
