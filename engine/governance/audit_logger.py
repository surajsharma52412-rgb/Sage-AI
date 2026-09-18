"""
Audit Logger for Sage Multi-Agentic AI Architecture.
Records granular audit events for all agent steps, tool executions, and security checks.
"""
import logging
from typing import Dict, Any, Optional, List

from database.db_manager import get_db

logger = logging.getLogger(__name__)


class AuditLogger:
    """Central audit and activity logging for multi-agent workflows."""

    def __init__(self):
        self._db = get_db()

    def log_action(
        self,
        agent_name: str,
        action: str,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """Logs an action to the database audit table."""
        logger.info("[AUDIT] [%s] %s (Task: %s)", agent_name, action, task_id or "N/A")
        try:
            return self._db.log_agent_action(
                agent_name=agent_name,
                action=action,
                task_id=task_id,
                details=details
            )
        except Exception as e:
            logger.warning("Failed to record audit log: %s", e)
            return -1

    def get_logs(
        self,
        task_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieves audit entries."""
        try:
            return self._db.get_agent_logs(task_id=task_id, agent_name=agent_name, limit=limit)
        except Exception:
            return []


_audit_logger_instance: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance
