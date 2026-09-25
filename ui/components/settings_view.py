"""
Settings View Component for Sage AI.
In-window settings page (replaces popup dialog) providing:
- Profile & AI Persona Configuration
- Theme Select & Font Scaling
- Seamless 'Back to Chat' navigation within the same window
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QFrame, QScrollArea,
    QGridLayout, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer

from database.db_manager import get_db
from .analytics_view import AnalyticsView


class SettingsView(QWidget):
    """Integrated in-window settings page with Profile and Model Usage & Analytics."""

    profile_updated = Signal(str, str)
    back_to_chat_requested = Signal()
    request_add_models = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = get_db()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Bar with 'Back to Chat'
        header = QHBoxLayout()
        header.setSpacing(14)

        back_btn = QPushButton("← Back to Chat")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
                border-color: #00D1FF;
            }
        """)
        back_btn.clicked.connect(self.back_to_chat_requested.emit)
        header.addWidget(back_btn)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("⚙️ Application Settings")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 18px; font-weight: 800; letter-spacing: 0.3px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Personalize your profile, AI assistant persona, and workspace configuration")
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()
        main_layout.addLayout(header)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("inWindowSettingsTabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #273449;
                background-color: #111827;
                border-radius: 12px;
                padding: 16px;
            }
            QTabBar::tab {
                background-color: #162033;
                color: #94A3B8;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 22px;
                margin-right: 4px;
                font-size: 13px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #111827;
                color: #00D1FF;
                border-color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
                font-weight: 700;
            }
        """)

        # Tab 0: Profile & Persona
        self.tabs.addTab(self._create_profile_tab(), "👤  Profile && Persona")

        # Tab 1: Model Usage & Analytics
        self.analytics_view = AnalyticsView(parent=self)
        self.analytics_view.back_to_chat_requested.connect(self.back_to_chat_requested.emit)
        self.analytics_view.request_add_models.connect(self.request_add_models.emit)
        self.tabs.addTab(self.analytics_view, "📊  Model Usage && Analytics")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs, 1)

    def _on_tab_changed(self, index: int):
        """Automatically refreshes live model token metrics when switching to Model Usage tab."""
        if index == 1 and hasattr(self, "analytics_view") and self.analytics_view:
            self.analytics_view.refresh_data()

    def refresh_usage(self):
        """Forces a refresh of model token usage and chart analytics."""
        if hasattr(self, "analytics_view") and self.analytics_view:
            self.analytics_view.refresh_data()

    # --- Profile Tab ---
    def _create_profile_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        tab = QWidget()
        scroll.setWidget(tab)
        scroll.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(18)

        # Avatar Preview Card
        avatar_card = QFrame()
        avatar_card.setObjectName("avatarCard")
        avatar_card.setStyleSheet("""
            QFrame#avatarCard {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        ac_layout = QHBoxLayout(avatar_card)
        ac_layout.setContentsMargins(20, 16, 20, 16)
        curr_name = self.db.get_setting("user_display_name", "")
        curr_email = self.db.get_setting("user_email", "")
        initials = "".join([part[0].upper() for part in (curr_name.strip().split() if curr_name else [])])[:2] or "U"
        self.preview_avatar = QLabel(initials)
        self.preview_avatar.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D1FF, stop:1 #008bb3);
                color: #0A0F14;
                font-weight: 900;
                font-size: 22px;
                border-radius: 30px;
                border: none;
                qproperty-alignment: AlignCenter;
            }
        """)
        self.preview_avatar.setFixedSize(60, 60)
        ac_layout.addWidget(self.preview_avatar)

        ac_info = QVBoxLayout()
        ac_info.setSpacing(4)

        self.preview_name_lbl = QLabel(curr_name or "Your Name")
        self.preview_name_lbl.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 700; border: none; background: transparent;")
        ac_info.addWidget(self.preview_name_lbl)

        self.preview_email_lbl = QLabel(curr_email or "your.email@example.com")
        self.preview_email_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; border: none; background: transparent;")
        ac_info.addWidget(self.preview_email_lbl)

        status_lbl = QLabel("● Online • SAGE AI Connected")
        status_lbl.setStyleSheet("color: #22C55E; font-size: 11px; border: none; background: transparent;")
        ac_info.addWidget(status_lbl)
        ac_layout.addLayout(ac_info, 1)

        layout.addWidget(avatar_card)

        # Form Inputs
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(16)
        form_grid.setVerticalSpacing(14)

        # Name
        name_title = QLabel("Full Display Name")
        name_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(name_title, 0, 0)

        curr_name = self.db.get_setting("user_display_name", "")
        self.name_edit = QLineEdit(curr_name)
        self.name_edit.setPlaceholderText("Enter your name")
        self.name_edit.setStyleSheet(self._input_style())
        self.name_edit.textChanged.connect(self._on_name_text_changed)
        form_grid.addWidget(self.name_edit, 1, 0)

        # Email
        email_title = QLabel("Email Address")
        email_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(email_title, 0, 1)

        curr_email = self.db.get_setting("user_email", "")
        self.email_edit = QLineEdit(curr_email)
        self.email_edit.setPlaceholderText("Enter your email")
        self.email_edit.setStyleSheet(self._input_style())
        self.email_edit.textChanged.connect(self._on_email_text_changed)
        form_grid.addWidget(self.email_edit, 1, 1)

        # Role
        role_title = QLabel("Developer Role / Bio")
        role_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(role_title, 2, 0)

        curr_role = self.db.get_setting("user_role", "")
        self.role_edit = QLineEdit(curr_role)
        self.role_edit.setPlaceholderText("e.g. Senior Software Engineer, Student")
        self.role_edit.setStyleSheet(self._input_style())
        form_grid.addWidget(self.role_edit, 3, 0)

        # AI Persona
        persona_title = QLabel("Preferred AI Assistant Persona")
        persona_title.setStyleSheet("color: #a0a8be; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(persona_title, 2, 1)

        self.persona_combo = QComboBox()
        self.persona_combo.addItems([
            "🌟 Friendly & Simple (Easy to understand, beginner-friendly)",
            "⚡ Code Architect (Clean, optimal, typed code)",
            "💡 Smart & Concise (Short, fast, direct answers)",
            "🔬 Deep Research (Comprehensive explanations & theory)",
            "🎨 Creative Assistant (Brainstorming & exploration)"
        ])
        curr_persona = self.db.get_setting("user_persona_idx", "0")
        try:
            self.persona_combo.setCurrentIndex(int(curr_persona))
        except Exception:
            pass
        self.persona_combo.setStyleSheet(self._combo_style())
        form_grid.addWidget(self.persona_combo, 3, 1)

        layout.addLayout(form_grid)

        # Motion & Performance Profile Section
        from ui.components.animation_system import get_anim_manager, PerformanceTier
        mgr = get_anim_manager()
        tier_card = QFrame()
        tier_card.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        tc_layout = QVBoxLayout(tier_card)
        tc_layout.setSpacing(6)
        tier_lbl = QLabel("⚡ Motion & Performance Engine Profile")
        tier_lbl.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700;")
        tc_layout.addWidget(tier_lbl)

        tier_combo = QComboBox()
        tier_combo.setStyleSheet(self._combo_style())
        tier_combo.addItem("🚀 High Performance (60 FPS, all glow conduits & micro-interactions)", PerformanceTier.HIGH.value)
        tier_combo.addItem("✨ Normal (Balanced smooth transitions & streaming feedback)", PerformanceTier.NORMAL.value)
        tier_combo.addItem("🔋 Low Performance (Power saver, disables continuous animation loops)", PerformanceTier.LOW.value)
        tier_combo.addItem("♿ Reduced Motion (Accessibility, disables large movements & scaling)", PerformanceTier.REDUCED_MOTION.value)

        curr_val = mgr.current_tier.value
        idx = tier_combo.findData(curr_val)
        if idx >= 0:
            tier_combo.setCurrentIndex(idx)
        tier_combo.currentIndexChanged.connect(lambda: mgr.set_tier(PerformanceTier(tier_combo.currentData())))
        tc_layout.addWidget(tier_combo)
        layout.addWidget(tier_card)

        layout.addStretch()

        # Save Button Row
        action_row = QHBoxLayout()
        self.profile_status = QLabel("")
        self.profile_status.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        action_row.addWidget(self.profile_status)
        action_row.addStretch()

        save_btn = QPushButton("✓  Save Profile Changes")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 800;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        save_btn.clicked.connect(self._save_profile)
        action_row.addWidget(save_btn)

        layout.addLayout(action_row)

        return scroll

    def _on_name_text_changed(self, text: str):
        self.preview_name_lbl.setText(text or "Your Name")
        parts = text.strip().split()
        initials = "".join(p[0].upper() for p in parts[:2]) if parts else "U"
        self.preview_avatar.setText(initials)

    def _on_email_text_changed(self, text: str):
        self.preview_email_lbl.setText(text or "your.email@example.com")

    def _save_profile(self):
        name = self.name_edit.text().strip() or "User"
        email = self.email_edit.text().strip()
        role = self.role_edit.text().strip()
        persona_idx = str(self.persona_combo.currentIndex())

        self.db.set_setting("user_display_name", name)
        self.db.set_setting("user_email", email)
        self.db.set_setting("user_role", role)
        self.db.set_setting("user_persona_idx", persona_idx)

        self.profile_status.setText("✓ Profile successfully updated!")
        self.profile_updated.emit(name, email)

    # --- Motion & Performance Tab ---
    def _create_motion_tab(self) -> QWidget:
        from ui.components.animation_system import (
            get_anim_manager, PerformanceTier, button_micro_press
        )
        mgr = get_anim_manager()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Overview Card
        overview_card = QFrame()
        overview_card.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        oc_layout = QVBoxLayout(overview_card)
        oc_layout.setSpacing(6)

        oc_title = QLabel("⚡  Autonomous Motion & Performance Engine")
        oc_title.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 800;")
        oc_layout.addWidget(oc_title)

        oc_desc = QLabel(
            "Configure real-time GPU-accelerated animations, multi-agent pipeline visualizers, "
            "and accessibility preferences for prefers-reduced-motion."
        )
        oc_desc.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.4;")
        oc_desc.setWordWrap(True)
        oc_layout.addWidget(oc_desc)
        layout.addWidget(overview_card)

        # Performance Tier Config Card
        tier_card = QFrame()
        tier_card.setStyleSheet("""
            QFrame {
                background-color: #121A2A;
                border: 1px solid #273449;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        tc_layout = QVBoxLayout(tier_card)
        tc_layout.setSpacing(12)

        tier_lbl = QLabel("Active Animation Profile")
        tier_lbl.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700;")
        tc_layout.addWidget(tier_lbl)

        tier_combo = QComboBox()
        tier_combo.setStyleSheet(self._combo_style())
        tier_combo.addItem("🚀 High Performance (60 FPS, all glow conduits & micro-interactions)", PerformanceTier.HIGH.value)
        tier_combo.addItem("✨ Normal (Balanced smooth transitions & streaming feedback)", PerformanceTier.NORMAL.value)
        tier_combo.addItem("🔋 Low Performance (Power saver, disables continuous animation loops)", PerformanceTier.LOW.value)
        tier_combo.addItem("♿ Reduced Motion (Accessibility, disables large movements & scaling)", PerformanceTier.REDUCED_MOTION.value)

        curr_val = mgr.current_tier.value
        idx = tier_combo.findData(curr_val)
        if idx >= 0:
            tier_combo.setCurrentIndex(idx)
        tc_layout.addWidget(tier_combo)

        tier_info_lbl = QLabel()
        tier_info_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 10px;")
        tier_info_lbl.setWordWrap(True)
        tc_layout.addWidget(tier_info_lbl)

        def _update_desc():
            data = tier_combo.currentData()
            if data == PerformanceTier.HIGH.value:
                tier_info_lbl.setText("• Full visual fidelity: Multi-agent photon beam conduits, subtle glowing borders, tactile micro-presses, and smooth scroll interpolation enabled.")
            elif data == PerformanceTier.NORMAL.value:
                tier_info_lbl.setText("• Balanced experience: Fluid message entrances, stage transitions, and tactile feedback enabled with low CPU overhead.")
            elif data == PerformanceTier.LOW.value:
                tier_info_lbl.setText("• Battery Saver: Disables all continuous timers when idle, shortens transition durations, and prioritizes maximum battery longevity.")
            else:
                tier_info_lbl.setText("• Accessibility Mode (prefers-reduced-motion): Disables position and scale shifts. Retains instant color/state feedback to guarantee maximum clarity and comfort.")

        tier_combo.currentIndexChanged.connect(_update_desc)
        _update_desc()

        layout.addWidget(tier_card)

        # Capabilities Card
        feat_card = QFrame()
        feat_card.setStyleSheet("""
            QFrame {
                background-color: #121A2A;
                border: 1px solid #273449;
                border-radius: 12px;
                padding: 14px;
            }
        """)
        fc_layout = QVBoxLayout(feat_card)
        fc_layout.setSpacing(8)

        fc_title = QLabel("System Motion Capabilities")
        fc_title.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700;")
        fc_layout.addWidget(fc_title)

        caps = [
            ("🧠 Multi-Agent Flowchart", "Directional photon conduits & live stage indicator", "Active"),
            ("💬 Smart Chat Viewport", "Reading position protection during live AI token streams", "Active"),
            ("📋 Tactile Micro-Interactions", "Physical press feedback & auto-reverting 'Copied!' label", "Active"),
            ("⚡ 0% Idle CPU Guarantee", "Background animation timers automatically pause when inactive", "Active"),
        ]

        for c_title, c_sub, c_status in caps:
            row = QHBoxLayout()
            lbl_title = QLabel(f"<b>{c_title}</b>: {c_sub}")
            lbl_title.setStyleSheet("color: #94A3B8; font-size: 11px;")
            row.addWidget(lbl_title, 1)

            lbl_badge = QLabel(f"● {c_status}")
            lbl_badge.setStyleSheet("color: #10B981; font-size: 10px; font-weight: 700;")
            row.addWidget(lbl_badge)
            fc_layout.addLayout(row)

        layout.addWidget(feat_card)

        # Action Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton("💾  Save Motion Profile")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0072ff, stop:1 #00d1ff);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                padding: 9px 24px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0084ff, stop:1 #38bdf8);
            }
        """)

        def _save_motion():
            data = tier_combo.currentData()
            button_micro_press(save_btn)
            mgr.set_tier(PerformanceTier(data))
            orig_text = save_btn.text()
            save_btn.setText("✅  Saved!")
            QTimer.singleShot(1500, lambda: save_btn.setText(orig_text))

        save_btn.clicked.connect(_save_motion)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(container)
        return scroll

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #060913;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #f4f5fb;
                font-size: 13px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: #0FE6B5;
            }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #060913;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #f4f5fb;
                font-size: 12px;
                padding: 8px 12px;
            }
            QComboBox:focus {
                border-color: #0FE6B5;
            }
            QComboBox QAbstractItemView {
                background-color: #0a1120;
                color: #f4f5fb;
                selection-background-color: rgba(15, 230, 181, 0.2);
                selection-color: #0FE6B5;
                border: 1px solid rgba(15, 230, 181, 0.3);
            }
        """
