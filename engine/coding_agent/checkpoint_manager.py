"""
Checkpoint Manager & User Changes Guardian for SAGE Autonomous Coding Agent.
Implements Sections 15 & 16 of Master Specification:
- Pre-task Git commit / file snapshots
- Rollback support on catastrophic failure
- Existing Uncommitted User Changes Guardian:
  - Scans workspace prior to execution
  - Identifies uncommitted files touched by user
  - Protects user files from unintended overwrite or deletion
  - Confines agent modifications strictly to files requested for the active task
"""
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from .tool_system import ToolSystem

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages transactional snapshots, rollback points, and preserves uncommitted user work."""

    def __init__(self, tools: ToolSystem):
        self.tools = tools
        self.checkpoints: List[Dict[str, Any]] = []
        self.initial_uncommitted_user_files: Set[str] = set()

    def record_pre_task_state(self) -> Dict[str, Any]:
        """
        Scans Git status to identify existing uncommitted user changes.
        Locks these files so the agent will never reset or delete them.
        """
        status_res = self.tools.git_status()
        self.initial_uncommitted_user_files.clear()

        if status_res["success"] and status_res["stdout"]:
            for line in status_res["stdout"].splitlines():
                line = line.strip()
                if line and not line.startswith("##"):
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        self.initial_uncommitted_user_files.add(parts[1].replace("\\", "/"))

        return {
            "uncommitted_user_files": list(self.initial_uncommitted_user_files),
            "count": len(self.initial_uncommitted_user_files)
        }

    def is_user_file_protected(self, file_path: str) -> bool:
        """Checks if a file has pre-existing uncommitted user changes."""
        clean = file_path.replace("\\", "/").lstrip("./")
        return clean in self.initial_uncommitted_user_files

    def create_checkpoint(self, task_id: str, description: str, files_to_modify: List[str]) -> Dict[str, Any]:
        """
        Creates a snapshot prior to executing a task.
        Captures pre-modification file contents so rollback can be performed safely.
        """
        snapshot = {}
        for f in files_to_modify:
            full = self.tools.workspace_root / f
            if full.exists() and full.is_file():
                try:
                    snapshot[f] = full.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            else:
                snapshot[f] = "__DOES_NOT_EXIST__"

        checkpoint_data = {
            "checkpoint_id": f"chk_{int(time.time())}_{task_id}",
            "task_id": task_id,
            "description": description,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "snapshot": snapshot,
            "files_tracked": list(snapshot.keys())
        }
        self.checkpoints.append(checkpoint_data)
        return checkpoint_data

    def rollback_to_checkpoint(self, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Restores files to snapshot state without touching unrelated user files.
        """
        if not self.checkpoints:
            return {"success": False, "error": "No checkpoints available to rollback."}

        target_chk = self.checkpoints[-1]
        if checkpoint_id:
            for chk in self.checkpoints:
                if chk["checkpoint_id"] == checkpoint_id:
                    target_chk = chk
                    break

        restored_files = []
        for rel_path, old_content in target_chk["snapshot"].items():
            full = self.tools.workspace_root / rel_path
            try:
                if old_content == "__DOES_NOT_EXIST__":
                    if full.exists():
                        full.unlink()
                        restored_files.append(f"Deleted {rel_path} (reverted to non-existent)")
                else:
                    full.parent.mkdir(parents=True, exist_ok=True)
                    full.write_text(old_content, encoding="utf-8")
                    restored_files.append(f"Restored {rel_path}")
            except Exception as e:
                logger.error("Error rolling back %s: %s", rel_path, e)

        return {
            "success": True,
            "checkpoint_id": target_chk["checkpoint_id"],
            "restored_files": restored_files
        }
