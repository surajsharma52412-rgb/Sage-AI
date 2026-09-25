"""
Visual Verification Script for Sage Universal AI Auto Router.
Captures high-resolution screenshots of:
1. Global Ranking Queue (All 54 Models)
2. By Task Type filter (Coding / Development Queue)
3. By Provider filter (Google Gemini)
4. Double-click Factor Score Breakdown Dialog
Saves screenshots directly to the artifacts directory.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

out_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\aa19c0a8-7e1d-4b6c-b405-ecf2ecfd2f11")
out_dir.mkdir(parents=True, exist_ok=True)

app = QApplication.instance() or QApplication(sys.argv)

from ui.main_window import MainWindow
win = MainWindow()
win.resize(1380, 880)
win.show()
app.processEvents()

# 1. Capture Global Ranking Dashboard (Overall Rank - All 54 Models)
win._handle_navigation("auto_router")
app.processEvents()
time.sleep(0.5)
app.processEvents()
win.grab().save(str(out_dir / "sage_auto_router_global_queue.png"))
print("Saved sage_auto_router_global_queue.png")

# 2. Capture Coding Task Filter
view = win.global_ranking_view
view._set_filter_mode("task")
view.task_combo.setCurrentIndex(1)  # Coding / Development
app.processEvents()
time.sleep(0.4)
app.processEvents()
win.grab().save(str(out_dir / "sage_auto_router_coding_queue.png"))
print("Saved sage_auto_router_coding_queue.png")

# 3. Capture By Provider Filter
view._set_filter_mode("provider")
view.provider_combo.setCurrentIndex(1)  # Google Gemini
app.processEvents()
time.sleep(0.4)
app.processEvents()
win.grab().save(str(out_dir / "sage_auto_router_by_provider.png"))
print("Saved sage_auto_router_by_provider.png")

# 4. Open Factor Breakdown Dialog for Rank #1 Model
view._set_filter_mode("overall")
app.processEvents()
time.sleep(0.3)
app.processEvents()

from ui.components.global_ranking_view import FactorBreakdownDialog
if view._cached_scores:
    top_score = view._cached_scores[0]
    dlg = FactorBreakdownDialog(top_score, parent=win)
    dlg.show()
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()
    dlg.grab().save(str(out_dir / "sage_auto_router_factor_breakdown.png"))
    print("Saved sage_auto_router_factor_breakdown.png")
    dlg.close()

win.close()
print("All screenshots successfully captured!")
