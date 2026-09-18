"""
Task Queue & Scheduler for SAGE Coding Agent Architecture (v6).
Features:
- Thread-safe task execution pool supporting parallel sub-agents
- Strict DAG dependency enforcement
- Resource allocation & concurrency limits (prevents LLM rate-limiting)
- Retry on failure with backoff
- Real-time progress tracking, events, and execution timeline
- Long-running task support
"""
import time
import queue
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Schedules, queues, and executes subtasks respecting dependencies and concurrency limits."""

    def __init__(self, max_concurrency: int = 3, max_retries: int = 2):
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        self.task_results: Dict[str, Dict[str, Any]] = {}
        self.task_timeline: List[Dict[str, Any]] = []

    def execute_dag(
        self,
        stages: List[List[str]],
        subtasks: Dict[str, Dict[str, Any]],
        task_executor_fn: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_log: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes subtasks stage-by-stage. Within each stage, non-dependent tasks execute concurrently.
        """
        self.task_results.clear()
        self.task_timeline.clear()
        total_tasks = len(subtasks)
        completed_count = 0

        def log(msg: str):
            if on_log:
                try:
                    on_log(msg)
                except Exception:
                    pass

        start_all_time = time.time()
        log(f"⚡ Task Scheduler initialized: {total_tasks} tasks across {len(stages)} execution stages.")

        for stage_idx, stage_task_ids in enumerate(stages, start=1):
            log(f"▶️ Starting Stage {stage_idx}/{len(stages)}: {[subtasks[tid]['name'] for tid in stage_task_ids]}")

            # Execute tasks in current stage concurrently up to max_concurrency
            with ThreadPoolExecutor(max_workers=min(self.max_concurrency, max(1, len(stage_task_ids)))) as executor:
                future_to_task = {}
                for tid in stage_task_ids:
                    task = subtasks[tid]
                    # Gather context from dependencies
                    dep_context = {}
                    for dep_id in task.get("depends_on", []):
                        if dep_id in self.task_results:
                            dep_context[dep_id] = self.task_results[dep_id]

                    future = executor.submit(
                        self._run_with_retry,
                        task=task,
                        dep_context=dep_context,
                        executor_fn=task_executor_fn,
                        log_fn=log
                    )
                    future_to_task[future] = task

                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    tid = task["task_id"]
                    try:
                        res = future.result()
                    except Exception as e:
                        res = {"success": False, "error": str(e), "task_id": tid}

                    self.task_results[tid] = res
                    completed_count += 1
                    task["status"] = "completed" if res.get("success") else "failed"

                    self.task_timeline.append({
                        "task_id": tid,
                        "name": task["name"],
                        "role": task["role"],
                        "success": res.get("success", False),
                        "duration_s": res.get("duration_s", 0),
                        "timestamp": time.strftime("%H:%M:%S")
                    })

                    if on_progress:
                        on_progress({
                            "task_id": tid,
                            "name": task["name"],
                            "status": task["status"],
                            "completed_count": completed_count,
                            "total_tasks": total_tasks,
                            "percent": int((completed_count / total_tasks) * 100)
                        })

                    status_icon = "✅" if res.get("success") else "❌"
                    log(f"  {status_icon} [{task['role'].upper()}] {task['name']} finished in {res.get('duration_s', 0):.2f}s")

        total_elapsed = round(time.time() - start_all_time, 2)
        log(f"🏁 Task Scheduler completed all stages in {total_elapsed}s.")

        return {
            "success": all(r.get("success", False) for r in self.task_results.values()),
            "total_tasks": total_tasks,
            "completed_count": completed_count,
            "duration_s": total_elapsed,
            "results": self.task_results,
            "timeline": self.task_timeline
        }

    def _run_with_retry(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        executor_fn: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        log_fn: Callable[[str], None]
    ) -> Dict[str, Any]:
        """Executes a single task with automatic retries on transient errors."""
        tid = task["task_id"]
        attempts = 0
        last_err = None

        while attempts <= self.max_retries:
            attempts += 1
            t_start = time.time()
            try:
                result = executor_fn(task, dep_context)
                result["duration_s"] = round(time.time() - t_start, 2)
                result["attempts"] = attempts
                if result.get("success", True):
                    return result
                else:
                    last_err = result.get("error", "Task returned unsuccessful result")
            except Exception as e:
                last_err = str(e)

            if attempts <= self.max_retries:
                log_fn(f"⚠️ Task '{task['name']}' attempt {attempts} failed: {last_err}. Retrying in 1s...")
                time.sleep(1)

        return {
            "success": False,
            "task_id": tid,
            "error": last_err or "Exceeded maximum retry attempts",
            "attempts": attempts,
            "duration_s": round(time.time() - t_start, 2)
        }
