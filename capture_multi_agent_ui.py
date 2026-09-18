"""
Capture screenshot of the Multi-Agent Hub View and MainWindow.
"""
import sys
import os
from pathlib import Path

# Use native Windows platform with QTimer to capture and exit automatically

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.main_window import MainWindow
from ui.styles.qss_theme import QSS_STYLE

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent / "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS_STYLE)

    win = MainWindow()
    win.resize(1340, 860)
    win.show()
    app.processEvents()

    # Switch to Multi-Agent Hub (Index 4)
    win.stack.setCurrentIndex(4)
    win.sidebar.set_active_nav("multi_agent")
    app.processEvents()

    # Pre-populate sample bus message and deliverable for visual appeal
    hub = win.multi_agent_view
    hub.goal_input.setText("Build a website, create images, write code, analyze data and deploy it")
    hub.status_lbl.setText("✅ Automated Completion: Goal accomplished in 1.4s with 4 deliverable(s)!")
    hub.progress_bar.setValue(100)

    hub.bus_browser.append("<b>[Orchestrator ➔ Task Decomposer]</b> <span style='color:#0FE6B5;'>(decompose)</span>: Partitioning goal into 5 dependency steps...")
    hub.bus_browser.append("<b>[Planning Agent ➔ All]</b> <span style='color:#0FE6B5;'>(plan_created)</span>: Strategic plan formulated with 4 milestones.")
    hub.bus_browser.append("<b>[Research Agent ➔ Coding Agent]</b> <span style='color:#0FE6B5;'>(research_brief)</span>: Intelligence gathered on modern UI frameworks.")
    hub.bus_browser.append("<b>[Coding Agent ➔ All]</b> <span style='color:#0FE6B5;'>(code_generated)</span>: Full stack application code and test suites authored.")
    hub.bus_browser.append("<b>[Image / Media Agent ➔ All]</b> <span style='color:#0FE6B5;'>(image_rendered)</span>: Header visual and SVG architecture diagram rendered.")
    hub.bus_browser.append("<b>[Self-Reflection ➔ Orchestrator]</b> <span style='color:#0FE6B5;'>(quality_check)</span>: Deliverables score: 98% (AST syntax valid, quality verified).")

    from ui.components.message_bubble import format_markdown_to_html
    sample_deliverable = (
        "## 🎯 Goal Accomplished\n"
        "> **Build a website, create images, write code, analyze data and deploy it**\n\n"
        "### 🤖 Specialized Agents Collaboration:\n"
        "- ✅ **Project Strategy & Milestones** (`Planning Agent`): Roadmaps and milestones established.\n"
        "- ✅ **Software Engineering & Implementation** (`Coding Agent`): Responsive web application and backend authored.\n"
        "- ✅ **Visual Media & Diagram Generation** (`Image / Media Agent`): High-res visuals and architecture diagrams rendered.\n"
        "- ✅ **Quantitative Data Analysis & Metrics** (`Data Analysis Agent`): Statistical benchmarks and metrics computed.\n\n"
        "### 🔍 Self-Reflection Score: **98%**\n"
        "- Code syntax and structure verified successfully.\n"
        "- Written assets and documentation met quality standards.\n"
    )
    hub.out_browser.setHtml(format_markdown_to_html(sample_deliverable))

    app.processEvents()

    # Capture MainWindow with Multi-Agent Hub
    p_main = ARTIFACTS_DIR / "multi_agent_hub_window.png"
    win.grab().save(str(p_main))
    print(f"Captured: {p_main}")

    # Capture Multi-Agent Hub view specifically
    p_hub = ARTIFACTS_DIR / "multi_agent_hub_view.png"
    hub.grab().save(str(p_hub))
    print(f"Captured: {p_hub}")

    win.close()

if __name__ == "__main__":
    run()
