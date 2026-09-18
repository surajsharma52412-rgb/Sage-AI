"""
Settings Dialog Component for Sage AI (Lunar Engine).
Manages provider API keys, live key verification tests, Ollama server auto-start & tests,
Mem0 memory toggles, and fast-mode preferences stored in SQLite.
"""
import requests
import webbrowser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QTabWidget, QWidget,
    QFrame, QMessageBox, QComboBox, QScrollArea, QApplication,
    QInputDialog
)
from PySide6.QtCore import Qt

from config import PROVIDER_PRESET_MODELS, DEFAULT_MODELS
from database.db_manager import get_db
from engine.model_scanner import ModelScanner
from engine.providers.ollama_provider import OllamaProvider
from engine.ollama_manager import (
    start_ollama_service, is_ollama_running, get_installed_ollama_models
)


class SettingsDialog(QDialog):
    """Configuration dialog for API keys, local endpoints, and engine options."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add & Connect AI Models — Sage AI")
        self.resize(850, 710)
        self.setObjectName("settingsDialog")
        self.setStyleSheet("""
            QDialog#settingsDialog {
                background-color: #0A0F14;
                color: #F8FAFC;
            }
            QTabWidget::pane {
                border: 1px solid rgba(0, 209, 255, 0.2);
                background-color: #0A0F14;
                border-radius: 12px;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #0c1324;
                color: #94A3B8;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 9px 18px;
                font-size: 12px;
                font-weight: 600;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.5);
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background-color: rgba(0, 209, 255, 0.08);
                color: #F8FAFC;
            }
        """)
        self.db = get_db()

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # Dialog Header
        header = QHBoxLayout()
        icon_lbl = QLabel("🤖")
        icon_lbl.setStyleSheet("color: #00D1FF; font-size: 22px;")
        header.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Add & Connect AI Models")
        title.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 800; letter-spacing: 0.3px;")
        title_box.addWidget(title)
        subtitle = QLabel("Easily add free cloud AI, frontier reasoning models, or 100% private offline AI")
        subtitle.setStyleSheet("color: #7d8aa4; font-size: 11px;")
        title_box.addWidget(subtitle)
        header.addLayout(title_box)

        header.addStretch()

        scan_all_btn = QPushButton("🔍 Scan All Connected Models")
        scan_all_btn.setCursor(Qt.PointingHandCursor)
        scan_all_btn.setToolTip("Test credentials and auto-discover models for all configured AI providers")
        scan_all_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.25);
                border-color: #00D1FF;
            }
        """)
        scan_all_btn.clicked.connect(self._scan_all_models)
        header.addWidget(scan_all_btn)

        main_layout.addLayout(header)

        # Tab Widget
        self.tabs = QTabWidget()

        # Tab 1: Cloud AI Providers & Models
        self.tabs.addTab(self._create_api_keys_tab(), "✨ Add Cloud AI & Models")

        # Tab 2: Local Offline AI (Ollama)
        self.tabs.addTab(self._create_local_tab(), "💻 Add Local AI (Ollama)")

        # Tab 3: Behavior & Memory
        self.tabs.addTab(self._create_behavior_tab(), "⚡ Memory && Routing")

        # Tab 4: Gmail & Automations
        self.tabs.addTab(self._create_automations_tab(), "📧 Gmail && Automations")

        main_layout.addWidget(self.tabs, 1)

        # Feedback notification banner
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        main_layout.addWidget(self.status_lbl)

        # Bottom Button Bar
        btn_bar = QHBoxLayout()

        usage_btn = QPushButton("📊 View Model Usage && Tokens")
        usage_btn.setCursor(Qt.PointingHandCursor)
        usage_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
                border-color: #00D1FF;
            }
        """)
        usage_btn.clicked.connect(self._open_usage_dialog)
        btn_bar.addWidget(usage_btn)

        btn_bar.addStretch()

        close_btn = QPushButton("Cancel")
        close_btn.setStyleSheet("background-color: transparent; color: #a8afc2; border: 1px solid #626c85; border-radius: 6px; padding: 6px 16px;")
        close_btn.clicked.connect(self.reject)
        btn_bar.addWidget(close_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("newChatBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_settings)
        btn_bar.addWidget(save_btn)

        main_layout.addLayout(btn_bar)

    def _open_usage_dialog(self):
        from ui.components.usage_dialog import UsageDialog
        dlg = UsageDialog(self)
        dlg.exec()

    def _setup_model_combo(self, provider_key: str) -> QComboBox:
        """Helper to create an editable QComboBox populated with discovered models or presets."""
        combo = QComboBox()
        combo.setEditable(True)
        combo.setStyleSheet("""
            QComboBox {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                selection-background-color: #00D1FF;
                selection-color: #0A0F14;
            }
            QComboBox:focus {
                border: 1px solid #00D1FF;
            }
            QComboBox QAbstractItemView {
                background-color: #09101d;
                color: #F8FAFC;
                selection-background-color: rgba(0, 209, 255, 0.2);
                selection-color: #00D1FF;
                border: 1px solid #00D1FF;
            }
        """)
        discovered = self.db.get_discovered_models(provider_key)
        if discovered:
            for d in discovered:
                combo.addItem(d["model_name"])
        else:
            presets = PROVIDER_PRESET_MODELS.get(provider_key, [])
            for m in presets:
                combo.addItem(m)
        return combo

    def _update_combo(self, combo: QComboBox, items: list):
        """Helper to update items in a combo box while preserving current selection."""
        if not combo:
            return
        curr = combo.currentText().strip()
        combo.clear()
        for item in items:
            combo.addItem(item)
        if curr:
            combo.setCurrentText(curr)
        elif items:
            combo.setCurrentText(items[0])

    def _create_secure_input_row(
        self,
        placeholder: str,
        portal_url: str = ""
    ) -> tuple:
        """Creates a line edit with toggle visibility, paste, and optional portal link button."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        line_edit = QLineEdit()
        line_edit.setEchoMode(QLineEdit.Password)
        line_edit.setPlaceholderText(placeholder)
        layout.addWidget(line_edit, 1)

        # Eye toggle button
        eye_btn = QPushButton("👁")
        eye_btn.setToolTip("Show / Hide Key")
        eye_btn.setFixedSize(28, 28)
        eye_btn.setCursor(Qt.PointingHandCursor)
        eye_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #a8afc2;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 5px;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.2);
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        def toggle_echo():
            if line_edit.echoMode() == QLineEdit.Password:
                line_edit.setEchoMode(QLineEdit.Normal)
                eye_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 209, 255, 0.15);
                        color: #00D1FF;
                        border: 1px solid #00D1FF;
                        border-radius: 5px;
                        font-size: 13px;
                        padding: 0px;
                    }
                """)
            else:
                line_edit.setEchoMode(QLineEdit.Password)
                eye_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #162033;
                        color: #a8afc2;
                        border: 1px solid rgba(0, 209, 255, 0.25);
                        border-radius: 5px;
                        font-size: 13px;
                        padding: 0px;
                    }
                    QPushButton:hover {
                        background-color: rgba(0, 209, 255, 0.2);
                        color: #00D1FF;
                        border-color: #00D1FF;
                    }
                """)
        eye_btn.clicked.connect(toggle_echo)
        layout.addWidget(eye_btn)

        # Paste button
        paste_btn = QPushButton("📋")
        paste_btn.setToolTip("Paste from Clipboard")
        paste_btn.setFixedSize(28, 28)
        paste_btn.setCursor(Qt.PointingHandCursor)
        paste_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #a8afc2;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 5px;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.2);
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """)
        def paste_clipboard():
            clip_text = QApplication.clipboard().text().strip()
            if clip_text:
                line_edit.setText(clip_text)
        paste_btn.clicked.connect(paste_clipboard)
        layout.addWidget(paste_btn)

        # Portal link button
        if portal_url:
            link_btn = QPushButton("🔗 Get Key")
            link_btn.setToolTip(f"Open developer portal: {portal_url}")
            link_btn.setFixedHeight(28)
            link_btn.setCursor(Qt.PointingHandCursor)
            link_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 209, 255, 0.08);
                    color: #00D1FF;
                    border: 1px solid rgba(0, 209, 255, 0.3);
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 209, 255, 0.25);
                    border-color: #00D1FF;
                }
            """)
            link_btn.clicked.connect(lambda checked=False, url=portal_url: webbrowser.open(url))
            layout.addWidget(link_btn)

        return line_edit, container

    def _create_provider_card(
        self,
        icon: str,
        title: str,
        description: str,
        badges: list = None,
        how_to_step: str = ""
    ) -> tuple:
        """Creates a styled provider card frame with icon, title, badges, and quick help."""
        card = QFrame()
        card.setObjectName("providerCard")
        card.setStyleSheet("""
            QFrame#providerCard {
                background-color: rgba(8, 14, 28, 0.85);
                border: 1px solid rgba(0, 209, 255, 0.15);
                border-radius: 12px;
                padding: 4px;
            }
            QFrame#providerCard:hover {
                border-color: rgba(0, 209, 255, 0.35);
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        # Card header row: Icon + Title + Badges
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18px; background: transparent;")
        header_row.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #00D1FF; font-size: 14px; font-weight: 700; background: transparent;")
        header_row.addWidget(title_lbl)

        if badges:
            for text, fg, bg, border in badges:
                badge_lbl = QLabel(text)
                badge_lbl.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    border-radius: 4px;
                    padding: 2px 7px;
                    font-size: 10px;
                    font-weight: 700;
                """)
                header_row.addWidget(badge_lbl)

        header_row.addStretch()

        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
        header_row.addWidget(desc_lbl)

        card_layout.addLayout(header_row)

        if how_to_step:
            step_lbl = QLabel(f"💡 {how_to_step}")
            step_lbl.setStyleSheet("color: #657491; font-size: 10.5px; background: transparent;")
            step_lbl.setWordWrap(True)
            card_layout.addWidget(step_lbl)

        return card, card_layout

    def _create_model_selection_row(self, provider_key: str, combo: QComboBox) -> QHBoxLayout:
        """Helper to build a model selection row with a convenient '+ Add Custom Model' button."""
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("Active Model:")
        lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600;")
        row.addWidget(lbl)
        row.addWidget(combo, 1)

        custom_btn = QPushButton("＋ Add Custom Model")
        custom_btn.setToolTip(f"Add and select any custom model name for {provider_key.capitalize()}")
        custom_btn.setCursor(Qt.PointingHandCursor)
        custom_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.08);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.3);
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.22);
                border-color: #00D1FF;
            }
        """)
        custom_btn.clicked.connect(lambda: self._prompt_add_custom_model(combo, provider_key))
        row.addWidget(custom_btn)
        return row

    def _prompt_add_custom_model(self, combo: QComboBox, provider_key: str):
        """Allows users to quickly add any model identifier without manual JSON editing."""
        model_name, ok = QInputDialog.getText(
            self,
            f"Add Custom Model — {provider_key.capitalize()}",
            f"Enter model identifier for {provider_key.capitalize()}:\n(e.g. meta-llama/llama-3.3-70b-instruct, deepseek/deepseek-r1, or qwen/qwen-2.5-coder-32b)"
        )
        if ok and model_name.strip():
            m = model_name.strip()
            if combo.findText(m) == -1:
                combo.addItem(m)
            combo.setCurrentText(m)
            self.status_lbl.setText(f"✓ Added and selected custom model: {m}")
            self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")

    def _create_api_keys_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # ──────────────────────────────────────────────────
        # 🚀 Quick Start Guide Banner (Beginner Friendly)
        # ──────────────────────────────────────────────────
        quick_start = QFrame()
        quick_start.setStyleSheet("""
            QFrame {
                background-color: #0b1426;
                border: 1.5px solid rgba(0, 209, 255, 0.4);
                border-radius: 12px;
                padding: 12px;
            }
        """)
        qs_layout = QVBoxLayout(quick_start)
        qs_layout.setSpacing(6)

        qs_header = QHBoxLayout()
        qs_icon = QLabel("🚀")
        qs_icon.setStyleSheet("font-size: 16px; background: transparent;")
        qs_header.addWidget(qs_icon)
        qs_title = QLabel("Quick Start: How to Add Free AI in 30 Seconds")
        qs_title.setStyleSheet("color: #00D1FF; font-size: 13.5px; font-weight: 800; background: transparent;")
        qs_header.addWidget(qs_title)
        qs_header.addStretch()
        qs_layout.addLayout(qs_header)

        qs_desc = QLabel(
            "<b>New to Sage? You don't need a credit card!</b> Get started with our recommended free options:<br>"
            "• <span style='color:#00D1FF;'>💎 <b>Google Gemini</b></span>: 100% Free tier, high intelligence, handles large files & context.<br>"
            "• <span style='color:#f59e0b;'>⚡ <b>Groq</b></span>: 100% Free tier, ultra-fast responses (500+ words/sec), perfect for instant chat.<br>"
            "• <span style='color:#38bdf8;'>💻 <b>Local Ollama</b></span>: 100% Free & private, runs completely offline on your computer (see Local tab).<br><br>"
            "👉 <i>Just click '<b>🔗 Get Key</b>' on any card below, copy your key, paste it, and click '<b>⚡ Test & Connect</b>'!</i>"
        )
        qs_desc.setStyleSheet("color: #d6e2f5; font-size: 11.5px; line-height: 1.5; background: transparent;")
        qs_desc.setWordWrap(True)
        qs_layout.addWidget(qs_desc)

        layout.addWidget(quick_start)

        # ──────────────────────────────────────────────────
        # 1. Google Gemini Card (Recommended for Beginners)
        # ──────────────────────────────────────────────────
        gem_badges = [
            ("🟢 100% Free Tier", "#00D1FF", "rgba(0, 209, 255, 0.15)", "rgba(0, 209, 255, 0.4)"),
            ("⭐ Recommended for Beginners", "#38bdf8", "rgba(56, 189, 248, 0.15)", "rgba(56, 189, 248, 0.4)")
        ]
        gem_card, gem_layout = self._create_provider_card(
            "💎", "Google Gemini", "Google AI Studio",
            badges=gem_badges,
            how_to_step="1. Click '🔗 Get Key' (Free Google account)  ➔  2. Paste key below  ➔  3. Click '⚡ Test & Connect'"
        )

        gem_key_row = QHBoxLayout()
        gem_key_row.setSpacing(6)
        self.gemini_input, gem_container = self._create_secure_input_row("AIzaSy...", "https://aistudio.google.com/app/apikey")
        gem_key_row.addWidget(gem_container, 1)
        test_gem_btn = QPushButton("⚡ Test && Connect")
        test_gem_btn.setFixedWidth(120)
        test_gem_btn.setCursor(Qt.PointingHandCursor)
        test_gem_btn.setStyleSheet(self._test_btn_style())
        test_gem_btn.clicked.connect(self._test_gemini_key)
        gem_key_row.addWidget(test_gem_btn)
        gem_layout.addLayout(gem_key_row)

        self.gemini_status = QLabel("")
        self.gemini_status.setStyleSheet("font-size: 11px;")
        gem_layout.addWidget(self.gemini_status)

        self.gemini_model_combo = self._setup_model_combo("gemini")
        gem_model_row = self._create_model_selection_row("gemini", self.gemini_model_combo)
        gem_layout.addLayout(gem_model_row)

        layout.addWidget(gem_card)

        # ──────────────────────────────────────────────────
        # 2. Groq Card (Ultra-Fast & Free)
        # ──────────────────────────────────────────────────
        groq_badges = [
            ("🟢 100% Free Tier", "#00D1FF", "rgba(0, 209, 255, 0.15)", "rgba(0, 209, 255, 0.4)"),
            ("⚡ Ultra Fast (500+ tok/s)", "#f59e0b", "rgba(245, 158, 11, 0.15)", "rgba(245, 158, 11, 0.4)")
        ]
        groq_card, groq_layout = self._create_provider_card(
            "⚡", "Groq", "Ultra-fast inference",
            badges=groq_badges,
            how_to_step="1. Click '🔗 Get Key' (Free account)  ➔  2. Paste key below  ➔  3. Click '⚡ Test & Connect'"
        )

        groq_key_row = QHBoxLayout()
        groq_key_row.setSpacing(6)
        self.groq_input, groq_container = self._create_secure_input_row("gsk_...", "https://console.groq.com/keys")
        groq_key_row.addWidget(groq_container, 1)
        test_groq_btn = QPushButton("⚡ Test && Connect")
        test_groq_btn.setFixedWidth(120)
        test_groq_btn.setCursor(Qt.PointingHandCursor)
        test_groq_btn.setStyleSheet(self._test_btn_style())
        test_groq_btn.clicked.connect(self._test_groq_key)
        groq_key_row.addWidget(test_groq_btn)
        groq_layout.addLayout(groq_key_row)

        self.groq_status = QLabel("")
        self.groq_status.setStyleSheet("font-size: 11px;")
        groq_layout.addWidget(self.groq_status)

        self.groq_model_combo = self._setup_model_combo("groq")
        groq_model_row = self._create_model_selection_row("groq", self.groq_model_combo)
        groq_layout.addLayout(groq_model_row)

        layout.addWidget(groq_card)

        # ──────────────────────────────────────────────────
        # 3. OpenRouter Card (50+ Frontier & Open Models)
        # ──────────────────────────────────────────────────
        or_badges = [
            ("🌐 50+ Models", "#38bdf8", "rgba(56, 189, 248, 0.15)", "rgba(56, 189, 248, 0.4)"),
            ("DeepSeek • Claude • GPT-4", "#a855f7", "rgba(168, 85, 247, 0.15)", "rgba(168, 85, 247, 0.4)")
        ]
        or_card, or_layout = self._create_provider_card(
            "🌐", "OpenRouter", "Unified model gateway",
            badges=or_badges,
            how_to_step="1. Click '🔗 Get Key' at openrouter.ai  ➔  2. Paste key below  ➔  3. Click '⚡ Test & Connect'"
        )

        or_key_row = QHBoxLayout()
        or_key_row.setSpacing(6)
        self.openrouter_input, or_container = self._create_secure_input_row("sk-or-v1-...", "https://openrouter.ai/keys")
        or_key_row.addWidget(or_container, 1)
        test_or_btn = QPushButton("⚡ Test && Connect")
        test_or_btn.setFixedWidth(120)
        test_or_btn.setCursor(Qt.PointingHandCursor)
        test_or_btn.setStyleSheet(self._test_btn_style())
        test_or_btn.clicked.connect(self._test_openrouter_key)
        or_key_row.addWidget(test_or_btn)
        or_layout.addLayout(or_key_row)

        self.openrouter_status = QLabel("")
        self.openrouter_status.setStyleSheet("font-size: 11px;")
        or_layout.addWidget(self.openrouter_status)

        self.openrouter_model_combo = self._setup_model_combo("openrouter")
        or_model_row = self._create_model_selection_row("openrouter", self.openrouter_model_combo)
        or_layout.addLayout(or_model_row)

        layout.addWidget(or_card)

        # ──────────────────────────────────────────────────
        # 4. NVIDIA NIM Card (High-Performance GPU Models)
        # ──────────────────────────────────────────────────
        nv_badges = [
            ("🟢 1000 Free Credits", "#00D1FF", "rgba(0, 209, 255, 0.15)", "rgba(0, 209, 255, 0.4)"),
            ("GPU Accelerated", "#10b981", "rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.4)")
        ]
        nv_card, nv_layout = self._create_provider_card(
            "🟢", "NVIDIA NIM", "Enterprise GPU models",
            badges=nv_badges,
            how_to_step="1. Click '🔗 Get Key' at build.nvidia.com  ➔  2. Paste key below  ➔  3. Click '⚡ Test & Connect'"
        )

        nv_key_row = QHBoxLayout()
        nv_key_row.setSpacing(6)
        self.nvidia_input, nv_container = self._create_secure_input_row("nvapi-...", "https://build.nvidia.com/")
        nv_key_row.addWidget(nv_container, 1)
        test_nv_btn = QPushButton("⚡ Test && Connect")
        test_nv_btn.setFixedWidth(120)
        test_nv_btn.setCursor(Qt.PointingHandCursor)
        test_nv_btn.setStyleSheet(self._test_btn_style())
        test_nv_btn.clicked.connect(self._test_nvidia_key)
        nv_key_row.addWidget(test_nv_btn)
        nv_layout.addLayout(nv_key_row)

        self.nvidia_status = QLabel("")
        self.nvidia_status.setStyleSheet("font-size: 11px;")
        nv_layout.addWidget(self.nvidia_status)

        self.nvidia_model_combo = self._setup_model_combo("nvidia")
        nv_model_row = self._create_model_selection_row("nvidia", self.nvidia_model_combo)
        nv_layout.addLayout(nv_model_row)

        layout.addWidget(nv_card)

        # ──────────────────────────────────────────────────
        # 5. Tavily Search Card
        # ──────────────────────────────────────────────────
        tav_badges = [("Live Web Search", "#38bdf8", "rgba(56, 189, 248, 0.15)", "rgba(56, 189, 248, 0.4)")]
        tav_card, tav_layout = self._create_provider_card(
            "🔍", "Tavily Search", "Real-time internet evidence extraction",
            badges=tav_badges,
            how_to_step="Enables real-time citations & live internet data extraction in chat."
        )

        tav_key_row = QHBoxLayout()
        tav_key_row.setSpacing(6)
        self.tavily_input, tav_container = self._create_secure_input_row("tvly-...", "https://app.tavily.com/")
        tav_key_row.addWidget(tav_container, 1)
        test_tav_btn = QPushButton("⚡ Test Connection")
        test_tav_btn.setFixedWidth(120)
        test_tav_btn.setCursor(Qt.PointingHandCursor)
        test_tav_btn.setStyleSheet(self._test_btn_style())
        test_tav_btn.clicked.connect(self._test_tavily_key)
        tav_key_row.addWidget(test_tav_btn)
        tav_layout.addLayout(tav_key_row)

        self.tavily_status = QLabel("")
        self.tavily_status.setStyleSheet("font-size: 11px;")
        tav_layout.addWidget(self.tavily_status)

        layout.addWidget(tav_card)

        # ──────────────────────────────────────────────────
        # 6. GitHub Token Card
        # ──────────────────────────────────────────────────
        gh_badges = [("Repository Access", "#94A3B8", "rgba(143, 160, 181, 0.12)", "rgba(143, 160, 181, 0.3)")]
        gh_card, gh_layout = self._create_provider_card(
            "🐙", "GitHub Token", "Repository inspection & code management",
            badges=gh_badges,
            how_to_step="Optional. Used to fetch public and private repo contents and PRs."
        )

        gh_key_row = QHBoxLayout()
        gh_key_row.setSpacing(6)
        self.github_input, gh_container = self._create_secure_input_row("ghp_...", "https://github.com/settings/tokens")
        gh_key_row.addWidget(gh_container, 1)
        gh_layout.addLayout(gh_key_row)

        layout.addWidget(gh_card)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _test_btn_style(self) -> str:
        """Returns the stylesheet for test/scan buttons."""
        return """
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.28);
                border-color: #00D1FF;
            }
        """

    def _test_openrouter_key(self):
        key = self.openrouter_input.text().strip()
        if not key:
            self.openrouter_status.setText("⚠️ Please enter or paste your OpenRouter key first.")
            self.openrouter_status.setStyleSheet("color: #ffb84d;")
            return
        self.openrouter_status.setText("⏳ Connecting and discovering models...")
        self.openrouter_status.setStyleSheet("color: #38bdf8;")
        self.openrouter_status.repaint()
        try:
            models, quota = ModelScanner.scan_openrouter(key)
            if models or quota:
                self._update_combo(self.openrouter_model_combo, [m["model_name"] for m in models])
                rem_info = ""
                if quota and quota.get("remaining_amount") is not None:
                    rem_info = f" • ${quota['remaining_amount']:.2f} credit remaining"
                self.openrouter_status.setText(f"✅ Connected! {len(models)} models ready{rem_info}")
                self.openrouter_status.setStyleSheet("color: #00D1FF; font-weight: 600;")
            else:
                self.openrouter_status.setText("❌ Connection failed. Check that your key has no extra spaces.")
                self.openrouter_status.setStyleSheet("color: #ff5c77;")
        except Exception as e:
            self.openrouter_status.setText(f"❌ Connection error: {e}")
            self.openrouter_status.setStyleSheet("color: #ff5c77;")

    def _test_groq_key(self):
        key = self.groq_input.text().strip()
        if not key:
            self.groq_status.setText("⚠️ Please enter or paste your Groq key first.")
            self.groq_status.setStyleSheet("color: #ffb84d;")
            return
        self.groq_status.setText("⏳ Connecting to Groq (Free Tier)...")
        self.groq_status.setStyleSheet("color: #38bdf8;")
        self.groq_status.repaint()
        try:
            models = ModelScanner.scan_groq(key)
            if models:
                self._update_combo(self.groq_model_combo, [m["model_name"] for m in models])
                self.groq_status.setText(f"✅ Connected! {len(models)} models ready (Groq Free Tier active)")
                self.groq_status.setStyleSheet("color: #00D1FF; font-weight: 600;")
            else:
                self.groq_status.setText("❌ Connection failed. Verify your key from console.groq.com/keys")
                self.groq_status.setStyleSheet("color: #ff5c77;")
        except Exception as e:
            self.groq_status.setText(f"❌ Connection error: {e}")
            self.groq_status.setStyleSheet("color: #ff5c77;")

    def _test_gemini_key(self):
        key = self.gemini_input.text().strip()
        if not key:
            self.gemini_status.setText("⚠️ Please enter or paste your Gemini key first.")
            self.gemini_status.setStyleSheet("color: #ffb84d;")
            return
        self.gemini_status.setText("⏳ Connecting to Google AI Studio...")
        self.gemini_status.setStyleSheet("color: #38bdf8;")
        self.gemini_status.repaint()
        try:
            models = ModelScanner.scan_gemini(key)
            if models:
                self._update_combo(self.gemini_model_combo, [m["model_name"] for m in models])
                self.gemini_status.setText(f"✅ Connected! {len(models)} models ready (Gemini Free Tier active)")
                self.gemini_status.setStyleSheet("color: #00D1FF; font-weight: 600;")
            else:
                self.gemini_status.setText("❌ Connection failed. Check key at aistudio.google.com/app/apikey")
                self.gemini_status.setStyleSheet("color: #ff5c77;")
        except Exception as e:
            self.gemini_status.setText(f"❌ Connection error: {e}")
            self.gemini_status.setStyleSheet("color: #ff5c77;")

    def _test_nvidia_key(self):
        key = self.nvidia_input.text().strip()
        if not key:
            self.nvidia_status.setText("⚠️ Please enter or paste your NVIDIA key first.")
            self.nvidia_status.setStyleSheet("color: #ffb84d;")
            return
        self.nvidia_status.setText("⏳ Connecting to NVIDIA NIM...")
        self.nvidia_status.setStyleSheet("color: #38bdf8;")
        self.nvidia_status.repaint()
        try:
            models = ModelScanner.scan_nvidia(key)
            if models:
                self._update_combo(self.nvidia_model_combo, [m["model_name"] for m in models])
                quota = self.db.get_provider_quota("nvidia") or {}
                rem_cr = quota.get("remaining_amount", 1000)
                self.nvidia_status.setText(f"✅ Connected! {len(models)} models ready • {int(rem_cr)} free credits left")
                self.nvidia_status.setStyleSheet("color: #00D1FF; font-weight: 600;")
            else:
                self.nvidia_status.setText("❌ Connection failed. Check key at build.nvidia.com")
                self.nvidia_status.setStyleSheet("color: #ff5c77;")
        except Exception as e:
            self.nvidia_status.setText(f"❌ Connection error: {e}")
            self.nvidia_status.setStyleSheet("color: #ff5c77;")

    def _scan_all_models(self):
        """Scans all configured providers, updates dropdowns and reports total models found."""
        self.status_lbl.setText("🔍 Scanning all providers for authorized models and quotas...")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 600;")
        self.status_lbl.repaint()

        total = 0
        or_key = self.openrouter_input.text().strip()
        if or_key:
            or_m, _ = ModelScanner.scan_openrouter(or_key)
            if or_m:
                total += len(or_m)
                self._update_combo(self.openrouter_model_combo, [m["model_name"] for m in or_m])
                self.openrouter_status.setText(f"✅ {len(or_m)} models")
                self.openrouter_status.setStyleSheet("color: #00D1FF;")

        g_key = self.groq_input.text().strip()
        if g_key:
            g_m = ModelScanner.scan_groq(g_key)
            if g_m:
                total += len(g_m)
                self._update_combo(self.groq_model_combo, [m["model_name"] for m in g_m])
                self.groq_status.setText(f"✅ {len(g_m)} models")
                self.groq_status.setStyleSheet("color: #00D1FF;")

        gem_key = self.gemini_input.text().strip()
        if gem_key:
            gem_m = ModelScanner.scan_gemini(gem_key)
            if gem_m:
                total += len(gem_m)
                self._update_combo(self.gemini_model_combo, [m["model_name"] for m in gem_m])
                self.gemini_status.setText(f"✅ {len(gem_m)} models")
                self.gemini_status.setStyleSheet("color: #00D1FF;")

        nv_key = self.nvidia_input.text().strip()
        if nv_key:
            nv_m = ModelScanner.scan_nvidia(nv_key)
            if nv_m:
                total += len(nv_m)
                self._update_combo(self.nvidia_model_combo, [m["model_name"] for m in nv_m])
                self.nvidia_status.setText(f"✅ {len(nv_m)} models")
                self.nvidia_status.setStyleSheet("color: #00D1FF;")

        ol_url = self.ollama_url_input.text().strip() or "http://127.0.0.1:11434"
        ol_m = ModelScanner.scan_ollama(ol_url)
        if ol_m:
            total += len(ol_m)
            if hasattr(self, "ollama_model_combo"):
                self._update_combo(self.ollama_model_combo, [m["model_name"] for m in ol_m])

        self.status_lbl.setText(f"✅ Model scan complete! Found {total} available models across all providers.")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")

    def _test_tavily_key(self):
        key = self.tavily_input.text().strip()
        if not key:
            self.tavily_status.setText("⚠️ Enter key first")
            self.tavily_status.setStyleSheet("color: #ffb84d;")
            return
        try:
            r = requests.post("https://api.tavily.com/search", json={"api_key": key, "query": "test", "max_results": 1}, timeout=8)
            if r.status_code == 200:
                self.tavily_status.setText("✅ Connected!")
                self.tavily_status.setStyleSheet("color: #00D1FF;")
            else:
                self.tavily_status.setText(f"❌ Error {r.status_code}")
                self.tavily_status.setStyleSheet("color: #ff5c77;")
        except Exception:
            self.tavily_status.setText("❌ Connection failed")
            self.tavily_status.setStyleSheet("color: #ff5c77;")

    def _create_local_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # ──────────────────────────────────────────────────
        # Ollama Card (100% Free & Offline)
        # ──────────────────────────────────────────────────
        ol_badges = [
            ("🟢 100% Free Forever", "#00D1FF", "rgba(0, 209, 255, 0.15)", "rgba(0, 209, 255, 0.4)"),
            ("🔒 Completely Offline & Private", "#38bdf8", "rgba(56, 189, 248, 0.15)", "rgba(56, 189, 248, 0.4)"),
            ("No API Key Needed", "#a855f7", "rgba(168, 85, 247, 0.15)", "rgba(168, 85, 247, 0.4)")
        ]
        ol_card, ol_layout = self._create_provider_card(
            "💻", "Local Ollama AI", "Runs directly on your computer",
            badges=ol_badges,
            how_to_step="1. Download Ollama from ollama.com  ➔  2. Click '🚀 Start Ollama'  ➔  3. Select your local model"
        )

        ollama_row = QHBoxLayout()
        ollama_row.setSpacing(8)
        self.ollama_url_input = QLineEdit()
        self.ollama_url_input.setPlaceholderText("http://127.0.0.1:11434")
        ollama_row.addWidget(self.ollama_url_input, 1)

        test_ollama_btn = QPushButton("⚡ Test Connection")
        test_ollama_btn.setCursor(Qt.PointingHandCursor)
        test_ollama_btn.setStyleSheet(self._test_btn_style())
        test_ollama_btn.clicked.connect(self._test_ollama_connection)
        ollama_row.addWidget(test_ollama_btn)

        start_ollama_btn = QPushButton("🚀 Start Ollama")
        start_ollama_btn.setCursor(Qt.PointingHandCursor)
        start_ollama_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.28);
                border-color: #38bdf8;
            }
        """)
        start_ollama_btn.clicked.connect(self._start_ollama_manually)
        ollama_row.addWidget(start_ollama_btn)

        ol_layout.addLayout(ollama_row)

        self.ollama_status_lbl = QLabel("Ollama status: Checking...")
        self.ollama_status_lbl.setStyleSheet("color: #a8afc2; font-size: 11px;")
        ol_layout.addWidget(self.ollama_status_lbl)

        # Ollama Model selection row with '+ Add Custom Model'
        self.ollama_model_combo = self._setup_model_combo("ollama")
        ollama_model_row = self._create_model_selection_row("ollama", self.ollama_model_combo)
        ol_layout.addLayout(ollama_model_row)

        layout.addWidget(ol_card)

        # Check Ollama right now
        self._test_ollama_connection()

        # ──────────────────────────────────────────────────
        # Black Forest Labs FLUX.1 Image Studio
        # ──────────────────────────────────────────────────
        from engine.providers.image_provider import ImageProvider
        img_prov = ImageProvider()
        rem_credits = img_prov.get_remaining_credits()

        flux_badges = [
            ("🟢 25 Free Credits", "#00D1FF", "rgba(0, 209, 255, 0.15)", "rgba(0, 209, 255, 0.4)"),
            ("✨ Black Forest FLUX.1", "#38bdf8", "rgba(56, 189, 248, 0.15)", "rgba(56, 189, 248, 0.4)")
        ]
        flux_card, flux_layout = self._create_provider_card(
            "🎨", "Black Forest Labs FLUX.1", "1024×1024 Neural Image Generation Engine",
            badges=flux_badges,
            how_to_step="Free credits checked automatically before every image generation."
        )

        credit_row = QHBoxLayout()
        credit_row.setSpacing(10)
        self.image_credit_lbl = QLabel(f"💳 Remaining Free Credits: <b>{rem_credits}</b> / 25")
        self.image_credit_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        credit_row.addWidget(self.image_credit_lbl)

        credit_row.addStretch()

        refill_btn = QPushButton("🔄 Refill Free Credits (+25)")
        refill_btn.setCursor(Qt.PointingHandCursor)
        refill_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.25);
                border-color: #00D1FF;
            }
        """)
        refill_btn.clicked.connect(self._refill_image_credits)
        credit_row.addWidget(refill_btn)
        flux_layout.addLayout(credit_row)

        sd_opt_lbl = QLabel("Optional Local Automatic1111 URL (leave as default if using Black Forest FLUX.1):")
        sd_opt_lbl.setStyleSheet("color: #626c85; font-size: 11px; margin-top: 6px;")
        flux_layout.addWidget(sd_opt_lbl)

        sd_row = QHBoxLayout()
        self.sd_url_input = QLineEdit()
        self.sd_url_input.setPlaceholderText("http://127.0.0.1:7860")
        sd_row.addWidget(self.sd_url_input, 1)
        flux_layout.addLayout(sd_row)

        layout.addWidget(flux_card)

        layout.addStretch()
        return widget

    def _start_ollama_manually(self):
        url = self.ollama_url_input.text().strip() or "http://127.0.0.1:11434"
        self.ollama_status_lbl.setText("Starting Ollama background process...")
        success, msg = start_ollama_service(url)
        if success:
            models = get_installed_ollama_models(url)
            self._update_ollama_models_dropdown(models)
            self.ollama_status_lbl.setText(f"✅ Running! Available models: {', '.join(models)}")
            self.ollama_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11px;")
        else:
            self.ollama_status_lbl.setText(f"❌ {msg}")
            self.ollama_status_lbl.setStyleSheet("color: #ff5c77; font-size: 11px;")

    def _update_ollama_models_dropdown(self, models: list):
        if not hasattr(self, "ollama_model_combo"):
            return
        curr = self.ollama_model_combo.currentText()
        for m in models:
            if self.ollama_model_combo.findText(m) == -1:
                self.ollama_model_combo.addItem(m)
        if curr:
            self.ollama_model_combo.setCurrentText(curr)

    def _refill_image_credits(self):
        """Refills free credits for Black Forest Labs FLUX.1."""
        from engine.providers.image_provider import ImageProvider
        img_prov = ImageProvider()
        new_balance = img_prov.refill_credits(25)
        if hasattr(self, "image_credit_lbl"):
            self.image_credit_lbl.setText(f"💳 Remaining Free Credits: <b>{new_balance}</b> / 25")
        QMessageBox.information(
            self,
            "Credits Refilled",
            f"Successfully refilled free image credits!\n\nYou now have {new_balance} free credits available for Black Forest Labs FLUX.1."
        )

    def _create_automations_tab(self) -> QWidget:
        """Tab for configuring Gmail integration, App Passwords, and automation preferences."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Info banner
        info_box = QFrame()
        info_box.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 209, 255, 0.06);
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        info_layout = QVBoxLayout(info_box)
        info_layout.setSpacing(4)
        title = QLabel("🤖 Sage AI Autonomous Email & Task Assistant")
        title.setStyleSheet("color: #00D1FF; font-size: 13px; font-weight: 700;")
        info_layout.addWidget(title)

        desc = QLabel(
            "Empower Sage AI to scan your inbox for unread messages, generate contextual intelligent replies,\n"
            "and automate desktop tasks. Every outbound email strictly requires your explicit permission in\n"
            "a Human-in-the-Loop review modal before any transmission."
        )
        desc.setStyleSheet("color: #a8afc2; font-size: 11px;")
        info_layout.addWidget(desc)
        layout.addWidget(info_box)

        # Sandbox mode toggle
        self.gmail_sandbox_toggle = QCheckBox("🛡️ Safe Sandbox Mode (Simulate incoming emails && safe testing)")
        self.gmail_sandbox_toggle.setChecked(True)
        self.gmail_sandbox_toggle.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 600;")
        layout.addWidget(self.gmail_sandbox_toggle)

        sandbox_desc = QLabel(
            "Recommended for testing! Uses simulated incoming emails (Sarah Connor, Alex Rivers, GitHub) so you can\n"
            "test smart AI drafting and the permission authorization flow without touching your real mailbox."
        )
        sandbox_desc.setStyleSheet("color: #626c85; font-size: 11px; margin-left: 20px;")
        layout.addWidget(sandbox_desc)

        # Grid for credentials
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)

        row = 0
        grid.addWidget(QLabel("Gmail Address:"), row, 0)
        self.gmail_address_input = QLineEdit()
        self.gmail_address_input.setPlaceholderText("your.email@gmail.com")
        grid.addWidget(self.gmail_address_input, row, 1)
        row += 1

        grid.addWidget(QLabel("Google App Password:"), row, 0)
        self.gmail_password_input, pw_container = self._create_secure_input_row(
            "16-char App Password (e.g. abcd efgh ijkl mnop)",
            "https://myaccount.google.com/apppasswords"
        )
        grid.addWidget(pw_container, row, 1)
        row += 1

        app_pw_hint = QLabel("💡 Note: Generate a 16-character App Password at myaccount.google.com/apppasswords (requires 2-Step Verification).")
        app_pw_hint.setStyleSheet("color: #626c85; font-size: 10px;")
        grid.addWidget(app_pw_hint, row, 1)
        row += 1

        grid.addWidget(QLabel("IMAP Host:"), row, 0)
        self.gmail_imap_input = QLineEdit("imap.gmail.com")
        grid.addWidget(self.gmail_imap_input, row, 1)
        row += 1

        grid.addWidget(QLabel("SMTP Host:"), row, 0)
        self.gmail_smtp_input = QLineEdit("smtp.gmail.com")
        grid.addWidget(self.gmail_smtp_input, row, 1)
        row += 1

        layout.addLayout(grid)

        # Test connection row
        test_row = QHBoxLayout()
        test_mail_btn = QPushButton("🔍 Test Mail Connection")
        test_mail_btn.setCursor(Qt.PointingHandCursor)
        test_mail_btn.setStyleSheet("""
            QPushButton {
                background-color: #162033;
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.4);
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.18);
                border-color: #00D1FF;
            }
        """)
        test_mail_btn.clicked.connect(self._test_gmail_connection)
        test_row.addWidget(test_mail_btn)

        self.mail_status_lbl = QLabel("")
        self.mail_status_lbl.setStyleSheet("font-size: 11px;")
        test_row.addWidget(self.mail_status_lbl, 1)
        layout.addLayout(test_row)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _test_gmail_connection(self):
        if self.gmail_sandbox_toggle.isChecked():
            self.mail_status_lbl.setText("✅ Safe Sandbox Active: Ready to simulate 3 unread emails with permission checks.")
            self.mail_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11px;")
            return

        user = self.gmail_address_input.text().strip()
        pw = self.gmail_password_input.text().strip().replace(" ", "")
        imap_host = self.gmail_imap_input.text().strip() or "imap.gmail.com"

        if not user or not pw:
            self.mail_status_lbl.setText("⚠️ Please enter both your Gmail address and Google App Password.")
            self.mail_status_lbl.setStyleSheet("color: #ffb84d; font-size: 11px;")
            return

        self.mail_status_lbl.setText("Connecting to IMAP...")
        self.mail_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.mail_status_lbl.repaint()

        import imaplib
        try:
            mail = imaplib.IMAP4_SSL(imap_host, 993, timeout=8)
            mail.login(user, pw)
            mail.logout()
            self.mail_status_lbl.setText("✅ Authentication successful! Gmail IMAP is ready.")
            self.mail_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11px;")
        except Exception as e:
            self.mail_status_lbl.setText(f"❌ Connection error: {e}")
            self.mail_status_lbl.setStyleSheet("color: #ff5c77; font-size: 11px;")

    def _create_behavior_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        self.mem0_toggle = QCheckBox("Enable Long-term Memory (Mem0 Integration)")
        self.mem0_toggle.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.mem0_toggle)

        mem0_desc = QLabel("Stores personalized preferences across chat sessions.")
        mem0_desc.setStyleSheet("color: #626c85; font-size: 11px; margin-left: 20px;")
        layout.addWidget(mem0_desc)

        self.fast_mode_toggle = QCheckBox("Enable Fast Mode (Prioritize Low-Latency Models)")
        self.fast_mode_toggle.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.fast_mode_toggle)

        fast_desc = QLabel("Directs queries first to Groq or local cache before larger reasoning models.")
        fast_desc.setStyleSheet("color: #626c85; font-size: 11px; margin-left: 20px;")
        layout.addWidget(fast_desc)

        self.cascade_toggle = QCheckBox("Enable Automatic Waterfall Fallback")
        self.cascade_toggle.setChecked(True)
        self.cascade_toggle.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.cascade_toggle)

        cascade_desc = QLabel("Automatically attempts next provider if primary encounters rate limit or network error.")
        cascade_desc.setStyleSheet("color: #626c85; font-size: 11px; margin-left: 20px;")
        layout.addWidget(cascade_desc)

        layout.addStretch()
        return widget

    def _load_settings(self):
        self.openrouter_input.setText(self.db.get_setting("openrouter_api_key", ""))
        self.groq_input.setText(self.db.get_setting("groq_api_key", ""))
        self.gemini_input.setText(self.db.get_setting("gemini_api_key", ""))
        self.nvidia_input.setText(self.db.get_setting("nvidia_api_key", ""))
        self.tavily_input.setText(self.db.get_setting("tavily_api_key", ""))
        self.github_input.setText(self.db.get_setting("github_token", ""))
        self.ollama_url_input.setText(self.db.get_setting("ollama_base_url", "http://127.0.0.1:11434"))
        self.sd_url_input.setText(self.db.get_setting("sd_base_url", "http://127.0.0.1:7860"))
        self.mem0_toggle.setChecked(self.db.get_setting("mem0_enabled", "false") == "true")
        self.fast_mode_toggle.setChecked(self.db.get_setting("fast_mode", "false") == "true")
        self.cascade_toggle.setChecked(self.db.get_setting("cascade_enabled", "true") == "true")

        # Load Gmail / Automations
        self.gmail_address_input.setText(self.db.get_setting("gmail_address", ""))
        self.gmail_password_input.setText(self.db.get_setting("gmail_app_password", ""))
        self.gmail_sandbox_toggle.setChecked(self.db.get_setting("gmail_sandbox_mode", "true") == "true")
        self.gmail_imap_input.setText(self.db.get_setting("gmail_imap_host", "imap.gmail.com"))
        self.gmail_smtp_input.setText(self.db.get_setting("gmail_smtp_host", "smtp.gmail.com"))

        # Load Provider Models
        openrouter_model = self.db.get_setting("openrouter_model", DEFAULT_MODELS.get("openrouter_coding", "qwen/qwen-2.5-coder-32b-instruct"))
        if self.openrouter_model_combo.findText(openrouter_model) == -1:
            self.openrouter_model_combo.addItem(openrouter_model)
        self.openrouter_model_combo.setCurrentText(openrouter_model)

        groq_model = self.db.get_setting("groq_model", DEFAULT_MODELS.get("groq_chat", "llama-3.3-70b-versatile"))
        if self.groq_model_combo.findText(groq_model) == -1:
            self.groq_model_combo.addItem(groq_model)
        self.groq_model_combo.setCurrentText(groq_model)

        gemini_model = self.db.get_setting("gemini_model", DEFAULT_MODELS.get("gemini_chat", "gemini-1.5-flash"))
        if self.gemini_model_combo.findText(gemini_model) == -1:
            self.gemini_model_combo.addItem(gemini_model)
        self.gemini_model_combo.setCurrentText(gemini_model)

        nvidia_model = self.db.get_setting("nvidia_model", DEFAULT_MODELS.get("nvidia_chat", "meta/llama-3.1-70b-instruct"))
        if self.nvidia_model_combo.findText(nvidia_model) == -1:
            self.nvidia_model_combo.addItem(nvidia_model)
        self.nvidia_model_combo.setCurrentText(nvidia_model)

        ollama_model = self.db.get_setting("ollama_model", DEFAULT_MODELS.get("ollama_chat", "llama3.2:latest"))
        if hasattr(self, "ollama_model_combo"):
            if self.ollama_model_combo.findText(ollama_model) == -1:
                self.ollama_model_combo.addItem(ollama_model)
            self.ollama_model_combo.setCurrentText(ollama_model)

    def _save_settings(self):
        self.db.set_setting("openrouter_api_key", self.openrouter_input.text().strip())
        self.db.set_setting("groq_api_key", self.groq_input.text().strip())
        self.db.set_setting("gemini_api_key", self.gemini_input.text().strip())
        self.db.set_setting("nvidia_api_key", self.nvidia_input.text().strip())
        self.db.set_setting("tavily_api_key", self.tavily_input.text().strip())
        self.db.set_setting("github_token", self.github_input.text().strip())
        self.db.set_setting("ollama_base_url", self.ollama_url_input.text().strip() or "http://127.0.0.1:11434")
        self.db.set_setting("sd_base_url", self.sd_url_input.text().strip() or "http://127.0.0.1:7860")
        self.db.set_setting("mem0_enabled", "true" if self.mem0_toggle.isChecked() else "false")
        self.db.set_setting("fast_mode", "true" if self.fast_mode_toggle.isChecked() else "false")
        self.db.set_setting("cascade_enabled", "true" if self.cascade_toggle.isChecked() else "false")

        # Save Gmail / Automations
        self.db.set_setting("gmail_address", self.gmail_address_input.text().strip())
        self.db.set_setting("gmail_app_password", self.gmail_password_input.text().strip())
        self.db.set_setting("gmail_sandbox_mode", "true" if self.gmail_sandbox_toggle.isChecked() else "false")
        self.db.set_setting("gmail_imap_host", self.gmail_imap_input.text().strip() or "imap.gmail.com")
        self.db.set_setting("gmail_smtp_host", self.gmail_smtp_input.text().strip() or "smtp.gmail.com")

        # Save Provider Models
        self.db.set_setting("openrouter_model", self.openrouter_model_combo.currentText().strip())
        self.db.set_setting("groq_model", self.groq_model_combo.currentText().strip())
        self.db.set_setting("gemini_model", self.gemini_model_combo.currentText().strip())
        self.db.set_setting("nvidia_model", self.nvidia_model_combo.currentText().strip())
        if hasattr(self, "ollama_model_combo"):
            self.db.set_setting("ollama_model", self.ollama_model_combo.currentText().strip())

        self.status_lbl.setText("✓ Settings successfully saved to SQLite!")
        self.accept()

    def _test_ollama_connection(self):
        url = self.ollama_url_input.text().strip() or "http://127.0.0.1:11434"
        if is_ollama_running(url):
            models = get_installed_ollama_models(url)
            self._update_ollama_models_dropdown(models)
            model_info = f"Online! Detected {len(models)} model(s): {', '.join(models)}" if models else "Online (No models installed yet)"
            self.ollama_status_lbl.setText(f"✅ {model_info}")
            self.ollama_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11px;")
        else:
            self.ollama_status_lbl.setText("⚠️ Ollama is stopped. Click '🚀 Start Ollama' to launch it.")
            self.ollama_status_lbl.setStyleSheet("color: #ffb84d; font-size: 11px;")
