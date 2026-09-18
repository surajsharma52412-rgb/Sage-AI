"""
Codebase Indexing Engine for SAGE Autonomous Coding Agent.
Performs symbol-level AST & lexical indexing of source files:
- Classes, functions, methods, signatures, docstrings
- Imports, exports, and inter-module dependencies
- Incremental indexing (SHA-256 hash detection so only modified files re-index)
- Focused symbol retrieval and code-section extraction (prevents token blowout)
"""
import os
import ast
import re
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CodebaseIndexer:
    """Indexes source code symbols and enables focused snippet retrieval."""

    def __init__(self, workspace_root: Path, cache_dir: Optional[Path] = None):
        self.workspace_root = workspace_root.resolve()
        self.cache_dir = cache_dir or (self.workspace_root / ".sage_cache")
        self.file_hashes: Dict[str, str] = {}  # rel_path -> sha256
        self.symbols_by_file: Dict[str, List[Dict[str, Any]]] = {}  # rel_path -> list of symbols
        self.symbol_lookup: Dict[str, List[Dict[str, Any]]] = {}  # symbol_name -> occurrences
        self._load_cached_index()

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.cache_dir = self.workspace_root / ".sage_cache"
        self._load_cached_index()

    def update_index(self, force_all: bool = False) -> Dict[str, Any]:
        """
        Incrementally updates index by inspecting file hashes.
        Only parses files that have changed or been newly created.
        """
        current_files = self._get_indexable_files()
        reindexed = 0
        deleted = 0

        # Detect deleted files
        current_rel_paths = {f["rel_path"] for f in current_files}
        for indexed_path in list(self.symbols_by_file.keys()):
            if indexed_path not in current_rel_paths:
                self._remove_file_from_index(indexed_path)
                deleted += 1

        # Check for modifications
        for f_info in current_files:
            rel_path = f_info["rel_path"]
            full_path = self.workspace_root / rel_path
            current_hash = self._compute_hash(full_path)

            if force_all or self.file_hashes.get(rel_path) != current_hash:
                self._index_single_file(rel_path, full_path)
                self.file_hashes[rel_path] = current_hash
                reindexed += 1

        self._persist_cached_index()

        return {
            "total_files_indexed": len(self.symbols_by_file),
            "total_symbols": sum(len(s) for s in self.symbols_by_file.values()),
            "reindexed_count": reindexed,
            "deleted_count": deleted
        }

    def find_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Finds all definitions and locations matching a symbol name."""
        name_lower = symbol_name.lower().strip()
        matches = []
        for name, defs in self.symbol_lookup.items():
            if name_lower in name.lower():
                matches.extend(defs)
        return matches

    def retrieve_relevant_snippets(self, query: str, max_tokens_approx: int = 3000) -> str:
        """
        Retrieves focused code blocks matching query keywords, prioritizing
        symbol definitions over entire raw files.
        """
        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not tokens:
            return ""

        scored_symbols = []
        for name, defs in self.symbol_lookup.items():
            score = 0
            for t in tokens:
                if t == name.lower():
                    score += 5
                elif t in name.lower():
                    score += 2

            if score > 0:
                for d in defs:
                    scored_symbols.append((score, d))

        scored_symbols.sort(key=lambda x: x[0], reverse=True)

        snippets = []
        total_chars = 0
        max_chars = max_tokens_approx * 4
        seen_keys = set()

        for score, sym in scored_symbols:
            key = f"{sym['file']}:{sym['start_line']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            snippet = (
                f"--- File: {sym['file']} (Lines {sym['start_line']}-{sym['end_line']}) ---\n"
                f"{sym.get('code', sym['name'])}\n"
            )
            if total_chars + len(snippet) > max_chars:
                break
            snippets.append(snippet)
            total_chars += len(snippet)

        return "\n".join(snippets)

    # --- Internal Parsing ---

    def _index_single_file(self, rel_path: str, full_path: Path):
        """Extracts AST symbols from a single file."""
        self._remove_file_from_index(rel_path)

        symbols = []
        ext = full_path.suffix.lower()

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        if ext == ".py":
            symbols = self._parse_python_symbols(rel_path, content)
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            symbols = self._parse_js_symbols(rel_path, content)

        self.symbols_by_file[rel_path] = symbols
        for sym in symbols:
            name = sym["name"]
            if name not in self.symbol_lookup:
                self.symbol_lookup[name] = []
            self.symbol_lookup[name].append(sym)

    def _parse_python_symbols(self, rel_path: str, content: str) -> List[Dict[str, Any]]:
        symbols = []
        lines = content.splitlines()

        try:
            tree = ast.parse(content)
        except Exception:
            return symbols

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start + 10)
                code_snippet = "\n".join(lines[start - 1 : min(end, start + 30)])
                symbols.append({
                    "name": node.name,
                    "kind": "class",
                    "file": rel_path,
                    "start_line": start,
                    "end_line": end,
                    "docstring": ast.get_docstring(node) or "",
                    "code": code_snippet
                })

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start + 10)
                code_snippet = "\n".join(lines[start - 1 : min(end, start + 25)])
                symbols.append({
                    "name": node.name,
                    "kind": "function",
                    "file": rel_path,
                    "start_line": start,
                    "end_line": end,
                    "docstring": ast.get_docstring(node) or "",
                    "code": code_snippet
                })

        return symbols

    def _parse_js_symbols(self, rel_path: str, content: str) -> List[Dict[str, Any]]:
        symbols = []
        lines = content.splitlines()

        # Regex symbol extraction for JS/TS
        fn_pattern = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(", re.MULTILINE)
        class_pattern = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_$]+)", re.MULTILINE)
        arrow_pattern = re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.MULTILINE)

        for match in fn_pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            code_snippet = "\n".join(lines[line_no - 1 : min(len(lines), line_no + 20)])
            symbols.append({
                "name": match.group(1),
                "kind": "function",
                "file": rel_path,
                "start_line": line_no,
                "end_line": min(len(lines), line_no + 20),
                "code": code_snippet
            })

        for match in class_pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            code_snippet = "\n".join(lines[line_no - 1 : min(len(lines), line_no + 25)])
            symbols.append({
                "name": match.group(1),
                "kind": "class",
                "file": rel_path,
                "start_line": line_no,
                "end_line": min(len(lines), line_no + 25),
                "code": code_snippet
            })

        for match in arrow_pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            code_snippet = "\n".join(lines[line_no - 1 : min(len(lines), line_no + 20)])
            symbols.append({
                "name": match.group(1),
                "kind": "function",
                "file": rel_path,
                "start_line": line_no,
                "end_line": min(len(lines), line_no + 20),
                "code": code_snippet
            })

        return symbols

    def _remove_file_from_index(self, rel_path: str):
        if rel_path in self.symbols_by_file:
            old_syms = self.symbols_by_file[rel_path]
            for s in old_syms:
                name = s["name"]
                if name in self.symbol_lookup:
                    self.symbol_lookup[name] = [x for x in self.symbol_lookup[name] if x["file"] != rel_path]
                    if not self.symbol_lookup[name]:
                        del self.symbol_lookup[name]
            del self.symbols_by_file[rel_path]
        self.file_hashes.pop(rel_path, None)

    def _get_indexable_files(self) -> List[Dict[str, Any]]:
        files = []
        ignore = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".next"}
        for root, dirs, fnames in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in ignore and not d.startswith(".")]
            for fn in fnames:
                ext = Path(fn).suffix.lower()
                if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go"}:
                    p = Path(root) / fn
                    try:
                        rel = str(p.relative_to(self.workspace_root)).replace("\\", "/")
                        files.append({"rel_path": rel, "ext": ext})
                    except Exception:
                        pass
        return files

    def _compute_hash(self, path: Path) -> str:
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def _load_cached_index(self):
        index_file = self.cache_dir / "code_symbols.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                self.file_hashes = data.get("hashes", {})
                self.symbols_by_file = data.get("symbols_by_file", {})
                self.symbol_lookup = {}
                for f, syms in self.symbols_by_file.items():
                    for s in syms:
                        name = s["name"]
                        if name not in self.symbol_lookup:
                            self.symbol_lookup[name] = []
                        self.symbol_lookup[name].append(s)
            except Exception:
                pass

    def _persist_cached_index(self):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            index_file = self.cache_dir / "code_symbols.json"
            data = {
                "hashes": self.file_hashes,
                "symbols_by_file": self.symbols_by_file
            }
            index_file.write_text(json.dumps(data), encoding="utf-8")
        except Exception as e:
            logger.debug("Could not persist code symbol index: %s", e)
