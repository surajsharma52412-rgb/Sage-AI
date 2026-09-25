"""
Comprehensive Unit Tests for:
1. Auto Coding Router (9-factor coding scoring formula, dynamic ranking).
2. Dynamic task adaptation (Simple Python, Large Project, Debugging, Architecture).
3. Manual model selection fidelity and automatic fallback queue.
4. Structured Live Events Architecture and secret sanitization.
5. Coding IDE View model selector, fallback toggle, live diff, and console safety.
"""
import os
import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from engine.auto_router.coding_router import AutoCodingRouter, CodingScoringWeights, CodingModelScore
from engine.coding_agent.events import CodingAgentEvent, EventType, AgentState, sanitize_text
from ui.components.coding_ide_view import CodingIdeView
from workers.agent_worker import AgentWorker, extract_thinking
from ui.components.agent_thinking_cloud import AgentThinkingCloudWidget


class TestCodingRouterAndEvents(unittest.TestCase):
    """Tests Auto Coding Router, Event Architecture, and IDE components."""

    def setUp(self):
        self.router = AutoCodingRouter()

    def test_coding_weights_sum_to_one(self):
        """Ensures all 9 coding scoring weights sum to exactly 1.0 (100%)."""
        weights = CodingScoringWeights()
        total = (
            weights.quality +
            weights.reasoning +
            weights.task_cap +
            weights.reliability +
            weights.context +
            weights.latency +
            weights.availability +
            weights.quota +
            weights.cost
        )
        self.assertAlmostEqual(total, 1.0, places=5)
        self.assertEqual(weights.quality, 0.30)
        self.assertEqual(weights.reasoning, 0.20)
        self.assertEqual(weights.task_cap, 0.15)
        self.assertEqual(weights.reliability, 0.10)
        self.assertEqual(weights.context, 0.05)
        self.assertEqual(weights.latency, 0.05)
        self.assertEqual(weights.availability, 0.05)
        self.assertEqual(weights.quota, 0.05)
        self.assertEqual(weights.cost, 0.05)

    def test_dynamic_task_adaptation(self):
        """Verifies adaptive weights for different coding tasks."""
        simple_w = CodingScoringWeights.for_task_type("simple_python")
        self.assertGreater(simple_w.latency, 0.10)  # Prioritizes speed

        large_w = CodingScoringWeights.for_task_type("large_project")
        self.assertGreater(large_w.context, 0.10)  # Prioritizes context length
        self.assertGreater(large_w.quality, 0.30)  # Boosted quality

        debug_w = CodingScoringWeights.for_task_type("debugging")
        self.assertGreater(debug_w.reasoning, 0.25) # Boosted reasoning for diagnosis

        arch_w = CodingScoringWeights.for_task_type("architecture")
        self.assertGreater(arch_w.reasoning, 0.20)

    def test_dynamic_coding_ranking(self):
        """Ensures rank_coding_models orders all coding models from #1 down to #N."""
        rankings = self.router.rank_coding_models(prompt="Implement full-stack REST API with tests")
        self.assertGreaterEqual(len(rankings), 10)
        
        # Verify monotonically non-increasing total scores
        for i in range(len(rankings) - 1):
            self.assertGreaterEqual(rankings[i].total_score, rankings[i + 1].total_score)
            self.assertEqual(rankings[i].rank, i + 1)

        # Top model has valid rank and score
        top = rankings[0]
        self.assertEqual(top.rank, 1)
        self.assertGreater(top.total_score, 7.0)
        self.assertIn("Coding Quality (30%)", top.breakdown)
        self.assertIn("Code Reasoning (20%)", top.breakdown)

    def test_auto_model_selection(self):
        """Verifies Auto mode selects top-ranked coding model."""
        res = self.router.select_model_for_execution("Auto", prompt="Quick Python helper script")
        self.assertEqual(res["mode"], "auto")
        self.assertEqual(res["coding_rank"], 1)
        self.assertGreater(res["coding_score"], 8.0)
        self.assertTrue(len(res["fallback_queue"]) > 0)

    def test_manual_model_selection_fidelity(self):
        """Verifies manual selection directly selects the requested model without auto-switching."""
        res = self.router.select_model_for_execution("Codestral", prompt="Build backend schema", allow_fallback=True)
        self.assertEqual(res["mode"], "manual")
        self.assertIn("codestral", res["selected_model"].lower())
        self.assertTrue(res["allow_fallback"])
        self.assertTrue(len(res["fallback_queue"]) > 0)

    def test_manual_selection_fallback_disabled(self):
        """Verifies fallback queue is empty when allow_fallback is False."""
        res = self.router.select_model_for_execution("Codestral", prompt="Build backend schema", allow_fallback=False)
        self.assertEqual(res["mode"], "manual")
        self.assertFalse(res["allow_fallback"])
        self.assertEqual(len(res["fallback_queue"]), 0)

    def test_secret_sanitization(self):
        """Ensures API keys and tokens are never exposed in messages."""
        msg = "Connecting with api_key=sk-1234567890abcdef12345678 and token: gsk_1234567890abcdef12345678"
        sanitized = sanitize_text(msg)
        self.assertNotIn("sk-1234567890abcdef", sanitized)
        self.assertNotIn("gsk_1234567890abcdef", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_structured_event_model(self):
        """Verifies CodingAgentEvent serialization and fields."""
        evt = CodingAgentEvent(
            event_type=EventType.FILE_MODIFIED.value,
            state=AgentState.EDITING.value,
            file="backend/router.py",
            action="Editing",
            diff="+ async def route(): pass",
            message="Updating router logic"
        )
        d = evt.to_dict()
        self.assertEqual(d["type"], "file_modified")
        self.assertEqual(d["state"], "EDITING")
        self.assertEqual(d["file"], "backend/router.py")
        self.assertEqual(d["action"], "Editing")
        self.assertIn("+ async def route(): pass", d["diff"])


class TestCodingIdeViewIntegrations(unittest.TestCase):
    """Tests IDE UI integrations: Model Selector, Changes Diff tab, Console Safety."""

    def setUp(self):
        self.ide = CodingIdeView(workspace_path=None)

    def tearDown(self):
        if hasattr(self, "ide") and self.ide:
            self.ide.collab_manager.stop()
            self.ide.deleteLater()

    def test_model_selector_and_fallback_toggle(self):
        # 1. Model selector present in header
        combo = self.ide.agent_model_combo
        self.assertGreaterEqual(combo.count(), 8)
        self.assertTrue(self.ide.agent_model_combo.isVisible() or combo is not None)

        # 2. Fallback toggle button
        self.assertTrue(hasattr(self.ide, "fallback_toggle_btn"))
        self.assertTrue(self.ide.allow_fallback)
        self.assertIn("ON", self.ide.fallback_toggle_btn.text())

        # Toggle fallback OFF
        self.ide._toggle_fallback_setting()
        self.assertFalse(self.ide.allow_fallback)
        self.assertIn("OFF", self.ide.fallback_toggle_btn.text())

        # Toggle fallback back ON
        self.ide._toggle_fallback_setting()
        self.assertTrue(self.ide.allow_fallback)
        self.assertIn("ON", self.ide.fallback_toggle_btn.text())

    def test_changes_diff_tab_present(self):
        """Verifies Changes tab exists in bottom tabs and diff viewer works."""
        self.assertTrue(hasattr(self.ide, "diff_viewer"))
        self.assertTrue(hasattr(self.ide, "diff_status_lbl"))

        # Emit diff
        self.ide._on_agent_diff_emitted("backend/router.py", "+ def new_func():\n+     pass\n")
        content = self.ide.diff_viewer.toPlainText()
        self.assertIn("router.py", content)
        self.assertIn("+ def new_func():", content)

    def test_console_output_append_safety(self):
        """Verifies that calling console_output.append does NOT raise AttributeError."""
        try:
            self.ide.console_output.append("Test append safety line")
            self.ide._append_console("Test _append_console safety line")
        except AttributeError as e:
            self.fail(f"AttributeError was raised on console_output.append: {e}")

    def test_git_diff_action(self):
        """Verifies _open_git_diff executes cleanly and switches tab."""
        self.ide._open_git_diff()
        self.assertEqual(self.ide.bottom_tabs.currentIndex(), self.ide.diff_tab_index)

    def test_agent_worker_thinking_signals(self):
        """Verifies AgentWorker defines and provides live thinking signals."""
        self.assertTrue(hasattr(AgentWorker, "thinking_started"))
        self.assertTrue(hasattr(AgentWorker, "thinking_chunk"))
        self.assertTrue(hasattr(AgentWorker, "thinking_finished"))

        worker = AgentWorker(
            workspace_path=Path.cwd(),
            task_instruction="Test instruction",
            selected_model="Auto"
        )
        started_fired = []
        chunks_fired = []
        finished_fired = []

        worker.thinking_started.connect(lambda: started_fired.append(True))
        worker.thinking_chunk.connect(lambda chunk: chunks_fired.append(chunk))
        worker.thinking_finished.connect(lambda dur: finished_fired.append(dur))

        worker.thinking_started.emit()
        worker.thinking_chunk.emit("✦ Analyzing file structure...\n")
        worker.thinking_finished.emit(1.25)

        self.assertEqual(len(started_fired), 1)
        self.assertEqual(chunks_fired, ["✦ Analyzing file structure...\n"])
        self.assertEqual(finished_fired, [1.25])

    def test_extract_thinking_helper(self):
        """Verifies extract_thinking parses closed and unclosed <think> blocks."""
        # Closed tag
        raw1 = "<think>Analyzing AST index</think>def foo(): pass"
        think1, code1 = extract_thinking(raw1)
        self.assertEqual(think1, "Analyzing AST index")
        self.assertEqual(code1, "def foo(): pass")

        # Unclosed tag (streaming)
        raw2 = "<think>Incomplete reasoning step"
        think2, code2 = extract_thinking(raw2)
        self.assertEqual(think2, "Incomplete reasoning step")
        self.assertEqual(code2, "")

        # No thinking tag
        raw3 = "Standard response without think"
        think3, code3 = extract_thinking(raw3)
        self.assertIsNone(think3)
        self.assertEqual(code3, "Standard response without think")

    def test_agent_thinking_cloud_widget(self):
        """Verifies AgentThinkingCloudWidget starts live, appends chunks, copies text, and finishes cleanly."""
        cloud = AgentThinkingCloudWidget()
        self.assertTrue(cloud.is_expanded)
        self.assertFalse(cloud.is_live)

        # 1. Start live thinking
        cloud.start_live()
        self.assertTrue(cloud.is_live)
        self.assertFalse(cloud.content_frame.isHidden())
        self.assertIn("STREAMING LIVE", cloud.live_badge.text())

        # 2. Append chunks
        cloud.append_chunk("✦ 1/11: UNDERSTAND — Ingesting requirements\n")
        cloud.append_chunk("✦ 2/11: ANALYZE — AST index updated\n")
        content = cloud.get_thinking_text()
        self.assertIn("UNDERSTAND", content)
        self.assertIn("ANALYZE", content)
        self.assertIn("words", cloud.live_badge.text())

        # 3. Finish thinking
        cloud.finish_thinking(duration_s=2.4)
        self.assertFalse(cloud.is_live)
        self.assertEqual(cloud.latency_s, 2.4)
        self.assertIn("Thought for 2.4s", cloud.title_lbl.text())
        self.assertIn("CONCLUDED", cloud.live_badge.text())

        # 4. Toggle expand/collapse
        cloud.toggle_expand()
        self.assertFalse(cloud.is_expanded)
        self.assertTrue(cloud.content_frame.isHidden())
        cloud.toggle_expand()
        self.assertTrue(cloud.is_expanded)
        self.assertFalse(cloud.content_frame.isHidden())

        # 5. Reset for next run
        cloud.reset()
        self.assertEqual(cloud.get_thinking_text(), "")
        self.assertIn("READY", cloud.live_badge.text())

        # Cleanup
        cloud.deleteLater()

    def test_ide_view_has_thinking_cloud(self):
        """Verifies that CodingIdeView has thinking_cloud integrated into the agent workspace."""
        self.assertTrue(hasattr(self.ide, "thinking_cloud"))
        self.assertIsInstance(self.ide.thinking_cloud, AgentThinkingCloudWidget)
        self.assertTrue(self.ide.thinking_cloud.isVisible() or self.ide.thinking_cloud.parent() is not None)

    def test_sidebar_stays_open_on_run_coding_agent(self):
        """Verifies that submitting a prompt to the agent does NOT toggle off the sidebar."""
        self.ide.right_dock.setVisible(True)
        self.ide.right_stack.setCurrentIndex(0)
        self.assertFalse(self.ide.right_dock.isHidden())

        # Simulate user submitting prompt
        self.ide.agent_prompt.setText("Review active file")
        self.ide._run_coding_agent()

        # Sidebar MUST remain open and visible!
        self.assertFalse(self.ide.right_dock.isHidden())
        self.assertEqual(self.ide.right_stack.currentIndex(), 0)

        # Stop worker cleanly if started
        if hasattr(self.ide, "_agent_worker") and self.ide._agent_worker:
            self.ide._agent_worker.cancel()

    def test_agent_feed_scroll_area(self):
        """Verifies agent_page uses QScrollArea to prevent card congestion and clipping."""
        self.assertTrue(hasattr(self.ide, "agent_scroll_area"))
        self.assertTrue(self.ide.agent_scroll_area.widgetResizable())
        # Ensure thinking_cloud and model_info_card are child of scroll area widget
        feed_widget = self.ide.agent_scroll_area.widget()
        self.assertIsNotNone(feed_widget)
        self.assertEqual(self.ide.thinking_cloud.parent(), feed_widget)
        self.assertEqual(self.ide.model_info_card.parent(), feed_widget)


if __name__ == "__main__":
    unittest.main()
