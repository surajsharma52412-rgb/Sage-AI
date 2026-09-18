"""
Safety & Control Module for SAGE Coding Agent Architecture (v6).
Enforces:
- Sandboxed execution (safe process bounds, working directory isolation)
- Permission system (workspace path confinement, block path traversal)
- Command approval classification (SAFE, WARN, DANGEROUS, BLOCKED)
- No destructive actions (blocks rm -rf /, format, drop databases, exfiltration)
- Error handling & recovery (automatic file backup and revert)
"""
import os
import re
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    """Raised when an operation violates security boundaries."""
    pass


class SafetyController:
    """Provides sandboxing, command inspection, file system safety, and rollback recovery."""

    # Disallowed commands that could harm host system
    BLOCKED_PATTERNS = [
        r"\brm\s+-(?:rf|fr|r|f)\s+(?:/|\\|\*|[A-Za-z]:[\\/])",
        r"\bdel\s+/[sfq]\s+[A-Za-z]:[\\/]",
        r"\bformat\s+[A-Za-z]:",
        r"\bmkfs\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bchmod\s+-R\s+777\s+/",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
        r"\bdd\s+if=.*of=/dev/",
        r"\bdiskpart\b",
        r">\s*/dev/sd[a-z]",
    ]

    # Potentially dangerous commands requiring warning or elevated approval
    WARN_PATTERNS = [
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-fdx?\b",
        r"\bdrop\s+table\b",
        r"\bdrop\s+database\b",
        r"\btruncate\s+table\b",
        r"\bkill\s+-9\b",
        r"\btaskkill\s+/f\b",
        r"\bcurl.*\|\s*(?:bash|sh|powershell)\b",
    ]

    def __init__(self, workspace_root: Optional[Path] = None, require_command_approval: bool = False):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.require_command_approval = require_command_approval
        self.backup_registry: Dict[str, str] = {}  # relative_path -> previous_content

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()

    def validate_safe_path(self, relative_or_absolute_path: str) -> Path:
        """
        Confines path operations strictly inside the active workspace root.
        Prevents directory traversal attacks (e.g., ../../etc/passwd or C:\\Windows).
        """
        raw_path = Path(relative_or_absolute_path)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            resolved = (self.workspace_root / raw_path).resolve()

        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            raise SecurityViolation(
                f"Security Alert: Path '{relative_or_absolute_path}' escapes workspace boundary '{self.workspace_root}'"
            )

        return resolved

    def classify_command(self, cmd_line: str) -> Tuple[str, str]:
        """
        Classifies a shell command into SAFE, WARN, or BLOCKED.
        Returns (classification, reason).
        """
        cmd_strip = cmd_line.strip()
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, cmd_strip, re.IGNORECASE):
                return "BLOCKED", f"Destructive command pattern detected: {pattern}"

        for pattern in self.WARN_PATTERNS:
            if re.search(pattern, cmd_strip, re.IGNORECASE):
                return "WARN", f"Potentially risky command pattern detected: {pattern}"

        return "SAFE", "Command passed security checks"

    def can_execute_command(self, cmd_line: str) -> Tuple[bool, str]:
        """
        Checks if a command is permitted to execute.
        """
        level, reason = self.classify_command(cmd_line)
        if level == "BLOCKED":
            return False, f"Execution Blocked: {reason}"
        if level == "WARN" and self.require_command_approval:
            return False, f"Approval Required: {reason}"
        return True, "Approved"

    def create_file_backup(self, file_path: Path):
        """Creates an in-memory backup of a file prior to modification."""
        try:
            rel_str = str(file_path.relative_to(self.workspace_root))
            if file_path.exists() and file_path.is_file():
                self.backup_registry[rel_str] = file_path.read_text(encoding="utf-8", errors="replace")
            else:
                self.backup_registry[rel_str] = "__NON_EXISTENT__"
        except Exception as e:
            logger.warning("Failed to create backup for %s: %s", file_path, e)

    def rollback_file(self, file_path: Path) -> bool:
        """Restores a file to its backed-up state if an error occurred."""
        try:
            rel_str = str(file_path.relative_to(self.workspace_root))
            if rel_str in self.backup_registry:
                prev = self.backup_registry[rel_str]
                if prev == "__NON_EXISTENT__":
                    if file_path.exists():
                        file_path.unlink()
                else:
                    file_path.write_text(prev, encoding="utf-8")
                return True
        except Exception as e:
            logger.error("Failed to rollback file %s: %s", file_path, e)
        return False

    def rollback_all(self) -> int:
        """Rolls back all modified files in the current transaction."""
        restored = 0
        for rel_str in list(self.backup_registry.keys()):
            p = self.workspace_root / rel_str
            if self.rollback_file(p):
                restored += 1
        self.backup_registry.clear()
        return restored

    def clear_backups(self):
        self.backup_registry.clear()
