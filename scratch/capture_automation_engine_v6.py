"""
Visual verification capture script for SAGE AI — Automation Engine v6.
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

from ui.components.automations_view import AutomationsView
from ui.styles.qss_theme import QSS_STYLE
from engine.automation.ai_workflow_generator import AIWorkflowGenerator

ARTIFACTS_DIR = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\3bac7561-9181-4444-8c49-b5530d94077a")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def capture_automation_v6():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    view = AutomationsView()
    view.resize(1360, 860)
    view.show()
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    # 1. Capture initial template view with selected node in inspector
    if view.current_workflow and len(view.current_workflow.nodes) > 1:
        first_node = view.current_workflow.nodes[1]
        view.canvas.selected_node_id = first_node.id
        view.inspector.load_node(first_node)
        view.canvas.update()
        app.processEvents()

    shot1 = ARTIFACTS_DIR / "automation_v6_canvas.png"
    view.grab().save(str(shot1))
    print(f"Captured Canvas Screenshot: {shot1}", flush=True)

    # 2. Run Dry-Run execution to show live status, logs, and drawer
    view._run_workflow(is_dry_run=True)
    t_end = time.time() + 2.5
    while time.time() < t_end and view.active_executor and view.active_executor.status == "running":
        app.processEvents()
        time.sleep(0.05)

    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    shot2 = ARTIFACTS_DIR / "automation_v6_execution.png"
    view.grab().save(str(shot2))
    print(f"Captured Execution Screenshot: {shot2}", flush=True)

    # 3. Test NL generation
    view.nl_input.setText("Track GPU prices on web and if under $500 alert me with order approval")
    view._generate_workflow_from_nl()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    shot3 = ARTIFACTS_DIR / "automation_v6_nl_generation.png"
    view.grab().save(str(shot3))
    print(f"Captured NL Generation Screenshot: {shot3}", flush=True)

    view.close()
    app.processEvents()
    os._exit(0)

if __name__ == "__main__":
    capture_automation_v6()
