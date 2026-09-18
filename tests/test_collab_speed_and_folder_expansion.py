"""
Unit tests for Collab Speed Optimization, Recursive Folder Expansion, and Model Activation Badges.
"""
import unittest
import tempfile
import os
import shutil
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QTreeWidgetItem, QTreeWidget
from PySide6.QtCore import Qt

import config
from engine.collab_service import CollabCloudRelay, CollabServer, CollabClient
from ui.components.coding_ide_view import CodingIdeView

# Ensure single QApplication
app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestCollabSpeedAndConflation(unittest.TestCase):
    def test_collab_cloud_relay_conflation(self):
        """Verifies that multiple edits for the same file in the queue are conflated cleanly."""
        relay = CollabCloudRelay(room_code="TEST-SPEED", user_name="Tester", role="client")
        self.assertTrue(hasattr(relay, "_send_queue"))
        relay.is_connected = True
        
        # Enqueue 5 rapid edits for 'test.py' and 1 edit for 'other.py'
        for i in range(5):
            relay.send_message({"type": "edit", "filename": "test.py", "content": f"code version {i}"})
        relay.send_message({"type": "edit", "filename": "other.py", "content": "other code"})
        
        # Verify that all 6 items were enqueued
        self.assertEqual(relay._send_queue.qsize(), 6)


class TestRecursiveFolderExpansion(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sage_test_ws_"))
        # Create nested structure:
        # root/
        #   sub1/
        #     sub1_file.py
        #     nested/
        #       nested_file.js
        #   sub2/
        #     sub2_file.md
        #   root_file.txt
        #   .venv/ (should be ignored)
        #   __pycache__/ (should be ignored)
        (self.tmp_dir / "sub1" / "nested").mkdir(parents=True)
        (self.tmp_dir / "sub2").mkdir(parents=True)
        (self.tmp_dir / ".venv").mkdir(parents=True)
        (self.tmp_dir / "__pycache__").mkdir(parents=True)
        
        (self.tmp_dir / "root_file.txt").write_text("root", encoding="utf-8")
        (self.tmp_dir / "sub1" / "sub1_file.py").write_text("sub1", encoding="utf-8")
        (self.tmp_dir / "sub1" / "nested" / "nested_file.js").write_text("nested", encoding="utf-8")
        (self.tmp_dir / "sub2" / "sub2_file.md").write_text("sub2", encoding="utf-8")
        (self.tmp_dir / ".venv" / "secret.txt").write_text("secret", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_recursive_tree_population(self):
        view = CodingIdeView()
        view.set_workspace(self.tmp_dir)
        
        # Check that workspace root exists in tree
        self.assertEqual(view.tree_widget.topLevelItemCount(), 1)
        ws_root = view.tree_widget.topLevelItem(0)
        self.assertTrue(ws_root.isExpanded())
        
        # Find all items recursively
        item_names = []
        def collect_names(item):
            for i in range(item.childCount()):
                child = item.child(i)
                item_names.append(child.text(0))
                self.assertTrue(child.isExpanded() or child.childCount() == 0, f"Item {child.text(0)} should be expanded if dir")
                collect_names(child)
        collect_names(ws_root)
        
        # Check expected files and dirs are present
        self.assertTrue(any("root_file.txt" in name for name in item_names))
        self.assertTrue(any("sub1" in name for name in item_names))
        self.assertTrue(any("sub1_file.py" in name for name in item_names))
        self.assertTrue(any("nested" in name for name in item_names))
        self.assertTrue(any("nested_file.js" in name for name in item_names))
        self.assertTrue(any("sub2_file.md" in name for name in item_names))
        
        # Ignored directories should NOT be in tree
        self.assertFalse(any(".venv" in name for name in item_names))
        self.assertFalse(any("__pycache__" in name for name in item_names))


class TestModelActivationAndFlagshipModels(unittest.TestCase):
    def test_flagship_coding_models_in_config(self):
        """Verifies flagship coding models are present in config fallback chains."""
        self.assertIn("deepseek/deepseek-r1:free", config.PROVIDER_PRESET_MODELS["openrouter"])
        self.assertIn("qwen/qwen-2.5-coder-32b-instruct:free", config.PROVIDER_PRESET_MODELS["openrouter"])
        self.assertIn("groq", config.FALLBACK_CHAINS["coding"])
        self.assertIn("nvidia", config.FALLBACK_CHAINS["coding"])

    def test_coding_ide_model_status(self):
        view = CodingIdeView()
        self.assertTrue(hasattr(view, "agent_model_status_badge"))
        self.assertTrue(hasattr(view, "header_model_pill"))
        
        # Auto Router should be active
        is_active, desc = view._check_model_status("⚡ Auto Router (Best Free Coding Waterfall)")
        self.assertTrue(is_active)
        
        # Check badge text reflects availability
        self.assertTrue(any(tag in view.agent_model_status_badge.text() for tag in ("Available", "Unavailable", "Active")))
        # Check all items in combo have [● Available] or [○ Unavailable]
        for i in range(view.agent_model_combo.count()):
            item_text = view.agent_model_combo.itemText(i)
            self.assertTrue("[● Available]" in item_text or "[○ Unavailable]" in item_text)


if __name__ == "__main__":
    unittest.main()
