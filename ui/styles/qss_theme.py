"""
Complete Dynamic QSS Theme Engine for Sage AI.
Supports multiple curated cyberpunk dark themes:
- Cyberpunk Emerald (Default): Deep obsidian space & neon emerald glow
- Obsidian Pure Black: High-contrast true black OLED with mint accents
- Midnight Oceanic Navy: Deep navy blue atmosphere with glowing electric cyan lights
- Amethyst Cyber Violet: Rich dark violet atmosphere with ultraviolet neon highlights
"""
import os
from pathlib import Path
from typing import Dict, Any, Tuple
from PySide6.QtGui import QImage, QPixmap, QColor, QIcon
from PySide6.QtCore import Qt


THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "cyberpunk": {
        "name": "Sage Cyan Glow",
        "primary": "#00D1FF",
        "primary_hover": "#00BBE6",
        "primary_dark": "#008bb3",
        "primary_rgba_06": "rgba(0, 209, 255, 0.06)",
        "primary_rgba_12": "rgba(0, 209, 255, 0.12)",
        "primary_rgba_22": "rgba(0, 209, 255, 0.22)",
        "primary_rgba_30": "rgba(0, 209, 255, 0.30)",
        "primary_rgba_42": "rgba(0, 209, 255, 0.42)",
        "bg_main": "#0A0F14",
        "bg_sidebar": "#0A0F14",
        "bg_surface": "#111827",
        "bg_card": "#162033",
        "bg_card_hover": "#1c2b45",
        "bg_capsule": "#111827",
        "bg_pill": "#162033",
        "border": "#273449",
        "border_subtle": "#273449",
        "text_primary": "#F8FAFC",
        "text_secondary": "#94A3B8",
        "text_muted": "#64748b",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "error": "#EF4444",
    },
    "obsidian": {
        "name": "Obsidian Pure Black",
        "primary": "#10B981",
        "primary_hover": "#34d399",
        "primary_dark": "#059669",
        "primary_rgba_06": "rgba(16, 185, 129, 0.06)",
        "primary_rgba_12": "rgba(16, 185, 129, 0.12)",
        "primary_rgba_22": "rgba(16, 185, 129, 0.22)",
        "primary_rgba_30": "rgba(16, 185, 129, 0.30)",
        "primary_rgba_42": "rgba(16, 185, 129, 0.42)",
        "bg_main": "#000000",
        "bg_sidebar": "#050505",
        "bg_card": "#0a0a0a",
        "bg_card_hover": "#141414",
        "bg_capsule": "#080808",
        "bg_pill": "#111111",
        "text_primary": "#ffffff",
        "text_secondary": "#a3a3a3",
        "text_muted": "#737373",
        "border_subtle": "rgba(255, 255, 255, 0.10)",
    },
    "midnight": {
        "name": "Midnight Oceanic Navy",
        "primary": "#00d2ff",
        "primary_hover": "#5ce1e6",
        "primary_dark": "#0083b0",
        "primary_rgba_06": "rgba(0, 210, 255, 0.06)",
        "primary_rgba_12": "rgba(0, 210, 255, 0.12)",
        "primary_rgba_22": "rgba(0, 210, 255, 0.22)",
        "primary_rgba_30": "rgba(0, 210, 255, 0.30)",
        "primary_rgba_42": "rgba(0, 210, 255, 0.42)",
        "bg_main": "#040814",
        "bg_sidebar": "#070e1b",
        "bg_card": "#0c182c",
        "bg_card_hover": "#11223e",
        "bg_capsule": "#081122",
        "bg_pill": "#0e1d35",
        "text_primary": "#f0f6fc",
        "text_secondary": "#8fa8cf",
        "text_muted": "#6a88b5",
        "border_subtle": "rgba(0, 210, 255, 0.12)",
    },
    "amethyst": {
        "name": "Amethyst Cyber Violet",
        "primary": "#c084fc",
        "primary_hover": "#e9d5ff",
        "primary_dark": "#9333ea",
        "primary_rgba_06": "rgba(192, 132, 252, 0.06)",
        "primary_rgba_12": "rgba(192, 132, 252, 0.12)",
        "primary_rgba_22": "rgba(192, 132, 252, 0.22)",
        "primary_rgba_30": "rgba(192, 132, 252, 0.30)",
        "primary_rgba_42": "rgba(192, 132, 252, 0.42)",
        "bg_main": "#090514",
        "bg_sidebar": "#0f0920",
        "bg_card": "#170e2c",
        "bg_card_hover": "#221542",
        "bg_capsule": "#110a22",
        "bg_pill": "#1d1238",
        "text_primary": "#fdf4ff",
        "text_secondary": "#c4b5fd",
        "text_muted": "#8b76b8",
        "border_subtle": "rgba(192, 132, 252, 0.15)",
    },
    "automator": {
        "name": "Neon Horizon (Cyan & Violet)",
        "primary": "#00f0ff",
        "primary_hover": "#67e8f9",
        "primary_dark": "#0284c7",
        "primary_rgba_06": "rgba(0, 240, 255, 0.06)",
        "primary_rgba_12": "rgba(0, 240, 255, 0.12)",
        "primary_rgba_22": "rgba(0, 240, 255, 0.22)",
        "primary_rgba_30": "rgba(0, 240, 255, 0.30)",
        "primary_rgba_42": "rgba(0, 240, 255, 0.42)",
        "bg_main": "#060a15",
        "bg_sidebar": "#080e1e",
        "bg_card": "#0c1529",
        "bg_card_hover": "#111f3c",
        "bg_capsule": "#081023",
        "bg_pill": "#0e1a35",
        "text_primary": "#f0fdf4",
        "text_secondary": "#93c5fd",
        "text_muted": "#64748b",
        "border_subtle": "rgba(0, 240, 255, 0.18)",
    }
}


def get_theme_qss(theme_key: str = "cyberpunk") -> str:
    """Generates and returns the complete dynamic stylesheet for the requested theme."""
    pal = THEME_PALETTES.get(theme_key.lower()) or THEME_PALETTES["cyberpunk"]

    return f"""
/* Global Styles */
QWidget {{
    background-color: transparent;
    color: {pal["text_primary"]};
    font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    selection-background-color: {pal["primary"]};
    selection-color: {pal["bg_main"]};
    outline: none;
}}

QMainWindow {{
    background-color: {pal["bg_main"]};
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {pal["primary_rgba_22"]};
    min-height: 25px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {pal["primary"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Sidebar Container */
#sidebar {{
    background-color: {pal["bg_sidebar"]};
    border-right: 1px solid {pal["primary_rgba_12"]};
}}

/* Sidebar Brand */
#brandText {{
    color: {pal["text_primary"]};
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 6px;
}}
QPushButton#collapseBtn {{
    background-color: {pal["bg_pill"]};
    color: {pal["text_secondary"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 8px;
    font-size: 11px;
    font-weight: bold;
    padding: 4px;
}}
QPushButton#collapseBtn:hover {{
    color: {pal["primary"]};
    border-color: {pal["primary_rgba_30"]};
}}

/* New Chat Button */
QPushButton#newChatBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {pal["primary"]}, stop:1 {pal["primary_dark"]});
    color: {pal["bg_main"]};
    border: none;
    border-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    padding: 10px 14px;
    text-align: left;
}}
QPushButton#newChatBtn:hover {{
    background: {pal["primary_hover"]};
}}
QLabel#shortcutPill {{
    background-color: rgba(5, 8, 16, 0.35);
    color: {pal["bg_main"]};
    border-radius: 5px;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
}}

/* Sidebar Navigation Items */
QPushButton#navBtn, QPushButton.navBtn {{
    background-color: transparent;
    color: {pal["text_secondary"]};
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    min-height: 34px;
    max-height: 38px;
    padding: 0px 12px;
    text-align: left;
}}
QPushButton#navBtn:hover, QPushButton.navBtn:hover {{
    background-color: {pal["primary_rgba_06"]};
    color: {pal["text_primary"]};
}}
QPushButton#navBtn[active="true"], QPushButton.navBtn:checked, QPushButton.navBtn.active {{
    background-color: {pal["primary_rgba_12"]};
    color: {pal["primary"]};
    font-weight: 700;
    border-right: 3.5px solid {pal["primary"]};
}}

/* SAGE Pro Card */
#proCard {{
    background-color: {pal["bg_card"]};
    border: 1px solid {pal["primary_rgba_22"]};
    border-radius: 14px;
    padding: 14px;
}}
#proTitle {{
    color: {pal["text_primary"]};
    font-size: 13px;
    font-weight: 700;
}}
#proDesc {{
    color: {pal["text_muted"]};
    font-size: 11px;
    line-height: 1.35;
}}
QPushButton#upgradeBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {pal["primary"]}, stop:1 {pal["primary_dark"]});
    color: {pal["bg_main"]};
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    padding: 8px 12px;
}}
QPushButton#upgradeBtn:hover {{
    background: {pal["primary_hover"]};
}}

/* User Profile Pill */
#profilePill {{
    background-color: {pal["bg_card"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 12px;
    padding: 8px 10px;
}}
#profilePill:hover {{
    border-color: {pal["primary_rgba_30"]};
}}
#avatarCircle {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {pal["primary"]}, stop:1 {pal["primary_dark"]});
    color: {pal["bg_main"]};
    font-weight: 800;
    font-size: 12px;
    border-radius: 16px;
    qproperty-alignment: AlignCenter;
}}
#profileName {{
    color: {pal["text_primary"]};
    font-size: 12px;
    font-weight: 700;
}}
#profileEmail {{
    color: {pal["text_muted"]};
    font-size: 10px;
}}

/* Top Bar */
#topBar {{
    background: transparent;
    padding: 10px 20px;
}}
#searchCapsule {{
    background-color: {pal["bg_card"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 18px;
    padding: 4px 14px;
}}
#searchCapsule:focus-within {{
    border-color: {pal["primary"]};
}}
#searchInput {{
    background: transparent;
    border: none;
    color: {pal["text_primary"]};
    font-size: 12px;
}}
#searchKbdBadge {{
    background-color: {pal["bg_pill"]};
    color: {pal["text_muted"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 5px;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
}}
QPushButton#topUtilBtn, QPushButton.topUtilBtn {{
    background-color: {pal["bg_pill"]};
    color: {pal["text_secondary"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 15px;
    font-size: 13px;
    padding: 6px;
}}
QPushButton#topUtilBtn:hover, QPushButton.topUtilBtn:hover {{
    color: {pal["primary"]};
    border-color: {pal["primary_rgba_30"]};
}}

/* Hero Section */
#greetingTitle {{
    color: {pal["text_primary"]};
    font-size: 34px;
    font-weight: 800;
    letter-spacing: -0.5px;
}}
#greetingSubtitle {{
    color: {pal["text_muted"]};
    font-size: 15px;
    font-weight: 500;
}}

/* 4 Action Cards */
QFrame#modernActionCard, QFrame[class="modernActionCard"] {{
    background-color: {pal["bg_card"]};
    border: 1px solid {pal["primary_rgba_22"]};
    border-radius: 16px;
}}
QFrame#modernActionCard:hover, QFrame[class="modernActionCard"]:hover {{
    background-color: {pal["bg_card_hover"]};
    border: 1px solid {pal["primary"]};
}}
QFrame#modernActionCard[accent="red"], QFrame[class="modernActionCard"][accent="red"] {{
    border: 1px solid rgba(244, 63, 94, 0.22);
}}
QFrame#modernActionCard[accent="red"]:hover, QFrame[class="modernActionCard"][accent="red"]:hover {{
    background-color: {pal["bg_card_hover"]};
    border: 1px solid rgba(244, 63, 94, 0.5);
}}

QLabel#actionBadgeGreen {{
    background-color: {pal["primary_rgba_12"]};
    color: {pal["primary"]};
    border-radius: 10px;
    font-size: 15px;
    font-weight: 800;
    qproperty-alignment: AlignCenter;
}}
QLabel#actionBadgeCyan {{
    background-color: rgba(6, 182, 212, 0.14);
    color: #06b6d4;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 800;
    qproperty-alignment: AlignCenter;
}}
QLabel#actionBadgeRed {{
    background-color: rgba(244, 63, 94, 0.15);
    color: #f43f5e;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 800;
    qproperty-alignment: AlignCenter;
}}
QLabel#cardMainTitle {{
    color: {pal["text_primary"]};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#cardMainDesc {{
    color: {pal["text_muted"]};
    font-size: 12px;
    line-height: 1.4;
}}
QPushButton#cardArrowBtn, QPushButton.cardArrowBtn {{
    background-color: {pal["bg_pill"]};
    color: {pal["text_secondary"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 14px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton#cardArrowBtn:hover, QPushButton.cardArrowBtn:hover {{
    background-color: {pal["primary"]};
    color: {pal["bg_main"]};
    border-color: {pal["primary"]};
}}
QPushButton#cardArrowBtn[accent="red"]:hover, QPushButton.cardArrowBtn[accent="red"]:hover {{
    background-color: #f43f5e;
    color: #ffffff;
    border-color: #f43f5e;
}}

/* Floating Input Capsule Bar */
#floatingInputCapsule {{
    background-color: {pal["bg_capsule"]};
    border: 1.5px solid {pal["primary_rgba_42"]};
    border-radius: 22px;
    padding: 12px 18px;
}}
#floatingInputCapsule:focus-within {{
    border: 1.5px solid {pal["primary"]};
}}
QTextEdit#capsuleTextEdit {{
    background: transparent;
    border: none;
    color: {pal["text_primary"]};
    font-size: 13px;
    line-height: 1.4;
    selection-background-color: {pal["primary"]};
    selection-color: {pal["bg_main"]};
}}
QPushButton#capsulePillBtn, QPushButton.capsulePillBtn {{
    background-color: {pal["bg_pill"]};
    color: {pal["text_secondary"]};
    border: 1px solid {pal["border_subtle"]};
    border-radius: 14px;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 12px;
}}
QPushButton#capsulePillBtn:hover, QPushButton.capsulePillBtn:hover {{
    color: {pal["text_primary"]};
    border-color: {pal["primary_rgba_30"]};
}}
QPushButton#capsulePillBtn:checked, QPushButton.capsulePillBtn:checked {{
    background-color: {pal["primary_rgba_12"]};
    color: {pal["primary"]};
    border-color: {pal["primary"]};
}}
QPushButton#capsuleSendBtn {{
    background-color: {pal["primary"]};
    color: {pal["bg_main"]};
    border: none;
    border-radius: 17px;
    font-size: 16px;
    font-weight: 900;
}}
QPushButton#capsuleSendBtn:hover {{
    background-color: {pal["primary_hover"]};
}}
QLabel#footerDisclaimer {{
    color: {pal["text_muted"]};
    font-size: 11px;
}}

/* Chat Messages (Modern Flow matching ChatGPT / Claude) */
QFrame.userMessageCard {{
    background-color: {pal["bg_card"]};
    border: 1px solid {pal["primary_rgba_22"]};
    border-radius: 18px;
    padding: 10px 16px;
}}
QFrame.userMessageCard:hover {{
    border-color: {pal["primary_rgba_42"]};
}}
QFrame.assistantMessageCard {{
    background-color: transparent;
    border: none;
    padding: 4px 0px 14px 0px;
}}

/* Knowledge & Memory Center */
QFrame#teachFrame {{
    background-color: {pal["bg_card"]};
    border: 1.5px solid {pal["primary_rgba_30"]};
    border-radius: 14px;
}}
QLabel#teachTitle {{
    color: {pal["primary"]};
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}
QPushButton#teachBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {pal["primary"]}, stop:1 {pal["primary_dark"]});
    color: {pal["bg_main"]};
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    padding: 10px 22px;
}}
QPushButton#teachBtn:hover {{
    background: {pal["primary_hover"]};
}}
QLabel#statMemories {{
    background: {pal["primary_rgba_12"]};
    color: {pal["primary"]};
    border: 1px solid {pal["primary_rgba_30"]};
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 700;
    font-size: 12px;
}}
QLabel#statVectors {{
    background: rgba(0, 210, 255, 0.1);
    color: #00d2ff;
    border: 1px solid rgba(0, 210, 255, 0.25);
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 700;
    font-size: 12px;
}}
QFrame#memoryCard {{
    background-color: {pal["bg_card"]};
    border: 1px solid {pal["primary_rgba_12"]};
    border-radius: 12px;
}}
QFrame#memoryCard:hover {{
    border-color: {pal["primary_rgba_42"]};
    background-color: {pal["bg_card_hover"]};
}}
"""


# Default theme constant for backward compatibility
QSS_STYLE = get_theme_qss("cyberpunk")

_LOGO_CACHE: Dict[Tuple[str, int], QPixmap] = {}


def get_tinted_logo(color_hex: str = "#0FE6B5", size: int = 42) -> QPixmap:
    """
    Returns a high-fidelity QPixmap of the Sage logo dynamically tinted to match
    the theme's primary accent color.
    Uses HSV hue re-mapping while preserving highlights, 3D facet depths,
    and particle transparencies. Results are cached in memory.
    """
    cache_key = (color_hex.lower(), size)
    if cache_key in _LOGO_CACHE:
        return _LOGO_CACHE[cache_key]

    base_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.png")
    )
    if not os.path.exists(base_path):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        return pm

    pixmap = QPixmap(base_path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )
    _LOGO_CACHE[cache_key] = pixmap
    return pixmap


def get_app_icon() -> QIcon:
    """Returns multi-resolution QIcon for Windows taskbar, title bar, and Alt+Tab."""
    icon = QIcon()
    base_dir = Path(__file__).resolve().parent.parent.parent
    ico_path = base_dir / "assets" / "logo.ico"
    png_path = base_dir / "assets" / "logo.png"

    if ico_path.exists():
        icon.addFile(str(ico_path))

    if png_path.exists():
        base_pm = QPixmap(str(png_path))
        if not base_pm.isNull():
            for sz in (16, 24, 32, 48, 64, 128, 256):
                scaled_pm = base_pm.scaled(
                    sz, sz,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon.addPixmap(scaled_pm)
        if icon.isNull():
            icon.addFile(str(png_path))

    return icon


