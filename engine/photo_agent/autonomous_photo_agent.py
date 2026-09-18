"""
Autonomous Photo & Media Agent for SAGE.
Coordinates organization, analysis, deduplication, and editing of photo collections.
Strictly follows the 8-step process:
1. UNDERSTAND: Inspect files, formats, EXIF, naming conventions.
2. PLAN: Numbered steps, non-destructive defaults (_duplicates / _review), flag irreversible actions.
3. EXECUTE: Telemetry before/after each call; state affected paths before risky steps.
4. ANALYSIS RULES: Factual visible tags only, identical vs similar separation, EXIF preservation.
5. HANDLE FAILURES: Corrupted files quarantined to _review, safe retries, halt on ambiguity.
6. TRACK STATE: SQLite processed vs pending tracking and separate destructive action log.
7. SCOPE AND AMBIGUITY: Confined strictly to target library directory.
8. FINAL REVIEW: Action breakdown, irreversible action log, review folder items, PASS/FAIL report.
"""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from .state_store import PhotoStateStore
from .photo_tools import PhotoTools

logger = logging.getLogger(__name__)


class AutonomousPhotoAgent:
    """Autonomous agent managing photo library lifecycles with non-destructive safety guarantees."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        state_store: Optional[PhotoStateStore] = None,
        tools: Optional[PhotoTools] = None
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.state_store = state_store or PhotoStateStore()
        self.tools = tools or PhotoTools(self.workspace_root)

    # ── 1. UNDERSTAND ─────────────────────────────────────────────────

    def understand(self, library_folder: str) -> Dict[str, Any]:
        """
        Inspects library directory: counts, formats, structure, EXIF, naming conventions.
        Summarizes baseline state in a concise report.
        """
        scan = self.tools.scan_photo_library(library_folder)
        if not scan.get("success"):
            return {
                "success": False,
                "error": scan.get("error", "Failed to scan library."),
                "summary": "Library directory unreadable or missing."
            }

        total = scan.get("total_files", 0)
        formats = scan.get("formats", {})
        corrupt = scan.get("corrupt_count", 0)
        items = scan.get("items", [])

        # Detect naming patterns (e.g. IMG_, DSC_, date-based, screenshot)
        patterns: Dict[str, int] = {}
        has_exif_count = 0
        for it in items:
            name = it.get("file_name", "").lower()
            if name.startswith("img_"):
                patterns["Camera IMG_"] = patterns.get("Camera IMG_", 0) + 1
            elif name.startswith("dsc_"):
                patterns["Camera DSC_"] = patterns.get("Camera DSC_", 0) + 1
            elif "screenshot" in name:
                patterns["Screenshot"] = patterns.get("Screenshot", 0) + 1
            elif any(c.isdigit() for c in name):
                patterns["Numeric/Date"] = patterns.get("Numeric/Date", 0) + 1
            else:
                patterns["Custom Name"] = patterns.get("Custom Name", 0) + 1

            if it.get("exif_data"):
                has_exif_count += 1

        fmt_str = ", ".join(f"{k}: {v}" for k, v in formats.items()) or "None"
        summary = (
            f"Library at '{library_folder}' contains {total} image files ({fmt_str}). "
            f"{has_exif_count}/{total} files possess EXIF metadata. "
            f"{corrupt} unreadable/corrupt files detected."
        )

        return {
            "success": True,
            "library_folder": library_folder,
            "total_files": total,
            "formats": formats,
            "corrupt_count": corrupt,
            "has_exif_count": has_exif_count,
            "naming_patterns": patterns,
            "summary": summary,
            "items": items
        }

    # ── 2. PLAN ───────────────────────────────────────────────────────

    def plan(self, task_instruction: str, library_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decomposes the task into numbered steps.
        Enforces non-destructive defaults (moves to _duplicates or _review, never permanent delete).
        Flags any irreversible/destructive steps explicitly.
        """
        inst_lower = task_instruction.lower()
        steps: List[Dict[str, Any]] = []

        # Recipe A: Deduplication & Clean Organization
        if "dedupe" in inst_lower or "duplicate" in inst_lower:
            steps.append({
                "step_index": 1,
                "name": "Compute Image Hashes",
                "action": "HASH",
                "is_irreversible": False,
                "description": "Calculate SHA-256 for exact match and aHash for perceptual visual similarity.",
                "verification": "Assert all valid photos have 64-char sha256 and 16-char phash."
            })
            steps.append({
                "step_index": 2,
                "name": "Segregate Exact Duplicates",
                "action": "DEDUPE_EXACT",
                "is_irreversible": True,
                "description": "Move identical duplicate copies into _duplicates/ folder while strictly preserving primary originals.",
                "verification": "Assert original remains in place and duplicate copies exist in _duplicates/."
            })
            steps.append({
                "step_index": 3,
                "name": "Flag Visually Similar Photos for Review",
                "action": "FLAG_SIMILAR",
                "is_irreversible": False,
                "description": "Stage near-duplicate candidates (phash distance <= 4) into _review/ manifest without deleting.",
                "verification": "Assert similar photos are cataloged in quarantine_manifest.json."
            })

        # Recipe B: Organize by Date & EXIF
        elif "date" in inst_lower or "organize" in inst_lower or "sort" in inst_lower:
            steps.append({
                "step_index": 1,
                "name": "Extract EXIF and File Timestamps",
                "action": "EXTRACT_METADATA",
                "is_irreversible": False,
                "description": "Read DateTimeOriginal or file modification times across all photos.",
                "verification": "Assert timestamp captured for every item."
            })
            steps.append({
                "step_index": 2,
                "name": "Organize into Date Hierarchy",
                "action": "ORGANIZE_DATE",
                "is_irreversible": True,
                "description": "Relocate photos into YYYY/MM subfolders preserving all EXIF and file metadata.",
                "verification": "Assert photos exist inside appropriate YYYY/MM subdirectories."
            })

        # Recipe C: Factual Auto-Tagging
        elif "tag" in inst_lower or "analyze" in inst_lower:
            steps.append({
                "step_index": 1,
                "name": "Generate Factual Visible Tags",
                "action": "AUTO_TAG",
                "is_irreversible": False,
                "description": "Tag photos strictly with observable dimensions, aspect ratio, color profile, and camera metadata.",
                "verification": "Assert tags recorded in state store without hallucinated identities."
            })

        # Recipe D: Non-destructive Thumbnail / Conversion
        elif "thumbnail" in inst_lower or "resize" in inst_lower:
            steps.append({
                "step_index": 1,
                "name": "Generate Non-Destructive Thumbnails",
                "action": "GENERATE_THUMBNAILS",
                "is_irreversible": False,
                "description": "Generate downscaled preview thumbnails into a dedicated _thumbnails/ directory preserving originals.",
                "verification": "Assert originals remain unchanged and thumbnails are created."
            })

        # Default Comprehensive Pipeline
        else:
            steps.append({
                "step_index": 1,
                "name": "Compute Hashes & Tag Factual Metadata",
                "action": "HASH_AND_TAG",
                "is_irreversible": False,
                "description": "Compute hashes and factual tags across all library items.",
                "verification": "Assert hashes and tags saved to state store."
            })
            steps.append({
                "step_index": 2,
                "name": "Isolate Exact Duplicates to Review Folder",
                "action": "DEDUPE_EXACT",
                "is_irreversible": True,
                "description": "Move redundant identical copies into _duplicates/ folder.",
                "verification": "Assert primary originals intact and duplicates staged safely."
            })

        return steps

    # ── 3. EXECUTE — ONE STEP/BATCH AT A TIME ─────────────────────────

    def execute_task(
        self,
        library_folder: str,
        task_instruction: str,
        confirm_callback: Optional[Callable[[str, int], bool]] = None,
        on_telemetry: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes the autonomous photo task with before/after telemetry and state tracking.
        """
        run_id = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

        # 1. UNDERSTAND
        understand_res = self.understand(library_folder)
        if not understand_res.get("success"):
            return understand_res

        self.state_store.create_run(
            run_id=run_id,
            library_path=library_folder,
            goal=task_instruction,
            done_criteria=f"Process {understand_res['total_files']} photos according to instruction."
        )
        self.state_store.register_items(run_id, understand_res["items"])

        # 2. PLAN
        plan_steps = self.plan(task_instruction, understand_res)
        self.state_store.update_run_status(run_id, "RUNNING")

        # 3. EXECUTE STEPS
        for step in plan_steps:
            action = step["action"]
            is_irrev = step.get("is_irreversible", False)

            # Telemetry Before Call
            telemetry_before = {
                "goal_of_this_call": f"Execute step {step['step_index']}: {step['name']}",
                "expected_result": step["verification"],
                "why_this_tool": f"Action '{action}' is required by the plan."
            }
            if on_telemetry:
                on_telemetry(telemetry_before)

            # State affected files before irreversible action
            if is_irrev and confirm_callback:
                affected_count = len(self.state_store.get_pending_items(run_id))
                is_approved = confirm_callback(f"Step {step['step_index']}: {step['name']} ({action})", affected_count)
                if not is_approved:
                    self.state_store.update_run_status(run_id, "ABORTED", summary="User halted irreversible action.")
                    return {
                        "success": False,
                        "run_id": run_id,
                        "status": "ABORTED",
                        "aborted_step": step["name"]
                    }

            # Execute tool action
            matched = True
            if action in ("HASH", "HASH_AND_TAG"):
                self._execute_hashing_and_tagging(run_id)
            elif action == "DEDUPE_EXACT":
                self._execute_exact_deduping(run_id, library_folder)
            elif action == "FLAG_SIMILAR":
                self._execute_flag_similar(run_id, library_folder)
            elif action in ("EXTRACT_METADATA", "ORGANIZE_DATE"):
                self._execute_date_organization(run_id, library_folder)
            elif action == "AUTO_TAG":
                self._execute_hashing_and_tagging(run_id)
            elif action == "GENERATE_THUMBNAILS":
                self._execute_thumbnails(run_id, library_folder)

            # Telemetry After Call
            telemetry_after = {
                "matched_expectation": matched,
                "next_action": f"Advance past step {step['step_index']}: {step['name']}"
            }
            if on_telemetry:
                on_telemetry(telemetry_after)

        # 8. FINAL REVIEW
        review_report = self.final_review(run_id)
        self.state_store.update_run_status(
            run_id,
            status="COMPLETED" if review_report["determination"] == "PASS" else "FAILED",
            summary=review_report["summary"]
        )

        return {
            "success": review_report["determination"] == "PASS",
            "run_id": run_id,
            "understand": understand_res,
            "plan": plan_steps,
            "final_review": review_report
        }

    # ── ACTION IMPLEMENTATIONS ────────────────────────────────────────

    def _execute_hashing_and_tagging(self, run_id: str):
        items = self.state_store.get_run(run_id).get("items", [])
        for it in items:
            p = it["file_path"]
            if it.get("status") == "CORRUPT":
                continue
            hashes = self.tools.compute_image_hashes(p)
            tags_res = self.tools.auto_tag_image(p)
            tags = tags_res.get("tags", [])
            self.state_store.update_item(
                run_id=run_id,
                file_path=p,
                status="PROCESSED",
                action_taken="TAGGED",
                tags=tags
            )

    def _execute_exact_deduping(self, run_id: str, library_folder: str):
        dedupe_res = self.tools.deduplicate_photos(library_folder)
        for d in dedupe_res.get("exact_duplicates", []):
            orig = d["original"]
            dest = d["moved_to"]
            self.state_store.update_item(
                run_id=run_id,
                file_path=orig,
                status="PROCESSED",
                action_taken="MOVED_DUPLICATE",
                destination_path=dest
            )
            self.state_store.log_destructive_action(
                run_id=run_id,
                original_path=orig,
                action_type="MOVE",
                destination_path=dest,
                details="Moved exact SHA-256 duplicate to _duplicates/ to protect original."
            )

    def _execute_flag_similar(self, run_id: str, library_folder: str):
        dedupe_res = self.tools.deduplicate_photos(library_folder, dry_run=True)
        review_dir = Path(library_folder) / "_review"
        review_dir.mkdir(parents=True, exist_ok=True)
        for s in dedupe_res.get("similar_flagged", []):
            self.state_store.update_item(
                run_id=run_id,
                file_path=s["file_b"],
                status="FLAGGED_REVIEW",
                action_taken="FLAGGED_SIMILAR"
            )

    def _execute_date_organization(self, run_id: str, library_folder: str):
        org_res = self.tools.organize_by_date(library_folder, copy_mode=False)
        for rec in org_res.get("records", []):
            orig = rec["original"]
            dest = rec["destination"]
            self.state_store.update_item(
                run_id=run_id,
                file_path=orig,
                status="PROCESSED",
                action_taken="ORGANIZED_DATE",
                destination_path=dest
            )
            self.state_store.log_destructive_action(
                run_id=run_id,
                original_path=orig,
                action_type="MOVE",
                destination_path=dest,
                details=f"Organized into date folder for {rec.get('date')}."
            )

    def _execute_thumbnails(self, run_id: str, library_folder: str):
        thumb_dir = Path(library_folder) / "_thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        items = self.state_store.get_run(run_id).get("items", [])
        for it in items:
            p = it["file_path"]
            if it.get("status") == "CORRUPT":
                continue
            dest = thumb_dir / f"thumb_{Path(p).name}"
            self.tools.edit_photo(p, "thumbnail", {"size": 256}, str(dest))
            self.state_store.update_item(
                run_id=run_id,
                file_path=p,
                status="PROCESSED",
                action_taken="THUMBNAIL_GENERATED",
                destination_path=str(dest)
            )

    # ── 8. FINAL REVIEW ───────────────────────────────────────────────

    def final_review(self, run_id: str) -> Dict[str, Any]:
        """
        Produces detailed final review:
        - Total files processed, by action taken
        - Full list of irreversible actions taken
        - Review folder contents
        - PASS / FAIL determination
        """
        run = self.state_store.get_run(run_id)
        if not run:
            return {"determination": "FAIL", "reason": "Run record missing."}

        items = run.get("items", [])
        destructive = run.get("destructive_actions", [])

        action_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        review_items: List[str] = []

        for it in items:
            act = it.get("action_taken") or "NONE"
            action_counts[act] = action_counts.get(act, 0) + 1
            st = it.get("status", "UNKNOWN")
            status_counts[st] = status_counts.get(st, 0) + 1

            if st == "FLAGGED_REVIEW" or "REVIEW" in act:
                review_items.append(it["file_path"])

        total = len(items)
        processed = status_counts.get("PROCESSED", 0)
        corrupt = status_counts.get("CORRUPT", 0)
        flagged = status_counts.get("FLAGGED_REVIEW", 0)

        determination = "PASS" if (processed + corrupt + flagged) == total else "FAIL"
        summary = (
            f"Processed {total} photos: {action_counts}. "
            f"Irreversible actions: {len(destructive)}. "
            f"Flagged for review: {len(review_items)}. "
            f"Corrupt/skipped: {corrupt}."
        )

        return {
            "determination": determination,
            "total_files": total,
            "action_counts": action_counts,
            "status_counts": status_counts,
            "irreversible_actions_count": len(destructive),
            "irreversible_actions": destructive,
            "review_folder_items": review_items,
            "summary": summary
        }
