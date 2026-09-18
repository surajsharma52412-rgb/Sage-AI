"""
Script to capture screenshots verifying:
1. In-Window Graphical Analytics View (Token Bar Chart, Model Donut Chart, Ratio Meter)
2. In-Window Settings View (Profile & Theme)
3. In-Window Add & Connect AI Models View
4. Overhauled Project Studio with 6 Guided Goal Cards & Live File Filter
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1340, 840)
    win.show()
    app.processEvents()

    # 1. Capture Graphical Analytics View (Index 8)
    win._handle_navigation("usage")
    app.processEvents()
    p_analytics = ARTIFACTS_DIR / "in_window_graphical_analytics.png"
    win.grab().save(str(p_analytics))
    print(f"Captured: {p_analytics}")

    # 2. Capture In-Window Settings View (Index 6)
    win._handle_navigation("settings")
    app.processEvents()
    p_settings = ARTIFACTS_DIR / "in_window_settings_view.png"
    win.grab().save(str(p_settings))
    print(f"Captured: {p_settings}")

    # 3. Capture In-Window Add AI Models View (Index 7)
    win._handle_navigation("api_keys")
    app.processEvents()
    p_models = ARTIFACTS_DIR / "in_window_add_models_view.png"
    win.grab().save(str(p_models))
    print(f"Captured: {p_models}")

    # 4. Capture Overhauled Project Studio (Index 1)
    win._handle_navigation("projects")
    app.processEvents()
    p_studio = ARTIFACTS_DIR / "project_studio_guided_goals.png"
    win.grab().save(str(p_studio))
    print(f"Captured: {p_studio}")

    win.close()
    print("All in-window verification screenshots captured successfully!")

if __name__ == "__main__":
    run()
