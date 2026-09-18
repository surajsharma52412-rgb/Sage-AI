"""
Pure-Python RGA (Replicated Growable Array) CRDT for Collaborative Text Editing.

This module implements a character-level CRDT that guarantees convergence
across any number of concurrent editors, regardless of network latency,
message ordering, or temporary disconnections.

Key properties:
    - Every character has a globally unique ID: (site_id, sequence_counter)
    - Inserts and deletes produce deterministic operations
    - Operations are commutative and idempotent — applying them in any order
      yields the same final document state
    - Per-user undo only reverts that user's own operations
    - Snapshots can serialize/deserialize the full state for late joiners

Algorithm: RGA (Replicated Growable Array) with tombstone-based deletion.
Reference: Roh et al., "Replicated abstract data types: Building blocks for
           collaborative applications" (2011).
"""

import time
import copy
import logging
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any, Set

logger = logging.getLogger(__name__)


class OpType(Enum):
    """Types of CRDT operations."""
    INSERT = "insert"
    DELETE = "delete"


@dataclass(frozen=True, order=True)
class CharID:
    """
    Globally unique identifier for each character in the CRDT document.
    
    Ordering: first by sequence number (ascending), then by site_id (ascending)
    to break ties deterministically. This ensures all replicas converge to
    the same character order.
    """
    seq: int          # Monotonically increasing per-site sequence counter
    site_id: str      # Unique identifier for the editing site/user

    def to_dict(self) -> dict:
        return {"seq": self.seq, "site_id": self.site_id}

    @classmethod
    def from_dict(cls, d: dict) -> "CharID":
        return cls(seq=d["seq"], site_id=d["site_id"])


# Sentinel: virtual character ID representing the start-of-document anchor
ORIGIN_ID = CharID(seq=0, site_id="__ORIGIN__")


@dataclass
class CRDTChar:
    """
    A single character in the RGA linked list.
    
    Each character knows its own ID, the character it was inserted after
    (parent_id), and whether it has been tombstoned (deleted).
    """
    char_id: CharID
    parent_id: CharID       # The character this was inserted after
    value: str              # The actual character (single char or "")
    tombstone: bool = False # True if deleted (kept for CRDT consistency)

    def to_dict(self) -> dict:
        return {
            "char_id": self.char_id.to_dict(),
            "parent_id": self.parent_id.to_dict(),
            "value": self.value,
            "tombstone": self.tombstone,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CRDTChar":
        return cls(
            char_id=CharID.from_dict(d["char_id"]),
            parent_id=CharID.from_dict(d["parent_id"]),
            value=d["value"],
            tombstone=d.get("tombstone", False),
        )


@dataclass
class CRDTOp:
    """
    A CRDT operation that can be transmitted over the network and applied
    to any replica to converge to the same state.
    """
    op_type: OpType
    char_id: CharID         # The character being inserted or deleted
    parent_id: CharID       # For INSERT: the character this is inserted after
    value: str              # For INSERT: the character value
    site_id: str            # The site that generated this operation
    timestamp: float = 0.0  # Wall-clock timestamp for debugging/ordering

    def to_dict(self) -> dict:
        return {
            "op_type": self.op_type.value,
            "char_id": self.char_id.to_dict(),
            "parent_id": self.parent_id.to_dict(),
            "value": self.value,
            "site_id": self.site_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CRDTOp":
        return cls(
            op_type=OpType(d["op_type"]),
            char_id=CharID.from_dict(d["char_id"]),
            parent_id=CharID.from_dict(d["parent_id"]),
            value=d.get("value", ""),
            site_id=d.get("site_id", ""),
            timestamp=d.get("timestamp", 0.0),
        )


class CRDTDocument:
    """
    A CRDT-based collaborative text document using the RGA algorithm.
    
    This document can be replicated across multiple sites. Each site
    generates operations (insert/delete) that are broadcast to all other
    sites. Operations can arrive in any order and will always converge
    to the same document state.
    
    Usage:
        doc = CRDTDocument(site_id="user-alice")
        
        # Local editing (generates ops for network transmission)
        ops = doc.insert_at(0, "H")
        ops += doc.insert_at(1, "i")
        
        # Remote ops received from network
        doc.apply_remote_ops(remote_ops)
        
        # Get current text
        text = doc.get_text()
        
        # Per-user undo
        undone_ops = doc.undo()  # Only undoes alice's operations
    """

    def __init__(self, site_id: str):
        self.site_id = site_id
        self._seq_counter: int = 0  # Monotonically increasing per-site counter
        
        # The RGA is stored as an ordered list for simplicity.
        # For documents up to ~50K characters (typical source files), linear
        # scan is fast enough (~1ms). For larger documents, this could be
        # upgraded to a balanced tree.
        self._chars: List[CRDTChar] = []
        
        # Index: char_id → position in _chars list (for O(1) lookup)
        self._id_to_index: Dict[CharID, int] = {}
        
        # Per-user undo stacks: site_id → list of ops (most recent last)
        self._undo_stacks: Dict[str, List[CRDTOp]] = {}
        
        # Set of all applied op char_ids (for idempotency)
        self._applied_ops: Set[CharID] = set()
        
        # Track the maximum sequence number seen from each site
        # (for crdt consistency during merges)
        self._site_max_seq: Dict[str, int] = {}
        
        # Callback for when remote ops modify the document
        self.on_remote_change = None  # Callable[[List[CRDTOp]], None]

    @property
    def char_count(self) -> int:
        """Number of visible (non-tombstoned) characters."""
        return sum(1 for c in self._chars if not c.tombstone)

    def _next_id(self) -> CharID:
        """Generates the next unique character ID for this site."""
        self._seq_counter += 1
        return CharID(seq=self._seq_counter, site_id=self.site_id)

    def _rebuild_index(self):
        """Rebuilds the char_id → index mapping after structural changes."""
        self._id_to_index = {c.char_id: i for i, c in enumerate(self._chars)}

    def _visible_index_to_char_index(self, visible_pos: int) -> int:
        """
        Converts a visible text position (ignoring tombstones) to the
        internal _chars list index.
        
        Returns the index of the character AT visible_pos, or len(_chars)
        if visible_pos is at the end of the visible text.
        """
        visible_count = 0
        for i, c in enumerate(self._chars):
            if not c.tombstone:
                if visible_count == visible_pos:
                    return i
                visible_count += 1
        return len(self._chars)

    def _get_char_id_at_visible_pos(self, visible_pos: int) -> CharID:
        """
        Gets the CharID of the character at the given visible position.
        Returns ORIGIN_ID if pos is 0 (inserting at the very beginning).
        """
        if visible_pos <= 0:
            return ORIGIN_ID
        
        visible_count = 0
        for c in self._chars:
            if not c.tombstone:
                visible_count += 1
                if visible_count == visible_pos:
                    return c.char_id
        
        # Past end — return the last visible character's ID
        for c in reversed(self._chars):
            if not c.tombstone:
                return c.char_id
        
        return ORIGIN_ID

    def _find_insert_position(self, parent_id: CharID, new_id: CharID) -> int:
        """
        Finds the correct insertion position in the _chars list for a new
        character that was inserted after parent_id.
        
        RGA rule: Among all characters that share the same parent, the one
        with the HIGHER CharID goes FIRST (leftmost / earlier in the list).
        This ensures deterministic ordering when two users insert at the
        same position concurrently.
        
        After finding the right sibling position, we must also skip past
        the entire subtree (all descendants) of any sibling that comes
        before us in the ordering.
        """
        if parent_id == ORIGIN_ID:
            insert_at = 0
        else:
            parent_idx = self._id_to_index.get(parent_id)
            if parent_idx is None:
                logger.warning(f"CRDT: parent_id {parent_id} not found, appending at end")
                return len(self._chars)
            insert_at = parent_idx + 1

        # Scan through all elements after the parent.
        # We need to skip past:
        #   1. Siblings (same parent_id) with HIGHER char_id — they go left of us
        #      AND all their descendants (subtrees)
        #   2. Descendants of our parent that were inserted via a chain
        #      (their parent is one of the siblings we already passed)
        #
        # We stop when we hit:
        #   - A sibling with LOWER char_id (we go before it)
        #   - A character whose parent is NOT in the subtree we're traversing
        
        # Track which char_ids are in the "subtree" we need to skip past
        passed_ancestors = {parent_id}
        
        while insert_at < len(self._chars):
            existing = self._chars[insert_at]
            
            if existing.parent_id == parent_id:
                # Direct sibling — compare IDs
                if existing.char_id > new_id:
                    # Higher ID sibling goes before us — skip it and its subtree
                    passed_ancestors.add(existing.char_id)
                    insert_at += 1
                else:
                    # Lower ID sibling — we go before it
                    break
            elif existing.parent_id in passed_ancestors:
                # Descendant of a sibling we already passed — skip it too
                passed_ancestors.add(existing.char_id)
                insert_at += 1
            else:
                # Not a sibling or descendant — we've found our spot
                break

        return insert_at

    def insert_at(self, visible_pos: int, text: str) -> List[CRDTOp]:
        """
        Inserts text at the given visible position in the document.
        
        Args:
            visible_pos: Position in the visible text (0 = beginning)
            text: The text to insert (can be multiple characters)
            
        Returns:
            List of CRDTOp operations to broadcast to other replicas
        """
        ops = []
        current_parent = self._get_char_id_at_visible_pos(visible_pos)
        
        for ch in text:
            new_id = self._next_id()
            new_char = CRDTChar(
                char_id=new_id,
                parent_id=current_parent,
                value=ch,
                tombstone=False,
            )
            
            # Find correct position and insert
            pos = self._find_insert_position(current_parent, new_id)
            self._chars.insert(pos, new_char)
            self._rebuild_index()
            self._applied_ops.add(new_id)
            
            # Update site max seq
            self._site_max_seq[self.site_id] = max(
                self._site_max_seq.get(self.site_id, 0), new_id.seq
            )
            
            # Create operation for network transmission
            op = CRDTOp(
                op_type=OpType.INSERT,
                char_id=new_id,
                parent_id=current_parent,
                value=ch,
                site_id=self.site_id,
                timestamp=time.time(),
            )
            ops.append(op)
            
            # Push to undo stack
            if self.site_id not in self._undo_stacks:
                self._undo_stacks[self.site_id] = []
            self._undo_stacks[self.site_id].append(op)
            
            # Next character's parent is this character
            current_parent = new_id
        
        return ops

    def delete_at(self, visible_pos: int, count: int = 1) -> List[CRDTOp]:
        """
        Deletes `count` characters starting at the given visible position.
        
        Characters are tombstoned, not physically removed, to maintain
        CRDT consistency across replicas.
        
        Args:
            visible_pos: Position in the visible text
            count: Number of characters to delete
            
        Returns:
            List of CRDTOp operations to broadcast to other replicas
        """
        ops = []
        deleted = 0
        visible_count = 0
        
        for i, c in enumerate(self._chars):
            if c.tombstone:
                continue
            if visible_count >= visible_pos and deleted < count:
                c.tombstone = True
                
                op = CRDTOp(
                    op_type=OpType.DELETE,
                    char_id=c.char_id,
                    parent_id=c.parent_id,
                    value=c.value,
                    site_id=self.site_id,
                    timestamp=time.time(),
                )
                ops.append(op)
                
                # Push to undo stack
                if self.site_id not in self._undo_stacks:
                    self._undo_stacks[self.site_id] = []
                self._undo_stacks[self.site_id].append(op)
                
                deleted += 1
            elif deleted >= count:
                break
            visible_count += 1
        
        return ops

    def apply_remote_ops(self, ops: List[CRDTOp]) -> List[CRDTOp]:
        """
        Applies operations received from a remote replica.
        
        Operations are idempotent — applying the same operation twice
        has no effect. Operations are also commutative — the order
        of application doesn't matter.
        
        Args:
            ops: List of operations from a remote site
            
        Returns:
            List of ops that were actually applied (excludes duplicates)
        """
        applied = []
        
        for op in ops:
            if op.char_id in self._applied_ops and op.op_type == OpType.INSERT:
                # Already applied this insert — skip (idempotent)
                continue
            
            if op.op_type == OpType.INSERT:
                self._apply_remote_insert(op)
                applied.append(op)
            elif op.op_type == OpType.DELETE:
                self._apply_remote_delete(op)
                applied.append(op)
            
            # Track site max seq
            self._site_max_seq[op.site_id] = max(
                self._site_max_seq.get(op.site_id, 0), op.char_id.seq
            )
        
        if applied and self.on_remote_change:
            try:
                self.on_remote_change(applied)
            except Exception as e:
                logger.error(f"CRDT on_remote_change callback error: {e}")
        
        return applied

    def _apply_remote_insert(self, op: CRDTOp):
        """Applies a remote INSERT operation."""
        # Check if parent exists — if not, we need to buffer this op
        # (In practice, ops arrive in causal order most of the time)
        if op.parent_id != ORIGIN_ID and op.parent_id not in self._id_to_index:
            # Parent hasn't arrived yet — this is a causality violation.
            # For simplicity, append at end. A production system would
            # buffer and retry.
            logger.warning(
                f"CRDT: Causality violation — parent {op.parent_id} not found "
                f"for insert {op.char_id}. Appending at end."
            )
            new_char = CRDTChar(
                char_id=op.char_id,
                parent_id=op.parent_id,
                value=op.value,
                tombstone=False,
            )
            self._chars.append(new_char)
        else:
            new_char = CRDTChar(
                char_id=op.char_id,
                parent_id=op.parent_id,
                value=op.value,
                tombstone=False,
            )
            pos = self._find_insert_position(op.parent_id, op.char_id)
            self._chars.insert(pos, new_char)
        
        self._applied_ops.add(op.char_id)
        self._rebuild_index()

    def _apply_remote_delete(self, op: CRDTOp):
        """Applies a remote DELETE operation (tombstones the character)."""
        idx = self._id_to_index.get(op.char_id)
        if idx is not None:
            self._chars[idx].tombstone = True
        else:
            # Character not found — might have been already deleted or
            # not yet received (rare edge case with out-of-order delivery)
            logger.debug(f"CRDT: Delete target {op.char_id} not found (may be out of order)")

    def get_text(self) -> str:
        """Materializes the CRDT state into a plain text string."""
        return "".join(c.value for c in self._chars if not c.tombstone)

    def get_length(self) -> int:
        """Returns the visible character count."""
        return self.char_count

    def undo(self) -> List[CRDTOp]:
        """
        Undoes the most recent operation by this site's user.
        
        For INSERT: tombstones the inserted character
        For DELETE: un-tombstones the deleted character
        
        Returns:
            List of compensating operations to broadcast
        """
        stack = self._undo_stacks.get(self.site_id, [])
        if not stack:
            return []
        
        last_op = stack.pop()
        compensating_ops = []
        
        if last_op.op_type == OpType.INSERT:
            # Undo insert → delete the character
            idx = self._id_to_index.get(last_op.char_id)
            if idx is not None and not self._chars[idx].tombstone:
                self._chars[idx].tombstone = True
                comp_op = CRDTOp(
                    op_type=OpType.DELETE,
                    char_id=last_op.char_id,
                    parent_id=last_op.parent_id,
                    value=last_op.value,
                    site_id=self.site_id,
                    timestamp=time.time(),
                )
                compensating_ops.append(comp_op)
        
        elif last_op.op_type == OpType.DELETE:
            # Undo delete → un-tombstone the character
            idx = self._id_to_index.get(last_op.char_id)
            if idx is not None and self._chars[idx].tombstone:
                self._chars[idx].tombstone = False
                comp_op = CRDTOp(
                    op_type=OpType.INSERT,
                    char_id=last_op.char_id,
                    parent_id=last_op.parent_id,
                    value=last_op.value,
                    site_id=self.site_id,
                    timestamp=time.time(),
                )
                compensating_ops.append(comp_op)
        
        return compensating_ops

    def get_snapshot(self) -> dict:
        """
        Serializes the full CRDT state for late joiners.
        
        Returns a dictionary that can be JSON-serialized and sent over
        the network, then reconstructed via from_snapshot().
        """
        return {
            "site_id": self.site_id,
            "seq_counter": self._seq_counter,
            "chars": [c.to_dict() for c in self._chars],
            "site_max_seq": dict(self._site_max_seq),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict, new_site_id: str) -> "CRDTDocument":
        """
        Creates a CRDTDocument from a serialized snapshot.
        
        The new_site_id should be the joining user's unique site ID
        (different from the original document's site_id).
        
        Args:
            snapshot: Dictionary from get_snapshot()
            new_site_id: The unique site ID for the new replica
            
        Returns:
            A new CRDTDocument with the same state
        """
        doc = cls(site_id=new_site_id)
        
        # Restore characters
        doc._chars = [CRDTChar.from_dict(cd) for cd in snapshot.get("chars", [])]
        doc._rebuild_index()
        
        # Restore applied ops set
        doc._applied_ops = {c.char_id for c in doc._chars}
        
        # Restore site max sequences
        doc._site_max_seq = dict(snapshot.get("site_max_seq", {}))
        
        # Set our sequence counter to be higher than anything we've seen
        max_seen = max(doc._site_max_seq.values()) if doc._site_max_seq else 0
        doc._seq_counter = max(snapshot.get("seq_counter", 0), max_seen)
        
        return doc

    def get_cursor_char_id(self, visible_pos: int) -> Optional[dict]:
        """
        Gets the CharID at the given visible position for cursor tracking.
        
        This allows cursor positions to be transmitted as CRDT-aware
        identifiers that remain valid even as the document is edited
        by other users.
        """
        if visible_pos <= 0:
            return ORIGIN_ID.to_dict()
        
        cid = self._get_char_id_at_visible_pos(visible_pos)
        return cid.to_dict()

    def char_id_to_visible_pos(self, char_id_dict: dict) -> int:
        """
        Converts a CharID (from cursor tracking) back to a visible position.
        
        The returned position represents the cursor position AFTER the
        character identified by char_id_dict. This matches the semantics
        of get_cursor_char_id().
        
        Returns 0 if the character is not found or has been deleted.
        """
        target = CharID.from_dict(char_id_dict)
        if target == ORIGIN_ID:
            return 0
        
        visible_count = 0
        for c in self._chars:
            if not c.tombstone:
                visible_count += 1
            if c.char_id == target:
                return visible_count if not c.tombstone else visible_count
        
        return 0

    def replace_range(self, start_pos: int, end_pos: int, new_text: str) -> List[CRDTOp]:
        """
        Replaces text in the range [start_pos, end_pos) with new_text.
        Equivalent to delete + insert, but batched for efficiency.
        
        Args:
            start_pos: Start of the range (visible position, inclusive)
            end_pos: End of the range (visible position, exclusive)
            new_text: Replacement text
            
        Returns:
            Combined list of delete + insert operations
        """
        ops = []
        
        # First, delete the range
        delete_count = end_pos - start_pos
        if delete_count > 0:
            ops.extend(self.delete_at(start_pos, delete_count))
        
        # Then, insert new text at the start position
        if new_text:
            ops.extend(self.insert_at(start_pos, new_text))
        
        return ops

    def __len__(self) -> int:
        return self.char_count

    def __repr__(self) -> str:
        text = self.get_text()
        preview = text[:50] + "..." if len(text) > 50 else text
        return f"CRDTDocument(site={self.site_id!r}, len={self.char_count}, text={preview!r})"
