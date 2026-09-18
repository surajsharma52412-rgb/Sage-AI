"""
Capture Team tab and Whiteboard tab in the right dock.
"""
import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.coding_ide_view import CodingIdeView
ide = CodingIdeView()
ide.resize(1280, 800)
ide.show()
app.processEvents()
time.sleep(0.3)
app.processEvents()

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")

# 1. Switch to Team Collaboration
ide._toggle_tool_panel("collab")
app.processEvents()
time.sleep(0.3)
app.processEvents()
shot1 = ARTIFACTS_DIR / "ide_team_tab.png"
ide.grab().save(str(shot1))
print(f"Captured Team tab: {shot1}", flush=True)

# 2. Switch to Whiteboard
ide._toggle_tool_panel("whiteboard")
app.processEvents()
time.sleep(0.3)
app.processEvents()
shot2 = ARTIFACTS_DIR / "ide_whiteboard_tab.png"
ide.grab().save(str(shot2))
print(f"Captured Whiteboard tab: {shot2}", flush=True)

ide.close()
app.processEvents()
print("CAPTURES COMPLETED!", flush=True)
os._exit(0)
