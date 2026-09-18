"""
Script to capture screenshots verifying the bug fixes for General Settings Dialog and the redesigned ProjectAgentView.
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from ui.components.general_settings_dialog import GeneralSettingsDialog
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1300, 820)
    win.show()
    app.processEvents()

    # 1. Capture Redesigned Projects Tab in Main Window
    # Switch stack to Index 1 (Projects view)
    win.stack.setCurrentIndex(1)
    # Also trigger tree refresh
    win.project_view._refresh_tree()
    app.processEvents()

    p_proj = ARTIFACTS_DIR / "project_agent_view_redesigned.png"
    win.grab().save(str(p_proj))
    print(f"Captured: {p_proj}")

    # 2. Capture General Settings Dialog - Profile Tab
    dlg = GeneralSettingsDialog(win)
    dlg.tabs.setCurrentIndex(0)
    dlg.show()
    app.processEvents()

    p_profile = ARTIFACTS_DIR / "general_settings_profile.png"
    dlg.grab().save(str(p_profile))
    print(f"Captured: {p_profile}")

    # 3. Capture General Settings Dialog - Analyse Tab
    dlg.tabs.setCurrentIndex(1)
    app.processEvents()

    p_analyse = ARTIFACTS_DIR / "general_settings_analyse.png"
    dlg.grab().save(str(p_analyse))
    print(f"Captured: {p_analyse}")

    # 4. Capture General Settings Dialog - Theme Select Tab
    dlg.tabs.setCurrentIndex(2)
    app.processEvents()

    p_themes = ARTIFACTS_DIR / "general_settings_themes.png"
    dlg.grab().save(str(p_themes))
    print(f"Captured: {p_themes}")

    dlg.close()
    win.close()
    print("All verification screenshots successfully captured!")

if __name__ == "__main__":
    run()
