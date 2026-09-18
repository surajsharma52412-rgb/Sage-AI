"""
CRDT WebSocket Sync Client for SAGE Collaborative IDE.

Connects to a CRDTSyncServer and maintains local CRDTDocument mirrors
for each open file. Handles:
    - WebSocket connection with auto-reconnect (exponential backoff)
    - Local CRDT op generation and transmission
    - Remote op application
    - Offline queue (ops generated while disconnected are replayed on reconnect)
    - Cursor position broadcasting
    - Presence updates
    - Save/run requests

Emits Qt signals for UI consumption, following the same pattern as
the existing CollabManager.
"""

import json
import time
import asyncio
import logging
import uuid
import threading
import random
from typing import Dict, Optional, List, Any, Callable
from collections import deque

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QObject, Signal
    HAS_QT = True
except ImportError:
    HAS_QT = False
    # Fallback for testing without Qt
    class QObject:
        def __init__(self, parent=None):
            pass
    class Signal:
        def __init__(self, *args):
            pass
        def emit(self, *args):
            pass
        def connect(self, *args):
            pass

try:
    import websockets
    from websockets.asyncio.client import connect as ws_connect
    HAS_WEBSOCKETS = True
except ImportError:
    try:
        import websockets
        from websockets.client import connect as ws_connect
        HAS_WEBSOCKETS = True
    except ImportError:
        HAS_WEBSOCKETS = False
        ws_connect = None

from engine.collab.crdt_document import CRDTDocument, CRDTOp, OpType


class ConnectionState:
    """Connection state constants."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    OFFLINE = "offline"


class CRDTSyncClient(QObject):
    """
    WebSocket client that maintains local CRDT document replicas
    synchronized with the server.
    
    Features:
        - Automatic reconnection with exponential backoff
        - Offline operation queue for disconnected editing
        - Qt signal-based event system for UI integration
        - Per-file CRDTDocument management
    """

    # ─── Qt Signals for UI Integration ───
    if HAS_QT:
        # Connection events
        connected = Signal(dict)             # Welcome message with full state
        disconnected = Signal(str)           # Reason string
        connection_state_changed = Signal(str)  # ConnectionState value
        
        # Document events
        remote_ops_received = Signal(str, list)     # (file_path, ops_dicts)
        document_snapshot_received = Signal(str, dict)  # (file_path, snapshot)
        
        # Cursor/presence events
        cursor_update_received = Signal(dict)   # {peer_id, peer_name, color, file_path, cursor_pos, ...}
        presence_update_received = Signal(dict) # {peer_id, peer_name, active_file, role, color}
        
        # Peer events
        peer_joined = Signal(dict)           # {peer_id, peer_name, role, color}
        peer_left = Signal(dict)             # {peer_id, peer_name}
        peers_updated = Signal(list)         # List of peer info dicts
        
        # File tree events
        file_tree_updated = Signal(list)     # List of file tree entries
        file_operation_received = Signal(dict) # {operation, file_path, ...}
        
        # Save events
        save_ack_received = Signal(dict)     # {file_path, saved_by, saved_at, version}
        
        # Execution events
        run_status_received = Signal(dict)   # {status, file_path, triggered_by, ...}
        run_output_received = Signal(dict)   # {run_id, output, stream}
        
        # Role events
        role_changed = Signal(dict)          # {new_role, changed_by}
        
        # Comment/Chat events
        comment_received = Signal(dict)      # {file_path, line, text, author, ...}
        chat_received = Signal(dict)         # {text, author, color, timestamp}
        
        # Error events
        error_received = Signal(str)         # Error message
        
        # Log
        log_emitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.peer_id: str = str(uuid.uuid4())[:8]
        self.peer_name: str = "Developer"
        self.assigned_color: str = "#0FE6B5"
        self.role: str = "editor"
        
        # Connection state
        self._server_url: str = ""
        self._state: str = ConnectionState.DISCONNECTED
        self._websocket = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._should_reconnect: bool = True
        self._reconnect_attempts: int = 0
        self._max_reconnect_delay: float = 16.0
        
        # Local CRDT documents: file_path → CRDTDocument
        self._documents: Dict[str, CRDTDocument] = {}
        
        # Offline operation queue: list of (file_path, ops_dicts)
        self._offline_queue: deque = deque()
        
        # Peer tracking
        self._peers: Dict[str, dict] = {}   # peer_id → peer info dict
        self._owner_id: str = ""
        self._owner_name: str = ""
        
        # File tree
        self._file_tree: List[dict] = []
        
        # Lock for thread safety
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def get_document(self, file_path: str) -> Optional[CRDTDocument]:
        """Gets the local CRDTDocument for a file, if it exists."""
        return self._documents.get(file_path)

    def get_or_create_document(self, file_path: str) -> CRDTDocument:
        """Gets or creates a local CRDTDocument for a file."""
        if file_path not in self._documents:
            self._documents[file_path] = CRDTDocument(site_id=self.peer_id)
        return self._documents[file_path]

    # ─────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────

    def connect_to_server(self, url: str, peer_name: str = "Developer") -> bool:
        """
        Connects to a CRDT sync server.
        
        Args:
            url: WebSocket URL (e.g., "ws://192.168.1.5:9090")
            peer_name: Display name for this peer
            
        Returns:
            True if connection thread started successfully
        """
        if not HAS_WEBSOCKETS:
            self.log_emitted.emit("websockets package not installed")
            return False
        
        self._server_url = url
        self.peer_name = peer_name
        self._should_reconnect = True
        self._reconnect_attempts = 0
        
        self._set_state(ConnectionState.CONNECTING)
        
        self._thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._thread.start()
        
        return True

    def disconnect(self):
        """Disconnects from the server."""
        self._should_reconnect = False
        self._set_state(ConnectionState.DISCONNECTED)
        
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        self._peers.clear()
        self._documents.clear()
        self.disconnected.emit("Disconnected from server")

    def _set_state(self, new_state: str):
        """Updates connection state and emits signal."""
        self._state = new_state
        self.connection_state_changed.emit(new_state)

    def _connection_loop(self):
        """Background thread: manages WebSocket connection with reconnect."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            logger.error(f"Connection loop error: {e}")
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _connect_and_listen(self):
        """Connects to the server and processes messages. Reconnects on failure."""
        while self._should_reconnect:
            try:
                async with ws_connect(
                    self._server_url,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=10 * 1024 * 1024,
                    open_timeout=5,
                ) as websocket:
                    self._websocket = websocket
                    self._reconnect_attempts = 0
                    
                    # Send join handshake
                    join_msg = {
                        "type": "join",
                        "peer_name": self.peer_name,
                        "peer_id": self.peer_id,
                    }
                    await websocket.send(json.dumps(join_msg))
                    
                    self._set_state(ConnectionState.CONNECTED)
                    self.log_emitted.emit(f"✓ Connected to CRDT server at {self._server_url}")
                    
                    # Flush offline queue
                    await self._flush_offline_queue()
                    
                    # Listen for messages
                    async for raw_message in websocket:
                        try:
                            msg = json.loads(raw_message)
                            await self._handle_message(msg)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"Message handling error: {e}")
                            
            except Exception as e:
                if not self._should_reconnect:
                    break
                
                self._set_state(ConnectionState.RECONNECTING)
                self._reconnect_attempts += 1
                
                # Exponential backoff with jitter
                delay = min(
                    2 ** self._reconnect_attempts + random.uniform(0, 1),
                    self._max_reconnect_delay
                )
                
                self.log_emitted.emit(
                    f"⚠️ Connection lost. Reconnecting in {delay:.1f}s "
                    f"(attempt {self._reconnect_attempts})..."
                )
                
                await asyncio.sleep(delay)
        
        self._websocket = None
        self._set_state(ConnectionState.DISCONNECTED)

    async def _flush_offline_queue(self):
        """Replays queued operations that were generated while offline."""
        with self._lock:
            queue_copy = list(self._offline_queue)
            self._offline_queue.clear()
        
        if queue_copy:
            self.log_emitted.emit(f"📤 Replaying {len(queue_copy)} offline operations...")
        
        for file_path, ops_dicts in queue_copy:
            msg = {
                "type": "ops",
                "file_path": file_path,
                "ops": ops_dicts,
                "timestamp": time.time(),
            }
            try:
                await self._websocket.send(json.dumps(msg))
            except Exception as e:
                logger.error(f"Failed to replay offline op: {e}")
                # Re-queue on failure
                with self._lock:
                    self._offline_queue.append((file_path, ops_dicts))

    # ─────────────────────────────────────────────
    # Message Handling
    # ─────────────────────────────────────────────

    async def _handle_message(self, msg: dict):
        """Routes incoming messages by type."""
        msg_type = msg.get("type", "")
        
        if msg_type == "joined":
            self._handle_joined(msg)
        elif msg_type == "ops":
            self._handle_remote_ops(msg)
        elif msg_type == "ops_batch":
            self._handle_ops_batch(msg)
        elif msg_type == "cursor_update":
            self.cursor_update_received.emit(msg)
        elif msg_type == "presence":
            self._handle_presence_update(msg)
        elif msg_type == "peer_joined":
            self._handle_peer_joined(msg)
        elif msg_type == "peer_left":
            self._handle_peer_left(msg)
        elif msg_type == "peers_updated":
            self._handle_peers_updated(msg)
        elif msg_type == "snapshot_response":
            self._handle_snapshot_response(msg)
        elif msg_type == "file_tree_update":
            self._file_tree = msg.get("tree", [])
            self.file_tree_updated.emit(self._file_tree)
        elif msg_type == "file_operation":
            self._handle_file_operation(msg)
        elif msg_type == "save_ack":
            self.save_ack_received.emit(msg)
        elif msg_type == "run_status":
            self.run_status_received.emit(msg)
        elif msg_type == "run_output":
            self.run_output_received.emit(msg)
        elif msg_type == "role_changed":
            self.role = msg.get("new_role", self.role)
            self.role_changed.emit(msg)
        elif msg_type == "comment":
            self.comment_received.emit(msg)
        elif msg_type == "chat":
            self.chat_received.emit(msg)
        elif msg_type == "error":
            self.error_received.emit(msg.get("message", "Unknown error"))

    def _handle_joined(self, msg: dict):
        """Processes the welcome message after joining."""
        self.assigned_color = msg.get("assigned_color", "#0FE6B5")
        self.role = msg.get("role", "editor")
        self._owner_name = msg.get("owner_name", "Host")
        self._owner_id = msg.get("owner_id", "")
        
        # Initialize documents from snapshots
        documents = msg.get("documents", {})
        for file_path, snapshot in documents.items():
            doc = CRDTDocument.from_snapshot(snapshot, self.peer_id)
            self._documents[file_path] = doc
        
        # Initialize peers
        peers = msg.get("peers", [])
        self._peers = {p["peer_id"]: p for p in peers}
        
        # Initialize file tree
        self._file_tree = msg.get("file_tree", [])
        
        self.connected.emit(msg)
        self.peers_updated.emit(list(self._peers.values()))
        self.file_tree_updated.emit(self._file_tree)
        
        self.log_emitted.emit(
            f"✓ Joined workspace hosted by {self._owner_name} "
            f"({len(self._documents)} files, {len(self._peers)} peers)"
        )

    def _handle_remote_ops(self, msg: dict):
        """Applies remote CRDT operations to the local document mirror."""
        sender_id = msg.get("sender_id", "")
        if sender_id == self.peer_id:
            return  # Ignore own ops echoed back
        
        file_path = msg.get("file_path", "")
        ops_data = msg.get("ops", [])
        
        if not file_path or not ops_data:
            return
        
        doc = self.get_or_create_document(file_path)
        ops = [CRDTOp.from_dict(op) for op in ops_data]
        doc.apply_remote_ops(ops)
        
        self.remote_ops_received.emit(file_path, ops_data)

    def _handle_ops_batch(self, msg: dict):
        """Handles batched operations from the server."""
        # Process each batch item as individual ops
        file_path = msg.get("file_path", "")
        ops_data = msg.get("ops", [])
        
        if file_path and ops_data:
            doc = self.get_or_create_document(file_path)
            ops = [CRDTOp.from_dict(op) for op in ops_data]
            doc.apply_remote_ops(ops)
            self.remote_ops_received.emit(file_path, ops_data)

    def _handle_presence_update(self, msg: dict):
        """Updates peer presence info."""
        peer_id = msg.get("peer_id", "")
        if peer_id and peer_id in self._peers:
            self._peers[peer_id].update(msg)
        self.presence_update_received.emit(msg)

    def _handle_peer_joined(self, msg: dict):
        """Handles a new peer joining."""
        peer_id = msg.get("peer_id", "")
        if peer_id:
            self._peers[peer_id] = msg
        self.peer_joined.emit(msg)
        self.peers_updated.emit(list(self._peers.values()))
        self.log_emitted.emit(f"👋 {msg.get('peer_name', 'Peer')} joined")

    def _handle_peer_left(self, msg: dict):
        """Handles a peer leaving."""
        peer_id = msg.get("peer_id", "")
        self._peers.pop(peer_id, None)
        self.peer_left.emit(msg)
        self.peers_updated.emit(list(self._peers.values()))
        self.log_emitted.emit(f"🚪 {msg.get('peer_name', 'Peer')} left")

    def _handle_peers_updated(self, msg: dict):
        """Handles full peer list update."""
        peers = msg.get("peers", [])
        self._peers = {p["peer_id"]: p for p in peers}
        self.peers_updated.emit(list(self._peers.values()))

    def _handle_snapshot_response(self, msg: dict):
        """Handles a document snapshot response."""
        file_path = msg.get("file_path", "")
        snapshot = msg.get("snapshot")
        
        if snapshot and file_path:
            doc = CRDTDocument.from_snapshot(snapshot, self.peer_id)
            self._documents[file_path] = doc
            self.document_snapshot_received.emit(file_path, snapshot)

    def _handle_file_operation(self, msg: dict):
        """Handles file create/rename/delete from other peers."""
        operation = msg.get("operation", "")
        file_path = msg.get("file_path", "")
        
        if operation == "delete":
            self._documents.pop(file_path, None)
        elif operation == "rename":
            new_path = msg.get("new_path", "")
            if file_path in self._documents:
                self._documents[new_path] = self._documents.pop(file_path)
        
        self.file_operation_received.emit(msg)

    # ─────────────────────────────────────────────
    # Outgoing Messages
    # ─────────────────────────────────────────────

    def send_ops(self, file_path: str, ops: List[CRDTOp]):
        """
        Sends local CRDT operations to the server.
        If disconnected, queues them for replay on reconnect.
        """
        ops_dicts = [op.to_dict() for op in ops]
        
        if self.is_connected and self._websocket:
            msg = {
                "type": "ops",
                "file_path": file_path,
                "ops": ops_dicts,
                "timestamp": time.time(),
            }
            self._send_async(json.dumps(msg))
        else:
            # Queue for offline replay
            with self._lock:
                self._offline_queue.append((file_path, ops_dicts))

    def send_cursor_update(self, file_path: str, cursor_pos: int,
                           selection_start: int = 0, selection_end: int = 0):
        """Broadcasts cursor position to all peers."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "cursor_update",
            "file_path": file_path,
            "cursor_pos": cursor_pos,
            "selection_start": selection_start,
            "selection_end": selection_end,
        }
        self._send_async(json.dumps(msg))

    def send_presence(self, active_file: str):
        """Updates which file this peer is currently viewing."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "presence",
            "active_file": active_file,
        }
        self._send_async(json.dumps(msg))

    def send_save_request(self, file_path: str, version: int = 0):
        """Requests a Ctrl+S save for a file."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "save_request",
            "file_path": file_path,
            "version": version,
        }
        self._send_async(json.dumps(msg))

    def send_run_request(self, file_path: str, run_id: Optional[str] = None):
        """Requests shared code execution."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "run_request",
            "file_path": file_path,
            "run_id": run_id or str(uuid.uuid4())[:8],
        }
        self._send_async(json.dumps(msg))

    def send_run_kill(self, run_id: str):
        """Requests cancellation of a running execution."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "run_kill",
            "run_id": run_id,
        }
        self._send_async(json.dumps(msg))

    def send_file_operation(self, operation: str, file_path: str, **kwargs):
        """Sends a file create/rename/delete operation."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "file_operation",
            "operation": operation,
            "file_path": file_path,
            **kwargs,
        }
        self._send_async(json.dumps(msg))

    def send_comment(self, file_path: str, line_start: int, line_end: int, text: str):
        """Sends an inline comment."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "comment",
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
            "text": text,
            "comment_id": str(uuid.uuid4())[:8],
        }
        self._send_async(json.dumps(msg))

    def send_chat(self, text: str):
        """Sends a chat message."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "chat",
            "text": text,
        }
        self._send_async(json.dumps(msg))

    def send_snapshot_request(self, file_path: str):
        """Requests a full document snapshot from the server."""
        if not self.is_connected:
            return
        
        msg = {
            "type": "snapshot_request",
            "file_path": file_path,
        }
        self._send_async(json.dumps(msg))

    def _send_async(self, message: str):
        """Sends a message asynchronously via the event loop."""
        if self._loop and self._websocket:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._websocket.send(message),
                    self._loop
                )
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
