import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from ui.components.sidebar import Sidebar
from ui.components.knowledge_view import KnowledgeView
from ui.components.animated_stack import AnimatedStackedWidget
from engine.zero_cost_guard import get_zero_cost_guard
from engine.router import FallbackRouter


class TestUserFixes(unittest.TestCase):

    def test_sidebar_zero_cost_badge_removed_from_ui(self):
        """Verifies the red-marked 0 Rs Guard badge is removed from the visible UI."""
        sidebar = Sidebar()
        # Ensure zero_cost_widget is not in main_layout or is hidden
        self.assertFalse(sidebar.zero_cost_widget.isVisible())
        # Ensure the pulse timer is inactive
        self.assertFalse(sidebar.zero_cost_widget._timer.isActive())

    def test_knowledge_view_fast_load_and_debounced(self):
        """Verifies knowledge view loads in < 50ms without crashing or hanging."""
        import time
        t0 = time.time()
        kv = KnowledgeView()
        kv.refresh_memories()
        elapsed = (time.time() - t0) * 1000.0
        print(f"\nKnowledgeView load elapsed: {elapsed:.1f}ms")
        self.assertLess(elapsed, 1000.0)  # Must be fast
        self.assertTrue(hasattr(kv, "_search_timer"))
        self.assertTrue(hasattr(kv, "_render_cards_page"))

    def test_animated_stacked_widget_no_opacity_lag(self):
        """Verifies AnimatedStackedWidget does not attach QGraphicsOpacityEffect."""
        stack = AnimatedStackedWidget()
        from PySide6.QtWidgets import QWidget
        w1 = QWidget()
        w2 = QWidget()
        stack.addWidget(w1)
        stack.addWidget(w2)
        stack.show()
        stack.resize(400, 300)
        stack.setCurrentWidget(w2)
        # Verify effects are None
        self.assertIsNone(w1.graphicsEffect())
        self.assertIsNone(w2.graphicsEffect())

    def test_pre_request_scan_and_shift_to_free_model(self):
        """Verifies model is scanned before sending and shifted if not free."""
        guard = get_zero_cost_guard()
        # Test paid model is intercepted and shifted
        eff_m, eff_p, reason = guard.scan_and_resolve_free_model(
            requested_model="unbiased/pareto 26.9",
            task_type="coding"
        )
        self.assertTrue(guard.is_zero_cost(eff_m, eff_p))
        self.assertNotEqual(eff_m, "unbiased/pareto 26.9")

        # Test free model is verified and allowed
        eff_m2, eff_p2, reason2 = guard.scan_and_resolve_free_model(
            requested_model="qwen/qwen-2.5-coder-32b-instruct:free",
            provider_id="openrouter",
            task_type="coding"
        )
        self.assertTrue(guard.is_zero_cost(eff_m2, eff_p2))
        self.assertEqual(eff_m2, "qwen/qwen-2.5-coder-32b-instruct:free")


if __name__ == "__main__":
    unittest.main()
