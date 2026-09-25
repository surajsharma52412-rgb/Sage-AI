"""
Message Bubble Component for Sage AI.
Custom chat bubble cards for User and Assistant, formatted with Markdown,
syntax-highlighted code blocks with one-click copy, citation chips, and generated image previews.
"""
import base64
import html
import re
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextBrowser, QSizePolicy, QApplication, QFileDialog, QToolTip,
    QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QUrl, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QDesktopServices, QTextCursor, QCursor

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False


LANG_DISPLAY_MAP = {
    "python": ("Python", "python"),
    "py": ("Python", "python"),
    "javascript": ("JavaScript", "javascript"),
    "js": ("JavaScript", "javascript"),
    "typescript": ("TypeScript", "typescript"),
    "ts": ("TypeScript", "typescript"),
    "html": ("HTML", "html"),
    "htm": ("HTML", "html"),
    "css": ("CSS", "css"),
    "json": ("JSON", "json"),
    "sql": ("SQL", "sql"),
    "c": ("C", "c"),
    "cpp": ("C++", "cpp"),
    "c++": ("C++", "cpp"),
    "c#": ("C#", "csharp"),
    "csharp": ("C#", "csharp"),
    "cs": ("C#", "csharp"),
    "java": ("Java", "java"),
    "rust": ("Rust", "rust"),
    "rs": ("Rust", "rust"),
    "go": ("Go", "go"),
    "golang": ("Go", "go"),
    "bash": ("Bash", "bash"),
    "sh": ("Shell", "bash"),
    "shell": ("Shell", "bash"),
    "powershell": ("PowerShell", "powershell"),
    "ps1": ("PowerShell", "powershell"),
    "yaml": ("YAML", "yaml"),
    "yml": ("YAML", "yaml"),
    "xml": ("XML", "xml"),
    "markdown": ("Markdown", "markdown"),
    "md": ("Markdown", "markdown"),
    "plaintext": ("Plain text", None),
    "plain text": ("Plain text", None),
    "text": ("Plain text", None),
    "txt": ("Plain text", None),
    "ascii": ("Plain text", None),
}


def _format_lang_info(raw_lang: str) -> Tuple[str, Optional[str]]:
    cleaned = (raw_lang or "").strip().lower()
    if not cleaned:
        return "Plain text", None
    if cleaned in LANG_DISPLAY_MAP:
        return LANG_DISPLAY_MAP[cleaned]
    return cleaned.capitalize(), cleaned


def _highlight_code(code_str: str, lexer_name: Optional[str]) -> str:
    if not HAS_PYGMENTS or not lexer_name or lexer_name.lower() in ("plain text", "plaintext", "text", "ascii"):
        return html.escape(code_str)
    try:
        lexer = get_lexer_by_name(lexer_name)
        formatter = HtmlFormatter(nowrap=True, noclasses=True, style='monokai')
        return highlight(code_str, lexer, formatter).strip("\r\n")
    except Exception:
        return html.escape(code_str)


def _detect_and_fence_ascii_art(text: str) -> str:
    """Automatically detects consecutive lines of ASCII art / text drawings and fences them."""
    lines = text.split('\n')
    in_fence = False
    ascii_run = []
    new_lines = []

    def is_ascii_art_line(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if s.startswith('```'):
            return False
        art_chars = sum(1 for c in s if c in r'/\\|_~=+-*^vV<>@#()[]')
        total_non_space = len(s)
        if total_non_space >= 3 and (art_chars / total_non_space) >= 0.35:
            return True
        if len(s) >= 2 and s[0] in r'/\\|' and s[-1] in r'/\\|':
            return True
        return False

    def flush_ascii_run():
        nonlocal ascii_run, new_lines
        if len(ascii_run) >= 3:
            new_lines.append('```plain text')
            new_lines.extend(ascii_run)
            new_lines.append('```')
        else:
            new_lines.extend(ascii_run)
        ascii_run = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            flush_ascii_run()
            in_fence = not in_fence
            new_lines.append(line)
            continue
        if in_fence:
            new_lines.append(line)
            continue

        if is_ascii_art_line(line):
            ascii_run.append(line)
        else:
            flush_ascii_run()
            new_lines.append(line)

    flush_ascii_run()
    return '\n'.join(new_lines)


def _render_code_card(code: str, lang: str, code_idx: int) -> str:
    """Renders a ChatGPT-style code card with header bar, language badge, copy action, and solid background."""
    lang_title, lexer_name = _format_lang_info(lang)
    code_clean = code.rstrip("\r\n")
    body_code = _highlight_code(code_clean, lexer_name)

    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="background-color: #0A0F14; border: 1px solid #273449; '
        f'border-radius: 10px; margin: 12px 0;">'
        f'<tr>'
        f'<td style="background-color: #162033; padding: 7px 14px; border-bottom: 1px solid #273449; '
        f'color: #94A3B8; font-family: \'Segoe UI\', -apple-system, sans-serif; font-size: 12px; font-weight: 600;">'
        f'<span style="color: #00D1FF; font-weight: bold; font-family: monospace;">&lt;/&gt;</span> &nbsp;{lang_title}'
        f'</td>'
        f'<td align="right" style="background-color: #162033; padding: 7px 14px; border-bottom: 1px solid #273449; '
        f'color: #94A3B8; font-family: \'Segoe UI\', -apple-system, sans-serif; font-size: 12px;">'
        f'<a href="copy:{code_idx}" style="color: #00D1FF; text-decoration: none; font-weight: 600;">📋 Copy</a>'
        f'</td>'
        f'</tr>'
        f'<tr>'
        f'<td colspan="2" style="padding: 12px 16px; background-color: #0A0F14;">'
        f'<pre style="margin: 0; padding: 0; background: transparent; border: none; color: #F8FAFC; '
        f'font-family: \'Cascadia Code\', \'Consolas\', \'Courier New\', monospace; font-size: 13px; '
        f'line-height: 1.35; white-space: pre;">{body_code}</pre>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def format_markdown_to_html(md_text: str, code_blocks_out: Optional[Dict[str, str]] = None) -> str:
    """Converts Markdown text into styled HTML with ChatGPT-style code blocks and dark theme."""
    if not HAS_MARKDOWN:
        escaped = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre style='color: #f4f5fb; font-family: monospace;'>{escaped}</pre>"

    # 1. Auto-detect unfenced ASCII drawings and wrap them in fences
    preprocessed_text = _detect_and_fence_ascii_art(md_text)

    # 2. Extract and preserve code fences before markdown parsing
    extracted_blocks: List[Tuple[str, str]] = []  # [(code, lang)]
    def _fence_repl(match):
        idx = len(extracted_blocks)
        lang = match.group(1).strip()
        code = match.group(2)
        extracted_blocks.append((code, lang))
        return f"\n\n@@@CODEBLOCK_{idx}@@@\n\n"

    fence_re = re.compile(
        r'(?:^|\n)[ \t]*```([a-zA-Z0-9_#+.\- ]*)[ \t]*\r?\n(.*?)\r?\n[ \t]*```[ \t]*(?=\n|$)',
        re.DOTALL
    )
    md_prepared = fence_re.sub(_fence_repl, preprocessed_text)

    # 3. Standard Markdown conversion for formatting, bold, italics, tables, and lists
    extensions = ['tables', 'nl2br', 'sane_lists']
    try:
        html_body = markdown.markdown(md_prepared, extensions=extensions)
    except Exception:
        html_body = f"<p>{md_text}</p>"

    # 4. Insert ChatGPT-style code cards for extracted code blocks
    for i, (raw_code, lang) in enumerate(extracted_blocks):
        if code_blocks_out is not None:
            code_blocks_out[str(i)] = raw_code.rstrip("\r\n")
        card_html = _render_code_card(raw_code, lang, i)
        html_body = html_body.replace(f"<p>@@@CODEBLOCK_{i}@@@</p>", card_html)
        html_body = html_body.replace(f"@@@CODEBLOCK_{i}@@@", card_html)

    # 5. Handle any remaining <pre><code>...</code></pre> blocks (e.g. 4-space indented code)
    def _wrap_indented_pre(match):
        idx = len(extracted_blocks)
        raw_code = html.unescape(match.group(1))
        extracted_blocks.append((raw_code, "plain text"))
        if code_blocks_out is not None:
            code_blocks_out[str(idx)] = raw_code.rstrip("\r\n")
        return _render_code_card(raw_code, "plain text", idx)

    html_body = re.sub(r'<pre><code>(.*?)</code></pre>', _wrap_indented_pre, html_body, flags=re.DOTALL)

    # 6. Mark standard markdown tables with class
    html_body = re.sub(r'<table>', r'<table class="markdownTable">', html_body)

    # Custom Modern SAGE dark styles for embedded HTML
    style = """
    <style>
        body, p, li, td {
            color: #F8FAFC;
            font-family: 'Segoe UI', 'Inter', sans-serif;
            font-size: 13px;
            line-height: 1.5;
        }
        h1, h2, h3, h4 {
            color: #00D1FF;
            margin-top: 10px;
            margin-bottom: 6px;
            font-weight: 700;
        }
        h1 { font-size: 17px; }
        h2 { font-size: 15px; }
        h3 { font-size: 14px; }
        code {
            background-color: rgba(255, 255, 255, 0.08);
            color: #00D1FF;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Cascadia Code', 'Consolas', monospace;
            font-size: 12px;
        }
        pre {
            background-color: #0A0F14;
            border: 1px solid #273449;
            border-radius: 8px;
            padding: 10px;
            color: #F8FAFC;
            font-family: 'Cascadia Code', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.35;
            white-space: pre;
            overflow-x: auto;
        }
        pre code {
            background-color: transparent;
            padding: 0;
            color: #F8FAFC;
            font-family: 'Cascadia Code', 'Consolas', monospace;
        }
        blockquote {
            border-left: 3px solid #00D1FF;
            margin: 6px 0;
            padding-left: 10px;
            color: #94A3B8;
            font-style: italic;
        }
        a {
            color: #00D1FF;
            text-decoration: underline;
        }
        table.markdownTable {
            border-collapse: collapse;
            width: 100%;
            margin: 8px 0;
        }
        table.markdownTable th, table.markdownTable td {
            border: 1px solid #273449;
            padding: 6px 10px;
            text-align: left;
        }
        table.markdownTable th {
            background-color: #162033;
            color: #00D1FF;
            font-weight: bold;
        }
        hr {
            border: none;
            border-top: 1px solid #273449;
            margin: 12px 0;
        }
    </style>
    """
    return f"<html><head>{style}</head><body>{html_body}</body></html>"


def extract_thinking(content: Optional[str]) -> tuple:
    """Extracts <think>...</think> chain-of-thought and returns (thinking_text, clean_content)."""
    if not content or not isinstance(content, str):
        return None, "" if content is None else str(content)
    match = re.search(r'<think>(.*?)</think>', content, flags=re.DOTALL | re.IGNORECASE)
    if match:
        thinking_text = match.group(1).strip()
        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
        return thinking_text, clean_content
    unclosed = re.search(r'<think>(.*)', content, flags=re.DOTALL | re.IGNORECASE)
    if unclosed:
        return unclosed.group(1).strip(), ""
    return None, content


class ThinkingSection(QFrame):
    """Claude-style collapsible thinking/reasoning disclosure box with live streaming support."""

    def __init__(self, thinking_text: str = "", latency_s: Optional[float] = None, is_live: bool = False, parent=None):
        super().__init__(parent)
        self.thinking_text = thinking_text or ""
        self.is_expanded = is_live
        self.latency_s = latency_s
        self.is_live = is_live
        self._start_time = time.time() if is_live else None
        self._live_timer: Optional[QTimer] = None

        self._init_ui()
        if is_live:
            self.start_live()

        self.destroyed.connect(self._cleanup_timer)

    def _cleanup_timer(self):
        if self._live_timer:
            try:
                if self._live_timer.isActive():
                    self._live_timer.stop()
            except Exception:
                pass
            self._live_timer = None

    def closeEvent(self, event):
        self._cleanup_timer()
        super().closeEvent(event)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(6)

        # Header Toggle Button
        duration_str = f"Thought for {self.latency_s:.1f}s" if self.latency_s and self.latency_s > 0 else "Thinking Process"
        initial_label = "✦  Thinking live (0.0s)  ◌" if self.is_live else f"✦  {duration_str}  ▾"

        self.header_btn = QPushButton(initial_label)
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.setFocusPolicy(Qt.NoFocus)
        self._apply_header_style()
        self.header_btn.clicked.connect(self._toggle_expand)
        main_layout.addWidget(self.header_btn)

        # Collapsible Content Container
        self.content_frame = QFrame()
        self.content_frame.setVisible(self.is_expanded)
        self.content_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(17, 24, 39, 0.8);
                border-left: 2.5px solid #00D1FF;
                border-radius: 4px;
                margin-left: 6px;
                margin-right: 4px;
            }
        """)
        cf_layout = QVBoxLayout(self.content_frame)
        cf_layout.setContentsMargins(12, 8, 12, 8)

        self.text_lbl = QTextBrowser()
        self.text_lbl.setPlainText(self.thinking_text)
        self.text_lbl.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                color: #94A3B8;
                font-family: 'Cascadia Code', 'Consolas', 'Segoe UI', monospace;
                font-size: 12px;
                line-height: 1.45;
            }
        """)
        self.text_lbl.setReadOnly(True)
        self.text_lbl.setMaximumHeight(260)
        cf_layout.addWidget(self.text_lbl)

        main_layout.addWidget(self.content_frame)

    def _apply_header_style(self):
        if self.is_live:
            self.header_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 209, 255, 0.15);
                    color: #00D1FF;
                    border: 1px solid #00D1FF;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 6px 12px;
                    text-align: left;
                }
            """)
        else:
            self.header_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 209, 255, 0.06);
                    color: #94A3B8;
                    border: 1px solid rgba(0, 209, 255, 0.2);
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 6px 12px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: rgba(0, 209, 255, 0.12);
                    color: #00D1FF;
                    border-color: rgba(0, 209, 255, 0.4);
                }
            """)

    def start_live(self):
        """Activates live streaming mode with real-time timer."""
        self.is_live = True
        self.is_expanded = True
        self.content_frame.setVisible(True)
        self._start_time = time.time()
        self._apply_header_style()

        if self._live_timer is None:
            self._live_timer = QTimer(self)
            self._live_timer.timeout.connect(self._update_live_timer)
        if not self._live_timer.isActive():
            self._live_timer.start(100)

    def _update_live_timer(self):
        try:
            if not self.isVisible() or not hasattr(self, "header_btn"):
                self._cleanup_timer()
                return
            if self._start_time:
                elapsed = time.time() - self._start_time
                self.header_btn.setText(f"✦  Thinking live ({elapsed:.1f}s)  ◌")
        except Exception:
            self._cleanup_timer()

    def append_chunk(self, chunk: str):
        """Appends streaming thinking tokens to the viewer incrementally."""
        try:
            self.thinking_text += chunk
            cursor = self.text_lbl.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(chunk)
            self.text_lbl.setTextCursor(cursor)
        except Exception:
            pass

    def finish_live(self, duration_s: Optional[float] = None):
        """Concludes live thinking and displays final duration."""
        self._cleanup_timer()
        self.is_live = False

        if duration_s:
            self.latency_s = duration_s
        elif self._start_time:
            self.latency_s = time.time() - self._start_time

        try:
            duration_str = f"Thought for {self.latency_s:.1f}s" if self.latency_s and self.latency_s > 0 else "Thought"
            arrow = "▴" if self.is_expanded else "▾"
            self.header_btn.setText(f"✦  {duration_str}  {arrow}")
            self._apply_header_style()
        except Exception:
            pass

    def _toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.content_frame.setVisible(self.is_expanded)

        duration_str = f"Thought for {self.latency_s:.1f}s" if self.latency_s and self.latency_s > 0 else "Thinking Process"
        arrow = "▴" if self.is_expanded else "▾"
        label = f"✦  Thinking live  {arrow}" if self.is_live else f"✦  {duration_str}  {arrow}"
        self.header_btn.setText(label)


class AnimatedImageGeneratingCard(QFrame):
    """
    Animated shimmer card displayed in the chat stream while an image is being generated.
    Features:
    - Moving light beam across dark glassmorphism canvas
    - Rotating artistic emoji animation: 🎨 -> ✨ -> 🖌️ -> 🪄 -> 🔮 -> 🌌
    - Live breathing neon border glow
    - Real-time generation status text
    """
    ICONS = ["🎨", "✨", "🖌️", "🪄", "🔮", "🌌"]

    def __init__(self, prompt: str = "", parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self._frame_idx = 0
        self._pulse_step = 0.0

        self.setFixedSize(500, 240)
        self._init_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(50)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_lbl = QLabel("🎨")
        self.icon_lbl.setStyleSheet("font-size: 36px; background: transparent;")
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_lbl)

        self.title_lbl = QLabel("Creating image with FLUX.1...")
        self.title_lbl.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 800; background: transparent;")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)

        short_prompt = self.prompt
        if len(short_prompt) > 65:
            short_prompt = short_prompt[:62] + "..."
        self.sub_lbl = QLabel(f'"{short_prompt}"' if short_prompt else "Diffusion sampling • Synthesizing high-res pixels")
        self.sub_lbl.setStyleSheet("color: #00D1FF; font-size: 11px; font-weight: 600; font-style: italic; background: transparent;")
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sub_lbl)

        self.badge_lbl = QLabel("● Synthesizing Latent Pixels  (100% Free Guaranteed • 0 Rs)")
        self.badge_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 700; background: transparent;")
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.badge_lbl)

        self._update_style(0.3)

    def _on_tick(self):
        self._pulse_step += 0.09
        idx = int(self._pulse_step * 2.2) % len(self.ICONS)
        if idx != self._frame_idx:
            self._frame_idx = idx
            self.icon_lbl.setText(self.ICONS[self._frame_idx])

        alpha = 0.25 + 0.35 * (0.5 * (1 + math.sin(self._pulse_step)))
        self._update_style(alpha)

    def _update_style(self, alpha: float):
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(17, 24, 39, 0.95),
                    stop:0.5 rgba(22, 33, 54, 0.90),
                    stop:1 rgba(10, 15, 20, 0.95));
                border: 1.5px solid rgba(0, 209, 255, {alpha:.2f});
                border-radius: 14px;
            }}
        """)

    def stop(self):
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()


class MessageBubble(QFrame):
    """Chat message bubble card supporting user/assistant roles, code blocks, images, citations, and thinking."""

    def __init__(
        self,
        role: str,
        content: str,
        model: Optional[str] = None,
        timestamp: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        is_image: bool = False,
        image_data: Optional[str] = None,
        latency_ms: Optional[float] = None,
        thinking: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        username: Optional[str] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.role = role
        self.raw_content = content
        self.model = model
        self.timestamp = timestamp
        self.citations = citations or []
        self.is_image = is_image
        self.image_data = image_data
        self.latency_ms = latency_ms
        self.thinking = thinking
        self.attachments = attachments or []
        self.attachments_box: Optional[QWidget] = None
        self.username = username or "Suraj Sharma"
        self.telemetry = telemetry or {}
        self.telem_badge: Optional[QLabel] = None
        self.header_layout: Optional[QHBoxLayout] = None
        self.image_generating_card: Optional[AnimatedImageGeneratingCard] = None
        self.img_container: Optional[QWidget] = None
        self._code_blocks: Dict[str, str] = {}

        # Extract thinking tags if present
        extracted_thinking, clean_content = extract_thinking(self.raw_content)
        self.thinking_text = self.thinking or extracted_thinking
        self.display_content = clean_content if extracted_thinking else self.raw_content

        self.setProperty("class", "userMessageRow" if role == "user" else "assistantMessageCard")
        self._init_ui()

    def _init_ui(self):
        is_user = self.role == "user"

        if is_user:
            self.setStyleSheet("background: transparent; border: none;")
            self.setProperty("class", "userMessageRow")

            row_layout = QHBoxLayout(self)
            row_layout.setContentsMargins(0, 4, 0, 4)
            row_layout.setSpacing(0)
            row_layout.addStretch(1)

            # User capsule card on the right
            user_card = QFrame()
            user_card.setProperty("class", "userMessageCard")
            user_card.setMaximumWidth(780)
            user_card_layout = QVBoxLayout(user_card)
            user_card_layout.setContentsMargins(16, 10, 16, 10)
            user_card_layout.setSpacing(6)

            # Attachment chips if present
            if self.attachments:
                self.attachments_box = QWidget()
                att_box = self.attachments_box
                att_layout = QHBoxLayout(att_box)
                att_layout.setContentsMargins(0, 2, 0, 4)
                att_layout.setSpacing(6)
                att_layout.setAlignment(Qt.AlignLeft)
                for a in self.attachments:
                    is_img = a.get("is_image", False)
                    icon_str = "🖼" if is_img else "📄"
                    fname = a.get("name", "file")
                    fsize = a.get("size", 0)
                    size_str = f"{fsize} B" if fsize < 1024 else f"{fsize // 1024} KB"
                    chip = QLabel(f"{icon_str}  {fname} ({size_str})")
                    chip.setStyleSheet("""
                        background-color: #162033;
                        color: #00D1FF;
                        border: 1px solid rgba(0, 209, 255, 0.35);
                        border-radius: 8px;
                        padding: 3px 8px;
                        font-size: 11px;
                        font-weight: 600;
                    """)
                    att_layout.addWidget(chip)
                user_card_layout.addWidget(att_box)

            # User prompt text
            html_content = format_markdown_to_html(self.display_content, self._code_blocks)
            self.text_browser = QTextBrowser()
            self.text_browser.setHtml(html_content)
            self.text_browser.setOpenExternalLinks(False)
            self.text_browser.anchorClicked.connect(self._handle_anchor_clicked)
            self.text_browser.setStyleSheet(
                "background: transparent; border: none; padding: 0px; selection-background-color: #00D1FF;"
            )
            self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.text_browser.document().contentsChanged.connect(self._adjust_browser_height)
            user_card_layout.addWidget(self.text_browser)

            row_layout.addWidget(user_card)

        else:
            self.setStyleSheet("background: transparent; border: none;")
            self.setProperty("class", "assistantMessageCard")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 6, 0, 18)
            layout.setSpacing(8)

            # Header row: SAGE AI + model badge + timestamp + copy btn
            header_layout = QHBoxLayout()
            header_layout.setSpacing(8)

            sender_lbl = QLabel("SAGE AI")
            sender_lbl.setProperty("class", "senderName")
            header_layout.addWidget(sender_lbl)

            if self.model:
                model_badge = QLabel(self.model)
                model_badge.setProperty("class", "modelBadge")
                header_layout.addWidget(model_badge)

            if self.timestamp:
                time_short = self.timestamp.split("T")[-1][:5] if "T" in self.timestamp else self.timestamp
                time_lbl = QLabel(time_short)
                time_lbl.setProperty("class", "timestampLabel")
                header_layout.addWidget(time_lbl)

            # Routing Telemetry Badge
            if self.telemetry and "global_rank" in self.telemetry:
                rank = self.telemetry.get("global_rank", 1)
                score = self.telemetry.get("overall_score", 9.6)
                fb_used = "Yes" if self.telemetry.get("fallback_used") else "No"
                prov = self.telemetry.get("provider_id", "OpenRouter").upper()
                mod = self.model or "Auto Model"

                self.telem_badge = QLabel(f"🧭 Rank #{rank} • {score:.1f}")
                self.telem_badge.setStyleSheet("""
                    background: rgba(0, 209, 255, 0.12);
                    color: #00D1FF;
                    border: 1px solid rgba(0, 209, 255, 0.35);
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 7px;
                """)
                tooltip_str = (
                    f"Model: Auto\n"
                    f"Provider: Auto\n"
                    f"Mode: Balanced\n\n"
                    f"Current Model: {mod}\n"
                    f"Provider: {prov}\n"
                    f"Rank: #{rank} / ALL 54 MODELS\n"
                    f"Score: {score:.1f}\n"
                    f"Fallback Used: {fb_used}"
                )
                self.telem_badge.setToolTip(tooltip_str)
                header_layout.addWidget(self.telem_badge)

            self.header_layout = header_layout
            header_layout.addStretch()

            # Copy response button
            self.copy_btn = QPushButton("📋 Copy")
            self.copy_btn.setProperty("class", "codeCopyBtn")
            self.copy_btn.setToolTip("Copy message text")
            self.copy_btn.clicked.connect(self._copy_raw_content)
            header_layout.addWidget(self.copy_btn)

            layout.addLayout(header_layout)

            # Attachment chips row if attachments present
            if self.attachments:
                self.attachments_box = QWidget()
                att_box = self.attachments_box
                att_layout = QHBoxLayout(att_box)
                att_layout.setContentsMargins(0, 2, 0, 4)
                att_layout.setSpacing(6)
                att_layout.setAlignment(Qt.AlignLeft)
                for a in self.attachments:
                    is_img = a.get("is_image", False)
                    icon_str = "🖼" if is_img else "📄"
                    fname = a.get("name", "file")
                    fsize = a.get("size", 0)
                    size_str = f"{fsize} B" if fsize < 1024 else f"{fsize // 1024} KB"
                    chip = QLabel(f"{icon_str}  {fname} ({size_str})")
                    chip.setStyleSheet("""
                        background-color: #162033;
                        color: #00D1FF;
                        border: 1px solid rgba(0, 209, 255, 0.35);
                        border-radius: 8px;
                        padding: 3px 8px;
                        font-size: 11px;
                        font-weight: 600;
                    """)
                    att_layout.addWidget(chip)
                layout.addWidget(att_box)

            # Image preview or loading shimmer card
            if self.is_image:
                if self.image_data:
                    self._render_image_container(layout=layout, smooth_reveal=False)
                else:
                    self.show_image_loading(self.display_content or self.raw_content, layout=layout)

            # Claude-style Thinking Section (if present)
            self.thinking_widget: Optional[ThinkingSection] = None
            if self.thinking_text:
                lat_s = (self.latency_ms / 1000.0) if self.latency_ms else None
                self.thinking_widget = ThinkingSection(self.thinking_text, latency_s=lat_s)
                layout.addWidget(self.thinking_widget)

            # Message Text / Markdown Content
            html_content = format_markdown_to_html(self.display_content, self._code_blocks)
            self.text_browser = QTextBrowser()
            self.text_browser.setHtml(html_content)
            self.text_browser.setOpenExternalLinks(False)
            self.text_browser.anchorClicked.connect(self._handle_anchor_clicked)
            self.text_browser.setStyleSheet(
                "background: transparent; border: none; padding: 0px; selection-background-color: #00D1FF;"
            )
            self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.text_browser.document().contentsChanged.connect(self._adjust_browser_height)
            layout.addWidget(self.text_browser)

            # Citations row if present
            if self.citations:
                cit_layout = QHBoxLayout()
                cit_layout.setSpacing(6)
                cit_prefix = QLabel("Sources:")
                cit_prefix.setStyleSheet("color: #626c85; font-size: 11px; font-weight: 600;")
                cit_layout.addWidget(cit_prefix)

                for c in self.citations[:4]:
                    chip = QLabel(f"🌐 {c.get('title', 'Source')[:25]}")
                    chip.setProperty("class", "citationChip")
                    url = c.get("url")
                    if url:
                        chip.setToolTip(url)
                        chip.setCursor(Qt.PointingHandCursor)
                        chip.mousePressEvent = lambda event, u=url: QDesktopServices.openUrl(QUrl(u))
                    cit_layout.addWidget(chip)

                cit_layout.addStretch()
                layout.addLayout(cit_layout)

    def start_live_thinking(self):
        """Initializes and displays live thinking section."""
        if self.thinking_widget is None:
            self.thinking_widget = ThinkingSection("", latency_s=None, is_live=True)
            idx = self.layout().indexOf(self.text_browser)
            if idx >= 0:
                self.layout().insertWidget(idx, self.thinking_widget)
            else:
                self.layout().addWidget(self.thinking_widget)
        else:
            self.thinking_widget.start_live()

    def append_live_thinking_chunk(self, chunk: str):
        """Streams reasoning chunk into the active thinking view."""
        if self.thinking_widget is None:
            self.start_live_thinking()
        self.thinking_widget.append_chunk(chunk)

    def finish_live_thinking(self, duration_s: Optional[float] = None):
        """Marks thinking process as finished."""
        if self.thinking_widget:
            self.thinking_widget.finish_live(duration_s)

    def append_live_response_chunk(self, chunk: str):
        """Streams response tokens into the main markdown view in real time with 35ms smooth throttling."""
        self.display_content += chunk
        self.raw_content += chunk
        if not hasattr(self, "_render_timer"):
            self._render_timer = QTimer(self)
            self._render_timer.setSingleShot(True)
            self._render_timer.timeout.connect(self._flush_live_render)

        if not self._render_timer.isActive():
            self._render_timer.start(35)

    def _flush_live_render(self):
        """Renders accumulated markdown into html smoothly without freezing GUI loop."""
        if hasattr(self, "text_browser") and self.text_browser:
            self._code_blocks.clear()
            html_content = format_markdown_to_html(self.display_content, self._code_blocks)
            self.text_browser.setHtml(html_content)
            self._adjust_browser_height()

    def _adjust_browser_height(self):
        try:
            if not hasattr(self, "text_browser") or not self.text_browser:
                return

            # Determine effective wrapping width
            vp = self.text_browser.viewport()
            if not vp:
                return
            vp_w = vp.width()
            if vp_w <= 20:
                parent_w = self.width() if self.width() > 100 else 780
                if self.role == "user":
                    vp_w = min(740, max(200, parent_w - 60))
                else:
                    vp_w = max(200, parent_w - 24)

            self.text_browser.document().setTextWidth(vp_w)
            doc_height = int(self.text_browser.document().size().height()) + 14
            self.text_browser.setFixedHeight(max(26, doc_height))
            self.updateGeometry()
        except (RuntimeError, AttributeError):
            return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_browser_height()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._adjust_browser_height)
        QTimer.singleShot(50, self._adjust_browser_height)
        QTimer.singleShot(150, self._adjust_browser_height)

    def _handle_anchor_clicked(self, url: QUrl):
        """Handles internal code block copy triggers and external hyperlink clicks."""
        url_str = url.toString()
        if url_str.startswith("copy:"):
            code_id = url_str.split(":", 1)[1]
            code_text = self._code_blocks.get(code_id, "")
            if code_text:
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(code_text)
                QToolTip.showText(QCursor.pos(), "✅ Code copied to clipboard!", self)
        elif url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)

    def _copy_raw_content(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.raw_content)
        if hasattr(self, "copy_btn") and self.copy_btn:
            try:
                from ui.components.animation_system import button_micro_press
                button_micro_press(self.copy_btn)
            except Exception:
                pass
            orig_text = "📋 Copy"
            self.copy_btn.setText("✅ Copied!")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText(orig_text) if hasattr(self, "copy_btn") and self.copy_btn else None)

    def _save_image(self, pixmap: QPixmap):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Picture",
            "sage_ai_picture.png",
            "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)"
        )
        if path:
            pixmap.save(path)

    def _copy_image(self, pixmap: QPixmap, btn: QPushButton):
        QApplication.clipboard().setPixmap(pixmap)
        orig_text = btn.text()
        btn.setText("✅ Copied!")
        QTimer.singleShot(1800, lambda: btn.setText(orig_text))

    def set_telemetry(self, telemetry: Dict[str, Any]):
        """Dynamically attaches routing telemetry to the message bubble header."""
        self.telemetry = telemetry
        if not telemetry or "global_rank" not in telemetry or not self.header_layout:
            return

        rank = telemetry.get("global_rank", 1)
        score = telemetry.get("overall_score", 9.6)
        fb_used = "Yes" if telemetry.get("fallback_used") else "No"
        prov = telemetry.get("provider_id", "OpenRouter").upper()
        mod = self.model or "Auto Model"

        tooltip_str = (
            f"Model: Auto\n"
            f"Provider: Auto\n"
            f"Mode: Balanced\n\n"
            f"Current Model: {mod}\n"
            f"Provider: {prov}\n"
            f"Rank: #{rank} / ALL 54 MODELS\n"
            f"Score: {score:.1f}\n"
            f"Fallback Used: {fb_used}"
        )

        if self.telem_badge:
            self.telem_badge.setText(f"🧭 Rank #{rank} • {score:.1f}")
            self.telem_badge.setToolTip(tooltip_str)
        else:
            self.telem_badge = QLabel(f"🧭 Rank #{rank} • {score:.1f}")
            self.telem_badge.setStyleSheet("""
                background: rgba(0, 209, 255, 0.12);
                color: #00D1FF;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 5px;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 7px;
            """)
            self.telem_badge.setToolTip(tooltip_str)
            # Insert right before the trailing stretch
            insert_idx = max(0, self.header_layout.count() - 2)
            self.header_layout.insertWidget(insert_idx, self.telem_badge)

    def show_image_loading(self, prompt: str = "", layout: Optional[QVBoxLayout] = None):
        """Displays animated image creation shimmer card while generation is in progress."""
        self.is_image = True
        target_layout = layout or self.layout()
        if hasattr(self, "text_browser") and not self.display_content:
            self.text_browser.setVisible(False)
        if not self.image_generating_card:
            self.image_generating_card = AnimatedImageGeneratingCard(prompt, self)
            if target_layout:
                target_layout.addWidget(self.image_generating_card)
        self._adjust_browser_height()

    def set_generated_image(self, image_data: str, content: str = "", latency_ms: Optional[float] = None):
        """Replaces image generation loading card with the final rendered image using a smooth reveal animation."""
        if hasattr(self, "image_generating_card") and self.image_generating_card:
            self.image_generating_card.stop()
            self.image_generating_card.deleteLater()
            self.image_generating_card = None

        self.image_data = image_data
        self.is_image = True
        self.latency_ms = latency_ms

        if content and hasattr(self, "text_browser"):
            self.text_browser.setVisible(True)
            self.raw_content = content
            self.display_content = content
            html = format_markdown_to_html(content)
            self.text_browser.setHtml(html)

        self._render_image_container(smooth_reveal=True)
        self._adjust_browser_height()

    def _render_image_container(self, layout: Optional[QVBoxLayout] = None, smooth_reveal: bool = False):
        if not self.image_data:
            return
        try:
            target_layout = layout or self.layout()
            if self.img_container:
                self.img_container.deleteLater()
                self.img_container = None

            img_bytes = base64.b64decode(self.image_data)
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            if not pixmap.isNull():
                img_container = QWidget()
                self.img_container = img_container
                img_c_layout = QVBoxLayout(img_container)
                img_c_layout.setContentsMargins(0, 4, 0, 8)
                img_c_layout.setSpacing(8)

                scaled_pixmap = pixmap.scaledToWidth(min(600, pixmap.width()), Qt.SmoothTransformation)
                img_label = QLabel()
                img_label.setPixmap(scaled_pixmap)
                img_label.setAlignment(Qt.AlignCenter)
                img_label.setStyleSheet("border: 1px solid rgba(0, 209, 255, 0.35); border-radius: 10px; background-color: #0A0F14; padding: 4px;")
                img_c_layout.addWidget(img_label)

                # Action bar: Save, Copy, View Full
                action_bar = QHBoxLayout()
                action_bar.setSpacing(8)
                action_bar.setAlignment(Qt.AlignLeft)

                btn_style = """
                    QPushButton {
                        background-color: #162033;
                        color: #00D1FF;
                        border: 1px solid rgba(0, 209, 255, 0.3);
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: rgba(0, 209, 255, 0.18);
                        border-color: #00D1FF;
                    }
                """

                save_btn = QPushButton("💾 Save Image")
                save_btn.setStyleSheet(btn_style)
                save_btn.setCursor(Qt.PointingHandCursor)
                save_btn.clicked.connect(lambda: self._save_image(pixmap))
                action_bar.addWidget(save_btn)

                copy_btn = QPushButton("📋 Copy Image")
                copy_btn.setStyleSheet(btn_style)
                copy_btn.setCursor(Qt.PointingHandCursor)
                copy_btn.clicked.connect(lambda: self._copy_image(pixmap, copy_btn))
                action_bar.addWidget(copy_btn)

                view_btn = QPushButton("🔍 View Full")
                view_btn.setStyleSheet(btn_style)
                view_btn.setCursor(Qt.PointingHandCursor)
                view_btn.clicked.connect(lambda: self._view_full_image(pixmap))
                action_bar.addWidget(view_btn)

                action_bar.addStretch()
                img_c_layout.addLayout(action_bar)

                if target_layout:
                    target_layout.addWidget(img_container)

                if smooth_reveal:
                    eff = QGraphicsOpacityEffect(img_container)
                    img_container.setGraphicsEffect(eff)
                    eff.setOpacity(0.0)
                    anim = QPropertyAnimation(eff, b"opacity", img_container)
                    anim.setDuration(320)
                    anim.setStartValue(0.0)
                    anim.setEndValue(1.0)
                    anim.setEasingCurve(QEasingCurve.OutCubic)
                    def _clear_eff():
                        img_container.setGraphicsEffect(None)
                    anim.finished.connect(_clear_eff)
                    img_container._reveal_anim = anim
                    anim.start()
        except Exception:
            pass

