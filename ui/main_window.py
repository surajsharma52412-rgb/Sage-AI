"""
Main Window for Sage AI.
Coordinates the TopBar, Sidebar, Chat Viewport, Project Agent View, and Settings Modal.
Direct singleton service invocation inside QThread workers with Qt Signal/Slot communication.
"""
import os
import getpass
import time
import logging
from typing import Optional, Any, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QMessageBox, QApplication, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from ui.components.animated_stack import AnimatedStackedWidget

from database.db_manager import get_db
from workers.chat_worker import ChatWorker
from ui.components.message_bubble import (
    extract_thinking, format_markdown_to_html, ThinkingSection, MessageBubble
)
from .components import (
    Sidebar, TopBar, ChatViewport, MessageInputBar, SettingsDialog,
    GeneralSettingsDialog, CodingIdeView, AutomationsView, MultiAgentView, KnowledgeView,
    SettingsView, AddModelsView, AnalyticsView, HomeDashboardView,
    GlobalRankingView
)


class StartupModelTraceWorker(QThread):
    """Background worker that traces and syncs all API key models on application startup."""
    trace_finished = Signal(dict)

    def run(self):
        try:
            from engine.model_scanner import ModelScanner
            result = ModelScanner.trace_and_sync_all_configured_providers()
            self.trace_finished.emit(result)
        except Exception as e:
            logger.warning("Startup model trace encountered an error: %s", e)
            self.trace_finished.emit({
                "error": str(e),
                "total_models": 0,
                "added_free": [],
                "added_paid": [],
                "removed": [],
                "changed": [],
                "scanned_providers": []
            })


class MainWindow(QMainWindow):
    """Primary application window matching the reference sci-fi emerald mockup."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sage AI – Multi-Agentic AI Architecture")
        self.resize(1180, 780)
        self.setMinimumSize(1020, 640)

        # Set Window & Taskbar Icon
        from ui.styles.qss_theme import get_app_icon
        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.db = get_db()
        self.current_session_id: Optional[str] = None
        self.current_worker: Optional[ChatWorker] = None
        self.streaming_bubble: Optional[MessageBubble] = None
        self._in_thinking: bool = False
        self._thinking_buffer: str = ""
        self._response_buffer: str = ""
        self._thinking_start_time: Optional[float] = None

        self._init_ui()
        self._init_sessions()

        # Launch directly into Home section as default
        self._handle_navigation("home")

        # Background trace all API key models on startup (trace additions, removals, changes)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(600, self._start_startup_model_trace)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_has_animated_open", False):
            self._has_animated_open = True
            self._animate_window_open()

    def _animate_window_open(self):
        """Hardware-accelerated window open fade without CPU offscreen rasterization."""
        try:
            self.setWindowOpacity(0.0)
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(160)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._open_anim = anim
            anim.start()
        except Exception:
            self.setWindowOpacity(1.0)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = Sidebar(self)
        self.sidebar.new_chat_requested.connect(self._create_new_chat)
        self.sidebar.nav_changed.connect(self._handle_navigation)
        self.sidebar.profile_clicked.connect(lambda: self._open_general_settings(tab_idx=0))
        self.sidebar.chat_session_selected.connect(self._switch_to_session)
        self.sidebar.chat_session_deleted.connect(self._delete_session)
        self.sidebar.chat_session_renamed.connect(self._rename_session)
        root_layout.addWidget(self.sidebar)

        # 2. Right Main Content Area
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Bar
        self.top_bar = TopBar(right_container)
        self.top_bar.settings_clicked.connect(lambda: self._open_general_settings(tab_idx=0))
        self.top_bar.help_clicked.connect(self._show_help)
        self.top_bar.search_submitted.connect(self._handle_global_search)
        right_layout.addWidget(self.top_bar)

        # Stacked Views with Fluid Page Transition Animations
        self.stack = AnimatedStackedWidget(right_container, duration=150)

        # Page 0: Home / Chat Container with sub-stack
        self.home_container = AnimatedStackedWidget(duration=150)

        # Sub-page 0: Home Dashboard View (Matches exact reference picture)
        self.home_view = HomeDashboardView(self)
        self.home_view.prompt_submitted.connect(self._handle_home_prompt_submit)
        self.home_view.new_chat_requested.connect(self._create_new_chat)
        self.home_view.navigate_requested.connect(self._handle_navigation)
        self.home_view.generate_image_requested.connect(self._handle_home_generate_image)
        self.home_container.addWidget(self.home_view)  # Sub-index 0: Home Dashboard

        # Sub-page 1: Interactive Chat Stream View (ChatViewport + Floating MessageInputBar)
        self.chat_page = QWidget()
        chat_layout = QVBoxLayout(self.chat_page)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self.chat_viewport = ChatViewport(self.chat_page)
        self.chat_viewport.starter_card_clicked.connect(self._handle_starter_click)
        chat_layout.addWidget(self.chat_viewport, 1)

        self.input_bar = MessageInputBar(self.chat_page)
        self.input_bar.submitted.connect(self._handle_message_submit)
        self.input_bar.cancelled.connect(self._handle_cancel)
        self.input_bar.manage_models_requested.connect(lambda: self._handle_navigation("api_keys"))
        self.input_bar.global_ranking_requested.connect(lambda: self._handle_navigation("auto_router"))
        chat_layout.addWidget(self.input_bar)

        self.home_container.addWidget(self.chat_page)  # Sub-index 1: Chat Stream

        self.stack.addWidget(self.home_container)  # Index 0: Home / Chat

        # Page 1: Coding Agent & IDE Workspace
        self.coding_ide_view = CodingIdeView(parent=self)
        self.coding_ide_view.fullscreen_toggled.connect(self._toggle_ide_fullscreen)
        if hasattr(self.coding_ide_view, "home_requested"):
            self.coding_ide_view.home_requested.connect(lambda: self._handle_navigation("home"))
        self.stack.addWidget(self.coding_ide_view)  # Coding Agent / IDE

        # Page 2: AI Automations View
        self.automations_view = AutomationsView(parent=self)
        self.stack.addWidget(self.automations_view)  # AI Automations

        # Page 3: Multi-Agent Hub View (Orchestrator + 7 Specialized Agents)
        self.multi_agent_view = MultiAgentView(parent=self)
        self.stack.addWidget(self.multi_agent_view)  # Multi-Agent Hub

        # Page 4: Knowledge & Memory Center ("Teach Model / Tell Model to Remember")
        self.knowledge_view = KnowledgeView(parent=self)
        self.stack.addWidget(self.knowledge_view)  # Knowledge

        # Page 5: In-Window Settings View (Profile & Persona)
        self.settings_view = SettingsView(parent=self)
        self.settings_view.profile_updated.connect(self._on_profile_updated)
        self.settings_view.back_to_chat_requested.connect(lambda: self._handle_navigation("chat"))
        self.settings_view.request_add_models.connect(lambda: self._handle_navigation("api_keys"))
        self.stack.addWidget(self.settings_view)  # Settings

        # Page 6: In-Window Add & Connect AI Models View
        self.add_models_view = AddModelsView(parent=self)
        self.add_models_view.models_updated.connect(self.input_bar.refresh_models)
        self.add_models_view.back_to_chat_requested.connect(lambda: self._handle_navigation("chat"))
        self.stack.addWidget(self.add_models_view)  # Add AI Models

        # Page 7: In-Window Graphical Analytics & Usage View
        self.analytics_view = AnalyticsView(parent=self)
        self.analytics_view.back_to_chat_requested.connect(lambda: self._handle_navigation("chat"))
        self.analytics_view.request_add_models.connect(lambda: self._handle_navigation("api_keys"))
        self.stack.addWidget(self.analytics_view)  # Analytics / Model Usage

        # Page 8: AI Auto Router Global Queue Dashboard (Universal Model Ranking)
        self.global_ranking_view = GlobalRankingView(parent=self)
        self.global_ranking_view.back_to_chat_requested.connect(lambda: self._handle_navigation("chat"))
        self.global_ranking_view.request_add_models.connect(lambda: self._handle_navigation("api_keys"))
        self.stack.addWidget(self.global_ranking_view)  # Global Model Ranking Dashboard

        right_layout.addWidget(self.stack, 1)
        root_layout.addWidget(right_container, 1)

        # Wire Global F11 & Escape shortcuts for Whole-Screen IDE mode
        self.f11_shortcut = QShortcut(QKeySequence(Qt.Key_F11), self)
        self.f11_shortcut.activated.connect(self._on_f11_pressed)

        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.esc_shortcut.activated.connect(self._on_esc_pressed)

        # Apply saved user theme if non-default
        saved_theme = self.db.get_setting("app_theme_key", "cyberpunk")
        if saved_theme and saved_theme.lower() != "cyberpunk":
            self._apply_theme(saved_theme)

    def _init_sessions(self):
        sessions = self.db.get_sessions()
        if not sessions:
            new_session = self.db.create_session("Welcome to Sage AI")
            self.current_session_id = new_session["id"]
            sessions = [new_session]
        else:
            self.current_session_id = sessions[0]["id"]

        # Load profile in sidebar
        user_name = self.db.get_setting("user_display_name", "")
        user_email = self.db.get_setting("user_email", "")
        self.sidebar.update_profile(user_name or "Developer", user_email or "user@local")
        if hasattr(self, "chat_viewport") and self.chat_viewport:
            self.chat_viewport.update_user_name(user_name)
        if hasattr(self, "home_dashboard") and self.home_dashboard:
            self.home_dashboard.update_user_name(user_name)
        if hasattr(self, "coding_ide_view") and self.coding_ide_view:
            self.coding_ide_view.update_profile_name(user_name)

        # Load chat history into sidebar
        self.sidebar.load_sessions(sessions)
        self.stack.setCurrentIndex(0)
        self.home_container.setCurrentIndex(1)
        self.sidebar.set_active_nav("home")
        self.chat_viewport.set_empty_state_visible(True)

        # Check if first launch / onboarding completed on this computer
        if self.db.get_setting("onboarding_completed") != "true":
            from PySide6.QtCore import QTimer
            QTimer.singleShot(150, self._show_onboarding_dialog)

    def _show_onboarding_dialog(self):
        from ui.components.onboarding_dialog import FirstLaunchOnboardingDialog
        dlg = FirstLaunchOnboardingDialog(parent=self)
        if dlg.exec():
            user_name = self.db.get_setting("user_display_name", "")
            user_email = self.db.get_setting("user_email", "")
            self.sidebar.update_profile(user_name or "Developer", user_email or "user@local")
            if hasattr(self, "chat_viewport") and self.chat_viewport:
                self.chat_viewport.update_user_name(user_name)
            if hasattr(self, "home_dashboard") and self.home_dashboard:
                self.home_dashboard.update_user_name(user_name)
            if hasattr(self, "coding_ide_view") and self.coding_ide_view:
                self.coding_ide_view.update_profile_name(user_name)

    def _start_startup_model_trace(self):
        """Launches non-blocking background model scan and diff tracer."""
        self._model_trace_worker = StartupModelTraceWorker(parent=self)
        self._model_trace_worker.trace_finished.connect(self._on_startup_model_trace_finished)
        self._model_trace_worker.start()

    def _on_startup_model_trace_finished(self, result: Dict[str, Any]):
        """Handles completion of the startup model trace."""
        added_free = result.get("added_free", [])
        added_paid = result.get("added_paid", [])
        removed = result.get("removed", [])
        changed = result.get("changed", [])
        total_models = result.get("total_models", 0)
        scanned_provs = result.get("scanned_providers", [])

        logger.info(
            "Startup Model Trace Completed: %d models across %s. "
            "+%d free added, +%d paid added, -%d removed, ~%d changed.",
            total_models, scanned_provs, len(added_free), len(added_paid), len(removed), len(changed)
        )

        # Refresh UI models across the app
        if hasattr(self, "input_bar") and hasattr(self.input_bar, "refresh_models"):
            self.input_bar.refresh_models()
        if hasattr(self, "coding_ide_view") and hasattr(self.coding_ide_view, "_refresh_agent_models"):
            self.coding_ide_view._refresh_agent_models()

        # If any new free models or changes occurred, show trace badge in TopBar
        if added_free or removed or changed:
            msg_parts = []
            tooltip_lines = ["<b>Model Trace Report (Startup Scan):</b>"]
            if added_free:
                msg_parts.append(f"+{len(added_free)} Free Added")
                tooltip_lines.append(f"<br><b>New Free Models ({len(added_free)}):</b>")
                for m in added_free[:5]:
                    tooltip_lines.append(f"• {m.get('display_name')} ({m.get('provider_id')})")
                if len(added_free) > 5:
                    tooltip_lines.append(f"• ... and {len(added_free)-5} more")
            if removed:
                msg_parts.append(f"-{len(removed)} Removed")
                tooltip_lines.append(f"<br><b>Discontinued Models ({len(removed)}):</b>")
                for m in removed[:3]:
                    tooltip_lines.append(f"• {m.get('display_name')} ({m.get('provider_id')})")
            if changed:
                msg_parts.append(f"~{len(changed)} Changed")
                tooltip_lines.append(f"<br><b>Changed Models ({len(changed)}):</b>")
                for m in changed[:3]:
                    tooltip_lines.append(f"• {m.get('display_name')}: {m.get('change_summary')}")

            summary_badge_text = " • ".join(msg_parts)
            if hasattr(self, "top_bar") and hasattr(self.top_bar, "show_trace_status"):
                self.top_bar.show_trace_status(f"⚡ {summary_badge_text}", tooltip="<br>".join(tooltip_lines))

    def _switch_page(self, widget: QWidget):
        """Switches main stack view instantly with zero latency or rasterization lag."""
        if self.stack.currentWidget() == widget:
            return
        self.stack.setCurrentWidget(widget)

    def _handle_navigation(self, nav_name: str):
        if hasattr(self, "coding_ide_view") and self.coding_ide_view.is_fullscreen and nav_name != "coding_agent":
            self.coding_ide_view.toggle_fullscreen(False)

        self.sidebar.setVisible(True)
        self.top_bar.setVisible(True)

        if nav_name == "home":
            self._switch_page(self.home_container)
            self.home_container.setCurrentIndex(1)
            self.sidebar.set_active_nav("home")
            self.chat_viewport.clear_messages()
            self.chat_viewport.set_empty_state_visible(True)
        elif nav_name == "chat":
            self._switch_page(self.home_container)
            self.home_container.setCurrentIndex(1)
            self.sidebar.set_active_nav("chat")
            if self.current_session_id:
                self._load_session_messages(self.current_session_id)
        elif nav_name in ("image_gen", "image_generation"):
            self._switch_page(self.home_container)
            self.home_container.setCurrentIndex(1)
            self.sidebar.set_active_nav("chat")
            if hasattr(self, "input_bar"):
                self.input_bar.image_btn.setChecked(True)
        elif nav_name == "multi_agent":
            self._switch_page(self.multi_agent_view)
            self.sidebar.set_active_nav("multi_agent")
        elif nav_name == "coding_agent":
            self._switch_page(self.coding_ide_view)
            self.sidebar.set_active_nav("coding_agent")
        elif nav_name == "automations":
            self._switch_page(self.automations_view)
            self.sidebar.set_active_nav("automations")
        elif nav_name == "knowledge":
            self._switch_page(self.knowledge_view)
            self.sidebar.set_active_nav("knowledge")
        elif nav_name == "usage":
            self.analytics_view.refresh_data()
            self._switch_page(self.analytics_view)
            if hasattr(self, "settings_view") and self.settings_view:
                self.settings_view.tabs.setCurrentIndex(1)
                self.settings_view.refresh_usage()
        elif nav_name == "settings":
            self._switch_page(self.settings_view)
            self.sidebar.set_active_nav("settings")
        elif nav_name == "api_keys":
            self._switch_page(self.add_models_view)
        elif nav_name == "auto_router":
            self.global_ranking_view.refresh_ranking()
            self._switch_page(self.global_ranking_view)
            self.sidebar.set_active_nav("auto_router")

    def _handle_home_prompt_submit(self, prompt: str):
        """Switches to active chat view and sends the prompt submitted from Home dashboard."""
        self.stack.setCurrentIndex(0)
        self.home_container.setCurrentIndex(1)
        self.sidebar.set_active_nav("chat")
        self._handle_message_submit(prompt, force_web=False, selected_model="Auto Router", attachments=[])

    def _handle_home_generate_image(self, prompt: str, model: str, ratio: str):
        """Dispatches image generation request from Home dashboard directly into Chat stream."""
        self.stack.setCurrentIndex(0)
        self.home_container.setCurrentIndex(1)
        self.sidebar.set_active_nav("chat")
        full_prompt = f"Generate an image using {model} with aspect ratio {ratio}: {prompt}"
        self._handle_message_submit(full_prompt, force_web=False, selected_model="image: Black Forest FLUX.1", attachments=[])

    def _handle_global_search(self, query: str):
        """Handles search input from top bar."""
        self.stack.setCurrentIndex(0)
        self.home_container.setCurrentIndex(1)
        self.sidebar.set_active_nav("chat")
        self._handle_message_submit(f"Search and answer: {query}", force_web=True, selected_model="Auto Router", attachments=[])

    def _open_api_key_settings(self):
        self.stack.setCurrentIndex(7)

    def _open_general_settings(self, tab_idx: int = 0):
        self.stack.setCurrentIndex(6)
        if hasattr(self, "settings_view") and self.settings_view:
            self.settings_view.tabs.setCurrentIndex(tab_idx)

    def _open_usage(self):
        if hasattr(self, "coding_ide_view") and self.coding_ide_view.is_fullscreen:
            self._toggle_ide_fullscreen(False)
        self.sidebar.set_active_nav("settings")
        self._open_general_settings(tab_idx=1)

    def _toggle_ide_fullscreen(self, enabled: bool):
        """Expands or restores the IDE workspace across the whole screen."""
        if enabled:
            self._was_maximized_before_fs = self.isMaximized()
            self.sidebar.setVisible(False)
            self.top_bar.setVisible(False)
            self.showFullScreen()
            if hasattr(self, "coding_ide_view"):
                self.coding_ide_view.is_fullscreen = True
                self.coding_ide_view.fullscreen_btn.setText("🗗")
        else:
            self.sidebar.setVisible(True)
            self.top_bar.setVisible(True)
            if hasattr(self, "coding_ide_view"):
                self.coding_ide_view.is_fullscreen = False
                self.coding_ide_view.fullscreen_btn.setText("⛶")
            if self.isFullScreen():
                if getattr(self, "_was_maximized_before_fs", False):
                    self.showMaximized()
                else:
                    self.showNormal()

    def _on_f11_pressed(self):
        """Toggles fullscreen: whole-screen IDE if on IDE view, or full window."""
        if self.stack.currentIndex() == 2 and hasattr(self, "coding_ide_view"):
            self.coding_ide_view.toggle_fullscreen()
        else:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def _on_esc_pressed(self):
        """Exits whole-screen IDE mode when Escape is pressed."""
        if hasattr(self, "coding_ide_view") and self.coding_ide_view.is_fullscreen:
            self._toggle_ide_fullscreen(False)

    def _apply_theme(self, theme_key: str, force: bool = False):
        """Applies dynamic QSS theme globally and updates header accent, background, and logos."""
        from ui.styles.qss_theme import get_theme_qss, THEME_PALETTES
        pal = THEME_PALETTES.get(theme_key.lower()) or THEME_PALETTES["cyberpunk"]
        app = QApplication.instance()
        current_theme = getattr(app, "_current_theme_key", None)
        if app and (force or current_theme != theme_key):
            app.setStyleSheet(get_theme_qss(theme_key))
            app._current_theme_key = theme_key
            self.db.set_setting("app_theme_key", theme_key)
        self.top_bar.update_theme_accent(pal["primary"])
        if hasattr(self, "sidebar") and self.sidebar:
            self.sidebar.update_theme(pal)
        if hasattr(self, "chat_viewport") and self.chat_viewport:
            self.chat_viewport.apply_theme(pal)
        if hasattr(self, "multi_agent_view") and self.multi_agent_view:
            self.multi_agent_view.apply_theme(pal)
        if hasattr(self, "knowledge_view") and self.knowledge_view:
            self.knowledge_view.apply_theme(pal)

    def _on_profile_updated(self, name: str, email: str):
        self.sidebar.update_profile(name, email)
        if hasattr(self, "chat_viewport") and self.chat_viewport:
            self.chat_viewport.update_user_name(name)

    def _open_usage(self):
        from ui.components.usage_dialog import UsageDialog
        dialog = UsageDialog(self)
        dialog.exec()

    def _show_help(self):
        QMessageBox.information(
            self,
            "About Sage AI",
            "Sage AI\n\n"
            "• Auto-routing waterfall between cloud models & local Ollama\n"
            "• Autonomous Project Coding Agent\n"
            "• Offline Chronometer & Knowledge Engine\n\n"
            "Keyboard Shortcuts:\n"
            "• Enter: Send message\n"
            "• Shift + Enter: New line in input\n"
            "• Ctrl + N: New chat"
        )

    def _create_new_chat(self):
        new_session = self.db.create_session("New Chat")
        self.current_session_id = new_session["id"]
        self.chat_viewport.clear_messages()
        self.chat_viewport.set_empty_state_visible(True)
        self.stack.setCurrentIndex(0)
        self.home_container.setCurrentIndex(1)
        self.sidebar.set_active_nav("chat")

        # Add to sidebar chat history
        self.sidebar.add_session(new_session["id"], new_session["title"])
        self.sidebar.set_active_session(new_session["id"])

    def _switch_to_session(self, session_id: str):
        """Switch to an existing chat session from the history list."""
        self.current_session_id = session_id
        self.sidebar.set_active_session(session_id)
        self._load_session_messages(session_id)
        self.stack.setCurrentIndex(0)
        self.home_container.setCurrentIndex(1)
        self.sidebar.set_active_nav("chat")

    def _rename_session(self, session_id: str, new_title: str):
        """Renames a chat session title in the database and sidebar."""
        if not new_title.strip():
            return
        self.db.update_session_title(session_id, new_title.strip())
        self.sidebar.update_session_title(session_id, new_title.strip())

    def _delete_session(self, session_id: str):
        """Delete a chat session from history."""
        self.db.delete_session(session_id)
        self.sidebar.remove_session(session_id)

        # If we deleted the current session, switch to another
        if session_id == self.current_session_id:
            sessions = self.db.get_sessions()
            if sessions:
                self.current_session_id = sessions[0]["id"]
                self.sidebar.set_active_session(self.current_session_id)
                self._load_session_messages(self.current_session_id)
            else:
                # Create a fresh session
                self._create_new_chat()

    def _load_session_messages(self, session_id: str):
        self.chat_viewport.clear_messages()
        messages = self.db.get_session_messages(session_id)

        if not messages:
            self.chat_viewport.set_empty_state_visible(True)
            return

        self.chat_viewport.set_empty_state_visible(False)
        for msg in messages:
            meta = msg.get("metadata", {})
            self.chat_viewport.add_message(
                role=msg["role"],
                content=msg["content"],
                model=msg.get("model"),
                timestamp=msg.get("timestamp"),
                citations=msg.get("sources"),
                is_image=meta.get("is_image", False),
                image_data=meta.get("image_data"),
                latency_ms=meta.get("latency_ms"),
                thinking=meta.get("thinking"),
                attachments=meta.get("attachments"),
                username=self.db.get_setting("user_display_name", "") or "User" if msg["role"] == "user" else None
            )

        # Trigger layout passes to ensure all loaded messages fit the container without shrinking
        from PySide6.QtCore import QTimer
        QTimer.singleShot(40, self.chat_viewport._refresh_all_bubbles_height)
        QTimer.singleShot(120, self.chat_viewport._refresh_all_bubbles_height)

    def _handle_starter_click(self, prompt_text: str):
        self.input_bar.set_input_text(prompt_text)
        if "generate an image" in prompt_text.lower():
            if hasattr(self.input_bar, "image_btn") and not self.input_bar.image_btn.isChecked():
                self.input_bar.image_btn.setChecked(True)

    def _handle_message_submit(self, prompt: str, force_web: bool, selected_model: str, attachments: Optional[list] = None):
        if not self.current_session_id:
            self._create_new_chat()
        self.sidebar.set_active_nav("chat")

        # 1. Store and display user message
        meta = {}
        if attachments:
            meta["attachments"] = [
                {"name": a.get("name"), "size": a.get("size"), "path": a.get("path"), "is_image": a.get("is_image", False)}
                for a in attachments
            ]
        user_msg = self.db.add_message(
            session_id=self.current_session_id,
            role="user",
            content=prompt,
            metadata=meta if meta else None
        )
        curr_user_name = self.db.get_setting("user_display_name", "") or "User"
        self.chat_viewport.add_message(
            role="user",
            content=prompt,
            timestamp=user_msg["timestamp"],
            attachments=attachments,
            username=curr_user_name
        )

        # 2. Get history for context
        history = self.db.get_session_messages(self.current_session_id)

        # 3. Update session title if first message
        if len(history) <= 2:
            title_candidate = prompt if len(prompt) <= 28 else prompt[:25] + "..."
            if not title_candidate and attachments:
                title_candidate = f"File: {attachments[0].get('name', 'attached')}"
            self.db.update_session_title(self.current_session_id, title_candidate or "New Chat")
            self.sidebar.update_session_title(self.current_session_id, title_candidate or "New Chat")

        # 4. Launch ChatWorker in background thread with Live Streaming & Thinking
        self.input_bar.set_busy(True)
        self.chat_viewport.show_working_stage("Analyzing request...")

        self.streaming_bubble = self.chat_viewport.create_streaming_message(
            role="assistant",
            model=selected_model or "Auto Router"
        )
        is_image_request = (
            (selected_model and selected_model.startswith("image:"))
            or (prompt and prompt.lower().startswith(("generate an image", "create an image", "generate image", "create image", "generate a picture", "generate a photo")))
        )
        if is_image_request and self.streaming_bubble:
            self.streaming_bubble.show_image_loading(prompt)
        self._in_thinking = False
        self._thinking_buffer = ""
        self._response_buffer = ""
        self._thinking_start_time = None

        # Build comprehensive LLM prompt including attached code/files
        llm_prompt = prompt
        if attachments:
            attach_blocks = []
            for a in attachments:
                name = a.get("name", "file")
                content = a.get("content", "")
                is_image = a.get("is_image", False)
                if is_image:
                    attach_blocks.append(f"### Attached Image: `{name}` (Image data attached)")
                elif content:
                    attach_blocks.append(f"### Attached File: `{name}`\n```\n{content}\n```")
            if attach_blocks:
                header = f"{prompt}\n\n" if prompt else ""
                llm_prompt = header + "\n\n".join(attach_blocks)

        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.quit()
            self.current_worker.wait(400)

        self.current_worker = ChatWorker(
            prompt=llm_prompt,
            session_id=self.current_session_id,
            history=history[:-1],
            force_web=force_web,
            selected_model=selected_model
        )
        self.current_worker.stage_changed.connect(self.chat_viewport.show_working_stage)
        self.current_worker.token_received.connect(self._on_token_received)
        self.current_worker.finished.connect(self._on_worker_finished)
        self.current_worker.failed.connect(self._on_worker_failed)
        self.current_worker.start()

    def _on_token_received(self, chunk: str):
        try:
            if not self.streaming_bubble:
                return

            # Handle <think> tags for live streaming reasoning
            if "<think>" in chunk:
                parts = chunk.split("<think>", 1)
                if parts[0]:
                    self.streaming_bubble.append_live_response_chunk(parts[0])
                    self._response_buffer += parts[0]
                self._in_thinking = True
                self._thinking_start_time = time.time()
                self.streaming_bubble.start_live_thinking()
                chunk = parts[1]

            if self._in_thinking:
                if "</think>" in chunk:
                    parts = chunk.split("</think>", 1)
                    if parts[0]:
                        self.streaming_bubble.append_live_thinking_chunk(parts[0])
                        self._thinking_buffer += parts[0]
                    duration = time.time() - (self._thinking_start_time or time.time())
                    self.streaming_bubble.finish_live_thinking(duration)
                    self._in_thinking = False
                    if len(parts) > 1 and parts[1]:
                        self.streaming_bubble.append_live_response_chunk(parts[1])
                        self._response_buffer += parts[1]
                else:
                    self.streaming_bubble.append_live_thinking_chunk(chunk)
                    self._thinking_buffer += chunk
            else:
                self.streaming_bubble.append_live_response_chunk(chunk)
                self._response_buffer += chunk

            if not hasattr(self, "_stream_scroll_timer"):
                self._stream_scroll_timer = QTimer(self)
                self._stream_scroll_timer.setSingleShot(True)
                self._stream_scroll_timer.timeout.connect(lambda: self.chat_viewport.scroll_to_bottom(smooth=False))
            if not self._stream_scroll_timer.isActive():
                self._stream_scroll_timer.start(50)
        except Exception as e:
            logger.warning("Token streaming error: %s", e)

    def _on_worker_finished(self, result: dict):
        self.chat_viewport.hide_working_stage()
        self.input_bar.set_busy(False)

        try:
            if result.get("session_id") != self.current_session_id:
                if self.streaming_bubble:
                    if hasattr(self.streaming_bubble, "thinking_widget") and self.streaming_bubble.thinking_widget:
                        self.streaming_bubble.thinking_widget.finish_live()
                    self.streaming_bubble.deleteLater()
                    self.streaming_bubble = None
                return

            # Clean up thinking timer if still running
            if self._in_thinking and self.streaming_bubble:
                duration = time.time() - (self._thinking_start_time or time.time())
                self.streaming_bubble.finish_live_thinking(duration)
                self._in_thinking = False

            raw_text = result.get("text") or ""
            # Check if thinking was detected in final text if not streamed
            extracted_thinking, clean_text = extract_thinking(raw_text)
            final_thinking = (
                self._thinking_buffer
                or extracted_thinking
                or (result.get("metadata", {}).get("thinking") if result.get("metadata") else None)
            )
            final_text = clean_text if extracted_thinking else raw_text

            metadata = {
                "is_image": result.get("is_image", False),
                "image_data": result.get("image_data"),
                "latency_ms": result.get("latency_ms", 0),
                "thinking": final_thinking
            }
            msg = self.db.add_message(
                session_id=self.current_session_id,
                role="assistant",
                content=final_text,
                model=result.get("model_name"),
                sources=result.get("citations"),
                metadata=metadata
            )

            if self.streaming_bubble:
                if result.get("is_image") and result.get("image_data"):
                    # Smoothly transition streaming shimmer card to generated image with animation
                    if hasattr(self.streaming_bubble, "thinking_widget") and self.streaming_bubble.thinking_widget:
                        self.streaming_bubble.thinking_widget.finish_live()
                    self.streaming_bubble.model = result.get("model_name")
                    self.streaming_bubble.set_generated_image(
                        image_data=result.get("image_data"),
                        content=final_text,
                        latency_ms=result.get("latency_ms")
                    )
                else:
                    self.streaming_bubble.model = result.get("model_name")
                    self.streaming_bubble.raw_content = final_text
                    self.streaming_bubble.display_content = final_text
                    self.streaming_bubble.latency_ms = result.get("latency_ms")
                    html = format_markdown_to_html(final_text)
                    self.streaming_bubble.text_browser.setHtml(html)
                    self.streaming_bubble._adjust_browser_height()

                    # Update telemetry badge if available
                    telem = result.get("metadata") or {}
                    if telem and "global_rank" in telem:
                        self.streaming_bubble.set_telemetry(telem)

                    # If thinking arrived in batch and section not yet added
                    if final_thinking and not self.streaming_bubble.thinking_widget:
                        lat_s = (result.get("latency_ms", 0) / 1000.0)
                        self.streaming_bubble.thinking_widget = ThinkingSection(final_thinking, latency_s=lat_s)
                        idx = self.streaming_bubble.layout().indexOf(self.streaming_bubble.text_browser)
                        self.streaming_bubble.layout().insertWidget(max(0, idx), self.streaming_bubble.thinking_widget)
                self.streaming_bubble = None
            else:
                self.chat_viewport.add_message(
                    role="assistant",
                    content=final_text,
                    model=result.get("model_name"),
                    timestamp=msg["timestamp"],
                    citations=result.get("citations"),
                    is_image=result.get("is_image", False),
                    image_data=result.get("image_data"),
                    latency_ms=result.get("latency_ms"),
                    thinking=final_thinking,
                    telemetry=result.get("metadata")
                )

            self.chat_viewport.scroll_to_bottom()
        except Exception as e:
            logger.error("Error handling worker finished: %s", e)
            if self.streaming_bubble:
                try:
                    self.streaming_bubble.deleteLater()
                except Exception:
                    pass
                self.streaming_bubble = None
            self.chat_viewport.add_message(
                role="assistant",
                content=f"⚠️ {result.get('text') or 'Completed with warnings.'}",
                model=result.get("model_name") or "Response"
            )

    def _on_worker_failed(self, error_msg: str):
        self.chat_viewport.hide_working_stage()
        self.input_bar.set_busy(False)
        if self.streaming_bubble:
            if hasattr(self.streaming_bubble, "thinking_widget") and self.streaming_bubble.thinking_widget:
                self.streaming_bubble.thinking_widget.finish_live()
            self.streaming_bubble.deleteLater()
            self.streaming_bubble = None

        err_text = (
            f"⚠️ **Engine Error:**\n{error_msg}\n\n"
            f"*Click **Add AI Models (✨)** in the sidebar to configure free API keys (Groq, Gemini, NVIDIA NIM) or connect local Ollama.*"
        )
        msg = self.db.add_message(
            session_id=self.current_session_id,
            role="assistant",
            content=err_text,
            model="Error Handler"
        )
        self.chat_viewport.add_message(
            role="assistant",
            content=err_text,
            model="Error Handler",
            timestamp=msg["timestamp"]
        )

    def _handle_cancel(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.quit()
            self.current_worker.wait(1000)
            self.current_worker = None

        if self.streaming_bubble:
            if hasattr(self.streaming_bubble, "thinking_widget") and self.streaming_bubble.thinking_widget:
                self.streaming_bubble.thinking_widget.finish_live()
            self.streaming_bubble.deleteLater()
            self.streaming_bubble = None

        self.chat_viewport.hide_working_stage()
        self.input_bar.set_busy(False)
