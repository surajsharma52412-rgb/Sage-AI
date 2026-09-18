"""
Unit tests for Knowledge Center, Teach Model / Memory System, and Dynamic Themes.
"""
import unittest
import tempfile
from pathlib import Path

from engine.orchestrator.memory_manager import MemoryManager
from engine.shared_resources.vector_db import get_vector_db
from engine.shared_resources.knowledge_base import KnowledgeBase
from ui.styles.qss_theme import get_theme_qss, THEME_PALETTES


class TestKnowledgeAndThemes(unittest.TestCase):
    """Tests for teaching the model, memory management, and theme engine."""

    def setUp(self):
        self.memory_manager = MemoryManager()
        self.vector_db = get_vector_db()

    def test_theme_palettes_and_qss_generation(self):
        """Verify all 4 themes generate valid non-empty QSS stylesheets."""
        themes = ["cyberpunk", "obsidian", "midnight", "amethyst"]
        for t_key in themes:
            self.assertIn(t_key, THEME_PALETTES)
            qss = get_theme_qss(t_key)
            self.assertIsInstance(qss, str)
            self.assertGreater(len(qss), 500)
            pal = THEME_PALETTES[t_key]
            # Verify primary accent color is injected
            self.assertIn(pal["primary"], qss)

    def test_teach_and_retrieve_memory(self):
        """Verify teaching the model stores memory and retrieves it by relevance."""
        title = "Python Typing Standards"
        content = "Always write type annotations for all function parameters and return types."
        category = "directive"
        tags = "code,python,typing"

        res = self.memory_manager.teach_memory(
            title=title,
            content=content,
            category=category,
            tags=tags
        )

        self.assertIn("id", res)
        mem_id = res["id"]
        self.assertEqual(res["title"], title)

        # Retrieve relevant context
        ctx = self.memory_manager.retrieve_relevant_context("Python Typing Standards annotations")
        self.assertIn("Typing", ctx)

        # Verify listing all memories includes this item
        all_memories = self.memory_manager.list_all_memories()
        found = any(m.get("id") == mem_id for m in all_memories)
        self.assertTrue(found)

        # Clean up memory
        deleted = self.memory_manager.forget_memory(mem_id)
        self.assertTrue(deleted)

    def test_knowledge_base_delete_entry(self):
        """Verify KnowledgeBase entry deletion works properly."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        kb = KnowledgeBase(filepath=temp_path)
        kb.add_entry("test_rule", "Test Rule Title", "Rule content", ["test"])
        self.assertIsNotNone(kb.get_entry("test_rule"))

        # Delete entry
        deleted = kb.delete_entry("test_rule")
        self.assertTrue(deleted)
        self.assertIsNone(kb.get_entry("test_rule"))

        # Clean up
        if temp_path.exists():
            temp_path.unlink()

    def test_vector_db_add_list_delete(self):
        """Verify VectorDatabase add, list, and delete operations."""
        doc_id = "test_doc_xyz_999"
        self.vector_db.add_document(
            doc_id=doc_id,
            title="Database Vector Test",
            content="Testing semantic indexing and deletion capabilities.",
            tags="test,vector"
        )

        docs = self.vector_db.list_all_documents()
        self.assertTrue(any(d.get("id") == doc_id for d in docs))

        # Delete
        del_res = self.vector_db.delete_document(doc_id)
        self.assertTrue(del_res)
        docs_after = self.vector_db.list_all_documents()
        self.assertFalse(any(d.get("id") == doc_id for d in docs_after))

    def test_get_tinted_logo(self):
        """Verify dynamic logo recoloring for all themes."""
        from ui.styles.qss_theme import get_tinted_logo
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        themes = ["#0FE6B5", "#10B981", "#00d2ff", "#c084fc"]
        for hex_color in themes:
            pix = get_tinted_logo(hex_color, 42)
            self.assertFalse(pix.isNull())
            self.assertEqual(pix.width(), 42)
            self.assertEqual(pix.height(), 42)

    def test_multi_agent_view_scroll_and_theme(self):
        """Verify MultiAgentView scroll container and theme application."""
        from PySide6.QtWidgets import QApplication, QScrollArea
        from ui.components.multi_agent_view import MultiAgentView
        from ui.styles.qss_theme import THEME_PALETTES
        app = QApplication.instance() or QApplication([])

        mav = MultiAgentView()
        self.assertIsInstance(mav.scroll_area, QScrollArea)
        self.assertEqual(len(mav.agent_cards), 7)
        # Verify apply_theme updates button styling to active theme primary
        mav.apply_theme(THEME_PALETTES["amethyst"])
        self.assertIn("#c084fc", mav.run_btn.styleSheet())


if __name__ == "__main__":
    unittest.main()

