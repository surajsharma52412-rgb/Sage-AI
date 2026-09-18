import os
import sys
from pathlib import Path

# Ensure repo root is on path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

def capture_all():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)
    
    from ui.main_window import MainWindow
    win = MainWindow()
    win.resize(1200, 780)
    win.show()
    app.processEvents()

    artifact_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")

    # 1. Capture Home Section on startup
    p1 = win.grab()
    p1.save(str(artifact_dir / "home_section_opens_first.png"), "PNG")
    print("Saved home_section_opens_first.png")

    # 2. Capture IDE section without sidebar
    win._handle_navigation("coding_agent")
    app.processEvents()
    p2 = win.grab()
    p2.save(str(artifact_dir / "ide_section_no_sidebar.png"), "PNG")
    print("Saved ide_section_no_sidebar.png")

    # 3. Capture Model Usage as side of window
    win._handle_navigation("usage")
    app.processEvents()
    p3 = win.grab()
    p3.save(str(artifact_dir / "model_usage_side_of_window.png"), "PNG")
    print("Saved model_usage_side_of_window.png")

    win.close()

if __name__ == "__main__":
    capture_all()
