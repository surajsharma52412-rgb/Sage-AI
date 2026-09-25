import os
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.coding_ide_view import CodingIdeView
from engine.auto_router.coding_router import AutoCodingRouter

artifacts_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\97493313-966f-4701-aaf1-4f309461c450")
artifacts_dir.mkdir(parents=True, exist_ok=True)

# 1. Instantiate IDE view
ide = CodingIdeView(workspace_path=Path.cwd())
ide.resize(1280, 800)
ide.show()

# Switch right panel to Agent tab explicitly
ide.right_dock.setVisible(True)
ide.right_stack.setCurrentIndex(0)
ide._update_tool_buttons_style("agent")

# Populate model selection
router = AutoCodingRouter()
m_info = router.select_model_for_execution("Auto", prompt="Optimize Python server and add tests")
ide._update_model_info_card(m_info)
ide._on_agent_status_changed("ANALYZING")
ide._on_agent_file_tracked("engine/auto_router/coding_router.py", "Editing", "● Working")

# Activate live thinking cloud
ide.thinking_cloud.start_live()
ide.thinking_cloud.append_chunk("✦ 1/11: UNDERSTAND — Ingesting user requirements & constraints...\n")
ide.thinking_cloud.append_chunk("✦ 2/11: ANALYZE — Inspecting AST symbol index & architecture...\n")
ide.thinking_cloud.append_chunk("✦ 5/11: IMPLEMENT — Delegating tasks to internal specialist workers...\n")

# Add live activity events
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

def capture():
    app.processEvents()
    out_path = str(artifacts_dir / "agent_uncongested.png")
    pix = ide.grab()
    pix.save(out_path)
    print(f"Screenshot saved to: {out_path}")
    ide.thinking_cloud.finish_thinking(3.2)
    ide.deleteLater()
    app.quit()

QTimer.singleShot(500, capture)
app.exec()
