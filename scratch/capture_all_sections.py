import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

out_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\400adf20-1312-4401-8865-2ea7bc5f3096")
out_dir.mkdir(parents=True, exist_ok=True)

app = QApplication.instance() or QApplication(sys.argv)

from ui.main_window import MainWindow
win = MainWindow()
win.resize(1380, 880)
win.show()
app.processEvents()

# 1. Capture Home Dashboard
win._handle_navigation("home")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_home_dashboard.png"))
print("Saved sage_home_dashboard.png")

# 2. Capture Chat View
win._handle_navigation("chat")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_chat_viewport.png"))
print("Saved sage_chat_viewport.png")

# 3. Capture Coding IDE
win._handle_navigation("coding_agent")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_coding_ide.png"))
print("Saved sage_coding_ide.png")

# 4. Capture Automations Studio
win._handle_navigation("automations")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_automations_studio.png"))
print("Saved sage_automations_studio.png")

# 5. Capture Analytics / Model Usage
win._handle_navigation("usage")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_model_usage_analytics.png"))
print("Saved sage_model_usage_analytics.png")

# 6. Capture Multi-Agent Hub
win._handle_navigation("multi_agent")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_multi_agent_hub.png"))
print("Saved sage_multi_agent_hub.png")

# 7. Capture Knowledge View
win._handle_navigation("knowledge")
app.processEvents()
time.sleep(0.3)
app.processEvents()
win.grab().save(str(out_dir / "sage_knowledge_view.png"))
print("Saved sage_knowledge_view.png")

win.close()
print("All screenshots captured successfully!")
