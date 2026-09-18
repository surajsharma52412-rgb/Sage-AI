"""
Interactive Collaborative Whiteboard for Sage AI (Lunar Engine).
Allows real-time pair sketching, system architecture diagramming, and visual brainstorming.
"""
import time
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QButtonGroup, QFileDialog, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QRectF, QPointF, QSize
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QPainterPath, QPixmap,
    QFont, QCursor, QLinearGradient
)


class WhiteboardCanvas(QWidget):
    """Drawing surface with antialiased rendering, vector stroke storage, and grid snapping."""

    stroke_finished = Signal(dict)
    peer_activity = Signal(str)

    CANVAS_BG = QColor("#0A0F14")
    GRID_DOT_COLOR = QColor(255, 255, 255, 18)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Drawing settings
        self.active_tool: str = "pen"       # "pen", "line", "rect", "circle", "eraser", "text"
        self.active_color: str = "#0FE6B5"  # default emerald
        self.active_width: int = 4
        self.my_name: str = "Me"

        # Stored vector strokes
        # Each stroke: {"tool": str, "points": [(x, y), ...], "color": str, "width": int, "peer_name": str}
        self.strokes: List[Dict[str, Any]] = []
        self.current_stroke: Optional[Dict[str, Any]] = None
        self.show_sample_mindmap: bool = False

        # Remote peers drawing indicators: peer_name -> (x, y)
        self.peer_cursors: Dict[str, Tuple[int, int]] = {}

        # Cached hardware-accelerated backing pixmaps for lag-free 60+ FPS drawing
        self._grid_pixmap: Optional[QPixmap] = None
        self._strokes_pixmap: Optional[QPixmap] = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_grid_pixmap()
        self._rebuild_strokes_pixmap()

    def _rebuild_grid_pixmap(self):
        w = max(10, self.width())
        h = max(10, self.height())
        self._grid_pixmap = QPixmap(w, h)
        self._grid_pixmap.fill(self.CANVAS_BG)

        p = QPainter(self._grid_pixmap)
        grid_spacing = 28
        p.setPen(QPen(self.GRID_DOT_COLOR, 1))
        for x in range(grid_spacing, w, grid_spacing):
            for y in range(grid_spacing, h, grid_spacing):
                p.drawPoint(x, y)
        p.end()

    def _rebuild_strokes_pixmap(self):
        w = max(10, self.width())
        h = max(10, self.height())
        self._strokes_pixmap = QPixmap(w, h)
        self._strokes_pixmap.fill(Qt.transparent)

        p = QPainter(self._strokes_pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        for stroke in self.strokes:
            self._draw_stroke(p, stroke)
        p.end()

    def set_tool(self, tool: str):
        self.active_tool = tool
        if tool == "eraser":
            self.setCursor(QCursor(Qt.PointingHandCursor))
        elif tool == "text":
            self.setCursor(QCursor(Qt.IBeamCursor))
        else:
            self.setCursor(QCursor(Qt.CrossCursor))

    def set_color(self, color_hex: str):
        self.active_color = color_hex

    def set_stroke_width(self, width: int):
        self.active_width = width

    def add_remote_stroke(self, stroke: dict):
        self.strokes.append(stroke)
        if self._strokes_pixmap:
            p = QPainter(self._strokes_pixmap)
            p.setRenderHint(QPainter.Antialiasing)
            self._draw_stroke(p, stroke)
            p.end()
        peer = stroke.get("peer_name", "Peer")
        self.peer_activity.emit(f"🎨 {peer} drew on canvas")
        self.update()

    def clear_canvas(self):
        self.strokes.clear()
        self.current_stroke = None
        self.show_sample_mindmap = False
        self._rebuild_strokes_pixmap()
        self.update()

    def undo_stroke(self):
        if self.strokes:
            self.strokes.pop()
            self._rebuild_strokes_pixmap()
            self.update()

    def set_history(self, strokes: List[dict]):
        self.strokes = [dict(s) for s in strokes]
        self._rebuild_strokes_pixmap()
        self.update()

    # --- Mouse Events ---

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            pt = (int(pos.x()), int(pos.y()))
            if self.active_tool == "text":
                from PySide6.QtWidgets import QInputDialog
                text, ok = QInputDialog.getText(self, "Add Text Note", "Enter text for whiteboard:")
                if ok and text.strip():
                    stroke = {
                        "tool": "text",
                        "points": [pt],
                        "text": text.strip(),
                        "color": self.active_color,
                        "width": self.active_width,
                        "peer_name": self.my_name,
                    }
                    self.strokes.append(stroke)
                    if self._strokes_pixmap:
                        p = QPainter(self._strokes_pixmap)
                        p.setRenderHint(QPainter.Antialiasing)
                        self._draw_stroke(p, stroke)
                        p.end()
                    self.stroke_finished.emit(stroke)
                    self.update()
                return

            self.current_stroke = {
                "tool": self.active_tool,
                "points": [pt],
                "color": self.active_color if self.active_tool != "eraser" else "#0A0F14",
                "width": self.active_width if self.active_tool != "eraser" else 24,
                "peer_name": self.my_name,
            }
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.current_stroke:
            pos = event.position()
            pt = (int(pos.x()), int(pos.y()))
            points = self.current_stroke["points"]
            tool = self.current_stroke["tool"]

            if tool in ("pen", "eraser"):
                # Smooth decimation: ignore subpixel micro-jitter (< ~2.5px)
                if points:
                    last_pt = points[-1]
                    dx = pt[0] - last_pt[0]
                    dy = pt[1] - last_pt[1]
                    if dx * dx + dy * dy < 7:
                        return
                points.append(pt)
                
                # Fast dirty-rect redraw for minimal GPU/CPU load
                if len(points) >= 2:
                    p0 = points[-2]
                    p1 = points[-1]
                    margin = int(self.current_stroke.get("width", 8)) * 2 + 10
                    rx = min(p0[0], p1[0]) - margin
                    ry = min(p0[1], p1[1]) - margin
                    rw = abs(p1[0] - p0[0]) + margin * 2
                    rh = abs(p1[1] - p0[1]) + margin * 2
                    self.update(QRect(rx, ry, rw, rh))
                    return
            else:
                # Shapes only need start and current end point
                if len(points) == 1:
                    points.append(pt)
                else:
                    points[-1] = pt

            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_stroke:
            pos = event.position()
            pt = (int(pos.x()), int(pos.y()))
            points = self.current_stroke["points"]
            tool = self.current_stroke["tool"]

            if tool in ("pen", "eraser"):
                if not points or points[-1] != pt:
                    points.append(pt)
            else:
                if len(points) == 1:
                    points.append(pt)
                else:
                    points[-1] = pt

            # Commit stroke to vector list and paint onto backing pixmap
            if points:
                stroke_copy = dict(self.current_stroke)
                self.strokes.append(stroke_copy)
                if self._strokes_pixmap:
                    p = QPainter(self._strokes_pixmap)
                    p.setRenderHint(QPainter.Antialiasing)
                    self._draw_stroke(p, stroke_copy)
                    p.end()
                self.stroke_finished.emit(stroke_copy)

            self.current_stroke = None
            self.update()

    # --- Paint Event ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Background Grid (Instant single blit from cached pixmap)
        if self._grid_pixmap and not self._grid_pixmap.isNull():
            painter.drawPixmap(0, 0, self._grid_pixmap)
        else:
            painter.fillRect(self.rect(), self.CANVAS_BG)

        # 2. Mindmap or Empty State
        w = self.width()
        h = self.height()
        if self.show_sample_mindmap:
            self._draw_mindmap(painter)
        elif not self.strokes and not self.current_stroke:
            painter.setPen(QColor(148, 163, 184, 80))
            painter.setFont(QFont("Segoe UI", 11, QFont.Medium))
            hint_rect = QRectF(20, h / 2.0 - 30, w - 40, 60)
            painter.drawText(hint_rect, Qt.AlignCenter, "🎨 Whiteboard Canvas (Fresh & Ready)\nSelect a tool on the left to start sketching architecture")

        # 3. Committed Strokes (Instant single blit from double-buffered pixmap)
        if self._strokes_pixmap and not self._strokes_pixmap.isNull():
            painter.drawPixmap(0, 0, self._strokes_pixmap)
        else:
            for stroke in self.strokes:
                self._draw_stroke(painter, stroke)

        # 4. Active In-Progress Stroke (Rendered dynamically on top)
        if self.current_stroke:
            self._draw_stroke(painter, self.current_stroke)

    def _draw_mindmap(self, painter: QPainter):
        """Draws the Sage Platform interactive architecture diagram & handwritten notes."""
        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # Draw connecting curved bezier lines from center to nodes
        # Center -> Frontend (top-left), Backend (bottom-left), Database (top-right), Deployment (bottom-right)
        p_center = QPointF(cx, cy)
        p_fe = QPointF(max(95.0, cx - 180.0), max(55.0, cy - 75.0))
        p_be = QPointF(max(95.0, cx - 180.0), min(h - 95.0, cy + 75.0))
        p_db = QPointF(min(w - 120.0, cx + 180.0), max(55.0, cy - 75.0))
        p_dep = QPointF(min(w - 150.0, cx + 155.0), min(h - 95.0, cy + 65.0))

        # Bezier connectors
        def _draw_branch(p_start, p_end, col_hex):
            path = QPainterPath()
            path.moveTo(p_start)
            c1 = QPointF((p_start.x() + p_end.x()) / 2.0, p_start.y())
            c2 = QPointF((p_start.x() + p_end.x()) / 2.0, p_end.y())
            path.cubicTo(c1, c2, p_end)
            pen = QPen(QColor(col_hex), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        _draw_branch(p_center, p_fe, "#00D1FF")
        _draw_branch(p_center, p_be, "#8b5cf6")
        _draw_branch(p_center, p_db, "#ec4899")
        _draw_branch(p_center, p_dep, "#eab308")

        # 1. Center Node: Sage Platform (Glowing violet pill)
        c_w, c_h = 130.0, 38.0
        c_rect = QRectF(cx - c_w/2.0, cy - c_h/2.0, c_w, c_h)
        c_grad = QLinearGradient(c_rect.topLeft(), c_rect.bottomRight())
        c_grad.setColorAt(0.0, QColor("#6366f1"))
        c_grad.setColorAt(1.0, QColor("#4338ca"))
        painter.setPen(QPen(QColor("#a5b4fc"), 1.5))
        painter.setBrush(QBrush(c_grad))
        painter.drawRoundedRect(c_rect, 19, 19)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(c_rect, Qt.AlignCenter, "Sage Platform")

        # Helper to draw node with bullet points and optional peer cursor
        def _draw_node(pt, title, bullets, border_col, cursor_name=None, cursor_col="#00D1FF", cursor_pos="top"):
            nw, nh = 130.0, 28.0
            n_rect = QRectF(pt.x() - nw/2.0, pt.y() - nh/2.0, nw, nh)
            painter.setPen(QPen(QColor(border_col), 1.5))
            painter.setBrush(QBrush(QColor("#080f1e")))
            painter.drawRoundedRect(n_rect, 14, 14)

            painter.setPen(QColor("#f4f5fb"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(n_rect, Qt.AlignCenter, title)

            # Bullets below node
            painter.setFont(QFont("Segoe UI", 8.5))
            painter.setPen(QColor("#94a3b8"))
            by = pt.y() + nh/2.0 + 8.0
            for b in bullets:
                painter.drawText(QRectF(pt.x() - nw/2.0, by, nw + 20.0, 15.0), Qt.AlignLeft | Qt.AlignVCenter, f"• {b}")
                by += 14.0

            # Peer cursor badge
            if cursor_name:
                cur_x = pt.x() + nw/2.0 - 10.0
                cur_y = (pt.y() - nh/2.0 - 14.0) if cursor_pos == "top" else (pt.y() + nh/2.0 + 38.0)
                cur_rect = QRectF(cur_x, cur_y, 44.0, 16.0)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(cursor_col)))
                painter.drawRoundedRect(cur_rect, 4, 4)
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                painter.drawText(cur_rect, Qt.AlignCenter, cursor_name)

        _draw_node(p_fe, "Frontend", ["React + Tailwind", "Components", "Pages", "State Management"], "#00D1FF", "Priya", "#00D1FF", "top")
        _draw_node(p_be, "Backend", ["FastAPI", "Authentication", "Database", "APIs"], "#8b5cf6", "Suraj", "#8b5cf6", "bottom")
        _draw_node(p_db, "Database", ["SQLite / PostgreSQL", "Models", "Migrations"], "#ec4899", "Ankit", "#00D1FF", "top")
        _draw_node(p_dep, "Deployment", ["Docker", "CI/CD", "Cloud Hosting"], "#eab308")

        # Handwritten style note on bottom-right corner: "Build Something Amazing! — Sage AI"
        note_rect = QRectF(w - 145.0, h - 55.0, 140.0, 48.0)
        painter.save()
        painter.translate(note_rect.center())
        painter.rotate(-12.0)
        painter.setPen(QColor("#c084fc"))
        note_font = QFont("Segoe Print", 8, QFont.Bold)
        note_font.setStyleHint(QFont.Cursive)
        painter.setFont(note_font)
        painter.drawText(QRectF(-68.0, -22.0, 136.0, 44.0), Qt.AlignCenter, "Build Something Amazing!\n— Sage AI ✨")
        painter.restore()

        # 6. Zoom controls overlay at bottom-left
        zm_rect = QRectF(14.0, h - 32.0, 96.0, 22.0)
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.setBrush(QBrush(QColor(8, 14, 26, 210)))
        painter.drawRoundedRect(zm_rect, 6, 6)
        painter.setPen(QColor("#cbd5e1"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(zm_rect, Qt.AlignCenter, "−   100%   ＋")


    def _draw_stroke(self, painter: QPainter, stroke: dict):
        points = stroke.get("points", [])
        if not points:
            return

        tool = stroke.get("tool", "pen")
        color = QColor(stroke.get("color", "#00D1FF"))
        width = stroke.get("width", 4)

        pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if tool in ("pen", "eraser"):
            if len(points) == 1:
                painter.drawPoint(points[0][0], points[0][1])
            else:
                path = QPainterPath()
                path.moveTo(points[0][0], points[0][1])
                for i in range(1, len(points)):
                    p0 = points[i - 1]
                    p1 = points[i]
                    # Midpoint quadratic smoothing
                    mid_x = (p0[0] + p1[0]) / 2.0
                    mid_y = (p0[1] + p1[1]) / 2.0
                    path.quadTo(p0[0], p0[1], mid_x, mid_y)
                path.lineTo(points[-1][0], points[-1][1])
                painter.drawPath(path)

        elif tool == "line":
            if len(points) >= 2:
                painter.drawLine(points[0][0], points[0][1], points[-1][0], points[-1][1])

        elif tool == "rect":
            if len(points) >= 2:
                p0 = points[0]
                p1 = points[-1]
                x = min(p0[0], p1[0])
                y = min(p0[1], p1[1])
                w = abs(p1[0] - p0[0])
                h = abs(p1[1] - p0[1])
                painter.drawRoundedRect(x, y, w, h, 6, 6)

        elif tool == "circle":
            if len(points) >= 2:
                p0 = points[0]
                p1 = points[-1]
                x = min(p0[0], p1[0])
                y = min(p0[1], p1[1])
                w = abs(p1[0] - p0[0])
                h = abs(p1[1] - p0[1])
                painter.drawEllipse(x, y, w, h)

        elif tool == "text":
            txt = stroke.get("text", "")
            if txt and points:
                painter.setFont(QFont("Segoe UI", 12, QFont.Medium))
                painter.setPen(color)
                painter.drawText(points[0][0], points[0][1], txt)


class CollabWhiteboardWidget(QWidget):
    """
    Complete Collaborative Whiteboard Suite with Dark Cyberpunk Emerald Toolbars,
    Vector Palettes, Undo/Clear, and CollabManager network integration.
    """

    broadcast_stroke_requested = Signal(dict)
    broadcast_clear_requested = Signal()
    broadcast_undo_requested = Signal()
    maximize_toggled = Signal(bool)

    PALETTE = [
        ("#0FE6B5", "Emerald"),
        ("#00D1FF", "Cyan"),
        ("#a855f7", "Violet"),
        ("#f43f5e", "Rose"),
        ("#eab308", "Amber"),
        ("#ffffff", "White"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_maximized: bool = False
        self._init_ui()

    def minimumSizeHint(self) -> QSize:
        return QSize(50, 50)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(6)

        # 1. Top Header Bar matching reference photo: "Collaborative Whiteboard" [Palette | Widths | ⚙ ⛶ Share]
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background-color: #070b14;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 2px 6px;
            }
        """)
        hdr_l = QHBoxLayout(hdr_frame)
        hdr_l.setContentsMargins(4, 2, 4, 2)
        hdr_l.setSpacing(5)

        wb_icon = QLabel("📋")
        wb_icon.setStyleSheet("color: #0FE6B5; font-size: 13px;")
        hdr_l.addWidget(wb_icon)

        hdr_title = QLabel("Whiteboard")
        hdr_title.setStyleSheet("color: #f4f5fb; font-size: 11.5px; font-weight: 700;")
        hdr_l.addWidget(hdr_title)

        # Peer activity indicator
        self.activity_tag = QLabel("")
        self.activity_tag.setStyleSheet("color: #38bdf8; font-size: 9.5px; font-style: italic;")
        hdr_l.addWidget(self.activity_tag)

        hdr_l.addStretch()

        # Color palette swatches
        self.color_buttons = []
        for hex_col, name in self.PALETTE:
            c_btn = QPushButton()
            c_btn.setFixedSize(16, 16)
            c_btn.setCursor(Qt.PointingHandCursor)
            c_btn.setToolTip(f"Color: {name}")
            c_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_col};
                    border: 1px solid rgba(255, 255, 255, 0.25);
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    border: 2px solid #ffffff;
                }}
            """)
            c_btn.clicked.connect(lambda _, c=hex_col: self._select_color(c))
            hdr_l.addWidget(c_btn)
            self.color_buttons.append(c_btn)

        # Stroke Width selector buttons
        for w_val, w_label in [(2, "1x"), (4, "2x"), (8, "4x")]:
            w_btn = QPushButton(w_label)
            w_btn.setCursor(Qt.PointingHandCursor)
            w_btn.setToolTip(f"Stroke Width: {w_label}")
            w_btn.setStyleSheet("""
                QPushButton {
                    background-color: #111827;
                    color: #94a3b8;
                    border: 1px solid #273449;
                    border-radius: 4px;
                    padding: 2px 5px;
                    font-size: 9.5px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    color: #0FE6B5;
                    border-color: #0FE6B5;
                }
            """)
            w_btn.clicked.connect(lambda _, wv=w_val: self._select_width(wv))
            hdr_l.addWidget(w_btn)

        # Settings Icon
        wb_settings_btn = QPushButton("⚙")
        wb_settings_btn.setFixedSize(24, 24)
        wb_settings_btn.setCursor(Qt.PointingHandCursor)
        wb_settings_btn.setToolTip("Whiteboard Settings & Canvas Grid")
        wb_settings_btn.setStyleSheet("background: transparent; color: #8fa0b5; border: none; font-size: 13px;")
        hdr_l.addWidget(wb_settings_btn)

        # Maximize / Expand Icon
        self.max_btn = QPushButton("⛶")
        self.max_btn.setFixedSize(24, 24)
        self.max_btn.setCursor(Qt.PointingHandCursor)
        self.max_btn.setToolTip("Maximize / Restore Whiteboard")
        self.max_btn.setStyleSheet("background: transparent; color: #8fa0b5; border: none; font-size: 13px;")
        self.max_btn.clicked.connect(self._toggle_maximize)
        self.maximize_btn = self.max_btn
        hdr_l.addWidget(self.max_btn)

        # Purple Share Button
        self.share_wb_btn = QPushButton("🔗 Share")
        self.share_wb_btn.setCursor(Qt.PointingHandCursor)
        self.share_wb_btn.setToolTip("Share Whiteboard Canvas to Team Session")
        self.share_wb_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: #ffffff;
                border: 1px solid #7c3aed;
                border-radius: 5px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #4f46e5;
            }
        """)
        hdr_l.addWidget(self.share_wb_btn)
        layout.addWidget(hdr_frame)

        # 2. Main Body with Left Vertical Drawing Toolbar + Canvas
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        # Left Vertical Toolbar (Pen, Line, Rect, Circle, Text, Eraser, Pointer)
        v_toolbar = QFrame()
        v_toolbar.setStyleSheet("""
            QFrame {
                background-color: #070c18;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 3px;
            }
        """)
        vt_layout = QVBoxLayout(v_toolbar)
        vt_layout.setContentsMargins(3, 4, 3, 4)
        vt_layout.setSpacing(4)

        self.tool_buttons: Dict[str, QPushButton] = {}
        tools = [
            ("pen", "✏️", "Pen / Freehand Sketch"),
            ("line", "↘", "Connector Line / Arrow"),
            ("rect", "▭", "Box / Rectangle"),
            ("circle", "◯", "Circle / Node"),
            ("text", "T", "Text Note Tool"),
            ("eraser", "⌫", "Eraser"),
            ("select", "↖", "Select / Pointer Tool"),
        ]
        self.tool_group = QButtonGroup(self)
        for tool_id, icon, tip in tools:
            btn = QPushButton(icon)
            btn.setCheckable(True)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #0FE6B5;
                    background-color: rgba(15, 230, 181, 0.1);
                }
                QPushButton:checked {
                    background-color: rgba(15, 230, 181, 0.22);
                    color: #0FE6B5;
                    border: 1px solid rgba(15, 230, 181, 0.5);
                }
            """)
            btn.clicked.connect(lambda _, t=tool_id: self._select_tool(t))
            self.tool_group.addButton(btn)
            self.tool_buttons[tool_id] = btn
            vt_layout.addWidget(btn)

        self.tool_buttons["pen"].setChecked(True)
        vt_layout.addStretch()

        # Undo & Clear at bottom of vertical toolbar
        undo_btn = QPushButton("↩")
        undo_btn.setFixedSize(24, 24)
        undo_btn.setCursor(Qt.PointingHandCursor)
        undo_btn.setToolTip("Undo Last Stroke (Ctrl+Z)")
        undo_btn.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 11px;")
        undo_btn.clicked.connect(self._undo_stroke)
        vt_layout.addWidget(undo_btn)

        clear_btn = QPushButton("🗑️")
        clear_btn.setFixedSize(24, 24)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Clear Canvas")
        clear_btn.setStyleSheet("background: transparent; color: #64748b; border: none; font-size: 11px;")
        clear_btn.clicked.connect(self._clear_canvas)
        vt_layout.addWidget(clear_btn)

        body_layout.addWidget(v_toolbar)

        # Whiteboard Canvas Surface
        self.canvas = WhiteboardCanvas(self)
        self.canvas.stroke_finished.connect(self.broadcast_stroke_requested.emit)
        body_layout.addWidget(self.canvas, 1)

        layout.addWidget(body_widget, 1)

        # Wire canvas signals
        self.canvas.stroke_finished.connect(self._on_local_stroke_finished)
        self.canvas.peer_activity.connect(self._show_activity)

    def _select_tool(self, tool_id: str):
        self.canvas.set_tool(tool_id)

    def _undo_stroke(self):
        self.canvas.undo_stroke()
        self.broadcast_undo_requested.emit()

    def _clear_canvas(self):
        ans = QMessageBox.question(
            self,
            "Clear Collaborative Whiteboard",
            "Are you sure you want to clear the whiteboard canvas?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            self.canvas.clear_canvas()
            self.broadcast_clear_requested.emit()

    def _select_tool(self, tool_id: str):
        self.canvas.set_tool(tool_id)

    def _select_color(self, hex_code: str):
        self.canvas.set_color(hex_code)
        if self.canvas.active_tool == "eraser":
            self.tool_buttons["pen"].setChecked(True)
            self.canvas.set_tool("pen")

    def _select_width(self, width: int):
        self.canvas.set_stroke_width(width)

    def _on_local_stroke_finished(self, stroke: dict):
        self.broadcast_stroke_requested.emit(stroke)

    def _on_undo_clicked(self):
        self.canvas.undo_stroke()
        self.broadcast_undo_requested.emit()

    def _on_clear_clicked(self):
        ans = QMessageBox.question(
            self,
            "Clear Collaborative Whiteboard",
            "Are you sure you want to clear the entire whiteboard for everyone in the room?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            self.canvas.clear_canvas()
            self.broadcast_clear_requested.emit()

    def _toggle_maximize(self):
        self.is_maximized = not self.is_maximized
        if self.is_maximized:
            self.maximize_btn.setText("🗗 Restore")
        else:
            self.maximize_btn.setText("⛶ Maximize")
        self.maximize_toggled.emit(self.is_maximized)

    def _export_as_image(self):
        fpath, _ = QFileDialog.getSaveFileName(self, "Export Whiteboard as PNG", "whiteboard_sketch.png", "PNG Image (*.png)")
        if not fpath:
            return

        pixmap = self.canvas.grab()
        ok = pixmap.save(fpath, "PNG")
        if ok:
            QMessageBox.information(self, "Export Successful", f"Whiteboard sketch saved to:\n{fpath}")
        else:
            QMessageBox.critical(self, "Export Error", "Could not save whiteboard image.")

    def _show_activity(self, text: str):
        self.activity_tag.setText(text)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: self.activity_tag.setText(""))

    # --- External Handlers from CollabManager ---

    def handle_remote_stroke(self, stroke: dict):
        self.canvas.add_remote_stroke(stroke)

    def handle_remote_clear(self, peer_name: str):
        self.canvas.clear_canvas()
        self._show_activity(f"🗑️ {peer_name} cleared the canvas")

    def handle_remote_undo(self, peer_name: str):
        self.canvas.undo_stroke()
        self._show_activity(f"↩ {peer_name} undid a stroke")

    def handle_history_synced(self, strokes: list):
        self.canvas.set_history(strokes)
        if strokes:
            self._show_activity(f"✓ Synced {len(strokes)} whiteboard elements")
