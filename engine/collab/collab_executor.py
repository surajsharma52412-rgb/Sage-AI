"""
Collaborative Execution Service for SAGE Collaborative IDE.

Manages shared code execution across all connected peers:
    - FIFO execution queue (one active run at a time per workspace)
    - Live stdout/stderr streaming to all peers
    - Run tagging (who triggered, when, status)
    - Kill support (SIGTERM → SIGKILL after timeout)
    - Uses existing SandboxRunner/SecureSandbox for isolation
"""

import os
import sys
import time
import uuid
import queue
import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RunRequest:
    """Represents a queued or active execution request."""
    run_id: str
    file_path: str
    triggered_by: str
    triggered_by_id: str = ""
    status: str = "queued"      # queued → running → completed/failed/killed/timed_out
    started_at: float = 0.0
    completed_at: float = 0.0
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""


class CollabExecutor:
    """
    Manages shared code execution for a collaborative workspace.
    
    One executor instance per workspace. Runs are queued and executed
    sequentially to prevent output interleaving.
    """

    def __init__(
        self,
        workspace_root: Path,
        default_timeout: float = 60.0,
        on_output: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
    ):
        self.workspace_root = workspace_root.resolve()
        self.default_timeout = default_timeout
        
        # Callbacks for broadcasting
        self.on_output = on_output    # (run_id, output_text, stream) → broadcasts to all peers
        self.on_status = on_status    # (run_request) → broadcasts status change
        
        # Execution queue
        self._queue: queue.Queue = queue.Queue()
        self._current_run: Optional[RunRequest] = None
        self._current_process: Optional[subprocess.Popen] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # History
        self._history: List[RunRequest] = []
        self._max_history = 50

    def start(self):
        """Starts the execution worker thread."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop(self):
        """Stops the executor and kills any running process."""
        self._running = False
        self.kill_current()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def submit_run(
        self,
        file_path: str,
        triggered_by: str,
        triggered_by_id: str = "",
        run_id: Optional[str] = None,
    ) -> RunRequest:
        """
        Submits a run request to the execution queue.
        
        Returns the RunRequest with its assigned run_id.
        """
        request = RunRequest(
            run_id=run_id or str(uuid.uuid4())[:8],
            file_path=file_path,
            triggered_by=triggered_by,
            triggered_by_id=triggered_by_id,
            status="queued",
        )
        
        self._queue.put(request)
        
        if self.on_status:
            self.on_status(request)
        
        return request

    def kill_current(self, killed_by: str = "System") -> bool:
        """Kills the currently running process."""
        with self._lock:
            proc = self._current_process
            run = self._current_run
        
        if proc and run:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                
                run.status = "killed"
                run.completed_at = time.time()
                
                if self.on_output:
                    self.on_output(run.run_id, f"\n⚠️ Execution killed by {killed_by}", "stderr")
                if self.on_status:
                    self.on_status(run)
                
                return True
            except Exception as e:
                logger.error(f"Failed to kill process: {e}")
        
        return False

    def get_queue_position(self) -> int:
        """Returns the number of pending runs in the queue."""
        return self._queue.qsize()

    def get_current_run(self) -> Optional[RunRequest]:
        """Returns the currently executing run, if any."""
        return self._current_run

    def get_history(self) -> List[RunRequest]:
        """Returns recent run history."""
        return list(self._history)

    def _worker_loop(self):
        """Background thread that processes the execution queue."""
        while self._running:
            try:
                request = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            self._execute_run(request)

    def _execute_run(self, request: RunRequest):
        """Executes a single run request."""
        with self._lock:
            self._current_run = request
        
        request.status = "running"
        request.started_at = time.time()
        
        if self.on_status:
            self.on_status(request)
        
        if self.on_output:
            self.on_output(
                request.run_id,
                f"▶ Run by {request.triggered_by} at "
                f"{time.strftime('%H:%M:%S', time.localtime(request.started_at))} "
                f"— {request.file_path}\n",
                "stdout"
            )
        
        file_path = self.workspace_root / request.file_path
        
        if not file_path.exists():
            request.status = "failed"
            request.stderr = f"File not found: {request.file_path}"
            request.completed_at = time.time()
            request.exit_code = 127
            
            if self.on_output:
                self.on_output(request.run_id, request.stderr, "stderr")
            if self.on_status:
                self.on_status(request)
            
            self._finish_run(request)
            return
        
        # Determine command based on file extension
        ext = file_path.suffix.lower()
        if ext == ".py":
            cmd = [sys.executable, str(file_path)]
        elif ext == ".js":
            cmd = ["node", str(file_path)]
        elif ext == ".sh":
            cmd = ["bash", str(file_path)]
        elif ext == ".bat":
            cmd = ["cmd", "/c", str(file_path)]
        else:
            cmd = [sys.executable, str(file_path)]  # Default to Python
        
        # Execute with live output streaming
        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
            
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.workspace_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                creationflags=creationflags,
            )
            
            with self._lock:
                self._current_process = proc
            
            # Stream stdout and stderr in separate threads
            stdout_lines = []
            stderr_lines = []
            
            def stream_output(pipe, stream_name, line_buffer):
                for line in pipe:
                    line_buffer.append(line)
                    if self.on_output:
                        self.on_output(request.run_id, line, stream_name)
            
            stdout_thread = threading.Thread(
                target=stream_output,
                args=(proc.stdout, "stdout", stdout_lines),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=stream_output,
                args=(proc.stderr, "stderr", stderr_lines),
                daemon=True
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process with timeout
            try:
                exit_code = proc.wait(timeout=self.default_timeout)
                request.exit_code = exit_code
                request.status = "completed" if exit_code == 0 else "failed"
            except subprocess.TimeoutExpired:
                proc.kill()
                request.status = "timed_out"
                request.exit_code = -1
                if self.on_output:
                    self.on_output(
                        request.run_id,
                        f"\n⏱️ Execution timed out after {self.default_timeout}s\n",
                        "stderr"
                    )
            
            # Wait for output threads
            stdout_thread.join(timeout=2.0)
            stderr_thread.join(timeout=2.0)
            
            request.stdout = "".join(stdout_lines)
            request.stderr = "".join(stderr_lines)
            
        except FileNotFoundError:
            request.status = "failed"
            request.exit_code = 127
            request.stderr = f"Command not found: {cmd[0]}"
            if self.on_output:
                self.on_output(request.run_id, request.stderr, "stderr")
        except Exception as e:
            request.status = "failed"
            request.exit_code = -1
            request.stderr = str(e)
            if self.on_output:
                self.on_output(request.run_id, f"Execution error: {e}\n", "stderr")
        
        request.completed_at = time.time()
        
        if self.on_output:
            duration = request.completed_at - request.started_at
            status_icon = "✅" if request.status == "completed" else "❌"
            self.on_output(
                request.run_id,
                f"\n{status_icon} Finished in {duration:.2f}s (exit code: {request.exit_code})\n",
                "stdout"
            )
        
        if self.on_status:
            self.on_status(request)
        
        self._finish_run(request)

    def _finish_run(self, request: RunRequest):
        """Cleans up after a run completes."""
        with self._lock:
            self._current_process = None
            self._current_run = None
        
        self._history.append(request)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
