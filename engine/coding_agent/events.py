"""
Structured Live Event Architecture for Sage Coding Agent.
Encapsulates real-time, actionable engineering events emitted by the agent:
- File tracking (read, create, edit, delete)
- Command executions ($ pytest tests/ -> ✓ 24 passed)
- Tool calls
- Model selection & fallback
- State transitions (IDLE, ANALYZING, EDITING, RUNNING, etc.)

NOTE: Never exposes raw private chain-of-thought, API keys, tokens, or .env secrets.
"""
import re
import time
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


class AgentState(str, Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    READING = "READING"
    PLANNING = "PLANNING"
    EDITING = "EDITING"
    CREATING = "CREATING"
    DELETING = "DELETING"
    RUNNING = "RUNNING"
    TESTING = "TESTING"
    VALIDATING = "VALIDATING"
    WAITING = "WAITING"
    FALLBACK = "FALLBACK"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class EventType(str, Enum):
    TASK_STARTED = "task_started"
    TASK_ANALYZING = "task_analyzing"
    FILE_READ = "file_read"
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    COMMAND_STARTED = "command_started"
    COMMAND_FINISHED = "command_finished"
    TEST_STARTED = "test_started"
    TEST_FINISHED = "test_finished"
    MODEL_SELECTED = "model_selected"
    MODEL_FALLBACK = "model_fallback"
    ERROR = "error"
    WARNING = "warning"
    TASK_COMPLETED = "task_completed"


def sanitize_text(text: str) -> str:
    """Masks secrets and sensitive variables from public messages and logs."""
    if not text:
        return text
    sanitized = text
    # Mask key-value patterns
    sanitized = re.sub(
        r"(api[_-]?key|secret|token|password|bearer\s+)[:=]\s*([a-zA-Z0-9_\-\.]{8,})",
        r"\1: [REDACTED]",
        sanitized,
        flags=re.IGNORECASE
    )
    # Mask token patterns
    sanitized = re.sub(r"sk-[a-zA-Z0-9_\-]{15,}", "[REDACTED_KEY]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"ghp_[a-zA-Z0-9]{15,}", "[REDACTED_KEY]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"gsk_[a-zA-Z0-9]{15,}", "[REDACTED_KEY]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"nvapi-[a-zA-Z0-9_\-]{15,}", "[REDACTED_KEY]", sanitized, flags=re.IGNORECASE)
    return sanitized


@dataclass
class CodingAgentEvent:
    """Structured event model for live coding activity feed."""
    event_type: str
    status: str = "running"
    file: Optional[str] = None
    action: Optional[str] = None
    message: str = ""
    command: Optional[str] = None
    diff: Optional[str] = None
    state: str = AgentState.RUNNING.value
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "status": self.status,
            "file": self.file,
            "action": self.action,
            "message": sanitize_text(self.message),
            "command": sanitize_text(self.command) if self.command else None,
            "diff": self.diff,
            "state": self.state,
            "timestamp": self.timestamp,
            "metadata": {k: (sanitize_text(v) if isinstance(v, str) else v) for k, v in self.metadata.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodingAgentEvent":
        return cls(
            event_type=data.get("type", EventType.TASK_ANALYZING.value),
            status=data.get("status", "running"),
            file=data.get("file"),
            action=data.get("action"),
            message=data.get("message", ""),
            command=data.get("command"),
            diff=data.get("diff"),
            state=data.get("state", AgentState.RUNNING.value),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )
