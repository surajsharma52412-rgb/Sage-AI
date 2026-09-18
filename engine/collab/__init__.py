"""
SAGE Collaborative IDE Engine — CRDT-Powered Real-Time Collaboration.

This package provides the core infrastructure for conflict-free multi-user
real-time collaborative editing, replacing the legacy "last write wins"
approach with CRDTs (Conflict-Free Replicated Data Types).

Components:
    - CRDTDocument:    Pure-Python RGA text CRDT with per-user undo
    - CRDTSyncServer:  WebSocket server managing workspace sync
    - CRDTSyncClient:  WebSocket client with offline queue + reconnect
    - WorkspaceWatcher: Filesystem monitoring for folder-level auto-share
    - CollabPersistence: SQLite-backed save/version history
    - CollabExecutor:   Shared code execution service
    - CollabPermissions: Owner/Editor/Viewer role enforcement
    - CollabComments:   Inline comments + session chat
    - SharedTerminal:   Shared PTY terminal sessions
"""

from engine.collab.crdt_document import CRDTDocument, CRDTOp, OpType

__all__ = [
    "CRDTDocument",
    "CRDTOp",
    "OpType",
]
