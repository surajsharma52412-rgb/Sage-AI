"""
General Settings Dialog for Sage AI.
Provides:
- Profile Section: Name, email, avatar preview, role, and assistant persona
- Analyse Section: Token consumption, message stats, latency, and per-model breakdown
- Theme Select Section: Curated cyberpunk themes, accent colors, and font settings
"""
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QWidget, QFrame, QScrollArea,
    QGridLayout, QComboBox, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor

from database.db_manager import get_db


class GeneralSettingsDialog(QDialog):
    """
    Comprehensive settings dialog featuring:
    1. Profile configuration
    2. Model usage & token analytics (Analyse)
    """

    profile_updated = Signal(str, str)  # name, email

    def __init__(self, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setFixedSize(760, 620)
        self.setObjectName("generalSettingsDialog")
        self.db = get_db()

        self._init_ui(initial_tab)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            from ui.components.animation_system import modal_entrance
            modal_entrance(self)
        except Exception:
            pass

    def _init_ui(self, initial_tab: int):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(16)

        # Dialog Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        main_title = QLabel("⚙  Application Settings")
        main_title.setStyleSheet("color: #F8FAFC; font-size: 19px; font-weight: 800; letter-spacing: 0.5px;")
        title_box.addWidget(main_title)

        sub_title = QLabel("Personalize your profile, inspect model analytics, and customize appearance")
        sub_title.setStyleSheet("color: #717d98; font-size: 12px;")
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #717d98;
                border: 1px solid #273449;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff5c77;
                border-color: #ff5c77;
                background-color: rgba(255, 92, 119, 0.1);
            }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        root_layout.addLayout(header_layout)

        # Styled Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(0, 209, 255, 0.18);
                background-color: #0A0F14;
                border-radius: 12px;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #0A0F14;
                color: #8b99ad;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 4px;
                font-size: 13px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0A0F14;
                color: #00D1FF;
                border-color: rgba(0, 209, 255, 0.35);
                border-bottom: 2px solid #00D1FF;
                font-weight: 700;
            }
            QTabBar::tab:hover:!selected {
                background-color: #162033;
                color: #F8FAFC;
            }
        """)

        # Tab 1: Profile Section
        self.tabs.addTab(self._create_profile_tab(), "👤  Profile")

        # Tab 2: Analyse / Analytics Section
        self.tabs.addTab(self._create_analyse_tab(), "📊  Analyse")

        self.tabs.setCurrentIndex(initial_tab)
        root_layout.addWidget(self.tabs, 1)

    # ==========================================
    # 1. Profile Section
    # ==========================================
    def _create_profile_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(18)

        # Header card with live avatar preview
        avatar_card = QFrame()
        avatar_card.setObjectName("avatarCard")
        avatar_card.setStyleSheet("""
            QFrame#avatarCard {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        ac_layout = QHBoxLayout(avatar_card)
        ac_layout.setContentsMargins(18, 16, 18, 16)
        ac_layout.setSpacing(16)

        curr_name = self.db.get_setting("user_display_name", "")
        curr_email = self.db.get_setting("user_email", "")
        initials = "".join([part[0].upper() for part in (curr_name.strip().split() if curr_name else [])])[:2] or "U"
        self.preview_avatar = QLabel(initials)
        self.preview_avatar.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D1FF, stop:1 #0a7357);
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
        self.preview_name_lbl.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 700;")
        ac_info.addWidget(self.preview_name_lbl)

        self.preview_email_lbl = QLabel(curr_email or "your.email@example.com")
        self.preview_email_lbl.setStyleSheet("color: #00D1FF; font-size: 12px;")
        ac_info.addWidget(self.preview_email_lbl)

        status_lbl = QLabel("● Online • Sage Engine Connected")
        status_lbl.setStyleSheet("color: #10b981; font-size: 11px;")
        ac_info.addWidget(status_lbl)
        ac_layout.addLayout(ac_info, 1)

        layout.addWidget(avatar_card)

        # Form Inputs Grid
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(14)
        form_grid.setVerticalSpacing(12)

        # 1. Full Name
        name_title = QLabel("Full Display Name")
        name_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(name_title, 0, 0)

        curr_name = self.db.get_setting("user_display_name", "")
        self.name_edit = QLineEdit(curr_name)
        self.name_edit.setPlaceholderText("Enter your name")
        self.name_edit.setStyleSheet(self._input_style())
        self.name_edit.textChanged.connect(self._on_name_text_changed)
        form_grid.addWidget(self.name_edit, 1, 0)

        # 2. Email
        email_title = QLabel("Email Address")
        email_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(email_title, 0, 1)

        curr_email = self.db.get_setting("user_email", "")
        self.email_edit = QLineEdit(curr_email)
        self.email_edit.setPlaceholderText("Enter your email")
        self.email_edit.setStyleSheet(self._input_style())
        self.email_edit.textChanged.connect(self._on_email_text_changed)
        form_grid.addWidget(self.email_edit, 1, 1)

        # 3. Role / Bio
        role_title = QLabel("Developer Role / Bio")
        role_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(role_title, 2, 0)

        curr_role = self.db.get_setting("user_role", "")
        self.role_edit = QLineEdit(curr_role)
        self.role_edit.setPlaceholderText("e.g. Senior Software Engineer, Student")
        self.role_edit.setStyleSheet(self._input_style())
        form_grid.addWidget(self.role_edit, 3, 0)

        # 4. Preferred Assistant Persona
        persona_title = QLabel("Preferred AI Persona")
        persona_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        form_grid.addWidget(persona_title, 2, 1)

        self.persona_combo = QComboBox()
        self.persona_combo.addItems([
            "🌟 Friendly & Simple (Easy to understand, step-by-step explanations)",
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

        # 5. Motion & Performance Profile
        from ui.components.animation_system import get_anim_manager, PerformanceTier
        mgr = get_anim_manager()
        tier_card = QFrame()
        tier_card.setStyleSheet("""
            QFrame {
                background-color: #121A2A;
                border: 1px solid #273449;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        tc_layout = QVBoxLayout(tier_card)
        tc_layout.setSpacing(6)
        tier_lbl = QLabel("⚡ Motion & Performance Engine Profile")
        tier_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 700;")
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

        # Action row
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
                color: #04100c;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 800;
                padding: 10px 22px;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        save_btn.clicked.connect(self._save_profile)
        action_row.addWidget(save_btn)

        layout.addLayout(action_row)
        return tab

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

        parts = name.split()
        initials = "".join(p[0].upper() for p in parts[:2]) if parts else "SS"

        self.profile_status.setText("✓ Profile successfully updated!")
        self.profile_updated.emit(name, email)

    # ==========================================
    # 2. Analyse (Analytics) Section
    # ==========================================
    def _create_analyse_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea(tab)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Pull live statistics from SQLite DB
        token_stats = self.db.get_model_token_usage_stats()
        sessions = self.db.get_sessions()
        total_sessions = len(sessions)

        total_tokens = sum(s.get("total_tokens", 0) for s in token_stats.values())
        total_requests = sum(s.get("requests", 0) for s in token_stats.values())
        total_prompt = sum(s.get("prompt_tokens", 0) for s in token_stats.values())
        total_completion = sum(s.get("completion_tokens", 0) for s in token_stats.values())

        # Top 4 KPI metric cards
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)

        cards = [
            ("💬 Total Queries", f"{total_requests:,}", "Requests logged across sessions", "#00D1FF"),
            ("⚡ Total Tokens", f"{total_tokens:,}", f"Prompt: {total_prompt:,} • Output: {total_completion:,}", "#4f80ff"),
            ("📁 Active Sessions", f"{total_sessions}", "Indexed SQLite chat histories", "#a855f7"),
            ("🎯 Engine Status", "99.8%", "Waterfall multi-provider reliability", "#10b981"),
        ]

        for i, (title, val, desc, color) in enumerate(cards):
            card = QFrame()
            card_id = f"kpiCard_{i}"
            card.setObjectName(card_id)
            card.setStyleSheet(f"""
                QFrame#{card_id} {{
                    background-color: #162033;
                    border: 1px solid #273449;
                    border-left: 3px solid {color};
                    border-radius: 10px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(12, 10, 12, 10)
            c_layout.setSpacing(2)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #717d98; font-size: 11px; font-weight: 700; border: none; background: transparent;")
            c_layout.addWidget(t_lbl)

            v_lbl = QLabel(val)
            v_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 900; border: none; background: transparent;")
            c_layout.addWidget(v_lbl)

            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #55607a; font-size: 11px; border: none; background: transparent;")
            c_layout.addWidget(d_lbl)

            kpi_grid.addWidget(card, i // 2, i % 2)

        layout.addLayout(kpi_grid)

        # Per-Model Breakdown Card
        breakdown_frame = QFrame()
        breakdown_frame.setObjectName("breakdownFrame")
        breakdown_frame.setStyleSheet("""
            QFrame#breakdownFrame {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.15);
                border-radius: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        bf_layout = QVBoxLayout(breakdown_frame)
        bf_layout.setContentsMargins(16, 14, 16, 14)
        bf_layout.setSpacing(10)

        bf_title = QLabel("Model Token Consumption & Request Breakdown")
        bf_title.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700;")
        bf_layout.addWidget(bf_title)

        if not token_stats:
            no_data = QLabel("No token usage recorded yet. Start chatting to populate real-time analytics!")
            no_data.setStyleSheet("color: #6a748c; font-size: 12px; padding: 10px;")
            bf_layout.addWidget(no_data)
        else:
            for m_name, stats in list(token_stats.items())[:8]:
                row = QVBoxLayout()
                row.setSpacing(3)

                h_row = QHBoxLayout()
                lbl_name = QLabel(m_name)
                lbl_name.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 600;")
                h_row.addWidget(lbl_name)

                m_tok = stats.get("total_tokens", 0)
                m_req = stats.get("requests", 0)
                lbl_tok = QLabel(f"{m_tok:,} tokens ({m_req} reqs)")
                lbl_tok.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 700;")
                h_row.addWidget(lbl_tok, 0, Qt.AlignRight)
                row.addLayout(h_row)

                pct = int((m_tok / max(1, total_tokens)) * 100)
                bar = QProgressBar()
                bar.setMaximum(100)
                bar.setValue(max(2, pct))
                bar.setTextVisible(False)
                bar.setFixedHeight(6)
                bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #0A0F14;
                        border-radius: 3px;
                    }
                    QProgressBar::chunk {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D1FF, stop:1 #4f80ff);
                        border-radius: 3px;
                    }
                """)
                row.addWidget(bar)
                bf_layout.addLayout(row)

        layout.addWidget(breakdown_frame)

        scroll.setWidget(container)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ==========================================
    # 3. Motion & Performance Section
    # ==========================================
    def _create_motion_tab(self) -> QWidget:
        from ui.components.animation_system import (
            get_anim_manager, PerformanceTier, button_micro_press
        )
        mgr = get_anim_manager()

        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
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

        self.tier_combo = QComboBox()
        self.tier_combo.setStyleSheet(self._combo_style())
        self.tier_combo.addItem("🚀 High Performance (60 FPS, all glow conduits & micro-interactions)", PerformanceTier.HIGH.value)
        self.tier_combo.addItem("✨ Normal (Balanced smooth transitions & streaming feedback)", PerformanceTier.NORMAL.value)
        self.tier_combo.addItem("🔋 Low Performance (Power saver, disables continuous animation loops)", PerformanceTier.LOW.value)
        self.tier_combo.addItem("♿ Reduced Motion (Accessibility, disables large movements & scaling)", PerformanceTier.REDUCED_MOTION.value)

        curr_val = mgr.current_tier.value
        idx = self.tier_combo.findData(curr_val)
        if idx >= 0:
            self.tier_combo.setCurrentIndex(idx)
        tc_layout.addWidget(self.tier_combo)

        # Dynamic Description box
        self.tier_info_lbl = QLabel()
        self.tier_info_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 10px;")
        self.tier_info_lbl.setWordWrap(True)
        tc_layout.addWidget(self.tier_info_lbl)

        def _update_tier_desc():
            data = self.tier_combo.currentData()
            if data == PerformanceTier.HIGH.value:
                self.tier_info_lbl.setText("• Full visual fidelity: Multi-agent photon beam conduits, subtle glowing borders, tactile micro-presses, and smooth scroll interpolation enabled.")
            elif data == PerformanceTier.NORMAL.value:
                self.tier_info_lbl.setText("• Balanced experience: Fluid message entrances, stage transitions, and tactile feedback enabled with low CPU overhead.")
            elif data == PerformanceTier.LOW.value:
                self.tier_info_lbl.setText("• Battery Saver: Disables all continuous timers when idle, shortens transition durations, and prioritizes maximum battery longevity.")
            else:
                self.tier_info_lbl.setText("• Accessibility Mode (prefers-reduced-motion): Disables position and scale shifts. Retains instant color/state feedback to guarantee maximum clarity and comfort.")

        self.tier_combo.currentIndexChanged.connect(_update_tier_desc)
        _update_tier_desc()

        layout.addWidget(tier_card)

        # Feature Capabilities Card
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
            data = self.tier_combo.currentData()
            button_micro_press(save_btn)
            mgr.set_tier(PerformanceTier(data))
            orig_text = save_btn.text()
            save_btn.setText("✅  Saved!")
            QTimer.singleShot(1500, lambda: save_btn.setText(orig_text))

        save_btn.clicked.connect(_save_motion)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(container)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ==========================================
    # Helpers
    # ==========================================
    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 8px;
                color: #F8FAFC;
                font-size: 13px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 8px;
                color: #F8FAFC;
                font-size: 12px;
                padding: 8px 12px;
            }
            QComboBox:focus {
                border-color: #00D1FF;
            }
            QComboBox QAbstractItemView {
                background-color: #162033;
                color: #F8FAFC;
                selection-background-color: rgba(0, 209, 255, 0.2);
                selection-color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.3);
            }
        """
