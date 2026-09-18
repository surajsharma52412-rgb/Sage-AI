import os
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

def capture_all():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    from ui.main_window import MainWindow
    win = MainWindow()
    win.resize(1360, 860)
    win.show()
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    artifact_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")

    # 1. Capture Automation Section Windowed
    win._handle_navigation("automations")
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()
    p1 = win.grab()
    p1.save(str(artifact_dir / "automation_section_matches_photo.png"), "PNG")
    print("Saved automation_section_matches_photo.png", flush=True)

    # 2. Capture Automation Section Fullscreen Mode (1920x1080)
    win.resize(1920, 1080)
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()
    p_full = win.grab()
    p_full.save(str(artifact_dir / "automation_fullscreen_mode.png"), "PNG")
    print("Saved automation_fullscreen_mode.png", flush=True)

    # 3. Capture Settings Theme section
    win.resize(1360, 860)
    win._handle_navigation("settings")
    win.settings_view.tabs.setCurrentIndex(1) # Theme tab
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()
    p2 = win.grab()
    p2.save(str(artifact_dir / "settings_theme_section.png"), "PNG")
    print("Saved settings_theme_section.png", flush=True)

    # 4. Apply Neon Horizon theme & Capture Automation Studio under Neon Horizon theme
    win._apply_theme("automator")
    win._handle_navigation("automations")
    win.resize(1920, 1080)
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()
    p3 = win.grab()
    p3.save(str(artifact_dir / "automation_section_neon_theme.png"), "PNG")
    print("Saved automation_section_neon_theme.png", flush=True)

    win.close()

if __name__ == "__main__":
    capture_all()
