"""
Multi-Agent Hub View for Sage Multi-Agentic AI Architecture.
Visualizes the Core Brain Orchestrator, the 7 Specialized AI Agents,
the Communication Bus, and runs end-to-end multi-agent goals.
"""
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextBrowser, QScrollArea, QFrame, QGridLayout,
    QProgressBar, QSplitter
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QColor

from config import (
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_IMAGE_MEDIA,
    AGENT_DATA_ANALYSIS,
    AGENT_CONTENT,
    AGENT_EXECUTION,
    AGENT_PLANNING,
    AGENT_METADATA,
)
from engine.orchestrator.core_brain import get_orchestrator
from engine.shared_resources.communication_bus import get_comm_bus


class _MultiAgentSignalBridge(QObject):
    stage_updated = Signal(str)
    step_updated = Signal(dict)
    bus_event = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)


class AgentCard(QFrame):
    """Visual card displaying a specialized agent's role, status, and capabilities."""

    def __init__(self, agent_name: str, parent=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.meta = AGENT_METADATA.get(agent_name, {})
        self.setObjectName("agentCard")
        self.setMinimumHeight(130)
        self.setMaximumHeight(152)
        self.setMinimumWidth(165)
        self._init_ui()

    def _init_ui(self):
        color = self.meta.get("color", "#00D1FF")
        bg = self.meta.get("bg_color", "rgba(0, 209, 255, 0.08)")
        self.setStyleSheet(f"""
            QFrame#agentCard {{
                background-color: {bg};
                border: 1px solid {color}33;
                border-radius: 12px;
            }}
            QFrame#agentCard:hover {{
                border: 1.5px solid {color};
                background-color: {color}1a;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Row 1: Icon on left + Status Dot on right
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel(self.meta.get("icon", "🤖"))
        icon_lbl.setStyleSheet("font-size: 16px; background: transparent;")
        top_row.addWidget(icon_lbl)
        top_row.addStretch()

        self.status_dot = QLabel("● Ready")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 700; background: transparent;")
        top_row.addWidget(self.status_dot)
        layout.addLayout(top_row)

        # Row 2: Agent Name - Full Width so it NEVER truncates!
        name_lbl = QLabel(self.agent_name)
        name_lbl.setStyleSheet(f"color: {color}; font-size: 12.5px; font-weight: 700; background: transparent;")
        layout.addWidget(name_lbl)

        # Tagline
        tagline = QLabel(self.meta.get("tagline", ""))
        tagline.setStyleSheet("color: #94A3B8; font-size: 10.5px; font-style: italic; background: transparent;")
        layout.addWidget(tagline)

        # Capabilities bullet list (concise 2 points to avoid vertical squeeze)
        caps = self.meta.get("capabilities", [])[:2]
        caps_txt = " • ".join(caps)
        cap_lbl = QLabel(caps_txt)
        cap_lbl.setWordWrap(True)
        cap_lbl.setStyleSheet("color: #626c85; font-size: 10px; background: transparent;")
        layout.addWidget(cap_lbl)
        layout.addStretch()

    def set_working(self, working: bool):
        color = self.meta.get("color", "#00D1FF")
        if working:
            self.status_dot.setText("● Active")
            self.status_dot.setStyleSheet("color: #ffb84d; font-size: 10px; font-weight: 700;")
        else:
            self.status_dot.setText("● Ready")
            self.status_dot.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600;")


class MultiAgentView(QWidget):
    """Primary Multi-Agent Orchestrator View with responsive scrolling container."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.orchestrator = get_orchestrator()
        self.comm_bus = get_comm_bus()
        self.signals = _MultiAgentSignalBridge()
        self.agent_cards: Dict[str, AgentCard] = {}
        self._preset_buttons: List[QPushButton] = []

        self._init_ui()
        self._wire_signals()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Responsive Scroll Area prevents widget overlapping on smaller screens
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("multiAgentScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea#multiAgentScrollArea {
                background: transparent;
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
        content_widget.setStyleSheet("QWidget#multiAgentContent { background: transparent; }")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 18, 24, 20)
        main_layout.setSpacing(14)

        # 1. Top Architectural Header
        # Specifically scoped with QFrame#archHeaderFrame so child QLabels don't inherit border/padding
        self.header_frame = QFrame()
        self.header_frame.setObjectName("archHeaderFrame")
        self.header_frame.setStyleSheet("""
            QFrame#archHeaderFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 209, 255, 0.12),
                    stop:0.5 rgba(56, 189, 248, 0.10),
                    stop:1 rgba(168, 85, 247, 0.12));
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 14px;
            }
        """)
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(5)

        title_lbl = QLabel("Sage – Multi-Agentic AI Architecture")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 18px; font-weight: 800; letter-spacing: 0.5px; background: transparent;")
        header_layout.addWidget(title_lbl)

        self.sub_lbl = QLabel("Plan • Create • Code • Automate • Anything  |  One Request. Many Agents. Real Results.")
        self.sub_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600; background: transparent;")
        header_layout.addWidget(self.sub_lbl)

        pipeline_flow = QLabel("Task Decomposer ➔ Agent Router ➔ Workflow Manager ➔ 7 Specialized Agents ➔ Self-Reflection ➔ Automated Completion")
        pipeline_flow.setStyleSheet("color: #94A3B8; font-size: 11px; margin-top: 2px; background: transparent;")
        header_layout.addWidget(pipeline_flow)

        main_layout.addWidget(self.header_frame)

        # 2. Specialized Agents Grid (Cards for all 7 agents)
        agents_label = QLabel("SPECIALIZED AI AGENTS (Work Together to Complete Tasks)")
        agents_label.setStyleSheet("color: #626c85; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        main_layout.addWidget(agents_label)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        agents_list = [
            AGENT_RESEARCH, AGENT_CODING, AGENT_IMAGE_MEDIA, AGENT_DATA_ANALYSIS,
            AGENT_CONTENT, AGENT_EXECUTION, AGENT_PLANNING
        ]

        row = 0
        col = 0
        for ag_name in agents_list:
            card = AgentCard(ag_name, self)
            self.agent_cards[ag_name] = card
            grid_layout.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        main_layout.addLayout(grid_layout)

        # 3. Goal Input Section
        self.input_frame = QFrame()
        self.input_frame.setObjectName("goalInputFrame")
        self.input_frame.setStyleSheet("""
            QFrame#goalInputFrame {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 12px;
            }
        """)
        input_layout = QVBoxLayout(self.input_frame)
        input_layout.setContentsMargins(14, 12, 14, 12)
        input_layout.setSpacing(8)

        input_top_row = QHBoxLayout()
        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText("Enter complex goal, e.g.: 'Build a website, create images, write code, analyze data and deploy it'")
        self.goal_input.setStyleSheet("""
            QLineEdit {
                background-color: #0A0F14;
                color: #F8FAFC;
                border: 1px solid #162033;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00D1FF;
            }
        """)
        self.goal_input.returnPressed.connect(self._run_goal)
        input_top_row.addWidget(self.goal_input, 1)

        self.run_btn = QPushButton("🚀 Run Multi-Agent Goal")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D1FF, stop:1 #00D1FF);
                color: #0A0F14;
                font-weight: 700;
                font-size: 13px;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #00BBE6;
            }
        """)
        self.run_btn.clicked.connect(self._run_goal)
        input_top_row.addWidget(self.run_btn)
        input_layout.addLayout(input_top_row)

        # Quick templates
        tmpl_row = QHBoxLayout()
        tmpl_lbl = QLabel("Quick Presets:")
        tmpl_lbl.setStyleSheet("color: #626c85; font-size: 11px;")
        tmpl_row.addWidget(tmpl_lbl)

        presets = [
            ("🌐 Full Web App & Visuals", "Build a landing page website with modern CSS styles, generate a header diagram, write test code, and create summary docs."),
            ("📊 Data Intelligence Brief", "Research current web trends in AI, analyze performance metrics dataset, and write an analytical report with charts."),
            ("⚙️ Project Architecture Plan", "Formulate a multi-tier cloud microservice architecture with milestones, API specifications, and Docker deployment scripts.")
        ]
        self._preset_buttons.clear()
        for label, text in presets:
            btn = QPushButton(label)
            btn.setObjectName("presetBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton#presetBtn {
                    background: rgba(0, 209, 255, 0.08);
                    color: #00D1FF;
                    border: 1px solid rgba(0, 209, 255, 0.2);
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton#presetBtn:hover {
                    background: rgba(0, 209, 255, 0.18);
                }
            """)
            btn.clicked.connect(lambda chk=False, t=text: self.goal_input.setText(t))
            tmpl_row.addWidget(btn)
            self._preset_buttons.append(btn)

        tmpl_row.addStretch()
        input_layout.addLayout(tmpl_row)

        main_layout.addWidget(self.input_frame)

        # 4. Progress and Live Pipeline Status
        self.status_lbl = QLabel("Ready. Enter a goal above to orchestrate all 7 agents.")
        self.status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        main_layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #162033;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D1FF, stop:0.5 #38bdf8, stop:1 #a855f7);
                border-radius: 3px;
            }
        """)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # 5. Splitter: Left = Inter-Agent Communication Bus Feed, Right = Deliverables
        splitter = QSplitter(Qt.Horizontal)
        splitter.setMinimumHeight(240)

        # Left: Communication Bus Log
        bus_container = QFrame()
        bus_container.setObjectName("busContainer")
        bus_container.setStyleSheet("QFrame#busContainer { background-color: #0A0F14; border: 1px solid #162033; border-radius: 10px; }")
        bus_layout = QVBoxLayout(bus_container)
        bus_layout.setContentsMargins(10, 8, 10, 8)
        self.bus_header = QLabel("📡 Inter-Agent Communication Bus")
        self.bus_header.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 700;")
        bus_layout.addWidget(self.bus_header)

        self.bus_browser = QTextBrowser()
        self.bus_browser.setStyleSheet("background: transparent; border: none; color: #94A3B8; font-size: 11px;")
        bus_layout.addWidget(self.bus_browser)
        splitter.addWidget(bus_container)

        # Right: Final Deliverables Output
        out_container = QFrame()
        out_container.setObjectName("outContainer")
        out_container.setStyleSheet("QFrame#outContainer { background-color: #0A0F14; border: 1px solid #162033; border-radius: 10px; }")
        out_layout = QVBoxLayout(out_container)
        out_layout.setContentsMargins(10, 8, 10, 8)
        out_header = QLabel("📦 Deliverables & Automated Completion")
        out_header.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700;")
        out_layout.addWidget(out_header)

        self.out_browser = QTextBrowser()
        self.out_browser.setStyleSheet("background: transparent; border: none; color: #F8FAFC; font-size: 12px;")
        self.out_browser.setOpenExternalLinks(True)
        out_layout.addWidget(self.out_browser)
        splitter.addWidget(out_container)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main_layout.addWidget(splitter, 1)

        self.scroll_area.setWidget(content_widget)
        root_layout.addWidget(self.scroll_area)

    def apply_theme(self, pal: Dict[str, Any]):
        """Dynamically updates headers, buttons, and accents according to active theme."""
        primary = pal.get("primary", "#00D1FF")
        rgba_12 = pal.get("primary_rgba_12", "rgba(0, 209, 255, 0.12)")
        rgba_30 = pal.get("primary_rgba_30", "rgba(0, 209, 255, 0.30)")
        rgba_08 = pal.get("primary_rgba_06", "rgba(0, 209, 255, 0.08)")
        primary_dark = pal.get("primary_dark", "#00D1FF")
        primary_hover = pal.get("primary_hover", primary)

        if hasattr(self, "header_frame") and self.header_frame:
            self.header_frame.setStyleSheet(f"""
                QFrame#archHeaderFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {rgba_12},
                        stop:0.5 rgba(56, 189, 248, 0.10),
                        stop:1 rgba(168, 85, 247, 0.12));
                    border: 1px solid {rgba_30};
                    border-radius: 14px;
                }}
            """)
        if hasattr(self, "sub_lbl") and self.sub_lbl:
            self.sub_lbl.setStyleSheet(f"color: {primary}; font-size: 12px; font-weight: 600; background: transparent;")
        if hasattr(self, "run_btn") and self.run_btn:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {primary}, stop:1 {primary_dark});
                    color: #0A0F14;
                    font-weight: 700;
                    font-size: 13px;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background: {primary_hover};
                }}
            """)
        if hasattr(self, "bus_header") and self.bus_header:
            self.bus_header.setStyleSheet(f"color: {primary}; font-size: 11px; font-weight: 700;")
        for btn in self._preset_buttons:
            btn.setStyleSheet(f"""
                QPushButton#presetBtn {{
                    background: {rgba_08};
                    color: {primary};
                    border: 1px solid {rgba_30};
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                }}
                QPushButton#presetBtn:hover {{
                    background: {rgba_12};
                }}
            """)


    def _wire_signals(self):
        self.signals.stage_updated.connect(self._on_stage_updated)
        self.signals.step_updated.connect(self._on_step_updated)
        self.signals.bus_event.connect(self._on_bus_event)
        self.signals.finished.connect(self._on_goal_finished)
        self.signals.failed.connect(self._on_goal_failed)

        # Subscribe to Communication Bus events
        self.comm_bus.subscribe("*", lambda evt: self.signals.bus_event.emit(evt))

    def _run_goal(self):
        goal = self.goal_input.text().strip()
        if not goal:
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ Orchestrating...")
        self.progress_bar.setValue(15)
        self.status_lbl.setText("🧠 Task Decomposer breaking goal into steps...")
        self.bus_browser.clear()
        self.out_browser.clear()

        # Execute in background thread
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
        self.bus_browser.append(f"<b>[{from_ag} ➔ {to_ag}]</b> <span style='color:#00D1FF;'>({mtype})</span>: {cnt}")

    def _on_goal_finished(self, res: dict):
        self.progress_bar.setValue(100)
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🚀 Run Multi-Agent Goal")
        self.status_lbl.setText(f"✅ Automated Completion in {res.get('elapsed_seconds', 0)}s!")

        # Reset cards to ready
        for card in self.agent_cards.values():
            card.set_working(False)

        # Render markdown to HTML
        from ui.components.message_bubble import format_markdown_to_html
        summary = res.get("final_summary", "")
        self.out_browser.setHtml(format_markdown_to_html(summary))

    def _on_goal_failed(self, error: str):
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🚀 Run Multi-Agent Goal")
        self.status_lbl.setText(f"⚠️ Orchestrator Error: {error}")
        for card in self.agent_cards.values():
            card.set_working(False)
        self.out_browser.setPlainText(f"Error during execution:\n{error}")
