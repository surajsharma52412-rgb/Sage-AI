"""
Safety Approval Gates & Safe Execution Engine for SAGE Coding Agent.
Implements Sections 16 and 36 of the Ultimate Master Architecture:
- Classifies operations into SAFE_AUTONOMOUS vs REQUIRES_USER_APPROVAL
- Prevents destructive data loss, unauthorized production deployments, or irreversible overwrites
- Autonomous when safe, controlled when risky
"""
import re
import logging
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class ActionRiskTier(str, Enum):
    SAFE_AUTONOMOUS = "SAFE_AUTONOMOUS"              # Read, write local files, run tests, build
    MODERATE_RISK = "MODERATE_RISK"                  # Installing packages, modifying configuration
    REQUIRES_USER_APPROVAL = "REQUIRES_USER_APPROVAL"  # Destructive deletes, git reset --hard, drop db, production deploy


@dataclass
class GateEvaluationResult:
    is_safe_to_proceed: bool
    risk_tier: ActionRiskTier
    reason: str
    approval_prompt: Optional[str] = None


class SafetyApprovalGates:
    """
    Evaluates actions before execution.
    Allows routine autonomous execution to run freely while intercepting dangerous operations.
    """

    DESTRUCTIVE_COMMAND_REGEXES = [
        (r"\brm\s+-(?:rf|fr|r|f)\s+", "Recursive directory deletion"),
        (r"\bdel\s+/[sfq]\s+", "Recursive file deletion on Windows"),
        (r"\bgit\s+reset\s+--hard\b", "Hard reset discarding uncommitted git history"),
        (r"\bgit\s+clean\s+-fdx?\b", "Untracked file wipe"),
        (r"\bdrop\s+(?:table|database)\b", "Destructive SQL drop statement"),
        (r"\btruncate\s+table\b", "Destructive SQL table truncation"),
        (r"\bformat\s+[A-Za-z]:", "Filesystem volume formatting"),
        (r"\bmkfs\b", "Filesystem rebuild"),
        (r"\bdeploy\s+--prod(?:uction)?\b", "Live production deployment")
    ]

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.approval_handler: Optional[Callable[[str], bool]] = None

    def set_approval_handler(self, handler: Callable[[str], bool]):
        """Sets a callback function for requesting explicit user confirmation."""
        self.approval_handler = handler

    def evaluate_command(self, command: str) -> GateEvaluationResult:
        """Evaluates whether a command can run autonomously or requires an approval gate."""
        cmd_lower = command.lower().strip()

        for pattern, desc in self.DESTRUCTIVE_COMMAND_REGEXES:
            if re.search(pattern, cmd_lower):
                prompt = f"Dangerous operation detected: '{command}'. Reason: {desc}. Do you grant permission to execute?"
                return GateEvaluationResult(
                    is_safe_to_proceed=False,
                    risk_tier=ActionRiskTier.REQUIRES_USER_APPROVAL,
                    reason=desc,
                    approval_prompt=prompt
                )

        # Check moderate risks
        if any(cmd_lower.startswith(p) for p in ("npm install", "pip install", "yarn add", "poetry add")):
            return GateEvaluationResult(
                is_safe_to_proceed=True,
                risk_tier=ActionRiskTier.MODERATE_RISK,
                reason="Package installation will modify dependency tree"
            )

        return GateEvaluationResult(
            is_safe_to_proceed=True,
            risk_tier=ActionRiskTier.SAFE_AUTONOMOUS,
            reason="Standard non-destructive command execution"
        )

    def evaluate_file_write(
        self,
        target_path: Path,
        existing_content: Optional[str] = None,
        new_content: str = ""
    ) -> GateEvaluationResult:
        """Evaluates whether writing to a file is safe or represents a massive destructive overwrite."""
        # If target file exists and is large, but new content is almost empty
        if existing_content and len(existing_content) > 500 and len(new_content) < 30:
            prompt = f"File '{target_path.name}' contains {len(existing_content)} characters. Replacing it with only {len(new_content)} characters may truncate data. Confirm overwrite?"
            return GateEvaluationResult(
                is_safe_to_proceed=False,
                risk_tier=ActionRiskTier.REQUIRES_USER_APPROVAL,
                reason="Substantial file truncation detected",
                approval_prompt=prompt
            )

        return GateEvaluationResult(
            is_safe_to_proceed=True,
            risk_tier=ActionRiskTier.SAFE_AUTONOMOUS,
            reason="Safe autonomous file update"
        )

    def request_approval_if_needed(self, eval_res: GateEvaluationResult) -> bool:
        """Executes approval callback if registered, or defaults to safe rejection."""
        if eval_res.is_safe_to_proceed:
            return True
        if self.approval_handler and eval_res.approval_prompt:
            return self.approval_handler(eval_res.approval_prompt)
        # Without approval handler, dangerous operations are blocked by default for safety
        logger.warning("Dangerous action blocked because no approval handler granted permission: %s", eval_res.reason)
        return False
