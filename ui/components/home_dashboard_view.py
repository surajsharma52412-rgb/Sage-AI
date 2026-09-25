"""
Home Dashboard View for SAGE AI.
Matches the exact reference picture:
- Center Column:
  - Hero greeting card: "Good afternoon, Suraj." + "Think. Create. Automate. With Sage AI." + glowing crystal badge
  - 4 Quick Action cards: Start a Chat, Generate Image, Write Code, Automate Tasks
  - Interactive Workspace Box: Tabs, "How can I help you today?", prompt suggestion pills, input bar with web search & send
- Right Column:
  - "+ New Chat" button
  - AI Agents card with live status dots (General Assistant, Coding Agent, Research Agent, Automation Agent)
  - Recent Projects card with time stamps
  - Image Generation card with prompt input, model selector, generate button, and 4 gallery thumbnails
  - "Built for a smarter you." footer
"""
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QComboBox, QScrollArea, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont

from database.db_manager import get_db


class HomeDashboardView(QWidget):
    """Main Home Dashboard matching the reference picture layout."""

    # Interactive Signals
    prompt_submitted = Signal(str)
    new_chat_requested = Signal()
    navigate_requested = Signal(str)  # 'chat', 'coding_agent', 'image_gen', 'automations', 'projects'
    agent_selected = Signal(str)
    generate_image_requested = Signal(str, str, str)  # prompt, model, aspect_ratio

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeDashboardView")
        self._assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
        self._init_ui()

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(20)

        # -------------------------------------------------------------
        # 1. Center Column (Scrollable or responsive)
        # -------------------------------------------------------------
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        center_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        center_scroll.setStyleSheet("background: transparent; border: none;")

        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 8, 0)
        center_layout.setSpacing(18)

        # --- A. Hero Banner Card ---
        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_card.setStyleSheet("""
            QFrame#heroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #101927, stop:0.5 #132238, stop:1 #0c1626);
                border: 1px solid #273449;
                border-radius: 16px;
            }
        """)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(28, 22, 28, 22)
        hero_layout.setSpacing(20)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(8)

        # Title: Good afternoon, Suraj.
        greeting_layout = QHBoxLayout()
        greeting_layout.setSpacing(6)
        greeting_lbl = QLabel("Good afternoon,")
        greeting_lbl.setStyleSheet("color: #F8FAFC; font-size: 27px; font-weight: 800; background: transparent; border: none;")
        greeting_layout.addWidget(greeting_lbl)

        db_user = get_db().get_setting("user_display_name", "")
        first_name = db_user.strip().split()[0] if db_user and db_user.strip() else "there"
        self.name_accent_lbl = QLabel(f"{first_name}.")
        self.name_accent_lbl.setStyleSheet("color: #00D1FF; font-size: 27px; font-weight: 800; background: transparent; border: none;")
        greeting_layout.addWidget(self.name_accent_lbl)
        greeting_layout.addStretch()
        hero_text_col.addLayout(greeting_layout)

        # Subtitle: Think. Create. Automate. With Sage AI.
        motto_lbl = QLabel("Think. Create. Automate. With Sage AI.")
        motto_lbl.setStyleSheet("color: #94A3B8; font-size: 14px; font-weight: 500; background: transparent; border: none;")
        hero_text_col.addWidget(motto_lbl)

        hero_layout.addLayout(hero_text_col, 1)

        # Hero Right: Glowing 3D Crystal Logo Badge
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

        hero_logo_lbl = QLabel()
        logo_file = self._assets_dir / "logo.png"
        if logo_file.exists():
            pix = QPixmap(str(logo_file)).scaled(62, 62, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            hero_logo_lbl.setPixmap(pix)
        hero_logo_lbl.setStyleSheet("background: transparent; border: none;")
        hero_logo_col.addWidget(hero_logo_lbl, 0, Qt.AlignCenter)

        sage_txt = QLabel("SAGE AI")
        sage_txt.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; background: transparent; border: none;")
        hero_logo_col.addWidget(sage_txt, 0, Qt.AlignCenter)

        badge_box.addLayout(hero_logo_col)
        hero_layout.addLayout(badge_box)

        center_layout.addWidget(hero_card)

        # --- B. 4 Quick Action Cards ---
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        action_cards = [
            ("Start a Chat", "Get intelligent\nanswers and ideas.", "💬", "chat", "#00D1FF", "#0f2744"),
            ("Generate Image", "Create stunning\nimages from text.", "🖼", "image_gen", "#22C55E", "#0f3325"),
            ("Write Code", "Build, debug and\nimprove faster.", "</>", "coding_agent", "#38BDF8", "#0e263d"),
            ("Automate Tasks", "Let AI agents handle\nrepetitive work.", "⚙", "automations", "#818CF8", "#1c1f44"),
        ]

        for title, desc, icon, nav_key, accent_col, icon_bg in action_cards:
            card = QFrame()
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: #162033;
                    border: 1px solid #273449;
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    border-color: {accent_col};
                    background-color: #1c2a44;
                }}
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(14, 14, 14, 14)
            c_layout.setSpacing(8)

            # Icon in rounded box
            icon_box = QLabel(icon)
            icon_box.setFixedSize(34, 34)
            icon_box.setAlignment(Qt.AlignCenter)
            icon_box.setStyleSheet(f"""
                background-color: {icon_bg};
                color: {accent_col};
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.06);
            """)
            c_layout.addWidget(icon_box)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700; background: transparent; border: none;")
            c_layout.addWidget(t_lbl)

            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; line-height: 1.2; background: transparent; border: none;")
            c_layout.addWidget(d_lbl)

            # Arrow button at bottom right
            arrow_row = QHBoxLayout()
            arrow_row.addStretch()
            arrow_btn = QLabel("›")
            arrow_btn.setFixedSize(22, 22)
            arrow_btn.setAlignment(Qt.AlignCenter)
            arrow_btn.setStyleSheet(f"""
                background-color: #111827;
                color: {accent_col};
                font-size: 15px;
                font-weight: 800;
                border-radius: 11px;
                border: 1px solid #273449;
            """)
            arrow_row.addWidget(arrow_btn)
            c_layout.addLayout(arrow_row)

            # Click handler
            card.mousePressEvent = lambda e, k=nav_key: self.navigate_requested.emit(k)
            cards_row.addWidget(card, 1)

        center_layout.addLayout(cards_row)

        # --- C. Central Interactive Workspace Box ---
        workspace_box = QFrame()
        workspace_box.setObjectName("workspaceBox")
        workspace_box.setStyleSheet("""
            QFrame#workspaceBox {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 14px;
            }
        """)
        ws_layout = QVBoxLayout(workspace_box)
        ws_layout.setContentsMargins(18, 14, 18, 18)
        ws_layout.setSpacing(14)

        # Workspace Tabs
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)

        tab_items = [
            ("💬 Chat", True),
            ("🖼 Image Generation", False),
            ("</> Code", False),
            ("📄 Documents", False),
            ("🔍 Web Search", False)
        ]

        self.ws_tab_buttons = []
        for text, active in tab_items:
            t_btn = QPushButton(text)
            t_btn.setCursor(Qt.PointingHandCursor)
            if active:
                t_btn.setStyleSheet("""
                    QPushButton {
                        background: #0f2744;
                        color: #00D1FF;
                        border: 1px solid rgba(0, 209, 255, 0.4);
                        border-radius: 8px;
                        padding: 6px 14px;
                        font-size: 12px;
                        font-weight: 700;
                    }
                """)
            else:
                t_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #94A3B8;
                        border: none;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-size: 12px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background: #111827;
                        color: #F8FAFC;
                    }
                """)
            t_btn.clicked.connect(lambda checked, b=t_btn, txt=text: self._on_tab_clicked(b, txt))
            self.ws_tab_buttons.append(t_btn)
            tabs_row.addWidget(t_btn)

        tabs_row.addStretch()
        ws_layout.addLayout(tabs_row)

        # Sparkle Greeting Line
        sparkle_row = QHBoxLayout()
        sparkle_row.setSpacing(8)

        sparkle_icon = QLabel("✦")
        sparkle_icon.setStyleSheet("color: #00D1FF; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        sparkle_row.addWidget(sparkle_icon)

        sparkle_text = QLabel("How can I help you today?")
        sparkle_text.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 700; background: transparent; border: none;")
        sparkle_row.addWidget(sparkle_text)
        sparkle_row.addStretch()
        ws_layout.addLayout(sparkle_row)

        # 4 Prompt Suggestions (Pills)
        suggestions_row = QHBoxLayout()
        suggestions_row.setSpacing(8)

        suggestions = [
            ("⊕ Summarize a PDF", "Summarize this PDF document: "),
            ("🖼 Generate an image", "Generate a photorealistic image of "),
            ("</> Write a Python script", "Write a complete Python script to "),
            ("📋 Plan a travel itinerary", "Create a 5-day travel itinerary for "),
        ]

        for label_text, prompt_prefix in suggestions:
            pill = QPushButton(label_text)
            pill.setCursor(Qt.PointingHandCursor)
            pill.setStyleSheet("""
                QPushButton {
                    background-color: #111827;
                    color: #CBD5E1;
                    border: 1px solid #273449;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    border-color: #00D1FF;
                    color: #00D1FF;
                    background-color: #142236;
                }
            """)
            pill.clicked.connect(lambda checked, p=prompt_prefix: self._insert_suggestion(p))
            suggestions_row.addWidget(pill)

        suggestions_row.addStretch()
        ws_layout.addLayout(suggestions_row)

        # Input Row
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 10px;
            }
            QFrame:focus-within {
                border-color: #00D1FF;
            }
        """)
        ic_layout = QHBoxLayout(input_container)
        ic_layout.setContentsMargins(10, 6, 8, 6)
        ic_layout.setSpacing(8)

        # Paperclip Attachment Button
        self.clip_btn = QPushButton("📎")
        self.clip_btn.setFixedSize(28, 28)
        self.clip_btn.setCursor(Qt.PointingHandCursor)
        self.clip_btn.setToolTip("Attach file or image")
        self.clip_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        self.clip_btn.clicked.connect(self._attach_file)
        ic_layout.addWidget(self.clip_btn)

        # Text Input
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Ask me anything...")
        self.prompt_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #F8FAFC;
                font-size: 13px;
                padding: 4px;
            }
            QLineEdit::placeholder {
                color: #64748B;
            }
        """)
        self.prompt_input.returnPressed.connect(self._submit_prompt)
        ic_layout.addWidget(self.prompt_input, 1)

        # Web Search Dropdown Badge
        self.web_search_badge = QPushButton("🌐 Web Search ∨")
        self.web_search_badge.setCursor(Qt.PointingHandCursor)
        self.web_search_badge.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        ic_layout.addWidget(self.web_search_badge)

        # Cyan Send Button with Paper Airplane
        self.send_btn = QPushButton("✈")
        self.send_btn.setFixedSize(36, 32)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setToolTip("Send message")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        self.send_btn.clicked.connect(self._submit_prompt)
        ic_layout.addWidget(self.send_btn)

        ws_layout.addWidget(input_container)
        center_layout.addWidget(workspace_box)
        center_layout.addStretch()

        center_scroll.setWidget(center_widget)
        root_layout.addWidget(center_scroll, 1)

        # -------------------------------------------------------------
        # 2. Right Column (330px fixed width matching picture)
        # -------------------------------------------------------------
        right_panel = QFrame()
        right_panel.setFixedWidth(330)
        right_panel.setStyleSheet("background: transparent; border: none;")
        rp_layout = QVBoxLayout(right_panel)
        rp_layout.setContentsMargins(0, 0, 0, 0)
        rp_layout.setSpacing(14)

        # --- A. Top "+ New Chat" Button ---
        new_chat_btn = QPushButton("＋ New Chat")
        new_chat_btn.setCursor(Qt.PointingHandCursor)
        new_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 800;
                padding: 9px 18px;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        rp_layout.addWidget(new_chat_btn, 0, Qt.AlignRight)

        # --- B. AI Agents Card ---
        agents_card = QFrame()
        agents_card.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 12px;
            }
        """)
        ac_layout = QVBoxLayout(agents_card)
        ac_layout.setContentsMargins(14, 12, 14, 12)
        ac_layout.setSpacing(10)

        ac_hdr = QHBoxLayout()
        ac_title = QLabel("AI Agents")
        ac_title.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        ac_hdr.addWidget(ac_title)
        ac_hdr.addStretch()

        view_all_agents = QPushButton("View All")
        view_all_agents.setCursor(Qt.PointingHandCursor)
        view_all_agents.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        view_all_agents.clicked.connect(lambda: self.navigate_requested.emit("multi_agent"))
        ac_hdr.addWidget(view_all_agents)
        ac_layout.addLayout(ac_hdr)

        agent_items = [
            ("💬", "General Assistant", "Chat, search, explain", "Online", "#22C55E"),
            ("</>", "Coding Agent", "Development tasks", "Online", "#22C55E"),
            ("🔍", "Research Agent", "Find and summarize", "Online", "#22C55E"),
            ("⚙", "Automation Agent", "Automate workflows", "Idle", "#38BDF8"),
        ]

        for icon, name, desc, status, dot_col in agent_items:
            row = QHBoxLayout()
            row.setSpacing(10)

            i_lbl = QLabel(icon)
            i_lbl.setFixedSize(26, 26)
            i_lbl.setAlignment(Qt.AlignCenter)
            i_lbl.setStyleSheet("background-color: #111827; color: #94A3B8; border-radius: 6px; font-size: 11px; border: 1px solid #273449;")
            row.addWidget(i_lbl)

            info_col = QVBoxLayout()
            info_col.setSpacing(1)
            n_lbl = QLabel(name)
            n_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 600; background: transparent; border: none;")
            info_col.addWidget(n_lbl)

            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; background: transparent; border: none;")
            info_col.addWidget(d_lbl)
            row.addLayout(info_col, 1)

            st_lbl = QLabel(f"● {status}")
            st_lbl.setStyleSheet(f"color: {dot_col}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            row.addWidget(st_lbl)

            ac_layout.addLayout(row)

        rp_layout.addWidget(agents_card)

        # --- C. Recent Projects Card ---
        projects_card = QFrame()
        projects_card.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 12px;
            }
        """)
        pc_layout = QVBoxLayout(projects_card)
        pc_layout.setContentsMargins(14, 12, 14, 12)
        pc_layout.setSpacing(9)

        pc_hdr = QHBoxLayout()
        pc_title = QLabel("Recent Projects")
        pc_title.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        pc_hdr.addWidget(pc_title)
        pc_hdr.addStretch()

        view_all_projects = QPushButton("View All")
        view_all_projects.setCursor(Qt.PointingHandCursor)
        view_all_projects.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        view_all_projects.clicked.connect(lambda: self.navigate_requested.emit("coding_agent"))
        pc_hdr.addWidget(view_all_projects)
        pc_layout.addLayout(pc_hdr)

        recent_projects = [
            ("House Price Prediction", "2 hours ago"),
            ("Sage Web UI", "1 day ago"),
            ("Automation Tools", "3 days ago"),
            ("Travel Itinerary Planner", "5 days ago"),
        ]

        for p_title, p_time in recent_projects:
            row = QHBoxLayout()
            row.setSpacing(8)

            doc_icon = QLabel("📄")
            doc_icon.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent; border: none;")
            row.addWidget(doc_icon)

            p_col = QVBoxLayout()
            p_col.setSpacing(1)
            t_lbl = QLabel(p_title)
            t_lbl.setStyleSheet("color: #F8FAFC; font-size: 12px; font-weight: 600; background: transparent; border: none;")
            p_col.addWidget(t_lbl)

            tm_lbl = QLabel(p_time)
            tm_lbl.setStyleSheet("color: #64748B; font-size: 10px; background: transparent; border: none;")
            p_col.addWidget(tm_lbl)
            row.addLayout(p_col, 1)

            pc_layout.addLayout(row)

        rp_layout.addWidget(projects_card)

        # --- D. Image Generation Card ---
        img_card = QFrame()
        img_card.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 12px;
            }
        """)
        ic_card_layout = QVBoxLayout(img_card)
        ic_card_layout.setContentsMargins(14, 12, 14, 12)
        ic_card_layout.setSpacing(10)

        ic_hdr = QHBoxLayout()
        ic_title = QLabel("Image Generation")
        ic_title.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        ic_hdr.addWidget(ic_title)
        ic_hdr.addStretch()

        view_all_img = QPushButton("View All")
        view_all_img.setCursor(Qt.PointingHandCursor)
        view_all_img.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        view_all_img.clicked.connect(lambda: self.navigate_requested.emit("image_gen"))
        ic_hdr.addWidget(view_all_img)
        ic_card_layout.addLayout(ic_hdr)

        # Describe prompt input
        self.img_prompt_input = QLineEdit()
        self.img_prompt_input.setPlaceholderText("Describe the image you want to create...")
        self.img_prompt_input.setStyleSheet("""
            QLineEdit {
                background-color: #111827;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #F8FAFC;
                font-size: 11px;
                padding: 6px 8px;
            }
            QLineEdit::placeholder {
                color: #64748B;
            }
        """)
        ic_card_layout.addWidget(self.img_prompt_input)

        # Dropdowns & Generate Button Row
        control_row = QHBoxLayout()
        control_row.setSpacing(6)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["FLUX (Default)", "SDXL Turbo", "DALL-E 3"])
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #111827;
                color: #CBD5E1;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 10px;
            }
        """)
        control_row.addWidget(self.model_combo, 1)

        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(["16:9", "1:1", "4:3", "9:16"])
        self.ratio_combo.setStyleSheet("""
            QComboBox {
                background-color: #111827;
                color: #CBD5E1;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 10px;
            }
        """)
        control_row.addWidget(self.ratio_combo)

        self.gen_btn = QPushButton("🖼 Generate Image")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        self.gen_btn.clicked.connect(self._on_generate_image)
        control_row.addWidget(self.gen_btn)

        ic_card_layout.addLayout(control_row)

        # 4 Image Thumbnails Row
        thumbs_row = QHBoxLayout()
        thumbs_row.setSpacing(6)

        thumb_files = [
            "thumb_mountain.png",
            "thumb_cyberpunk.png",
            "thumb_wolf.png",
            "thumb_plant.png",
        ]

        for tf in thumb_files:
            t_lbl = QLabel()
            t_lbl.setFixedSize(68, 68)
            t_lbl.setCursor(Qt.PointingHandCursor)
            t_path = self._assets_dir / tf
            if t_path.exists():
                pix = QPixmap(str(t_path)).scaled(68, 68, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                t_lbl.setPixmap(pix)
            t_lbl.setStyleSheet("""
                QLabel {
                    border: 1px solid #273449;
                    border-radius: 8px;
                    background-color: #111827;
                }
                QLabel:hover {
                    border-color: #00D1FF;
                }
            """)
            t_lbl.setAlignment(Qt.AlignCenter)
            thumbs_row.addWidget(t_lbl)

        ic_card_layout.addLayout(thumbs_row)
        rp_layout.addWidget(img_card)

        # --- E. Bottom Right Footer ---
        built_lbl = QLabel("Built for a smarter you.")
        built_lbl.setStyleSheet("color: #475569; font-size: 10px; font-weight: 500; background: transparent; border: none;")
        built_lbl.setAlignment(Qt.AlignRight)
        rp_layout.addWidget(built_lbl)

        rp_layout.addStretch()
        root_layout.addWidget(right_panel)

    # --- Handlers ---

    def _on_tab_clicked(self, clicked_btn: QPushButton, text: str):
        for btn in self.ws_tab_buttons:
            if btn == clicked_btn:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #0f2744;
                        color: #00D1FF;
                        border: 1px solid rgba(0, 209, 255, 0.4);
                        border-radius: 8px;
                        padding: 6px 14px;
                        font-size: 12px;
                        font-weight: 700;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #94A3B8;
                        border: none;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-size: 12px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background: #111827;
                        color: #F8FAFC;
                    }
                """)

    def _insert_suggestion(self, prompt: str):
        self.prompt_input.setText(prompt)
        self.prompt_input.setFocus()
        self.prompt_input.setCursorPosition(len(prompt))

    def _submit_prompt(self):
        text = self.prompt_input.text().strip()
        if text:
            self.prompt_input.clear()
            self.prompt_submitted.emit(text)

    def _attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Attach File to Prompt", "", "All Files (*.*)"
        )
        if file_path:
            curr = self.prompt_input.text().strip()
            self.prompt_input.setText(f"{curr} [Attached: {Path(file_path).name}] ")

    def _on_generate_image(self):
        prompt = self.img_prompt_input.text().strip()
        model = self.model_combo.currentText()
        ratio = self.ratio_combo.currentText()
        if prompt:
            self.img_prompt_input.clear()
            self.gen_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00E6FF;
                    color: #0A0F14;
                    border: 2px solid #FFFFFF;
                    border-radius: 6px;
                    padding: 5px 8px;
                    font-size: 11px;
                    font-weight: 800;
                }
            """)
            QTimer.singleShot(250, lambda: self.gen_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00D1FF;
                    color: #0A0F14;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 8px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #00BBE6;
                }
            """))
            self.generate_image_requested.emit(prompt, model, ratio)
        else:
            self.navigate_requested.emit("image_gen")

    def update_user_name(self, name: Optional[str] = None):
        """Dynamically updates the hero greeting when user enters their name."""
        if not name:
            name = get_db().get_setting("user_display_name", "")
        first_name = name.strip().split()[0] if name and name.strip() else "there"
        if hasattr(self, "name_accent_lbl") and self.name_accent_lbl:
            self.name_accent_lbl.setText(f"{first_name}.")

