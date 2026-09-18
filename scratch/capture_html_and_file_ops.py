"""
Visual verification script to capture:
1. HTML file opened in IDE with syntax highlighting and browser preview button.
2. New toolbar buttons: '＋ New File', 'Save As...', and explorer '📁＋' (New Folder).
3. Top coding models dropdown in the Coding Agent pane.
"""
import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.main_window import MainWindow
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\9bfc78cd-de89-4a52-9fb2-8e58f82a4d48")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1380, 880)
    win.show()
    app.processEvents()

    # Switch to Coding IDE View
    win.stack.setCurrentIndex(2)
    win.sidebar.set_active_nav("coding_agent")
    app.processEvents()

    ide = win.coding_ide_view

    # Open index.html to demonstrate HTML opening, syntax highlighting & browser preview
    html_code = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>Sage AI - Lunar Workspace</title>\n"
        "  <link rel=\"stylesheet\" href=\"style.css\">\n"
        "</head>\n"
        "<body>\n"
        "  <div class=\"hero-container\">\n"
        "    <h1>Welcome to Sage AI IDE</h1>\n"
        "    <p>Top Coding Models: Claude 3.7, DeepSeek R1 & Qwen 2.5 Coder</p>\n"
        "    <button id=\"explore-btn\">Launch Workspace</button>\n"
        "  </div>\n"
        "</body>\n"
        "</html>"
    )
    ide.open_document(
        filename="index.html",
        content=html_code,
        language="HTML",
        is_shared=False,
        switch_to=True
    )

    # Also open style.css tab to show multi-tab support
    ide.open_document(
        filename="style.css",
        content="body { background-color: #080b16; color: #0FE6B5; font-family: sans-serif; }",
        language="CSS",
        is_shared=False,
        switch_to=False
    )

    # Switch bottom tab to Autonomous Coding Agent to showcase top coding models
    ide.bottom_tabs.setCurrentIndex(1)
    ide.agent_model_combo.setCurrentIndex(1)  # Claude 3.7 Sonnet

    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    # Capture high-res screenshot
    out_path = ARTIFACTS_DIR / "html_ide_and_file_ops.png"
    win.grab().save(str(out_path))
    print(f"Captured: {out_path}")

    win.close()
    win.deleteLater()


if __name__ == "__main__":
    run()
