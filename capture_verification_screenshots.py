"""
Script to capture screenshots of the updated UI:
1. Main Window with Bottom Chat History in Sidebar
2. General Settings Dialog - Profile Tab
3. General Settings Dialog - Analyse Tab
4. GeneralSettings Dialog - Theme Select Tab
5. API Key Enter Dialog
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ui.main_window import MainWindow
from ui.components.general_settings_dialog import GeneralSettingsDialog
from ui.components.settings_dialog import SettingsDialog

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Main Window screenshot
    win = MainWindow()
    win.resize(1300, 820)
    win.show()
    app.processEvents()

    # Populate a few sample sessions to show history at the bottom
    win.sidebar.load_sessions([
        {"id": "sess-1", "title": "DeepSeek Model Exploration"},
        {"id": "sess-2", "title": "Python Async Task Queue"},
        {"id": "sess-3", "title": "PySide6 UI Architecture"}
    ])
    win.sidebar.set_active_session("sess-1")
    app.processEvents()

    p_main = ARTIFACTS_DIR / "main_window_bottom_history.png"
    win.grab().save(str(p_main))
    print(f"Captured: {p_main}")

    # 2. General Settings Dialog - Profile Tab
    dlg_profile = GeneralSettingsDialog(win, initial_tab=0)
    dlg_profile.show()
    app.processEvents()
    p_profile = ARTIFACTS_DIR / "general_settings_profile.png"
    dlg_profile.grab().save(str(p_profile))
    print(f"Captured: {p_profile}")
    dlg_profile.close()

    # 3. General Settings Dialog - Analyse Tab
    dlg_analyse = GeneralSettingsDialog(win, initial_tab=1)
    dlg_analyse.show()
    app.processEvents()
    p_analyse = ARTIFACTS_DIR / "general_settings_analyse.png"
    dlg_analyse.grab().save(str(p_analyse))
    print(f"Captured: {p_analyse}")
    dlg_analyse.close()

    # 4. General Settings Dialog - Theme Select Tab
    dlg_theme = GeneralSettingsDialog(win, initial_tab=2)
    dlg_theme.show()
    app.processEvents()
    p_theme = ARTIFACTS_DIR / "general_settings_theme.png"
    dlg_theme.grab().save(str(p_theme))
    print(f"Captured: {p_theme}")
    dlg_theme.close()

    # 5. API Key Enter Dialog
    dlg_keys = SettingsDialog(win)
    dlg_keys.show()
    app.processEvents()
    p_keys = ARTIFACTS_DIR / "api_key_enter_dialog.png"
    dlg_keys.grab().save(str(p_keys))
    print(f"Captured: {p_keys}")
    dlg_keys.close()

    win.close()
    print("All screenshots successfully captured!")

if __name__ == "__main__":
    run()
