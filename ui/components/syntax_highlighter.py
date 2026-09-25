"""
Multi-Language Syntax Highlighter for Sage AI.
Provides high-performance syntax highlighting using QSyntaxHighlighter
across Python, JavaScript/TypeScript, HTML/XML, CSS, C/C++, Rust, Go, SQL, JSON, Shell, and Markdown.
"""
import re
from typing import Dict, List, Tuple
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextDocument
from PySide6.QtCore import Qt


# VS Code Dark+ / Dark Modern Theme Color Palette
PALETTE = {
    "control_keyword": "#c586c0",  # VS Code magenta/purple (import, from, return, if, for, while, etc.)
    "keyword": "#569cd6",          # VS Code keyword blue (def, class, async, await, pass, etc.)
    "constant": "#569cd6",         # VS Code blue (True, False, None, null, undefined)
    "function": "#dcdcaa",         # VS Code warm yellow (print, function calls, def names)
    "type": "#4ec9b0",             # VS Code class/type mint/teal (Path, QApplication, int, str, dict)
    "string": "#ce9178",           # VS Code warm terracotta/peach (strings, docstrings)
    "number": "#b5cea8",           # VS Code soft pale sage green (1300, 820, 0, 42)
    "comment": "#6a9955",          # VS Code forest green (# ..., // ...)
    "decorator": "#dcdcaa",        # VS Code warm yellow (@decorator)
    "tag": "#569cd6",              # VS Code blue (HTML tags)
    "attribute": "#9cdcfe",        # VS Code light sky blue (HTML attributes)
    "css_property": "#9cdcfe",     # VS Code light sky blue (CSS properties)
    "variable": "#9cdcfe",         # VS Code light sky blue (identifiers, parameters)
    "operator": "#d4d4d4",         # VS Code light gray operators
    "builtin": "#dcdcaa",          # VS Code function yellow / type teal
}


def _create_format(color_hex: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color_hex))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class MultiLanguageHighlighter(QSyntaxHighlighter):
    """Universal syntax highlighter supporting 10+ programming and markup languages."""

    # File extension to language mapping
    EXTENSION_MAP = {
        ".py": "python",
        ".pyw": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".html": "html",
        ".htm": "html",
        ".xml": "html",
        ".svg": "html",
        ".css": "css",
        ".scss": "css",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "cpp",
        ".hpp": "cpp",
        ".rs": "rust",
        ".go": "go",
        ".sql": "sql",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sh": "shell",
        ".bash": "shell",
        ".ps1": "shell",
        ".bat": "shell",
        ".cmd": "shell",
        ".md": "markdown",
    }

    LANGUAGE_CANONICAL = {
        "python": "python",
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "typescript",
        "ts": "typescript",
        "html": "html",
        "xml": "html",
        "css": "css",
        "c": "c",
        "c++": "cpp",
        "cpp": "cpp",
        "c/c++": "cpp",
        "rust": "rust",
        "go": "go",
        "golang": "go",
        "sql": "sql",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "shell": "shell",
        "bash": "shell",
        "sh": "shell",
        "powershell": "shell",
        "ps1": "shell",
        "markdown": "markdown",
        "md": "markdown",
        "text": "plain",
        "plain": "plain",
    }

    LANGUAGE_DISPLAY_NAMES = {
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "html": "HTML",
        "css": "CSS",
        "cpp": "C/C++",
        "c": "C/C++",
        "rust": "Rust",
        "go": "Go",
        "sql": "SQL",
        "json": "JSON",
        "yaml": "YAML",
        "shell": "Shell",
        "markdown": "Markdown",
        "plain": "Text",
    }

    def __init__(self, parent: QTextDocument = None, language: str = "python"):
        super().__init__(parent)
        lang_clean = language.lower().strip()
        self.language = self.LANGUAGE_CANONICAL.get(lang_clean, lang_clean)
        self.highlighting_rules: List[Tuple[re.Pattern, QTextCharFormat]] = []
        self._build_rules()

    @property
    def current_language(self) -> str:
        return self.LANGUAGE_DISPLAY_NAMES.get(self.language, self.language.capitalize())

    @property
    def rules(self) -> List[Tuple[re.Pattern, QTextCharFormat]]:
        return self.highlighting_rules

    def set_language(self, language: str) -> str:
        """Switches highlighting language mode and re-highlights document."""
        lang_clean = language.lower().strip()
        canonical = self.LANGUAGE_CANONICAL.get(lang_clean, lang_clean)
        if canonical != self.language or not self.highlighting_rules:
            self.language = canonical
            self._build_rules()
            self.rehighlight()
        return self.current_language

    def set_language_by_filename(self, filename: str) -> str:
        """Detects language by file extension and updates rules. Returns friendly name."""
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        lang = self.EXTENSION_MAP.get(ext, "plain")
        return self.set_language(lang)

    def _build_rules(self):
        self.highlighting_rules.clear()
        fmt_control = _create_format(PALETTE["control_keyword"])
        fmt_keyword = _create_format(PALETTE["keyword"])
        fmt_constant = _create_format(PALETTE["constant"])
        fmt_builtin = _create_format(PALETTE["builtin"])
        fmt_function = _create_format(PALETTE["function"])
        fmt_type = _create_format(PALETTE["type"])
        fmt_string = _create_format(PALETTE["string"])
        fmt_number = _create_format(PALETTE["number"])
        fmt_comment = _create_format(PALETTE["comment"], italic=True)
        fmt_decorator = _create_format(PALETTE["decorator"])
        fmt_variable = _create_format(PALETTE["variable"])

        # Numbers rule (applicable to almost all programming languages)
        self.highlighting_rules.append((re.compile(r"\b0x[0-9a-fA-F]+\b"), fmt_number))
        self.highlighting_rules.append((re.compile(r"\b[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\b"), fmt_number))

        if self.language == "python":
            # 1. Variables / Identifiers default
            self.highlighting_rules.append((re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"), fmt_variable))

            # 2. PascalCase Classes & Types (e.g. Path, QApplication, MainWindow)
            self.highlighting_rules.append((re.compile(r"\b[A-Z][a-zA-Z0-9_]*\b"), fmt_type))

            # 3. Builtin Types
            builtin_types = [
                "int", "str", "float", "bool", "list", "dict", "set", "tuple", "bytes",
                "bytearray", "object", "type", "complex"
            ]
            self._add_word_rules(builtin_types, fmt_type)

            # 4. Builtin Functions & Constants
            builtin_funcs = [
                "print", "len", "range", "open", "isinstance", "issubclass", "sum",
                "min", "max", "all", "any", "enumerate", "zip", "map", "filter",
                "sorted", "reversed", "dir", "help", "id", "input", "format",
                "super", "round", "abs", "divmod", "hash", "repr", "pow"
            ]
            self._add_word_rules(builtin_funcs, fmt_function)
            self._add_word_rules(["True", "False", "None", "self"], fmt_constant)

            # 5. Control Keywords (VS Code Purple #c586c0)
            control_keywords = [
                "import", "from", "as", "return", "if", "elif", "else", "for", "while",
                "try", "except", "finally", "with", "in", "is", "and", "or", "not",
                "yield", "raise", "match", "case", "assert"
            ]
            self._add_word_rules(control_keywords, fmt_control)

            # 6. Declaration Keywords (VS Code Blue #569cd6)
            decl_keywords = [
                "def", "class", "async", "await", "lambda", "global", "nonlocal", "del", "pass"
            ]
            self._add_word_rules(decl_keywords, fmt_keyword)

            # 7. Function Calls: foo(...)
            self.highlighting_rules.append((re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()"), fmt_function))

            # 8. Function Definitions: def foo
            self.highlighting_rules.append((re.compile(r"(?<=def\s)[a-zA-Z_][a-zA-Z0-9_]*"), fmt_function))

            # 9. Decorators: @decorator
            self.highlighting_rules.append((re.compile(r"@[a-zA-Z_][a-zA-Z0-9_\.]*"), fmt_decorator))

            # 10. Numbers
            self.highlighting_rules.append((re.compile(r"\b0x[0-9a-fA-F]+\b"), fmt_number))
            self.highlighting_rules.append((re.compile(r"\b[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\b"), fmt_number))

            # 11. Strings: "...", '...', f"...", r"..."
            self.highlighting_rules.append((re.compile(r"[bfrBFR]?\"[^\"]*\""), fmt_string))
            self.highlighting_rules.append((re.compile(r"[bfrBFR]?'[^']*'"), fmt_string))

            # 12. Single Line Comments: # ...
            self.highlighting_rules.append((re.compile(r"#[^\n]*"), fmt_comment))

        elif self.language in ("javascript", "typescript"):
            # Variables default
            self.highlighting_rules.append((re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"), fmt_variable))
            # PascalCase types/classes
            self.highlighting_rules.append((re.compile(r"\b[A-Z][a-zA-Z0-9_]*\b"), fmt_type))

            # Control keywords (VS Code Purple #c586c0)
            js_control = [
                "import", "from", "export", "default", "return", "if", "else", "for",
                "while", "do", "try", "catch", "finally", "switch", "case", "break",
                "continue", "yield", "as"
            ]
            self._add_word_rules(js_control, fmt_control)

            # Declaration keywords (VS Code Blue #569cd6)
            js_decl = [
                "const", "let", "var", "function", "class", "async", "await", "new",
                "typeof", "instanceof", "in", "of", "delete", "void", "interface",
                "type", "enum", "extends", "implements", "namespace", "static"
            ]
            self._add_word_rules(js_decl, fmt_keyword)

            # Constants
            self._add_word_rules(["true", "false", "null", "undefined", "this", "super", "NaN", "Infinity"], fmt_constant)

            # Built-ins
            self._add_word_rules(["console", "window", "document", "process", "Math", "JSON", "Promise", "Array", "Object", "String", "Number", "Boolean", "fetch", "require", "setTimeout", "setInterval"], fmt_function)

            # Function calls
            self.highlighting_rules.append((re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()"), fmt_function))
            # Strings
            self.highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt_string))
            self.highlighting_rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt_string))
            self.highlighting_rules.append((re.compile(r"`[^`\\]*(\\.[^`\\]*)*`"), fmt_string))
            # Comments
            self.highlighting_rules.append((re.compile(r"//[^\n]*"), fmt_comment))

        elif self.language == "html":
            fmt_tag = _create_format(PALETTE["tag"], bold=True)
            fmt_attr = _create_format(PALETTE["attribute"])
            # HTML Tags <div, </div, >
            self.highlighting_rules.append((re.compile(r"</?[a-zA-Z0-9\-]+"), fmt_tag))
            self.highlighting_rules.append((re.compile(r"/?>"), fmt_tag))
            # Attributes: class=, id=, href=
            self.highlighting_rules.append((re.compile(r"\b[a-zA-Z0-9_\-]+(?=\=)"), fmt_attr))
            # Quoted attribute strings
            self.highlighting_rules.append((re.compile(r'"[^"]*"'), fmt_string))
            self.highlighting_rules.append((re.compile(r"'[^']*'"), fmt_string))
            # Comments: <!-- ... -->
            self.highlighting_rules.append((re.compile(r"<!--[^\n]*-->"), fmt_comment))

        elif self.language == "css":
            fmt_prop = _create_format(PALETTE["css_property"], bold=True)
            fmt_val = _create_format(PALETTE["string"])
            # CSS Selectors: .class, #id
            self.highlighting_rules.append((re.compile(r"[.#][a-zA-Z0-9_\-]+"), fmt_keyword))
            # CSS Properties: background-color:, margin:
            self.highlighting_rules.append((re.compile(r"\b[a-zA-Z\-]+(?=\s*:)"), fmt_prop))
            # Color hex codes: #ffffff, #00D1FF
            self.highlighting_rules.append((re.compile(r"#[0-9a-fA-F]{3,8}\b"), fmt_number))
            # CSS units: 10px, 2rem, 100%
            self.highlighting_rules.append((re.compile(r"\b[0-9]+(px|rem|em|%|vh|vw|pt|s|ms)\b"), fmt_number))
            # Strings
            self.highlighting_rules.append((re.compile(r'"[^"]*"'), fmt_val))
            self.highlighting_rules.append((re.compile(r"'[^']*'"), fmt_val))
            # Comments
            self.highlighting_rules.append((re.compile(r"/\*[^\n]*\*/"), fmt_comment))

        elif self.language in ("c", "cpp"):
            keywords = [
                "auto", "break", "case", "char", "const", "continue", "default",
                "do", "double", "else", "enum", "extern", "float", "for", "goto",
                "if", "int", "long", "register", "return", "short", "signed",
                "sizeof", "static", "struct", "switch", "typedef", "union",
                "unsigned", "void", "volatile", "while", "class", "namespace",
                "new", "delete", "public", "private", "protected", "template",
                "typename", "using", "virtual", "friend", "inline", "bool",
                "nullptr", "constexpr", "override", "final", "try", "catch", "throw"
            ]
            builtins = [
                "std", "cout", "cin", "endl", "vector", "string", "map", "unordered_map",
                "set", "pair", "printf", "scanf", "malloc", "free", "size_t", "NULL",
                "true", "false"
            ]
            self._add_word_rules(keywords, fmt_keyword)
            self._add_word_rules(builtins, fmt_builtin)
            # Preprocessor directives: #include, #define
            self.highlighting_rules.append((re.compile(r"#[a-zA-Z_]+"), fmt_decorator))
            # Function calls: foo(
            self.highlighting_rules.append((re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()"), fmt_function))
            # Strings & characters
            self.highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt_string))
            self.highlighting_rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt_string))
            # Comments
            self.highlighting_rules.append((re.compile(r"//[^\n]*"), fmt_comment))

        elif self.language == "rust":
            keywords = [
                "as", "break", "const", "continue", "crate", "else", "enum", "extern",
                "false", "fn", "for", "if", "impl", "in", "let", "loop", "match",
                "mod", "move", "mut", "pub", "ref", "return", "self", "Self",
                "static", "struct", "super", "trait", "true", "type", "unsafe",
                "use", "where", "while", "async", "await", "dyn"
            ]
            builtins = [
                "println", "print", "format", "panic", "vec", "Option", "Some", "None",
                "Result", "Ok", "Err", "String", "Vec", "Box", "Rc", "Arc", "i8",
                "i16", "i32", "i64", "i128", "u8", "u16", "u32", "u64", "u128",
                "f32", "f64", "bool", "char", "usize", "isize"
            ]
            self._add_word_rules(keywords, fmt_keyword)
            self._add_word_rules(builtins, fmt_builtin)
            # Macros e.g. println!
            self.highlighting_rules.append((re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*!"), fmt_decorator))
            # Function definition
            self.highlighting_rules.append((re.compile(r"\bfn\s+([a-zA-Z_][a-zA-Z0-9_]*)"), fmt_function))
            # Strings
            self.highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt_string))
            # Comments
            self.highlighting_rules.append((re.compile(r"//[^\n]*"), fmt_comment))

        elif self.language == "go":
            keywords = [
                "break", "case", "chan", "const", "continue", "default", "defer",
                "else", "fallthrough", "for", "func", "go", "goto", "if", "import",
                "interface", "map", "package", "range", "return", "select", "struct",
                "switch", "type", "var"
            ]
            builtins = [
                "fmt", "Println", "Printf", "Sprintf", "append", "cap", "close",
                "complex", "copy", "delete", "imag", "len", "make", "new", "panic",
                "print", "println", "real", "recover", "string", "int", "bool",
                "byte", "rune", "error", "nil", "true", "false"
            ]
            self._add_word_rules(keywords, fmt_keyword)
            self._add_word_rules(builtins, fmt_builtin)
            # Function definition
            self.highlighting_rules.append((re.compile(r"\bfunc\s+([a-zA-Z_][a-zA-Z0-9_]*)"), fmt_function))
            # Strings
            self.highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt_string))
            self.highlighting_rules.append((re.compile(r"`[^`]*`"), fmt_string))
            # Comments
            self.highlighting_rules.append((re.compile(r"//[^\n]*"), fmt_comment))

        elif self.language == "sql":
            keywords = [
                "SELECT", "FROM", "WHERE", "INSERT", "INTO", "UPDATE", "DELETE",
                "CREATE", "TABLE", "DROP", "ALTER", "ADD", "JOIN", "LEFT", "RIGHT",
                "INNER", "OUTER", "FULL", "ON", "GROUP", "BY", "ORDER", "HAVING",
                "LIMIT", "OFFSET", "UNION", "ALL", "DISTINCT", "AS", "AND", "OR",
                "NOT", "NULL", "IS", "IN", "BETWEEN", "LIKE", "EXISTS", "CASE",
                "WHEN", "THEN", "ELSE", "END", "INDEX", "PRIMARY", "KEY", "FOREIGN",
                "REFERENCES", "CHECK", "DEFAULT", "CONSTRAINT", "PRAGMA", "VALUES", "SET"
            ]
            builtins = [
                "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "UPPER", "LOWER",
                "LENGTH", "SUBSTR", "ROUND", "NOW", "DATETIME", "CAST"
            ]
            # Case-insensitive SQL keywords
            for kw in keywords:
                self.highlighting_rules.append((re.compile(rf"\b{kw}\b", re.IGNORECASE), fmt_keyword))
            for b in builtins:
                self.highlighting_rules.append((re.compile(rf"\b{b}\b", re.IGNORECASE), fmt_builtin))
            # Strings
            self.highlighting_rules.append((re.compile(r"'[^']*'"), fmt_string))
            # Comments: -- ...
            self.highlighting_rules.append((re.compile(r"--[^\n]*"), fmt_comment))

        elif self.language in ("shell", "bash", "powershell"):
            keywords = [
                "if", "then", "else", "elif", "fi", "case", "esac", "for", "select",
                "while", "until", "do", "done", "in", "function", "time", "return",
                "exit", "set", "unset", "export", "source", "alias"
            ]
            builtins = [
                "echo", "cd", "pwd", "ls", "mkdir", "rm", "cp", "mv", "touch", "cat",
                "grep", "sed", "awk", "curl", "wget", "chmod", "chown", "ps", "kill",
                "tar", "zip", "find", "sudo", "git", "python", "node", "npm"
            ]
            self._add_word_rules(keywords, fmt_keyword)
            self._add_word_rules(builtins, fmt_builtin)
            # Variables: $VAR, ${VAR}
            self.highlighting_rules.append((re.compile(r"\$[a-zA-Z_0-9]+|\$\{[a-zA-Z_0-9]+\}"), fmt_type))
            # Strings
            self.highlighting_rules.append((re.compile(r'"[^"]*"'), fmt_string))
            self.highlighting_rules.append((re.compile(r"'[^']*'"), fmt_string))
            # Comments
            self.highlighting_rules.append((re.compile(r"#[^\n]*"), fmt_comment))

        elif self.language == "json":
            fmt_key = _create_format(PALETTE["keyword"], bold=True)
            # JSON keys: "key":
            self.highlighting_rules.append((re.compile(r'"[^"]*"\s*(?=:)'), fmt_key))
            # JSON string values: : "value"
            self.highlighting_rules.append((re.compile(r':\s*"[^"]*"'), fmt_string))
            # Booleans and null
            self._add_word_rules(["true", "false", "null"], fmt_builtin)

        elif self.language == "markdown":
            fmt_header = _create_format(PALETTE["keyword"], bold=True)
            fmt_code = _create_format(PALETTE["builtin"])
            fmt_link = _create_format(PALETTE["function"])
            # Headers #, ##, ###
            self.highlighting_rules.append((re.compile(r"^#{1,6}\s+[^\n]*", re.MULTILINE), fmt_header))
            # Inline code `...`
            self.highlighting_rules.append((re.compile(r"`[^`]+`"), fmt_code))
            # Links [text](url)
            self.highlighting_rules.append((re.compile(r"\[[^\]]+\]\([^\)]+\)"), fmt_link))
            # Lists and blockquotes
            self.highlighting_rules.append((re.compile(r"^(\*|-|\+|\d+\.)\s+", re.MULTILINE), fmt_type))
            self.highlighting_rules.append((re.compile(r"^>[^\n]*", re.MULTILINE), fmt_comment))

    def _add_word_rules(self, words: List[str], fmt: QTextCharFormat):
        """Combines multiple keyword words into a single optimized regex alternation for 10x faster highlighting."""
        if not words:
            return
        sorted_words = sorted(words, key=len, reverse=True)
        pattern_str = r"\b(?:" + "|".join(re.escape(w) for w in sorted_words) + r")\b"
        self.highlighting_rules.append((re.compile(pattern_str), fmt))

    def highlightBlock(self, text: str):
        """Applies all compiled pattern rules to the current text block."""
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)

        # Multi-line string or comment block handling for Python / C++ / JS
        self.setCurrentBlockState(0)
        if self.language == "python":
            if self.previousBlockState() in (0, -1, 1):
                self._highlight_multiline(text, '"""', '"""', 1, _create_format(PALETTE["string"]))
            if self.previousBlockState() in (0, -1, 2) and self.currentBlockState() <= 0:
                self._highlight_multiline(text, "'''", "'''", 2, _create_format(PALETTE["string"]))
        elif self.language in ("javascript", "typescript", "c", "cpp", "css"):
            self._highlight_multiline(text, "/*", "*/", 3, _create_format(PALETTE["comment"], italic=True))

    def _highlight_multiline(self, text: str, delimiter_start: str, delimiter_end: str, state_id: int, fmt: QTextCharFormat):
        start_idx = 0

        if self.previousBlockState() == state_id:
            end_idx = text.find(delimiter_end, 0)
            if end_idx == -1:
                self.setCurrentBlockState(state_id)
                self.setFormat(0, len(text), fmt)
                return
            else:
                length = end_idx + len(delimiter_end)
                self.setFormat(0, length, fmt)
                start_idx = end_idx + len(delimiter_end)

        while start_idx < len(text):
            found_start = text.find(delimiter_start, start_idx)
            if found_start == -1:
                break
            found_end = text.find(delimiter_end, found_start + len(delimiter_start))
            if found_end == -1:
                self.setCurrentBlockState(state_id)
                self.setFormat(found_start, len(text) - found_start, fmt)
                break
            else:
                length = (found_end + len(delimiter_end)) - found_start
                self.setFormat(found_start, length, fmt)
                start_idx = found_end + len(delimiter_end)
