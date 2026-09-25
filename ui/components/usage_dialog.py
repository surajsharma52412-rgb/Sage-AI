"""
Model Usage & Analytics Dialog for Sage AI.
Displays real-time token counts, request totals, latency statistics,
and per-model breakdowns stored in the local SQLite database.
"""
import json
from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QWidget, QScrollArea
)
from PySide6.QtCore import Qt

from database.db_manager import get_db
from engine.model_scanner import ModelScanner


class MetricCard(QFrame):
    """Stat card displaying a single aggregated metric."""

    def __init__(self, title: str, value: str, subtitle: str = "", accent: str = "#00D1FF", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.18);
                border-radius: 12px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #8b95ad; font-size: 11px; font-weight: 600; text-transform: uppercase;")
        layout.addWidget(title_lbl)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"color: {accent}; font-size: 20px; font-weight: 800;")
        layout.addWidget(val_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet("color: #626c85; font-size: 10px;")
            layout.addWidget(sub_lbl)


class QuotaCard(QFrame):
    """Card displaying a provider's remaining allowance, credit or tier quota."""

    def __init__(self, provider_id: str, display_name: str, quota_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 10px;
                padding: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet("color: #f4f5fb; font-size: 12px; font-weight: 700;")
        header.addWidget(name_lbl)
        header.addStretch()

        is_free = quota_data.get("is_free_tier", False)
        tier_type = quota_data.get("tier_type") or ("100% Free Offline" if provider_id == "ollama" else ("Free Tier" if is_free else "Paid / Credits"))
        badge = QLabel(tier_type)
        badge_color = "#10b981" if is_free else "#38bdf8"
        badge.setStyleSheet(f"color: {badge_color}; background-color: rgba(16, 185, 129, 0.12); font-size: 9px; font-weight: 700; border-radius: 4px; padding: 2px 6px;")
        header.addWidget(badge)
        layout.addLayout(header)

        rem = quota_data.get("remaining_amount", 0.0)
        unit = quota_data.get("currency_or_unit", "")
        if unit == "USD":
            val_text = f"${rem:.2f} USD"
        elif "Unlimited" in unit:
            val_text = "Unlimited"
        elif "Credits" in unit:
            val_text = f"{int(rem):,} Credits"
        else:
            val_text = f"{int(rem):,} {unit}" if rem else "Active"

        val_lbl = QLabel(val_text)
        val_lbl.setStyleSheet("color: #00D1FF; font-size: 15px; font-weight: 800;")
        layout.addWidget(val_lbl)

        sub_text = f"Used: {quota_data.get('used_amount', 0):.1f}" if unit == "USD" else quota_data.get("details", {}).get("tier", "Active Quota")
        if isinstance(sub_text, dict):
            sub_text = "Standard API Tier"
        sub_lbl = QLabel(str(sub_text))
        sub_lbl.setStyleSheet("color: #626c85; font-size: 10px;")
        layout.addWidget(sub_lbl)

        reset_time = quota_data.get("reset_time")
        if not reset_time:
            from engine.model_scanner import ModelScanner
            r_info = ModelScanner.get_provider_reset_info(provider_id)
            reset_time = r_info.get("reset_time", "")

        if provider_id == "ollama":
            reset_lbl = QLabel("⏱ Unlimited Local • No Limits")
            reset_lbl.setStyleSheet("color: #00D1FF; font-size: 10px; font-weight: 600;")
            layout.addWidget(reset_lbl)
        elif reset_time:
            reset_lbl = QLabel(f"⏱ Limits Reset: {reset_time}")
            reset_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 600;")
            layout.addWidget(reset_lbl)


class UsageDialog(QDialog):
    """Interactive analytics dashboard for model usage, token metrics, and remaining quotas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sage AI - Model Usage & Remaining Quotas")
        self.resize(820, 660)
        self.db = get_db()

        self._init_ui()
        self._refresh_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        icon_lbl = QLabel("📊")
        icon_lbl.setStyleSheet("color: #00D1FF; font-size: 20px;")
        header.addWidget(icon_lbl)

        title = QLabel("Model Usage & Remaining Balances")
        title.setStyleSheet("color: #f4f5fb; font-size: 16px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        rescan_btn = QPushButton("🔍 Rescan Quotas && Models")
        rescan_btn.setCursor(Qt.PointingHandCursor)
        rescan_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.25);
            }
        """)
        rescan_btn.clicked.connect(self._rescan_quotas)
        header.addWidget(rescan_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #a0a8be;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: rgba(0, 209, 255, 0.3);
            }
        """)
        refresh_btn.clicked.connect(self._refresh_data)
        header.addWidget(refresh_btn)

        main_layout.addLayout(header)

        # Top Aggregate Metrics Row
        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(10)
        main_layout.addLayout(self.metrics_layout)

        # Provider Quotas & Balances Section
        quota_hdr = QLabel("Provider Remaining Allowances & Balances")
        quota_hdr.setStyleSheet("color: #f4f5fb; font-size: 13px; font-weight: 700; margin-top: 4px;")
        main_layout.addWidget(quota_hdr)

        self.quotas_layout = QHBoxLayout()
        self.quotas_layout.setSpacing(10)
        main_layout.addLayout(self.quotas_layout)

        # Table Header Label
        table_hdr = QLabel("Per-Model Token Breakdown & History")
        table_hdr.setStyleSheet("color: #f4f5fb; font-size: 13px; font-weight: 700; margin-top: 6px;")
        main_layout.addWidget(table_hdr)

        # Per-Model Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Provider", "Model Name", "Tier", "Limit Reset Time", "Requests", "Prompt Tokens",
            "Completion Tokens", "Total Tokens", "Avg Latency"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0A0F14;
                border: 1px solid rgba(0, 209, 255, 0.15);
                border-radius: 10px;
                gridline-color: rgba(255, 255, 255, 0.04);
                color: #f4f5fb;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #162033;
                color: #00D1FF;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid rgba(0, 209, 255, 0.2);
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QTableWidget::item:selected {
                background-color: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
            }
        """)
        main_layout.addWidget(self.table, 1)

        # Bottom Button Bar
        bottom_bar = QHBoxLayout()
        reset_btn = QPushButton("🗑 Reset Usage Data")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(244, 63, 94, 0.12);
                color: #f43f5e;
                border: 1px solid rgba(244, 63, 94, 0.25);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(244, 63, 94, 0.22);
                border-color: #f43f5e;
            }
        """)
        reset_btn.clicked.connect(self._reset_usage)
        bottom_bar.addWidget(reset_btn)

        bottom_bar.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #f4f5fb;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 6px 20px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #00D1FF;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

    def _rescan_quotas(self):
        """Scans all configured providers to refresh live quotas and discovered models."""
        ModelScanner.scan_all_configured()
        self._refresh_data()

    def _refresh_data(self):
        summary = self.db.get_model_usage_summary()

        # Clear existing metric widgets
        for i in reversed(range(self.metrics_layout.count())):
            item = self.metrics_layout.itemAt(i)
            w = item.widget()
            if w:
                w.deleteLater()

        # Add top metric cards
        total_req = summary.get("total_requests", 0)
        total_tok = summary.get("total_tokens", 0)
        avg_lat = summary.get("avg_latency_ms", 0.0)

        by_prov = summary.get("by_provider", [])
        top_prov = by_prov[0]["provider_id"].upper() if by_prov else "None"

        c1 = MetricCard("Total Queries", f"{total_req:,}", "Invocations across all models", "#00D1FF")
        c2 = MetricCard("Total Tokens", f"{total_tok:,}", "Prompt + Completion", "#38bdf8")
        c3 = MetricCard("Average Latency", f"{avg_lat / 1000.0:.2f}s" if avg_lat >= 1000 else f"{int(avg_lat)}ms", "Response turn-around", "#fbbf24")
        c4 = MetricCard("Primary Provider", top_prov, f"{len(summary.get('by_model', []))} models used", "#a78bfa")

        self.metrics_layout.addWidget(c1)
        self.metrics_layout.addWidget(c2)
        self.metrics_layout.addWidget(c3)
        self.metrics_layout.addWidget(c4)

        # Refresh Provider Quotas
        for i in reversed(range(self.quotas_layout.count())):
            item = self.quotas_layout.itemAt(i)
            w = item.widget()
            if w:
                w.deleteLater()

        quotas = self.db.get_all_provider_quotas()
        provider_names = {
            "nvidia": "NVIDIA NIM",
            "groq": "Groq Cloud",
            "openrouter": "OpenRouter",
            "gemini": "Google Gemini",
            "ollama": "Local Ollama"
        }

        # If no quotas yet, create defaults from known provider state
        quota_list = list(quotas.values()) if isinstance(quotas, dict) else (quotas or [])
        if not quota_list:
            quota_list = [
                {"provider_id": "nvidia", "total_limit": 1000, "used_amount": 0, "remaining_amount": 1000, "currency_or_unit": "Credits", "is_free_tier": 1},
                {"provider_id": "groq", "total_limit": 14400, "used_amount": 0, "remaining_amount": 14400, "currency_or_unit": "Requests/Day", "is_free_tier": 1},
                {"provider_id": "gemini", "total_limit": 1500, "used_amount": 0, "remaining_amount": 1500, "currency_or_unit": "Requests/Day", "is_free_tier": 1},
                {"provider_id": "ollama", "total_limit": 0, "used_amount": 0, "remaining_amount": 0, "currency_or_unit": "Unlimited", "is_free_tier": 1},
            ]

        for q in quota_list:
            pid = q.get("provider_id", "")
            dname = provider_names.get(pid, pid.upper())
            qcard = QuotaCard(pid, dname, q)
            self.quotas_layout.addWidget(qcard)

        # Populate table
        models = summary.get("by_model", [])
        self.table.setRowCount(len(models))

        for row_idx, m in enumerate(models):
            pid = m.get("provider_id", "")
            r_info = ModelScanner.get_provider_reset_info(pid)
            tier_name = r_info.get("tier_type", "Free Tier")
            reset_time_name = r_info.get("reset_time", "00:00 UTC")

            p_item = QTableWidgetItem(pid.upper())
            name_item = QTableWidgetItem(m["model_name"])
            tier_item = QTableWidgetItem(tier_name)
            reset_item = QTableWidgetItem(reset_time_name)
            req_item = QTableWidgetItem(f"{m['requests']:,}")
            prompt_item = QTableWidgetItem(f"{m['prompt_tokens']:,}")
            comp_item = QTableWidgetItem(f"{m['completion_tokens']:,}")
            total_item = QTableWidgetItem(f"{m['total_tokens']:,}")
            lat_item = QTableWidgetItem(f"{m['avg_latency_ms']:.0f} ms")

            # Center align tier and reset columns
            tier_item.setTextAlignment(Qt.AlignCenter)
            reset_item.setTextAlignment(Qt.AlignCenter)

            # Right align numerical columns
            for item in [req_item, prompt_item, comp_item, total_item, lat_item]:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.table.setItem(row_idx, 0, p_item)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, tier_item)
            self.table.setItem(row_idx, 3, reset_item)
            self.table.setItem(row_idx, 4, req_item)
            self.table.setItem(row_idx, 5, prompt_item)
            self.table.setItem(row_idx, 6, comp_item)
            self.table.setItem(row_idx, 7, total_item)
            self.table.setItem(row_idx, 8, lat_item)

    def _reset_usage(self):
        reply = QMessageBox.question(
            self,
            "Reset Usage Data",
            "Are you sure you want to reset all recorded token and request analytics? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.reset_model_usage()
            self._refresh_data()

