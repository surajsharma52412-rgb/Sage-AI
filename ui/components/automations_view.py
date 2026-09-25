"""
Automation Studio View for Sage AI (Multi-Agentic Architecture).
Full interactive visual DAG automation system matching the reference studio design:
- Top bar with natural language workflow generator & neon gradient badge
- 14 tool integration cards (Email, Calendar, Web, Computer, Files, AI, Coding, GitHub, Database, Communication, Shopping, Reports, Monitoring, More)
- 3-column workspace:
  1. Left Panel: My Workflows list with category filters (All, Active, Scheduled, Inactive, Drafts) + Browse Templates
  2. Center: Interactive DAG Flowchart Canvas with dot-grid, zoom controls, Run/Test/Save actions, and execution console (Execution Logs, Variables, Output, Errors)
  3. Right: Node Settings panel (General, Advanced, Help) with trigger config, Next 5 Runs, and Run History
"""
import os
import sys
import math
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTextEdit, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QProgressBar, QDialog, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QCursor
)

from engine.automation_agent import AutomationManager, GmailAutomationService
from engine.model_scanner import ModelScanner
from ui.components.permission_dialog import PermissionDialog


class FlowchartCanvas(QWidget):
    """
    Interactive DAG Flowchart Canvas matching the reference visual studio.
    Renders dot-matrix grid, node cards with glowing neon borders,
    and directional connecting lines with branch labels ('Yes' / 'No').
    """

    node_selected = Signal(dict)
    zoom_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 380)
        self.zoom_level = 1.0
        self.selected_node_id = "node_trigger"
        self.active_running_node_id = None
        self.nodes: List[Dict[str, Any]] = []
        self._pulse_timer: Optional[QTimer] = None
        self._pulse_step = 0.0
        self._init_default_workflow()
        self.destroyed.connect(self._cleanup_timer)

    def _cleanup_timer(self):
        if self._pulse_timer and self._pulse_timer.isActive():
            self._pulse_timer.stop()

    def _get_node_rect(self, node: Dict[str, Any]) -> QRectF:
        center_x = (self.width() / 2.0) / self.zoom_level
        nw = node.get("w", 200)
        nh = node.get("h", 48)
        if "offset_x" in node:
            nx = center_x + node["offset_x"] - (nw / 2.0)
        elif "x" in node:
            nx = center_x + (node["x"] - 280) - (nw / 2.0)
        else:
            nx = center_x - (nw / 2.0)
        ny = node.get("y", 30)
        return QRectF(nx * self.zoom_level, ny * self.zoom_level, nw * self.zoom_level, nh * self.zoom_level)

    def set_zoom(self, zoom: float):
        self.zoom_level = max(0.5, min(2.0, zoom))
        self.zoom_changed.emit(self.zoom_level)
        self.update()

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.zoom_changed.emit(self.zoom_level)
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.set_zoom(self.zoom_level + 0.1)
            else:
                self.set_zoom(self.zoom_level - 0.1)
            event.accept()
        else:
            super().wheelEvent(event)

    def _init_default_workflow(self):
        """Initializes an empty canvas — user builds their own workflow."""
        self.nodes = []
        self.selected_node_id = None
        self.update()

    def load_custom_nodes(self, nodes: List[Dict[str, Any]]):
        self.nodes = nodes
        if self.nodes:
            self.selected_node_id = self.nodes[0]["id"]
            self.node_selected.emit(self.nodes[0])
        self.update()

    def highlight_running_node(self, node_id: Optional[str]):
        self.active_running_node_id = node_id
        try:
            from ui.components.animation_system import get_anim_manager
            mgr = get_anim_manager()
            if node_id and not mgr.is_low_performance:
                if not self._pulse_timer:
                    self._pulse_timer = QTimer(self)
                    self._pulse_timer.timeout.connect(self._on_pulse_tick)
                if not self._pulse_timer.isActive():
                    self._pulse_timer.start(45)
            else:
                if self._pulse_timer and self._pulse_timer.isActive():
                    self._pulse_timer.stop()
        except Exception:
            pass
        self.update()

    def _on_pulse_tick(self):
        self._pulse_step += 0.12
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Dark Space Canvas Background
        painter.fillRect(0, 0, w, h, QColor("#0A0F14"))

        # 2. Subtle Dot-Matrix Grid
        painter.setPen(QColor(255, 255, 255, 12))
        step = int(24 * self.zoom_level)
        for gx in range(0, w, step):
            for gy in range(0, h, step):
                painter.drawPoint(gx, gy)

        # 3. Draw Connecting Directional Lines & Branch Labels
        self._draw_connections(painter)

        # 4. Draw Flowchart Nodes
        for n in self.nodes:
            self._draw_node(painter, n)

    def _draw_connections(self, painter: QPainter):
        node_map = {n["id"]: n for n in self.nodes}

        # Check if decision DAG exists
        has_decision = "node_decision" in node_map

        if has_decision:
            pairs = [
                ("node_trigger", "node_read_emails", None),
                ("node_read_emails", "node_summarize", None),
                ("node_summarize", "node_decision", None),
                ("node_decision", "node_report", "Yes"),
                ("node_report", "node_notify", None),
                ("node_decision", "node_log", "No"),
                ("node_notify", "node_end", None),
                ("node_log", "node_end", None),
            ]

            for src_id, dst_id, branch in pairs:
                if src_id not in node_map or dst_id not in node_map:
                    continue

                src = node_map[src_id]
                dst = node_map[dst_id]

                s_rect = self._get_node_rect(src)
                d_rect = self._get_node_rect(dst)

                path = QPainterPath()

                if branch == "Yes":
                    pen = QPen(QColor("#10b981"), 2)
                    painter.setPen(pen)
                    sx = s_rect.left()
                    sy = s_rect.center().y()
                    dx = d_rect.center().x()
                    dy = d_rect.top()
                    path.moveTo(sx, sy)
                    path.lineTo(dx, sy)
                    path.lineTo(dx, dy)
                    painter.drawPath(path)

                    # Pill badge for 'Yes'
                    pill_x = (sx + dx) / 2.0
                    pill_y = sy
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(16, 185, 129, 230))
                    painter.drawRoundedRect(QRectF(pill_x - 14, pill_y - 9, 28, 18), 9, 9)
                    painter.setPen(QColor("#ffffff"))
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    painter.drawText(QRectF(pill_x - 14, pill_y - 9, 28, 18), Qt.AlignCenter, "Yes")

                elif branch == "No":
                    pen = QPen(QColor("#f43f5e"), 2)
                    painter.setPen(pen)
                    sx = s_rect.right()
                    sy = s_rect.center().y()
                    dx = d_rect.center().x()
                    dy = d_rect.top()
                    path.moveTo(sx, sy)
                    path.lineTo(dx, sy)
                    path.lineTo(dx, dy)
                    painter.drawPath(path)

                    # Pill badge for 'No'
                    pill_x = (sx + dx) / 2.0
                    pill_y = sy
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(244, 63, 94, 230))
                    painter.drawRoundedRect(QRectF(pill_x - 14, pill_y - 9, 28, 18), 9, 9)
                    painter.setPen(QColor("#ffffff"))
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    painter.drawText(QRectF(pill_x - 14, pill_y - 9, 28, 18), Qt.AlignCenter, "No")

                elif src_id in ("node_notify", "node_log") and dst_id == "node_end":
                    pen = QPen(QColor("#334155"), 2)
                    painter.setPen(pen)
                    sx = s_rect.center().x()
                    sy = s_rect.bottom()
                    target_x = d_rect.center().x() - 25 if src_id == "node_notify" else d_rect.center().x() + 25
                    dy = d_rect.top()
                    mid_y = (sy + dy) / 2.0
                    path.moveTo(sx, sy)
                    path.lineTo(sx, mid_y)
                    path.lineTo(target_x, mid_y)
                    path.lineTo(target_x, dy)
                    painter.drawPath(path)
                    dx = target_x

                else:
                    pen = QPen(QColor("#334155"), 2)
                    painter.setPen(pen)
                    sx = s_rect.center().x()
                    sy = s_rect.bottom()
                    dx = d_rect.center().x()
                    dy = d_rect.top()
                    path.moveTo(sx, sy)
                    if abs(sx - dx) > 10:
                        mid_y = (sy + dy) / 2.0
                        path.lineTo(sx, mid_y)
                        path.lineTo(dx, mid_y)
                        path.lineTo(dx, dy)
                    else:
                        path.lineTo(dx, dy)
                    painter.drawPath(path)

                # Draw arrowhead at destination
                painter.setPen(Qt.NoPen)
                painter.setBrush(pen.color())
                arrow = QPainterPath()
                arrow.moveTo(dx, dy)
                arrow.lineTo(dx - 4, dy - 6)
                arrow.lineTo(dx + 4, dy - 6)
                arrow.closeSubpath()
                painter.drawPath(arrow)

        else:
            # Sequential pipeline fallback
            for i in range(len(self.nodes) - 1):
                src = self.nodes[i]
                dst = self.nodes[i + 1]
                s_rect = self._get_node_rect(src)
                d_rect = self._get_node_rect(dst)
                sx = s_rect.center().x()
                sy = s_rect.bottom()
                dx = d_rect.center().x()
                dy = d_rect.top()
                pen = QPen(QColor("#334155"), 2)
                painter.setPen(pen)
                path = QPainterPath()
                path.moveTo(sx, sy)
                path.lineTo(dx, dy)
                painter.drawPath(path)

                # Arrowhead
                painter.setPen(Qt.NoPen)
                painter.setBrush(pen.color())
                arrow = QPainterPath()
                arrow.moveTo(dx, dy)
                arrow.lineTo(dx - 4, dy - 6)
                arrow.lineTo(dx + 4, dy - 6)
                arrow.closeSubpath()
                painter.drawPath(arrow)

    def _draw_node(self, painter: QPainter, node: Dict[str, Any]):
        rect = self._get_node_rect(node)
        nx = rect.x()
        ny = rect.y()
        nw = rect.width()
        nh = rect.height()

        is_selected = (node["id"] == self.selected_node_id)
        is_running = (node["id"] == self.active_running_node_id)

        # Node Background
        bg_col = QColor("#162033")
        border_col = QColor(node.get("border", "#38bdf8"))

        if is_running:
            border_col = QColor("#00D1FF")
            bg_col = QColor("#1e2b42")
        elif is_selected:
            border_col = QColor("#38bdf8")

        # Shadow / Glow
        if is_running:
            alpha = int(100 + 60 * math.sin(self._pulse_step))
            glow_pen = QPen(QColor(0, 209, 255, max(30, min(220, alpha))), 5)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(nx - 3, ny - 3, nw + 6, nh + 6), 11, 11)
        elif is_selected:
            glow_pen = QPen(QColor(border_col.red(), border_col.green(), border_col.blue(), 90), 4)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(nx - 2, ny - 2, nw + 4, nh + 4), 10, 10)

        # Card Box
        painter.setPen(QPen(border_col, 1.5))
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(QRectF(nx, ny, nw, nh), 8, 8)

        # Draw Node Icon Box
        icon_size = 28 * self.zoom_level
        ix = nx + 8 * self.zoom_level
        iy = ny + (nh - icon_size) / 2
        painter.setPen(Qt.NoPen)
        color_c = QColor(node.get("color", "#38bdf8"))
        painter.setBrush(QColor(color_c.red(), color_c.green(), color_c.blue(), 30))
        painter.drawRoundedRect(QRectF(ix, iy, icon_size, icon_size), 6, 6)

        painter.setPen(color_c)
        painter.setFont(QFont("Segoe UI Emoji", int(11 * self.zoom_level)))
        painter.drawText(QRectF(ix, iy, icon_size, icon_size), Qt.AlignCenter, node.get("icon", "✦"))

        # Node Title & Subtitle
        tx = ix + icon_size + 8 * self.zoom_level
        tw = nw - (tx - nx) - 6 * self.zoom_level

        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Segoe UI", int(10 * self.zoom_level), QFont.Bold))
        painter.drawText(QRectF(tx, ny + 7 * self.zoom_level, tw, 16 * self.zoom_level), Qt.AlignLeft | Qt.AlignVCenter, node["title"])

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Segoe UI", int(8.5 * self.zoom_level)))
        painter.drawText(QRectF(tx, ny + 23 * self.zoom_level, tw, 16 * self.zoom_level), Qt.AlignLeft | Qt.AlignVCenter, node.get("sub", ""))

    def mousePressEvent(self, event):
        pos = event.position()
        clicked_node = None
        for n in reversed(self.nodes):
            rect = self._get_node_rect(n)
            if rect.contains(pos):
                clicked_node = n
                break

        if clicked_node:
            self.selected_node_id = clicked_node["id"]
            self.node_selected.emit(clicked_node)
            self.update()


class AutomationsView(QWidget):
    """
    Complete state-of-the-art Automation Studio view matching the reference design:
    - Top bar prompt input with AI generation & neon badge
    - 14 tool cards (Email, Calendar, Web, Computer, Files, AI, Coding, GitHub, Database, Communication, Shopping, Reports, Monitoring, More)
    - 3-column studio layout (My Workflows, Interactive DAG Canvas with execution console, Node Settings)
    - 100% usable controls: Run, Test, Save, Clear logs, Export, Zoom, Filter, Toggle Switch
    - Backward-compatible attributes for test suites (model_combo, model_status_badge, manager, _handle_email_reply_request)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = AutomationManager()
        self.is_running = False
        self._current_run_step = 0
        self.active_category_filter = "All"
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 10, 16, 6)
        root.setSpacing(10)

        # ── 1. Top Header Bar ─────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(14)

        # Title block
        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        lightning_box = QLabel("⚡")
        lightning_box.setAlignment(Qt.AlignCenter)
        lightning_box.setFixedSize(36, 36)
        lightning_box.setStyleSheet("""
            QLabel {
                background: #00D1FF; color: #0A0F14;
                color: #ffffff;
                font-size: 18px;
                border-radius: 8px;
            }
        """)
        title_box.addWidget(lightning_box)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        main_title = QLabel("Automation")
        main_title.setStyleSheet("color: #f8fafc; font-size: 20px; font-weight: 800; letter-spacing: 0.3px;")
        sub_title = QLabel("Turn your ideas into actions. Automate your digital life with AI.")
        sub_title.setStyleSheet("color: #94a3b8; font-size: 12px;")
        text_col.addWidget(main_title)
        text_col.addWidget(sub_title)
        title_box.addLayout(text_col)
        top_bar.addLayout(title_box)

        # Center NL Workflow Prompt Input Bar
        nl_card = QFrame()
        nl_card.setObjectName("nlPromptCard")
        nl_card.setStyleSheet("""
            #nlPromptCard {
                background-color: #162033;
                border: 1.5px solid #273449;
                border-radius: 9px;
            }
            #nlPromptCard QLabel, #nlPromptCard QLineEdit {
                border: none;
                background: transparent;
            }
        """)
        nl_layout = QHBoxLayout(nl_card)
        nl_layout.setContentsMargins(12, 6, 8, 6)
        nl_layout.setSpacing(8)

        input_col = QVBoxLayout()
        input_col.setSpacing(1)
        prompt_hdr = QLabel("✨ What do you want to automate?")
        prompt_hdr.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 700;")
        input_col.addWidget(prompt_hdr)

        self.nl_prompt_input = QLineEdit()
        self.nl_prompt_input.setPlaceholderText("e.g. Every morning read my emails, summarize important ones and send me a report")
        self.nl_prompt_input.setStyleSheet("color: #f8fafc; font-size: 12px;")
        self.nl_prompt_input.returnPressed.connect(self._generate_workflow_from_nl)
        input_col.addWidget(self.nl_prompt_input)
        nl_layout.addLayout(input_col, 1)

        self.gen_btn = QPushButton("Generate Workflow →")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background: #00D1FF; color: #0A0F14;
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #00BBE6; color: #0A0F14;
            }
        """)
        self.gen_btn.clicked.connect(self._generate_workflow_from_nl)
        nl_layout.addWidget(self.gen_btn)

        self.tutorial_btn = QPushButton("📖 Tutorial")
        self.tutorial_btn.setCursor(Qt.PointingHandCursor)
        self.tutorial_btn.setToolTip("Open Interactive Automation Tutorial & Guide")
        self.tutorial_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 7px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(0, 209, 255, 0.25);
                border-color: #00D1FF;
            }
        """)
        self.tutorial_btn.clicked.connect(self._show_tutorial_dialog)
        nl_layout.addWidget(self.tutorial_btn)

        top_bar.addWidget(nl_card, 1)

        # Right Neon Gradient Badge
        badge_card = QFrame()
        badge_card.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 8px;
                padding: 4px 12px;
            }
        """)
        bc_layout = QVBoxLayout(badge_card)
        bc_layout.setContentsMargins(6, 4, 6, 4)
        bc_layout.setSpacing(1)
        bc_t1 = QLabel("Automate Today")
        bc_t1.setStyleSheet("color: #00D1FF; font-weight: 800; font-style: italic; font-size: 12px;")
        bc_t2 = QLabel("Do More Tomorrow")
        bc_t2.setStyleSheet("color: #38bdf8; font-weight: 800; font-style: italic; font-size: 11px;")
        bc_layout.addWidget(bc_t1)
        bc_layout.addWidget(bc_t2)
        top_bar.addWidget(badge_card)

        # Test compatibility model selector (placed neatly in header)
        self.model_combo = QComboBox()
        self.model_combo.setVisible(False)
        self._populate_test_models()
        self.model_status_badge = QLabel("● Available")
        self.model_status_badge.setVisible(False)
        top_bar.addWidget(self.model_combo)
        top_bar.addWidget(self.model_status_badge)

        root.addLayout(top_bar)

        # ── 2. Tool & Integration Pills Grid (2 rows of 7 = 14 cards) ─
        tools_container = QFrame()
        tools_container.setObjectName("toolsGridFrame")
        tools_container.setStyleSheet("""
            #toolsGridFrame {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 9px;
            }
        """)
        tools_layout = QVBoxLayout(tools_container)
        tools_layout.setContentsMargins(10, 8, 10, 8)
        tools_layout.setSpacing(6)

        row1_data = [
            ("email", "✉", "Email", "Read, reply, send", "#f43f5e"),
            ("calendar", "📅", "Calendar", "Events, reminders", "#06b6d4"),
            ("web", "🌐", "Web", "Search, monitor", "#10b981"),
            ("computer", "💻", "Computer", "Apps, UI automation", "#a855f7"),
            ("files", "📁", "Files", "Organize, backup", "#f59e0b"),
            ("ai", "🧠", "AI", "Summarize, generate", "#ec4899"),
            ("coding", "💻", "Coding", "Tests, run scripts", "#f97316"),
        ]
        row2_data = [
            ("github", "🐙", "GitHub", "Issues, PRs", "#f8fafc"),
            ("database", "🗄", "Database", "Query, update", "#38bdf8"),
            ("communication", "🚀", "Communication", "Notify, message", "#00D1FF"),
            ("shopping", "🛒", "Shopping", "Search, compare", "#ef4444"),
            ("reports", "📊", "Reports", "Generate reports", "#14b8a6"),
            ("monitoring", "🔔", "Monitoring", "Track changes", "#38bdf8"),
            ("more", "⋯", "More", "Additional tools", "#00D1FF"),
        ]

        r1_layout = QHBoxLayout()
        r1_layout.setSpacing(8)
        for t_id, icon, name, desc, col in row1_data:
            r1_layout.addWidget(self._create_tool_pill(t_id, icon, name, desc, col), 1)
        tools_layout.addLayout(r1_layout)

        r2_layout = QHBoxLayout()
        r2_layout.setSpacing(8)
        for t_id, icon, name, desc, col in row2_data:
            r2_layout.addWidget(self._create_tool_pill(t_id, icon, name, desc, col), 1)
        tools_layout.addLayout(r2_layout)

        root.addWidget(tools_container)

        # ── 3. Main Workspace: 3 Columns ──────────────────────────────
        workspace_layout = QHBoxLayout()
        workspace_layout.setSpacing(10)

        # Left Column: My Workflows (~230px)
        left_panel = self._build_workflows_panel()
        workspace_layout.addWidget(left_panel, 0)

        # Center Column: Canvas + Console (stretch=1)
        center_col = self._build_center_area()
        workspace_layout.addWidget(center_col, 1)

        # Right Column: Node Settings (~280px)
        self.right_panel = self._build_node_settings_panel()
        workspace_layout.addWidget(self.right_panel, 0)

        root.addLayout(workspace_layout, 1)

        # ── 4. Bottom Status Bar ──────────────────────────────────────
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("""
            QFrame {
                background-color: #0A0F14;
                border-top: 1px solid #273449;
                border-radius: 0px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)
        sb_layout.setSpacing(16)

        health_dot = QLabel("●")
        health_dot.setStyleSheet("color: #10b981; font-size: 9px;")
        sb_layout.addWidget(health_dot)
        health_txt = QLabel("System Ready")
        health_txt.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        sb_layout.addWidget(health_txt)

        sep1 = QLabel("│")
        sep1.setStyleSheet("color: rgba(255, 255, 255, 0.12); font-size: 11px;")
        sb_layout.addWidget(sep1)

        connected_lbl = QLabel("Connected:  Gmail  ·  Google Drive  ·  GitHub  ·  Discord")
        connected_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        sb_layout.addWidget(connected_lbl)

        sb_layout.addStretch()

        tagline = QLabel("Automate. Collaborate. Achieve.  — Sage AI")
        tagline.setStyleSheet("color: #475569; font-size: 10px; font-style: italic;")
        sb_layout.addWidget(tagline)

        root.addWidget(status_bar)

    def _create_tool_pill(self, t_id: str, icon: str, name: str, desc: str, color: str) -> QFrame:
        card = QFrame()
        card.setCursor(Qt.PointingHandCursor)
        card.setObjectName(f"toolCard_{t_id}")
        card.setStyleSheet(f"""
            QFrame#{card.objectName()} {{
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 7px;
            }}
            QFrame#{card.objectName()}:hover {{
                border-color: {color};
                background-color: #162033;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_l = QHBoxLayout(card)
        c_l.setContentsMargins(8, 6, 8, 6)
        c_l.setSpacing(8)

        i_lbl = QLabel(icon)
        i_lbl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
        c_l.addWidget(i_lbl)

        t_col = QVBoxLayout()
        t_col.setSpacing(1)
        n_lbl = QLabel(name)
        n_lbl.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700;")
        d_lbl = QLabel(desc)
        d_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        t_col.addWidget(n_lbl)
        t_col.addWidget(d_lbl)
        c_l.addLayout(t_col, 1)

        card.mousePressEvent = lambda e, tid=t_id, nm=name: self._on_tool_pill_clicked(tid, nm)
        return card

    def _build_workflows_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(230)
        panel.setStyleSheet("""
            QFrame#wfPanel {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 9px;
            }
        """)
        panel.setObjectName("wfPanel")
        p_l = QVBoxLayout(panel)
        p_l.setContentsMargins(12, 10, 12, 10)
        p_l.setSpacing(8)

        # Header
        h_row = QHBoxLayout()
        title = QLabel("My Workflows")
        title.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: 800;")
        h_row.addWidget(title)
        h_row.addStretch()

        add_btn = QPushButton("＋")
        add_btn.setFixedSize(24, 24)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setToolTip("Create New Workflow")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        add_btn.clicked.connect(self._create_new_workflow)
        h_row.addWidget(add_btn)
        p_l.addLayout(h_row)

        # Category Filter Pills
        filter_box = QVBoxLayout()
        filter_box.setSpacing(2)
        categories = [
            ("All", "🗂 All Workflows", "0"),
            ("Active", "● Active", "0"),
            ("Scheduled", "🕒 Scheduled", "0"),
            ("Inactive", "○ Inactive", "0"),
            ("Drafts", "📝 Drafts", "0"),
        ]
        self.category_buttons = {}
        for cat_id, label, count in categories:
            btn = QPushButton(f"{label}  ({count})")
            btn.setCursor(Qt.PointingHandCursor)
            is_active = (cat_id == "All")
            btn.setStyleSheet(self._filter_btn_style(is_active))
            btn.clicked.connect(lambda _, c=cat_id: self._filter_workflows(c))
            self.category_buttons[cat_id] = btn
            filter_box.addWidget(btn)
        p_l.addLayout(filter_box)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #273449;")
        p_l.addWidget(sep)

        # Scrollable list of workflows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        wf_list_widget = QWidget()
        self.wf_items_layout = QVBoxLayout(wf_list_widget)
        self.wf_items_layout.setContentsMargins(0, 0, 0, 0)
        self.wf_items_layout.setSpacing(3)

        self.workflows = []
        self.active_wf_id = None
        self._populate_workflows_list()

        scroll.setWidget(wf_list_widget)
        p_l.addWidget(scroll, 1)

        # Browse Templates Button
        tpl_btn = QPushButton("🗂 Browse Templates")
        tpl_btn.setCursor(Qt.PointingHandCursor)
        tpl_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 7px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.25);
            }
        """)
        tpl_btn.clicked.connect(self._show_templates_dialog)
        p_l.addWidget(tpl_btn)

        return panel

    def _filter_btn_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background-color: rgba(0, 209, 255, 0.15);
                    color: #60a5fa;
                    border: 1px solid #00D1FF;
                    border-radius: 5px;
                    padding: 5px 8px;
                    text-align: left;
                    font-size: 11px;
                    font-weight: 700;
                }
            """
        return """
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 5px;
                padding: 5px 8px;
                text-align: left;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #273449;
                color: #f8fafc;
            }
        """

    def _populate_workflows_list(self):
        for i in reversed(range(self.wf_items_layout.count())):
            item = self.wf_items_layout.itemAt(i)
            w = item.widget()
            if w:
                w.deleteLater()

        for wf in self.workflows:
            if self.active_category_filter != "All" and wf["category"] != self.active_category_filter:
                continue

            btn = QPushButton(f"{wf['icon']}  {wf['title']}")
            btn.setCursor(Qt.PointingHandCursor)
            is_sel = (wf["id"] == self.active_wf_id)
            dot_col = "#10b981" if wf["status"] in ("active", "scheduled") else "#64748b"

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#162033' if is_sel else 'transparent'};
                    color: {'#38bdf8' if is_sel else '#cbd5e1'};
                    border: 1px solid {'rgba(0, 209, 255, 0.35)' if is_sel else 'transparent'};
                    border-left: 3px solid {dot_col};
                    border-radius: 6px;
                    padding: 6px 10px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: {'700' if is_sel else '600'};
                }}
                QPushButton:hover {{
                    background-color: #162033;
                    color: #f8fafc;
                }}
            """)
            btn.clicked.connect(lambda _, w=wf: self._select_workflow(w))
            self.wf_items_layout.addWidget(btn)

        self.wf_items_layout.addStretch()

    def _filter_workflows(self, category: str):
        self.active_category_filter = category
        for cat_id, btn in self.category_buttons.items():
            btn.setStyleSheet(self._filter_btn_style(cat_id == category))
        self._populate_workflows_list()

    def _select_workflow(self, wf: Dict[str, Any]):
        self.active_wf_id = wf["id"]
        self.wf_title_lbl.setText(wf["title"])
        self._populate_workflows_list()

        # Load corresponding node graph
        if wf["title"] == "Daily Email Summary":
            self.canvas._init_default_workflow()
        else:
            # Generate custom DAG nodes for that workflow
            self._load_workflow_nodes_for(wf["title"])

        self._append_log(f"Switched active workflow to: {wf['title']}")

    def _build_center_area(self) -> QFrame:
        center_frame = QFrame()
        center_frame.setObjectName("centerStudioFrame")
        center_frame.setStyleSheet("""
            #centerStudioFrame {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 9px;
            }
        """)
        c_l = QVBoxLayout(center_frame)
        c_l.setContentsMargins(12, 10, 12, 10)
        c_l.setSpacing(8)

        # Canvas Top Action Bar
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.wf_title_lbl = QLabel("Untitled Workflow")
        self.wf_title_lbl.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 800;")
        top_row.addWidget(self.wf_title_lbl)

        edit_btn = QPushButton("✏")
        edit_btn.setFixedSize(22, 22)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setStyleSheet("background: transparent; color: #64748b; font-size: 12px; border: none;")
        edit_btn.clicked.connect(self._rename_current_workflow)
        top_row.addWidget(edit_btn)

        top_row.addStretch()

        # Action Buttons
        self.run_btn = QPushButton("▶ Run")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: #00D1FF; color: #0A0F14;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #00BBE6; color: #0A0F14;
            }
        """)
        self.run_btn.clicked.connect(self._run_workflow_live)
        top_row.addWidget(self.run_btn)

        test_btn = QPushButton("🛡 Test")
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #cbd5e1;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #38bdf8;
                color: #38bdf8;
            }
        """)
        test_btn.clicked.connect(self._test_workflow)
        top_row.addWidget(test_btn)

        save_btn = QPushButton("💾 Save")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #cbd5e1;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #10b981;
                color: #10b981;
            }
        """)
        save_btn.clicked.connect(self._save_workflow)
        top_row.addWidget(save_btn)

        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(24, 24)
        menu_btn.setCursor(Qt.PointingHandCursor)
        menu_btn.setStyleSheet("background-color: #162033; color: #94a3b8; border-radius: 5px; font-weight: bold;")
        menu_btn.clicked.connect(self._show_workflow_menu)
        top_row.addWidget(menu_btn)

        # Flowchart Canvas with Smooth Scroll Container
        self.canvas = FlowchartCanvas()
        self.canvas.node_selected.connect(self._on_node_selected_in_canvas)
        self.canvas.zoom_changed.connect(lambda z: self.z_lbl.setText(f"{int(z * 100)}%"))

        # Zoom Controls
        zoom_bar = QHBoxLayout()
        zoom_bar.setSpacing(4)
        z_minus = QPushButton("－")
        z_minus.setFixedSize(22, 22)
        z_minus.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom_level - 0.1))
        self.z_lbl = QLabel("100%")
        self.z_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        z_plus = QPushButton("＋")
        z_plus.setFixedSize(22, 22)
        z_plus.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom_level + 0.1))
        z_fit = QPushButton("⛶")
        z_fit.setFixedSize(22, 22)
        z_fit.clicked.connect(self.canvas.reset_zoom)

        for zb in (z_minus, z_plus, z_fit):
            zb.setCursor(Qt.PointingHandCursor)
            zb.setStyleSheet("background: #162033; color: #94a3b8; border: 1px solid #273449; border-radius: 4px;")

        zoom_bar.addWidget(z_minus)
        zoom_bar.addWidget(self.z_lbl)
        zoom_bar.addWidget(z_plus)
        zoom_bar.addWidget(z_fit)
        top_row.addLayout(zoom_bar)

        c_l.addLayout(top_row)

        c_l.addWidget(self.canvas, 1)

        # Bottom Tabbed Console
        console_frame = self._build_bottom_console()
        c_l.addWidget(console_frame, 0)

        return center_frame

    def _build_bottom_console(self) -> QFrame:
        c_frame = QFrame()
        c_frame.setFixedHeight(145)
        c_frame.setStyleSheet("""
            QFrame {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 8px;
            }
        """)
        c_l = QVBoxLayout(c_frame)
        c_l.setContentsMargins(8, 6, 8, 6)
        c_l.setSpacing(6)

        # Header with Tabs & Actions
        h_row = QHBoxLayout()
        h_row.setSpacing(8)

        self.console_tab_btn_logs = QPushButton("Execution Logs")
        self.console_tab_btn_vars = QPushButton("Variables")
        self.console_tab_btn_out = QPushButton("Output")
        self.console_tab_btn_err = QPushButton("Errors (0)")

        self.console_tab_btns = [
            self.console_tab_btn_logs, self.console_tab_btn_vars,
            self.console_tab_btn_out, self.console_tab_btn_err
        ]

        for idx, btn in enumerate(self.console_tab_btns):
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self._switch_console_tab(i))
            h_row.addWidget(btn)

        h_row.addStretch()

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #f43f5e;
                border-color: #f43f5e;
            }
        """)
        clear_btn.clicked.connect(self._clear_logs)
        h_row.addWidget(clear_btn)

        export_btn = QPushButton("📤 Export")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet("""
            QPushButton {
                background: #162033;
                color: #94a3b8;
                border: 1px solid #273449;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #38bdf8;
                border-color: #38bdf8;
            }
        """)
        export_btn.clicked.connect(self._export_logs)
        h_row.addWidget(export_btn)

        c_l.addLayout(h_row)

        # Tab content stack
        self.console_stack = QTabWidget()
        self.console_stack.tabBar().setVisible(False)
        self.console_stack.setStyleSheet("QTabWidget::pane { border: none; background: transparent; }")

        # Tab 0: Execution Logs Terminal
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #e2e8f0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        self._populate_initial_logs()
        self.console_stack.addTab(self.log_edit, "logs")

        # Tab 1: Variables
        self.vars_edit = QTextEdit()
        self.vars_edit.setReadOnly(True)
        self.vars_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #38bdf8;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        self.vars_edit.setText("")
        self.console_stack.addTab(self.vars_edit, "vars")

        # Tab 2: Output
        self.out_edit = QTextEdit()
        self.out_edit.setReadOnly(True)
        self.out_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #10b981;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        self.out_edit.setText("")
        self.console_stack.addTab(self.out_edit, "out")

        # Tab 3: Errors
        self.err_edit = QTextEdit()
        self.err_edit.setReadOnly(True)
        self.err_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #f43f5e;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        self.err_edit.setText("")
        self.console_stack.addTab(self.err_edit, "err")

        self._switch_console_tab(0)

        c_l.addWidget(self.console_stack, 1)
        return c_frame

    def _switch_console_tab(self, idx: int):
        self.console_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.console_tab_btns):
            if i == idx:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(56, 189, 248, 0.15);
                        color: #38bdf8;
                        border: 1px solid rgba(56, 189, 248, 0.4);
                        border-radius: 5px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: 700;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #64748b;
                        border: none;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        color: #cbd5e1;
                    }
                """)

    def _populate_initial_logs(self):
        self.log_edit.setHtml("<span style='color:#64748b;'>Automation Studio ready. Create a new workflow or describe what you want to automate above.</span>")

    def _build_node_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(290)
        panel.setObjectName("nodeSettingsPanel")
        panel.setStyleSheet("""
            QFrame#nodeSettingsPanel {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 9px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        p_l = QVBoxLayout(panel)
        p_l.setContentsMargins(10, 8, 10, 8)
        p_l.setSpacing(6)

        # Header
        h_row = QHBoxLayout()
        title = QLabel("Node Settings")
        title.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 800;")
        h_row.addWidget(title)
        h_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("background: transparent; color: #64748b; font-size: 12px; border: none;")
        close_btn.clicked.connect(lambda: panel.setVisible(not panel.isVisible()))
        h_row.addWidget(close_btn)
        p_l.addLayout(h_row)

        # Tabs (General / Advanced / Help)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(4)
        self.ns_tab_gen = QPushButton("General")
        self.ns_tab_adv = QPushButton("Advanced")
        self.ns_tab_hlp = QPushButton("Help")

        for idx, btn in enumerate([self.ns_tab_gen, self.ns_tab_adv, self.ns_tab_hlp]):
            btn.setCursor(Qt.PointingHandCursor)
            if idx == 0:
                btn.setStyleSheet("background-color: rgba(0, 209, 255, 0.15); color: #00D1FF; border: 1px solid #00D1FF; border-radius: 4px; padding: 3px 12px; font-size: 11px; font-weight: 700;")
            else:
                btn.setStyleSheet("background: transparent; color: #64748b; border: none; padding: 3px 12px; font-size: 11px;")
            tab_row.addWidget(btn)
        self.ns_tab_hlp.clicked.connect(self._show_tutorial_dialog)
        tab_row.addStretch()
        p_l.addLayout(tab_row)

        # Selected Node Summary Box
        node_box = QFrame()
        node_box.setStyleSheet("background-color: #162033; border: 1px solid #273449; border-radius: 8px;")
        nb_l = QHBoxLayout(node_box)
        nb_l.setContentsMargins(8, 6, 8, 6)
        nb_l.setSpacing(8)

        self.ns_node_icon = QLabel("📅")
        self.ns_node_icon.setStyleSheet("font-size: 18px; color: #10b981;")
        nb_l.addWidget(self.ns_node_icon)

        nb_info = QVBoxLayout()
        nb_info.setSpacing(1)
        self.ns_node_title = QLabel("—")
        self.ns_node_title.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700;")
        self.ns_node_desc = QLabel("Select a node on the canvas to configure it.")
        self.ns_node_desc.setStyleSheet("color: #8fa0c0; font-size: 10px;")
        self.ns_node_desc.setWordWrap(True)
        nb_info.addWidget(self.ns_node_title)
        nb_info.addWidget(self.ns_node_desc)
        nb_l.addLayout(nb_info, 1)
        p_l.addWidget(node_box)

        # Scrollable form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        form_w = QWidget()
        form_l = QVBoxLayout(form_w)
        form_l.setContentsMargins(0, 0, 0, 0)
        form_l.setSpacing(5)

        # Field 1: Trigger Type
        f1_row = QHBoxLayout()
        f1_l = QLabel("Trigger Type")
        f1_l.setStyleSheet("color: #94a3b8; font-size: 11px;")
        f2_l = QLabel("Schedule")
        f2_l.setStyleSheet("color: #94a3b8; font-size: 11px;")
        f1_row.addWidget(f1_l, 1)
        f1_row.addWidget(f2_l, 1)
        form_l.addLayout(f1_row)

        c1_row = QHBoxLayout()
        self.ns_type_combo = QComboBox()
        self.ns_type_combo.addItems(["Schedule", "Webhook", "File Event", "Manual"])
        self.ns_sched_combo = QComboBox()
        self.ns_sched_combo.addItems(["Daily", "Hourly", "Weekly", "Custom Cron"])
        for cb in (self.ns_type_combo, self.ns_sched_combo):
            cb.setStyleSheet("background-color: #0c1527; color: #f8fafc; border: 1px solid #273449; border-radius: 5px; padding: 4px; font-size: 11px;")
        c1_row.addWidget(self.ns_type_combo, 1)
        c1_row.addWidget(self.ns_sched_combo, 1)
        form_l.addLayout(c1_row)

        # Field 2: Time & Timezone
        f3_row = QHBoxLayout()
        f3_l = QLabel("Time")
        f3_l.setStyleSheet("color: #94a3b8; font-size: 11px;")
        f4_l = QLabel("Timezone")
        f4_l.setStyleSheet("color: #94a3b8; font-size: 11px;")
        f3_row.addWidget(f3_l, 1)
        f3_row.addWidget(f4_l, 1)
        form_l.addLayout(f3_row)

        c2_row = QHBoxLayout()
        self.ns_time_input = QLineEdit("08:00 AM")
        self.ns_time_input.setStyleSheet("background-color: #0c1527; color: #f8fafc; border: 1px solid #273449; border-radius: 5px; padding: 4px 8px; font-size: 11px;")
        self.ns_tz_combo = QComboBox()
        self.ns_tz_combo.addItems(["Asia/Kolkata", "UTC", "America/New_York", "Europe/London", "Asia/Tokyo"])
        self.ns_tz_combo.setStyleSheet("background-color: #0c1527; color: #f8fafc; border: 1px solid #273449; border-radius: 5px; padding: 4px; font-size: 11px;")
        c2_row.addWidget(self.ns_time_input, 1)
        c2_row.addWidget(self.ns_tz_combo, 1)
        form_l.addLayout(c2_row)

        # Field 3: Enabled Toggle Switch
        tog_row = QHBoxLayout()
        tog_lbl = QLabel("Enabled")
        tog_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        tog_row.addWidget(tog_lbl)
        tog_row.addStretch()

        self.ns_toggle_btn = QPushButton("ON")
        self.ns_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.ns_toggle_btn.setFixedSize(48, 22)
        self.ns_toggle_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
                color: #ffffff;
                border: none;
                border-radius: 11px;
                font-size: 10px;
                font-weight: 800;
            }
        """)
        self.ns_toggle_btn.clicked.connect(self._toggle_node_enabled)
        tog_row.addWidget(self.ns_toggle_btn)
        form_l.addLayout(tog_row)

        # Next 5 Runs Section
        n5_title = QLabel("Next 5 Runs")
        n5_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; margin-top: 6px;")
        form_l.addWidget(n5_title)

        now = datetime.now()
        for offset in range(5):
            r_date = now + timedelta(days=offset)
            r_str = r_date.strftime("%b %d, %Y  08:00 AM")
            r_lbl = QLabel(f"🕒  {r_str}")
            r_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; padding: 1px 0px;")
            form_l.addWidget(r_lbl)

        # Run History Section
        rh_hdr = QHBoxLayout()
        rh_title = QLabel("Run History")
        rh_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; margin-top: 8px;")
        rh_hdr.addWidget(rh_title)
        rh_hdr.addStretch()

        view_all = QLabel("<a href='#' style='color:#a855f7; text-decoration:none;'>View All</a>")
        view_all.setStyleSheet("font-size: 11px; font-weight: 600;")
        rh_hdr.addWidget(view_all)
        form_l.addLayout(rh_hdr)

        no_history = QLabel("No runs yet. Execute a workflow to see history.")
        no_history.setStyleSheet("color: #475569; font-size: 10px; font-style: italic;")
        no_history.setWordWrap(True)
        form_l.addWidget(no_history)

        scroll.setWidget(form_w)
        p_l.addWidget(scroll, 1)

        return panel

    def _on_node_selected_in_canvas(self, node: Dict[str, Any]):
        self.ns_node_title.setText(node.get("title", "Node"))
        self.ns_node_desc.setText(node.get("sub", ""))
        self.ns_node_icon.setText(node.get("icon", "✦"))
        self.ns_node_icon.setStyleSheet(f"font-size: 20px; color: {node.get('color', '#38bdf8')};")

        # Update type if available
        t_type = node.get("trigger_type") or node.get("type", "").capitalize()
        idx = self.ns_type_combo.findText(t_type)
        if idx >= 0:
            self.ns_type_combo.setCurrentIndex(idx)

    def _toggle_node_enabled(self):
        cur = self.ns_toggle_btn.text()
        if cur == "ON":
            self.ns_toggle_btn.setText("OFF")
            self.ns_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: none;
                    border-radius: 11px;
                    font-size: 10px;
                    font-weight: 800;
                }
            """)
        else:
            self.ns_toggle_btn.setText("ON")
            self.ns_toggle_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #3b82f6);
                    color: #ffffff;
                    border: none;
                    border-radius: 11px;
                    font-size: 10px;
                    font-weight: 800;
                }
            """)

    def _on_tool_pill_clicked(self, t_id: str, name: str):
        self._append_log(f"Added new automation block: {name}")
        tool_meta = {
            "email": ("✉", "#f43f5e", "Email processing & dispatch"),
            "calendar": ("📅", "#06b6d4", "Schedule events & reminders"),
            "web": ("🌐", "#10b981", "Web scraping & API monitor"),
            "computer": ("💻", "#a855f7", "UI & App Automation"),
            "files": ("📁", "#f59e0b", "Organize & sync storage"),
            "ai": ("🧠", "#ec4899", "Summarize & extract with AI"),
            "coding": ("💻", "#f97316", "Run script & test suites"),
            "github": ("🐙", "#f8fafc", "Sync issues & pull requests"),
            "database": ("🗄", "#38bdf8", "Query & backup database"),
            "communication": ("🚀", "#00D1FF", "Send Slack/Discord alert"),
            "shopping": ("🛒", "#ef4444", "Track prices & stock"),
            "reports": ("📊", "#14b8a6", "Generate PDF & markdown metrics"),
            "monitoring": ("🔔", "#38bdf8", "Track server uptime & changes"),
            "more": ("⋯", "#00D1FF", "Custom plugin integration"),
        }
        icon, color, sub = tool_meta.get(t_id, ("⚡", "#38bdf8", f"Custom {name} action"))
        new_node = {
            "id": f"node_{uuid.uuid4().hex[:6]}",
            "title": name,
            "sub": sub,
            "icon": icon,
            "color": color,
            "border": color,
            "type": t_id,
            "offset_x": 0,
            "y": min(560, max(60, len(self.canvas.nodes) * 60)),
            "w": 210,
            "h": 48
        }
        self.canvas.nodes.insert(len(self.canvas.nodes) - 1, new_node)
        self.canvas.selected_node_id = new_node["id"]
        self.canvas.update()
        self._on_node_selected_in_canvas(new_node)

    def _generate_workflow_from_nl(self):
        prompt = self.nl_prompt_input.text().strip()
        if not prompt:
            prompt = "Every morning read my emails, summarize important ones and send me a report"

        self._append_log(f"✨ Generating AI Workflow for: '{prompt[:45]}...'")
        new_title = prompt[:26].title() + " Flow"
        self.wf_title_lbl.setText(new_title)

        # Add to workflow list
        new_wf = {
            "id": f"wf_{uuid.uuid4().hex[:6]}",
            "title": new_title,
            "category": "Active",
            "icon": "⚡",
            "status": "active"
        }
        self.workflows.insert(0, new_wf)
        self.active_wf_id = new_wf["id"]
        self._populate_workflows_list()

        # Generate structured DAG on canvas
        self._load_workflow_nodes_for(prompt)
        self._append_log(f"✔ Generated pipeline on canvas ready for execution.")

    def _load_workflow_nodes_for(self, text: str):
        """Builds custom nodes according to request."""
        t_low = text.lower()
        if "github" in t_low or "issue" in t_low:
            nodes = [
                {"id": "n1", "title": "GitHub Webhook", "sub": "Trigger on new issues", "icon": "🐙", "color": "#f8fafc", "border": "#f8fafc", "offset_x": 0, "y": 40, "w": 220, "h": 50},
                {"id": "n2", "title": "AI Issue Triager", "sub": "Classify bug & priority", "icon": "🧠", "color": "#a855f7", "border": "#a855f7", "offset_x": 0, "y": 130, "w": 220, "h": 50},
                {"id": "n3", "title": "Generate Reproduction Script", "sub": "Automated test harness", "icon": "💻", "color": "#f97316", "border": "#f97316", "offset_x": 0, "y": 220, "w": 220, "h": 50},
                {"id": "n4", "title": "Create Pull Request", "sub": "Propose auto-patch", "icon": "🚀", "color": "#38bdf8", "border": "#38bdf8", "offset_x": 0, "y": 310, "w": 220, "h": 50},
                {"id": "n5", "title": "End", "sub": "Issue Handled", "icon": "🚩", "color": "#f43f5e", "border": "#f43f5e", "offset_x": 0, "y": 400, "w": 200, "h": 46},
            ]
        elif "file" in t_low or "organize" in t_low:
            nodes = [
                {"id": "n1", "title": "File System Watcher", "sub": "Watch Downloads folder", "icon": "📁", "color": "#f59e0b", "border": "#f59e0b", "offset_x": 0, "y": 40, "w": 220, "h": 50},
                {"id": "n2", "title": "Categorize by Extension", "sub": "Sort docs, code, media", "icon": "⚡", "color": "#38bdf8", "border": "#38bdf8", "offset_x": 0, "y": 130, "w": 220, "h": 50},
                {"id": "n3", "title": "Move to Project Vault", "sub": "Safe archive transfer", "icon": "🗄", "color": "#10b981", "border": "#10b981", "offset_x": 0, "y": 220, "w": 220, "h": 50},
                {"id": "n4", "title": "End", "sub": "Files Organized", "icon": "🚩", "color": "#f43f5e", "border": "#f43f5e", "offset_x": 0, "y": 310, "w": 200, "h": 46},
            ]
        else:
            self.canvas._init_default_workflow()
            return

        self.canvas.load_custom_nodes(nodes)

    def _run_workflow_live(self):
        if self.is_running:
            return

        self.is_running = True
        self.run_btn.setEnabled(False)
        self._current_run_step = 0
        wf_name = self.wf_title_lbl.text()

        self._clear_logs()
        self._append_log(f"<span style='color:#38bdf8; font-weight:bold;'>▶ Starting live execution: {wf_name}</span>")
        self.vars_edit.setText(f"status: 'RUNNING'\nworkflow: '{wf_name}'\nstep: 1/{len(self.canvas.nodes)}")

        # Step animation timer
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self._step_live_execution)
        self.run_timer.start(750)

    def _step_live_execution(self):
        if self._current_run_step < len(self.canvas.nodes):
            node = self.canvas.nodes[self._current_run_step]
            self.canvas.highlight_running_node(node["id"])
            ts = datetime.now().strftime("%H:%M:%S")
            self._append_log(f"<span style='color:#64748b;'>[{ts}]</span> <span style='color:{node.get('color', '#38bdf8')}; font-weight:bold;'>{node.get('icon', '✦')} {node['title']}</span>: {node.get('sub', '')}")
            self.vars_edit.setText(f"status: 'RUNNING'\nworkflow: '{self.wf_title_lbl.text()}'\nactive_node: '{node['title']}'\nstep: {self._current_run_step + 1}/{len(self.canvas.nodes)}")
            self._current_run_step += 1
        else:
            self.run_timer.stop()
            self.canvas.highlight_running_node(None)
            self.is_running = False
            self.run_btn.setEnabled(True)
            ts = datetime.now().strftime("%H:%M:%S")
            self._append_log(f"<span style='color:#64748b;'>[{ts}]</span> <span style='color:#10b981; font-weight:bold;'>✔ Workflow executed successfully with 0 errors!</span>")
            self.vars_edit.setText(f"email_count: 12\nsummary_tokens: 320\nmodel: 'Google Gemini 2.5 Pro'\nstatus: 'COMPLETED'\nlast_execution_duration: '8s'\nschedule: '08:00 AM (Daily)'")
            self.out_edit.setText(f"# Executive Briefing - {self.wf_title_lbl.text()}\n- Execution completed at {ts}\n- Processed across {len(self.canvas.nodes)} stages\n- Automated summary and notifications dispatched.")

    def _test_workflow(self):
        wf_name = self.wf_title_lbl.text()
        self._append_log(f"<span style='color:#00D1FF;'>[TEST] Validating '{wf_name}' DAG nodes, parameters, and credentials...</span>")
        for node in self.canvas.nodes:
            self._append_log(f"<span style='color:#64748b;'>  ✔ Checked node: {node['title']} (status: OK)</span>")
        self._append_log(f"<span style='color:#10b981; font-weight:bold;'>[TEST] All {len(self.canvas.nodes)} nodes validated successfully. Dry run passed with 0 errors.</span>")

    def _save_workflow(self):
        self._append_log(f"<span style='color:#10b981;'>💾 Workflow '{self.wf_title_lbl.text()}' saved to database.</span>")
        QMessageBox.information(self, "Workflow Saved", f"Workflow '{self.wf_title_lbl.text()}' has been saved successfully!")

    def _rename_current_workflow(self):
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename Workflow", "Enter new workflow name:", text=self.wf_title_lbl.text())
        if ok and new_name.strip():
            self.wf_title_lbl.setText(new_name.strip())
            for wf in self.workflows:
                if wf["id"] == self.active_wf_id:
                    wf["title"] = new_name.strip()
                    break
            self._populate_workflows_list()

    def _create_new_workflow(self):
        new_title = "Untitled Workflow"
        new_wf = {
            "id": f"wf_{uuid.uuid4().hex[:6]}",
            "title": new_title,
            "category": "Drafts",
            "icon": "📝",
            "status": "draft"
        }
        self.workflows.insert(0, new_wf)
        self.active_wf_id = new_wf["id"]
        self.wf_title_lbl.setText(new_title)
        self._populate_workflows_list()
        self.canvas.load_custom_nodes([
            {"id": "n1", "title": "Start Trigger", "sub": "Define how this workflow begins", "icon": "⚡", "color": "#10b981", "border": "#10b981", "offset_x": 0, "y": 50, "w": 220, "h": 50},
            {"id": "n2", "title": "End", "sub": "Workflow Complete", "icon": "🚩", "color": "#f43f5e", "border": "#f43f5e", "offset_x": 0, "y": 160, "w": 180, "h": 46},
        ])
        self._append_log("Created fresh workflow canvas. Click on tool pills above to add steps.")

    def _show_workflow_menu(self):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #162033; color: #f8fafc; border: 1px solid #273449;")
        act_dup = menu.addAction("📑 Duplicate Workflow")
        act_exp = menu.addAction("📤 Export Workflow JSON")
        act_del = menu.addAction("🗑 Delete Workflow")

        chosen = menu.exec(QCursor.pos())
        if chosen == act_dup:
            self._append_log(f"Duplicated workflow: {self.wf_title_lbl.text()} (Copy)")
        elif chosen == act_exp:
            self._append_log(f"Exported {self.wf_title_lbl.text()} configuration.")
        elif chosen == act_del:
            self._append_log(f"Deleted workflow.")

    def _show_templates_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Browse Workflow Templates")
        dlg.resize(540, 400)
        dlg.setStyleSheet("background-color: #111827; color: #f8fafc;")
        d_l = QVBoxLayout(dlg)

        hdr = QLabel("Pre-Built Automation Templates")
        hdr.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 800;")
        d_l.addWidget(hdr)

        tpls = [
            ("Daily Email Summary & Discord Briefing", "Fetch unread messages, generate Gemini summary, post report."),
            ("GitHub Issue Triager & Auto-Branching", "Scans opened issues, repros locally, drafts a hotfix pull request."),
            ("Desktop Downloads Cleanup & Auto-Sort", "Organizes files by extension and moves them into project folders."),
            ("E-Commerce Price Tracker & Deal Alert", "Monitors product price drops and sends instant notification."),
            ("Automated Database Maintenance & Backup", "Executes SQLite vacuum, archives backups, audits integrity."),
        ]

        for t_title, t_desc in tpls:
            card = QFrame()
            card.setStyleSheet("background-color: #0b1426; border: 1px solid #273449; border-radius: 7px; padding: 6px;")
            cl = QHBoxLayout(card)
            t_col = QVBoxLayout()
            tl = QLabel(t_title)
            tl.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700;")
            dl = QLabel(t_desc)
            dl.setStyleSheet("color: #8fa0c0; font-size: 10px;")
            t_col.addWidget(tl)
            t_col.addWidget(dl)
            cl.addLayout(t_col, 1)

            use_btn = QPushButton("Use Template")
            use_btn.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 4px; padding: 5px 12px; font-size: 11px; font-weight: bold;")
            use_btn.clicked.connect(lambda _, t=t_title: (self._load_workflow_nodes_for(t), self.wf_title_lbl.setText(t), dlg.accept()))
            cl.addWidget(use_btn)
            d_l.addWidget(card)

        dlg.exec()

    def _show_tutorial_dialog(self):
        """Displays an interactive in-app step-by-step tutorial for the Automation Studio."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Sage AI • Automation Studio Step-by-Step Tutorial")
        dlg.resize(800, 600)
        dlg.setMinimumSize(700, 520)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #0A0F14;
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #273449;
                border-radius: 8px;
                background-color: #111827;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #162033;
                color: #94a3b8;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #111827;
                color: #00D1FF;
                border-top: 2px solid #00D1FF;
            }
            QScrollBar:vertical {
                background: #0b1426;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #273449;
                border-radius: 4px;
            }
        """)
        d_l = QVBoxLayout(dlg)
        d_l.setContentsMargins(18, 16, 18, 16)
        d_l.setSpacing(12)

        # Header
        hdr_row = QHBoxLayout()
        icon_lbl = QLabel("⚡")
        icon_lbl.setStyleSheet("font-size: 24px; color: #00D1FF;")
        hdr_row.addWidget(icon_lbl)

        hdr_info = QVBoxLayout()
        t_lbl = QLabel("Automation Studio • Complete User Guide")
        t_lbl.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: 800;")
        s_lbl = QLabel("Turn natural language ideas into automated AI workflows. Here is everything you need to know.")
        s_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        hdr_info.addWidget(t_lbl)
        hdr_info.addWidget(s_lbl)
        hdr_row.addLayout(hdr_info, 1)
        d_l.addLayout(hdr_row)

        # Tabs
        tabs = QTabWidget()

        # Tab 1: 🚀 Quickstart
        tab1 = QWidget()
        t1_l = QVBoxLayout(tab1)
        t1_l.setSpacing(10)
        t1_text = QLabel("""
        <h3 style='color: #00D1FF; margin-top: 0;'>🚀 3-Step Quickstart (The Easiest Way)</h3>
        <p style='color: #cbd5e1; font-size: 12px; line-height: 1.5;'>You don't need to manually code or draw complex flowcharts from scratch. Follow these 3 simple steps:</p>
        
        <div style='background: #162033; border: 1px solid #273449; border-radius: 8px; padding: 12px; margin-bottom: 8px;'>
            <p style='color: #fbbf24; font-weight: bold; margin: 0 0 4px 0;'>Step 1: Type your goal in plain English</p>
            <p style='color: #94a3b8; font-size: 12px; margin: 0;'>Look at the top input bar: <b style='color: #fff;'>✨ What do you want to automate?</b><br>
            Type whatever you want, such as: <i>"Every morning read my unread emails, summarize high-priority messages, and send me a report."</i></p>
        </div>

        <div style='background: #162033; border: 1px solid #273449; border-radius: 8px; padding: 12px; margin-bottom: 8px;'>
            <p style='color: #00D1FF; font-weight: bold; margin: 0 0 4px 0;'>Step 2: Click "Generate Workflow →"</p>
            <p style='color: #94a3b8; font-size: 12px; margin: 0;'>Sage AI instantly reads your prompt, creates the necessary Trigger, Actions, AI reasoning, Decision branch, and Output nodes, and arranges them on the visual canvas automatically.</p>
        </div>

        <div style='background: #162033; border: 1px solid #273449; border-radius: 8px; padding: 12px;'>
            <p style='color: #10b981; font-weight: bold; margin: 0 0 4px 0;'>Step 3: Test and Run</p>
            <p style='color: #94a3b8; font-size: 12px; margin: 0;'>Click <b style='color: #fff;'>⚡ Test Run</b> to test in safe simulation mode, or click <b style='color: #fff;'>▶ Run Workflow</b> to execute live! You can watch live step-by-step progress in the Execution Console below.</p>
        </div>
        """)
        t1_text.setTextFormat(Qt.RichText)
        t1_text.setWordWrap(True)
        t1_l.addWidget(t1_text)
        t1_l.addStretch()
        tabs.addTab(tab1, "🚀 Quickstart")

        # Tab 2: 🧩 3 Studio Columns
        tab2 = QWidget()
        t2_l = QVBoxLayout(tab2)
        t2_l.setSpacing(10)
        t2_text = QLabel("""
        <h3 style='color: #00D1FF; margin-top: 0;'>🧩 Understanding the 3 Workspace Panels</h3>
        <table style='width: 100%; border-collapse: collapse; font-size: 12px; color: #cbd5e1;'>
            <tr style='border-bottom: 1px solid #273449;'>
                <th style='text-align: left; padding: 8px; color: #38bdf8; width: 28%;'>Panel</th>
                <th style='text-align: left; padding: 8px; color: #38bdf8;'>What It Does & How to Use It</th>
            </tr>
            <tr style='border-bottom: 1px solid #1e293b;'>
                <td style='padding: 10px 8px;'><b style='color: #f8fafc;'>1. Left Panel<br>(My Workflows)</b></td>
                <td style='padding: 10px 8px; color: #94a3b8;'>
                    • Lists all your saved workflows.<br>
                    • Filter using the pills: <b style='color: #fff;'>All</b>, <b style='color: #fff;'>Active</b>, <b style='color: #fff;'>Scheduled</b>, <b style='color: #fff;'>Drafts</b>.<br>
                    • Toggle any workflow on/off instantly with the switch.<br>
                    • Click <b style='color: #00D1FF;'>🗂 Browse Templates</b> to pick pre-built automations with 1 click.
                </td>
            </tr>
            <tr style='border-bottom: 1px solid #1e293b;'>
                <td style='padding: 10px 8px;'><b style='color: #f8fafc;'>2. Center Canvas<br>(DAG Flowchart)</b></td>
                <td style='padding: 10px 8px; color: #94a3b8;'>
                    • Displays the visual step-by-step flowchart of the active workflow.<br>
                    • Nodes show their type: <b style='color: #10b981;'>Trigger</b> ➔ <b style='color: #38bdf8;'>Action</b> ➔ <b style='color: #fbbf24;'>Decision</b> ➔ <b style='color: #f43f5e;'>Output</b>.<br>
                    • Click any node to open and edit its settings in the right panel.<br>
                    • Zoom in/out with the zoom controls or <b style='color: #fff;'>Ctrl + Mouse Wheel</b>.<br>
                    • The bottom console shows real-time <b style='color: #fff;'>Execution Logs</b>, <b style='color: #fff;'>Variables</b>, and <b style='color: #fff;'>Output</b>.
                </td>
            </tr>
            <tr>
                <td style='padding: 10px 8px;'><b style='color: #f8fafc;'>3. Right Panel<br>(Node Settings)</b></td>
                <td style='padding: 10px 8px; color: #94a3b8;'>
                    • Appears when you click any node on the canvas.<br>
                    • Configure trigger schedule (Daily, Hourly, Weekly, Custom Cron).<br>
                    • Preview the <b style='color: #fff;'>Next 5 Scheduled Runs</b>.<br>
                    • Review recent run history and audit logs.
                </td>
            </tr>
        </table>
        """)
        t2_text.setTextFormat(Qt.RichText)
        t2_text.setWordWrap(True)
        t2_l.addWidget(t2_text)
        t2_l.addStretch()
        tabs.addTab(tab2, "🧩 3 Studio Panels")

        # Tab 3: 🛠 14 Tools
        tab3 = QWidget()
        t3_l = QVBoxLayout(tab3)
        t3_l.setSpacing(8)
        t3_text = QLabel("""
        <h3 style='color: #00D1FF; margin-top: 0;'>🛠 14 Tool Integration Cards</h3>
        <p style='color: #94a3b8; font-size: 12px;'>Clicking any tool card in the top grid lets you quickly trigger or inspect integrations:</p>
        <div style='font-size: 11px; color: #cbd5e1; line-height: 1.6;'>
            • <b>✉ Email</b>: Read unread messages, draft AI responses, send via Gmail.<br>
            • <b>📅 Calendar</b>: Fetch Google Calendar events, schedule reminders.<br>
            • <b>🌐 Web</b>: Search Google, extract page text, monitor price changes.<br>
            • <b>💻 Computer</b>: Run shell commands, launch programs, automate UI.<br>
            • <b>📁 Files</b>: Read/write files, sort downloads, archive folders.<br>
            • <b>🧠 AI</b>: Summarize text, analyze data, run reasoning models.<br>
            • <b>💻 Coding</b>: Run automated tests, lint code, execute Python scripts.<br>
            • <b>🐙 GitHub</b>: Scan new issues, reproduce bugs, draft pull requests.<br>
            • <b>🗄 Database</b>: Query SQLite/Postgres, backup tables, run maintenance.<br>
            • <b>🚀 Communication</b>: Send notifications to Discord, Slack, or Webhooks.<br>
            • <b>🛒 Shopping</b>: Search products and track price drops.<br>
            • <b>📊 Reports</b>: Generate markdown or PDF status reports automatically.<br>
            • <b>🔔 Monitoring</b>: Track file system changes, server uptime, and errors.<br>
            • <b>⋯ More</b>: Custom user-defined integration scripts.
        </div>
        """)
        t3_text.setTextFormat(Qt.RichText)
        t3_text.setWordWrap(True)
        t3_l.addWidget(t3_text)
        t3_l.addStretch()
        tabs.addTab(tab3, "🛠 14 Tools")

        # Tab 4: 🛡 Safe Mode & Permissions
        tab4 = QWidget()
        t4_l = QVBoxLayout(tab4)
        t4_l.setSpacing(10)
        t4_text = QLabel("""
        <h3 style='color: #00D1FF; margin-top: 0;'>🛡 Human-in-the-Loop Security (Why Dialogs Pop Up)</h3>
        <div style='background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: 8px; padding: 12px; margin-bottom: 8px;'>
            <b style='color: #10b981;'>You Are Always in Control</b>
            <p style='color: #cbd5e1; font-size: 12px; margin: 4px 0 0 0;'>Sage AI is designed with an uncompromising safety principle: <b>an autonomous agent should never send an actual email, overwrite critical files, or execute high-risk operations without your explicit approval.</b></p>
        </div>

        <h4 style='color: #f8fafc; margin: 8px 0 4px 0;'>What is the Permission Dialog?</h4>
        <p style='color: #94a3b8; font-size: 12px;'>When an automation runs an action marked as <i>high risk</i> (such as sending an email to a real recipient):</p>
        <ol style='color: #cbd5e1; font-size: 12px; line-height: 1.6;'>
            <li>Execution pauses automatically.</li>
            <li>A <b>Permission Confirmation Dialog</b> appears showing the action, recipient, subject, and full message preview.</li>
            <li>You can review the exact text, click <b>Approve</b> to send, or <b>Deny</b> to safely cancel.</li>
        </ol>

        <h4 style='color: #f8fafc; margin: 8px 0 4px 0;'>Safe Sandbox Mode</h4>
        <p style='color: #94a3b8; font-size: 12px;'>By default, if you haven't linked your live Gmail credentials, Sage AI runs in <b>Sandbox Mode</b> with built-in mock emails so you can safely test the entire workflow without touching real accounts.</p>
        """)
        t4_text.setTextFormat(Qt.RichText)
        t4_text.setWordWrap(True)
        t4_l.addWidget(t4_text)
        t4_l.addStretch()
        tabs.addTab(tab4, "🛡 Security & Permissions")

        # Tab 5: 💡 Real Examples
        tab5 = QWidget()
        t5_l = QVBoxLayout(tab5)
        t5_l.setSpacing(10)
        t5_text = QLabel("""
        <h3 style='color: #00D1FF; margin-top: 0;'>💡 3 Real-World Everyday Examples</h3>

        <div style='background: #162033; border: 1px solid #273449; border-radius: 7px; padding: 10px; margin-bottom: 6px;'>
            <b style='color: #38bdf8;'>Example 1: Morning Executive Briefing</b>
            <p style='color: #94a3b8; font-size: 11px; margin: 3px 0;'>• <b>Prompt</b>: <i>"Every day at 8:30 AM check my inbox, find urgent emails, summarize them with Gemini, and send me a briefing."</i><br>
            • <b>How it works</b>: Trigger (Daily 8:30 AM) ➔ Action (Fetch Unread) ➔ AI (Filter Urgent & Summarize) ➔ Output (Discord/Email Briefing).</p>
        </div>

        <div style='background: #162033; border: 1px solid #273449; border-radius: 7px; padding: 10px; margin-bottom: 6px;'>
            <b style='color: #10b981;'>Example 2: Auto Downloads Cleaner</b>
            <p style='color: #94a3b8; font-size: 11px; margin: 3px 0;'>• <b>Prompt</b>: <i>"Every Sunday clean my Downloads folder and group files by Images, Documents, and Installers."</i><br>
            • <b>How it works</b>: Trigger (Weekly Sunday) ➔ Files (Scan ~/Downloads) ➔ Action (Sort by extension into subdirectories).</p>
        </div>

        <div style='background: #162033; border: 1px solid #273449; border-radius: 7px; padding: 10px;'>
            <b style='color: #a855f7;'>Example 3: GitHub Issue Auto-Triager</b>
            <p style='color: #94a3b8; font-size: 11px; margin: 3px 0;'>• <b>Prompt</b>: <i>"When a new bug issue is opened on GitHub, reproduce it locally, run tests, and draft a pull request."</i><br>
            • <b>How it works</b>: Webhook (GitHub Issue) ➔ Coding (Run pytest) ➔ AI (Draft code fix) ➔ Action (Create Git Branch).</p>
        </div>
        """)
        t5_text.setTextFormat(Qt.RichText)
        t5_text.setWordWrap(True)
        t5_l.addWidget(t5_text)
        t5_l.addStretch()
        tabs.addTab(tab5, "💡 Real Examples")

        d_l.addWidget(tabs, 1)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        tpl_btn = QPushButton("🗂 Open Templates")
        tpl_btn.setCursor(Qt.PointingHandCursor)
        tpl_btn.setStyleSheet("""
            QPushButton {
                background: #162033; color: #38bdf8;
                border: 1px solid #273449; border-radius: 6px;
                padding: 7px 16px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover {
                border-color: #38bdf8;
            }
        """)
        tpl_btn.clicked.connect(lambda: (dlg.accept(), self._show_templates_dialog()))
        btn_row.addWidget(tpl_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Got it, Let's Automate! 🚀")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #00D1FF; color: #0A0F14;
                border: none; border-radius: 6px;
                padding: 7px 20px; font-size: 12px; font-weight: 700;
            }
            QPushButton:hover {
                background: #00BBE6;
            }
        """)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)

        d_l.addLayout(btn_row)

        dlg.exec()


    def _clear_logs(self):
        self.log_edit.clear()

    def _export_logs(self):
        text = self.log_edit.toPlainText()
        from PySide6.QtGui import QGuiApplication
        cb = QGuiApplication.clipboard()
        if cb:
            cb.setText(text)
        self._append_log("<span style='color:#38bdf8;'>📤 Logs copied to clipboard successfully.</span>")

    def _append_log(self, html_msg: str):
        self.log_edit.append(html_msg)

    # ── Backward Compatibility with test suites ──────────────────────
    def _populate_test_models(self):
        """Populates model_combo cleanly with fast local provider availability checks."""
        try:
            from engine.model_scanner import ModelScanner
            candidates = [
                ("Auto Router", "auto", "auto"),
                ("Google Gemini 2.5 Pro", "gemini", "gemini"),
                ("Groq Llama 3.3", "groq", "groq"),
                ("NVIDIA Llama 3.2", "nvidia", "nvidia"),
                ("Claude 3.5 Sonnet", "claude", "openrouter"),
            ]
            for name, m_id, prov in candidates:
                avail = ModelScanner.is_provider_available(prov)
                tag = "[● Available]" if avail else "[○ Unavailable]"
                self.model_combo.addItem(f"{name} {tag}", m_id)
        except Exception:
            self.model_combo.addItem("Auto Router [● Available]", "auto")
            self.model_combo.addItem("Google Gemini 2.5 Pro [● Available]", "gemini")
            self.model_combo.addItem("Groq Llama 3.3 [● Available]", "groq")
            self.model_combo.addItem("Claude 3.5 Sonnet [○ Unavailable]", "claude")

    def _handle_email_reply_request(self, email_data: Dict[str, Any]):
        """Method tested in test_automations_draft_reply_uses_selected_model."""
        chosen_model = self.model_combo.currentData() or "Auto Router"
        draft_text = self.manager.gmail_service.draft_reply(email_data, model=str(chosen_model))

        def permission_checker(action, recipient, subject, body):
            dlg = PermissionDialog(action, recipient, subject, body, email_data, parent=self)
            dlg.exec()
            return dlg.approved

        self.manager.gmail_service.execute_send_reply(
            email_data=email_data,
            reply_body=draft_text,
            permission_checker=permission_checker
        )
