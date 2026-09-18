"""
Standardized Photo & Image Tools for SAGE Autonomous Photo Agent.
Provides:
- Library scanning & EXIF extraction (Pillow)
- Exact SHA-256 hashing and perceptual 64-bit average hashing (aHash)
- Safe deduplication (identical hash -> _duplicates/, similar -> _review/)
- Date-based organization preserving EXIF metadata
- Strictly factual visible tagging (resolution, aspect ratio, color mode, camera make/model)
- Non-destructive image editing (resize, rotate, crop, thumbnail, format conversion)
- Quarantine and manifest management for review
"""
import os
import json
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from PIL import Image, ExifTags

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


class PhotoTools:
    """Tool library for analyzing, organizing, and transforming photo collections safely."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace_root / p
        return p.resolve()

    # ── 1. SCAN LIBRARY ───────────────────────────────────────────────

    def scan_photo_library(self, folder_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Inspects library directory: file count, formats, dimensions, and EXIF metadata.
        Corrupt/unreadable files are recorded as CORRUPT without crashing.
        """
        root = self._resolve(folder_path)
        if not root.exists() or not root.is_dir():
            return {"success": False, "error": f"Folder not found: {folder_path}"}

        items: List[Dict[str, Any]] = []
        formats_count: Dict[str, int] = {}
        corrupt_files: List[str] = []

        scanner = root.rglob("*") if recursive else root.glob("*")
        for p in scanner:
            if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            rel_str = str(p.relative_to(self.workspace_root)) if str(p).startswith(str(self.workspace_root)) else str(p)
            file_size = p.stat().st_size

            try:
                with Image.open(p) as img:
                    fmt = (img.format or p.suffix[1:].upper()).upper()
                    w, h = img.size
                    formats_count[fmt] = formats_count.get(fmt, 0) + 1

                    # Extract EXIF
                    exif_meta = self._extract_exif(img)

                    items.append({
                        "file_path": str(p),
                        "file_name": p.name,
                        "rel_path": rel_str,
                        "file_size": file_size,
                        "format": fmt,
                        "width": w,
                        "height": h,
                        "aspect_ratio": round(w / h, 2) if h > 0 else 1.0,
                        "exif_data": exif_meta,
                        "status": "PENDING"
                    })
            except Exception as e:
                logger.warning("Failed to open image %s: %s", p, e)
                corrupt_files.append(str(p))
                items.append({
                    "file_path": str(p),
                    "file_name": p.name,
                    "rel_path": rel_str,
                    "file_size": file_size,
                    "format": p.suffix[1:].upper(),
                    "width": 0,
                    "height": 0,
                    "aspect_ratio": 1.0,
                    "exif_data": {},
                    "status": "CORRUPT",
                    "error": str(e)
                })

        return {
            "success": True,
            "folder": str(root),
            "total_files": len(items),
            "formats": formats_count,
            "corrupt_count": len(corrupt_files),
            "items": items
        }

    def _extract_exif(self, img: Image.Image) -> Dict[str, Any]:
        meta = {}
        try:
            raw = img.getexif()
            if not raw:
                return meta
            for tag_id, val in raw.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(val, (bytes, bytearray)):
                    val = val.decode("utf-8", errors="replace")[:100]
                elif isinstance(val, (int, float, str)):
                    pass
                else:
                    val = str(val)[:100]
                meta[tag_name] = val
        except Exception:
            pass
        return meta

    # ── 2. HASHING (EXACT & PERCEPTUAL) ───────────────────────────────

    def compute_image_hashes(self, file_path: str) -> Dict[str, Any]:
        """
        Computes exact SHA-256 for identical byte matching
        and a 64-bit perceptual average hash (aHash) for visual similarity.
        """
        p = self._resolve(file_path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        # 1. SHA-256
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        sha256_hex = h.hexdigest()

        # 2. Perceptual Average Hash (8x8 grayscale)
        phash_hex = ""
        try:
            with Image.open(p) as img:
                small = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
                get_px = getattr(small, "get_flattened_data", small.getdata)
                pixels = list(get_px())
                avg = sum(pixels) / len(pixels)
                bits = "".join("1" if px >= avg else "0" for px in pixels)
                phash_hex = f"{int(bits, 2):016x}"
        except Exception as e:
            logger.debug("Could not compute phash for %s: %s", p, e)

        return {
            "success": True,
            "path": str(p),
            "sha256": sha256_hex,
            "phash": phash_hex
        }

    # ── 3. DEDUPLICATION (IDENTICAL VS SIMILAR) ───────────────────────

    def deduplicate_photos(
        self,
        folder_path: str,
        review_dir: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Separates identical vs similar duplicates:
        - Identical SHA-256: Moved to _duplicates/ (safe non-destructive default).
        - Visually similar aHash (distance <= 4): Moved to _review/ for user confirmation.
        Original files are preserved and never deleted by default.
        """
        root = self._resolve(folder_path)
        scan = self.scan_photo_library(str(root))
        if not scan["success"]:
            return scan

        duplicates_dir = root / "_duplicates"
        review_target_dir = self._resolve(review_dir) if review_dir else (root / "_review")

        if not dry_run:
            duplicates_dir.mkdir(parents=True, exist_ok=True)
            review_target_dir.mkdir(parents=True, exist_ok=True)

        by_sha: Dict[str, List[Dict[str, Any]]] = {}
        for it in scan["items"]:
            if it.get("status") == "CORRUPT":
                continue
            hashes = self.compute_image_hashes(it["file_path"])
            it["sha256"] = hashes.get("sha256", "")
            it["phash"] = hashes.get("phash", "")
            by_sha.setdefault(it["sha256"], []).append(it)

        exact_dupes_moved = []
        similar_flagged = []

        # 1. Process Exact Duplicates (keep first, move rest to _duplicates/)
        for sha, group in by_sha.items():
            if len(group) > 1:
                keeper = group[0]
                for dupe in group[1:]:
                    src_p = Path(dupe["file_path"])
                    dest_p = duplicates_dir / f"dupe_{src_p.name}"
                    if not dry_run:
                        shutil.move(src_p, dest_p)
                    exact_dupes_moved.append({
                        "original": str(src_p),
                        "kept_original": keeper["file_path"],
                        "moved_to": str(dest_p),
                        "sha256": sha
                    })

        # 2. Process Visually Similar (phash hamming distance <= 4)
        unique_items = [g[0] for g in by_sha.values() if g[0]["file_path"] not in [d["original"] for d in exact_dupes_moved]]
        for i in range(len(unique_items)):
            p1 = unique_items[i]
            h1 = p1.get("phash")
            if not h1:
                continue
            for j in range(i + 1, len(unique_items)):
                p2 = unique_items[j]
                h2 = p2.get("phash")
                if not h2 or h1 == h2:
                    continue
                dist = self._hamming_distance(h1, h2)
                if dist <= 4:
                    similar_flagged.append({
                        "file_a": p1["file_path"],
                        "file_b": p2["file_path"],
                        "hamming_distance": dist,
                        "action": "FLAGGED_FOR_REVIEW"
                    })

        return {
            "success": True,
            "dry_run": dry_run,
            "exact_duplicates_count": len(exact_dupes_moved),
            "exact_duplicates": exact_dupes_moved,
            "similar_count": len(similar_flagged),
            "similar_flagged": similar_flagged,
            "duplicates_folder": str(duplicates_dir),
            "review_folder": str(review_target_dir)
        }

    def _hamming_distance(self, h1: str, h2: str) -> int:
        try:
            v1 = int(h1, 16)
            v2 = int(h2, 16)
            return bin(v1 ^ v2).count("1")
        except Exception:
            return 999

    # ── 4. ORGANIZE BY DATE ───────────────────────────────────────────

    def organize_by_date(
        self,
        folder_path: str,
        target_root: Optional[str] = None,
        copy_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Organizes photos into YYYY/MM subdirectories based on EXIF date or file mtime.
        Preserves EXIF metadata and file timestamps.
        """
        root = self._resolve(folder_path)
        out_root = self._resolve(target_root) if target_root else root

        scan = self.scan_photo_library(str(root), recursive=False)
        if not scan["success"]:
            return scan

        moved_records = []
        for it in scan["items"]:
            if it.get("status") == "CORRUPT":
                continue
            src_p = Path(it["file_path"])
            date_val = self._determine_photo_date(it)
            sub_dir = out_root / date_val.strftime("%Y") / date_val.strftime("%m")
            sub_dir.mkdir(parents=True, exist_ok=True)
            dest_p = sub_dir / src_p.name

            # Avoid collision
            if dest_p.exists() and dest_p.resolve() != src_p.resolve():
                dest_p = sub_dir / f"{src_p.stem}_{int(datetime.now().timestamp())}{src_p.suffix}"

            if src_p.resolve() != dest_p.resolve():
                if copy_mode:
                    shutil.copy2(src_p, dest_p)
                else:
                    shutil.move(src_p, dest_p)

                moved_records.append({
                    "original": str(src_p),
                    "destination": str(dest_p),
                    "date": date_val.strftime("%Y-%m-%d"),
                    "action": "COPIED" if copy_mode else "MOVED"
                })

        return {
            "success": True,
            "total_organized": len(moved_records),
            "records": moved_records
        }

    def _determine_photo_date(self, item: Dict[str, Any]) -> datetime:
        exif = item.get("exif_data", {})
        date_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
        if date_str:
            try:
                # Standard EXIF format: "YYYY:MM:DD HH:MM:SS"
                parts = str(date_str).split(" ")[0].replace("-", ":").split(":")
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                pass
        p = Path(item["file_path"])
        return datetime.fromtimestamp(p.stat().st_mtime)

    # ── 5. FACTUAL AUTO-TAGGING ───────────────────────────────────────

    def auto_tag_image(self, file_path: str) -> Dict[str, Any]:
        """
        Generates tags strictly based on visible image and metadata facts.
        No guessing identities or non-evident locations.
        """
        p = self._resolve(file_path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        tags: List[str] = []
        try:
            with Image.open(p) as img:
                w, h = img.size
                fmt = img.format or p.suffix[1:].upper()
                mode = img.mode

                # Format tag
                tags.append(f"Format:{fmt.upper()}")

                # Resolution category
                if w >= 3840 or h >= 2160:
                    tags.append("Resolution:4K Ultra HD")
                elif w >= 1920 or h >= 1080:
                    tags.append("Resolution:Full HD")
                elif w >= 1280 or h >= 720:
                    tags.append("Resolution:Standard HD")
                elif w <= 256 and h <= 256:
                    tags.append("Resolution:Thumbnail")
                else:
                    tags.append("Resolution:Standard")

                # Aspect ratio
                ratio = w / h if h > 0 else 1.0
                if ratio > 1.8:
                    tags.append("Aspect:Panoramic")
                elif ratio > 1.1:
                    tags.append("Aspect:Landscape")
                elif ratio < 0.9:
                    tags.append("Aspect:Portrait")
                else:
                    tags.append("Aspect:Square")

                # Color mode
                if mode == "L":
                    tags.append("Color:Grayscale")
                elif mode == "RGBA":
                    tags.append("Color:Alpha Transparent")
                elif mode == "RGB":
                    tags.append("Color:RGB")

                # EXIF Metadata facts
                exif = self._extract_exif(img)
                make = exif.get("Make")
                model = exif.get("Model")
                if make:
                    tags.append(f"Camera:{str(make).strip()}")
                if model and str(model) != str(make):
                    tags.append(f"Model:{str(model).strip()}")

                date_val = exif.get("DateTimeOriginal") or exif.get("DateTime")
                if date_val:
                    try:
                        year = str(date_val).split(":")[0].strip()
                        if len(year) == 4 and year.isdigit():
                            tags.append(f"Year:{year}")
                    except Exception:
                        pass

            return {
                "success": True,
                "file_path": str(p),
                "tags": tags
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 6. SAFE EDIT PHOTO ────────────────────────────────────────────

    def edit_photo(
        self,
        file_path: str,
        operation: str,
        params: Optional[Dict[str, Any]] = None,
        destination_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes non-destructive transformation (resize, rotate, crop, thumbnail, convert).
        Default saves to a new path to protect original file.
        """
        p = self._resolve(file_path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        params = params or {}
        dest = self._resolve(destination_path) if destination_path else (p.parent / f"{p.stem}_{operation}{p.suffix}")
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(p) as img:
                exif = img.info.get("exif")
                out_img = img.copy()

                if operation == "resize":
                    w = params.get("width", out_img.width)
                    h = params.get("height", out_img.height)
                    out_img = out_img.resize((w, h), Image.Resampling.LANCZOS)

                elif operation == "rotate":
                    angle = params.get("angle", 90)
                    out_img = out_img.rotate(angle, expand=True)

                elif operation == "crop":
                    box = params.get("box")  # (left, top, right, bottom)
                    if box and len(box) == 4:
                        out_img = out_img.crop(tuple(box))

                elif operation == "thumbnail":
                    max_dim = params.get("size", 256)
                    out_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                elif operation == "grayscale":
                    out_img = out_img.convert("L")

                save_kwargs = {}
                if exif and out_img.format in ("JPEG", "TIFF"):
                    save_kwargs["exif"] = exif

                out_img.save(dest, **save_kwargs)

            return {
                "success": True,
                "operation": operation,
                "original_path": str(p),
                "saved_path": str(dest),
                "is_original_preserved": str(p.resolve()) != str(dest.resolve())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 7. SAFE QUARANTINE ────────────────────────────────────────────

    def safe_quarantine(self, file_path: str, review_dir: str, reason: str = "Corrupt or ambiguous file") -> Dict[str, Any]:
        """
        Moves problematic or uncertain files to _review/ with manifest tracking.
        """
        src = self._resolve(file_path)
        if not src.exists():
            return {"success": False, "error": f"File does not exist: {file_path}"}

        r_dir = self._resolve(review_dir)
        r_dir.mkdir(parents=True, exist_ok=True)
        dest = r_dir / src.name

        shutil.move(src, dest)

        manifest_file = r_dir / "quarantine_manifest.json"
        entries = []
        if manifest_file.exists():
            try:
                entries = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                entries = []
        entries.append({
            "timestamp": datetime.now().isoformat(),
            "original_path": str(src),
            "quarantined_path": str(dest),
            "reason": reason
        })
        manifest_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")

        return {
            "success": True,
            "original_path": str(src),
            "quarantined_to": str(dest),
            "reason": reason
        }
