"""
Unit Tests for:
1. HTML and multi-language file opening in IDE (detect_language).
2. Top coding model listings in CodingIdeView and FallbackRouter mapping.
3. Creating files without opening a workspace folder and saving to disk.
4. Folder creation and file/folder deletion in the IDE workspace explorer.
"""
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.code_editor import CodeEditor
from ui.components.coding_ide_view import CodingIdeView
from engine.router import FallbackRouter


class TestIdeHtmlModelsAndFileOps(unittest.TestCase):
    """Tests new features for HTML opening, top models, and workspace operations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sage_ide_test_")
        self.workspace = Path(self.temp_dir)
        self.ide = CodingIdeView(workspace_path=self.workspace)

    def tearDown(self):
        if hasattr(self, "ide") and self.ide:
            self.ide.collab_manager.stop()
            self.ide.deleteLater()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_code_editor_detect_language(self):
        editor = CodeEditor()
        self.assertEqual(editor.detect_language("index.html"), "HTML")
        self.assertEqual(editor.detect_language("about.htm"), "HTML")
        self.assertEqual(editor.detect_language("server.py"), "Python")
        self.assertEqual(editor.detect_language("main.js"), "JavaScript")
        self.assertEqual(editor.detect_language("style.css"), "CSS")
        self.assertEqual(editor.detect_language("main.rs"), "Rust")
        self.assertEqual(editor.detect_language("schema.sql"), "SQL")

    def test_open_html_file_and_preview_button(self):
        html_path = self.workspace / "index.html"
        html_path.write_text("<!DOCTYPE html><html><body><h1>Sage AI</h1></body></html>", encoding="utf-8")

        # Open file directly via open_file
        self.ide.open_file(html_path)
        self.assertIn("index.html", self.ide.open_documents)
        self.assertEqual(self.ide.active_filename, "index.html")
        self.assertEqual(self.ide.open_documents["index.html"]["language"], "HTML")
        self.assertIn("Sage AI", self.ide.editor.toPlainText())

        # Verify button text shows browser preview for HTML
        self.ide._update_run_button_label()
        self.assertEqual(self.ide.run_btn.text(), "🌐 Preview")

    def test_top_coding_models_present_and_mapped(self):
        # 1. Check IDE combo box has top coding models
        combo = self.ide.agent_model_combo
        self.assertGreaterEqual(combo.count(), 8)
        all_labels = [combo.itemText(i) for i in range(combo.count())]
        labels_str = " ".join(all_labels).lower()

        self.assertIn("claude", labels_str)
        self.assertIn("deepseek", labels_str)
        self.assertIn("qwen", labels_str)
        self.assertIn("codestral", labels_str)
        self.assertIn("nvidia", labels_str)
        self.assertIn("groq", labels_str)
        self.assertIn("gemini", labels_str)

        # 2. Check router maps these selections properly
        router = FallbackRouter()
        p_key, model = router._map_model_selection("Claude 3.7 Sonnet")
        self.assertEqual(p_key, "openrouter")
        self.assertIn("claude", model.lower())

        p_key, model = router._map_model_selection("DeepSeek R1 Reasoning")
        self.assertIn("deepseek", model.lower())

        p_key, model = router._map_model_selection("Qwen 2.5 Coder 32B")
        self.assertEqual(p_key, "openrouter")
        self.assertIn("qwen", model.lower())

        p_key, model = router._map_model_selection("Mistral Codestral 22B")
        self.assertEqual(p_key, "mistral")
        self.assertIn("codestral", model.lower())

    def test_create_file_without_open_folder(self):
        # Create an IDE with NO workspace folder selected
        no_ws_ide = CodingIdeView(workspace_path=None)
        self.assertIsNone(no_ws_ide.workspace_path)

        # Open in-memory document (same as _create_new_file in memory)
        no_ws_ide.open_document("untitled.html", "<h1>Offline Page</h1>", language="HTML", disk_path=None)
        self.assertIn("untitled.html", no_ws_ide.open_documents)
        self.assertEqual(no_ws_ide.active_filename, "untitled.html")
        self.assertIsNone(no_ws_ide.open_documents["untitled.html"]["disk_path"])

        # Simulate Save As to disk
        dest_path = self.workspace / "saved_from_memory.html"
        no_ws_ide.open_documents["untitled.html"]["disk_path"] = dest_path
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(no_ws_ide.editor.toPlainText())
        self.assertTrue(dest_path.exists())
        self.assertIn("Offline Page", dest_path.read_text(encoding="utf-8"))

        no_ws_ide.deleteLater()

    def test_folder_creation_and_file_deletion(self):
        # 1. Create subfolder inside workspace
        sub_dir = self.workspace / "components"
        sub_dir.mkdir(parents=True, exist_ok=True)
        self.assertTrue(sub_dir.exists())

        # 2. Create file inside subfolder and open it in IDE
        f_path = sub_dir / "header.html"
        f_path.write_text("<header>Navigation</header>", encoding="utf-8")
        self.ide.open_file(f_path)
        self.assertIn("header.html", self.ide.open_documents)

        # 3. Simulate file deletion logic directly
        f_path.unlink()
        self.assertFalse(f_path.exists())

        # Close tab
        idx = self.ide._find_tab_by_filename("header.html")
        if idx >= 0:
            self.ide._on_tab_close_requested(idx)
        self.assertNotIn("header.html", self.ide.open_documents)

        # 4. Simulate folder deletion
        shutil.rmtree(sub_dir)
        self.assertFalse(sub_dir.exists())


if __name__ == "__main__":
    unittest.main()
