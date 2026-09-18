"""
UI Components package for Sage AI (Lunar Engine).
"""
from .sidebar import Sidebar
from .top_bar import TopBar
from .chat_viewport import ChatViewport
from .message_bubble import MessageBubble
from .live_working_panel import LiveWorkingPanel
from .input_bar import MessageInputBar
from .coding_ide_view import CodingIdeView
from .permission_dialog import PermissionDialog
from .automations_view import AutomationsView
from .settings_dialog import SettingsDialog
from .general_settings_dialog import GeneralSettingsDialog
from .multi_agent_view import MultiAgentView
from .knowledge_view import KnowledgeView
from .settings_view import SettingsView
from .add_models_view import AddModelsView
from .analytics_view import AnalyticsView
from .code_editor import CodeEditor
from .syntax_highlighter import MultiLanguageHighlighter
from .collab_dialog import CollabDialog, CollabPanelWidget
from .collab_whiteboard import CollabWhiteboardWidget, WhiteboardCanvas
from .home_dashboard_view import HomeDashboardView
from .onboarding_dialog import FirstLaunchOnboardingDialog

__all__ = [
    "Sidebar",
    "TopBar",
    "ChatViewport",
    "MessageBubble",
    "LiveWorkingPanel",
    "MessageInputBar",
    "CodingIdeView",
    "PermissionDialog",
    "AutomationsView",
    "SettingsDialog",
    "GeneralSettingsDialog",
    "MultiAgentView",
    "KnowledgeView",
    "SettingsView",
    "AddModelsView",
    "AnalyticsView",
    "CodeEditor",
    "MultiLanguageHighlighter",
    "CollabDialog",
    "CollabPanelWidget",
    "CollabWhiteboardWidget",
    "WhiteboardCanvas",
    "HomeDashboardView",
    "FirstLaunchOnboardingDialog",
]

