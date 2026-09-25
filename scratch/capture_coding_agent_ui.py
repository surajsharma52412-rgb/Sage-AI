import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.coding_ide_view import CodingIdeView
from engine.auto_router.coding_router import AutoCodingRouter

artifacts_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\aa19c0a8-7e1d-4b6c-b405-ecf2ecfd2f11")
artifacts_dir.mkdir(parents=True, exist_ok=True)

# 1. Instantiate IDE view
ide = CodingIdeView(workspace_path=Path.cwd())
ide.resize(1280, 850)
ide.show()

# Switch right panel to Agent tab and show changes in bottom tabs
ide._toggle_tool_panel("agent")
ide._open_git_diff()

# Populate model selection with Auto and show rank card
router = AutoCodingRouter()
m_info = router.select_model_for_execution("Auto", prompt="Optimize Python server and add tests")
ide._update_model_info_card(m_info)
ide._on_agent_status_changed("ANALYZING")
ide._on_agent_file_tracked("engine/auto_router/coding_router.py", "Editing", "● Working")

# Add some live activity events to display real Codex-style feed
ide._on_agent_event({
    "type": "task_analyzing",
    "message": "Analyzing project architecture & coding dependencies"
})
ide._on_agent_event({
    "type": "file_read",
    "file": "engine/auto_router/coding_router.py",
    "message": "Inspected coding router implementation"
})
ide._on_agent_event({
    "type": "file_modified",
    "file": "engine/auto_router/coding_router.py",
    "message": "+ Added 9-factor coding scoring engine and dynamic rankings"
})
ide._on_agent_event({
    "type": "command_started",
    "command": "python -m unittest tests/test_coding_router_and_events.py",
    "message": "Running automated verification tests"
})
ide._on_agent_event({
    "type": "test_finished",
    "message": "12 tests passed successfully"
})

# Emit diff into diff viewer
ide._on_agent_diff_emitted(
    "engine/auto_router/coding_router.py",
    """@@ -1,15 +1,25 @@
+class AutoCodingRouter:
+    def rank_coding_models(self, prompt):
+        # 9-factor coding score formula
+        weights = CodingScoringWeights.for_task_type(task_profile)
+        return sorted(models, key=lambda m: m.total_score, reverse=True)
-model = DEFAULT_MODEL
+model = auto_coding_router.select_model_for_execution('Auto')"""
)

# Process events to allow Qt to layout everything
QApplication.processEvents()

# Capture screenshot 1: Full Coding IDE with Model Selector, Live Activity, File Tracker, Diff View
pix = ide.grab()
shot1 = artifacts_dir / "coding_agent_master_ui.png"
pix.save(str(shot1))
print(f"Captured: {shot1}")

# Capture screenshot 2: Close-up of Right Agent Dock
dock_pix = ide.right_dock.grab()
shot2 = artifacts_dir / "coding_agent_dock_detail.png"
dock_pix.save(str(shot2))
print(f"Captured: {shot2}")

# Capture screenshot 3: Bottom Panel Diff Viewer
bottom_pix = ide.bottom_panel.grab()
shot3 = artifacts_dir / "coding_agent_diff_viewer.png"
bottom_pix.save(str(shot3))
print(f"Captured: {shot3}")

ide.collab_manager.stop()
ide.deleteLater()
app.quit()
print("All screenshots captured successfully.")
