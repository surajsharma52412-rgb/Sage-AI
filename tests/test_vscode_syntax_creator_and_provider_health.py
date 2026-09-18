import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from ui.components.syntax_highlighter import MultiLanguageHighlighter, PALETTE
from ui.components.code_editor import CodeEditor
from ui.components.analytics_view import AnalyticsView
from engine.request_analyzer import RequestAnalyzer
from engine.providers.local_facts_provider import LocalFactsProvider
from engine.router import FallbackRouter
from database.db_manager import get_db
from config import INTENT_LOCAL_FACTS


class TestVsCodeSyntaxCreatorAndProviderHealth(unittest.TestCase):
    def setUp(self):
        self.db = get_db()

    def test_vscode_palette_values(self):
        """Verify the exact VS Code Dark+ color palette is in place."""
        self.assertEqual(PALETTE["control_keyword"].lower(), "#c586c0")  # magenta
        self.assertEqual(PALETTE["keyword"].lower(), "#569cd6")          # blue
        self.assertEqual(PALETTE["function"].lower(), "#dcdcaa")         # warm yellow
        self.assertEqual(PALETTE["type"].lower(), "#4ec9b0")             # mint/teal
        self.assertEqual(PALETTE["string"].lower(), "#ce9178")           # terracotta/peach
        self.assertEqual(PALETTE["number"].lower(), "#b5cea8")           # pale green
        self.assertEqual(PALETTE["comment"].lower(), "#6a9955")          # forest green

    def test_python_syntax_rules_match_vscode(self):
        """Verify Python syntax highlighter loads control vs decl keywords and types."""
        editor = CodeEditor()
        editor.set_language("Python")
        highlighter = editor.highlighter
        self.assertIsNotNone(highlighter)
        self.assertTrue(len(highlighter.rules) >= 10)

        # Ensure rules contain control keywords, decl keywords, functions, types, strings
        rule_colors = [fmt.foreground().color().name().lower() for _, fmt in highlighter.rules]
        self.assertIn("#c586c0", rule_colors)  # control keywords
        self.assertIn("#569cd6", rule_colors)  # decl keywords
        self.assertIn("#dcdcaa", rule_colors)  # functions
        self.assertIn("#4ec9b0", rule_colors)  # types
        self.assertIn("#ce9178", rule_colors)  # strings
        self.assertIn("#b5cea8", rule_colors)  # numbers
        self.assertIn("#6a9955", rule_colors)  # comments
        editor.deleteLater()

    def test_multiline_docstring_and_def_formatting(self):
        """Verify multiline docstrings and def function formatting apply correct VS Code colors."""
        editor = CodeEditor()
        editor.set_language("Python")
        sample_code = '"""\nDocstring line 1\n"""\ndef run():\n    app = QApplication.instance()'
        editor.setPlainText(sample_code)

        doc = editor.document()
        # Line 1: """
        b1 = doc.findBlockByLineNumber(0)
        f1 = b1.layout().formats()
        self.assertTrue(len(f1) > 0)
        self.assertEqual(f1[0].format.foreground().color().name().lower(), "#ce9178")

        # Line 4: def run():
        b4 = doc.findBlockByLineNumber(3)
        f4 = b4.layout().formats()
        # 'def' must be #569cd6 (blue)
        def_fmt = next((f for f in f4 if f.start == 0 and f.length == 3), None)
        self.assertIsNotNone(def_fmt)
        self.assertEqual(def_fmt.format.foreground().color().name().lower(), "#569cd6")

        # 'run' must be #dcdcaa (yellow)
        run_fmt = next((f for f in f4 if f.start == 4 and f.length == 3), None)
        self.assertIsNotNone(run_fmt)
        self.assertEqual(run_fmt.format.foreground().color().name().lower(), "#dcdcaa")

        editor.deleteLater()

    def test_creator_intent_routing(self):
        """Verify questions about creator route to local facts for instant offline response."""
        queries = [
            "who created you",
            "who is your creator",
            "who made you",
            "who built sage ai",
            "who is suraj sharma",
            "who is the developer of sage ai",
            "who designed you",
        ]
        for q in queries:
            res = RequestAnalyzer.analyze(q)
            self.assertEqual(
                res["intent"],
                INTENT_LOCAL_FACTS,
                f"Query '{q}' should route to INTENT_LOCAL_FACTS, got {res['intent']}"
            )

    def test_local_facts_creator_answer(self):
        """Verify LocalFactsProvider explicitly names Suraj Sharma as creator."""
        provider = LocalFactsProvider()
        queries = [
            "who created you?",
            "who is your creator",
            "who made sage ai",
            "who is Suraj Sharma",
        ]
        for q in queries:
            resp = provider.generate(q)
            self.assertIn(
                "Suraj Sharma",
                resp.text,
                f"Response for '{q}' must include Suraj Sharma"
            )
            self.assertIn("Creator", resp.text)

    def test_system_prompt_permanent_creator(self):
        """Verify Router system prompt permanently includes Suraj Sharma across personas."""
        router = FallbackRouter()
        prompt = router._get_persona_system_prompt()
        self.assertIn("Suraj Sharma", prompt)
        self.assertIn("permanent, immutable", prompt)

    def test_dynamic_provider_health_status(self):
        """Verify provider health checks actual keys: Inactive without key, Active with key."""
        analytics = AnalyticsView()
        
        # Save original keys to restore after test
        orig_groq = self.db.get_setting("groq_api_key")

        try:
            # 1. Without key: Groq must be Inactive
            self.db.set_setting("groq_api_key", "")
            health = analytics._get_provider_health()
            groq_info = next(p for p in health if p["id"] == "groq")
            self.assertFalse(groq_info["active"])
            self.assertIn("Inactive", groq_info["status_text"])
            self.assertEqual(groq_info["status_color"], "#ef4444")

            # 2. With key: Groq must be Active
            self.db.set_setting("groq_api_key", "gsk_test_key_12345")
            health_after = analytics._get_provider_health()
            groq_info_after = next(p for p in health_after if p["id"] == "groq")
            self.assertTrue(groq_info_after["active"])
            self.assertIn("Active", groq_info_after["status_text"])
            self.assertEqual(groq_info_after["status_color"], "#10b981")

        finally:
            # Restore original key
            self.db.set_setting("groq_api_key", orig_groq or "")
            analytics.deleteLater()


if __name__ == "__main__":
    unittest.main()
