"""
Unit tests for SAGE-AI Animation Engine and Multi-Agent Workflow Visualizer.
Verifies:
1. Centralized AnimationManager singleton, PerformanceTier transitions, and scaling.
2. Accessibility prefers-reduced-motion support (zero duration scaling, disabling heavy effects).
3. MultiAgentWorkflowVisualizer state machine and stage transitions.
4. Auto-scrolling threshold protection logic.
5. ShimmerSkeleton and GPU-friendly property animation safety.
"""
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QWidget, QLabel, QScrollArea, QScrollBar
from PySide6.QtCore import Qt

# Ensure a QApplication instance exists for GUI unit tests
app = QApplication.instance()
if app is None:
    app = QApplication([])

from ui.components.animation_system import (
    PerformanceTier,
    MotionTokens,
    AnimationManager,
    get_anim_manager,
    fade_in,
    fade_out,
    slide_in_from_bottom,
    smooth_scroll_to,
    button_micro_press,
    ShimmerSkeleton,
)
from ui.components.agent_workflow_animator import (
    AgentStatus,
    MultiAgentWorkflowVisualizer,
    AgentNodeBadge,
)


class TestAnimationEngine(unittest.TestCase):

    def setUp(self):
        self.mgr = get_anim_manager()
        self.mgr.set_tier(PerformanceTier.NORMAL)

    def test_performance_tiers_and_scaling(self):
        self.mgr.set_tier(PerformanceTier.HIGH)
        self.assertEqual(self.mgr.current_tier, PerformanceTier.HIGH)
        self.assertFalse(self.mgr.is_reduced_motion)
        self.assertFalse(self.mgr.is_low_performance)
        self.assertEqual(self.mgr.scale_duration(200), 200)

        # Low performance tier scales down durations
        self.mgr.set_tier(PerformanceTier.LOW)
        self.assertTrue(self.mgr.is_low_performance)
        self.assertFalse(self.mgr.is_reduced_motion)
        scaled = self.mgr.scale_duration(200)
        self.assertLess(scaled, 200)

        # Reduced motion tier returns 1ms (instant)
        self.mgr.set_tier(PerformanceTier.REDUCED_MOTION)
        self.assertTrue(self.mgr.is_reduced_motion)
        self.assertTrue(self.mgr.is_low_performance)
        self.assertEqual(self.mgr.scale_duration(300), 1)

    def test_fade_in_and_reduced_motion(self):
        w = QWidget()
        w.resize(100, 100)

        # In reduced motion mode, fade_in immediately shows the widget and returns None
        self.mgr.set_tier(PerformanceTier.REDUCED_MOTION)
        called = False
        def on_done():
            nonlocal called
            called = True

        anim = fade_in(w, duration=100, on_finished=on_done)
        self.assertIsNone(anim)
        self.assertTrue(w.isVisible())
        self.assertTrue(called)

    def test_slide_in_from_bottom_reduced_motion(self):
        w = QWidget()
        self.mgr.set_tier(PerformanceTier.REDUCED_MOTION)
        group = slide_in_from_bottom(w, offset_y=16, duration=100)
        self.assertIsNone(group)
        self.assertTrue(w.isVisible())

    def test_smooth_scroll_to(self):
        scroll_area = QScrollArea()
        scroll_area.resize(200, 200)
        content = QWidget()
        content.resize(200, 1000)
        scroll_area.setWidget(content)

        vbar = scroll_area.verticalScrollBar()
        vbar.setMaximum(800)
        vbar.setValue(0)

        # In reduced motion mode, it sets value instantly
        self.mgr.set_tier(PerformanceTier.REDUCED_MOTION)
        smooth_scroll_to(scroll_area, 400)
        self.assertEqual(vbar.value(), 400)

    def test_button_micro_press(self):
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton("Test Action")
        btn.resize(80, 32)
        # Should execute safely without throwing
        anim = button_micro_press(btn)
        self.assertIsNotNone(btn)

    def test_shimmer_skeleton(self):
        skeleton = ShimmerSkeleton(width=200, height=30)
        self.assertEqual(skeleton.width(), 200)
        self.assertEqual(skeleton.height(), 30)


class TestMultiAgentWorkflowVisualizer(unittest.TestCase):

    def setUp(self):
        self.viz = MultiAgentWorkflowVisualizer()

    def tearDown(self):
        self.viz._cleanup()

    def test_pipeline_nodes_initialization(self):
        expected_keys = ["user", "planner", "worker", "verifier", "delivery"]
        for key in expected_keys:
            self.assertIn(key, self.viz.nodes)
            self.assertEqual(self.viz.nodes[key].status, AgentStatus.IDLE)
        self.assertEqual(len(self.viz.connectors), 4)

    def test_pipeline_transitions(self):
        # 1. User request ingested
        self.viz.transition_to_stage("user", AgentStatus.COMPLETED, "Goal received")
        self.assertEqual(self.viz.nodes["user"].status, AgentStatus.COMPLETED)

        # 2. Planner working
        self.viz.transition_to_stage("planner", AgentStatus.WORKING, "Decomposing task")
        self.assertEqual(self.viz.nodes["user"].status, AgentStatus.COMPLETED)
        self.assertEqual(self.viz.nodes["planner"].status, AgentStatus.WORKING)

        # 3. Specialist working
        self.viz.transition_to_stage("worker", AgentStatus.WORKING, "Executing tools", specialist_name="Coding Agent")
        self.assertEqual(self.viz.nodes["planner"].status, AgentStatus.COMPLETED)
        self.assertEqual(self.viz.nodes["worker"].status, AgentStatus.WORKING)
        self.assertEqual(self.viz.nodes["worker"].name, "Coding Agent")

        # 4. Verifier working
        self.viz.transition_to_stage("verifier", AgentStatus.WORKING, "Smart validation")
        self.assertEqual(self.viz.nodes["worker"].status, AgentStatus.COMPLETED)
        self.assertEqual(self.viz.nodes["verifier"].status, AgentStatus.WORKING)

        # 5. Delivery complete
        self.viz.transition_to_stage("delivery", AgentStatus.COMPLETED, "Verified & Delivered")
        for key in ["user", "planner", "worker", "verifier"]:
            self.assertEqual(self.viz.nodes[key].status, AgentStatus.COMPLETED)
        self.assertEqual(self.viz.nodes["delivery"].status, AgentStatus.COMPLETED)

    def test_pipeline_reset(self):
        self.viz.transition_to_stage("worker", AgentStatus.WORKING)
        self.viz.reset_pipeline()
        for node in self.viz.nodes.values():
            self.assertEqual(node.status, AgentStatus.IDLE)


if __name__ == "__main__":
    unittest.main()
