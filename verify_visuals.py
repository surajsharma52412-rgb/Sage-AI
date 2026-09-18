"""
Script to capture visual verification screenshots of Sage AI:
1. File Attachments (input bar chips + message bubble chips)
2. Coding Agent / IDE Workspace (file tree, code editor, execution terminal, project agent)
3. AI Automations Workspace (Gmail cards, task triggers, compliance audit trail)
4. Permission-First Gate Modal (editable preview, authorization buttons)
5. Enhanced Settings Dialog (eye toggles, paste buttons, portal links, and Gmail/Automations tab)
"""
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap

from ui.main_window import MainWindow
from ui.components.usage_dialog import UsageDialog
from ui.components.settings_dialog import SettingsDialog
from ui.components.permission_dialog import PermissionDialog
from database.db_manager import get_db

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def capture():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 1. Setup MainWindow
    win = MainWindow()
    win.resize(1340, 840)
    win._create_new_chat()
    win.show()
    app.processEvents()

    # -------------------------------------------------------------
    # Capture 1: File Attachments in Chat & Input Bar
    # -------------------------------------------------------------
    test_file_path = os.path.abspath("test.py")
    win.input_bar.add_attachment(test_file_path)
    win.input_bar.text_input.setText("Please review my calculator script in test.py and optimize it.")

    win.chat_viewport.clear_messages()
    win.chat_viewport.set_empty_state_visible(False)
    
    # Add message with attachment chip
    file_size = os.path.getsize(test_file_path) if os.path.exists(test_file_path) else 1840
    win.chat_viewport.add_message(
        role="user",
        content="Please review my calculator script in test.py and optimize it.",
        model="User",
        attachments=[{"path": test_file_path, "name": "test.py", "size": file_size, "is_image": False}]
    )

    win.chat_viewport.add_message(
        role="assistant",
        content=(
            "### Code Review: `test.py` (Tkinter Calculator)\n\n"
            "I've inspected your attached file `test.py`. Here are key improvements:\n\n"
            "1. **Input Validation**: Handle zero-division errors gracefully.\n"
            "2. **Keyboard Bindings**: Add `Return` key binding for immediate evaluation.\n"
            "3. **Modular Layout**: Separate calculator engine from UI rendering.\n\n"
            "You can also open and run this script directly inside the new **⚡ Coding Agent / IDE** tab in the sidebar!"
        ),
        model="OpenRouter (qwen/qwen-2.5-coder-32b-instruct)",
        latency_ms=640.0,
        thinking="Analyzed test.py structure.\nDetected standard Tkinter geometry layout and basic math operations.\nGenerated architectural suggestions."
    )
    app.processEvents()
    
    att_pixmap = win.grab()
    att_out = ARTIFACTS_DIR / "sage_input_with_attachments.png"
    att_pixmap.save(str(att_out))
    print(f"Captured file attachments to {att_out}")

    # -------------------------------------------------------------
    # Capture 2: Coding Agent / IDE Workspace
    # -------------------------------------------------------------
    win._handle_navigation("coding_agent")
    app.processEvents()
    # Ensure test.py is highlighted/selected in editor
    if hasattr(win, "coding_ide_view") and os.path.exists(test_file_path):
        win.coding_ide_view.open_file_in_editor(test_file_path)
    app.processEvents()

    ide_pixmap = win.grab()
    ide_out = ARTIFACTS_DIR / "sage_coding_ide_workspace.png"
    ide_pixmap.save(str(ide_out))
    print(f"Captured Coding IDE workspace to {ide_out}")

    # -------------------------------------------------------------
    # Capture 3: AI Automations Workspace
    # -------------------------------------------------------------
    win._handle_navigation("automations")
    app.processEvents()

    auto_pixmap = win.grab()
    auto_out = ARTIFACTS_DIR / "sage_ai_automations_view.png"
    auto_pixmap.save(str(auto_out))
    print(f"Captured AI Automations view to {auto_out}")

    # -------------------------------------------------------------
    # Capture 4: Human-in-the-Loop Permission Dialog
    # -------------------------------------------------------------
    perm_dlg = PermissionDialog(
        action_type="📧 Send Gmail Reply",
        target="sarah.connor@cyberdyne-systems.com",
        subject="Re: Urgent: Project timeline & deployment review for Sage AI",
        body=(
            "Hi Sarah,\n\n"
            "Thank you for reaching out. The Sage AI multi-provider waterfall routing engine and autonomous IDE workspace "
            "are fully verified and ready for deployment. All 38 automated test suites passed with 100% success.\n\n"
            "I will attend the steering committee session this afternoon to present the live walkthrough.\n\n"
            "Best regards,\nSage AI Executive Assistant"
        ),
        parent=win
    )
    perm_dlg.show()
    app.processEvents()

    perm_pixmap = perm_dlg.grab()
    perm_out = ARTIFACTS_DIR / "sage_permission_dialog.png"
    perm_pixmap.save(str(perm_out))
    print(f"Captured Permission Dialog to {perm_out}")
    perm_dlg.close()

    # -------------------------------------------------------------
    # Capture 5: Settings Dialog - Tab 1 (Enhanced API Keys with Eye & Links)
    # -------------------------------------------------------------
    settings_dlg = SettingsDialog(win)
    settings_dlg.show()
    app.processEvents()

    set_api_pixmap = settings_dlg.grab()
    set_api_out = ARTIFACTS_DIR / "sage_settings_enhanced_apikeys.png"
    set_api_pixmap.save(str(set_api_out))
    print(f"Captured Settings API Keys to {set_api_out}")

    # -------------------------------------------------------------
    # Capture 6: Settings Dialog - Tab 4 (Gmail & Automations)
    # -------------------------------------------------------------
    settings_dlg.tabs.setCurrentIndex(3)  # Tab 4
    app.processEvents()

    set_gmail_pixmap = settings_dlg.grab()
    set_gmail_out = ARTIFACTS_DIR / "sage_settings_gmail_tab.png"
    set_gmail_pixmap.save(str(set_gmail_out))
    print(f"Captured Settings Gmail tab to {set_gmail_out}")
    settings_dlg.close()

    win.close()
    print("ALL_CAPTURES_SUCCESS")

if __name__ == "__main__":
    capture()
