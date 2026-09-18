"""
Role-Based Permissions for SAGE Collaborative IDE.

Implements an access control system for collaborative workspaces:
    - Three roles: Owner, Editor, Viewer
    - File-level locking by Owner
    - Workspace join approval flow
    - Permission enforcement for edit/run/save operations
"""

import time
import logging
from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class Role(Enum):
    """Workspace roles with ascending privilege levels."""
    VIEWER = "viewer"      # Read-only: sees live changes, cursors, but cannot edit
    EDITOR = "editor"      # Can edit unlocked files, run code, save
    OWNER = "owner"        # Full control: lock files, change roles, kick, approve joins


class Permission(Enum):
    """Granular permissions checked by the system."""
    EDIT_FILE = "edit_file"
    SAVE_FILE = "save_file"
    RUN_CODE = "run_code"
    CREATE_FILE = "create_file"
    DELETE_FILE = "delete_file"
    RENAME_FILE = "rename_file"
    LOCK_FILE = "lock_file"
    CHANGE_ROLE = "change_role"
    KICK_PEER = "kick_peer"
    APPROVE_JOIN = "approve_join"
    USE_TERMINAL = "use_terminal"
    ADD_COMMENT = "add_comment"
    SEND_CHAT = "send_chat"


# Role → set of allowed permissions
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.ADD_COMMENT,
        Permission.SEND_CHAT,
    },
    Role.EDITOR: {
        Permission.EDIT_FILE,
        Permission.SAVE_FILE,
        Permission.RUN_CODE,
        Permission.CREATE_FILE,
        Permission.DELETE_FILE,
        Permission.RENAME_FILE,
        Permission.USE_TERMINAL,
        Permission.ADD_COMMENT,
        Permission.SEND_CHAT,
    },
    Role.OWNER: {
        Permission.EDIT_FILE,
        Permission.SAVE_FILE,
        Permission.RUN_CODE,
        Permission.CREATE_FILE,
        Permission.DELETE_FILE,
        Permission.RENAME_FILE,
        Permission.LOCK_FILE,
        Permission.CHANGE_ROLE,
        Permission.KICK_PEER,
        Permission.APPROVE_JOIN,
        Permission.USE_TERMINAL,
        Permission.ADD_COMMENT,
        Permission.SEND_CHAT,
    },
}


@dataclass
class PeerPermission:
    """Tracks a peer's role and permissions state."""
    peer_id: str
    peer_name: str
    role: Role = Role.EDITOR
    joined_at: float = 0.0
    approved: bool = True  # False = pending approval

    def has_permission(self, perm: Permission) -> bool:
        """Checks if this peer has a specific permission."""
        if not self.approved:
            return False
        return perm in ROLE_PERMISSIONS.get(self.role, set())

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "peer_name": self.peer_name,
            "role": self.role.value,
            "joined_at": self.joined_at,
            "approved": self.approved,
        }


class CollabPermissions:
    """
    Manages workspace-level permissions for all peers.
    
    The Owner creates the workspace session. New peers join with a
    configurable default role (Editor by default). The Owner can:
    - Change any peer's role
    - Lock specific files (read-only for Editors)
    - Kick peers
    - Enable/disable join approval requirement
    """

    def __init__(self, owner_id: str, owner_name: str = "Host"):
        self._peers: Dict[str, PeerPermission] = {}
        self._locked_files: Set[str] = set()
        self._require_approval: bool = False
        self._default_role: Role = Role.EDITOR
        self._owner_id = owner_id
        
        # Register owner
        self._peers[owner_id] = PeerPermission(
            peer_id=owner_id,
            peer_name=owner_name,
            role=Role.OWNER,
            joined_at=time.time(),
            approved=True,
        )

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def add_peer(self, peer_id: str, peer_name: str) -> PeerPermission:
        """Registers a new peer with the default role."""
        peer = PeerPermission(
            peer_id=peer_id,
            peer_name=peer_name,
            role=self._default_role,
            joined_at=time.time(),
            approved=not self._require_approval,
        )
        self._peers[peer_id] = peer
        return peer

    def remove_peer(self, peer_id: str):
        """Removes a peer from the workspace."""
        if peer_id != self._owner_id:
            self._peers.pop(peer_id, None)

    def get_peer(self, peer_id: str) -> Optional[PeerPermission]:
        return self._peers.get(peer_id)

    def get_all_peers(self) -> List[PeerPermission]:
        return list(self._peers.values())

    def get_pending_peers(self) -> List[PeerPermission]:
        return [p for p in self._peers.values() if not p.approved]

    def approve_peer(self, peer_id: str, approver_id: str) -> bool:
        """Approves a pending peer. Only the Owner can approve."""
        approver = self._peers.get(approver_id)
        if not approver or approver.role != Role.OWNER:
            return False
        
        peer = self._peers.get(peer_id)
        if peer:
            peer.approved = True
            return True
        return False

    def reject_peer(self, peer_id: str, rejector_id: str) -> bool:
        """Rejects a pending peer. Only the Owner can reject."""
        rejector = self._peers.get(rejector_id)
        if not rejector or rejector.role != Role.OWNER:
            return False
        
        self._peers.pop(peer_id, None)
        return True

    def change_role(self, peer_id: str, new_role: Role, changer_id: str) -> bool:
        """
        Changes a peer's role. Only the Owner can do this.
        Cannot change the Owner's own role.
        """
        changer = self._peers.get(changer_id)
        if not changer or changer.role != Role.OWNER:
            return False
        
        if peer_id == self._owner_id:
            return False  # Can't change owner's role
        
        peer = self._peers.get(peer_id)
        if peer:
            peer.role = new_role
            return True
        return False

    def check_permission(self, peer_id: str, perm: Permission) -> bool:
        """Checks if a peer has a specific permission."""
        peer = self._peers.get(peer_id)
        if not peer:
            return False
        return peer.has_permission(perm)

    def can_edit_file(self, peer_id: str, file_path: str) -> bool:
        """Checks if a peer can edit a specific file."""
        peer = self._peers.get(peer_id)
        if not peer or not peer.approved:
            return False
        
        if not peer.has_permission(Permission.EDIT_FILE):
            return False
        
        # Check file lock (owners can always edit locked files)
        if file_path in self._locked_files and peer.role != Role.OWNER:
            return False
        
        return True

    def lock_file(self, file_path: str, locker_id: str) -> bool:
        """Locks a file (Owner only). Locked files are read-only for Editors."""
        if not self.check_permission(locker_id, Permission.LOCK_FILE):
            return False
        self._locked_files.add(file_path)
        return True

    def unlock_file(self, file_path: str, unlocker_id: str) -> bool:
        """Unlocks a file (Owner only)."""
        if not self.check_permission(unlocker_id, Permission.LOCK_FILE):
            return False
        self._locked_files.discard(file_path)
        return True

    def is_file_locked(self, file_path: str) -> bool:
        return file_path in self._locked_files

    def get_locked_files(self) -> Set[str]:
        return set(self._locked_files)

    def set_require_approval(self, require: bool, setter_id: str) -> bool:
        """Sets whether new joins require Owner approval."""
        if not self.check_permission(setter_id, Permission.APPROVE_JOIN):
            return False
        self._require_approval = require
        return True

    def set_default_role(self, role: Role, setter_id: str) -> bool:
        """Sets the default role for new joiners."""
        setter = self._peers.get(setter_id)
        if not setter or setter.role != Role.OWNER:
            return False
        if role == Role.OWNER:
            return False  # Can't set default to Owner
        self._default_role = role
        return True
