"""
Step-by-step diagnostic script for CodingIdeView and MainWindow.
"""
import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print("1. Importing PySide6...", flush=True)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

print("2. Creating QApplication...", flush=True)
app = QApplication.instance() or QApplication(sys.argv)

print("3. Testing CodingIdeView directly...", flush=True)
from ui.components.coding_ide_view import CodingIdeView
ide = CodingIdeView()
ide.resize(1280, 800)
ide.show()
app.processEvents()
time.sleep(0.3)
app.processEvents()

print(f"4. CodingIdeView created! Editor text lines: {ide.editor.blockCount()}", flush=True)
print(f"   Active tool tab index: {ide.right_stack.currentIndex()}", flush=True)
print(f"   Agent progress: {ide.agent_progress.value()}", flush=True)

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")
shot1 = ARTIFACTS_DIR / "ide_fresh_windowed.png"
ide.grab().save(str(shot1))
print(f"5. Saved ide_fresh_windowed.png: {shot1}", flush=True)

# Toggle right dock to test full-width editor
ide.right_dock.setVisible(False)
app.processEvents()
time.sleep(0.3)
app.processEvents()

shot2 = ARTIFACTS_DIR / "ide_full_width_editor.png"
ide.grab().save(str(shot2))
print(f"6. Saved ide_full_width_editor.png: {shot2}", flush=True)

ide.close()
app.processEvents()
print("7. CodingIdeView tests finished cleanly!", flush=True)

print("8. Testing MainWindow in windowed mode...", flush=True)
from ui.main_window import MainWindow
win = MainWindow()
win.resize(1280, 800)
win.show()
app.processEvents()
time.sleep(0.4)
app.processEvents()

print(f"9. MainWindow created! Sidebar visible: {win.sidebar.isVisible()}", flush=True)
shot3 = ARTIFACTS_DIR / "mainwindow_fresh_ide_windowed.png"
win.grab().save(str(shot3))
print(f"10. Saved mainwindow_fresh_ide_windowed.png: {shot3}", flush=True)

win.close()
app.processEvents()
print("ALL DIAGNOSTICS COMPLETED SUCCESSFULLY!", flush=True)
os._exit(0)
