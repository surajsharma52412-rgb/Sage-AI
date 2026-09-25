"""
UI Components package for Sage AI.
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
from .global_ranking_view import GlobalRankingView
from .animation_system import (
    PerformanceTier,
    MotionTokens,
    AnimationManager,
    get_anim_manager,
    fade_in,
    fade_out,
    slide_in_from_bottom,
    modal_entrance,
    smooth_scroll_to,
    animate_number_counter,
    button_micro_press,
    ShimmerSkeleton,
)
from .agent_workflow_animator import (
    AgentStatus,
    AgentNodeBadge,
    WorkflowConnector,
    MultiAgentWorkflowVisualizer,
)

__all__ = [
    "Sidebar",
    "TopBar",
    "ChatViewport",
    "GlobalRankingView",
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
    "PerformanceTier",
    "MotionTokens",
    "AnimationManager",
    "get_anim_manager",
    "fade_in",
    "fade_out",
    "slide_in_from_bottom",
    "modal_entrance",
    "smooth_scroll_to",
    "animate_number_counter",
    "button_micro_press",
    "ShimmerSkeleton",
    "AgentStatus",
    "AgentNodeBadge",
    "WorkflowConnector",
    "MultiAgentWorkflowVisualizer",
]

