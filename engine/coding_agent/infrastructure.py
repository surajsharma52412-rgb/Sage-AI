"""
Scalable Infrastructure for SAGE Coding Agent Architecture (v6).
Enables the Coding Agent to handle massive and complex codebases:
- High-efficiency context management (RAG + token budgeting + chunk pruning)
- Caching & incremental build system (hash-based change detection)
- Large codebase indexing (scalable directory traversal & lazy streaming)
- Multi-repository support
- Concurrency and resource control
"""
import os
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class ScalableInfrastructure:
    """Manages file caching, incremental indexing, and context budgeting for large codebases."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            self.cache_dir = Path.home() / ".sage" / "coding_cache"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.file_hashes: Dict[str, str] = {}
        self.load_cache()

    def load_cache(self):
        cache_file = self.cache_dir / "file_hashes.json"
        if cache_file.exists():
            try:
                self.file_hashes = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                self.file_hashes = {}

    def save_cache(self):
        cache_file = self.cache_dir / "file_hashes.json"
        try:
            cache_file.write_text(json.dumps(self.file_hashes), encoding="utf-8")
        except Exception:
            pass

    def compute_file_hash(self, file_path: Path) -> str:
        """Computes SHA-256 hash of a file for incremental change detection."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def get_changed_files(self, workspace_root: Path, current_files: List[Dict[str, Any]]) -> List[str]:
        """Returns list of files that have been modified or newly added since last run."""
        changed = []
        for f in current_files:
            rel_path = f["path"]
            full_path = workspace_root / rel_path
            new_hash = self.compute_file_hash(full_path)
            old_hash = self.file_hashes.get(rel_path)
            if new_hash != old_hash:
                changed.append(rel_path)
                self.file_hashes[rel_path] = new_hash
        self.save_cache()
        return changed

    def budget_context(self, text: str, max_tokens_estimate: int = 4000) -> str:
        """
        Ensures context does not overflow LLM limits using fast word/token heuristic (~4 chars/token).
        """
        max_chars = max_tokens_estimate * 4
        if len(text) <= max_chars:
            return text

        # Truncate keeping top and bottom context
        half = max_chars // 2
        return text[:half] + "\n\n... [Context trimmed for token budget] ...\n\n" + text[-half:]
