"""
Unit tests for Live-Thinking Coding Agent Integration in CodingIdeView & live_agent.py.
Verifies:
1. Live-thinking streaming (chain of thought, narration, tool calls, tool results).
2. Live activity bar tracking (ANALYZING, CREATING, EDITING, RUNNING).
3. Live touched files panel tracking with counts and item selection.
4. Live unified diff emission and real-time open document reloads.
5. New chat reset and task cancellation.
"""
import os
import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import Qt

# Ensure QApplication exists for GUI component testing
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ui.components.coding_ide_view import CodingIdeView
from live_agent import (
    ThinkParser, ToolParser, LiveThinkingChat, CodingAgent,
    LiveAgentWorker, InputBox, C_THINK, C_ANS, C_USER, C_OK, C_ERR, C_TOOL, C_RES
)


class TestLiveThinkingCodingAgent(unittest.TestCase):

    def setUp(self):
        self.ide = CodingIdeView()

    def tearDown(self):
        if hasattr(self.ide, "_agent_worker") and self.ide._agent_worker:
            self.ide._agent_worker.stop()
        self.ide.deleteLater()

    def test_think_parser_stream_splitting(self):
        """Verifies ThinkParser correctly separates thinking chunks from visible answer."""
        parser = ThinkParser()
        th1, ans1 = parser.feed("<think>Analyzing user request")
        self.assertIn("Analyzing user request", th1)
        self.assertEqual(ans1, "")

        th2, ans2 = parser.feed(" and checking files.</think>Here is the solution:")
        self.assertIn("and checking files.", th2)
        self.assertIn("Here is the solution:", ans2)

        th_flush, ans_flush = parser.flush()
        self.assertEqual(th_flush, "")
        self.assertEqual(ans_flush, "")

    def test_tool_parser_extraction(self):
        """Verifies ToolParser collects tool JSON blocks and yields surrounding narration."""
        parser = ToolParser()
        vis, tool = parser.feed("I will create the file now.\n<tool>{\"name\": \"write_file\", \"args\": {\"path\": \"app.py\", \"content\": \"print(1)\"}}</tool>")
        self.assertIn("I will create the file now.", vis)
        self.assertIsNotNone(tool)
        self.assertIn("write_file", tool)
        self.assertIn("app.py", tool)

    def test_ide_has_live_thinking_ui_components(self):
        """Verifies CodingIdeView contains all required live-thinking agent UI widgets."""
        self.assertTrue(hasattr(self.ide, "agent_activity_bar"))
        self.assertTrue(hasattr(self.ide, "agent_chat_view"))
        self.assertTrue(hasattr(self.ide, "agent_files_list"))
        self.assertTrue(hasattr(self.ide, "agent_files_header"))
        self.assertTrue(hasattr(self.ide, "agent_input_box"))
        self.assertTrue(hasattr(self.ide, "agent_run_btn"))
        self.assertTrue(hasattr(self.ide, "btn_new_agent"))
        self.assertTrue(hasattr(self.ide, "stop_btn_agent"))
        self.assertTrue(hasattr(self.ide, "chk_shell"))
        self.assertTrue(hasattr(self.ide, "btn_toggle_files"))

        # Check initial activity bar state
        self.assertIn("waiting for a task", self.ide.agent_activity_bar.text())

        # Check initial chat view has welcome HTML
        self.assertIn("Live-Thinking", self.ide.agent_chat_view.toPlainText())

    def test_live_file_event_updates_activity_bar_and_files_list(self):
        """Verifies _on_agent_file_event updates activity bar and populates touched files list."""
        # 1. Analyzing event
        self.ide._on_agent_file_event("analyze", "main.py")
        self.assertIn("ANALYZING", self.ide.agent_activity_bar.text())
        self.assertIn("main.py", self.ide.agent_activity_bar.text())
        self.assertEqual(self.ide.agent_files_list.count(), 1)
        self.assertIn("main.py", self.ide.agent_files_list.item(0).text())

        # 2. Creating event
        self.ide._on_agent_file_event("create", "utils.py")
        self.assertIn("CREATING", self.ide.agent_activity_bar.text())
        self.assertIn("utils.py", self.ide.agent_activity_bar.text())
        self.assertEqual(self.ide.agent_files_list.count(), 2)

        # 3. Editing event
        self.ide._on_agent_file_event("edit", "main.py")
        self.assertIn("EDITING", self.ide.agent_activity_bar.text())
        self.assertIn("main.py", self.ide.agent_activity_bar.text())
        self.assertEqual(self.ide.agent_files_list.count(), 2)
        # Check counts in item description
        item_text = self.ide.agent_files_list.item(0).text()
        self.assertTrue("edited" in item_text or "read" in item_text)

        # 4. Running event (shows in activity bar, but does not pollute files panel)
        self.ide._on_agent_file_event("run", "pytest tests/")
        self.assertIn("RUNNING", self.ide.agent_activity_bar.text())
        self.assertIn("pytest tests/", self.ide.agent_activity_bar.text())
        self.assertEqual(self.ide.agent_files_list.count(), 2)

    def test_live_thinking_stream_and_completion(self):
        """Verifies streaming thinking, answers, tools, and completion stats."""
        # Simulate thinking chunk
        self.ide._on_agent_thinking("Evaluating imports and architecture...")
        self.ide._agent_flush()
        chat_content = self.ide.agent_chat_view.toPlainText()
        self.assertIn("thinking — live", chat_content)
        self.assertIn("Evaluating imports and architecture...", chat_content)

        # Simulate agent answer
        self.ide._on_agent_answer("I will refactor the database connector.")
        self.ide._agent_flush()
        chat_content = self.ide.agent_chat_view.toPlainText()
        self.assertIn("agent", chat_content)
        self.assertIn("I will refactor the database connector.", chat_content)

        # Simulate tool call
        self.ide._on_agent_tool_call("write_file", '{"path": "db.py", "content": "class DB: pass"}')
        chat_content = self.ide.agent_chat_view.toPlainText()
        self.assertIn("write_file", chat_content)

        # Simulate tool result
        self.ide._on_agent_tool_result("OK — wrote 22 chars to db.py")
        chat_content = self.ide.agent_chat_view.toPlainText()
        self.assertIn("result", chat_content)
        self.assertIn("OK — wrote 22 chars", chat_content)

        # Simulate done
        self.ide._on_agent_done("Refactoring completed successfully.", {"tokens": 150, "seconds": 2.5, "steps": 2})
        chat_content = self.ide.agent_chat_view.toPlainText()
        self.assertIn("Refactoring completed successfully.", chat_content)
        self.assertIn("150 tokens", chat_content)
        self.assertIn("2 steps", chat_content)
        self.assertIn("task finished", self.ide.agent_activity_bar.text())

    def test_diff_emitted_and_open_document_reload(self):
        """Verifies diff_emitted updates diff_viewer and reloads open document tabs live."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "app.py"
            p.write_text("print('version 1')", encoding="utf-8")

            self.ide.workspace_path = Path(td)
            self.ide.open_file(p)
            self.assertIn("app.py", self.ide.open_documents)

            # Modify file on disk and emit diff
            p.write_text("print('version 2 - live update')", encoding="utf-8")
            diff_sample = "--- a/app.py\n+++ b/app.py\n-print('version 1')\n+print('version 2 - live update')\n"
            self.ide._on_agent_diff_emitted("app.py", diff_sample)

            # Check diff viewer updated
            diff_view_text = self.ide.diff_viewer.toPlainText()
            self.assertIn("app.py", diff_view_text)
            self.assertIn("+print('version 2 - live update')", diff_view_text)

            # Check editor reloaded live!
            editor = self.ide.open_documents["app.py"].get("editor") or self.ide.editor
            self.assertIn("version 2 - live update", editor.toPlainText())

    def test_new_chat_resets_view_and_state(self):
        """Verifies New button resets agent messages, activity bar, and file list."""
        self.ide._on_agent_file_event("create", "temp.py")
        self.assertEqual(self.ide.agent_files_list.count(), 1)

        self.ide._on_agent_new_chat()
        self.assertEqual(self.ide.agent_files_list.count(), 0)
        self.assertIn("waiting for a task", self.ide.agent_activity_bar.text())
        self.assertEqual(self.ide.agent_status_lbl.text(), "🟢 Ready")

    def test_agent_error_status_and_activity_bar(self):
        """Verifies failure/error displays 'errors' and NOT 'failed' in activity bar and console."""
        self.ide._on_agent_failed("Connection refused by provider")
        activity_text = self.ide.agent_activity_bar.text()
        self.assertIn("errors — see message", activity_text)
        self.assertNotIn("failed", activity_text.lower())
        self.assertIn("ERROR", self.ide.agent_status_lbl.text())
        chat_text = self.ide.agent_chat_view.toPlainText()
        self.assertIn("Connection refused by provider", chat_text)

        # Also verify tests_status_lbl displays 'errors'
        self.assertIn("0 errors", self.ide.tests_status_lbl.text())
        self.assertNotIn("0 failed", self.ide.tests_status_lbl.text())

    def test_tool_fallback_extraction(self):
        """Verifies CodingAgent._extract_tool_fallback correctly parses various model formats."""
        # 1. Unclosed or standard <tool> block
        text1 = "I will write the file now:\n<tool>{\"name\": \"write_file\", \"args\": {\"path\": \"index.html\", \"content\": \"<h1>Hi</h1>\"}}"
        tool1 = CodingAgent._extract_tool_fallback(text1)
        self.assertIsNotNone(tool1)
        self.assertIn("write_file", tool1)
        self.assertIn("index.html", tool1)

        # 2. Markdown codeblock containing json tool
        text2 = "Here is the tool call:\n```json\n{\"name\": \"write_file\", \"args\": {\"path\": \"styles.css\", \"content\": \"body { margin: 0; }\"}}\n```"
        tool2 = CodingAgent._extract_tool_fallback(text2)
        self.assertIsNotNone(tool2)
        self.assertIn("styles.css", tool2)

        # 3. Markdown codeblock with filename header
        text3 = "Here is the javascript code:\n### script.js\n```javascript\nconsole.log('loaded');\n```"
        tool3 = CodingAgent._extract_tool_fallback(text3)
        self.assertIsNotNone(tool3)
        self.assertIn("script.js", tool3)
        self.assertIn("console.log", tool3)

    def test_find_files_tool(self):
        """Verifies find_files tool correctly searches across folders."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            sub = Path(td) / "subdir"
            sub.mkdir()
            (sub / "main.py").write_text("print('test')", encoding="utf-8")
            (td / Path("index.html")).write_text("<h1>test</h1>", encoding="utf-8")

            agent = CodingAgent(workdir=td)
            res = agent._t_find_files({"path": ".", "pattern": "*.py"})
            self.assertIn("main.py", res)
            self.assertNotIn("index.html", res)

    def test_model_selection_updates_ui_and_worker(self):
        """Verifies model selector combo updates model card and routing selection."""
        self.assertTrue(hasattr(self.ide, "agent_model_combo"))
        self.assertGreater(self.ide.agent_model_combo.count(), 1)

        # Change selection to index 1 (e.g. Qwen Coder)
        self.ide.agent_model_combo.setCurrentIndex(1)
        chosen_text = self.ide.agent_model_combo.currentText()
        card_text = self.ide.mic_model_lbl.text()
        self.assertIn("Selected:", card_text)

        # Ensure router selects the model
        m_info = self.ide._coding_router.select_model_for_execution(
            selected_model=self.ide.agent_model_combo.currentData()
        )
        self.assertIsNotNone(m_info.get("selected_model"))


if __name__ == "__main__":
    unittest.main()

