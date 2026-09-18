"""
Add & Connect AI Models View Component for Sage AI (Lunar Engine).
In-window provider setup page (replaces popup dialog) providing:
- 100% Free Tier Quick-Start Guide
- Cloud Model Cards (Groq, Gemini, NVIDIA, OpenRouter) with 1-click test & connect
- Local Ollama Offline Setup
- In-window 'Back to Chat' navigation
"""
import webbrowser
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QFrame, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal

from database.db_manager import get_db
from engine.model_scanner import ModelScanner
from engine.ollama_manager import start_ollama_service, is_ollama_running, get_installed_ollama_models


class AddModelsView(QWidget):
    """Integrated in-window view for adding and testing AI models and provider keys."""

    models_updated = Signal()
    back_to_chat_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = get_db()
        self.status_labels: Dict[str, QLabel] = {}
        self.key_inputs: Dict[str, QLineEdit] = {}

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
                border: 1px solid rgba(0, 209, 255, 0.3);
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(0, 209, 255, 0.15);
            }
        """)
        back_btn.clicked.connect(self.back_to_chat_requested.emit)
        header.addWidget(back_btn)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("✨ Add & Connect AI Models")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 18px; font-weight: 800; letter-spacing: 0.3px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Connect 100% free cloud models or private local Ollama in 30 seconds")
        sub_lbl.setStyleSheet("color: #717d98; font-size: 11.5px;")
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()
        main_layout.addLayout(header)

        # Quick-Start Free Guide Banner
        free_banner = QFrame()
        free_banner.setObjectName("freeBanner")
        free_banner.setStyleSheet("""
            QFrame#freeBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #162033, stop:1 #162033);
                border: 1px solid rgba(0, 209, 255, 0.3);
                border-left: 4px solid #00D1FF;
                border-radius: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        fb_layout = QHBoxLayout(free_banner)
        fb_layout.setContentsMargins(16, 12, 16, 12)
        fb_layout.setSpacing(14)

        b_icon = QLabel("🚀")
        b_icon.setStyleSheet("font-size: 22px; border: none; background: transparent;")
        fb_layout.addWidget(b_icon)

        b_text = QLabel(
            "<b>Quick Start — 100% Free AI Options (No Credit Card Required):</b><br>"
            "• <b>Google Gemini</b>: Free tier with fast 1.5 Flash models.<br>"
            "• <b>Groq</b>: Free tier with ultra-low latency LLaMA 3.3 70B.<br>"
            "• <b>Local Ollama</b>: 100% free & private on your computer without internet."
        )
        b_text.setStyleSheet("color: #d1d9ea; font-size: 11.5px; line-height: 1.4; border: none; background: transparent;")
        fb_layout.addWidget(b_text, 1)

        main_layout.addWidget(free_banner)

        # Tabs: Cloud Providers vs. Local Ollama
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(0, 209, 255, 0.18);
                background-color: #0A0F14;
                border-radius: 12px;
                padding: 14px;
            }
            QTabBar::tab {
                background-color: #0A0F14;
                color: #8b99ad;
                border: 1px solid #273449;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 22px;
                margin-right: 4px;
                font-size: 12.5px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0A0F14;
                color: #00D1FF;
                border-bottom: 2px solid #00D1FF;
                font-weight: 700;
            }
        """)

        tabs.addTab(self._create_cloud_tab(), "🌐  Cloud AI Providers")
        tabs.addTab(self._create_local_tab(), "🔒  Local Offline Ollama")
        main_layout.addWidget(tabs, 1)

    def _create_cloud_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(14)

        providers = [
            (
                "groq",
                "Groq (Lightning Fast)",
                "[🟢 100% Free Tier] [⚡ Ultra Fast]",
                "https://console.groq.com/keys",
                "Free tier with 30 requests/min. Powers LLaMA 3.3 70B with sub-second latency.",
                "gsk_..."
            ),
            (
                "cerebras",
                "Cerebras",
                "[🏎️ 2,000+ Tokens/Sec] [⚡ Wafer-Scale]",
                "https://cloud.cerebras.ai/",
                "Ultra-fast hardware acceleration for LLaMA 3.1 & 3.3 models with instant response times.",
                "csk-..."
            ),
            (
                "nvidia",
                "NVIDIA NIM",
                "[⭐ 1,000 Free Credits] [🧠 TensorRT]",
                "https://build.nvidia.com/",
                "1,000 free inference credits on registration. Fast TensorRT models.",
                "nvapi-..."
            ),
            (
                "cloudflare",
                "Cloudflare Workers AI",
                "[🟢 Free Daily Allocation] [⚡ Edge Serverless]",
                "https://dash.cloudflare.com/",
                "Run LLaMA 3.3, Mistral, and DeepSeek serverless across Cloudflare's global edge network.",
                "API Token / Bearer ..."
            ),
            (
                "mistral",
                "Mistral AI",
                "[🚀 Frontier & Codestral] [🇫🇷 European Open AI]",
                "https://console.mistral.ai/api-keys/",
                "Access Mistral Large, Codestral coding specialist, and Mixtral models.",
                "sk-..."
            ),
            (
                "huggingface",
                "Hugging Face",
                "[🤗 Serverless Inference] [🌐 Open Models]",
                "https://huggingface.co/settings/tokens",
                "Access open foundation models via the Hugging Face Serverless Router.",
                "hf_..."
            ),
            (
                "cohere",
                "Cohere",
                "[💼 Command R+ Enterprise] [🔍 RAG Specialist]",
                "https://dashboard.cohere.com/api-keys",
                "Enterprise-grade Command R+ and Command R models built for reasoning and search.",
                "..."
            ),
            (
                "gemini",
                "Google Gemini",
                "[🟢 100% Free Tier] [🌟 Recommended]",
                "https://aistudio.google.com/app/apikey",
                "Free tier with generous daily limits for Gemini 1.5 Flash and Pro.",
                "AIzaSy..."
            ),
            (
                "openrouter",
                "OpenRouter",
                "[🟢 Free Models Available] [⚡ Zero Cost]",
                "https://openrouter.ai/keys",
                "Free access to DeepSeek R1, LLaMA 3.3, and Qwen 2.5 Coder without credit card.",
                "sk-or-v1-..."
            ),
        ]

        for p_id, p_name, badges, portal_url, desc, placeholder in providers:
            card = self._build_provider_card(p_id, p_name, badges, portal_url, desc, placeholder)
            layout.addWidget(card)

        scroll.setWidget(container)
        return scroll

    def _build_provider_card(self, p_id: str, p_name: str, badges: str, portal_url: str, desc: str, placeholder: str) -> QFrame:
        card = QFrame()
        card.setObjectName(f"provCard_{p_id}")
        card.setStyleSheet(f"""
            QFrame#provCard_{p_id} {{
                background-color: #162033;
                border: 1px solid #273449;
                border-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(10)

        # Top row: title, badges, get key link
        top_row = QHBoxLayout()
        lbl_title = QLabel(f"<b>{p_name}</b> <span style='color: #00D1FF; font-size: 11px;'>{badges}</span>")
        lbl_title.setStyleSheet("color: #F8FAFC; font-size: 13.5px; border: none; background: transparent;")
        top_row.addWidget(lbl_title)
        top_row.addStretch()

        get_btn = QPushButton("🔗 Get Free API Key ↗")
        get_btn.setCursor(Qt.PointingHandCursor)
        get_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #4f80ff;
                border: none;
                font-size: 11.5px;
                font-weight: 700;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)
        get_btn.clicked.connect(lambda checked=False, u=portal_url: webbrowser.open(u))
        top_row.addWidget(get_btn)
        c_layout.addLayout(top_row)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #717d98; font-size: 11px; border: none; background: transparent;")
        c_layout.addWidget(desc_lbl)

        # Input & action row
        in_row = QHBoxLayout()
        in_row.setSpacing(10)

        saved_key = self.db.get_setting(f"{p_id}_api_key") or ""
        key_edit = QLineEdit(saved_key)
        key_edit.setEchoMode(QLineEdit.Password)
        key_edit.setPlaceholderText(f"Paste your {p_name} API key here ({placeholder})")
        key_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #F8FAFC;
                font-size: 12px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        self.key_inputs[p_id] = key_edit
        in_row.addWidget(key_edit, 1)

        test_btn = QPushButton("⚡ Test && Connect")
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11.5px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        test_btn.clicked.connect(lambda checked=False, pid=p_id: self._test_and_save_key(pid))
        in_row.addWidget(test_btn)
        c_layout.addLayout(in_row)

        # Status label
        st_lbl = QLabel("● Active & Saved" if saved_key else "○ Not configured")
        st_lbl.setStyleSheet(f"color: {'#10b981' if saved_key else '#626c85'}; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        self.status_labels[p_id] = st_lbl
        c_layout.addWidget(st_lbl)

        return card

    def _create_local_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("ollamaCard")
        card.setStyleSheet("""
            QFrame#ollamaCard {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        c_l = QVBoxLayout(card)
        c_l.setContentsMargins(18, 16, 18, 16)
        c_l.setSpacing(12)

        title = QLabel("<b>Local Ollama Engine</b> <span style='color: #00D1FF;'>[100% Offline & Private]</span>")
        title.setStyleSheet("color: #F8FAFC; font-size: 14px;")
        c_l.addWidget(title)

        info = QLabel(
            "Ollama runs large language models entirely on your computer with zero cloud dependency and complete data privacy.<br><br>"
            "<b>Setup Instructions:</b><br>"
            "1. Download and install Ollama from <a href='https://ollama.com' style='color: #4f80ff;'>ollama.com</a>.<br>"
            "2. Open a terminal and pull your preferred model:<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>ollama run llama3.2:3b</code> (fast general chat)<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>ollama run qwen2.5-coder:7b</code> (coding specialist)<br>"
            "3. Ollama automatically serves locally on <code>http://127.0.0.1:11434</code>."
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        info.setStyleSheet("color: #a8b6cd; font-size: 12px; line-height: 1.5;")
        c_l.addWidget(info)

        layout.addWidget(card)

        # Interactive Ollama Controls Card
        ctrl_card = QFrame()
        ctrl_card.setObjectName("ollamaCtrlCard")
        ctrl_card.setStyleSheet("""
            QFrame#ollamaCtrlCard {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.2);
                border-radius: 12px;
            }
        """)
        cc_l = QVBoxLayout(ctrl_card)
        cc_l.setContentsMargins(18, 16, 18, 16)
        cc_l.setSpacing(12)

        ctrl_title = QLabel("<b>Ollama Local Service Control</b>")
        ctrl_title.setStyleSheet("color: #F8FAFC; font-size: 13.5px; border: none; background: transparent;")
        cc_l.addWidget(ctrl_title)

        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        url_lbl = QLabel("Server URL:")
        url_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; border: none; background: transparent;")
        url_row.addWidget(url_lbl)

        self.ollama_url_input = QLineEdit("http://127.0.0.1:11434")
        self.ollama_url_input.setStyleSheet("""
            QLineEdit {
                background-color: #0A0F14;
                border: 1px solid #273449;
                border-radius: 6px;
                color: #F8FAFC;
                font-size: 12px;
                padding: 7px 10px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        url_row.addWidget(self.ollama_url_input, 1)

        self.ollama_start_btn = QPushButton("🚀 Start Ollama")
        self.ollama_start_btn.setCursor(Qt.PointingHandCursor)
        self.ollama_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #00BBE6;
            }
        """)
        self.ollama_start_btn.clicked.connect(self._start_ollama_action)
        url_row.addWidget(self.ollama_start_btn)

        self.ollama_test_btn = QPushButton("⚡ Test")
        self.ollama_test_btn.setCursor(Qt.PointingHandCursor)
        self.ollama_test_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #e2e8f0;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #00D1FF;
                color: #00D1FF;
            }
        """)
        self.ollama_test_btn.clicked.connect(self._test_ollama_action)
        url_row.addWidget(self.ollama_test_btn)
        cc_l.addLayout(url_row)

        self.ollama_status_lbl = QLabel("○ Status: Click 'Start Ollama' to launch or 'Test' to check connection")
        self.ollama_status_lbl.setStyleSheet("color: #94A3B8; font-size: 11.5px; border: none; background: transparent;")
        cc_l.addWidget(self.ollama_status_lbl)

        layout.addWidget(ctrl_card)
        layout.addStretch()
        return tab

    def _start_ollama_action(self):
        url = self.ollama_url_input.text().strip() or "http://127.0.0.1:11434"
        self.ollama_status_lbl.setText("⏳ Starting Ollama background process...")
        self.ollama_status_lbl.setStyleSheet("color: #ffb84d; font-size: 11.5px; font-weight: bold;")
        self.ollama_status_lbl.repaint()
        
        success, msg = start_ollama_service(url)
        if success:
            models = get_installed_ollama_models(url)
            model_info = f" • Models: {', '.join(models)}" if models else " (No models installed yet)"
            self.ollama_status_lbl.setText(f"✅ Running on {url}{model_info}")
            self.ollama_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11.5px; font-weight: bold;")
            self.models_updated.emit()
        else:
            self.ollama_status_lbl.setText(f"❌ {msg}")
            self.ollama_status_lbl.setStyleSheet("color: #ff5c77; font-size: 11.5px;")

    def _test_ollama_action(self):
        url = self.ollama_url_input.text().strip() or "http://127.0.0.1:11434"
        if is_ollama_running(url):
            models = get_installed_ollama_models(url)
            model_info = f" • Models: {', '.join(models)}" if models else " (No models installed yet)"
            self.ollama_status_lbl.setText(f"✅ Ollama is running on {url}{model_info}")
            self.ollama_status_lbl.setStyleSheet("color: #00D1FF; font-size: 11.5px; font-weight: bold;")
        else:
            self.ollama_status_lbl.setText(f"○ Ollama is currently stopped/offline at {url}. Click 'Start Ollama' above.")
            self.ollama_status_lbl.setStyleSheet("color: #94A3B8; font-size: 11.5px;")

    def _test_and_save_key(self, provider_id: str):
        key_edit = self.key_inputs.get(provider_id)
        st_lbl = self.status_labels.get(provider_id)
        if not key_edit or not st_lbl:
            return

        key = key_edit.text().strip()
        setting_key = f"{provider_id}_api_key"
        if not key:
            self.db.set_setting(setting_key, "")
            st_lbl.setText("○ Key removed")
            st_lbl.setStyleSheet("color: #626c85; font-size: 11px;")
            self.models_updated.emit()
            return

        st_lbl.setText("⏳ Testing connection...")
        st_lbl.setStyleSheet("color: #ffb84d; font-size: 11px; font-weight: bold;")
        st_lbl.repaint()

        try:
            success = False
            if provider_id == "gemini":
                res = ModelScanner.scan_gemini(key)
                success = bool(res)
            elif provider_id == "groq":
                res = ModelScanner.scan_groq(key)
                success = bool(res)
            elif provider_id == "cerebras":
                res = ModelScanner.scan_cerebras(key)
                success = bool(res)
            elif provider_id == "nvidia":
                res = ModelScanner.scan_nvidia(key)
                success = bool(res)
            elif provider_id == "cloudflare":
                res = ModelScanner.scan_cloudflare(key)
                success = bool(res)
            elif provider_id == "mistral":
                res = ModelScanner.scan_mistral(key)
                success = bool(res)
            elif provider_id == "huggingface":
                res = ModelScanner.scan_huggingface(key)
                success = bool(res)
            elif provider_id == "cohere":
                res = ModelScanner.scan_cohere(key)
                success = bool(res)
            elif provider_id == "openrouter":
                res, _ = ModelScanner.scan_openrouter(key)
                success = bool(res)

            self.db.set_setting(setting_key, key)
            if success:
                st_lbl.setText("✅ Connected & Saved! Free Tier / Credits active.")
                st_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: bold;")
            else:
                st_lbl.setText("⚠️ Key saved. Models will be verified online.")
                st_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
            self.models_updated.emit()
        except Exception as e:
            self.db.set_setting(setting_key, key)
            st_lbl.setText(f"⚠️ Key saved. ({e})")
            st_lbl.setStyleSheet("color: #ffb84d; font-size: 11px;")
            self.models_updated.emit()
