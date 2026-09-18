"""
Capture script to verify the new type bar and layout in MultiAgentView.
"""
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from database.db_manager import get_db
from ui.main_window import MainWindow
from ui.components.multi_agent_view import MultiAgentView
from ui.styles.qss_theme import QSS_STYLE

BRAIN_ARTIFACTS = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\9529f5d6-9311-440c-b299-e8e070c14d1f")

def run():
    db = get_db()
    db.set_setting("onboarding_completed", "true")
    db.set_setting("multi_agent_recent_tasks", "[]")
    db.set_setting("multi_agent_user_files", "[]")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    # 1. Clean Initial State
    view = MultiAgentView()
    view.resize(1200, 800)
    view.show()
    app.processEvents()

    p_clean = BRAIN_ARTIFACTS / "hub_clean_initial.png"
    view.grab().save(str(p_clean))
    print(f"Saved clean initial to {p_clean}")

    # 2. Main Window with Multi-Agent Hub
    win = MainWindow()
    win.resize(1380, 880)
    win.show()
    app.processEvents()
    win.stack.setCurrentIndex(4)
    win.sidebar.set_active_nav("multi_agent")
    app.processEvents()

    p_win = BRAIN_ARTIFACTS / "main_window_multi_agent.png"
    win.grab().save(str(p_win))
    print(f"Saved main window to {p_win}")

    # 3. View with text and attached file
    view._add_file_chip("project_requirements.pdf", "2.4 MB", ".pdf")
    view.goal_input.setText("Build a modern landing page for the AI platform")
    app.processEvents()

    p_file = BRAIN_ARTIFACTS / "hub_with_file.png"
    view.grab().save(str(p_file))
    print(f"Saved with file to {p_file}")

    # Reset DB
    db.set_setting("multi_agent_recent_tasks", "[]")
    db.set_setting("multi_agent_user_files", "[]")

    win.close()
    view.close()
    app.processEvents()
    print("Done capture!")
    sys.exit(0)

if __name__ == "__main__":
    run()
