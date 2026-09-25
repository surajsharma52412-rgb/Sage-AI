"""
Searchable Model Selector Popup Component for Sage AI.
Matches the user's reference UI design:
- Top search input: '🔍 Search models'
- Categorized provider sections (Nvidia, Groq, OpenRouter, Gemini, Ollama, Auto Router)
- Model cards with token usage badges and '[Free]' / '[Active]' indicators
- Sticky bottom footer: '⚙ Manage models' and '🔄 Refresh Models'
"""
import math
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QTimer
from PySide6.QtGui import QColor

from database.db_manager import get_db
from engine.model_scanner import ModelScanner
from engine.ollama_manager import start_ollama_service, is_ollama_running


class ElidedLabel(QLabel):
    """A QLabel that cleanly elides text with ellipsis (...) without forcing layout expansion."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        if text:
            self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def setText(self, text: str):
        self._full_text = text
        if text:
            self.setToolTip(text)
        self._update_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self):
        if not self._full_text:
            super().setText("")
            return
        fm = self.fontMetrics()
        avail_width = max(20, self.width() - 4)
        elided = fm.elidedText(self._full_text, Qt.ElideRight, avail_width)
        super().setText(elided)

    def minimumSizeHint(self) -> QSize:
        return QSize(40, self.fontMetrics().height() + 2)


class ModelItemWidget(QFrame):
    """Clickable row representing a model."""

    clicked = Signal(str)

    def __init__(
        self,
        model_name: str,
        display_name: str,
        provider_name: str,
        tokens_used: int = 0,
        is_free: bool = False,
        is_active: bool = False,
        is_available: bool = True,
        tier_type: str = "",
        reset_time: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.model_name = model_name
        self.display_name = display_name
        self.provider_name = provider_name
        self.is_active = is_active
        self.is_available = is_available

        if not tier_type:
            if "ollama" in provider_name.lower() or "ollama" in model_name.lower():
                tier_type = "100% Free Offline"
                reset_time = "Never (Unlimited Local)"
            elif is_free:
                tier_type = "Free Tier"
                if not reset_time:
                    try:
                        from engine.model_scanner import ModelScanner
                        p_id = model_name.split(":")[0].strip() if ":" in model_name else provider_name
                        res_info = ModelScanner.get_provider_reset_info(p_id)
                        reset_time = res_info.get("reset_time", "")
                    except Exception:
                        reset_time = "Daily at 00:00 UTC"
            else:
                tier_type = "Paid / Credits"
        self.tier_type = tier_type
        self.reset_time = reset_time

        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("modelRow")
        self._init_ui(tokens_used, is_free)

    def _init_ui(self, tokens_used: int, is_free: bool):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Left title + token details
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = ElidedLabel(self.display_name)
        active_color = "#00D1FF" if self.is_active else "#F8FAFC"
        name_lbl.setStyleSheet(f"color: {active_color}; font-size: 13px; font-weight: 600;")
        info_col.addWidget(name_lbl)

        # Subtext: Token usage & ID & Reset Info
        sub_text_parts = []
        if tokens_used > 0:
            if tokens_used >= 1000:
                sub_text_parts.append(f"Used: {tokens_used/1000:.1f}k tokens")
            else:
                sub_text_parts.append(f"Used: {tokens_used} tokens")

        if self.display_name != self.model_name:
            sub_text_parts.append(self.model_name)

        if is_free and self.tier_type != "100% Free Offline" and self.reset_time:
            sub_text_parts.append(f"Resets {self.reset_time}")

        if sub_text_parts:
            sub_lbl = ElidedLabel(" • ".join(sub_text_parts))
            sub_lbl.setStyleSheet("color: #6a748c; font-size: 11px;")
            info_col.addWidget(sub_lbl)

        layout.addLayout(info_col, 1)

        # Right badges container - Fixed width / size policy so it never shrinks or clips
        badge_container = QWidget()
        badge_container.setStyleSheet("background: transparent;")
        badge_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        badge_layout = QHBoxLayout(badge_container)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(6)
        badge_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        if self.is_active:
            active_badge = QLabel("Selected")
            active_badge.setStyleSheet("""
                background-color: rgba(0, 209, 255, 0.18);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            """)
            badge_layout.addWidget(active_badge)

        # Explicit Available vs Unavailable Indicator
        if self.is_available:
            avail_badge = QLabel("● Available")
            avail_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #10b981;
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            """)
            badge_layout.addWidget(avail_badge)
        else:
            unavail_badge = QLabel("○ Unavailable")
            unavail_badge.setStyleSheet("""
                background-color: rgba(255, 184, 77, 0.12);
                color: #ffb84d;
                border: 1px solid rgba(255, 184, 77, 0.4);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            """)
            badge_layout.addWidget(unavail_badge)

        if is_free:
            badge_lbl = "🟢 100% Free Offline (0 Rs)" if self.tier_type == "100% Free Offline" else "🟢 Free Tier (0 Rs)"
            free_badge = QLabel(badge_lbl)
            free_badge.setToolTip(f"Tier: {self.tier_type} | Limit Reset: {self.reset_time or 'Daily 00:00 UTC'} | Cost: 0 Rs Guaranteed")
            free_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #10b981;
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            """)
            badge_layout.addWidget(free_badge)

            if self.reset_time and self.tier_type != "100% Free Offline":
                reset_badge = QLabel(f"⏱ Resets {self.reset_time}")
                reset_badge.setStyleSheet("""
                    background-color: rgba(0, 209, 255, 0.12);
                    color: #00D1FF;
                    border: 1px solid rgba(0, 209, 255, 0.3);
                    border-radius: 4px;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 2px 5px;
                """)
                badge_layout.addWidget(reset_badge)
        else:
            shift_badge = QLabel("🛡️ Shifts to Free")
            shift_badge.setToolTip("Paid model (> 0 Rs). Zero-Cost Guard will automatically shift requests to a 100% Free model (0 Rs).")
            shift_badge.setStyleSheet("""
                background-color: rgba(245, 158, 11, 0.15);
                color: #f59e0b;
                border: 1px solid rgba(245, 158, 11, 0.35);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            """)
            badge_layout.addWidget(shift_badge)

        layout.addWidget(badge_container, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.setStyleSheet("""
            QFrame#modelRow {
                background-color: transparent;
                border-radius: 8px;
            }
            QFrame#modelRow:hover {
                background-color: #1a2233;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.model_name)
        super().mousePressEvent(event)


class ModelSelectorPopup(QDialog):
    """
    Searchable popover menu matching the reference design:
    - Search models bar
    - Categorized providers & models
    - Manage models footer
    """

    model_selected = Signal(str)
    manage_models_requested = Signal()
    global_ranking_requested = Signal()

    def __init__(self, current_model: str = "Auto Router", parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(520, 540)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.current_model = current_model
        self.items: List[ModelItemWidget] = []
        self.group_headers: List[QWidget] = []

        self._init_ui()
        self._load_models()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Outer Popover Card Frame
        self.card = QFrame()
        self.card.setObjectName("modelCard")
        self.card.setStyleSheet("""
            QFrame#modelCard {
                background-color: #0b101c;
                border: 1px solid rgba(0, 209, 255, 0.3);
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 12, 12, 10)
        card_layout.setSpacing(10)

        # 1. Search Box
        search_box = QFrame()
        search_box.setStyleSheet("""
            QFrame {
                background-color: #060912;
                border: 1px solid #273449;
                border-radius: 8px;
            }
            QFrame:focus-within {
                border: 1px solid #00D1FF;
            }
        """)
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(10, 6, 10, 6)
        search_layout.setSpacing(6)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("color: #6a748c; font-size: 13px;")
        search_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search models")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #F8FAFC;
                font-size: 13px;
            }
        """)
        self.search_input.textChanged.connect(self._filter_models)
        search_layout.addWidget(self.search_input, 1)

        card_layout.addWidget(search_box)

        # Zero-Cost Guard Enforcer Status Banner with Live Breathing Animation
        self.zero_cost_banner = QFrame()
        self.zero_cost_banner.setCursor(Qt.PointingHandCursor)
        self.zero_cost_banner.setToolTip("Click to view Zero-Cost Guard budget savings & model shift analytics")
        zc_layout = QHBoxLayout(self.zero_cost_banner)
        zc_layout.setContentsMargins(10, 5, 10, 5)
        zc_layout.setSpacing(8)

        self.zc_icon = QLabel("🛡️")
        self.zc_icon.setStyleSheet("font-size: 13px; background: transparent;")
        zc_layout.addWidget(self.zc_icon)

        zc_text = QLabel("Zero-Cost Guard: Active (Guaranteed ≤ 0 Rs Free)")
        zc_text.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700; background: transparent;")
        zc_layout.addWidget(zc_text, 1)

        self.zc_dot = QLabel("● 0 Rs")
        self.zc_dot.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 800; background: transparent;")
        zc_layout.addWidget(self.zc_dot)

        self.zero_cost_banner.mousePressEvent = self._on_zero_cost_banner_clicked
        card_layout.addWidget(self.zero_cost_banner)

        self._zc_pulse_step = 0.0
        self._zc_timer = QTimer(self)
        self._zc_timer.timeout.connect(self._animate_zc_banner)
        self._zc_timer.start(50)

        # Global Model Ranking Quick Action Banner
        rank_banner = QPushButton("📊 View Global Model Ranking (All 54 Models) ➔")
        rank_banner.setCursor(Qt.PointingHandCursor)
        rank_banner.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.08);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 700;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.18);
                border-color: #00D1FF;
            }
        """)
        rank_banner.clicked.connect(self._on_global_ranking_clicked)
        card_layout.addWidget(rank_banner)

        # 2. Scrollable Model List
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 7px;
                margin: 2px 2px 2px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 209, 255, 0.25);
                border-radius: 3px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00D1FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(4, 4, 16, 4)
        self.list_layout.setSpacing(4)
        self.scroll.setWidget(self.list_container)

        card_layout.addWidget(self.scroll, 1)

        # 3. Bottom Sticky Action Bar: '⚙ Manage models'
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: #273449; max-height: 1px;")
        card_layout.addWidget(div)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(6, 4, 10, 4)
        footer_layout.setSpacing(8)

        manage_btn = QPushButton("✨  Add / Connect AI Models")
        manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.setToolTip("Add free models (Gemini, Groq), cloud keys, or local Ollama")
        manage_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #00D1FF;
                border: none;
                font-size: 12px;
                font-weight: 700;
                padding: 5px 8px;
                text-align: left;
            }
            QPushButton:hover {
                color: #00BBE6;
            }
        """)
        manage_btn.clicked.connect(self._on_manage_clicked)
        footer_layout.addWidget(manage_btn)

        footer_layout.addStretch()

        self.ollama_footer_btn = QPushButton("🚀 Start Ollama")
        self.ollama_footer_btn.setCursor(Qt.PointingHandCursor)
        self.ollama_footer_btn.setToolTip("Start local Ollama background server")
        self.ollama_footer_btn.setStyleSheet("""
            QPushButton {
                background: rgba(15, 230, 181, 0.1);
                color: #0FE6B5;
                border: 1px solid rgba(15, 230, 181, 0.3);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(15, 230, 181, 0.22);
                border-color: #0FE6B5;
            }
        """)
        self.ollama_footer_btn.clicked.connect(self._on_start_ollama_clicked)
        if not is_ollama_running():
            footer_layout.addWidget(self.ollama_footer_btn)

        rescan_btn = QPushButton("🔄  Scan")
        rescan_btn.setCursor(Qt.PointingHandCursor)
        rescan_btn.setToolTip("Scan API keys for newly available models")
        rescan_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.04);
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
            }
        """)
        rescan_btn.clicked.connect(self._on_rescan_clicked)
        footer_layout.addWidget(rescan_btn)

        card_layout.addLayout(footer_layout)
        root_layout.addWidget(self.card)

    def _is_model_active(self, provider_id: str, model_name: str) -> bool:
        """Determines if a model matches the currently selected model string."""
        cur = (self.current_model or "").lower().strip()
        if not cur or cur == "auto router" or "auto" in cur:
            return False
        if any(k in cur for k in ("picture", "flux", "diffusion")) and any(k in (model_name + provider_id).lower() for k in ("picture", "flux", "diffusion")):
            return True
        full_id = f"{provider_id}: {model_name}".lower()
        if cur == full_id or cur == model_name.lower():
            return True
        if model_name.lower() in cur or cur in model_name.lower():
            return True
        return False

    def _load_models(self):
        # Clear existing items
        for i in reversed(range(self.list_layout.count())):
            w = self.list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        self.items.clear()
        self.group_headers.clear()

        is_auto_active = ("auto" in (self.current_model or "auto router").lower())
        is_picture_active = any(k in (self.current_model or "").lower() for k in ("picture", "flux", "diffusion"))
        categorized = ModelScanner.get_categorized_models(free_only=True)
        active_model_info = None

        # 1. If a specific model is selected (not Auto Router), place it at the VERY TOP!
        if is_picture_active:
            cur_header = QLabel("📌  CURRENTLY SELECTED")
            cur_header.setStyleSheet("color: #00D1FF; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; margin-top: 4px; margin-bottom: 2px; margin-left: 6px;")
            self.list_layout.addWidget(cur_header)
            self.group_headers.append(cur_header)

            top_item = ModelItemWidget(
                model_name="image: Black Forest FLUX.1",
                display_name="🎨 Create Picture (Black Forest FLUX.1)",
                provider_name="Image Studio",
                tokens_used=0,
                is_free=True,
                is_active=True,
                is_available=ModelScanner.is_provider_available("openrouter") or ModelScanner.is_provider_available("huggingface")
            )
            top_item.clicked.connect(self._select_model)
            self.list_layout.addWidget(top_item)
            self.items.append(top_item)

            div = QFrame()
            div.setFrameShape(QFrame.HLine)
            div.setStyleSheet("background-color: rgba(0, 209, 255, 0.2); max-height: 1px; margin: 6px 0;")
            self.list_layout.addWidget(div)
            self.group_headers.append(div)
        elif not is_auto_active and self.current_model:
            active_model_info = None
            for group_name, models in categorized.items():
                for m in models:
                    if self._is_model_active(m.get("provider_id", ""), m.get("model_name", "")):
                        active_model_info = (group_name, m)
                        break
                if active_model_info:
                    break

            if active_model_info:
                group_name, m = active_model_info
                cur_header = QLabel("📌  CURRENTLY SELECTED MODEL")
                cur_header.setStyleSheet("color: #00D1FF; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; margin-top: 4px; margin-bottom: 2px; margin-left: 6px;")
                self.list_layout.addWidget(cur_header)
                self.group_headers.append(cur_header)

                top_item = ModelItemWidget(
                    model_name=f"{m['provider_id']}: {m['model_name']}",
                    display_name=m["display_name"],
                    provider_name=group_name,
                    tokens_used=m.get("tokens_used", 0),
                    is_free=True,
                    is_active=True,
                    is_available=ModelScanner.is_provider_available(m.get("provider_id", ""))
                )
                top_item.clicked.connect(self._select_model)
                self.list_layout.addWidget(top_item)
                self.items.append(top_item)

                div = QFrame()
                div.setFrameShape(QFrame.HLine)
                div.setStyleSheet("background-color: rgba(0, 209, 255, 0.2); max-height: 1px; margin: 6px 0;")
                self.list_layout.addWidget(div)
                self.group_headers.append(div)

        # 2. Add Auto Router
        auto_item = ModelItemWidget(
            model_name="Auto Router",
            display_name="⚡ Auto Router (Intelligent Waterfall)",
            provider_name="System",
            tokens_used=0,
            is_free=True,
            is_active=is_auto_active,
            is_available=ModelScanner.is_provider_available("auto")
        )
        auto_item.clicked.connect(self._select_model)
        self.list_layout.addWidget(auto_item)
        self.items.append(auto_item)

        # 3. Add Dedicated Picture Generator Option (if not already pinned at top)
        if not is_picture_active:
            pic_avail = ModelScanner.is_provider_available("openrouter") or ModelScanner.is_provider_available("huggingface")
            pic_item = ModelItemWidget(
                model_name="image: Black Forest FLUX.1",
                display_name="🎨 Create Picture (Black Forest FLUX.1)",
                provider_name="Image Studio",
                tokens_used=0,
                is_free=True,
                is_active=False,
                is_available=pic_avail
            )
            pic_item.clicked.connect(self._select_model)
            self.list_layout.addWidget(pic_item)
            self.items.append(pic_item)

        # 4. Add 100% Free Models Indicator Banner
        free_notice = QFrame()
        free_notice.setStyleSheet("""
            QFrame {
                background-color: rgba(16, 185, 129, 0.08);
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 6px;
                padding: 4px;
            }
        """)
        fn_layout = QHBoxLayout(free_notice)
        fn_layout.setContentsMargins(8, 4, 8, 4)
        fn_lbl = QLabel("✨ <b>Showing 100% Free AI Models Only</b> (Cloud Free-Tier & Local)")
        fn_lbl.setStyleSheet("color: #10b981; font-size: 11px; border: none; background: transparent;")
        fn_layout.addWidget(fn_lbl)
        self.list_layout.addWidget(free_notice)

        # 4. Add Quota Summary Card if available
        quotas = get_db().get_all_provider_quotas()
        if quotas:
            quota_banner = self._create_quota_banner(quotas)
            self.list_layout.addWidget(quota_banner)

        # 5. Categorized Models - strictly free only
        for group_name, models in categorized.items():
            free_models = [m for m in models if m.get("is_free", False)]
            if not free_models:
                continue

            # Group header label with explicit Tier and Reset schedule
            prov_key = group_name.lower().replace(" ", "_")
            if "ollama" in prov_key:
                header_text = f"{group_name} • 100% Free Offline (Unlimited Local)"
            else:
                res_info = ModelScanner.get_provider_reset_info(prov_key)
                header_text = f"{group_name} • Free Tier (Resets {res_info.get('reset_time', '00:00 UTC')})"

            header = QLabel(header_text)
            header.setStyleSheet("color: #4f80ff; font-size: 11px; font-weight: 700; margin-top: 8px; margin-bottom: 2px; margin-left: 6px;")
            self.list_layout.addWidget(header)
            self.group_headers.append(header)

            for m in free_models:
                m_name = m["model_name"]
                prov_id = m.get("provider_id", "")
                is_active = self._is_model_active(prov_id, m_name)
                # If already pinned at top, skip duplicate in category list
                if active_model_info and is_active:
                    continue
                item = ModelItemWidget(
                    model_name=f"{prov_id}: {m_name}",
                    display_name=m["display_name"],
                    provider_name=group_name,
                    tokens_used=m.get("tokens_used", 0),
                    is_free=True,
                    is_active=is_active,
                    is_available=ModelScanner.is_provider_available(prov_id),
                    tier_type=m.get("tier_type", ""),
                    reset_time=m.get("reset_time", "")
                )
                item.clicked.connect(self._select_model)
                self.list_layout.addWidget(item)
                self.items.append(item)

        self.list_layout.addStretch()

    def _create_quota_banner(self, quotas: Dict[str, Any]) -> QWidget:
        """Shows quick token balance summary chip and dynamic limit reset time."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 209, 255, 0.05);
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 6px;
                padding: 4px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        res_info = ModelScanner.get_provider_reset_info("gemini")
        reset_time_str = res_info.get("reset_time", "00:00 UTC")

        parts = []
        if "gemini" in quotas:
            rem = quotas["gemini"].get("remaining_amount", 1500)
            parts.append(f"Gemini: {int(rem)}/day")
        if "groq" in quotas:
            rem = quotas["groq"].get("remaining_amount", 14400)
            parts.append(f"Groq: {int(rem):,}/day")
        if "nvidia" in quotas:
            rem = quotas["nvidia"].get("remaining_amount", 1000.0)
            parts.append(f"NVIDIA: {int(rem)} free credits")
        if "openrouter" in quotas:
            rem = quotas["openrouter"].get("remaining_amount", 0.0)
            if rem > 0:
                parts.append(f"OpenRouter: ${rem:.2f}")

        lbl_text = " • ".join(parts) if parts else "Free Tier Cloud & Local Models Connected"
        lbl = QLabel(f"💳  {lbl_text}")
        lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600;")
        layout.addWidget(lbl)

        reset_lbl = QLabel(f"⏱  <b>Free Tier Limits Reset:</b> {reset_time_str}")
        reset_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 500;")
        layout.addWidget(reset_lbl)
        return frame

    def _filter_models(self, query: str):
        query = query.strip().lower()
        for item in self.items:
            match = (
                not query
                or query in item.display_name.lower()
                or query in item.model_name.lower()
                or query in item.provider_name.lower()
            )
            item.setVisible(match)

        # Hide empty headers
        for h in self.group_headers:
            h.setVisible(not query)

    def _select_model(self, model_identifier: str):
        self.model_selected.emit(model_identifier)
        self.accept()

    def _on_manage_clicked(self):
        self.manage_models_requested.emit()
        self.accept()

    def _on_global_ranking_clicked(self):
        self.global_ranking_requested.emit()
        self.accept()

    def _on_rescan_clicked(self):
        ModelScanner.scan_all_configured()
        self._load_models()

    def _on_start_ollama_clicked(self):
        if hasattr(self, "ollama_footer_btn"):
            self.ollama_footer_btn.setText("⏳ Starting...")
            self.ollama_footer_btn.setEnabled(False)
            self.ollama_footer_btn.repaint()
        import threading
        def _bg_start():
            start_ollama_service()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._after_ollama_started())
        threading.Thread(target=_bg_start, daemon=True).start()

    def _after_ollama_started(self):
        ModelScanner.scan_all_configured()
        self._load_models()
        if hasattr(self, "ollama_footer_btn"):
            if is_ollama_running():
                self.ollama_footer_btn.setText("✅ Ollama Active")
                self.ollama_footer_btn.setEnabled(False)
            else:
                self.ollama_footer_btn.setText("🚀 Start Ollama")
                self.ollama_footer_btn.setEnabled(True)

    def show_anchored(self, anchor_widget: QWidget):
        """Positions the popup right above or below the anchor widget, clamped to screen bounds."""
        point = anchor_widget.mapToGlobal(QPoint(0, 0))
        popup_x = point.x() + (anchor_widget.width() - self.width()) // 2
        popup_y = point.y() - self.height() - 8
        if popup_y < 50:
            popup_y = point.y() + anchor_widget.height() + 8

        screen = anchor_widget.screen() or QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            popup_x = max(geo.left() + 10, min(popup_x, geo.right() - self.width() - 10))
            if popup_y + self.height() > geo.bottom() - 10 and popup_y > geo.top() + 50:
                popup_y = max(geo.top() + 10, point.y() - self.height() - 8)

        self.move(popup_x, popup_y)
        self.show()
        self.search_input.setFocus()

    def _animate_zc_banner(self):
        """Animates a smooth breathing neon-emerald glow for the Zero-Cost Guard indicator banner."""
        self._zc_pulse_step = getattr(self, "_zc_pulse_step", 0.0) + 0.08
        glow_alpha = 0.10 + 0.12 * (0.5 * (1 + math.sin(self._zc_pulse_step)))
        border_alpha = 0.28 + 0.35 * (0.5 * (1 + math.sin(self._zc_pulse_step)))
        beacon_alpha = 0.40 + 0.60 * (0.5 * (1 + math.sin(self._zc_pulse_step)))

        self.zero_cost_banner.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, {glow_alpha:.3f}),
                    stop:1 rgba(15, 230, 181, {glow_alpha * 0.5:.3f}));
                border: 1px solid rgba(16, 185, 129, {border_alpha:.3f});
                border-radius: 8px;
            }}
            QFrame:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.28),
                    stop:1 rgba(15, 230, 181, 0.15));
                border-color: #10b981;
            }}
        """)
        if hasattr(self, "zc_dot"):
            self.zc_dot.setStyleSheet(f"color: rgba(16, 185, 129, {beacon_alpha:.2f}); font-size: 10px; font-weight: 800; background: transparent;")

    def _on_zero_cost_banner_clicked(self, event=None):
        try:
            from ui.components.zero_cost_dialog import ZeroCostGuardDialog
            dlg = ZeroCostGuardDialog(parent=self.parent())
            dlg.exec()
        except Exception:
            pass

    def showEvent(self, event):
        if hasattr(self, "_zc_timer") and not self._zc_timer.isActive():
            self._zc_timer.start(50)
        super().showEvent(event)

    def hideEvent(self, event):
        if hasattr(self, "_zc_timer") and self._zc_timer.isActive():
            self._zc_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "_zc_timer") and self._zc_timer.isActive():
            self._zc_timer.stop()
        super().closeEvent(event)
