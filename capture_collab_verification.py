"""
Capture verification screenshots for Multi-File Collaborative Pair Programming.
"""
import sys
import os
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
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

    # Switch to Coding IDE (Index 2)
    win.stack.setCurrentIndex(2)
    win.sidebar.set_active_nav("coding_agent")
    app.processEvents()

    ide = win.coding_ide_view

    # Pre-seed multi-file tabs in the IDE
    ide.open_document(
        filename="server.py",
        content=(
            "import socket\nimport threading\n\n"
            "# Multi-User Real-Time Collab Server\n"
            "class SharedRoom:\n"
            "    def __init__(self, port=8989):\n"
            "        self.port = port\n"
            "        self.peers = {}\n"
            "        self.documents = {}\n\n"
            "    def broadcast(self, sender, file_name, patch):\n"
            "        print(f'Syncing {file_name} from {sender}')\n"
        ),
        language="Python",
        is_shared=True,
        switch_to=False
    )

    ide.open_document(
        filename="app_client.js",
        content=(
            "// Real-time Collaborative Web Worker\n"
            "import { connectSession } from './socket_bridge.js';\n\n"
            "export async function initPairCoding(roomCode) {\n"
            "  console.log(`Connecting to collaborative room: ${roomCode}`);\n"
            "  const session = await connectSession(roomCode);\n"
            "  session.onSync((file, code) => updateEditorTab(file, code));\n"
            "}\n"
        ),
        language="JavaScript",
        is_shared=True,
        switch_to=False
    )

    ide.open_document(
        filename="style.css",
        content=(
            "/* Cyberpunk Dark Emerald IDE Stylesheet */\n"
            ":root {\n"
            "  --primary: #0FE6B5;\n"
            "  --bg-dark: #070b14;\n"
            "  --tab-active: #0c1424;\n"
            "  --border-glow: rgba(15, 230, 181, 0.4);\n"
            "}\n"
        ),
        language="CSS",
        is_shared=True,
        switch_to=True
    )

    # Start mock hosting session so status and chip show active collab
    ide.collab_manager.start_hosting(
        port=8989,
        host_name="Alex (Lead)",
        initial_files=ide.get_all_open_documents()
    )

    # Simulate a peer joined and editing server.py
    ide.collab_manager.active_peers = ["Alex (Lead) (Host)", "Elena (Pair Developer)"]
    ide.collab_manager.peer_list_updated.emit(ide.collab_manager.active_peers)
    ide.collab_manager.status_changed.emit("Hosting at 192.168.1.105:8989", True)

    # Peer is focused on server.py
    ide.collab_manager.peer_focus["Elena (Pair Developer)"] = "server.py"
    ide._on_peer_focus_changed("Elena (Pair Developer)", "server.py")

    ide.collab_chip.setText("👥 2 in Room")
    ide.collab_chip.setVisible(True)

    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    # Capture 1: Main IDE with Multi-File Tabs & Collab Indicators
    main_shot = ARTIFACTS_DIR / "multi_file_collab_ide.png"
    win.grab().save(str(main_shot))
    print(f"Captured: {main_shot}")

    # Capture 2: Collab Dialog with Multi-File Room Status
    dialog = CollabDialog(ide.collab_manager, default_user_name="Alex (Lead)", parent=win)
    dialog.show()
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()

    dlg_shot = ARTIFACTS_DIR / "collab_dialog_view.png"
    dialog.grab().save(str(dlg_shot))
    print(f"Captured: {dlg_shot}")

    dialog.close()
    dialog.deleteLater()

    # Clean shutdown
    ide.collab_manager.stop()
    win.close()
    win.deleteLater()


if __name__ == "__main__":
    run()
