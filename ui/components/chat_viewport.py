"""
Chat Viewport Component for Sage AI.
Matches the reference design:
- Planetary space horizon background with radiant emerald glow
- Centered floating Sage logo
- Dynamic greeting: 'Good evening, Suraj.' with neon emerald highlight
- 4 Horizontal action cards with custom badges and arrow buttons
- Auto-scrolling chat message stream
"""
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QTimer, QPointF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QPainter, QRadialGradient, QColor, QPen, QPainterPath

from .message_bubble import MessageBubble
from .live_working_panel import LiveWorkingPanel


class PlanetaryBackgroundWidget(QWidget):
    """Clean dark background matching SAGE AI cyber-slate palette."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.primary_color = QColor("#00D1FF")
        self.bg_space = QColor("#0A0F14")

    def apply_theme(self, pal: Dict[str, Any]):
        """Dynamically updates the background color."""
        self.primary_color = QColor(pal.get("primary", "#00D1FF"))
        self.bg_space = QColor(pal.get("bg_main", "#0A0F14"))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg_space)


class ModernActionCard(QFrame):
    """Action starter card matching SAGE section photo design."""

    clicked = Signal(str)

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        prompt_text: str,
        parent=None
    ):
        super().__init__(parent)
        self.prompt_text = prompt_text
        self.setObjectName("modernActionCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(150)

        self.setStyleSheet("""
            QFrame#modernActionCard {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 14px;
            }
            QFrame#modernActionCard:hover {
                background-color: #162033;
                border: 1px solid #00D1FF;
            }
            QLabel#cardIconBadge {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid #273449;
                border-radius: 8px;
                font-size: 16px;
            }
            QLabel#cardMainTitle {
                color: #F8FAFC;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#cardMainDesc {
                color: #94A3B8;
                font-size: 12px;
                line-height: 1.3;
            }
            QPushButton#cardArrowBtn {
                background-color: #162033;
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#cardArrowBtn:hover {
                background-color: #00D1FF;
                color: #0A0F14;
                border-color: #00D1FF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Icon Badge
        badge_lbl = QLabel(icon)
        badge_lbl.setObjectName("cardIconBadge")
        badge_lbl.setAlignment(Qt.AlignCenter)
        badge_lbl.setFixedSize(32, 32)
        layout.addWidget(badge_lbl)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setObjectName("cardMainTitle")
        layout.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("cardMainDesc")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl, 1)

        # Bottom Arrow Button Row
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        arrow_btn = QPushButton("›")
        arrow_btn.setObjectName("cardArrowBtn")
        arrow_btn.setFixedSize(24, 24)
        arrow_btn.setCursor(Qt.PointingHandCursor)
        arrow_btn.clicked.connect(lambda: self.clicked.emit(self.prompt_text))
        bottom_row.addWidget(arrow_btn)

        layout.addLayout(bottom_row)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.prompt_text)
        super().mousePressEvent(event)


class ChatViewport(QWidget):
    """Main chat viewport with clean background, hero greeting, and action cards."""

    starter_card_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatViewport")

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Clean Background Canvas
        self.canvas = PlanetaryBackgroundWidget(self)
        canvas_layout = QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("chatScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea#chatScrollArea { background: transparent; border: none; }")
        self.scroll_area.viewport().setAutoFillBackground(False)
        self.scroll_area.viewport().setStyleSheet("background: transparent;")

        self.container = QWidget()
        self.container.setObjectName("chatContentContainer")
        self.container.setAutoFillBackground(False)
        self.container.setStyleSheet("QWidget#chatContentContainer { background: transparent; }")
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(36, 16, 36, 16)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignTop)

        # Empty State Hero Widget
        self.empty_state_widget = self._create_empty_state()
        self.content_layout.addWidget(self.empty_state_widget)

        # Live Working Panel
        self.working_panel = LiveWorkingPanel()
        self.content_layout.addWidget(self.working_panel)

        self.scroll_area.setWidget(self.container)
        canvas_layout.addWidget(self.scroll_area)
        root_layout.addWidget(self.canvas)

    def _get_time_greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        elif hour < 17:
            return "Good afternoon"
        else:
            return "Good evening"

    def _create_empty_state(self) -> QWidget:
        widget = QWidget()
        widget.setAutoFillBackground(False)
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignCenter)

        # 1. Hero Banner Card (matches section photo)
        hero_card = QFrame()
        hero_card.setObjectName("heroBannerCard")
        hero_card.setStyleSheet("""
            QFrame#heroBannerCard {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 16px;
            }
        """)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(28, 22, 28, 22)
        hero_layout.setSpacing(20)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(6)

        time_greeting = self._get_time_greeting()
        user_name = self._get_display_name()
        self.greeting_title = QLabel(f"{time_greeting}, <span style='color: #00D1FF;'>{user_name}.</span>")
        self.greeting_title.setObjectName("greetingTitle")
        self.greeting_title.setTextFormat(Qt.RichText)
        self.greeting_title.setStyleSheet("font-size: 26px; font-weight: 800; color: #F8FAFC; background: transparent; border: none;")
        hero_text_col.addWidget(self.greeting_title)

        motto_lbl = QLabel("Think. Create. Automate. With Sage AI.")
        motto_lbl.setStyleSheet("color: #94A3B8; font-size: 14px; font-weight: 500; background: transparent; border: none;")
        hero_text_col.addWidget(motto_lbl)

        hero_layout.addLayout(hero_text_col, 1)

        # Hero Right: Badge with glowing crystal logo
        badge_box = QHBoxLayout()
        badge_box.setSpacing(12)
        badge_box.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        badge_text = QVBoxLayout()
        badge_text.setSpacing(2)
        badge_text.setAlignment(Qt.AlignRight)

        t1 = QLabel("Ideas\ntoday.")
        t1.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic; background: transparent; border: none; text-align: right;")
        t1.setAlignment(Qt.AlignRight)
        badge_text.addWidget(t1)

        t2 = QLabel("A smarter\ntomorrow.")
        t2.setStyleSheet("color: #CBD5E1; font-size: 11px; font-weight: 600; background: transparent; border: none; text-align: right;")
        t2.setAlignment(Qt.AlignRight)
        badge_text.addWidget(t2)
        badge_box.addLayout(badge_text)

        hero_logo_col = QVBoxLayout()
        hero_logo_col.setAlignment(Qt.AlignCenter)
        hero_logo_col.setSpacing(2)

        self.hero_logo_lbl = QLabel()
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.hero_logo_lbl.setPixmap(pix)
        self.hero_logo_lbl.setStyleSheet("background: transparent; border: none;")
        hero_logo_col.addWidget(self.hero_logo_lbl, 0, Qt.AlignCenter)

        sage_txt = QLabel("SAGE AI")
        sage_txt.setStyleSheet("color: #00D1FF; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; background: transparent; border: none;")
        hero_logo_col.addWidget(sage_txt, 0, Qt.AlignCenter)

        badge_box.addLayout(hero_logo_col)
        hero_layout.addLayout(badge_box)

        layout.addWidget(hero_card)

        # 2. 4 Action Cards Row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        cards_data = [
            ("💬", "Start a Chat", "Get intelligent\nanswers and ideas.",
             "Hello Sage, let's explore high-impact ideas and analyze a project plan."),
            ("🖼", "Generate Image", "Create stunning\nimages from text.",
             "Generate an image of a futuristic neon cybernetic city in rain."),
            ("</>", "Write Code", "Build, debug and\nimprove faster.",
             "Write a production-ready Python async task queue with priority scheduling and error retries."),
            ("⚙", "Automate Tasks", "Let AI agents handle\nrepetitive work.",
             "Help me architect an autonomous workflow automation pipeline in Python.")
        ]

        for icon, title, desc, prompt in cards_data:
            card = ModernActionCard(icon, title, desc, prompt)
            card.clicked.connect(self.starter_card_clicked.emit)
            cards_row.addWidget(card, 1)

        layout.addLayout(cards_row)

        # 3. Suggestions box matching section photo
        suggest_box = QFrame()
        suggest_box.setObjectName("suggestBox")
        suggest_box.setStyleSheet("""
            QFrame#suggestBox {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 14px;
            }
        """)
        s_layout = QVBoxLayout(suggest_box)
        s_layout.setContentsMargins(20, 16, 20, 16)
        s_layout.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)
        spk = QLabel("✦")
        spk.setStyleSheet("color: #00D1FF; font-size: 15px; font-weight: bold; background: transparent;")
        hdr_row.addWidget(spk)

        q_lbl = QLabel("How can I help you today?")
        q_lbl.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 700; background: transparent;")
        hdr_row.addWidget(q_lbl)
        hdr_row.addStretch()
        s_layout.addLayout(hdr_row)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(10)

        chips = [
            ("≡ Summarize a PDF", "Summarize this PDF document and extract the 5 most critical insights."),
            ("🖼 Generate an image", "Generate an image of a futuristic hyper-detailed cybernetic wolf in neon forest."),
            ("</> Write a Python script", "Write a Python script that parses CSV data, validates schemas, and generates a summary chart."),
            ("📅 Plan a travel itinerary", "Plan a comprehensive 5-day travel itinerary with daily schedules, attractions, and budget recommendations."),
        ]

        for chip_text, prompt in chips:
            btn = QPushButton(chip_text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #162033;
                    color: #CBD5E1;
                    border: 1px solid #273449;
                    border-radius: 14px;
                    padding: 8px 14px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1e2b42;
                    color: #00D1FF;
                    border-color: #00D1FF;
                }
            """)
            btn.clicked.connect(lambda checked=False, p=prompt: self.starter_card_clicked.emit(p))
            chips_row.addWidget(btn)

        chips_row.addStretch()
        s_layout.addLayout(chips_row)
        layout.addWidget(suggest_box)

        return widget

    def set_empty_state_visible(self, visible: bool):
        self.empty_state_widget.setVisible(visible)

    def clear_messages(self):
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            w = item.widget()
            if w and w not in (self.empty_state_widget, self.working_panel):
                w.deleteLater()
        self.set_empty_state_visible(True)

    def create_streaming_message(
        self,
        role: str = "assistant",
        model: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> MessageBubble:
        """Creates and inserts a live streaming message bubble."""
        self.set_empty_state_visible(False)
        now_ts = timestamp or datetime.now().isoformat()
        bubble = MessageBubble(
            role=role,
            content="",
            model=model,
            timestamp=now_ts
        )

        idx = self.content_layout.indexOf(self.working_panel)
        if idx >= 0:
            self.content_layout.insertWidget(idx, bubble)
        else:
            self.content_layout.addWidget(bubble)

        self._animate_bubble_entrance(bubble)
        self.scroll_to_bottom(smooth=True, force=True)
        return bubble

    def add_message(
        self,
        role: str,
        content: str,
        model: Optional[str] = None,
        timestamp: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        is_image: bool = False,
        image_data: Optional[str] = None,
        latency_ms: Optional[float] = None,
        thinking: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        username: Optional[str] = None,
        telemetry: Optional[Dict[str, Any]] = None
    ) -> MessageBubble:
        self.set_empty_state_visible(False)

        bubble = MessageBubble(
            role=role,
            content=content,
            model=model,
            timestamp=timestamp,
            citations=citations,
            is_image=is_image,
            image_data=image_data,
            latency_ms=latency_ms,
            thinking=thinking,
            attachments=attachments,
            username=username,
            telemetry=telemetry
        )

        idx = self.content_layout.indexOf(self.working_panel)
        if idx >= 0:
            self.content_layout.insertWidget(idx, bubble)
        else:
            self.content_layout.addWidget(bubble)

        self._animate_bubble_entrance(bubble)
        self.scroll_to_bottom(smooth=True, force=True)
        return bubble

    def _animate_bubble_entrance(self, bubble: QWidget):
        """Ultra-fast, zero-lag message entrance preserving native subpixel text clarity."""
        bubble.show()

    def scroll_to_bottom(self, smooth: bool = True, force: bool = False):
        """
        Scrolls viewport to bottom.
        If user has scrolled up to inspect previous responses (> 160px), does not forcibly hijack view unless force=True.
        """
        def _do_scroll():
            try:
                if hasattr(self, "scroll_area") and self.scroll_area:
                    bar = self.scroll_area.verticalScrollBar()
                    if bar:
                        target = bar.maximum()
                        current = bar.value()
                        # Protect user reading position if scrolled up
                        if not force and (target - current > 160):
                            return

                        if not smooth:
                            bar.setValue(target)
                        else:
                            from ui.components.animation_system import smooth_scroll_to
                            smooth_scroll_to(self.scroll_area, target, duration=140)
            except Exception:
                pass
        QTimer.singleShot(15, _do_scroll)

    def show_working_stage(self, stage_text: str):
        self.working_panel.set_stage(stage_text)
        self.scroll_to_bottom()

    def hide_working_stage(self):
        self.working_panel.stop()

    def _get_display_name(self) -> str:
        """Retrieves user first name from database or OS system account."""
        try:
            from database.db_manager import get_db
            name = get_db().get_setting("user_display_name")
            if name and name.strip():
                return name.strip().split()[0]
        except Exception:
            pass
        import getpass, os
        try:
            return getpass.getuser().capitalize()
        except Exception:
            return os.getenv("USERNAME") or os.getenv("USER") or "Explorer"

    def update_user_name(self, name: Optional[str] = None):
        """Dynamically updates the hero greeting when user changes their name in Settings."""
        if name and name.strip():
            first_name = name.strip().split()[0]
        else:
            first_name = self._get_display_name()
        color = getattr(self, "_current_primary", "#00D1FF")
        if hasattr(self, "greeting_title") and self.greeting_title:
            self.greeting_title.setText(
                f"{self._get_time_greeting()}, <span style='color: {color};'>{first_name}.</span>"
            )

    def apply_theme(self, pal: Dict[str, Any]):
        """Update canvas background and hero logo/greeting to match current theme."""
        from ui.styles.qss_theme import get_tinted_logo
        primary = pal.get("primary", "#00D1FF")
        self._current_primary = primary
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.apply_theme(pal)
        if hasattr(self, "hero_logo_lbl") and self.hero_logo_lbl:
            self.hero_logo_lbl.setPixmap(get_tinted_logo(primary, 84))
        if hasattr(self, "greeting_title") and self.greeting_title:
            user_name = self._get_display_name()
            self.greeting_title.setText(
                f"{self._get_time_greeting()}, <span style='color: {primary};'>{user_name}.</span>"
            )

    def _update_container_margins(self):
        """Maintains clean centered reading column aligned with input capsule."""
        vp_w = self.scroll_area.viewport().width() if hasattr(self, "scroll_area") and self.scroll_area else self.width()
        margin = max(32, int((vp_w - 920) / 2))
        self.content_layout.setContentsMargins(margin, 16, margin, 16)

    def _refresh_all_bubbles_height(self):
        """Recalculates full rendered height for all message bubbles so text never shrinks."""
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if item:
                w = item.widget()
                if isinstance(w, MessageBubble):
                    w._adjust_browser_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_container_margins()
        self._refresh_all_bubbles_height()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_container_margins()
        QTimer.singleShot(40, self._refresh_all_bubbles_height)
        QTimer.singleShot(120, self._refresh_all_bubbles_height)

