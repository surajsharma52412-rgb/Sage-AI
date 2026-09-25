"""
Capture screenshots of the Multi-Agent Hub and Tutorial Dialog.
"""
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.components.multi_agent_view import MultiAgentView, MultiAgentTutorialDialog
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\aa19c0a8-7e1d-4b6c-b405-ecf2ecfd2f11")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    # 1. MultiAgentView with Tutorial Button
    hub = MultiAgentView()
    hub.resize(1280, 800)
    hub.show()
    app.processEvents()

    hub.goal_input.setText("Build a responsive web application and analyze customer retention data")
    app.processEvents()

    p_hub = ARTIFACTS_DIR / "multi_agent_hub_tutorial_buttons.png"
    hub.grab().save(str(p_hub))
    print(f"Captured: {p_hub}")

    # 2. Tutorial Dialog - Tab 1: Quickstart
    dlg = MultiAgentTutorialDialog(hub)
    dlg.resize(860, 620)
    dlg.show()
    app.processEvents()

    p_dlg1 = ARTIFACTS_DIR / "multi_agent_tutorial_dialog.png"
    dlg.grab().save(str(p_dlg1))
    print(f"Captured: {p_dlg1}")

    # 3. Tab 2: 7 Specialized Agents
    dlg.tabs.setCurrentIndex(1)
    app.processEvents()

    p_dlg2 = ARTIFACTS_DIR / "multi_agent_tutorial_dialog_agents.png"
    dlg.grab().save(str(p_dlg2))
    print(f"Captured: {p_dlg2}")

    # 4. Tab 5: Interactive Examples
    dlg.tabs.setCurrentIndex(4)
    app.processEvents()

    p_dlg5 = ARTIFACTS_DIR / "multi_agent_tutorial_dialog_examples.png"
    dlg.grab().save(str(p_dlg5))
    print(f"Captured: {p_dlg5}")

    dlg.close()
    hub.close()
    print("ALL_CAPTURES_SUCCESS")
    os._exit(0)


if __name__ == "__main__":
    run()
