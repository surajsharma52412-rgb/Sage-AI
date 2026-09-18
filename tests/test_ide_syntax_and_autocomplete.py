import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QColor

# Ensure QApplication exists for GUI components
app = QApplication.instance() or QApplication(sys.argv)

from ui.components.syntax_highlighter import MultiLanguageHighlighter
from ui.components.code_editor import CodeEditor, LANGUAGE_COMPLETIONS
from ui.components.coding_ide_view import CodingIdeView


class TestIdeSyntaxAndAutocomplete(unittest.TestCase):
    def setUp(self):
        self.editor = CodeEditor()

    def tearDown(self):
        self.editor.deleteLater()

    def test_language_detection(self):
        """Test file extension auto-detection."""
        self.assertEqual(self.editor.set_language_by_filename("main.py"), "Python")
        self.assertEqual(self.editor.set_language_by_filename("app.js"), "JavaScript")
        self.assertEqual(self.editor.set_language_by_filename("index.ts"), "TypeScript")
        self.assertEqual(self.editor.set_language_by_filename("index.html"), "HTML")
        self.assertEqual(self.editor.set_language_by_filename("style.css"), "CSS")
        self.assertEqual(self.editor.set_language_by_filename("engine.cpp"), "C/C++")
        self.assertEqual(self.editor.set_language_by_filename("main.rs"), "Rust")
        self.assertEqual(self.editor.set_language_by_filename("server.go"), "Go")
        self.assertEqual(self.editor.set_language_by_filename("query.sql"), "SQL")
        self.assertEqual(self.editor.set_language_by_filename("data.json"), "JSON")
        self.assertEqual(self.editor.set_language_by_filename("script.sh"), "Shell")
        self.assertEqual(self.editor.set_language_by_filename("notes.md"), "Markdown")
        self.assertEqual(self.editor.set_language_by_filename("unknown.xyz"), "Text")

    def test_python_syntax_highlighting(self):
        """Test that syntax highlighter applies formatting rules in Python."""
        self.editor.set_language("Python")
        self.editor.setPlainText('def hello():\n    # greeting\n    print("world")\n    x = 123\n')

        # Check that highlighter is attached to document
        doc = self.editor.document()
        self.assertIsNotNone(self.editor.highlighter)
        self.assertEqual(self.editor.highlighter.current_language, "Python")

        # Verify highlighter rules exist
        rules = self.editor.highlighter.rules
        self.assertTrue(len(rules) > 0, "Highlighter should have rules defined for Python")

    def test_multi_language_rules(self):
        """Test that every supported language produces rules and built-ins."""
        languages = [
            "Python", "JavaScript", "TypeScript", "HTML", "CSS",
            "C/C++", "Rust", "Go", "SQL", "JSON", "Shell", "Markdown"
        ]
        for lang in languages:
            self.editor.set_language(lang)
            self.assertEqual(self.editor.highlighter.current_language, lang)
            self.assertTrue(
                len(self.editor.highlighter.rules) > 0,
                f"Highlighter must have rules for {lang}"
            )

    def test_autocomplete_prefix_p_shows_print(self):
        """User requirement: typing 'p' in Python shows syntax available like 'print'."""
        self.editor.set_language("Python")
        py_words = LANGUAGE_COMPLETIONS.get("Python", [])
        self.assertIn("print", py_words)
        self.assertIn("pass", py_words)

        # Autocomplete model should contain 'print'
        model = self.editor.completer.model()
        items = [model.index(i, 0).data() for i in range(model.rowCount())]
        self.assertIn("print", items)
        self.assertIn("pass", items)

        # Matching prefix 'p'
        p_matches = [w for w in items if w.startswith("p")]
        self.assertIn("print", p_matches)
        self.assertTrue(len(p_matches) >= 3, f"Expected multiple 'p' matches, got {p_matches}")

    def test_autocomplete_multi_language_keywords(self):
        """Verify autocomplete wordlists for various languages."""
        self.editor.set_language("JavaScript")
        model = self.editor.completer.model()
        items = [model.index(i, 0).data() for i in range(model.rowCount())]
        self.assertIn("function", items)
        self.assertIn("const", items)
        self.assertIn("Promise", items)

        self.editor.set_language("Rust")
        model = self.editor.completer.model()
        items = [model.index(i, 0).data() for i in range(model.rowCount())]
        self.assertIn("fn", items)
        self.assertIn("println!", items)
        self.assertIn("struct", items)

        self.editor.set_language("Go")
        model = self.editor.completer.model()
        items = [model.index(i, 0).data() for i in range(model.rowCount())]
        self.assertIn("func", items)
        self.assertIn("package", items)

    def test_dynamic_word_harvesting(self):
        """Typing custom identifiers in editor adds them to completions."""
        self.editor.set_language("Python")
        self.editor.setPlainText("def custom_awesome_function():\n    return 42\n")
        words = self.editor._collect_document_words()
        self.assertIn("custom_awesome_function", words)

    def test_coding_ide_view_integration(self):
        """Test CodingIdeView language combo, icons, and runner labels."""
        ide = CodingIdeView()
        self.assertIsNone(ide.workspace_path)
        self.assertIn("No Folder Selected", ide.path_lbl.text())
        self.assertIsNotNone(ide.lang_combo)
        self.assertGreaterEqual(ide.lang_combo.count(), 10)

        # Test icon mappings
        self.assertEqual(ide._get_file_icon(".py"), "🐍")
        self.assertEqual(ide._get_file_icon(".js"), "📜")
        self.assertEqual(ide._get_file_icon(".ts"), "📘")
        self.assertEqual(ide._get_file_icon(".html"), "🌐")
        self.assertEqual(ide._get_file_icon(".rs"), "🦀")
        self.assertEqual(ide._get_file_icon(".go"), "🐹")
        self.assertEqual(ide._get_file_icon(".sql"), "🗄️")

        # Test runner text updates
        test_py = Path("test.py")
        ide.active_file = test_py
        ide._update_run_button_label()
        self.assertIn("Python", ide.run_btn.text())

        test_js = Path("script.js")
        ide.active_file = test_js
        ide._update_run_button_label()
        self.assertIn("Node.js", ide.run_btn.text())

        test_html = Path("index.html")
        ide.active_file = test_html
        ide._update_run_button_label()
        self.assertTrue(any(k in ide.run_btn.text() for k in ("Preview", "Browser")))

        test_rs = Path("main.rs")
        ide.active_file = test_rs
        ide._update_run_button_label()
        self.assertIn("Cargo", ide.run_btn.text())

        ide.deleteLater()


if __name__ == "__main__":
    unittest.main()
