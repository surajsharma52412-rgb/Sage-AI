"""
CRDT WebSocket Sync Server for SAGE Collaborative IDE.

Manages real-time synchronization of CRDT document state across multiple
connected clients in a workspace. Handles:
    - CRDT operation relay with batching (50ms windows)
    - Workspace/document management (one CRDTDocument per file)
    - Cursor position broadcasting
    - Presence tracking (online/offline/active-file)
    - Snapshot delivery for late joiners
    - File tree updates
    - Shared execution requests/output
    - Permission enforcement
    - Comments and chat relay

Protocol:
    All messages are JSON objects with a "type" field. Supported types:
        - join / joined / peer_joined / peer_left
        - ops / snapshot_request / snapshot_response
        - cursor_update / presence
        - file_tree_update / file_operation
        - save_request / save_ack
        - run_request / run_output / run_status
        - permission_change
        - comment / chat
"""

import json
import time
import asyncio
import logging
import uuid
import threading
from typing import Dict, Set, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import websockets
    from websockets.asyncio.server import serve as ws_serve
    HAS_WEBSOCKETS = True
except ImportError:
    try:
        import websockets
        from websockets.server import serve as ws_serve
        HAS_WEBSOCKETS = True
    except ImportError:
        HAS_WEBSOCKETS = False
        ws_serve = None
        logger.warning("websockets package not available — CRDT sync server disabled")

from engine.collab.crdt_document import CRDTDocument, CRDTOp, OpType


@dataclass
class PeerInfo:
    """Tracks state for a connected peer."""
    peer_id: str
    peer_name: str
    role: str = "editor"          # "owner", "editor", "viewer"
    active_file: str = ""         # Currently open file path
    cursor_pos: int = 0           # Visible cursor position
    selection_start: int = 0      # Selection range start
    selection_end: int = 0        # Selection range end
    color: str = "#0FE6B5"        # Assigned cursor color
    connected_at: float = 0.0
    last_heartbeat: float = 0.0

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "peer_name": self.peer_name,
            "role": self.role,
            "active_file": self.active_file,
            "cursor_pos": self.cursor_pos,
            "selection_start": self.selection_start,
            "selection_end": self.selection_end,
            "color": self.color,
            "connected_at": self.connected_at,
        }


# Distinct colors for peer cursors (max 10 peers)
PEER_COLORS = [
    "#0FE6B5",  # Emerald
    "#FF6B8A",  # Rose
    "#61AFEF",  # Sky Blue
    "#E5C07B",  # Gold
    "#C678DD",  # Purple
    "#56B6C2",  # Teal
    "#FF9F43",  # Orange
    "#98C379",  # Green
    "#E06C75",  # Red
    "#ABB2BF",  # Silver
]


class CRDTSyncServer:
    """
    WebSocket server that manages real-time CRDT synchronization
    for a collaborative workspace.
    
    One server instance manages one workspace. Multiple files within
    the workspace each get their own CRDTDocument instance.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9090,
        owner_name: str = "Host",
        owner_id: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.owner_name = owner_name
        self.owner_id = owner_id or str(uuid.uuid4())[:8]
        
        # Connected clients: websocket → PeerInfo
        self._peers: Dict[Any, PeerInfo] = {}
        
        # CRDT documents: file_path → CRDTDocument
        self._documents: Dict[str, CRDTDocument] = {}
        
        # File tree state: list of file entries
        self._file_tree: List[dict] = []
        
        # Op batching: file_path → list of pending ops
        self._op_buffer: Dict[str, List[dict]] = {}
        self._batch_interval: float = 0.05  # 50ms batching window
        
        # Server state
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.is_running: bool = False
        self._color_index: int = 0
        self._lock = threading.Lock()
        
        # Callbacks for integration with SAGE UI
        self.on_peer_joined = None   # Callable[[str, str], None] (name, id)
        self.on_peer_left = None     # Callable[[str], None] (name)
        self.on_log = None           # Callable[[str], None]
        self.on_run_request = None   # Callable[[dict], None]
        self.on_save_request = None  # Callable[[dict], None]

    def _assign_color(self) -> str:
        """Assigns a distinct color to a new peer."""
        color = PEER_COLORS[self._color_index % len(PEER_COLORS)]
        self._color_index += 1
        return color

    def get_or_create_document(self, file_path: str) -> CRDTDocument:
        """Gets or creates a CRDTDocument for the given file path."""
        if file_path not in self._documents:
            doc = CRDTDocument(site_id=f"server-{file_path}")
            self._documents[file_path] = doc
        return self._documents[file_path]

    def seed_document(self, file_path: str, content: str):
        """Seeds a document with initial content (e.g., from disk)."""
        doc = self.get_or_create_document(file_path)
        if doc.get_length() == 0 and content:
            doc.insert_at(0, content)

    def set_file_tree(self, tree: List[dict]):
        """Updates the authoritative file tree."""
        self._file_tree = tree

    def get_peer_names(self) -> List[str]:
        """Returns list of connected peer names."""
        names = [f"{self.owner_name} (Owner)"]
        for info in self._peers.values():
            names.append(info.peer_name)
        return names

    def get_peers_info(self) -> List[dict]:
        """Returns detailed info about all connected peers."""
        peers = [{
            "peer_id": self.owner_id,
            "peer_name": self.owner_name,
            "role": "owner",
            "color": PEER_COLORS[0],
        }]
        for info in self._peers.values():
            peers.append(info.to_dict())
        return peers

    # ─────────────────────────────────────────────
    # Server Lifecycle
    # ─────────────────────────────────────────────

    def start(self) -> bool:
        """Starts the WebSocket server in a background thread."""
        if not HAS_WEBSOCKETS:
            if self.on_log:
                self.on_log("Cannot start CRDT server: websockets package not installed")
            return False

        if self.is_running:
            return True

        try:
            self._thread = threading.Thread(target=self._run_server, daemon=True)
            self._thread.start()
            
            # Wait for server to be ready (up to 3 seconds)
            for _ in range(30):
                if self.is_running:
                    break
                time.sleep(0.1)
            
            if self.is_running and self.on_log:
                self.on_log(f"CRDT Sync Server started on ws://{self.host}:{self.port}")
            return self.is_running
        except Exception as e:
            logger.error(f"Failed to start CRDT sync server: {e}")
            if self.on_log:
                self.on_log(f"Failed to start sync server: {e}")
            return False

    def stop(self):
        """Stops the server and disconnects all clients."""
        self.is_running = False
        
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        self._peers.clear()
        self._documents.clear()
        self._op_buffer.clear()
        
        if self.on_log:
            self.on_log("CRDT Sync Server stopped")

    def _run_server(self):
        """Background thread: runs the asyncio WebSocket server."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"CRDT sync server error: {e}")
        finally:
            try:
                self._loop.close()
            except Exception:
                pass
            self.is_running = False

    async def _serve(self):
        """Starts the WebSocket listener and op batcher."""
        try:
            self._server = await ws_serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message
            )
            self.is_running = True
            
            # Start the op batcher coroutine
            batcher_task = asyncio.create_task(self._op_batcher())
            
            # Keep running until stopped
            while self.is_running:
                await asyncio.sleep(0.1)
            
            batcher_task.cancel()
            self._server.close()
            await self._server.wait_closed()
        except Exception as e:
            logger.error(f"WebSocket serve error: {e}")
            self.is_running = False

    async def _op_batcher(self):
        """Periodically flushes buffered ops to all connected clients."""
        while self.is_running:
            await asyncio.sleep(self._batch_interval)
            
            with self._lock:
                buffers_to_send = dict(self._op_buffer)
                self._op_buffer.clear()
            
            for file_path, ops in buffers_to_send.items():
                if not ops:
                    continue
                batch_msg = json.dumps({
                    "type": "ops_batch",
                    "file_path": file_path,
                    "ops": ops,
                    "timestamp": time.time(),
                })
                await self._broadcast(batch_msg, exclude=None)

    # ─────────────────────────────────────────────
    # Connection Handling
    # ─────────────────────────────────────────────

    async def _handle_connection(self, websocket):
        """Handles a new WebSocket connection."""
        peer_info = None
        try:
            async for raw_message in websocket:
                try:
                    msg = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue
                
                msg_type = msg.get("type", "")
                
                if msg_type == "join":
                    peer_info = await self._handle_join(websocket, msg)
                elif peer_info is not None:
                    await self._handle_message(websocket, peer_info, msg)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Connection handler error: {e}")
        finally:
            if peer_info:
                await self._handle_disconnect(websocket, peer_info)

    async def _handle_join(self, websocket, msg: dict) -> PeerInfo:
        """Handles a new peer joining the workspace."""
        peer_name = msg.get("peer_name", "Anonymous")
        peer_id = msg.get("peer_id", str(uuid.uuid4())[:8])
        
        peer_info = PeerInfo(
            peer_id=peer_id,
            peer_name=peer_name,
            role="editor",  # Default role
            color=self._assign_color(),
            connected_at=time.time(),
            last_heartbeat=time.time(),
        )
        
        self._peers[websocket] = peer_info
        
        # Build welcome message with full state
        docs_snapshot = {}
        for file_path, doc in self._documents.items():
            docs_snapshot[file_path] = doc.get_snapshot()
        
        welcome = {
            "type": "joined",
            "peer_id": peer_id,
            "assigned_color": peer_info.color,
            "role": peer_info.role,
            "owner_name": self.owner_name,
            "owner_id": self.owner_id,
            "peers": self.get_peers_info(),
            "documents": docs_snapshot,
            "file_tree": self._file_tree,
            "timestamp": time.time(),
        }
        
        await websocket.send(json.dumps(welcome))
        
        # Broadcast peer_joined to all others
        join_msg = json.dumps({
            "type": "peer_joined",
            "peer_id": peer_id,
            "peer_name": peer_name,
            "role": peer_info.role,
            "color": peer_info.color,
            "peers": self.get_peers_info(),
        })
        await self._broadcast(join_msg, exclude=websocket)
        
        if self.on_peer_joined:
            try:
                self.on_peer_joined(peer_name, peer_id)
            except Exception:
                pass
        
        if self.on_log:
            self.on_log(f"👋 {peer_name} joined the workspace")
        
        return peer_info

    async def _handle_disconnect(self, websocket, peer_info: PeerInfo):
        """Handles a peer disconnecting."""
        self._peers.pop(websocket, None)
        
        # Broadcast peer_left to all remaining
        leave_msg = json.dumps({
            "type": "peer_left",
            "peer_id": peer_info.peer_id,
            "peer_name": peer_info.peer_name,
            "peers": self.get_peers_info(),
        })
        await self._broadcast(leave_msg, exclude=None)
        
        if self.on_peer_left:
            try:
                self.on_peer_left(peer_info.peer_name)
            except Exception:
                pass
        
        if self.on_log:
            self.on_log(f"🚪 {peer_info.peer_name} left the workspace")

    # ─────────────────────────────────────────────
    # Message Handling
    # ─────────────────────────────────────────────

    async def _handle_message(self, websocket, peer_info: PeerInfo, msg: dict):
        """Routes incoming messages by type."""
        msg_type = msg.get("type", "")
        
        if msg_type == "ops":
            await self._handle_ops(websocket, peer_info, msg)
        elif msg_type == "cursor_update":
            await self._handle_cursor_update(websocket, peer_info, msg)
        elif msg_type == "presence":
            await self._handle_presence(websocket, peer_info, msg)
        elif msg_type == "snapshot_request":
            await self._handle_snapshot_request(websocket, msg)
        elif msg_type == "file_tree_update":
            await self._handle_file_tree_update(websocket, peer_info, msg)
        elif msg_type == "file_operation":
            await self._handle_file_operation(websocket, peer_info, msg)
        elif msg_type == "save_request":
            await self._handle_save_request(websocket, peer_info, msg)
        elif msg_type == "run_request":
            await self._handle_run_request(websocket, peer_info, msg)
        elif msg_type == "run_kill":
            await self._handle_run_kill(websocket, peer_info, msg)
        elif msg_type == "permission_change":
            await self._handle_permission_change(websocket, peer_info, msg)
        elif msg_type == "comment":
            await self._handle_comment(websocket, peer_info, msg)
        elif msg_type == "chat":
            await self._handle_chat(websocket, peer_info, msg)
        elif msg_type == "heartbeat":
            peer_info.last_heartbeat = time.time()
        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def _handle_ops(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles incoming CRDT operations."""
        file_path = msg.get("file_path", "")
        ops_data = msg.get("ops", [])
        
        if not file_path or not ops_data:
            return
        
        # Check permissions
        if peer_info.role == "viewer":
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Viewers cannot edit files",
            }))
            return
        
        # Apply ops to the server's authoritative document
        doc = self.get_or_create_document(file_path)
        ops = [CRDTOp.from_dict(op) for op in ops_data]
        doc.apply_remote_ops(ops)
        
        # Buffer ops for batched broadcast (excluding sender)
        relay_msg = {
            "type": "ops",
            "file_path": file_path,
            "ops": ops_data,
            "sender_id": peer_info.peer_id,
            "sender_name": peer_info.peer_name,
            "timestamp": time.time(),
        }
        
        # Broadcast immediately to all except sender
        await self._broadcast(json.dumps(relay_msg), exclude=websocket)

    async def _handle_cursor_update(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles cursor position/selection updates."""
        peer_info.cursor_pos = msg.get("cursor_pos", 0)
        peer_info.selection_start = msg.get("selection_start", 0)
        peer_info.selection_end = msg.get("selection_end", 0)
        peer_info.active_file = msg.get("file_path", peer_info.active_file)
        
        # Relay to all other peers
        cursor_msg = json.dumps({
            "type": "cursor_update",
            "peer_id": peer_info.peer_id,
            "peer_name": peer_info.peer_name,
            "color": peer_info.color,
            "file_path": peer_info.active_file,
            "cursor_pos": peer_info.cursor_pos,
            "selection_start": peer_info.selection_start,
            "selection_end": peer_info.selection_end,
        })
        await self._broadcast(cursor_msg, exclude=websocket)

    async def _handle_presence(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles presence updates (which file is active)."""
        peer_info.active_file = msg.get("active_file", "")
        peer_info.last_heartbeat = time.time()
        
        presence_msg = json.dumps({
            "type": "presence",
            "peer_id": peer_info.peer_id,
            "peer_name": peer_info.peer_name,
            "active_file": peer_info.active_file,
            "role": peer_info.role,
            "color": peer_info.color,
        })
        await self._broadcast(presence_msg, exclude=websocket)

    async def _handle_snapshot_request(self, websocket, msg: dict):
        """Sends a full document snapshot to a requesting client."""
        file_path = msg.get("file_path", "")
        doc = self._documents.get(file_path)
        
        if doc:
            snapshot = doc.get_snapshot()
            await websocket.send(json.dumps({
                "type": "snapshot_response",
                "file_path": file_path,
                "snapshot": snapshot,
            }))
        else:
            await websocket.send(json.dumps({
                "type": "snapshot_response",
                "file_path": file_path,
                "snapshot": None,
                "error": "Document not found",
            }))

    async def _handle_file_tree_update(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles file tree changes from the host."""
        self._file_tree = msg.get("tree", [])
        await self._broadcast(json.dumps(msg), exclude=websocket)

    async def _handle_file_operation(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles file create/rename/delete operations."""
        operation = msg.get("operation", "")
        file_path = msg.get("file_path", "")
        
        if operation == "create":
            content = msg.get("content", "")
            language = msg.get("language", "")
            doc = self.get_or_create_document(file_path)
            if content:
                doc.insert_at(0, content)
        elif operation == "delete":
            self._documents.pop(file_path, None)
        elif operation == "rename":
            new_path = msg.get("new_path", "")
            if file_path in self._documents:
                self._documents[new_path] = self._documents.pop(file_path)
        
        # Broadcast to all peers
        await self._broadcast(json.dumps(msg), exclude=websocket)

    async def _handle_save_request(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles Ctrl+S save requests."""
        file_path = msg.get("file_path", "")
        doc = self._documents.get(file_path)
        
        if doc:
            msg["content"] = doc.get_text()
            msg["snapshot"] = doc.get_snapshot()
        
        if self.on_save_request:
            try:
                self.on_save_request(msg)
            except Exception as e:
                logger.error(f"Save request callback error: {e}")
        
        # Broadcast save_ack to all peers
        ack = json.dumps({
            "type": "save_ack",
            "file_path": file_path,
            "saved_by": peer_info.peer_name,
            "saved_at": time.time(),
            "version": msg.get("version", 0),
        })
        await self._broadcast(ack, exclude=None)

    async def _handle_run_request(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles shared execution requests."""
        if peer_info.role == "viewer":
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Viewers cannot execute code",
            }))
            return
        
        msg["triggered_by"] = peer_info.peer_name
        msg["triggered_by_id"] = peer_info.peer_id
        
        # Broadcast run status to all peers
        await self._broadcast(json.dumps({
            "type": "run_status",
            "status": "started",
            "file_path": msg.get("file_path", ""),
            "triggered_by": peer_info.peer_name,
            "run_id": msg.get("run_id", str(uuid.uuid4())[:8]),
            "timestamp": time.time(),
        }), exclude=None)
        
        if self.on_run_request:
            try:
                self.on_run_request(msg)
            except Exception as e:
                logger.error(f"Run request callback error: {e}")

    async def _handle_run_kill(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles run cancellation."""
        await self._broadcast(json.dumps({
            "type": "run_status",
            "status": "killed",
            "killed_by": peer_info.peer_name,
            "run_id": msg.get("run_id", ""),
            "timestamp": time.time(),
        }), exclude=None)

    async def _handle_permission_change(self, websocket, peer_info: PeerInfo, msg: dict):
        """Handles role changes (owner only)."""
        # Only owner can change permissions
        if peer_info.peer_id != self.owner_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Only the workspace owner can change permissions",
            }))
            return
        
        target_id = msg.get("target_peer_id", "")
        new_role = msg.get("new_role", "editor")
        
        for ws, info in self._peers.items():
            if info.peer_id == target_id:
                info.role = new_role
                
                # Notify the target peer
                await ws.send(json.dumps({
                    "type": "role_changed",
                    "new_role": new_role,
                    "changed_by": peer_info.peer_name,
                }))
                
                # Broadcast updated peers list
                await self._broadcast(json.dumps({
                    "type": "peers_updated",
                    "peers": self.get_peers_info(),
                }), exclude=None)
                break

    async def _handle_comment(self, websocket, peer_info: PeerInfo, msg: dict):
        """Relays inline comments to all peers."""
        msg["author"] = peer_info.peer_name
        msg["author_id"] = peer_info.peer_id
        msg["timestamp"] = time.time()
        await self._broadcast(json.dumps(msg), exclude=websocket)

    async def _handle_chat(self, websocket, peer_info: PeerInfo, msg: dict):
        """Relays chat messages to all peers."""
        msg["author"] = peer_info.peer_name
        msg["author_id"] = peer_info.peer_id
        msg["color"] = peer_info.color
        msg["timestamp"] = time.time()
        await self._broadcast(json.dumps(msg), exclude=None)

    # ─────────────────────────────────────────────
    # Broadcasting
    # ─────────────────────────────────────────────

    async def _broadcast(self, message: str, exclude=None):
        """Broadcasts a message to all connected peers except the excluded one."""
        dead = []
        for ws, info in list(self._peers.items()):
            if ws == exclude:
                continue
            try:
                await ws.send(message)
            except Exception:
                dead.append(ws)
        
        # Clean up dead connections
        for ws in dead:
            info = self._peers.pop(ws, None)
            if info and self.on_peer_left:
                try:
                    self.on_peer_left(info.peer_name)
                except Exception:
                    pass

    async def broadcast_run_output(self, run_id: str, output: str, stream: str = "stdout"):
        """Broadcasts execution output to all connected peers."""
        msg = json.dumps({
            "type": "run_output",
            "run_id": run_id,
            "output": output,
            "stream": stream,
            "timestamp": time.time(),
        })
        await self._broadcast(msg, exclude=None)

    def broadcast_run_output_sync(self, run_id: str, output: str, stream: str = "stdout"):
        """Thread-safe synchronous wrapper for broadcasting run output."""
        if self._loop and self.is_running:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_run_output(run_id, output, stream),
                    self._loop
                )
            except Exception as e:
                logger.error(f"Error broadcasting run output: {e}")

    def broadcast_message_sync(self, msg: dict):
        """Thread-safe synchronous wrapper for broadcasting any message."""
        if self._loop and self.is_running:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(json.dumps(msg), exclude=None),
                    self._loop
                )
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
