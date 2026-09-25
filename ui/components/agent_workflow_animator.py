"""
Multi-Agent Workflow Animator & Status Engine for SAGE AI.
Implements Sections 4, 5, and 10 of the Master Animation Specification:
- Interactive multi-agent pipeline visualization:
  USER -> PLANNER -> SPECIALIST (Research/Coding/Image/Data/DevOps) -> VERIFIER -> DELIVERY
- Clear agent status lifecycle: IDLE, THINKING, WORKING, WAITING, TOOL_CALL, COMPLETED, ERROR
- Animated connection conduits showing photon beam progress between active agents
- Non-blocking, GPU-friendly rendering with zero particle spam
- Respects reduced-motion and power saving performance tiers
"""
import math
import time
from enum import Enum
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QRadialGradient, QPainterPath
)

from ui.components.animation_system import get_anim_manager, MotionTokens


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"
    WAITING = "WAITING"
    TOOL_CALL = "TOOL_CALL"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


AGENT_STATUS_THEMES = {
    AgentStatus.IDLE: {
        "color": "#64748B",
        "bg": "rgba(22, 32, 51, 0.6)",
        "border": "#273449",
        "icon": "○",
        "label": "Idle"
    },
    AgentStatus.THINKING: {
        "color": "#38BDF8",
        "bg": "rgba(14, 165, 233, 0.12)",
        "border": "rgba(56, 189, 248, 0.6)",
        "icon": "⟳",
        "label": "Thinking..."
    },
    AgentStatus.WORKING: {
        "color": "#00D1FF",
        "bg": "rgba(0, 209, 255, 0.15)",
        "border": "#00D1FF",
        "icon": "⚡",
        "label": "Working"
    },
    AgentStatus.WAITING: {
        "color": "#F59E0B",
        "bg": "rgba(245, 158, 11, 0.12)",
        "border": "rgba(245, 158, 11, 0.5)",
        "icon": "⏳",
        "label": "Waiting"
    },
    AgentStatus.TOOL_CALL: {
        "color": "#C084FC",
        "bg": "rgba(192, 132, 252, 0.16)",
        "border": "#C084FC",
        "icon": "🔧",
        "label": "Tool Exec"
    },
    AgentStatus.COMPLETED: {
        "color": "#10B981",
        "bg": "rgba(16, 185, 129, 0.14)",
        "border": "#10B981",
        "icon": "✓",
        "label": "Completed"
    },
    AgentStatus.ERROR: {
        "color": "#EF4444",
        "bg": "rgba(239, 68, 68, 0.15)",
        "border": "#EF4444",
        "icon": "✕",
        "label": "Error"
    }
}


class AgentNodeBadge(QFrame):
    """
    Individual Agent Card in the visual workflow.
    Displays dynamic status, avatar icon, active tool snippet, and glowing beacon.
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        icon: str,
        role_desc: str,
        parent=None
    ):
        super().__init__(parent)
        self.agent_id = agent_id
        self.name = name
        self.icon = icon
        self.role_desc = role_desc
        self.status: AgentStatus = AgentStatus.IDLE
        self.status_detail: str = ""
        self._pulse_step = 0.0

        self.setFixedSize(148, 88)
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()
        self.apply_status(AgentStatus.IDLE)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Top row: Icon + Name + Indicator dot
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.icon_lbl = QLabel(self.icon)
        self.icon_lbl.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        top_row.addWidget(self.icon_lbl)

        self.name_lbl = QLabel(self.name)
        self.name_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        top_row.addWidget(self.name_lbl)

        top_row.addStretch()

        self.beacon_lbl = QLabel("●")
        self.beacon_lbl.setStyleSheet("color: #64748B; font-size: 9px; background: transparent; border: none;")
        top_row.addWidget(self.beacon_lbl)

        layout.addLayout(top_row)

        # Middle row: Role description
        self.role_lbl = QLabel(self.role_desc)
        self.role_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; background: transparent; border: none;")
        layout.addWidget(self.role_lbl)

        # Bottom row: Status badge text
        self.status_lbl = QLabel("Idle")
        self.status_lbl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 600; background: transparent; border: none;")
        layout.addWidget(self.status_lbl)

    def apply_status(self, status: AgentStatus, detail: str = ""):
        """Transitions agent node to a new lifecycle state with targeted feedback."""
        self.status = status
        self.status_detail = detail
        theme = AGENT_STATUS_THEMES.get(status, AGENT_STATUS_THEMES[AgentStatus.IDLE])

        label_text = detail if detail else theme["label"]
        self.status_lbl.setText(f"{theme['icon']} {label_text}")
        self.status_lbl.setStyleSheet(f"color: {theme['color']}; font-size: 10px; font-weight: 700; background: transparent; border: none;")
        self.beacon_lbl.setStyleSheet(f"color: {theme['color']}; font-size: 9px; background: transparent; border: none;")

        self.setStyleSheet(f"""
            AgentNodeBadge {{
                background-color: {theme['bg']};
                border: 1.5px solid {theme['border']};
                border-radius: 10px;
            }}
            AgentNodeBadge:hover {{
                border-color: {theme['color']};
            }}
        """)

    def update_pulse(self, step: float):
        """Animates beacon intensity for actively working agents without expensive CSS re-parsing."""
        pass


class WorkflowConnector(QWidget):
    """
    Animated photon conduit connecting two workflow nodes.
    Draws a directional pulse beam when data is actively flowing between agents.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(36)
        self.setFixedHeight(88)
        self.is_active = False
        self._pulse_offset = 0.0

    def set_active(self, active: bool):
        self.is_active = active
        self.update()

    def update_pulse(self, step: float):
        if self.is_active:
            self._pulse_offset = (step * 0.15) % 1.0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        mid_y = self.height() / 2.0
        w = self.width()

        # Base track line
        pen_track = QPen(QColor(39, 52, 73, 160), 2)
        painter.setPen(pen_track)
        painter.drawLine(0, int(mid_y), w, int(mid_y))

        # Arrowhead indicator
        arrow_path = QPainterPath()
        arrow_x = w - 6
        arrow_path.moveTo(arrow_x - 5, mid_y - 4)
        arrow_path.lineTo(arrow_x, mid_y)
        arrow_path.lineTo(arrow_x - 5, mid_y + 4)
        painter.strokePath(arrow_path, pen_track)

        # Flowing photon packet when active
        if self.is_active and not get_anim_manager().is_low_performance:
            photon_x = self._pulse_offset * w
            grad = QRadialGradient(photon_x, mid_y, 8)
            grad.setColorAt(0.0, QColor(0, 209, 255, 230))
            grad.setColorAt(0.5, QColor(0, 209, 255, 100))
            grad.setColorAt(1.0, QColor(0, 209, 255, 0))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(photon_x, mid_y), 7, 7)


class MultiAgentWorkflowVisualizer(QFrame):
    """
    Complete Multi-Agent AI Workflow Pipeline.
    Renders the live sequence:
    USER REQUEST ➔ PLANNER ➔ SPECIALIZED AGENT ➔ VERIFICATION ➔ RESPONSE
    Provides automated stage progression, smooth transitions, and tool-call indicators.
    """

    stage_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workflowVisualizer")
        self.setStyleSheet("""
            QFrame#workflowVisualizer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(17, 24, 39, 0.85),
                    stop:1 rgba(10, 15, 20, 0.85));
                border: 1px solid #273449;
                border-radius: 14px;
            }
        """)

        self.nodes: Dict[str, AgentNodeBadge] = {}
        self.connectors: List[WorkflowConnector] = []
        self._step_timer: Optional[QTimer] = None
        self._pulse_step = 0.0

        self._init_ui()
        self._start_animation_loop()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(10)

        # Header with workflow title and live execution status
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        pipeline_icon = QLabel("🧠")
        pipeline_icon.setStyleSheet("font-size: 16px; background: transparent;")
        header_layout.addWidget(pipeline_icon)

        title_lbl = QLabel("Multi-Agent Autonomous Orchestration Pipeline")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 800; letter-spacing: 0.5px; background: transparent;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self.active_stage_lbl = QLabel("● All Agents Ready")
        self.active_stage_lbl.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 700; background: transparent;")
        header_layout.addWidget(self.active_stage_lbl)

        root_layout.addLayout(header_layout)

        # Pipeline Flow Row
        flow_layout = QHBoxLayout()
        flow_layout.setContentsMargins(0, 4, 0, 4)
        flow_layout.setSpacing(0)

        stage_specs = [
            ("user", "User Request", "👤", "Goal Ingestion"),
            ("planner", "Planner Agent", "📋", "DAG Task Planning"),
            ("worker", "Specialist Agent", "⚡", "Execution & Tools"),
            ("verifier", "Verifier & QA", "🧪", "Smart Validation"),
            ("delivery", "Final Delivery", "🚀", "Verified Output")
        ]

        for i, (sid, sname, sicon, sdesc) in enumerate(stage_specs):
            node = AgentNodeBadge(agent_id=sid, name=sname, icon=sicon, role_desc=sdesc, parent=self)
            self.nodes[sid] = node
            flow_layout.addWidget(node)

            if i < len(stage_specs) - 1:
                conn = WorkflowConnector(self)
                self.connectors.append(conn)
                flow_layout.addWidget(conn)

        root_layout.addLayout(flow_layout)

    def _start_animation_loop(self):
        """Prepares timer hook without spinning indefinitely when idle."""
        self.destroyed.connect(self._cleanup)

    def _cleanup(self):
        if self._step_timer and self._step_timer.isActive():
            self._step_timer.stop()

    def _sync_timer(self):
        """Starts animation loop ONLY when active work or flowing conduits exist; stops when idle."""
        mgr = get_anim_manager()
        has_active = any(c.is_active for c in self.connectors) or any(
            n.status in (AgentStatus.WORKING, AgentStatus.THINKING, AgentStatus.TOOL_CALL)
            for n in self.nodes.values()
        )
        if has_active and not mgr.is_low_performance:
            if not self._step_timer:
                self._step_timer = QTimer(self)
                self._step_timer.timeout.connect(self._animate_tick)
            if not self._step_timer.isActive():
                self._step_timer.start(50)
        else:
            if self._step_timer and self._step_timer.isActive():
                self._step_timer.stop()

    def _animate_tick(self):
        self._pulse_step += 0.15
        for conn in self.connectors:
            if conn.is_active:
                conn.update_pulse(self._pulse_step)

    def transition_to_stage(
        self,
        active_stage_id: str,
        status: AgentStatus = AgentStatus.WORKING,
        detail: str = "",
        specialist_name: Optional[str] = None
    ):
        """
        Smoothly advances the workflow pipeline to the active stage.
        Completes prior stages, highlights current agent, and animates connectors.
        """
        stage_order = ["user", "planner", "worker", "verifier", "delivery"]
        if active_stage_id not in stage_order:
            return

        active_idx = stage_order.index(active_stage_id)

        # Update specialized agent label if specified (e.g. Coding Agent, Research Agent)
        if specialist_name and "worker" in self.nodes:
            self.nodes["worker"].name = specialist_name
            self.nodes["worker"].name_lbl.setText(specialist_name)

        # Update nodes
        for i, sid in enumerate(stage_order):
            node = self.nodes[sid]
            if i < active_idx:
                node.apply_status(AgentStatus.COMPLETED)
            elif i == active_idx:
                node.apply_status(status, detail)
            else:
                node.apply_status(AgentStatus.IDLE)

        # Update connectors
        for j, conn in enumerate(self.connectors):
            conn.set_active(j == active_idx - 1 if active_idx > 0 else False)

        # Header status text
        stage_name = self.nodes[active_stage_id].name
        if status == AgentStatus.COMPLETED:
            self.active_stage_lbl.setText("✓ Workflow Complete & Verified")
            self.active_stage_lbl.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 700; background: transparent;")
        elif status == AgentStatus.ERROR:
            self.active_stage_lbl.setText(f"✕ Error in {stage_name}")
            self.active_stage_lbl.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 700; background: transparent;")
        else:
            self.active_stage_lbl.setText(f"⚡ {stage_name}: {detail or status.value}")
            self.active_stage_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 700; background: transparent;")

        self._sync_timer()

    def reset_pipeline(self):
        """Resets all nodes to idle state and halts timers."""
        for node in self.nodes.values():
            node.apply_status(AgentStatus.IDLE)
        for conn in self.connectors:
            conn.set_active(False)
        self.active_stage_lbl.setText("● All Agents Ready")
        self.active_stage_lbl.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 700; background: transparent;")
        self._sync_timer()
