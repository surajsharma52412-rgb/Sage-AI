"""
Real-Time Collaborative Coding & Whiteboard Service for Sage AI (Lunar Engine).
Enables multi-user pair programming and synchronized architecture sketching across LAN, Wi-Fi, or direct IP.
Architecture:
- CollabServer: Threaded TCP server handling multiple peer connections, multi-file edits, and whiteboard strokes.
- CollabClient: Background socket thread communicating with host.
- CollabManager: Qt QObject bridge emitting thread-safe signals to the GUI.
"""
import os
import sys
import json
import socket
import select
import threading
import uuid
import time
import logging
import queue
import random
import string
import urllib.request
from typing import Optional, Dict, Any, List

try:
    import requests
    from requests.adapters import HTTPAdapter
except Exception:
    requests = None
    HTTPAdapter = None

try:
    import importlib
    _ws_mod = importlib.import_module("websockets.sync.client")
    ws_sync_connect = getattr(_ws_mod, "connect", None)
except Exception:
    try:
        from websockets.sync.client import connect as ws_sync_connect  # type: ignore  # noqa: F401
    except Exception:
        ws_sync_connect = None

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """Detects the primary LAN IP address of this machine."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


class CollabServer:
    """
    Lightweight TCP Socket Server for Collaborative Sessions.
    Broadcasts real-time multi-file document states, incremental edits, whiteboard strokes, and peer presence.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8989, host_name: str = "Host"):
        self.host = host
        self.port = port
        self.host_name = host_name
        self.server_socket: Optional[socket.socket] = None
        self.clients: Dict[socket.socket, Dict[str, Any]] = {}
        self.is_running: bool = False
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

        # Multi-Document State Registry (filename -> {filename, language, content, version})
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.peer_active_files: Dict[str, str] = {}  # peer_id -> filename
        self.active_file: str = "untitled.py"

        # Collaborative Whiteboard State (List of stroke dictionaries)
        self.whiteboard_strokes: List[Dict[str, Any]] = []

        # Callbacks to CollabManager
        self.on_peer_joined = None
        self.on_peer_left = None
        self.on_edit_received = None
        self.on_file_added = None
        self.on_peer_focus = None
        self.on_wb_stroke = None
        self.on_wb_clear = None
        self.on_wb_undo = None
        self.on_log = None

    @property
    def current_doc(self) -> Dict[str, Any]:
        """Backward compatibility for legacy single-document accessors."""
        with self._lock:
            if self.documents:
                if self.active_file in self.documents:
                    return self.documents[self.active_file]
                return next(iter(self.documents.values()))
            return {
                "filename": "untitled.py",
                "language": "Python",
                "content": "",
                "version": 0,
            }

    def add_document(self, filename: str, language: str, content: str) -> Dict[str, Any]:
        """Adds or updates a document in the shared session registry."""
        with self._lock:
            if filename in self.documents:
                self.documents[filename]["language"] = language
                self.documents[filename]["content"] = content
                self.documents[filename]["version"] += 1
            else:
                self.documents[filename] = {
                    "filename": filename,
                    "language": language,
                    "content": content,
                    "version": 1,
                }
            self.active_file = filename
            return dict(self.documents[filename])

    def update_doc_state(self, filename: str, language: str, content: str):
        """Updates authoritative document state."""
        self.add_document(filename, language, content)

    def start(self) -> bool:
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self.server_socket.bind((self.host, self.port))
            self.port = self.server_socket.getsockname()[1]
            self.server_socket.listen(10)
            self.is_running = True

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            if self.on_log:
                self.on_log(f"Hosting collaborative session on port {self.port}...")
            return True
        except Exception as e:
            if self.on_log:
                self.on_log(f"Failed to start host server on port {self.port}: {e}")
            self.stop()
            return False

    def stop(self):
        """Clean, zero-deadlock teardown of server and all connected sockets."""
        self.is_running = False

        # Close all peer sockets safely
        with self._lock:
            clients_to_close = list(self.clients.keys())
            self.clients.clear()
            self.peer_active_files.clear()

        for sock in clients_to_close:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

        # Close main listening server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

        # Wait for background loop thread to exit cleanly if called from another thread
        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            self._thread.join(timeout=0.6)

    def broadcast_message(self, message: dict, exclude_sock: Optional[socket.socket] = None):
        """Broadcasts a JSON packet to all peers safely with RLock protection."""
        try:
            payload = (json.dumps(message) + "\n").encode("utf-8")
        except Exception:
            return

        dead_socks = []
        with self._lock:
            client_sockets = list(self.clients.keys())

        for sock in client_sockets:
            if sock == exclude_sock:
                continue
            try:
                sock.sendall(payload)
            except Exception:
                dead_socks.append(sock)

        if dead_socks:
            with self._lock:
                for sock in dead_socks:
                    self._remove_client(sock, broadcast_leave=False)

    def _remove_client(self, sock: socket.socket, broadcast_leave: bool = True):
        """Removes a client safely without deadlock."""
        info = self.clients.pop(sock, None)
        try:
            sock.close()
        except Exception:
            pass

        if info:
            peer_name = info.get("name", "Unknown")
            peer_id = info.get("id")
            if peer_id in self.peer_active_files:
                self.peer_active_files.pop(peer_id, None)

            if self.on_peer_left:
                try:
                    self.on_peer_left(peer_name)
                except Exception:
                    pass

            if broadcast_leave and self.is_running:
                self.broadcast_message({
                    "type": "peer_left",
                    "peer_name": peer_name,
                    "peer_id": peer_id,
                    "peers": self.get_peer_names(),
                    "peer_active_files": self.peer_active_files,
                })

    def get_peer_names(self) -> List[str]:
        names = [f"{self.host_name} (Host)"]
        with self._lock:
            for info in self.clients.values():
                names.append(info.get("name", "Peer"))
        return names

    def _run_loop(self):
        while self.is_running:
            try:
                with self._lock:
                    if not self.server_socket:
                        break
                    watch_socks = [self.server_socket] + list(self.clients.keys())

                if not watch_socks:
                    time.sleep(0.05)
                    continue

                try:
                    readable, _, exceptional = select.select(watch_socks, [], watch_socks, 0.02)
                except (OSError, ValueError):
                    if not self.is_running:
                        break
                    continue

                for sock in exceptional:
                    if sock == self.server_socket:
                        break
                    with self._lock:
                        self._remove_client(sock)

                for sock in readable:
                    if not self.is_running:
                        break
                    if sock == self.server_socket:
                        # Accept new incoming peer
                        try:
                            client_sock, client_addr = self.server_socket.accept()
                            client_sock.setblocking(True)
                            try:
                                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                            except Exception:
                                pass
                            with self._lock:
                                self.clients[client_sock] = {
                                    "addr": client_addr,
                                    "name": f"Peer-{client_addr[0]}",
                                    "id": str(uuid.uuid4())[:8],
                                    "buffer": ""
                                }
                        except Exception:
                            pass
                    else:
                        # Process peer data
                        self._handle_client_data(sock)
            except Exception:
                if not self.is_running:
                    break

    def _handle_client_data(self, sock: socket.socket):
        try:
            chunk = sock.recv(4096)
            if not chunk:
                with self._lock:
                    self._remove_client(sock)
                return

            with self._lock:
                client_info = self.clients.get(sock)
                if not client_info:
                    return
                client_info["buffer"] += chunk.decode("utf-8", errors="replace")
                buffer = client_info["buffer"]

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                with self._lock:
                    if sock in self.clients:
                        self.clients[sock]["buffer"] = buffer
                    else:
                        break
                line = line.strip()
                if line:
                    self._process_client_message(sock, line)
        except Exception:
            with self._lock:
                self._remove_client(sock)

    def _process_client_message(self, sock: socket.socket, raw_line: str):
        try:
            msg = json.loads(raw_line)
        except Exception:
            return

        msg_type = msg.get("type")

        if msg_type == "join":
            peer_name = msg.get("peer_name", "Anonymous")
            peer_id = msg.get("peer_id", str(uuid.uuid4())[:8])
            with self._lock:
                if sock in self.clients:
                    self.clients[sock]["name"] = peer_name
                    self.clients[sock]["id"] = peer_id

            # Send welcome snapshot containing ALL shared documents & whiteboard strokes
            with self._lock:
                docs_snapshot = {k: dict(v) for k, v in self.documents.items()}
                active_f = self.active_file
                peers = self.get_peer_names()
                peer_files = dict(self.peer_active_files)
                wb_snapshot = list(self.whiteboard_strokes)

            welcome_msg = {
                "type": "joined",
                "host_name": self.host_name,
                "files": docs_snapshot,
                "active_file": active_f,
                "doc": self.current_doc,  # backward compatibility
                "peers": peers,
                "peer_active_files": peer_files,
                "whiteboard_strokes": wb_snapshot,
                "assigned_id": peer_id
            }
            try:
                sock.sendall((json.dumps(welcome_msg) + "\n").encode("utf-8"))
            except Exception:
                return

            if self.on_peer_joined:
                try:
                    self.on_peer_joined(peer_name, peer_id)
                except Exception:
                    pass

            # Broadcast to all other peers that someone joined
            self.broadcast_message({
                "type": "peer_joined",
                "peer_name": peer_name,
                "peer_id": peer_id,
                "peers": self.get_peer_names(),
                "peer_active_files": self.peer_active_files,
            }, exclude_sock=sock)

        elif msg_type == "edit":
            filename = msg.get("filename") or self.active_file
            content = msg.get("content", "")
            with self._lock:
                if filename in self.documents:
                    self.documents[filename]["content"] = content
                    self.documents[filename]["version"] = msg.get("version", self.documents[filename]["version"] + 1)
                else:
                    self.documents[filename] = {
                        "filename": filename,
                        "language": msg.get("language", "Python"),
                        "content": content,
                        "version": msg.get("version", 1),
                    }

            if self.on_edit_received:
                try:
                    self.on_edit_received(msg)
                except Exception:
                    pass

            self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type in ("file_add", "file_import"):
            filename = msg.get("filename")
            if not filename:
                return
            language = msg.get("language", "Python")
            content = msg.get("content", "")
            with self._lock:
                self.documents[filename] = {
                    "filename": filename,
                    "language": language,
                    "content": content,
                    "version": msg.get("version", 1),
                }

            if self.on_file_added:
                try:
                    self.on_file_added(msg)
                except Exception:
                    pass

            self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type == "file_focus":
            peer_id = msg.get("peer_id")
            peer_name = msg.get("peer_name", "Peer")
            filename = msg.get("filename", "")
            with self._lock:
                if peer_id:
                    self.peer_active_files[peer_id] = filename

            if self.on_peer_focus:
                try:
                    self.on_peer_focus(msg)
                except Exception:
                    pass

            self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type == "wb_stroke":
            stroke = msg.get("stroke")
            if stroke:
                with self._lock:
                    self.whiteboard_strokes.append(stroke)
                if self.on_wb_stroke:
                    try:
                        self.on_wb_stroke(stroke)
                    except Exception:
                        pass
                self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type == "wb_clear":
            with self._lock:
                self.whiteboard_strokes.clear()
            peer_name = msg.get("peer_name", "Peer")
            if self.on_wb_clear:
                try:
                    self.on_wb_clear(peer_name)
                except Exception:
                    pass
            self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type == "wb_undo":
            with self._lock:
                if self.whiteboard_strokes:
                    self.whiteboard_strokes.pop()
            peer_name = msg.get("peer_name", "Peer")
            if self.on_wb_undo:
                try:
                    self.on_wb_undo(peer_name)
                except Exception:
                    pass
            self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type == "file_change":
            # Legacy fallback
            filename = msg.get("filename", "untitled.py")
            language = msg.get("language", "Python")
            content = msg.get("content", "")
            self.add_document(filename, language, content)

            if self.on_edit_received:
                try:
                    self.on_edit_received(msg)
                except Exception:
                    pass

            self.broadcast_message(msg, exclude_sock=sock)

        elif msg_type == "cursor":
            self.broadcast_message(msg, exclude_sock=sock)


class CollabClient:
    """
    TCP Socket Client for connecting to an active Collaborative Session.
    """

    def __init__(self, host: str, port: int, user_name: str = "Peer"):
        self.host = host
        self.port = port
        self.user_name = user_name
        self.client_id = str(uuid.uuid4())[:8]
        self.sock: Optional[socket.socket] = None
        self.is_connected: bool = False
        self._is_disconnecting: bool = False
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_joined = None
        self.on_edit_received = None
        self.on_file_added = None
        self.on_peer_focus = None
        self.on_wb_stroke = None
        self.on_wb_clear = None
        self.on_wb_undo = None
        self.on_peer_joined = None
        self.on_peer_left = None
        self.on_disconnected = None
        self.on_log = None

    def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self.is_connected = True
            self._is_disconnecting = False

            # Send join handshake
            join_msg = {
                "type": "join",
                "peer_name": self.user_name,
                "peer_id": self.client_id
            }
            self.sock.sendall((json.dumps(join_msg) + "\n").encode("utf-8"))

            self._thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            if self.on_log:
                self.on_log(f"Connection to {self.host}:{self.port} failed: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Safe, non-reentrant client disconnection."""
        with self._lock:
            if self._is_disconnecting or not self.is_connected:
                return
            self._is_disconnecting = True
            self.is_connected = False
            sock = self.sock
            self.sock = None

        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            self._thread.join(timeout=0.6)

        if self.on_disconnected:
            try:
                self.on_disconnected("Disconnected from host.")
            except Exception:
                pass

    def send_message(self, message: dict):
        if not self.is_connected or not self.sock:
            return
        try:
            payload = (json.dumps(message) + "\n").encode("utf-8")
            self.sock.sendall(payload)
        except Exception as e:
            if self.on_log:
                self.on_log(f"Error sending collab update: {e}")
            self.disconnect()

    def send_whiteboard_stroke(self, stroke: dict):
        """Sends a drawn stroke to the host and all connected peers."""
        self.send_message({"type": "wb_stroke", "stroke": stroke, "peer_name": self.user_name})

    def send_whiteboard_clear(self):
        """Sends a clear command to the host and all peers."""
        self.send_message({"type": "wb_clear", "peer_name": self.user_name})

    def send_whiteboard_undo(self):
        """Sends an undo command to the host and all peers."""
        self.send_message({"type": "wb_undo", "peer_name": self.user_name})

    def _receive_loop(self):
        buffer = ""
        while self.is_connected and self.sock:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process_message(line)
            except Exception:
                break

        if self.is_connected:
            self.disconnect()

    def _process_message(self, raw_line: str):
        try:
            msg = json.loads(raw_line)
        except Exception:
            return

        msg_type = msg.get("type")
        if msg_type == "joined":
            if self.on_joined:
                self.on_joined(msg)
        elif msg_type == "edit":
            if self.on_edit_received:
                self.on_edit_received(msg)
        elif msg_type in ("file_add", "file_import"):
            if self.on_file_added:
                self.on_file_added(msg)
        elif msg_type == "file_focus":
            if self.on_peer_focus:
                self.on_peer_focus(msg)
        elif msg_type == "wb_stroke":
            if self.on_wb_stroke:
                self.on_wb_stroke(msg.get("stroke"))
        elif msg_type == "wb_clear":
            if self.on_wb_clear:
                self.on_wb_clear(msg.get("peer_name", "Peer"))
        elif msg_type == "wb_undo":
            if self.on_wb_undo:
                self.on_wb_undo(msg.get("peer_name", "Peer"))
        elif msg_type == "file_change":
            if self.on_edit_received:
                self.on_edit_received(msg)
        elif msg_type == "peer_joined":
            if self.on_peer_joined:
                self.on_peer_joined(msg.get("peer_name", "Peer"), msg.get("peer_id", ""))
        elif msg_type == "peer_left":
            if self.on_peer_left:
                self.on_peer_left(msg.get("peer_name", "Peer"))


def generate_room_code(prefix: str = "SAGE") -> str:
    """Generates a clean 6-8 character shareable room code (e.g. SAGE-4829)."""
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # Exclude ambiguous 0/O, 1/I
    suffix = "".join(random.choices(chars, k=4))
    return f"{prefix}-{suffix}"


class CollabCloudRelay:
    """
    Worldwide Internet Collaboration Relay over secure WebSocket/HTTP pub-sub channels.
    Enables real-time multi-file coding and interactive whiteboard sketching between users
    on completely different Wi-Fi networks, mobile hotspots, or offices without requiring
    the same local network or router port forwarding.
    """

    def __init__(self, room_code: str, user_name: str = "Developer", role: str = "client"):
        self.room_code = room_code.strip().upper()
        # Clean channel name for ntfy.sh
        clean_code = self.room_code.lower().replace("-", "_")
        self.channel = f"sage_collab_{clean_code}"
        self.user_name = user_name
        self.role = role  # "host" or "client"
        self.my_id = str(uuid.uuid4())[:8]

        self.ws_url = f"wss://ntfy.sh/{self.channel}/ws"
        self.publish_url = f"https://ntfy.sh/{self.channel}"

        self.is_connected = False
        self._lock = threading.RLock()
        self._send_queue: queue.Queue = queue.Queue()

        self._listen_thread: Optional[threading.Thread] = None
        self._send_thread: Optional[threading.Thread] = None
        self._ws_client = None
        self._connected_event = threading.Event()

        # Authoritative session state (replicated on host)
        self.documents: Dict[str, dict] = {}
        self.whiteboard_strokes: List[dict] = []
        self.peer_names: Dict[str, str] = {
            self.my_id: f"{self.user_name} (Host)" if self.role == "host" else self.user_name
        }
        self.peer_active_files: Dict[str, str] = {}

        # Callbacks matching CollabServer / CollabClient
        self.on_joined = None
        self.on_edit_received = None
        self.on_file_added = None
        self.on_peer_focus = None
        self.on_wb_stroke = None
        self.on_wb_clear = None
        self.on_wb_undo = None
        self.on_peer_joined = None
        self.on_peer_left = None
        self.on_disconnected = None
        self.on_log = None

    def start(self) -> bool:
        """Connects to the cloud relay WebSocket listener and starts the background sender."""
        if ws_sync_connect is None:
            if self.on_log:
                self.on_log("websockets package not installed. Cloud relay unavailable.")
            return False

        self.is_connected = True
        self._connected_event.clear()

        # 1. Background sender thread
        self._send_thread = threading.Thread(target=self._send_worker, daemon=True)
        self._send_thread.start()

        # 2. Background receiver listener thread
        self._listen_thread = threading.Thread(target=self._listen_worker, daemon=True)
        self._listen_thread.start()

        # Wait up to 6.0 seconds for connection handshake
        connected = self._connected_event.wait(timeout=6.0)
        if not connected or not self.is_connected:
            self.disconnect()
            return False

        if self.role == "client":
            # Broadcast join request to room host
            self.send_message({
                "type": "join",
                "peer_name": self.user_name,
                "peer_id": self.my_id
            })

        return True

    def send_message(self, message: dict):
        """Envelopes and queues a message to be published over the cloud channel."""
        if not self.is_connected:
            return

        envelope = {
            "sender_id": self.my_id,
            "sender_name": self.user_name,
            "room_code": self.room_code,
            "message": message,
            "timestamp": time.time()
        }
        self._send_queue.put(envelope)

    def _send_worker(self):
        """Background worker that publishes queued envelopes using persistent HTTP session with conflation."""
        session = None
        if requests and HTTPAdapter:
            try:
                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=1)
                session.mount("https://", adapter)
                session.mount("http://", adapter)
            except Exception:
                session = None

        while self.is_connected:
            try:
                first_envelope = self._send_queue.get(timeout=0.08)
            except queue.Empty:
                continue

            # Batch and conflate queued envelopes to drop obsolete typing states
            batch = [first_envelope]
            while True:
                try:
                    batch.append(self._send_queue.get_nowait())
                except queue.Empty:
                    break

            # Conflate multiple "edit" messages for same file down to the latest revision
            latest_edits = {}  # filename -> envelope
            to_send = []

            for env in batch:
                m = env.get("message", {})
                m_type = m.get("type")
                if m_type == "edit":
                    f_name = m.get("filename", "untitled.py")
                    latest_edits[f_name] = env
                else:
                    to_send.append(env)

            # Append the latest edit for each file (order preserved at end)
            to_send.extend(latest_edits.values())

            for envelope in to_send:
                if not self.is_connected:
                    break
                try:
                    data_bytes = json.dumps(envelope).encode("utf-8")
                    if session:
                        session.post(
                            self.publish_url,
                            data=data_bytes,
                            headers={"Content-Type": "application/json", "User-Agent": "SageAI-Collab/1.0"},
                            timeout=4
                        )
                    else:
                        req = urllib.request.Request(
                            self.publish_url,
                            data=data_bytes,
                            headers={"Content-Type": "application/json", "User-Agent": "SageAI-Collab/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=4) as resp:
                            pass
                except Exception as e:
                    if self.is_connected and self.on_log:
                        self.on_log(f"Cloud relay publish error: {e}")

        if session:
            try:
                session.close()
            except Exception:
                pass

    def _listen_worker(self):
        """Connects to the cloud relay WebSocket and streams incoming messages."""
        try:
            with ws_sync_connect(self.ws_url, open_timeout=6, close_timeout=2) as ws:
                self._ws_client = ws
                self._connected_event.set()
                if self.on_log:
                    self.on_log(f"Connected to Worldwide Cloud Relay (Room {self.room_code})")

                for raw in ws:
                    if not self.is_connected:
                        break
                    try:
                        pkt = json.loads(raw)
                    except Exception:
                        continue

                    if pkt.get("event") == "message":
                        msg_str = pkt.get("message", "")
                        self._process_incoming(msg_str)
        except Exception as e:
            if self.is_connected and self.on_log:
                self.on_log(f"Cloud relay disconnected: {e}")
        finally:
            self._connected_event.set()
            if self.is_connected:
                self.disconnect()

    def _process_incoming(self, raw_str: str):
        """Processes and dispatches incoming envelopes from other peers in the room."""
        try:
            envelope = json.loads(raw_str)
        except Exception:
            return

        # Ignore own echo packets
        if envelope.get("sender_id") == self.my_id:
            return

        msg = envelope.get("message")
        if not isinstance(msg, dict):
            return

        msg_type = msg.get("type")
        sender_id = envelope.get("sender_id", "")
        sender_name = envelope.get("sender_name", "Peer")

        if msg_type == "join":
            with self._lock:
                self.peer_names[sender_id] = sender_name

            if self.role == "host":
                # Send authoritative welcome packet back to room
                with self._lock:
                    docs_snapshot = {k: dict(v) for k, v in self.documents.items()}
                    wb_snapshot = list(self.whiteboard_strokes)
                    peers_list = list(self.peer_names.values())
                    peer_files = dict(self.peer_active_files)

                welcome_msg = {
                    "type": "joined",
                    "host_name": self.user_name,
                    "target_peer_id": sender_id,
                    "files": docs_snapshot,
                    "whiteboard_strokes": wb_snapshot,
                    "peers": peers_list,
                    "peer_active_files": peer_files,
                }
                self.send_message(welcome_msg)

            if self.on_peer_joined:
                self.on_peer_joined(sender_name, sender_id)

        elif msg_type == "joined":
            # Handshake snapshot received by client
            target_id = msg.get("target_peer_id")
            if target_id and target_id != self.my_id:
                return  # welcome was for someone else

            if self.role == "client" and self.on_joined:
                self.on_joined(msg)

        elif msg_type == "edit":
            filename = msg.get("filename", "untitled.py")
            content = msg.get("content", "")
            with self._lock:
                if filename in self.documents:
                    self.documents[filename]["content"] = content
                    self.documents[filename]["version"] = msg.get("version", self.documents[filename]["version"] + 1)
                else:
                    self.documents[filename] = {
                        "filename": filename,
                        "language": msg.get("language", "Python"),
                        "content": content,
                        "version": msg.get("version", 1),
                    }
            if self.on_edit_received:
                self.on_edit_received(msg)

        elif msg_type in ("file_add", "file_import"):
            filename = msg.get("filename")
            if filename:
                with self._lock:
                    self.documents[filename] = {
                        "filename": filename,
                        "language": msg.get("language", "Python"),
                        "content": msg.get("content", ""),
                        "version": msg.get("version", 1),
                    }
                if self.on_file_added:
                    self.on_file_added(msg)

        elif msg_type == "file_focus":
            filename = msg.get("filename", "")
            with self._lock:
                self.peer_active_files[sender_id] = filename
            if self.on_peer_focus:
                self.on_peer_focus(msg)

        elif msg_type == "wb_stroke":
            stroke = msg.get("stroke")
            if stroke:
                with self._lock:
                    self.whiteboard_strokes.append(stroke)
                if self.on_wb_stroke:
                    self.on_wb_stroke(stroke)

        elif msg_type == "wb_clear":
            with self._lock:
                self.whiteboard_strokes.clear()
            if self.on_wb_clear:
                self.on_wb_clear(msg.get("peer_name", sender_name))

        elif msg_type == "wb_undo":
            with self._lock:
                if self.whiteboard_strokes:
                    self.whiteboard_strokes.pop()
            if self.on_wb_undo:
                self.on_wb_undo(msg.get("peer_name", sender_name))

        elif msg_type == "peer_left":
            with self._lock:
                self.peer_names.pop(sender_id, None)
                self.peer_active_files.pop(sender_id, None)
            if self.on_peer_left:
                self.on_peer_left(msg.get("peer_name", sender_name))

    def disconnect(self):
        """Disconnects cleanly from the cloud relay without freezing."""
        if not self.is_connected:
            return
        self.is_connected = False

        try:
            self.send_message({"type": "peer_left", "peer_name": self.user_name})
        except Exception:
            pass

        if self._ws_client:
            try:
                self._ws_client.close()
            except Exception:
                pass
            self._ws_client = None

        if self.on_disconnected:
            try:
                self.on_disconnected("Disconnected from Cloud Relay.")
            except Exception:
                pass


class CollabManager(QObject):
    """
    Unified High-Level Controller for Real-Time Multi-File Collaboration & Whiteboard.
    Exposes thread-safe Qt signals for GUI consumption.
    """

    # Signals
    connected = Signal(str, str)            # (peer_or_host_name, role)
    disconnected = Signal(str)               # reason
    session_synced = Signal(dict)           # initial full session state with all files & whiteboard
    doc_sync_received = Signal(dict)         # backward compatible single doc / initial doc
    file_added = Signal(dict)                # new shared file added to session
    edit_received = Signal(dict)             # real-time typing edit payload with filename
    peer_focus_changed = Signal(str, str)    # (peer_name, filename)
    peer_joined = Signal(str, str)           # (peer_name, peer_id)
    peer_left = Signal(str)                  # peer_name
    peer_list_updated = Signal(list)         # list of peer names
    files_list_updated = Signal(list)        # list of all filenames in session
    status_changed = Signal(str, bool)       # (status_text, is_active)
    log_emitted = Signal(str)                # log message

    # Whiteboard Signals
    wb_stroke_received = Signal(dict)       # stroke dict
    wb_cleared = Signal(str)                # peer_name who cleared
    wb_undo_received = Signal(str)          # peer_name who undid
    wb_history_synced = Signal(list)        # list of strokes on connect

    def __init__(self, parent=None):
        super().__init__(parent)
        self.role: Optional[str] = None  # 'host' or 'client'
        self.connection_mode: str = "lan"  # "lan" or "cloud"
        self.server: Optional[CollabServer] = None
        self.client: Optional[CollabClient] = None
        self.cloud_relay: Optional[CollabCloudRelay] = None
        self.room_code: str = ""
        self.my_name: str = "Developer"
        self.my_id: str = str(uuid.uuid4())[:8]
        self.active_peers: List[str] = []
        self.shared_files: Dict[str, dict] = {}   # filename -> {filename, language, content, version}
        self.peer_focus: Dict[str, str] = {}     # peer_name -> filename
        self.whiteboard_strokes: List[dict] = []  # strokes history
        self._doc_version: int = 0
        self._is_stopping: bool = False
        self._lock = threading.RLock()

    @property
    def is_active(self) -> bool:
        if self.connection_mode == "cloud" and self.cloud_relay and self.cloud_relay.is_connected:
            return True
        if self.role == "host" and self.server and self.server.is_running:
            return True
        if self.role == "client" and self.client and self.client.is_connected:
            return True
        return False

    @property
    def port(self) -> int:
        """Returns the active TCP port of the host or client."""
        if self.role == "host" and self.server:
            return self.server.port
        if self.role == "client" and self.client:
            return self.client.port
        return 0

    def start_hosting(
        self,
        port: int = 8989,
        host_name: str = "Host",
        initial_doc: Optional[dict] = None,
        initial_files: Optional[Dict[str, dict]] = None,
        user_name: Optional[str] = None
    ) -> bool:
        """Starts hosting a local LAN collaborative session with multi-file and whiteboard support."""
        self.stop()
        effective_name = user_name or host_name
        with self._lock:
            self.connection_mode = "lan"
            self.role = "host"
            self.my_name = effective_name
            self.server = CollabServer(port=port, host_name=effective_name)
            self.shared_files.clear()
            self.peer_focus.clear()
            self.whiteboard_strokes.clear()

            # Seed initial files
            if initial_files:
                for f_name, f_data in initial_files.items():
                    doc = self.server.add_document(
                        filename=f_name,
                        language=f_data.get("language", "Python"),
                        content=f_data.get("content", "")
                    )
                    self.shared_files[f_name] = doc
            elif initial_doc:
                f_name = initial_doc.get("filename", "untitled.py")
                doc = self.server.add_document(
                    filename=f_name,
                    language=initial_doc.get("language", "Python"),
                    content=initial_doc.get("content", "")
                )
                self.shared_files[f_name] = doc

            self.server.on_peer_joined = self._on_server_peer_joined
            self.server.on_peer_left = self._on_server_peer_left
            self.server.on_edit_received = self._on_server_edit_received
            self.server.on_file_added = self._on_server_file_added
            self.server.on_peer_focus = self._on_server_peer_focus
            self.server.on_wb_stroke = self._on_server_wb_stroke
            self.server.on_wb_clear = self._on_server_wb_clear
            self.server.on_wb_undo = self._on_server_wb_undo
            self.server.on_log = lambda msg: self.log_emitted.emit(msg)

        if self.server.start():
            local_ip = get_local_ip()
            active_port = self.server.port
            self.room_code = f"{local_ip}:{active_port}"
            self.active_peers = [f"{self.my_name} (Host)"]
            self.status_changed.emit(f"Hosting LAN at {local_ip}:{active_port}", True)
            self.connected.emit(self.my_name, "host")
            self.peer_list_updated.emit(self.active_peers)
            self.files_list_updated.emit(list(self.shared_files.keys()))
            self.log_emitted.emit(f"✓ Collaboration Host active at {local_ip}:{active_port}")
            return True
        else:
            with self._lock:
                self.role = None
                self.server = None
            self.status_changed.emit("Failed to host", False)
            return False

    def start_hosting_cloud(
        self,
        room_code: Optional[str] = None,
        host_name: str = "Host",
        initial_doc: Optional[dict] = None,
        initial_files: Optional[Dict[str, dict]] = None,
        user_name: Optional[str] = None
    ) -> str:
        """
        Starts hosting a Worldwide Cloud Relay session.
        Participants on different Wi-Fi networks can connect using just the Room Code!
        """
        self.stop()
        effective_name = user_name or host_name
        effective_code = (room_code or generate_room_code()).strip().upper()
        if not effective_code.startswith("SAGE-") and len(effective_code) <= 8 and "-" not in effective_code:
            effective_code = f"SAGE-{effective_code}"

        with self._lock:
            self.connection_mode = "cloud"
            self.role = "host"
            self.my_name = effective_name
            self.room_code = effective_code
            self.shared_files.clear()
            self.peer_focus.clear()
            self.whiteboard_strokes.clear()

            self.cloud_relay = CollabCloudRelay(
                room_code=effective_code,
                user_name=effective_name,
                role="host"
            )

            # Seed initial files
            if initial_files:
                for f_name, f_data in initial_files.items():
                    doc = {
                        "filename": f_name,
                        "language": f_data.get("language", "Python"),
                        "content": f_data.get("content", ""),
                        "version": 1
                    }
                    self.cloud_relay.documents[f_name] = doc
                    self.shared_files[f_name] = doc
            elif initial_doc:
                f_name = initial_doc.get("filename", "untitled.py")
                doc = {
                    "filename": f_name,
                    "language": initial_doc.get("language", "Python"),
                    "content": initial_doc.get("content", ""),
                    "version": 1
                }
                self.cloud_relay.documents[f_name] = doc
                self.shared_files[f_name] = doc

            self.cloud_relay.on_joined = self._on_client_joined
            self.cloud_relay.on_edit_received = self._on_client_edit_received
            self.cloud_relay.on_file_added = self._on_client_file_added
            self.cloud_relay.on_peer_focus = self._on_client_peer_focus
            self.cloud_relay.on_wb_stroke = self._on_client_wb_stroke
            self.cloud_relay.on_wb_clear = self._on_client_wb_clear
            self.cloud_relay.on_wb_undo = self._on_client_wb_undo
            self.cloud_relay.on_peer_joined = self._on_server_peer_joined
            self.cloud_relay.on_peer_left = self._on_server_peer_left
            self.cloud_relay.on_disconnected = self._on_client_disconnected
            self.cloud_relay.on_log = lambda msg: self.log_emitted.emit(msg)

        if self.cloud_relay.start():
            self.active_peers = [f"{self.my_name} (Host)"]
            self.status_changed.emit(f"Hosting Worldwide: {effective_code}", True)
            self.connected.emit(self.my_name, "host")
            self.peer_list_updated.emit(self.active_peers)
            self.files_list_updated.emit(list(self.shared_files.keys()))
            self.log_emitted.emit(f"✓ Worldwide Cloud Relay Active • Room Code: {effective_code}")
            return effective_code
        else:
            with self._lock:
                self.role = None
                self.cloud_relay = None
            self.status_changed.emit("Cloud hosting failed", False)
            return ""

    def join_session(self, host: str, port: int, user_name: str = "Peer") -> bool:
        """Joins an existing LAN collaborative session."""
        self.stop()
        with self._lock:
            self.connection_mode = "lan"
            self.role = "client"
            self.my_name = user_name
            self.room_code = f"{host}:{port}"
            self.shared_files.clear()
            self.peer_focus.clear()
            self.whiteboard_strokes.clear()
            self.client = CollabClient(host=host, port=port, user_name=user_name)
            self.client.on_joined = self._on_client_joined
            self.client.on_edit_received = self._on_client_edit_received
            self.client.on_file_added = self._on_client_file_added
            self.client.on_peer_focus = self._on_client_peer_focus
            self.client.on_wb_stroke = self._on_client_wb_stroke
            self.client.on_wb_clear = self._on_client_wb_clear
            self.client.on_wb_undo = self._on_client_wb_undo
            self.client.on_peer_joined = self._on_client_peer_joined
            self.client.on_peer_left = self._on_client_peer_left
            self.client.on_disconnected = self._on_client_disconnected
            self.client.on_log = lambda msg: self.log_emitted.emit(msg)

        self.status_changed.emit(f"Connecting to {host}:{port}...", False)
        if self.client.connect():
            return True
        else:
            with self._lock:
                self.role = None
                self.client = None
            self.status_changed.emit("Connection failed", False)
            return False

    def join_session_cloud(self, room_code: str, user_name: str = "Developer") -> bool:
        """
        Joins an existing Worldwide Cloud Relay session by Room Code.
        Works across different networks and internet connections.
        """
        self.stop()
        effective_code = room_code.strip().upper()
        if not effective_code.startswith("SAGE-") and len(effective_code) <= 8 and "-" not in effective_code:
            effective_code = f"SAGE-{effective_code}"

        with self._lock:
            self.connection_mode = "cloud"
            self.role = "client"
            self.my_name = user_name
            self.room_code = effective_code
            self.shared_files.clear()
            self.peer_focus.clear()
            self.whiteboard_strokes.clear()

            self.cloud_relay = CollabCloudRelay(
                room_code=effective_code,
                user_name=user_name,
                role="client"
            )
            self.cloud_relay.on_joined = self._on_client_joined
            self.cloud_relay.on_edit_received = self._on_client_edit_received
            self.cloud_relay.on_file_added = self._on_client_file_added
            self.cloud_relay.on_peer_focus = self._on_client_peer_focus
            self.cloud_relay.on_wb_stroke = self._on_client_wb_stroke
            self.cloud_relay.on_wb_clear = self._on_client_wb_clear
            self.cloud_relay.on_wb_undo = self._on_client_wb_undo
            self.cloud_relay.on_peer_joined = self._on_client_peer_joined
            self.cloud_relay.on_peer_left = self._on_client_peer_left
            self.cloud_relay.on_disconnected = self._on_client_disconnected
            self.cloud_relay.on_log = lambda msg: self.log_emitted.emit(msg)

        self.status_changed.emit(f"Connecting to Cloud Room {effective_code}...", False)
        if self.cloud_relay.start():
            self.log_emitted.emit(f"✓ Connected to Cloud Room {effective_code}")
            return True
        else:
            with self._lock:
                self.role = None
                self.cloud_relay = None
            self.status_changed.emit("Cloud connection failed", False)
            return False

    def stop(self):
        """Stops hosting or disconnects cleanly with zero crashes."""
        with self._lock:
            if self._is_stopping:
                return
            self._is_stopping = True

            server_to_stop = self.server
            client_to_stop = self.client
            relay_to_stop = self.cloud_relay
            self.server = None
            self.client = None
            self.cloud_relay = None
            self.room_code = ""
            was_active = self.role is not None
            self.role = None
            self.active_peers.clear()
            self.shared_files.clear()
            self.peer_focus.clear()
            self.whiteboard_strokes.clear()

        if server_to_stop:
            server_to_stop.stop()
        if client_to_stop:
            client_to_stop.disconnect()
        if relay_to_stop:
            relay_to_stop.disconnect()

        self.peer_list_updated.emit([])
        self.files_list_updated.emit([])
        self.status_changed.emit("Offline", False)
        if was_active:
            self.disconnected.emit("Collaboration session closed.")

        with self._lock:
            self._is_stopping = False

    def stop_session(self):
        """Convenience alias for stop()."""
        self.stop()

    def leave_session(self):
        """Convenience alias for stop()."""
        self.stop()

    def broadcast_local_edit(self, content: str, cursor_pos: int = 0, filename: Optional[str] = None):
        """Called by local CodeEditor when user types code in a specific file."""
        if not self.is_active:
            return

        target_file = filename or (self.server.active_file if self.role == "host" and self.server else "untitled.py")
        self._doc_version += 1
        msg = {
            "type": "edit",
            "filename": target_file,
            "content": content,
            "cursor_pos": cursor_pos,
            "peer_id": self.my_id,
            "peer_name": self.my_name,
            "version": self._doc_version,
            "timestamp": time.time()
        }

        with self._lock:
            if target_file in self.shared_files:
                self.shared_files[target_file]["content"] = content
                self.shared_files[target_file]["version"] = self._doc_version

        if self.connection_mode == "cloud" and self.cloud_relay:
            self.cloud_relay.send_message(msg)
        elif self.role == "host" and self.server:
            lang = self.shared_files.get(target_file, {}).get("language", "Python")
            self.server.add_document(target_file, lang, content)
            self.server.broadcast_message(msg)
        elif self.role == "client" and self.client:
            self.client.send_message(msg)

    def broadcast_file_add(self, filename: str, language: str, content: str):
        """Adds a file to the shared collaborative session so all peers see it."""
        if not self.is_active:
            return

        self._doc_version += 1
        msg = {
            "type": "file_add",
            "filename": filename,
            "language": language,
            "content": content,
            "peer_id": self.my_id,
            "peer_name": self.my_name,
            "version": self._doc_version,
            "timestamp": time.time()
        }

        with self._lock:
            self.shared_files[filename] = {
                "filename": filename,
                "language": language,
                "content": content,
                "version": self._doc_version,
            }

        if self.connection_mode == "cloud" and self.cloud_relay:
            self.cloud_relay.send_message(msg)
        elif self.role == "host" and self.server:
            self.server.add_document(filename, language, content)
            self.server.broadcast_message(msg)
        elif self.role == "client" and self.client:
            self.client.send_message(msg)

        self.files_list_updated.emit(list(self.shared_files.keys()))
        self.file_added.emit(msg)

    def broadcast_file_focus(self, filename: str):
        """Broadcasts which file this peer is currently viewing/editing."""
        if not self.is_active:
            return

        msg = {
            "type": "file_focus",
            "filename": filename,
            "peer_id": self.my_id,
            "peer_name": self.my_name,
            "timestamp": time.time()
        }

        with self._lock:
            self.peer_focus[self.my_name] = filename

        if self.connection_mode == "cloud" and self.cloud_relay:
            self.cloud_relay.send_message(msg)
        elif self.role == "host" and self.server:
            self.server.set_peer_active_file(self.my_id, filename)
            self.server.broadcast_message(msg)
        elif self.role == "client" and self.client:
            self.client.send_message(msg)

        self.peer_focus_changed.emit(self.my_name, filename)

    # --- Whiteboard Broadcast Methods ---

    def broadcast_wb_stroke(self, stroke: dict):
        """Broadcasts a newly drawn stroke to all peers in the session."""
        if not self.is_active:
            return

        msg = {
            "type": "wb_stroke",
            "stroke": stroke,
            "peer_id": self.my_id,
            "peer_name": self.my_name,
            "timestamp": time.time()
        }

        with self._lock:
            self.whiteboard_strokes.append(stroke)

        if self.connection_mode == "cloud" and self.cloud_relay:
            self.cloud_relay.send_message(msg)
        elif self.role == "host" and self.server:
            with self.server._lock:
                self.server.whiteboard_strokes.append(stroke)
            self.server.broadcast_message(msg)
        elif self.role == "client" and self.client:
            self.client.send_message(msg)

    def broadcast_wb_clear(self):
        """Broadcasts a whiteboard clear command to all peers."""
        if not self.is_active:
            return

        msg = {
            "type": "wb_clear",
            "peer_id": self.my_id,
            "peer_name": self.my_name,
            "timestamp": time.time()
        }

        with self._lock:
            self.whiteboard_strokes.clear()

        if self.connection_mode == "cloud" and self.cloud_relay:
            self.cloud_relay.send_message(msg)
        elif self.role == "host" and self.server:
            with self.server._lock:
                self.server.whiteboard_strokes.clear()
            self.server.broadcast_message(msg)
        elif self.role == "client" and self.client:
            self.client.send_message(msg)

        self.wb_cleared.emit(self.my_name)

    def broadcast_wb_undo(self):
        """Broadcasts a whiteboard undo command to all peers."""
        if not self.is_active:
            return

        msg = {
            "type": "wb_undo",
            "peer_id": self.my_id,
            "peer_name": self.my_name,
            "timestamp": time.time()
        }

        with self._lock:
            if self.whiteboard_strokes:
                self.whiteboard_strokes.pop()

        if self.connection_mode == "cloud" and self.cloud_relay:
            self.cloud_relay.send_message(msg)
        elif self.role == "host" and self.server:
            with self.server._lock:
                if self.server.whiteboard_strokes:
                    self.server.whiteboard_strokes.pop()
            self.server.broadcast_message(msg)
        elif self.role == "client" and self.client:
            self.client.send_message(msg)

        self.wb_undo_received.emit(self.my_name)

    # --- Internal Server Callbacks ---
    def _on_server_peer_joined(self, name: str, pid: str):
        if self.connection_mode == "cloud" and self.cloud_relay:
            self.active_peers = list(self.cloud_relay.peer_names.values())
        elif self.server:
            self.active_peers = self.server.get_peer_names()
        else:
            self.active_peers = [self.my_name]

        self.peer_joined.emit(name, pid)
        self.peer_list_updated.emit(self.active_peers)
        self.log_emitted.emit(f"👋 Peer '{name}' joined the session.")

    def _on_server_peer_left(self, name: str):
        if self.connection_mode == "cloud" and self.cloud_relay:
            self.active_peers = list(self.cloud_relay.peer_names.values())
        elif self.server:
            self.active_peers = self.server.get_peer_names()
        else:
            self.active_peers = [self.my_name]

        self.peer_left.emit(name)
        self.peer_list_updated.emit(self.active_peers)
        self.log_emitted.emit(f"🚪 Peer '{name}' left the session.")

    def _on_server_edit_received(self, msg: dict):
        filename = msg.get("filename", "")
        with self._lock:
            if filename and filename in self.shared_files:
                self.shared_files[filename]["content"] = msg.get("content", "")
        self.edit_received.emit(msg)

    def _on_server_file_added(self, msg: dict):
        filename = msg.get("filename")
        if filename:
            with self._lock:
                self.shared_files[filename] = {
                    "filename": filename,
                    "language": msg.get("language", "Python"),
                    "content": msg.get("content", ""),
                    "version": msg.get("version", 1),
                }
            self.files_list_updated.emit(list(self.shared_files.keys()))
            self.file_added.emit(msg)

    def _on_server_peer_focus(self, msg: dict):
        peer_name = msg.get("peer_name", "Peer")
        filename = msg.get("filename", "")
        with self._lock:
            self.peer_focus[peer_name] = filename
        self.peer_focus_changed.emit(peer_name, filename)

    def _on_server_wb_stroke(self, stroke: dict):
        with self._lock:
            self.whiteboard_strokes.append(stroke)
        self.wb_stroke_received.emit(stroke)

    def _on_server_wb_clear(self, peer_name: str):
        with self._lock:
            self.whiteboard_strokes.clear()
        self.wb_cleared.emit(peer_name)

    def _on_server_wb_undo(self, peer_name: str):
        with self._lock:
            if self.whiteboard_strokes:
                self.whiteboard_strokes.pop()
        self.wb_undo_received.emit(peer_name)

    # --- Internal Client Callbacks ---
    def _on_client_joined(self, msg: dict):
        host_name = msg.get("host_name", "Host")
        peers = msg.get("peers", [host_name, self.my_name])
        self.active_peers = peers

        files = msg.get("files", {})
        wb_strokes = msg.get("whiteboard_strokes", [])
        with self._lock:
            self.shared_files = {k: dict(v) for k, v in files.items()}
            self.whiteboard_strokes = list(wb_strokes)

        self.connected.emit(host_name, "client")
        self.status_changed.emit(f"Connected to {host_name}", True)
        self.peer_list_updated.emit(self.active_peers)
        self.files_list_updated.emit(list(self.shared_files.keys()))
        self.session_synced.emit(msg)
        self.wb_history_synced.emit(self.whiteboard_strokes)

        doc = msg.get("doc")
        if doc:
            self.doc_sync_received.emit(doc)

        self.log_emitted.emit(f"✓ Connected to host '{host_name}' successfully ({len(self.shared_files)} shared files, {len(self.whiteboard_strokes)} whiteboard elements synced).")

    def _on_client_edit_received(self, msg: dict):
        if msg.get("peer_id") == self.my_id:
            return

        filename = msg.get("filename", "")
        with self._lock:
            if filename and filename in self.shared_files:
                self.shared_files[filename]["content"] = msg.get("content", "")

        self.edit_received.emit(msg)

    def _on_client_file_added(self, msg: dict):
        filename = msg.get("filename")
        if filename:
            with self._lock:
                self.shared_files[filename] = {
                    "filename": filename,
                    "language": msg.get("language", "Python"),
                    "content": msg.get("content", ""),
                    "version": msg.get("version", 1),
                }
            self.files_list_updated.emit(list(self.shared_files.keys()))
            self.file_added.emit(msg)

    def _on_client_peer_focus(self, msg: dict):
        peer_name = msg.get("peer_name", "Peer")
        filename = msg.get("filename", "")
        with self._lock:
            self.peer_focus[peer_name] = filename
        self.peer_focus_changed.emit(peer_name, filename)

    def _on_client_wb_stroke(self, stroke: dict):
        with self._lock:
            self.whiteboard_strokes.append(stroke)
        self.wb_stroke_received.emit(stroke)

    def _on_client_wb_clear(self, peer_name: str):
        with self._lock:
            self.whiteboard_strokes.clear()
        self.wb_cleared.emit(peer_name)

    def _on_client_wb_undo(self, peer_name: str):
        with self._lock:
            if self.whiteboard_strokes:
                self.whiteboard_strokes.pop()
        self.wb_undo_received.emit(peer_name)

    def _on_client_peer_joined(self, name: str, pid: str):
        if name not in self.active_peers:
            self.active_peers.append(name)
        self.peer_joined.emit(name, pid)
        self.peer_list_updated.emit(self.active_peers)
        self.log_emitted.emit(f"👋 Peer '{name}' joined the session.")

    def _on_client_peer_left(self, name: str):
        if name in self.active_peers:
            self.active_peers.remove(name)
        self.peer_left.emit(name)
        self.peer_list_updated.emit(self.active_peers)
        self.log_emitted.emit(f"🚪 Peer '{name}' left the session.")

    def _on_client_disconnected(self, reason: str):
        with self._lock:
            self.role = None
            self.active_peers.clear()
            self.shared_files.clear()
            self.peer_focus.clear()
            self.whiteboard_strokes.clear()

        self.peer_list_updated.emit([])
        self.files_list_updated.emit([])
        self.status_changed.emit("Disconnected", False)
        self.disconnected.emit(reason)
        self.log_emitted.emit(f"⚠️ {reason}")
