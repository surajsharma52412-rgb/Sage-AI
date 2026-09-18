"""
Advanced Code Editor Component for Sage AI (Lunar Engine).
Features:
- Integrated Multi-Language Syntax Highlighter (Python, JS, HTML, CSS, C++, Rust, Go, SQL, etc.)
- Real-Time Intelligent Autocomplete Helper (IntelliSense popup triggered as you type, e.g. 'p' -> 'print')
- Dynamic Document Word Harvesting (variables and functions in file auto-populate completions)
- Line Number Gutter with Current Line Highlight
- Auto-Indentation & Tab Handling
"""
import re
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QPlainTextEdit, QTextEdit, QCompleter
)
from PySide6.QtCore import Qt, QRect, QSize, QStringListModel, Signal, QTimer
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QTextFormat, QTextCursor, QFont, QKeyEvent, QFontMetrics
)

from ui.components.syntax_highlighter import MultiLanguageHighlighter


class CaseInsensitiveCompletions(dict):
    def __getitem__(self, key):
        return super().__getitem__(str(key).lower())

    def get(self, key, default=None):
        return super().get(str(key).lower(), default)

    def __contains__(self, key):
        return super().__contains__(str(key).lower())


# Multi-Language Autocompletion Dictionaries
LANGUAGE_COMPLETIONS: CaseInsensitiveCompletions = CaseInsensitiveCompletions({
    "python": [
        # Keywords
        "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
        "or", "pass", "raise", "return", "try", "while", "with", "yield",
        # Common 'p' words requested by user
        "print", "property", "pass", "pow", "pathlib", "pytest", "pyside6",
        "pandas", "parent", "pop", "position", "parse", "process", "platform",
        # Built-ins
        "abs", "all", "any", "bin", "bool", "bytearray", "bytes", "callable",
        "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir",
        "divmod", "enumerate", "eval", "exec", "filter", "float", "format",
        "frozenset", "getattr", "globals", "hasattr", "hash", "help", "hex",
        "id", "input", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "map", "max", "memoryview", "min", "next", "object",
        "oct", "open", "ord", "range", "repr", "reversed", "round", "set",
        "setattr", "slice", "sorted", "staticmethod", "str", "sum", "super",
        "tuple", "type", "vars", "zip", "__init__", "__str__", "__repr__",
        "__name__", "__main__", "self", "None", "True", "False"
    ],
    "javascript": [
        "console.log", "const", "let", "var", "function", "return", "promise",
        "push", "pop", "parseInt", "parseFloat", "process", "prototype",
        "import", "export", "from", "default", "class", "constructor", "this",
        "async", "await", "if", "else", "switch", "case", "break", "continue",
        "try", "catch", "finally", "throw", "typeof", "instanceof", "new",
        "null", "undefined", "true", "false", "document.getElementById",
        "addEventListener", "setTimeout", "setInterval", "fetch",
        "JSON.stringify", "JSON.parse", "Array", "Object", "String", "Number",
        "Boolean", "Map", "Set", "forEach", "filter", "map", "reduce",
        "find", "includes", "slice", "splice", "length", "window", "document"
    ],
    "typescript": [
        "console.log", "const", "let", "function", "return", "interface", "type",
        "namespace", "implements", "extends", "public", "private", "protected",
        "readonly", "async", "await", "promise", "push", "pop", "parseInt",
        "parseFloat", "process", "import", "export", "from", "class", "constructor",
        "this", "string", "number", "boolean", "any", "void", "never", "unknown",
        "Record", "Partial", "Omit", "Pick", "Array", "Promise"
    ],
    "html": [
        "<!DOCTYPE html>", "<html>", "<head>", "<title>", "<meta>", "<link>",
        "<style>", "<script>", "<body>", "<header>", "<nav>", "<main>",
        "<section>", "<article>", "<aside>", "<footer>", "<div>", "<p>",
        "<span>", "<a>", "<ul>", "<ol>", "<li>", "<h1>", "<h2>", "<h3>",
        "<h4>", "<h5>", "<h6>", "<button>", "<input>", "<textarea>", "<select>",
        "<option>", "<form>", "<label>", "<table>", "<tr>", "<th>", "<td>",
        "<img>", "<canvas>", "<svg>", "class=", "id=", "style=", "href=", "src="
    ],
    "css": [
        "display", "flex", "grid", "position", "relative", "absolute", "fixed",
        "padding", "margin", "width", "height", "max-width", "max-height",
        "min-width", "min-height", "background-color", "background", "color",
        "font-family", "font-size", "font-weight", "line-height", "border",
        "border-radius", "box-shadow", "justify-content", "align-items",
        "text-align", "overflow", "cursor", "pointer", "opacity", "z-index",
        "transition", "transform", "gap", "none", "block", "inline-block"
    ],
    "c": [
        "printf", "puts", "putchar", "pow", "public", "private", "int", "float",
        "double", "char", "void", "short", "long", "struct", "union", "enum",
        "typedef", "sizeof", "return", "if", "else", "for", "while", "do",
        "switch", "case", "default", "break", "continue", "include", "define",
        "malloc", "calloc", "realloc", "free", "NULL", "true", "false"
    ],
    "cpp": [
        "std::cout", "std::cin", "std::endl", "std::vector", "std::string",
        "std::map", "std::set", "std::pair", "std::make_shared", "std::unique_ptr",
        "printf", "puts", "pow", "public", "private", "protected", "class",
        "struct", "namespace", "template", "typename", "virtual", "override",
        "constexpr", "nullptr", "auto", "const", "new", "delete", "this",
        "try", "catch", "throw", "return", "if", "else", "for", "while"
    ],
    "rust": [
        "println!", "print!", "panic!", "pub", "pub(crate)", "fn", "let", "mut",
        "match", "if", "else", "loop", "while", "for", "in", "return", "break",
        "continue", "struct", "enum", "impl", "trait", "type", "use", "mod",
        "crate", "self", "Self", "super", "as", "where", "async", "await",
        "unsafe", "const", "static", "Vec", "String", "Option", "Result",
        "Some", "None", "Ok", "Err", "Box", "Rc", "Arc", "unwrap", "expect"
    ],
    "go": [
        "fmt.Println", "fmt.Printf", "fmt.Sprintf", "print", "println", "panic",
        "package", "import", "func", "return", "var", "const", "type", "struct",
        "interface", "if", "else", "for", "range", "switch", "case", "default",
        "break", "continue", "go", "chan", "select", "defer", "map", "make",
        "new", "len", "cap", "append", "copy", "delete", "string", "int",
        "bool", "byte", "rune", "error", "nil", "true", "false"
    ],
    "sql": [
        "SELECT", "FROM", "WHERE", "INSERT INTO", "UPDATE", "DELETE", "JOIN",
        "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "GROUP BY", "ORDER BY",
        "HAVING", "LIMIT", "OFFSET", "CREATE TABLE", "ALTER TABLE", "DROP TABLE",
        "PRIMARY KEY", "FOREIGN KEY", "REFERENCES", "INDEX", "COUNT", "SUM",
        "AVG", "MIN", "MAX", "DISTINCT", "AS", "AND", "OR", "NOT", "IN",
        "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL", "VALUES", "SET", "PRAGMA"
    ],
    "shell": [
        "echo", "printf", "cd", "ls", "pwd", "mkdir", "rm", "cp", "mv", "cat",
        "grep", "sed", "awk", "curl", "wget", "chmod", "chown", "ps", "kill",
        "export", "source", "which", "find", "python", "node", "git", "docker"
    ],
})


class LineNumberArea(QWidget):
    """Gutter widget displaying editor line numbers."""

    def __init__(self, editor: 'CodeEditor'):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """
    Advanced Monospace Code Editor with Multi-Language Syntax Highlighting,
    Real-Time Autocomplete Helper (IntelliSense), Line Number Gutter,
    and CRDT-powered collaborative editing with live cursor rendering.
    """

    # Signal emitted when local edits generate CRDT operations
    # Args: (file_path: str, ops: list[dict])
    crdt_ops_generated = Signal(str, list)

    # Signal emitted when cursor position changes (for broadcasting)
    # Args: (file_path: str, cursor_pos: int, sel_start: int, sel_end: int)
    cursor_moved = Signal(str, int, int, int)

    def __init__(self, language: str = "python", parent=None):
        super().__init__(parent)
        self.language = language.lower()

        # CRDT collaborative editing state
        self._crdt_doc = None            # Optional CRDTDocument instance
        self._crdt_file_path: str = ""   # File path for this editor's CRDT doc
        self._is_applying_remote: bool = False  # Guard against op feedback loops
        self._remote_cursors: Dict[str, dict] = {}  # peer_id → {name, color, pos, sel_start, sel_end}
        self._cursor_broadcast_timer = QTimer(self)
        self._cursor_broadcast_timer.setSingleShot(True)
        self._cursor_broadcast_timer.setInterval(50)  # 50ms debounce
        self._cursor_broadcast_timer.timeout.connect(self._broadcast_cursor_position)

        # 1. Monospace Font & Tab Width
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setTabStopDistance(32)  # 4 spaces

        # 2. Modern Dark Styling (VS Code Pure Dark)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #000000;
                color: #d4d4d4;
                border: 1px solid #273449;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
            QPlainTextEdit:focus {
                border: 1px solid rgba(0, 209, 255, 0.6);
            }
        """)

        # 3. Line Number Area Gutter
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.update_line_number_area_width(0)

        # 4. Multi-Language Syntax Highlighter
        self.highlighter = MultiLanguageHighlighter(self.document(), language=self.language)

        # 5. Autocompletion Helper
        self.completer: Optional[QCompleter] = None
        self.completer_model = QStringListModel(self)
        self._init_completer()

        self.highlight_current_line()

    # --- Language Switching ---

    def set_language(self, language: str) -> str:
        """Switches highlighting rules and autocomplete dictionary for the specified language."""
        display_name = self.highlighter.set_language(language)
        self.language = self.highlighter.language
        self._update_completer_words()
        return display_name

    def set_language_by_filename(self, filename: str) -> str:
        """Auto-detects language from file extension and switches editor mode."""
        display_name = self.highlighter.set_language_by_filename(filename)
        self.language = self.highlighter.language
        self._update_completer_words()
        return display_name

    def detect_language(self, filename: str) -> str:
        """Detects language display name from filename without altering current editor mode."""
        if not filename:
            return "Python"
        ext = Path(filename).suffix.lower()
        lang_key = MultiLanguageHighlighter.EXTENSION_MAP.get(ext, "text")
        lang_display_names = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "html": "HTML",
            "css": "CSS",
            "c": "C/C++",
            "cpp": "C/C++",
            "rust": "Rust",
            "go": "Go",
            "sql": "SQL",
            "json": "JSON",
            "shell": "Shell",
            "markdown": "Markdown",
            "text": "Text",
        }
        return lang_display_names.get(lang_key, "Text")

    def _collect_document_words(self) -> List[str]:
        """Extracts identifier words from current document."""
        doc_text = self.toPlainText()
        return sorted(list(set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", doc_text))))

    # --- Line Number Gutter Logic ---

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(max(1, self.blockCount()))))
        space = 20 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#000000"))

        # Thin separator border
        painter.setPen(QColor("#273449"))
        painter.drawLine(
            self.line_number_area.width() - 1,
            event.rect().top(),
            self.line_number_area.width() - 1,
            event.rect().bottom()
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        current_block_number = self.textCursor().blockNumber()

        font = self.font()
        font.setPointSize(9.5)
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number_str = str(block_number + 1)
                is_current = (block_number == current_block_number)

                if is_current:
                    painter.setPen(QColor("#c6c6c6"))
                    painter.setFont(QFont("Consolas", 9.5, QFont.Bold))
                else:
                    painter.setPen(QColor("#858585"))
                    painter.setFont(QFont("Consolas", 9.5))

                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter,
                    number_str
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        """Applies subtle glowing accent to current active line matching VS Code."""
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(255, 255, 255, 8))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    # --- Autocomplete (IntelliSense) Helper ---

    def _init_completer(self):
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self._insert_completion)

        popup = self.completer.popup()
        popup.setStyleSheet("""
            QListView {
                background-color: #0A0F14;
                color: #F8FAFC;
                border: 1px solid #00D1FF;
                border-radius: 6px;
                padding: 4px;
                font-family: Consolas, monospace;
                font-size: 11.5px;
                outline: none;
            }
            QListView::item {
                padding: 4px 8px;
                border-radius: 4px;
            }
            QListView::item:hover {
                background-color: #0d1a2c;
                color: #00D1FF;
            }
            QListView::item:selected {
                background-color: rgba(0, 209, 255, 0.22);
                color: #00D1FF;
                font-weight: bold;
            }
        """)
        self._update_completer_words()

    def _update_completer_words(self):
        """Combines language keywords with dynamic words extracted from current document."""
        words_set: Set[str] = set()

        # 1. Base language dictionary
        lang_key = self.language
        if lang_key in ("cpp", "c"):
            lang_words = LANGUAGE_COMPLETIONS.get("cpp", []) + LANGUAGE_COMPLETIONS.get("c", [])
        elif lang_key in ("javascript", "typescript"):
            lang_words = LANGUAGE_COMPLETIONS.get("javascript", []) + LANGUAGE_COMPLETIONS.get("typescript", [])
        else:
            lang_words = LANGUAGE_COMPLETIONS.get(lang_key, LANGUAGE_COMPLETIONS["python"])

        words_set.update(lang_words)

        # 2. Extract words from current document (variables, functions, classes)
        doc_words = self._collect_document_words()
        words_set.update(doc_words)

        # Sort alphabetically
        sorted_words = sorted(list(words_set))
        self.completer_model.setStringList(sorted_words)

    def _text_under_cursor(self) -> str:
        """Extracts the word or identifier prefix directly before cursor."""
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def _insert_completion(self, completion: str):
        """Replaces prefix under cursor with selected completion item."""
        if self.completer.widget() != self:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def keyPressEvent(self, event: QKeyEvent):
        # 1. If completer popup is visible, handle navigation and confirmation keys
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                self._insert_completion(self.completer.currentCompletion())
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() in (Qt.Key_Escape, Qt.Key_Backtab):
                self.completer.popup().hide()
                event.accept()
                return

        # Capture pre-edit state for CRDT op generation
        if self._crdt_doc and not self._is_applying_remote:
            pre_text = self.toPlainText()
            pre_cursor = self.textCursor().position()

        # 2. Auto-indentation on Enter key
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indentation = ""
            for char in current_line:
                if char in (" ", "\t"):
                    indentation += char
                else:
                    break
            # Add extra indent if line ends with ':' (Python) or '{' (JS/C++/etc.)
            stripped = current_line.rstrip()
            if stripped.endswith((":", "{")):
                indentation += "    "

            super().keyPressEvent(event)
            if indentation:
                self.insertPlainText(indentation)

            # Generate CRDT ops for the newline + indentation
            if self._crdt_doc and not self._is_applying_remote:
                self._generate_crdt_ops_from_diff(pre_text, pre_cursor)
            return

        # 3. Standard key event
        super().keyPressEvent(event)

        # 4. Generate CRDT operations from the text change
        if self._crdt_doc and not self._is_applying_remote:
            self._generate_crdt_ops_from_diff(pre_text, pre_cursor)

        # 5. Trigger Autocompletion helper popup
        if not self.completer:
            return

        prefix = self._text_under_cursor()
        # Trigger popup when prefix has at least 1 letter (e.g. user writes 'p')
        if len(prefix) >= 1 and prefix.isalnum() or prefix.startswith("_"):
            self._update_completer_words()
            self.completer.setCompletionPrefix(prefix)

            popup = self.completer.popup()
            if self.completer.completionCount() > 0:
                popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
                cr = self.cursorRect()
                cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width() + 24)
                self.completer.complete(cr)
            else:
                popup.hide()
        else:
            if self.completer.popup().isVisible():
                self.completer.popup().hide()

    # ─────────────────────────────────────────────
    # CRDT Collaborative Editing Methods
    # ─────────────────────────────────────────────

    def set_crdt_document(self, crdt_doc, file_path: str):
        """
        Attaches a CRDTDocument to this editor for collaborative editing.
        The editor will generate CRDT ops on local edits and apply remote ops.
        """
        self._crdt_doc = crdt_doc
        self._crdt_file_path = file_path

    def clear_crdt_document(self):
        """Detaches the CRDT document (e.g., when leaving a session)."""
        self._crdt_doc = None
        self._crdt_file_path = ""
        self._remote_cursors.clear()
        self.viewport().update()

    def _generate_crdt_ops_from_diff(self, pre_text: str, pre_cursor: int):
        """
        Compares pre-edit and post-edit text to generate CRDT operations.
        This is called after each keypress to produce the delta.
        """
        if not self._crdt_doc:
            return

        post_text = self.toPlainText()
        if pre_text == post_text:
            return

        # Compute the minimal diff (common prefix/suffix)
        pre_len = len(pre_text)
        post_len = len(post_text)

        # Find common prefix length
        common_prefix = 0
        min_len = min(pre_len, post_len)
        while common_prefix < min_len and pre_text[common_prefix] == post_text[common_prefix]:
            common_prefix += 1

        # Find common suffix length (avoiding overlap with prefix)
        common_suffix = 0
        while (common_suffix < (pre_len - common_prefix) and
               common_suffix < (post_len - common_prefix) and
               pre_text[pre_len - 1 - common_suffix] == post_text[post_len - 1 - common_suffix]):
            common_suffix += 1

        # Deleted characters: pre_text[common_prefix : pre_len - common_suffix]
        deleted_count = pre_len - common_prefix - common_suffix
        # Inserted characters: post_text[common_prefix : post_len - common_suffix]
        inserted_text = post_text[common_prefix:post_len - common_suffix]

        ops = []

        # Generate delete ops first
        if deleted_count > 0:
            ops.extend(self._crdt_doc.delete_at(common_prefix, deleted_count))

        # Generate insert ops
        if inserted_text:
            ops.extend(self._crdt_doc.insert_at(common_prefix, inserted_text))

        # Emit ops for network transmission
        if ops:
            ops_dicts = [op.to_dict() for op in ops]
            self.crdt_ops_generated.emit(self._crdt_file_path, ops_dicts)

    def apply_remote_crdt_ops(self, ops_dicts: list):
        """
        Applies remote CRDT operations to this editor's document and updates the view.
        Uses a guard flag to prevent generating local ops from the text change.
        """
        if not self._crdt_doc:
            return

        from engine.collab.crdt_document import CRDTOp
        ops = [CRDTOp.from_dict(d) for d in ops_dicts]

        self._is_applying_remote = True
        try:
            self._crdt_doc.apply_remote_ops(ops)

            # Save cursor state
            cursor = self.textCursor()
            old_pos = cursor.position()
            v_scroll = self.verticalScrollBar().value()

            # Update editor text from CRDT state
            new_text = self._crdt_doc.get_text()
            if self.toPlainText() != new_text:
                self.setPlainText(new_text)

                # Restore cursor position (clamped to new text length)
                new_cursor = self.textCursor()
                new_cursor.setPosition(min(old_pos, len(new_text)))
                self.setTextCursor(new_cursor)
                self.verticalScrollBar().setValue(v_scroll)
        finally:
            self._is_applying_remote = False

    def update_remote_cursor(self, peer_id: str, peer_name: str, color: str,
                             cursor_pos: int, sel_start: int = 0, sel_end: int = 0):
        """
        Updates a remote peer's cursor position for live rendering.
        """
        self._remote_cursors[peer_id] = {
            "name": peer_name,
            "color": color,
            "pos": cursor_pos,
            "sel_start": sel_start,
            "sel_end": sel_end,
            "updated_at": time.time(),
        }
        self.viewport().update()  # Trigger repaint

    def remove_remote_cursor(self, peer_id: str):
        """Removes a remote peer's cursor (e.g., when they disconnect)."""
        self._remote_cursors.pop(peer_id, None)
        self.viewport().update()

    def _on_cursor_position_changed(self):
        """Debounces cursor position broadcasting."""
        if self._crdt_doc and not self._is_applying_remote:
            self._cursor_broadcast_timer.start()

    def _broadcast_cursor_position(self):
        """Emits cursor position signal for network broadcasting."""
        if not self._crdt_file_path:
            return
        cursor = self.textCursor()
        pos = cursor.position()
        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()
        self.cursor_moved.emit(self._crdt_file_path, pos, sel_start, sel_end)

    def paintEvent(self, event):
        """Renders the editor content plus remote cursor overlays."""
        super().paintEvent(event)

        # Draw remote cursors and selections
        if not self._remote_cursors:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)

        text = self.toPlainText()
        text_len = len(text)

        for peer_id, cursor_info in self._remote_cursors.items():
            color = QColor(cursor_info["color"])
            pos = min(cursor_info["pos"], text_len)
            sel_start = min(cursor_info.get("sel_start", pos), text_len)
            sel_end = min(cursor_info.get("sel_end", pos), text_len)
            name = cursor_info["name"]

            # Draw selection highlight (semi-transparent)
            if sel_start != sel_end:
                sel_color = QColor(color)
                sel_color.setAlpha(40)
                self._draw_range_highlight(painter, sel_start, sel_end, sel_color)

            # Draw cursor line
            cursor_rect = self._get_cursor_rect_at_position(pos)
            if cursor_rect:
                # Cursor line (2px wide, full height)
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.drawLine(
                    cursor_rect.left(), cursor_rect.top(),
                    cursor_rect.left(), cursor_rect.bottom()
                )

                # Name label above cursor
                label_color = QColor(color)
                label_color.setAlpha(220)
                font = QFont("Segoe UI", 8, QFont.Bold)
                painter.setFont(font)
                fm = QFontMetrics(font)
                label_width = fm.horizontalAdvance(name) + 8
                label_height = fm.height() + 4
                label_x = cursor_rect.left()
                label_y = cursor_rect.top() - label_height - 2

                # Background pill for label
                painter.setBrush(QBrush(label_color))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(
                    label_x, label_y,
                    label_width, label_height,
                    3, 3
                )

                # Label text
                painter.setPen(QColor("#000000"))
                painter.drawText(
                    label_x + 4, label_y + fm.ascent() + 2,
                    name
                )

        painter.end()

    def _get_cursor_rect_at_position(self, pos: int) -> Optional[QRect]:
        """Gets the viewport rectangle for a cursor at the given text position."""
        cursor = QTextCursor(self.document())
        cursor.setPosition(min(pos, self.document().characterCount() - 1))
        rect = self.cursorRect(cursor)
        return rect if rect.isValid() else None

    def _draw_range_highlight(self, painter: QPainter, start: int, end: int, color: QColor):
        """Draws a semi-transparent highlight over a text range."""
        if start > end:
            start, end = end, start

        cursor = QTextCursor(self.document())

        # Draw block by block for multi-line selections
        cursor.setPosition(start)
        start_block = cursor.block()
        cursor.setPosition(min(end, self.document().characterCount() - 1))
        end_block = cursor.block()

        block = start_block
        while block.isValid():
            block_start = block.position()
            block_end = block_start + block.length() - 1

            range_start = max(start, block_start)
            range_end = min(end, block_end)

            if range_start < range_end:
                cursor_start = QTextCursor(self.document())
                cursor_start.setPosition(range_start)
                cursor_end = QTextCursor(self.document())
                cursor_end.setPosition(range_end)

                rect_start = self.cursorRect(cursor_start)
                rect_end = self.cursorRect(cursor_end)

                highlight_rect = QRect(
                    rect_start.left(),
                    rect_start.top(),
                    rect_end.right() - rect_start.left(),
                    rect_start.height()
                )
                painter.fillRect(highlight_rect, color)

            if block == end_block:
                break
            block = block.next()
