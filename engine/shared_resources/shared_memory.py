"""
Shared Memory for Sage Multi-Agentic AI Architecture.
Manages Short-Term (in-memory session scratchpad) and Long-Term (persistent SQLite)
memory shared across all specialized agents.
"""
import threading
import logging
from typing import Any, Dict, Optional, List

from database.db_manager import get_db

logger = logging.getLogger(__name__)


class SharedMemory:
    """Thread-safe multi-tier memory accessible by all specialized agents."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SharedMemory, cls).__new__(cls)
                cls._instance._init_memory()
            return cls._instance

    def _init_memory(self):
        self._short_term: Dict[str, Any] = {}
        self._memory_lock = threading.Lock()
        self._db = get_db()

    def set(
        self,
        key: str,
        value: Any,
        is_long_term: bool = False,
        memory_type: str = "general",
        agent_source: Optional[str] = None
    ):
        """Stores a memory entry in either short-term scratchpad or persistent long-term storage."""
        with self._memory_lock:
            self._short_term[key] = {
                "value": value,
                "type": memory_type,
                "agent_source": agent_source
            }

        if is_long_term:
            try:
                self._db.set_shared_memory(
                    key=key,
                    value=value,
                    memory_type=memory_type,
                    agent_source=agent_source
                )
            except Exception as e:
                logger.warning("Failed to persist long-term memory for %s: %s", key, e)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves value from short-term cache, falling back to persistent storage."""
        with self._memory_lock:
            if key in self._short_term:
                return self._short_term[key]["value"]

        # Check persistent storage
        try:
            persisted = self._db.get_shared_memory(key)
            if persisted is not None:
                with self._memory_lock:
                    self._short_term[key] = {
                        "value": persisted,
                        "type": "long_term",
                        "agent_source": "persisted"
                    }
                return persisted
        except Exception as e:
            logger.debug("Error checking persisted memory: %s", e)

        return default

    def get_all(self, memory_type: Optional[str] = None) -> Dict[str, Any]:
        """Returns snapshot of current memory items."""
        result = {}
        # Get persistent items
        try:
            persistent = self._db.get_all_shared_memory(memory_type=memory_type)
            result.update(persistent)
        except Exception as e:
            logger.debug("Error fetching persistent memory: %s", e)

        # Overlay short-term items
        with self._memory_lock:
            for k, v in self._short_term.items():
                if memory_type is None or v.get("type") == memory_type:
                    result[k] = v.get("value")

        return result

    def clear_short_term(self):
        """Clears working scratchpad memory (e.g. between complex multi-agent tasks)."""
        with self._memory_lock:
            self._short_term.clear()

    def delete(self, key: str) -> bool:
        """Removes a key from both short-term and persistent stores."""
        with self._memory_lock:
            self._short_term.pop(key, None)
        try:
            return self._db.delete_shared_memory(key)
        except Exception:
            return True


_shared_memory_instance: Optional[SharedMemory] = None

def get_shared_memory() -> SharedMemory:
    global _shared_memory_instance
    if _shared_memory_instance is None:
        _shared_memory_instance = SharedMemory()
    return _shared_memory_instance
