"""
Generates screenshots of the Free Tier badges and Limit Reset Times in ModelSelectorPopup and UsageDialog.
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from database.db_manager import get_db
from engine.model_scanner import ModelScanner
from ui.components.model_selector_popup import ModelSelectorPopup
from ui.components.usage_dialog import UsageDialog

db = get_db()
# Setup mock provider quotas with free tier and reset time
db.save_provider_quota("gemini", {
    "total_limit": 1500.0,
    "used_amount": 120.0,
    "remaining_amount": 1380.0,
    "currency_or_unit": "Requests/Day",
    "is_free_tier": True,
    "tier_type": "Free Tier",
    "reset_time": ModelScanner.get_provider_reset_info("gemini")["reset_time"]
})

db.save_provider_quota("groq", {
    "total_limit": 14400.0,
    "used_amount": 450.0,
    "remaining_amount": 13950.0,
    "currency_or_unit": "Requests/Day",
    "is_free_tier": True,
    "tier_type": "Free Tier",
    "reset_time": ModelScanner.get_provider_reset_info("groq")["reset_time"]
})

# 1. Capture ModelSelectorPopup
popup = ModelSelectorPopup()
popup.resize(520, 680)
popup.show()
app.processEvents()

pix = popup.grab()
artifacts_dir = Path(r"C:\Users\sura5\.gemini\antigravity-ide\brain\feec1930-ed47-4c4a-b17f-11849cfb1f7d")
popup_path = artifacts_dir / "free_tier_model_selector.png"
pix.save(str(popup_path), "PNG")
popup.close()
print(f"Saved popup screenshot: {popup_path}")

# 2. Capture UsageDialog
ud = UsageDialog()
ud.resize(840, 660)
ud.show()
app.processEvents()

pix_ud = ud.grab()
ud_path = artifacts_dir / "free_tier_usage_dialog.png"
pix_ud.save(str(ud_path), "PNG")
ud.close()
print(f"Saved usage dialog screenshot: {ud_path}")
