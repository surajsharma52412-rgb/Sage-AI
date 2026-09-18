"""
Script to capture screenshots verifying the friendly 'Add AI' UI updates:
1. Add & Connect AI Models Dialog - Cloud AI Tab (with Quick Start banner & badges)
2. Add & Connect AI Models Dialog - Local Ollama Tab (offline AI guidance)
3. Main Window - Updated Sidebar with '✨ Add AI Models'
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from ui.components.settings_dialog import SettingsDialog
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QSS_STYLE)

    # 1. Capture Main Window with updated sidebar
    win = MainWindow()
    win.resize(1300, 820)
    win.show()
    app.processEvents()

    p_main = ARTIFACTS_DIR / "main_window_add_ai_sidebar.png"
    win.grab().save(str(p_main))
    print(f"Captured: {p_main}")

    # 2. Capture Add & Connect AI Models Dialog - Cloud Tab
    dlg = SettingsDialog(win)
    dlg.tabs.setCurrentIndex(0)
    dlg.show()
    app.processEvents()

    p_cloud = ARTIFACTS_DIR / "add_ai_models_cloud_tab.png"
    dlg.grab().save(str(p_cloud))
    print(f"Captured: {p_cloud}")

    # 3. Capture Add & Connect AI Models Dialog - Local Ollama Tab
    dlg.tabs.setCurrentIndex(1)
    app.processEvents()

    p_local = ARTIFACTS_DIR / "add_ai_models_local_tab.png"
    dlg.grab().save(str(p_local))
    print(f"Captured: {p_local}")

    dlg.close()
    win.close()
    print("Verification screenshots captured successfully!")

if __name__ == "__main__":
    run()
