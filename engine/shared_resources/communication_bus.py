"""
Communication Bus for Sage Multi-Agentic AI Architecture.
Provides inter-agent messaging, event broadcasting, and coordination channels.
All messages are recorded to audit history and dispatched to active listeners.
"""
import threading
import logging
from typing import Callable, Dict, List, Any, Optional

from database.db_manager import get_db

logger = logging.getLogger(__name__)


class CommunicationBus:
    """Pub/Sub and point-to-point messaging bus for specialized AI agents."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CommunicationBus, cls).__new__(cls)
                cls._instance._init_bus()
            return cls._instance

    def _init_bus(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._wildcard_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._bus_lock = threading.Lock()
        self._db = get_db()

    def subscribe(self, channel_or_agent: str, callback: Callable[[Dict[str, Any]], None]):
        """Subscribes to messages directed to an agent or a broadcast channel."""
        with self._bus_lock:
            if channel_or_agent == "*":
                self._wildcard_listeners.append(callback)
            else:
                if channel_or_agent not in self._listeners:
                    self._listeners[channel_or_agent] = []
                self._listeners[channel_or_agent].append(callback)

    def unsubscribe(self, channel_or_agent: str, callback: Callable[[Dict[str, Any]], None]):
        with self._bus_lock:
            if channel_or_agent == "*":
                if callback in self._wildcard_listeners:
                    self._wildcard_listeners.remove(callback)
            elif channel_or_agent in self._listeners:
                if callback in self._listeners[channel_or_agent]:
                    self._listeners[channel_or_agent].remove(callback)

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatches a direct message from one agent to another and records it."""
        msg = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message_type": message_type,
            "content": content,
            "task_id": task_id,
        }

        # 1. Record in database for audit & visualization
        try:
            msg_id = self._db.record_inter_agent_message(
                from_agent=from_agent,
                to_agent=to_agent,
                message_type=message_type,
                content=content,
                task_id=task_id
            )
            msg["id"] = msg_id
        except Exception as e:
            logger.debug("Failed to record inter-agent message: %s", e)

        # 2. Dispatch to subscribers
        with self._bus_lock:
            callbacks = list(self._listeners.get(to_agent, []))
            wildcards = list(self._wildcard_listeners)

        for cb in callbacks + wildcards:
            try:
                cb(msg)
            except Exception as e:
                logger.warning("Error in CommunicationBus listener: %s", e)

        return msg

    def broadcast(
        self,
        from_agent: str,
        event_type: str,
        content: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Broadcasts an event or status update to all agents and orchestrators."""
        return self.send_message(
            from_agent=from_agent,
            to_agent="all",
            message_type=event_type,
            content=content,
            task_id=task_id
        )

    def get_history(self, task_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves stored communication bus history."""
        try:
            return self._db.get_inter_agent_messages(task_id=task_id, limit=limit)
        except Exception:
            return []


_comm_bus_instance: Optional[CommunicationBus] = None

def get_comm_bus() -> CommunicationBus:
    global _comm_bus_instance
    if _comm_bus_instance is None:
        _comm_bus_instance = CommunicationBus()
    return _comm_bus_instance
