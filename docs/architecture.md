# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: Review active file

## 🎯 Active Task
Analyze architecture & specify contracts for: Review active file


## 📄 Target File(s)
### Target File: `docs/architecture.md`
```
# System Architecture Blueprint

## 1. System Overview
Target: Analyze architecture & specify contracts for: make a website

## 🎯 Active Task
Analyze architecture & specify contracts for: make a website


## 📄 Target File(s)
### Target File: `models.py`
```
class Item: pass

```

## 🔍 Relevant Code Symbols
--- File: engine/request_analyzer.py (Lines 75-176) ---
    def analyze(
        cls,
        prompt: str,
        force_web: bool = False,
        selected_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes a prompt and returns an intent dictionary.
        
        Returns:
            {
                "intent": str,
                "confidence": float,
                "matched_pattern": Optional[str],
                "force_web": bool,
                "selected_model": Optional[str],
                "clean_query": str
            }
        """
        cleaned = prompt.strip()
        lower_prompt = cleaned.lower()

        # If user explicitly toggled web search and didn't ask for an image
        if force_web:
            return {
                "intent": INTENT_WEB_SEARCH,

--- File: engine/coding_agent/model_router.py (Lines 81-97) ---
    def select_model_for_task(self, role: str, available_models: Optional[List[str]] = None) -> Dict[str, Any]:
        """Chooses best model g
... [Remaining lines truncated for context budget]
```

### Target File: `models.py`
```
"""
Core Data Models and Schemas.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class User:
    id: str
    email: str
    role: str = "user"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

```

## 🔍 Relevant Code Symbols
--- File: engine/request_analyzer.py (Lines 75-176) ---
    def analyze(
        cls,
        prompt: str,
        force_web: bool = False,
        selected_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes a prompt and returns an intent dictionary.
        
        Returns:
            {
                "intent": str,
                "confidence": float,
                "matched_pattern": Optional[str],
                "force_web": bool,
                "selected_model": Optional[str],
                "clean_query": str
            }
        """
        cleaned = prompt.strip()
        lower_prompt = cleaned.lower()

        # If user explicitly toggled web search and didn't ask for an image
        if force_web:
            return {
                "intent": INTENT_WEB_SEARCH,

--- File: tests/test_ide_html_models_and_file_ops.py (Lines 50-63) ---
    def test_open_html_file_and_preview_button(self):
        html_path = self.workspace / "index.html"
        html_path.write_text("<!DOCTYPE html><html><body><h1>Sage AI</h1></body></html>", encoding="utf-8")

        # Open file directly via open_file
        self.ide.open_file(html_path)
        self.assertIn("index.html", self.ide.open_documents)
        self.assertEqual(self.ide.active_filename, "index.html")
        self.assertEqual(self.ide.open_documents["index.html"]["language"], "HTML")
        self.assertIn("Sage AI", self.ide.editor.toPlainText())

        # Verify button text shows browser preview for HTML
        self.ide._update_run_button_label()
        self.assertEqual(self.ide.run_btn.text(), "🌐 Preview")

--- File: engine/coding_agent/checkpoint_manager.py (Lines 52-55) ---
    def is_user_file_protected(self, file_path: str) -> bool:
        """Checks if a file has pre-existing uncommitted user changes."""
        clean = file_path.replace("\\", "/").lstrip("./")
        return clean in self.initial_uncommitted_user_files

--- File: engine/coding_agent/codebase_indexer.py (Lines 130-152) ---
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

--- File: engine/coding_agent/codebase_indexer.py (Lines 241-251) ---
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

--- File: engine/coding_agent/codebase_indexer.py (Lines 253-267) ---
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



## 💡 Architectural Decisions & Conventions
- **Implementation: Review active file**: Engineered using 11-stage autonomous loop with python
- **Implementation: Build full stack analytics dashboar**: Engineered using 11-stage autonomous loop with unknown
- **Implementation: Build a production-grade course enr**: Engineered using 11-stage autonomous loop with unknown

## 🏗️ Project Architecture Overview
- Project Name: New folder (2)
- Architecture Type: Backend REST API / Microservice
- Primary Language: python
- Frameworks: Flask

## 2. Core Modules
- Backend API Server
- Database Persistence Layer
- Responsive Frontend
- Containerized Deployment

## 3. Data Models
- User (id, email, password_hash, role, created_at)
- Entity / Resource Models
