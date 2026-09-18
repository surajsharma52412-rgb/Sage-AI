"""
Dedicated capture script for Model Usage view with Combined Tokens Left feature.
"""
import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.components.analytics_view import AnalyticsView
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def capture_usage():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    view = AnalyticsView()
    view.resize(1400, 920)
    view.show()
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()

    shot_path = ARTIFACTS_DIR / "model_usage_combined_tokens.png"
    view.grab().save(str(shot_path))
    print(f"Captured Model Usage Screenshot: {shot_path}", flush=True)

    view.close()
    app.processEvents()
    os._exit(0)

if __name__ == "__main__":
    capture_usage()
