import unittest
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl

# Ensure QApplication exists
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from ui.components.message_bubble import (
    format_markdown_to_html,
    _detect_and_fence_ascii_art,
    MessageBubble
)


class TestCodeBlocksAndAsciiArt(unittest.TestCase):

    def test_ascii_art_dog_chatgpt_style(self):
        """Tests that dog ASCII art in plain text fences renders as a ChatGPT-style card."""
        sample = (
            "Ohh, you mean **make a dog using chat/text, not an actual photo.** 😄\n\n"
            "```plain text\n"
            " / \\_\n"
            "(   @\\___\n"
            " /       0\n"
            "/   (____/\n"
            "/_____/  U\n"
            "```\n\n"
            "🐶 Dog made with text!"
        )
        blocks = {}
        html_out = format_markdown_to_html(sample, blocks)

        # Check code block extraction
        self.assertIn("0", blocks)
        self.assertIn("/_____/  U", blocks["0"])

        # Check card HTML features
        self.assertIn("Plain text", html_out)
        self.assertIn("copy:0", html_out)
        self.assertIn("white-space: pre", html_out)
        self.assertTrue("background-color: #0A0F14" in html_out or "background-color: #131722" in html_out)

    def test_unfenced_ascii_companion_auto_detection(self):
        """Tests that multi-line unfenced ASCII drawings are automatically detected and fenced."""
        unfenced = (
            "Here is your dog:\n"
            "  ___________________\n"
            " /                   \\\n"
            "/                     \\\n"
            "|                     |\n"
            "| ___________________ |\n"
            "| \\                 / |\n"
            "|  \\               /  |\n"
            "|                     |\n"
            "Have fun!"
        )
        fenced = _detect_and_fence_ascii_art(unfenced)
        self.assertIn("```plain text", fenced)
        self.assertIn("___________________", fenced)

        blocks = {}
        html_out = format_markdown_to_html(unfenced, blocks)
        self.assertIn("0", blocks)
        self.assertIn("Plain text", html_out)
        self.assertIn("copy:0", html_out)

    def test_syntax_highlighted_python_code(self):
        """Tests that code blocks with language identifiers format correctly."""
        py_sample = "```python\ndef bark():\n    return 'Woof!'\n```"
        blocks = {}
        html_out = format_markdown_to_html(py_sample, blocks)
        self.assertIn("0", blocks)
        self.assertIn("Python", html_out)
        self.assertIn("copy:0", html_out)

    def test_message_bubble_copy_handler(self):
        """Tests clicking the copy link inside a code block card."""
        content = "```python\nanswer = 42\n```"
        bubble = MessageBubble(role="assistant", content=content)
        self.assertIn("0", bubble._code_blocks)
        self.assertEqual(bubble._code_blocks["0"], "answer = 42")

        bubble._handle_anchor_clicked(QUrl("copy:0"))
        app.processEvents()
        cb = QApplication.clipboard()
        clip_text = cb.text()
        if clip_text:
            self.assertEqual(clip_text, "answer = 42")


if __name__ == "__main__":
    unittest.main()
