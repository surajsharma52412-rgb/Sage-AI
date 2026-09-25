"""
Zero-Cost Guard Analytics & Interception Dialog for Sage AI.
Displays real-time budget governance metrics, cost saved in Indian Rupees (₹),
and a log of intercepted paid requests shifted to 100% Free models.
"""
import math
from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QWidget, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from database.db_manager import get_db
from engine.zero_cost_guard import get_zero_cost_guard


class AnimatedGlowCard(QFrame):
    """Stat card with animated breathing glow border."""

    def __init__(self, title: str, value: str, subtitle: str = "", accent: str = "#10b981", parent=None):
        super().__init__(parent)
        self.accent = accent
        self._pulse_phase = 0.0

        c = QColor(accent)
        self.r, self.g, self.b = c.red(), c.green(), c.blue()

        self.setObjectName("glowCard")
        self._update_style(0.25)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #8b95ad; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; background: transparent;")
        layout.addWidget(t_lbl)

        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 800; font-family: 'Segoe UI', sans-serif; background: transparent;")
        layout.addWidget(self.val_lbl)

        if subtitle:
            s_lbl = QLabel(subtitle)
            s_lbl.setStyleSheet("color: #626c85; font-size: 10px; font-weight: 500; background: transparent;")
            layout.addWidget(s_lbl)

    def _update_style(self, alpha: float):
        bg_alpha = min(0.12, alpha * 0.25)
        self.setStyleSheet(f"""
            QFrame#glowCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba({self.r}, {self.g}, {self.b}, {bg_alpha:.3f}),
                    stop:1 #0b1120);
                border: 1px solid rgba({self.r}, {self.g}, {self.b}, {alpha:.3f});
                border-radius: 12px;
            }}
        """)

    def animate_step(self, step: float):
        self._pulse_phase = step
        alpha = 0.20 + 0.35 * (0.5 * (1 + math.sin(self._pulse_phase)))
        self._update_style(alpha)

    def set_value(self, value: str):
        self.val_lbl.setText(value)


class ZeroCostGuardDialog(QDialog):
    """
    Rich Glassmorphism Dialog presenting Zero-Cost Guard statistics,
    money saved in INR (Rs), and recent request shifts.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zero-Cost Guardrail & Shift Architecture")
        self.resize(760, 560)
        self.setMinimumSize(680, 480)
        self.db = get_db()
        self.guard = get_zero_cost_guard()
        self._pulse_step = 0.0

        # Animation timer for header glow
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_header)
        self._anim_timer.start(50)

        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #080d1a;
                color: #f4f5fb;
            }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Header with Animated Shield Glow
        self.header_frame = QFrame()
        self.header_frame.setObjectName("headerFrame")
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(16, 14, 16, 14)
        h_layout.setSpacing(14)

        self.shield_lbl = QLabel("🛡️")
        self.shield_lbl.setStyleSheet("font-size: 32px; background: transparent;")
        h_layout.addWidget(self.shield_lbl)

        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(2)

        title_lbl = QLabel("Zero-Cost Guard Architecture")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 18px; font-weight: 800;")
        header_text_col.addWidget(title_lbl)

        sub_lbl = QLabel("Every AI request is checked • Models exceeding 0 Rs are blocked and shifted to 100% Free models")
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        header_text_col.addWidget(sub_lbl)
        h_layout.addLayout(header_text_col, 1)

        # Live Status Pill
        self.status_pill = QLabel("● 0 Rs ACTIVE")
        self.status_pill.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            padding: 5px 12px;
        """)
        h_layout.addWidget(self.status_pill)
        main_layout.addWidget(self.header_frame)

        # 2. Metric Cards Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_saved = AnimatedGlowCard("Total Money Saved", "₹0.00 Rs", "Against frontier paid rates", accent="#10b981")
        self.card_blocked = AnimatedGlowCard("Requests Shifted", "0 Shifts", "Paid models intercepted", accent="#00D1FF")
        self.card_limit = AnimatedGlowCard("Max Price Limit", "0.00 Rs", "Strict Free-Tier Guarantee", accent="#a855f7")

        metrics_layout.addWidget(self.card_saved)
        metrics_layout.addWidget(self.card_blocked)
        metrics_layout.addWidget(self.card_limit)
        main_layout.addLayout(metrics_layout)

        # 3. Interception Log Table Section
        table_header_row = QHBoxLayout()
        lbl_table = QLabel("Recent Intercepted & Shifted Requests")
        lbl_table.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700;")
        table_header_row.addWidget(lbl_table)
        table_header_row.addStretch()

        self.count_badge = QLabel("0 records")
        self.count_badge.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 600;")
        table_header_row.addWidget(self.count_badge)
        main_layout.addLayout(table_header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Time", "Intercepted Paid Model", "Shifted Free Model", "Cost Saved", "Status"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0b101c;
                border: 1px solid #1a2538;
                border-radius: 8px;
                color: #e2e8f0;
                gridline-color: transparent;
                selection-background-color: rgba(16, 185, 129, 0.2);
            }
            QTableWidget::item {
                padding: 8px 10px;
                border-bottom: 1px solid #151e2e;
            }
            QHeaderView::section {
                background-color: #0e1626;
                color: #94A3B8;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                border: none;
                border-bottom: 1px solid #273449;
                padding: 8px 10px;
            }
        """)
        main_layout.addWidget(self.table, 1)

        # 4. Bottom Controls
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh Analytics")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.3);
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
                border-color: #00D1FF;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        btn_layout.addWidget(refresh_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #0A0F14;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

    def _animate_header(self):
        """Animates breathing glow on the dialog header, status pill, and metric cards."""
        self._pulse_step += 0.08
        alpha = 0.20 + 0.25 * (0.5 * (1 + math.sin(self._pulse_step)))

        self.header_frame.setStyleSheet(f"""
            QFrame#headerFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.12),
                    stop:1 rgba(0, 209, 255, 0.06));
                border: 1px solid rgba(16, 185, 129, {alpha:.2f});
                border-radius: 12px;
            }}
        """)

        # Pulse status pill
        pill_alpha = 0.12 + 0.15 * (0.5 * (1 + math.sin(self._pulse_step)))
        self.status_pill.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, {pill_alpha:.2f});
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, {alpha:.2f});
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            padding: 5px 12px;
        """)

        # Pulse metric cards with progressive phase shifts
        if hasattr(self, "card_saved"):
            self.card_saved.animate_step(self._pulse_step)
        if hasattr(self, "card_blocked"):
            self.card_blocked.animate_step(self._pulse_step + 1.2)
        if hasattr(self, "card_limit"):
            self.card_limit.animate_step(self._pulse_step + 2.4)

    def refresh_data(self):
        """Loads latest stats and interception logs from SQLite."""
        stats = self.db.get_zero_cost_stats()
        saved_rs = stats.get("total_saved_rs", 0.0)
        total_intercepted = stats.get("total_intercepted", 0)

        self.card_saved.set_value(f"₹{saved_rs:.2f} Rs")
        self.card_blocked.set_value(f"{total_intercepted} Shifts")

        shifts = self.db.get_zero_cost_shifts(limit=50)
        self.count_badge.setText(f"{len(shifts)} records")

        self.table.setRowCount(len(shifts))
        for row_idx, item in enumerate(shifts):
            # Time
            ts = item.get("timestamp", "")
            if "T" in ts:
                ts = ts.split("T")[1][:8]
            time_item = QTableWidgetItem(ts)
            time_item.setForeground(QColor("#94A3B8"))

            # Original paid model
            orig_m = item.get("original_model", "Unknown")
            orig_item = QTableWidgetItem(f"🚫 {orig_m}")
            orig_item.setForeground(QColor("#f59e0b"))

            # Shifted free model
            shift_m = item.get("shifted_model", "Free Model")
            shift_prov = item.get("shifted_provider", "")
            shift_disp = f"🟢 {shift_m}" + (f" ({shift_prov.title()})" if shift_prov else "")
            shift_item = QTableWidgetItem(shift_disp)
            shift_item.setForeground(QColor("#10b981"))

            # Cost saved
            c_saved = float(item.get("cost_saved_rs", 0.0))
            saved_item = QTableWidgetItem(f"₹{c_saved:.2f} Rs")
            saved_item.setForeground(QColor("#10b981"))
            saved_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            # Status
            status_item = QTableWidgetItem("0 Rs Free Tier")
            status_item.setForeground(QColor("#00D1FF"))
            status_item.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row_idx, 0, time_item)
            self.table.setItem(row_idx, 1, orig_item)
            self.table.setItem(row_idx, 2, shift_item)
            self.table.setItem(row_idx, 3, saved_item)
            self.table.setItem(row_idx, 4, status_item)

    def closeEvent(self, event):
        self._anim_timer.stop()
        super().closeEvent(event)
