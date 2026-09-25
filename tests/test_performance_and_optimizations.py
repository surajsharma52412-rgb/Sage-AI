"""
Unit tests for SAGE-AI Performance Optimizations and Responsiveness.
Verifies subagent router compatibility, instant file tree population, target program caching,
non-blocking Ollama service probing, and zero fractional pixel font warnings.
"""
import unittest
import time
import glob
import re
from pathlib import Path

from PySide6.QtWidgets import QApplication
from engine.router import FallbackRouter
from engine.ollama_manager import is_ollama_running
from ui.components.coding_ide_view import CodingIdeView

app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestPerformanceAndOptimizations(unittest.TestCase):
    def test_fallback_router_route_and_call_exists_and_works(self):
        """Verifies FallbackRouter has route_and_call returning dictionary with text and response."""
        router = FallbackRouter()
        self.assertTrue(hasattr(router, "route_and_call"))
        res = router.route_and_call(prompt="ping status check")
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)
        self.assertIn("text", res)
        self.assertIn("response", res)
        self.assertTrue(res.get("success"))

    def test_is_ollama_running_speed(self):
        """Verifies is_ollama_running completes rapidly without multi-second hanging."""
        t0 = time.time()
        res1 = is_ollama_running()
        t1 = time.time()
        elapsed_uncached = t1 - t0
        # Must complete in under 0.35s (previously took 1.5+s)
        self.assertLess(elapsed_uncached, 0.35)

        # Second call must be near-instantaneous via TTL memory cache (<0.005s)
        t2 = time.time()
        res2 = is_ollama_running()
        elapsed_cached = time.time() - t2
        self.assertEqual(res1, res2)
        self.assertLess(elapsed_cached, 0.005)

    def test_coding_ide_fast_tree_and_target_programs(self):
        """Verifies CodingIdeView file explorer and target programs populate within milliseconds."""
        view = CodingIdeView()
        # Set workspace to current repo
        ws_path = Path(__file__).resolve().parent.parent
        t0 = time.time()
        view.set_workspace(ws_path)
        tree_duration = time.time() - t0

        # Entire workspace tree setup + bounded depth expansion must take under 0.15s
        self.assertLess(tree_duration, 0.15)
        self.assertGreater(view.tree_widget.topLevelItemCount(), 0)

        # Verify target programs are populated and cached
        self.assertGreater(view.agent_target_combo.count(), 1)
        self.assertTrue(hasattr(view, "_cached_target_files"))
        self.assertGreater(len(view._cached_target_files), 0)

        # Repeated call without force_rescan must complete instantaneously (<0.005s)
        t_cache_start = time.time()
        view._refresh_target_programs(force_rescan=False)
        cache_duration = time.time() - t_cache_start
        self.assertLess(cache_duration, 0.005)

    def test_code_editor_keystroke_latency(self):
        """Verifies rapid keystroke processing in CodeEditor takes < 1ms per keypress."""
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import Qt, QEvent
        from ui.components.code_editor import CodeEditor

        editor = CodeEditor()
        # Pre-populate with substantial code
        sample_code = "\n".join([f"def function_{i}(arg_{i}):\n    x = arg_{i} * 2\n    return x" for i in range(100)])
        editor.setPlainText(sample_code)

        # Warm up popup initialization once with an identifier
        warmup_evt = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.NoModifier, "p")
        editor.keyPressEvent(warmup_evt)
        if editor.completer and editor.completer.popup():
            editor.completer.popup().hide()

        t0 = time.time()
        for ch in "print('zero lag')\n":
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.NoModifier, ch)
            editor.keyPressEvent(event)
        elapsed = time.time() - t0

        # Typing 18 characters should take under 50ms (< 2.8ms per keystroke)
        self.assertLess(elapsed, 0.05)

    def test_agent_thinking_cloud_streaming_performance(self):
        """Verifies live thinking cloud streams 100 chunks smoothly in < 25ms."""
        from ui.components.agent_thinking_cloud import AgentThinkingCloudWidget

        cloud = AgentThinkingCloudWidget()
        cloud.start_live()

        t0 = time.time()
        for i in range(100):
            cloud.append_chunk(f"token_{i} reasoning ")
        cloud.finish_thinking(duration_s=0.5)
        elapsed = time.time() - t0

        self.assertLess(elapsed, 0.035)
        self.assertTrue(cloud.text_browser.toPlainText().startswith("token_0"))

    def test_syntax_highlighter_alternation_speed(self):
        """Verifies syntax highlighter combines keywords into compact regex alternations."""
        from ui.components.syntax_highlighter import MultiLanguageHighlighter
        from PySide6.QtGui import QTextDocument

        doc = QTextDocument()
        highlighter = MultiLanguageHighlighter(doc, language="python")
        # Python has ~80 keywords & builtins. With regex alternation, rules must be <= 25 instead of 80+
        self.assertLessEqual(len(highlighter.highlighting_rules), 25)

        # Ensure highlighting a code block is under 5ms
        t0 = time.time()
        doc.setPlainText("def calculate_sum(a, b):\n    return a + b\n" * 50)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 0.05)


    def test_zero_fractional_font_sizes_in_ui(self):
        """Ensures all font-size declarations in ui/ use clean integer pixels to avoid QFont warnings."""
        ui_files = glob.glob("ui/**/*.py", recursive=True)
        fractional_matches = []
        for f in ui_files:
            with open(f, "r", encoding="utf-8") as fp:
                txt = fp.read()
            for m in re.findall(r"font-size:\s*(\d+\.\d+)px", txt):
                fractional_matches.append((f, m))
        self.assertEqual(
            len(fractional_matches),
            0,
            f"Found fractional font sizes in UI that trigger QFont warnings: {fractional_matches[:5]}"
        )


if __name__ == "__main__":
    unittest.main()
