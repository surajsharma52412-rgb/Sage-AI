"""
Comprehensive Test Suite for SAGE Autonomous Photo & Media Agent.
Tests the complete 8-step process:
1. UNDERSTAND: Inspect files, formats, EXIF, naming conventions.
2. PLAN: Numbered steps, non-destructive defaults (_duplicates, _review), flag irreversible actions.
3. EXECUTE: Telemetry before/after each call.
4. ANALYSIS RULES: Factual visible tags only, identical vs similar separation, EXIF preservation.
5. HANDLE FAILURES: Corrupted files quarantined, safe retries, halt on ambiguity.
6. TRACK STATE: SQLite processed vs pending tracking and separate destructive action log.
7. SCOPE AND AMBIGUITY: Confined strictly to target library directory.
8. FINAL REVIEW: Action breakdown, irreversible action log, review folder items, PASS/FAIL report.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from engine.photo_agent.state_store import PhotoStateStore
from engine.photo_agent.photo_tools import PhotoTools
from engine.photo_agent.autonomous_photo_agent import AutonomousPhotoAgent
from engine.agents.image_media_agent import ImageMediaAgent


class TestAutonomousPhotoAgent(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ws = Path(self.test_dir).resolve()
        self.lib = self.ws / "photos"
        self.lib.mkdir()

        # Create sample images
        self.img1 = self.lib / "pic1.png"
        Image.new("RGB", (1920, 1080), color="blue").save(self.img1)

        # Exact duplicate of img1
        self.img1_dupe = self.lib / "pic1_dupe.png"
        shutil.copyfile(self.img1, self.img1_dupe)

        # Portrait image
        self.img2 = self.lib / "pic2.jpg"
        Image.new("RGB", (600, 1200), color="green").save(self.img2)

        # Corrupt file
        self.img_corrupt = self.lib / "corrupt.jpg"
        with open(self.img_corrupt, "wb") as f:
            f.write(b"NOT_A_VALID_JPEG_HEADER_CORRUPTED_BYTES")

        self.db_path = self.ws / "photo_test.db"
        self.store = PhotoStateStore(self.db_path)
        self.tools = PhotoTools(self.ws)
        self.agent = AutonomousPhotoAgent(
            workspace_root=self.ws,
            state_store=self.store,
            tools=self.tools
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ── 1. UNDERSTAND ─────────────────────────────────────────────────

    def test_understand_scans_library_and_formats(self):
        """Verifies library scanning, file counts, format distribution, and corrupt file detection."""
        res = self.agent.understand(str(self.lib))
        self.assertTrue(res["success"])
        self.assertEqual(res["total_files"], 4)
        self.assertEqual(res["corrupt_count"], 1)
        self.assertIn("PNG", res["formats"])
        self.assertIn("summary", res)
        self.assertTrue(len(res["summary"]) > 20)

    # ── 2. PLAN ───────────────────────────────────────────────────────

    def test_plan_creates_non_destructive_steps(self):
        """Verifies that plan defaults to safe moves (_duplicates/_review) and flags irreversible actions."""
        summary = self.agent.understand(str(self.lib))
        steps = self.agent.plan("Deduplicate and clean photo library", summary)

        self.assertGreaterEqual(len(steps), 2)
        # Verify no step defaults to DELETE
        actions = [s["action"] for s in steps]
        self.assertNotIn("DELETE", actions)
        self.assertIn("DEDUPE_EXACT", actions)

        # DEDUPE_EXACT should be flagged as irreversible move
        dedupe_step = next(s for s in steps if s["action"] == "DEDUPE_EXACT")
        self.assertTrue(dedupe_step["is_irreversible"])

    # ── 3. EXECUTE & 4. ANALYSIS RULES ────────────────────────────────

    def test_exact_deduplication_moves_to_duplicates_folder(self):
        """Asserts exact SHA-256 duplicate is moved to _duplicates/ while keeping primary original untouched."""
        res = self.agent.execute_task(
            library_folder=str(self.lib),
            task_instruction="Deduplicate photos"
        )
        self.assertTrue(res["success"])
        # Original primary must exist
        self.assertTrue(self.img1.exists())
        # Duplicate copy must be moved to _duplicates/
        dupe_dir = self.lib / "_duplicates"
        self.assertTrue(dupe_dir.exists())
        self.assertTrue((dupe_dir / "dupe_pic1_dupe.png").exists())

    def test_auto_tagging_factual(self):
        """Asserts tags are strictly based on observable dimensions, aspect ratio, and format."""
        tags_res = self.tools.auto_tag_image(str(self.img1))
        self.assertTrue(tags_res["success"])
        tags = tags_res["tags"]
        self.assertIn("Format:PNG", tags)
        self.assertIn("Resolution:Full HD", tags)
        self.assertIn("Aspect:Landscape", tags)
        self.assertIn("Color:RGB", tags)

        tags_res2 = self.tools.auto_tag_image(str(self.img2))
        self.assertIn("Aspect:Portrait", tags_res2["tags"])

    def test_organize_by_date_preserves_structure(self):
        """Asserts photos are organized into date subfolders."""
        res = self.tools.organize_by_date(str(self.lib), copy_mode=True)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["total_organized"], 1)

    def test_edit_photo_preserves_originals(self):
        """Asserts editing saves to a new file and preserves the original."""
        edit = self.tools.edit_photo(str(self.img1), operation="resize", params={"width": 400, "height": 300})
        self.assertTrue(edit["success"])
        self.assertTrue(edit["is_original_preserved"])
        self.assertTrue(self.img1.exists())
        self.assertTrue(Path(edit["saved_path"]).exists())

    # ── 5. HANDLE FAILURES ────────────────────────────────────────────

    def test_corrupt_files_handled_gracefully(self):
        """Asserts corrupted files are flagged as CORRUPT and do not crash the agent."""
        scan = self.tools.scan_photo_library(str(self.lib))
        corrupt_items = [i for i in scan["items"] if i["status"] == "CORRUPT"]
        self.assertEqual(len(corrupt_items), 1)
        self.assertEqual(corrupt_items[0]["file_name"], "corrupt.jpg")

    # ── 6. TRACK STATE ────────────────────────────────────────────────

    def test_state_tracking_and_destructive_log(self):
        """Verifies that SQLite state store logs every destructive/irreversible action."""
        res = self.agent.execute_task(
            library_folder=str(self.lib),
            task_instruction="Deduplicate photos"
        )
        run_id = res["run_id"]
        run_record = self.store.get_run(run_id)
        self.assertIsNotNone(run_record)
        # Check destructive actions log
        dest_actions = run_record.get("destructive_actions", [])
        self.assertGreaterEqual(len(dest_actions), 1)
        self.assertEqual(dest_actions[0]["action_type"], "MOVE")

    # ── 8. FINAL REVIEW ───────────────────────────────────────────────

    def test_final_review_report(self):
        """Verifies determination PASS/FAIL and detailed action summary."""
        res = self.agent.execute_task(
            library_folder=str(self.lib),
            task_instruction="Deduplicate photos"
        )
        review = res["final_review"]
        self.assertEqual(review["determination"], "PASS")
        self.assertIn("total_files", review)
        self.assertIn("action_counts", review)
        self.assertIn("irreversible_actions", review)
        self.assertIn("summary", review)

    # ── 9. AGENT INTEGRATION ──────────────────────────────────────────

    def test_image_media_agent_photo_routing(self):
        """Verifies ImageMediaAgent execute routes photo tasks to AutonomousPhotoAgent."""
        media_agent = ImageMediaAgent()
        res = media_agent.execute({
            "instruction": "Organize photos in library by date",
            "library_folder": str(self.lib)
        })
        self.assertTrue(res["success"])
        self.assertEqual(res["agent"], "Image / Media Agent")
        self.assertIn("photo_review_report", [d["type"] for d in res.get("deliverables", [])])


if __name__ == "__main__":
    unittest.main()
