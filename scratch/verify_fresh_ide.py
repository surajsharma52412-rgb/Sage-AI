"""
Verification script for:
1. Fresh, clean state (no fake code, no fake users, no fake tasks).
2. Uncongested layout in normal windowed mode (outer sidebar hidden).
3. On-demand tool activation.
4. Clean header without moon logo or subtitle.
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

from ui.main_window import MainWindow
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def verify():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1280, 800)
    win.show()
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()

    ide = win.coding_ide_view
    assert ide is not None, "CodingIdeView missing"

    # 1. Verify outer sidebar is hidden in IDE mode
    print(f"Sidebar isVisible: {win.sidebar.isVisible()}")
    assert not win.sidebar.isVisible(), "Outer sidebar should be hidden in IDE mode"

    # 2. Verify header has no moon logo or multi-agent subtitle
    assert not hasattr(ide, "logo_widget"), "Moon logo should be removed"
    assert hasattr(ide, "home_btn"), "Home button should be present"

    # 3. Verify editor content is fresh
    editor_text = ide.editor.toPlainText()
    assert "LoginPage" not in editor_text, "Editor should not contain fake LoginPage code"
    assert "Welcome to Sage AI IDE" in editor_text, "Editor should contain clean welcome code"
    print("Clean editor verified!")

    # 4. Verify agent starts fresh
    assert ide.agent_progress.value() == 0, f"Expected 0% progress, got {ide.agent_progress.value()}"
    assert "Idle" in ide.agent_status_lbl.text(), f"Expected Idle status, got {ide.agent_status_lbl.text()}"
    print("Fresh agent state verified!")

    # 5. Verify collaboration starts clean
    assert "No remote collaborators" in ide.collab_empty_peers.text(), "Expected empty collaborators"
    print("Fresh collaboration state verified!")

    # 6. Verify whiteboard starts clean
    assert ide.whiteboard.canvas.show_sample_mindmap is False, "Whiteboard should not show sample mindmap by default"
    print("Fresh whiteboard state verified!")

    # Capture 1: Fresh Windowed Mode (Uncongested, outer sidebar hidden)
    shot1 = ARTIFACTS_DIR / "ide_fresh_windowed.png"
    win.grab().save(str(shot1))
    print(f"Captured Screenshot 1: {shot1}", flush=True)

    # 7. Test On-Demand Tool Toggling:
    # Switch to Whiteboard
    ide._toggle_tool_panel("whiteboard")
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()
    assert ide.right_stack.currentIndex() == 2, "Expected Whiteboard active"

    # Close the right dock completely to give editor full screen
    ide.right_dock.setVisible(False)
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    # Capture 2: Full-Width Editor Mode (Right dock closed, maximum breathing room)
    shot2 = ARTIFACTS_DIR / "ide_full_width_editor.png"
    win.grab().save(str(shot2))
    print(f"Captured Screenshot 2: {shot2}", flush=True)

    win.close()
    app.processEvents()
    print("ALL FRESH IDE VERIFICATIONS PASSED!", flush=True)
    os._exit(0)


if __name__ == "__main__":
    verify()
