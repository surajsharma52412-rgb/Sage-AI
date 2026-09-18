"""
Full-Screen IDE and Model Usage Screenshot Verification.
Captures both:
1. ide_fullscreen_photo_match.png (Visual match for Sage AI IDE reference photo)
2. model_usage_combined_tokens.png (Model usage view with Combined Tokens Left feature)
"""
import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from ui.main_window import MainWindow
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run_verification():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    ide = win.coding_ide_view
    assert ide is not None, "CodingIdeView not initialized"

    # Verify editor and tabs
    assert ide.active_filename == "Login.tsx", f"Expected Login.tsx active, got {ide.active_filename}"
    code_text = ide.editor.toPlainText()
    assert "export default function LoginPage()" in code_text, "LoginPage missing"

    # Capture 1: Full-Screen IDE matching photo
    shot1 = ARTIFACTS_DIR / "ide_fullscreen_photo_match.png"
    win.grab().save(str(shot1))
    print(f"Captured Screenshot 1: {shot1}", flush=True)

    # Capture 2: Model Usage with Combined Tokens
    win.stack.setCurrentIndex(8)
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    analytics = win.analytics_view
    assert hasattr(analytics, "combined_rem_val"), "combined_rem_val widget missing"
    print(f"Combined Tokens Left text: {analytics.combined_rem_val.text()}", flush=True)

    shot2 = ARTIFACTS_DIR / "model_usage_combined_tokens.png"
    win.grab().save(str(shot2))
    print(f"Captured Screenshot 2: {shot2}", flush=True)

    win.close()
    app.processEvents()
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!", flush=True)
    os._exit(0)


if __name__ == "__main__":
    run_verification()
