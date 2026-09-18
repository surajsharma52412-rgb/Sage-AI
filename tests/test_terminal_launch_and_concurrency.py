"""
Unit tests for silent process execution, concurrency guards, and terminal popup suppression in Sage AI.
"""
import unittest
import threading
import time
from unittest.mock import patch, MagicMock
import subprocess
import os

from engine.ollama_manager import (
    start_ollama_service,
    find_ollama_binary,
    is_ollama_starting,
    _start_lock
)
from engine.providers.ollama_provider import OllamaProvider


class TestTerminalLaunchAndConcurrency(unittest.TestCase):
    """Verifies that terminal popups and duplicate subprocess spawns are completely prevented."""

    def test_find_ollama_binary_gui_priority(self):
        """Verify find_ollama_binary prioritizes GUI app.exe over console ollama.exe."""
        with patch("os.path.isfile") as mock_isfile:
            # Simulate both ollama app.exe and ollama.exe existing
            mock_isfile.side_effect = lambda path: True if ("ollama app.exe" in path or "ollama.exe" in path) else False
            binary = find_ollama_binary()
            self.assertIsNotNone(binary)
            self.assertTrue("app.exe" in binary.lower())

    def test_concurrency_guard_prevents_duplicate_process_spawns(self):
        """Verify calling start_ollama_service concurrently from multiple threads only spawns once."""
        spawn_count = 0
        spawn_lock = threading.Lock()

        def fake_popen(*args, **kwargs):
            nonlocal spawn_count
            with spawn_lock:
                spawn_count += 1
            # Verify Windows-safe creation flags and startupinfo were passed
            if os.name == "nt":
                self.assertEqual(kwargs.get("creationflags"), subprocess.CREATE_NO_WINDOW)
                si = kwargs.get("startupinfo")
                self.assertIsNotNone(si)
                self.assertEqual(si.wShowWindow, subprocess.SW_HIDE)
            return MagicMock()

        # Simulate Ollama starting up and responding after 1 second
        is_running_state = [False]

        def fake_is_running(url="http://127.0.0.1:11434"):
            return is_running_state[0]

        def delayed_server_ready():
            time.sleep(0.8)
            is_running_state[0] = True

        ready_thread = threading.Thread(target=delayed_server_ready)

        with patch("engine.ollama_manager.is_ollama_running", side_effect=fake_is_running), \
             patch("engine.ollama_manager.find_ollama_binary", return_value=r"D:\Ollama\ollama app.exe"), \
             patch("subprocess.Popen", side_effect=fake_popen):

            ready_thread.start()

            # Launch 5 concurrent threads calling start_ollama_service simultaneously
            threads = []
            results = [None] * 5

            def worker(idx):
                results[idx] = start_ollama_service(timeout_sec=5)

            for i in range(5):
                t = threading.Thread(target=worker, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()
            ready_thread.join()

            # Process must ONLY have been spawned once despite 5 concurrent callers!
            self.assertEqual(spawn_count, 1, f"Expected exactly 1 process spawn, but got {spawn_count}")

    def test_ollama_provider_is_available_non_blocking_during_startup(self):
        """Verify OllamaProvider.is_available() does not block when startup is in progress."""
        with patch("engine.providers.ollama_provider.is_ollama_running", return_value=False), \
             patch("engine.providers.ollama_provider.is_ollama_starting", return_value=True), \
             patch("engine.providers.ollama_provider.start_ollama_service") as mock_start:

            provider = OllamaProvider()
            available = provider.is_available()
            self.assertFalse(available)
            # start_ollama_service must NOT be called again if already starting!
            mock_start.assert_not_called()

    def test_only_free_models_returned_in_categorized_models(self):
        """Verify get_categorized_models strictly returns only models where is_free is True."""
        from engine.model_scanner import ModelScanner
        categorized = ModelScanner.get_categorized_models(free_only=True)
        self.assertTrue(len(categorized) > 0)
        for group_name, models in categorized.items():
            for m in models:
                self.assertTrue(
                    m.get("is_free", False),
                    f"Model '{m.get('model_name')}' in group '{group_name}' is not marked as free!"
                )


if __name__ == "__main__":
    unittest.main()
