"""
Capture verification screenshots for:
1. Whole-screen IDE mode without the removed top notification banner.
2. Worldwide Internet (Cloud Relay) Collab Dialog with Room Code.
"""
import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.main_window import MainWindow
from ui.styles.qss_theme import QSS_STYLE
from ui.components.collab_dialog import CollabDialog

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\9bfc78cd-de89-4a52-9fb2-8e58f82a4d48")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1380, 880)
    win.show()
    app.processEvents()

    # Switch to Coding IDE View
    win.stack.setCurrentIndex(2)
    win.sidebar.set_active_nav("coding_agent")
    app.processEvents()

    ide = win.coding_ide_view

    # Seed tabs
    ide.open_document(
        filename="cloud_relay_bridge.py",
        content=(
            "import websockets\n"
            "import json\n\n"
            "# Worldwide Internet Pair Programming Relay\n"
            "class CloudCollabBridge:\n"
            "    def __init__(self, room_code='SAGE-7392'):\n"
            "        self.room_code = room_code\n"
            "        self.channel = f'sage_collab_{room_code.lower()}'\n"
            "        self.relay_url = f'wss://ntfy.sh/{self.channel}/ws'\n\n"
            "    async def connect_and_sync(self):\n"
            "        print(f'Syncing across networks via Room Code: {self.room_code}')\n"
        ),
        language="Python",
        is_shared=True,
        switch_to=True
    )

    # 1. Trigger whole-screen IDE mode
    win._toggle_ide_fullscreen(True)
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    # Capture 1: Clean Whole-screen IDE with NO top banner
    shot1 = ARTIFACTS_DIR / "fullscreen_clean_ide.png"
    win.grab().save(str(shot1))
    print(f"Captured: {shot1}")

    # Exit fullscreen for dialog display
    win._toggle_ide_fullscreen(False)
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()

    # 2. Open Collab Dialog showcasing Worldwide Internet mode
    dialog = CollabDialog(ide.collab_manager, default_user_name="Lead Engineer", parent=win)
    dialog.room_code_display.setText("SAGE-7392")
    dialog.show()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    # Capture 2: Worldwide Collab Dialog with Room Code
    shot2 = ARTIFACTS_DIR / "worldwide_collab_dialog.png"
    dialog.grab().save(str(shot2))
    print(f"Captured: {shot2}")

    dialog.close()
    dialog.deleteLater()

    # Clean teardown
    ide.collab_manager.stop()
    win.close()
    win.deleteLater()


if __name__ == "__main__":
    run()
