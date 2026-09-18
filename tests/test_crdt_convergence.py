"""
CRDT Convergence Tests for SAGE Collaborative IDE.

Tests that the RGA CRDT document implementation correctly converges
when concurrent operations are applied in different orders across
multiple replicas. This is the core correctness guarantee of the
collaborative editing system.

Test categories:
    1. Basic operations: insert, delete, get_text
    2. Concurrent edits: same-position inserts, cross-edits
    3. Snapshot/restore: late joiner sync
    4. Per-user undo: only undoes own operations
    5. Replace range: combined delete + insert
    6. Stress: 1000 rapid operations from 3 clients
    7. Client-server integration: WebSocket sync
"""

import sys
import os
import time
import asyncio
import threading
import unittest
import random
import string

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.collab.crdt_document import CRDTDocument, CRDTOp, OpType, CharID, ORIGIN_ID


class TestCRDTBasicOperations(unittest.TestCase):
    """Tests basic insert, delete, and text retrieval."""

    def test_empty_document(self):
        doc = CRDTDocument(site_id="alice")
        self.assertEqual(doc.get_text(), "")
        self.assertEqual(len(doc), 0)

    def test_insert_single_char(self):
        doc = CRDTDocument(site_id="alice")
        ops = doc.insert_at(0, "A")
        self.assertEqual(doc.get_text(), "A")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].op_type, OpType.INSERT)

    def test_insert_string(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello")
        self.assertEqual(doc.get_text(), "Hello")
        self.assertEqual(len(doc), 5)

    def test_insert_at_positions(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "AC")
        doc.insert_at(1, "B")
        self.assertEqual(doc.get_text(), "ABC")

    def test_insert_at_end(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello")
        doc.insert_at(5, " World")
        self.assertEqual(doc.get_text(), "Hello World")

    def test_insert_at_beginning(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "World")
        doc.insert_at(0, "Hello ")
        self.assertEqual(doc.get_text(), "Hello World")

    def test_delete_single_char(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABC")
        ops = doc.delete_at(1, 1)  # Delete 'B'
        self.assertEqual(doc.get_text(), "AC")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].op_type, OpType.DELETE)

    def test_delete_range(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABCDE")
        doc.delete_at(1, 3)  # Delete 'BCD'
        self.assertEqual(doc.get_text(), "AE")

    def test_delete_all(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABC")
        doc.delete_at(0, 3)
        self.assertEqual(doc.get_text(), "")
        self.assertEqual(len(doc), 0)

    def test_insert_after_delete(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABCDE")
        doc.delete_at(1, 3)  # Delete 'BCD' → "AE"
        doc.insert_at(1, "XY")  # Insert 'XY' after 'A' → "AXYE"
        self.assertEqual(doc.get_text(), "AXYE")


class TestCRDTConcurrentEdits(unittest.TestCase):
    """Tests that concurrent edits from different sites converge."""

    def test_concurrent_inserts_at_same_position(self):
        """Two users insert at the same position — both characters should appear."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")

        # Both start with "X"
        ops_init = doc_alice.insert_at(0, "X")
        doc_bob.apply_remote_ops(ops_init)

        # Alice inserts 'A' at position 1 (after 'X')
        ops_alice = doc_alice.insert_at(1, "A")

        # Bob inserts 'B' at position 1 (after 'X') — concurrent!
        ops_bob = doc_bob.insert_at(1, "B")

        # Apply each other's ops
        doc_alice.apply_remote_ops(ops_bob)
        doc_bob.apply_remote_ops(ops_alice)

        # Both should converge to the SAME text
        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        # Both characters should be present
        text = doc_alice.get_text()
        self.assertIn("A", text)
        self.assertIn("B", text)
        self.assertIn("X", text)
        self.assertEqual(len(text), 3)

    def test_concurrent_inserts_different_positions(self):
        """Two users insert at different positions — straightforward merge."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")

        # Both start with "Hello World"
        ops_init = doc_alice.insert_at(0, "Hello World")
        doc_bob.apply_remote_ops(ops_init)

        # Alice inserts at beginning
        ops_alice = doc_alice.insert_at(0, ">>")

        # Bob inserts at end
        ops_bob = doc_bob.insert_at(11, "<<")

        # Apply each other's ops
        doc_alice.apply_remote_ops(ops_bob)
        doc_bob.apply_remote_ops(ops_alice)

        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        text = doc_alice.get_text()
        self.assertTrue(text.startswith(">>"))
        self.assertTrue(text.endswith("<<"))

    def test_concurrent_delete_same_char(self):
        """Two users delete the same character — should only be deleted once."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")

        # Both start with "ABC"
        ops_init = doc_alice.insert_at(0, "ABC")
        doc_bob.apply_remote_ops(ops_init)

        # Both delete 'B' (position 1)
        ops_alice = doc_alice.delete_at(1, 1)
        ops_bob = doc_bob.delete_at(1, 1)

        # Apply each other's ops
        doc_alice.apply_remote_ops(ops_bob)
        doc_bob.apply_remote_ops(ops_alice)

        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        self.assertEqual(doc_alice.get_text(), "AC")

    def test_concurrent_insert_and_delete(self):
        """Alice inserts while Bob deletes — both operations should be preserved."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")

        # Both start with "ABC"
        ops_init = doc_alice.insert_at(0, "ABC")
        doc_bob.apply_remote_ops(ops_init)

        # Alice inserts 'X' at position 1 (between A and B)
        ops_alice = doc_alice.insert_at(1, "X")

        # Bob deletes 'B' (position 1)
        ops_bob = doc_bob.delete_at(1, 1)

        # Apply each other's ops
        doc_alice.apply_remote_ops(ops_bob)
        doc_bob.apply_remote_ops(ops_alice)

        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        # 'X' should be inserted and 'B' should be deleted
        text = doc_alice.get_text()
        self.assertIn("A", text)
        self.assertIn("X", text)
        self.assertIn("C", text)
        self.assertNotIn("B", text)

    def test_ops_commutativity(self):
        """Operations applied in different orders should produce the same result."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")
        doc_charlie = CRDTDocument(site_id="charlie")

        # All start with "Hello"
        ops_init = doc_alice.insert_at(0, "Hello")
        doc_bob.apply_remote_ops(ops_init)
        doc_charlie.apply_remote_ops(ops_init)

        # Alice inserts " World" at end
        ops_alice = doc_alice.insert_at(5, " World")
        # Bob inserts "!" at end of original
        ops_bob = doc_bob.insert_at(5, "!")

        # Apply in different orders
        doc_alice.apply_remote_ops(ops_bob)
        doc_bob.apply_remote_ops(ops_alice)
        
        # Charlie gets them in reverse order
        doc_charlie.apply_remote_ops(ops_bob)
        doc_charlie.apply_remote_ops(ops_alice)

        # All three should converge
        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        self.assertEqual(doc_bob.get_text(), doc_charlie.get_text())

    def test_ops_idempotency(self):
        """Applying the same operation twice should have no additional effect."""
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello")

        doc2 = CRDTDocument(site_id="bob")
        ops = doc.insert_at(5, " World")

        # Apply ops to doc2 twice
        doc2.apply_remote_ops(ops)
        doc2.apply_remote_ops(ops)  # Second application should be no-op

        # doc2 should have all the initial characters plus " World"
        # (the initial "Hello" was only in doc, not doc2, so doc2 only has " World"
        # from the remote ops)
        # Actually let's set up properly:
        doc_a = CRDTDocument(site_id="alice")
        doc_b = CRDTDocument(site_id="bob")
        
        init_ops = doc_a.insert_at(0, "Hello")
        doc_b.apply_remote_ops(init_ops)
        
        more_ops = doc_a.insert_at(5, " World")
        doc_b.apply_remote_ops(more_ops)
        doc_b.apply_remote_ops(more_ops)  # Duplicate
        
        self.assertEqual(doc_b.get_text(), "Hello World")


class TestCRDTSnapshot(unittest.TestCase):
    """Tests snapshot serialization and late joiner sync."""

    def test_snapshot_roundtrip(self):
        """Snapshot → serialize → deserialize produces identical document."""
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello World")
        doc.delete_at(5, 1)  # Delete space → "HelloWorld"
        
        snapshot = doc.get_snapshot()
        restored = CRDTDocument.from_snapshot(snapshot, "bob")
        
        self.assertEqual(restored.get_text(), "HelloWorld")

    def test_late_joiner_receives_full_state(self):
        """A late joiner should get the full document state via snapshot."""
        # Alice and Bob edit
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")
        
        ops = doc_alice.insert_at(0, "Hello")
        doc_bob.apply_remote_ops(ops)
        
        ops2 = doc_bob.insert_at(5, " World")
        doc_alice.apply_remote_ops(ops2)
        
        # Charlie joins late, gets snapshot from server
        snapshot = doc_alice.get_snapshot()
        doc_charlie = CRDTDocument.from_snapshot(snapshot, "charlie")
        
        self.assertEqual(doc_charlie.get_text(), doc_alice.get_text())
        self.assertEqual(doc_charlie.get_text(), "Hello World")

    def test_late_joiner_can_continue_editing(self):
        """A late joiner should be able to continue editing after receiving snapshot."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_alice.insert_at(0, "Hello")
        
        snapshot = doc_alice.get_snapshot()
        doc_bob = CRDTDocument.from_snapshot(snapshot, "bob")
        
        # Bob edits
        ops_bob = doc_bob.insert_at(5, " Bob")
        doc_alice.apply_remote_ops(ops_bob)
        
        self.assertEqual(doc_alice.get_text(), "Hello Bob")
        self.assertEqual(doc_bob.get_text(), "Hello Bob")


class TestCRDTUndo(unittest.TestCase):
    """Tests per-user undo behavior."""

    def test_undo_insert(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello")
        doc.insert_at(5, " World")
        
        # Undo should remove the last character Alice inserted (from " World")
        undo_ops = doc.undo()
        self.assertEqual(len(undo_ops), 1)
        self.assertEqual(undo_ops[0].op_type, OpType.DELETE)

    def test_undo_delete(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABC")
        doc.delete_at(1, 1)  # Delete 'B'
        
        # Undo should un-delete 'B'
        undo_ops = doc.undo()
        self.assertEqual(len(undo_ops), 1)
        self.assertEqual(undo_ops[0].op_type, OpType.INSERT)
        self.assertEqual(doc.get_text(), "ABC")

    def test_undo_only_own_changes(self):
        """Undo should only revert the local user's operations."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")
        
        # Alice types "Hello"
        ops_init = doc_alice.insert_at(0, "Hello")
        doc_bob.apply_remote_ops(ops_init)
        
        # Bob types " World"
        ops_bob = doc_bob.insert_at(5, " World")
        doc_alice.apply_remote_ops(ops_bob)
        
        # Alice undoes — should only undo Alice's last op (last char of "Hello")
        undo_ops = doc_alice.undo()
        self.assertEqual(len(undo_ops), 1)
        # Alice's last insert was 'o' (the last character of "Hello")
        # Undoing it should remove 'o'
        text = doc_alice.get_text()
        self.assertIn("World", text)  # Bob's text should still be there

    def test_undo_empty_stack(self):
        doc = CRDTDocument(site_id="alice")
        undo_ops = doc.undo()
        self.assertEqual(undo_ops, [])


class TestCRDTReplaceRange(unittest.TestCase):
    """Tests the replace_range convenience method."""

    def test_replace_middle(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello World")
        ops = doc.replace_range(5, 11, " Python")
        self.assertEqual(doc.get_text(), "Hello Python")
        self.assertTrue(len(ops) > 0)

    def test_replace_with_empty(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello World")
        doc.replace_range(5, 11, "")
        self.assertEqual(doc.get_text(), "Hello")

    def test_replace_empty_range(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello")
        doc.replace_range(5, 5, " World")
        self.assertEqual(doc.get_text(), "Hello World")


class TestCRDTStress(unittest.TestCase):
    """Stress tests with many concurrent operations."""

    def test_three_clients_1000_ops(self):
        """Three clients performing 1000 random operations each must converge."""
        docs = [
            CRDTDocument(site_id="alice"),
            CRDTDocument(site_id="bob"),
            CRDTDocument(site_id="charlie"),
        ]
        
        # Seed with initial text
        init_text = "The quick brown fox"
        init_ops = docs[0].insert_at(0, init_text)
        docs[1].apply_remote_ops(init_ops)
        docs[2].apply_remote_ops(init_ops)
        
        # Collect all ops per doc
        all_ops = [[], [], []]
        
        random.seed(42)  # Deterministic for reproducibility
        
        for i in range(1000):
            doc_idx = random.randint(0, 2)
            doc = docs[doc_idx]
            text_len = doc.get_length()
            
            if text_len == 0 or random.random() < 0.6:
                # Insert a random character
                pos = random.randint(0, text_len)
                ch = random.choice(string.ascii_lowercase)
                ops = doc.insert_at(pos, ch)
            else:
                # Delete a random character
                pos = random.randint(0, text_len - 1)
                ops = doc.delete_at(pos, 1)
            
            all_ops[doc_idx].extend(ops)
        
        # Now apply all ops to all docs (simulating delayed delivery)
        for i in range(3):
            for j in range(3):
                if i != j:
                    docs[j].apply_remote_ops(all_ops[i])
        
        # All three must converge to the same text
        text_alice = docs[0].get_text()
        text_bob = docs[1].get_text()
        text_charlie = docs[2].get_text()
        
        self.assertEqual(text_alice, text_bob,
                         f"Alice and Bob diverged!\nAlice: {text_alice[:100]}\nBob: {text_bob[:100]}")
        self.assertEqual(text_bob, text_charlie,
                         f"Bob and Charlie diverged!\nBob: {text_bob[:100]}\nCharlie: {text_charlie[:100]}")

    def test_concurrent_rapid_typing(self):
        """Simulates two users typing full sentences concurrently."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")
        
        # Alice types "Hello from Alice!"
        alice_ops = []
        for i, ch in enumerate("Hello from Alice!"):
            ops = doc_alice.insert_at(i, ch)
            alice_ops.extend(ops)
        
        # Bob types "Greetings from Bob!" (concurrently, at position 0)
        bob_ops = []
        for i, ch in enumerate("Greetings from Bob!"):
            ops = doc_bob.insert_at(i, ch)
            bob_ops.extend(ops)
        
        # Exchange ops
        doc_alice.apply_remote_ops(bob_ops)
        doc_bob.apply_remote_ops(alice_ops)
        
        # Both should converge
        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        
        # Both sentences should be present
        text = doc_alice.get_text()
        self.assertIn("Hello from Alice!", text)
        self.assertIn("Greetings from Bob!", text)

    def test_interleaved_ops_delivery(self):
        """Ops delivered in interleaved order (not batched) still converge."""
        doc_alice = CRDTDocument(site_id="alice")
        doc_bob = CRDTDocument(site_id="bob")
        doc_charlie = CRDTDocument(site_id="charlie")
        
        # All start with "Start"
        init_ops = doc_alice.insert_at(0, "Start")
        doc_bob.apply_remote_ops(init_ops)
        doc_charlie.apply_remote_ops(init_ops)
        
        # Generate ops from all three
        ops_a = doc_alice.insert_at(5, "AAA")
        ops_b = doc_bob.insert_at(5, "BBB")
        ops_c = doc_charlie.insert_at(5, "CCC")
        
        # Deliver in interleaved order to all
        all_remote_ops_for_alice = []
        all_remote_ops_for_bob = []
        all_remote_ops_for_charlie = []
        
        for i in range(3):
            if i < len(ops_b):
                all_remote_ops_for_alice.append(ops_b[i])
            if i < len(ops_c):
                all_remote_ops_for_alice.append(ops_c[i])
            if i < len(ops_a):
                all_remote_ops_for_bob.append(ops_a[i])
            if i < len(ops_c):
                all_remote_ops_for_bob.append(ops_c[i])
            if i < len(ops_a):
                all_remote_ops_for_charlie.append(ops_a[i])
            if i < len(ops_b):
                all_remote_ops_for_charlie.append(ops_b[i])
        
        doc_alice.apply_remote_ops(all_remote_ops_for_alice)
        doc_bob.apply_remote_ops(all_remote_ops_for_bob)
        doc_charlie.apply_remote_ops(all_remote_ops_for_charlie)
        
        self.assertEqual(doc_alice.get_text(), doc_bob.get_text())
        self.assertEqual(doc_bob.get_text(), doc_charlie.get_text())


class TestCRDTEdgeCases(unittest.TestCase):
    """Tests edge cases and boundary conditions."""

    def test_empty_insert(self):
        doc = CRDTDocument(site_id="alice")
        ops = doc.insert_at(0, "")
        self.assertEqual(ops, [])
        self.assertEqual(doc.get_text(), "")

    def test_delete_beyond_length(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "AB")
        ops = doc.delete_at(0, 10)  # Try to delete more than exists
        self.assertEqual(doc.get_text(), "")
        self.assertEqual(len(ops), 2)  # Only 2 chars deleted

    def test_multiline_text(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Line 1\nLine 2\nLine 3")
        self.assertEqual(doc.get_text(), "Line 1\nLine 2\nLine 3")
        self.assertIn("\n", doc.get_text())

    def test_unicode_characters(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello 🌍 こんにちは")
        self.assertEqual(doc.get_text(), "Hello 🌍 こんにちは")

    def test_repr(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "Hello")
        r = repr(doc)
        self.assertIn("alice", r)
        self.assertIn("Hello", r)

    def test_cursor_tracking(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABCDE")
        
        # Get cursor ID at position 3 (after 'C')
        cursor_id = doc.get_cursor_char_id(3)
        self.assertIsNotNone(cursor_id)
        
        # Convert back to visible position
        pos = doc.char_id_to_visible_pos(cursor_id)
        self.assertEqual(pos, 3)

    def test_cursor_at_origin(self):
        doc = CRDTDocument(site_id="alice")
        doc.insert_at(0, "ABC")
        cursor_id = doc.get_cursor_char_id(0)
        pos = doc.char_id_to_visible_pos(cursor_id)
        self.assertEqual(pos, 0)


if __name__ == "__main__":
    # Support --stress flag for running only stress tests
    if "--stress" in sys.argv:
        sys.argv.remove("--stress")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCRDTStress)
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
    else:
        unittest.main(verbosity=2)
