"""
Universal AI Auto Router Global Ranking Dashboard for Sage AI.
Displays all 54 registered models ranked globally from BEST (#1) to LOWEST (#54).
Features:
- Header matching reference diagram: "SAGE AI - Universal AI Auto Router"
- 8-Factor dynamic scoring weights display
- Filter views: [Overall Rank], [By Provider], [By Task Type]
- Search bar for quick model / provider lookup
- Color-coded status badges (Available, Rate Limited, Unavailable)
- Detailed Factor Breakdown inspection dialog
- Test Prompt Routing Simulator
"""
import logging
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QSizePolicy, QDialog, QGridLayout,
    QProgressBar, QApplication
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QCursor

from engine.auto_router import get_auto_router, TaskType, ModelScore, ModelStatus
from database.db_manager import get_db

logger = logging.getLogger(__name__)

# Provider branding badges
PROVIDER_COLORS = {
    "openrouter": ("#4f80ff", "#1e293b"),
    "gemini": ("#00D1FF", "#0f2b38"),
    "groq": ("#f97316", "#331f12"),
    "nvidia": ("#10b981", "#0d281e"),
    "mistral": ("#ff5c77", "#30131b"),
    "cerebras": ("#ec4899", "#2e1220"),
    "cloudflare": ("#f59e0b", "#2f220d"),
    "cohere": ("#8b5cf6", "#211538"),
    "huggingface": ("#eab308", "#2a220c"),
    "ollama": ("#06b6d4", "#0e2c33"),
    "image": ("#d946ef", "#2b0f30"),
}


class FactorBreakdownDialog(QDialog):
    """Inspects detailed 8-factor scoring weights for an individual model."""

    def __init__(self, score_item: ModelScore, parent=None):
        super().__init__(parent)
        self.score_item = score_item
        self.setWindowTitle(f"Scoring Breakdown — {score_item.model.display_name}")
        self.setFixedSize(520, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #0A0F14;
                border: 1px solid #1E293B;
                border-radius: 12px;
            }
            QLabel {
                color: #F8FAFC;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        hdr_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        m = self.score_item.model
        name_lbl = QLabel(m.display_name)
        name_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #F8FAFC;")
        title_box.addWidget(name_lbl)

        id_lbl = QLabel(f"{m.provider_id.upper()} • {m.model_id}")
        id_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        title_box.addWidget(id_lbl)
        hdr_row.addLayout(title_box)
        hdr_row.addStretch()

        score_badge = QLabel(f"{self.score_item.overall_score:.1f}")
        score_badge.setStyleSheet("""
            background: rgba(0, 209, 255, 0.15);
            color: #00D1FF;
            font-size: 22px;
            font-weight: 800;
            padding: 8px 16px;
            border: 1px solid rgba(0, 209, 255, 0.4);
            border-radius: 8px;
        """)
        hdr_row.addWidget(score_badge)
        layout.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #1E293B; max-height: 1px;")
        layout.addWidget(sep)

        # 8 Factors Grid
        factors = [
            ("Quality Benchmark", "30%", self.score_item.quality_factor, "#00D1FF"),
            ("Task Capability", "20%", self.score_item.task_factor, "#4f80ff"),
            ("Real-time Availability", "10%", self.score_item.availability_factor, "#10b981"),
            ("API Quota / Rate Limit", "10%", self.score_item.quota_factor, "#a855f7"),
            ("Latency / Speed", "10%", self.score_item.speed_factor, "#f59e0b"),
            ("Cost Efficiency", "10%", self.score_item.cost_factor, "#06b6d4"),
            ("Context Window", "5%", self.score_item.context_factor, "#ec4899"),
            ("Provider Health", "5%", self.score_item.health_factor, "#10b981"),
        ]

        factors_box = QVBoxLayout()
        factors_box.setSpacing(10)

        for name, weight, val, color in factors:
            row = QVBoxLayout()
            row.setSpacing(2)

            top_line = QHBoxLayout()
            lbl_name = QLabel(f"{name} ({weight})")
            lbl_name.setStyleSheet("font-size: 12px; color: #94A3B8; font-weight: 500;")
            top_line.addWidget(lbl_name)
            top_line.addStretch()

            lbl_val = QLabel(f"{val:.1f} / 10.0")
            lbl_val.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color};")
            top_line.addWidget(lbl_val)
            row.addLayout(top_line)

            bar = QProgressBar()
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(int(min(10.0, max(0.0, val)) * 10))
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: #162033;
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 3px;
                }}
            """)
            row.addWidget(bar)
            factors_box.addLayout(row)

        layout.addLayout(factors_box)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #202e48;
                border-color: #00D1FF;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class GlobalRankingView(QWidget):
    """
    Production-ready Global Model Ranking dashboard displaying all 54 core models.
    """

    back_to_chat_requested = Signal()
    request_add_models = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auto_router = get_auto_router()
        self._current_filter_mode = "overall"  # "overall", "provider", "task"
        self._selected_task = TaskType.GENERAL_CHAT
        self._selected_provider = "all"
        self._search_query = ""
        self._cached_scores: List[ModelScore] = []
        self._has_loaded_ranking = False

        self._init_ui()
        self.refresh_ranking()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_loaded_ranking:
            self.refresh_ranking()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ----------------------------------------------------------------------
        # 1. Top Header Bar
        # ----------------------------------------------------------------------
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #0C121A;
                border: 1px solid #1E293B;
                border-radius: 12px;
                padding: 12px 18px;
            }
        """)
        hdr_layout = QHBoxLayout(header_frame)
        hdr_layout.setContentsMargins(4, 4, 4, 4)
        hdr_layout.setSpacing(14)

        # Left Branding
        brand_box = QVBoxLayout()
        brand_box.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        moon_icon = QLabel("🌙")
        moon_icon.setStyleSheet("font-size: 20px;")
        title_row.addWidget(moon_icon)

        title_lbl = QLabel("SAGE AI")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 18px; font-weight: 800; letter-spacing: 1.5px;")
        title_row.addWidget(title_lbl)

        sub_badge = QLabel("UNIVERSAL AI AUTO ROUTER")
        sub_badge.setStyleSheet("""
            background: rgba(0, 209, 255, 0.12);
            color: #00D1FF;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid rgba(0, 209, 255, 0.3);
        """)
        title_row.addWidget(sub_badge)
        title_row.addStretch()
        brand_box.addLayout(title_row)

        subtitle_lbl = QLabel("All Models. One System. Best Answer. • Right Model. Right Task. Always.")
        subtitle_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        brand_box.addWidget(subtitle_lbl)

        hdr_layout.addLayout(brand_box)
        hdr_layout.addStretch()

        # Action buttons
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.rescore_btn = QPushButton("🔄 Rescore & Re-rank")
        self.rescore_btn.setCursor(Qt.PointingHandCursor)
        self.rescore_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #202e48;
                border-color: #00D1FF;
                color: #00D1FF;
            }
        """)
        self.rescore_btn.clicked.connect(self.refresh_ranking)
        actions_row.addWidget(self.rescore_btn)

        self.keys_btn = QPushButton("✨ Manage API Keys")
        self.keys_btn.setCursor(Qt.PointingHandCursor)
        self.keys_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.25);
            }
        """)
        self.keys_btn.clicked.connect(self.request_add_models.emit)
        actions_row.addWidget(self.keys_btn)

        self.back_btn = QPushButton("← Back to Chat")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #F8FAFC;
                border-color: #64748B;
            }
        """)
        self.back_btn.clicked.connect(self.back_to_chat_requested.emit)
        actions_row.addWidget(self.back_btn)

        hdr_layout.addLayout(actions_row)
        main_layout.addWidget(header_frame)

        # ----------------------------------------------------------------------
        # 2. Dynamic Scoring Engine Formula Weights Banner
        # ----------------------------------------------------------------------
        weights_frame = QFrame()
        weights_frame.setStyleSheet("""
            QFrame {
                background-color: #0A0F14;
                border: 1px solid #162033;
                border-radius: 10px;
                padding: 8px 14px;
            }
        """)
        w_layout = QHBoxLayout(weights_frame)
        w_layout.setContentsMargins(6, 4, 6, 4)
        w_layout.setSpacing(10)

        weights_title = QLabel("⚖️ Scoring Factors (Weights):")
        weights_title.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        w_layout.addWidget(weights_title)

        weights_items = [
            ("Quality", "30%", "#00D1FF"),
            ("Task Match", "20%", "#4f80ff"),
            ("Availability", "10%", "#10b981"),
            ("API Quota", "10%", "#a855f7"),
            ("Latency/Speed", "10%", "#f59e0b"),
            ("Cost", "10%", "#06b6d4"),
            ("Context", "5%", "#ec4899"),
            ("Health", "5%", "#10b981"),
        ]

        for factor, pct, color in weights_items:
            chip = QLabel(f"<b>{factor}</b> <span style='color:{color}; font-weight:bold;'>{pct}</span>")
            chip.setStyleSheet("""
                background-color: #121A24;
                color: #CBD5E1;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 5px;
                border: 1px solid #1e293b;
            """)
            w_layout.addWidget(chip)

        w_layout.addStretch()
        main_layout.addWidget(weights_frame)

        # ----------------------------------------------------------------------
        # 3. Controls & Filter Bar
        # ----------------------------------------------------------------------
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        # View Mode Toggle Pills: [Overall Rank] [By Provider] [By Task Type]
        view_toggle_frame = QFrame()
        view_toggle_frame.setStyleSheet("""
            QFrame {
                background-color: #0C121A;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 2px;
            }
        """)
        vt_layout = QHBoxLayout(view_toggle_frame)
        vt_layout.setContentsMargins(4, 2, 4, 2)
        vt_layout.setSpacing(4)

        self.btn_mode_overall = QPushButton("📊 Overall Rank")
        self.btn_mode_overall.setCheckable(True)
        self.btn_mode_overall.setChecked(True)
        self.btn_mode_overall.setCursor(Qt.PointingHandCursor)
        self.btn_mode_overall.clicked.connect(lambda: self._set_filter_mode("overall"))
        vt_layout.addWidget(self.btn_mode_overall)

        self.btn_mode_provider = QPushButton("🏢 By Provider")
        self.btn_mode_provider.setCheckable(True)
        self.btn_mode_provider.setCursor(Qt.PointingHandCursor)
        self.btn_mode_provider.clicked.connect(lambda: self._set_filter_mode("provider"))
        vt_layout.addWidget(self.btn_mode_provider)

        self.btn_mode_task = QPushButton("🎯 By Task Type")
        self.btn_mode_task.setCheckable(True)
        self.btn_mode_task.setCursor(Qt.PointingHandCursor)
        self.btn_mode_task.clicked.connect(lambda: self._set_filter_mode("task"))
        vt_layout.addWidget(self.btn_mode_task)

        self._style_pill_buttons()
        filter_bar.addWidget(view_toggle_frame)

        # Dropdowns for Provider or Task Type (visible when active)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "All Providers", "Google Gemini", "Groq", "OpenRouter", "NVIDIA NIM",
            "Mistral", "Cerebras", "Cloudflare", "Cohere", "Hugging Face", "Ollama (Local)"
        ])
        self.provider_combo.setStyleSheet("""
            QComboBox {
                background-color: #121A24;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                min-width: 130px;
            }
            QComboBox QAbstractItemView {
                background-color: #0C121A;
                color: #F8FAFC;
                selection-background-color: #00D1FF;
                selection-color: #0A0F14;
            }
        """)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_combo_changed)
        self.provider_combo.setVisible(False)
        filter_bar.addWidget(self.provider_combo)

        self.task_combo = QComboBox()
        self.task_combo.addItems([
            "General Chat", "Coding / Development", "Reasoning / Deep Analysis",
            "Vision & Multimodal", "Image Generation", "Fast & Lightweight",
            "Long Context (1M+)", "Agent / Tool Execution"
        ])
        self.task_combo.setStyleSheet("""
            QComboBox {
                background-color: #121A24;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                min-width: 170px;
            }
            QComboBox QAbstractItemView {
                background-color: #0C121A;
                color: #F8FAFC;
                selection-background-color: #00D1FF;
                selection-color: #0A0F14;
            }
        """)
        self.task_combo.currentIndexChanged.connect(self._on_task_combo_changed)
        self.task_combo.setVisible(False)
        filter_bar.addWidget(self.task_combo)

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search models by name, provider, or ID...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #0C121A;
                color: #F8FAFC;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                min-width: 260px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        filter_bar.addWidget(self.search_input)

        filter_bar.addStretch()

        # Legend: Available, Rate Limited, Unavailable
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(12)

        avail_leg = QLabel("🟢 Available")
        avail_leg.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        legend_layout.addWidget(avail_leg)

        rl_leg = QLabel("🟡 Rate Limited")
        rl_leg.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 600;")
        legend_layout.addWidget(rl_leg)

        unavail_leg = QLabel("🔴 Unavailable")
        unavail_leg.setStyleSheet("color: #ff5c77; font-size: 11px; font-weight: 600;")
        legend_layout.addWidget(unavail_leg)

        filter_bar.addLayout(legend_layout)
        main_layout.addLayout(filter_bar)

        # ----------------------------------------------------------------------
        # 4. Global Ranking Model Queue (Table matching user diagram)
        # ----------------------------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "# Rank", "Model Name", "Provider", "Score", "Context", "Speed", "Cost", "Status"
        ])
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0A0F14;
                border: 1px solid #1E293B;
                border-radius: 10px;
                gridline-color: #162033;
                color: #F8FAFC;
                font-size: 12px;
                selection-background-color: rgba(0, 209, 255, 0.15);
                selection-color: #00D1FF;
            }
            QHeaderView::section {
                background-color: #0C121A;
                color: #94A3B8;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border: none;
                border-bottom: 1px solid #1E293B;
                padding: 8px 10px;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #121A24;
            }
            QTableWidget::item:hover {
                background-color: #121A24;
            }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setCursor(Qt.PointingHandCursor)
        self.table.itemDoubleClicked.connect(self._on_table_row_double_clicked)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # # Rank
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # Model Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Provider
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Score
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Context
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Speed
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Cost
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Status

        main_layout.addWidget(self.table, 1)

        # ----------------------------------------------------------------------
        # 5. Bottom Status Strip & Quick Routing Simulator
        # ----------------------------------------------------------------------
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("""
            QFrame {
                background-color: #0C121A;
                border: 1px solid #1E293B;
                border-radius: 10px;
                padding: 8px 14px;
            }
        """)
        bf_layout = QHBoxLayout(bottom_frame)
        bf_layout.setContentsMargins(6, 4, 6, 4)
        bf_layout.setSpacing(12)

        self.summary_badge = QLabel("ALL 54 MODELS. ONE ROUTER.")
        self.summary_badge.setStyleSheet("""
            background: rgba(0, 209, 255, 0.12);
            color: #00D1FF;
            font-size: 11px;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 5px;
            letter-spacing: 0.8px;
        """)
        bf_layout.addWidget(self.summary_badge)

        self.status_count_lbl = QLabel("Showing 54 Models")
        self.status_count_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        bf_layout.addWidget(self.status_count_lbl)

        bf_layout.addStretch()

        hint_lbl = QLabel("💡 Double-click any model to inspect full 8-factor score breakdown")
        hint_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic;")
        bf_layout.addWidget(hint_lbl)

        main_layout.addWidget(bottom_frame)

    def _style_pill_buttons(self):
        style_active = """
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
            }
        """
        style_inactive = """
            QPushButton {
                background-color: transparent;
                color: #94A3B8;
                font-weight: 600;
                font-size: 11px;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                color: #F8FAFC;
                background-color: #162033;
            }
        """
        self.btn_mode_overall.setStyleSheet(style_active if self._current_filter_mode == "overall" else style_inactive)
        self.btn_mode_provider.setStyleSheet(style_active if self._current_filter_mode == "provider" else style_inactive)
        self.btn_mode_task.setStyleSheet(style_active if self._current_filter_mode == "task" else style_inactive)

    def _set_filter_mode(self, mode: str):
        self._current_filter_mode = mode
        self.btn_mode_overall.setChecked(mode == "overall")
        self.btn_mode_provider.setChecked(mode == "provider")
        self.btn_mode_task.setChecked(mode == "task")
        self.provider_combo.setVisible(mode == "provider")
        self.task_combo.setVisible(mode == "task")
        self._style_pill_buttons()
        self.refresh_ranking()

    def _on_provider_combo_changed(self, idx: int):
        prov_map = {
            0: "all",
            1: "gemini",
            2: "groq",
            3: "openrouter",
            4: "nvidia",
            5: "mistral",
            6: "cerebras",
            7: "cloudflare",
            8: "cohere",
            9: "huggingface",
            10: "ollama"
        }
        self._selected_provider = prov_map.get(idx, "all")
        self._populate_table()

    def _on_task_combo_changed(self, idx: int):
        task_map = {
            0: TaskType.GENERAL_CHAT,
            1: TaskType.CODING,
            2: TaskType.REASONING,
            3: TaskType.VISION,
            4: TaskType.IMAGE_GEN,
            5: TaskType.FAST_LIGHTWEIGHT,
            6: TaskType.LONG_CONTEXT,
            7: TaskType.AGENT
        }
        self._selected_task = task_map.get(idx, TaskType.GENERAL_CHAT)
        self.refresh_ranking()

    def _on_search_text_changed(self, text: str):
        self._search_query = text.strip().lower()
        self._populate_table()

    def refresh_ranking(self):
        """Re-scores and re-ranks all 54 models based on current active filters."""
        self._has_loaded_ranking = True
        task = self._selected_task if self._current_filter_mode == "task" else None
        # Get dynamic ranking across all 54 models (without filtering out image models in queue)
        self._cached_scores = self.auto_router.get_global_ranking(task=task, filter_incompatible=False)
        self._populate_table()

    def _populate_table(self):
        """Fills the ranking table based on active filter and search query."""
        self.table.setRowCount(0)

        displayed_count = 0
        avail_count = 0

        for score_item in self._cached_scores:
            m = score_item.model

            # Provider filter
            if self._current_filter_mode == "provider" and self._selected_provider != "all":
                if m.provider_id != self._selected_provider:
                    continue

            # Search query filter
            if self._search_query:
                q = self._search_query
                match = (
                    q in m.display_name.lower()
                    or q in m.model_id.lower()
                    or q in m.provider_id.lower()
                    or q in m.description.lower()
                )
                if not match:
                    continue

            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            displayed_count += 1

            if score_item.status == ModelStatus.AVAILABLE.value:
                avail_count += 1

            # 0: Rank #
            rank_item = QTableWidgetItem(f"#{score_item.global_rank}")
            rank_item.setTextAlignment(Qt.AlignCenter)
            if score_item.global_rank <= 3:
                rank_item.setForeground(QColor("#00D1FF"))
                f = rank_item.font()
                f.setBold(True)
                rank_item.setFont(f)
            else:
                rank_item.setForeground(QColor("#94A3B8"))
            self.table.setItem(row_idx, 0, rank_item)

            # 1: Model Name + ID
            name_item = QTableWidgetItem(m.display_name)
            name_item.setToolTip(f"{m.model_id}\n{m.description}")
            name_f = name_item.font()
            name_f.setBold(True)
            name_item.setFont(name_f)
            self.table.setItem(row_idx, 1, name_item)

            # 2: Provider Badge
            prov_text = m.provider_id.upper()
            if m.provider_id == "ollama":
                prov_text = "OLLAMA (LOCAL)"
            elif m.provider_id == "nvidia":
                prov_text = "NVIDIA NIM"
            prov_item = QTableWidgetItem(prov_text)
            prov_item.setTextAlignment(Qt.AlignCenter)
            p_color, _ = PROVIDER_COLORS.get(m.provider_id, ("#94A3B8", "#1E293B"))
            prov_item.setForeground(QColor(p_color))
            self.table.setItem(row_idx, 2, prov_item)

            # 3: Score
            score_val = score_item.overall_score
            score_item_cell = QTableWidgetItem(f"{score_val:.1f}")
            score_item_cell.setTextAlignment(Qt.AlignCenter)
            sf = score_item_cell.font()
            sf.setBold(True)
            score_item_cell.setFont(sf)
            if score_val >= 9.0:
                score_item_cell.setForeground(QColor("#00D1FF"))
            elif score_val >= 8.0:
                score_item_cell.setForeground(QColor("#4f80ff"))
            elif score_val >= 7.0:
                score_item_cell.setForeground(QColor("#10b981"))
            else:
                score_item_cell.setForeground(QColor("#94A3B8"))
            self.table.setItem(row_idx, 3, score_item_cell)

            # 4: Context
            ctx = m.context_length
            if ctx >= 1000000:
                ctx_str = f"{ctx // 1000000}M"
            elif ctx >= 1000:
                ctx_str = f"{ctx // 1000}K"
            else:
                ctx_str = str(ctx)
            ctx_item = QTableWidgetItem(ctx_str)
            ctx_item.setTextAlignment(Qt.AlignCenter)
            ctx_item.setForeground(QColor("#94A3B8"))
            self.table.setItem(row_idx, 4, ctx_item)

            # 5: Speed
            speed_item = QTableWidgetItem(f"{m.speed_score:.1f}/10")
            speed_item.setTextAlignment(Qt.AlignCenter)
            speed_item.setForeground(QColor("#CBD5E1"))
            self.table.setItem(row_idx, 5, speed_item)

            # 6: Cost (Free / Paid)
            cost_str = "Free" if m.is_free else "Paid"
            cost_item = QTableWidgetItem(cost_str)
            cost_item.setTextAlignment(Qt.AlignCenter)
            cost_item.setForeground(QColor("#10b981" if m.is_free else "#f59e0b"))
            self.table.setItem(row_idx, 6, cost_item)

            # 7: Status
            status_item = QTableWidgetItem()
            status_item.setTextAlignment(Qt.AlignCenter)
            if score_item.status == ModelStatus.AVAILABLE.value:
                status_item.setText("🟢 Available")
                status_item.setForeground(QColor("#10b981"))
            elif score_item.status == ModelStatus.RATE_LIMITED.value:
                status_item.setText("🟡 Cooldown")
                status_item.setForeground(QColor("#f59e0b"))
            else:
                status_item.setText("🔴 No Key")
                status_item.setForeground(QColor("#ff5c77"))
            self.table.setItem(row_idx, 7, status_item)

            # Store score_item reference in row 0
            rank_item.setData(Qt.UserRole, score_item)

        self.status_count_lbl.setText(f"Showing {displayed_count} Models • {avail_count} Ready to Route")

    def _on_table_row_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        rank_item = self.table.item(row, 0)
        if not rank_item:
            return
        score_item: Optional[ModelScore] = rank_item.data(Qt.UserRole)
        if score_item:
            dialog = FactorBreakdownDialog(score_item, parent=self)
            dialog.exec()
