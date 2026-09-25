import sys
import os
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ui.main_window import MainWindow

ARTIFACTS_DIR = BASE_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(1300, 840)
    win.show()
    app.processEvents()

    # 1. Capture Multi-Agent Hub (matching user's screenshot view)
    win._handle_navigation("multi_agent")
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    p1 = ARTIFACTS_DIR / "multi_agent_hub_updated.png"
    win.grab().save(str(p1))
    print(f"Captured: {p1}")

    # 2. Capture Knowledge Base view
    win._handle_navigation("knowledge")
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    p2 = ARTIFACTS_DIR / "knowledge_section_updated.png"
    win.grab().save(str(p2))
    print(f"Captured: {p2}")

    # 3. Capture Coding Agent view
    win._handle_navigation("coding_agent")
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    p3 = ARTIFACTS_DIR / "coding_agent_updated.png"
    win.grab().save(str(p3))
    print(f"Captured: {p3}")

    win.close()
    print("Verification screenshots successfully saved!")

if __name__ == "__main__":
    run()
