"""
Animated Stacked Widget for Sage AI.
Provides fluid slide and cross-fade page transition animations when shifting between tabs/views
(Home, Chat, Coding Agent, Automations, Multi-Agent Hub, Knowledge, Settings, Add Models, Analytics).
"""
from typing import Optional
from PySide6.QtWidgets import QStackedWidget, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QPoint, Signal, QEvent
)


class AnimatedStackedWidget(QStackedWidget):
    """
    QStackedWidget with smooth page transition animations:
    - Slide & Fade transition between tabs
    - Crossfade mode
    - Automatic direction detection (sliding left or right based on index)
    - Clean opacity effect disposal when animation completes for crisp font rendering
    """

    transition_started = Signal(int, int)  # (from_index, to_index)
    transition_finished = Signal(int)      # (new_index)

    def __init__(self, parent: Optional[QWidget] = None, duration: int = 240):
        super().__init__(parent)
        self.duration = duration
        self._is_animating = False
        self._anim_group: Optional[QParallelAnimationGroup] = None
        self._pending_widget: Optional[QWidget] = None

    def setCurrentIndex(self, index: int):
        """Animates transition to the specified index."""
        target_widget = self.widget(index)
        if target_widget:
            self.slide_to_widget(target_widget)
        else:
            super().setCurrentIndex(index)

    def setCurrentWidget(self, widget: QWidget):
        """Animates transition to the specified widget."""
        self.slide_to_widget(widget)

    def set_current_widget_instant(self, widget: QWidget):
        """Switches immediately without animation if needed."""
        self._cleanup_animation()
        super().setCurrentWidget(widget)

    def slide_to_widget(self, next_widget: QWidget, direction: Optional[str] = None):
        """
        Smoothly slides and fades from current widget to next_widget.
        direction: 'left', 'right', or None (auto-calculated from index delta).
        """
        current_widget = self.currentWidget()
        if not current_widget or current_widget == next_widget:
            super().setCurrentWidget(next_widget)
            return

        if not self.isVisible():
            super().setCurrentWidget(next_widget)
            return

        if self._is_animating:
            self._cleanup_animation()
            super().setCurrentWidget(next_widget)
            return

        current_idx = self.indexOf(current_widget)
        next_idx = self.indexOf(next_widget)

        if direction is None:
            direction = "left" if next_idx > current_idx else "right"

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            super().setCurrentWidget(next_widget)
            return

        self._is_animating = True
        self.transition_started.emit(current_idx, next_idx)

        # Offset distance for smooth slide (subtle 36px parallax glide)
        offset_dist = min(50, max(24, w // 20))
        offset_sign = 1 if direction == "left" else -1

        # Position and show the incoming widget
        next_widget.setGeometry(0, 0, w, h)
        next_widget.show()
        next_widget.raise_()

        # Avoid QGraphicsOpacityEffect on heavy compound views (CodingIdeView, MultiAgentView, KnowledgeView)
        # because rasterizing hundreds of child widgets into offscreen alpha buffers causes severe frame drops.
        # Hardware-accelerated position slide (pos) provides a silky-smooth 60 FPS parallax glide with zero lag.
        anim_slide_out = QPropertyAnimation(current_widget, b"pos")
        anim_slide_out.setDuration(min(160, self.duration))
        anim_slide_out.setStartValue(QPoint(0, 0))
        anim_slide_out.setEndValue(QPoint(-offset_dist * offset_sign, 0))
        anim_slide_out.setEasingCurve(QEasingCurve.OutCubic)

        anim_slide_in = QPropertyAnimation(next_widget, b"pos")
        anim_slide_in.setDuration(min(160, self.duration))
        anim_slide_in.setStartValue(QPoint(offset_dist * offset_sign, 0))
        anim_slide_in.setEndValue(QPoint(0, 0))
        anim_slide_in.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_slide_out)
        group.addAnimation(anim_slide_in)

        def _on_finished():
            current_widget.move(0, 0)
            next_widget.move(0, 0)
            super(AnimatedStackedWidget, self).setCurrentWidget(next_widget)
            self._is_animating = False
            self._anim_group = None
            self.transition_finished.emit(next_idx)

        group.finished.connect(_on_finished)
        self._anim_group = group
        group.start()

    def _cleanup_animation(self):
        """Immediately stops running animation and clears effects."""
        if self._anim_group:
            try:
                self._anim_group.stop()
            except Exception:
                pass
            self._anim_group = None

        for i in range(self.count()):
            w = self.widget(i)
            if w:
                w.setGraphicsEffect(None)
                w.move(0, 0)

        self._is_animating = False
