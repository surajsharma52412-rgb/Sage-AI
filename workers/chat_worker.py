"""
Chat Worker QThread for Sage AI.
Runs multi-provider waterfall fallback asynchronously, emitting real-time signals
for stage transitions and token streams.
"""
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QThread, Signal

from engine.router import FallbackRouter


class ChatWorker(QThread):
    """Asynchronous worker executing queries and emitting reactive UI updates."""

    stage_changed = Signal(str)
    token_received = Signal(str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        prompt: str,
        session_id: str,
        history: Optional[List[Dict[str, Any]]] = None,
        force_web: bool = False,
        selected_model: Optional[str] = None,
        router: Optional[FallbackRouter] = None,
        parent=None
    ):
        super().__init__(parent)
        self.prompt = prompt
        self.session_id = session_id
        self.history = history or []
        self.force_web = force_web
        self.selected_model = selected_model
        self.router = router or FallbackRouter()
        self._is_cancelled = False

    def cancel(self):
        """Requests cancellation of worker."""
        self._is_cancelled = True

    def run(self):
        try:
            def on_stage(stage: str):
                if not self._is_cancelled:
                    self.stage_changed.emit(stage)

            def on_chunk(chunk: str):
                if not self._is_cancelled:
                    self.token_received.emit(chunk)

            response = self.router.route_and_execute(
                prompt=self.prompt,
                history=self.history,
                force_web=self.force_web,
                selected_model=self.selected_model,
                on_stage_change=on_stage,
                on_chunk=on_chunk
            )

            if self._is_cancelled:
                return

            result_dict = {
                "session_id": self.session_id,
                "text": response.text,
                "model_name": response.model_name,
                "provider_id": response.provider_id,
                "success": response.success,
                "error_msg": response.error_msg,
                "citations": response.citations,
                "latency_ms": response.latency_ms,
                "is_image": response.is_image,
                "image_data": response.image_data,
                "metadata": response.metadata,
            }

            self.finished.emit(result_dict)

        except Exception as e:
            if not self._is_cancelled:
                self.failed.emit(f"Worker Exception: {str(e)}")
