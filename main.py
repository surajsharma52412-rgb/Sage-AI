"""
Sage – Multi-Agentic AI Architecture Entry Point.
"Plan • Create • Code • Automate • Anything"
Supports native PySide6 desktop mode and dual-mode Flask/pywebview runner.

Usage:
  python main.py                     # Native PySide6 Desktop GUI (Default)
  python main.py --mode desktop       # Native PySide6 Desktop GUI
  python main.py --mode web          # Dual-mode Flask web server
  python main.py --mode webview      # PyWebView native frame with web server
"""
import sys
import os
import argparse
from pathlib import Path

# Safeguard stdout/stderr when running as a windowed application via pythonw
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import APP_NAME, APP_ID, APP_SUBTITLE


def run_desktop():
    """Launches the native PySide6 Desktop application."""
    # 1. On Windows, explicitly set AppUserModelID before creating QApplication
    # This instructs Windows Shell / DWM to display our custom taskbar icon
    # instead of grouping under python.exe / pythonw.exe.
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import Qt
    # Enable High DPI pixmaps
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(f"{APP_NAME} – {APP_SUBTITLE}")
    app.setDesktopFileName(APP_ID)

    # Set Application & Windows Taskbar Icon
    from ui.styles.qss_theme import get_app_icon
    app_icon = get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Apply Dark Emerald & Cyberpunk Slate QSS Theme
    from ui.styles.qss_theme import QSS_STYLE
    app.setStyleSheet(QSS_STYLE)

    from ui.main_window import MainWindow
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()

    sys.exit(app.exec())


def run_web(port: int = 5000, use_webview: bool = False):
    """Launches the dual-mode Flask / pywebview runner."""
    from web_runner.web_server import run_web_app
    run_web_app(port=port, use_webview=use_webview)


def main():
    parser = argparse.ArgumentParser(description="Sage AI (Lunar Engine) Desktop & Web Assistant")
    parser.add_argument(
        "--mode",
        choices=["desktop", "web", "webview"],
        default="desktop",
        help="Execution mode: desktop (PySide6 native GUI), web (Flask), webview (pywebview)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for web server (default: 5000)"
    )

    args = parser.parse_args()

    if args.mode == "desktop":
        run_desktop()
    elif args.mode == "web":
        run_web(port=args.port, use_webview=False)
    elif args.mode == "webview":
        run_web(port=args.port, use_webview=True)


if __name__ == "__main__":
    main()
