"""
Ollama Service Manager for Sage AI.
Ensures Ollama is automatically launched on application startup,
monitors server health, and auto-discovers installed local models.
"""
import os
import shutil
import subprocess
import threading
import time
import logging
import requests
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Standard installation paths for Ollama on Windows
STANDARD_OLLAMA_PATHS = [
    r"D:\Ollama\ollama app.exe",
    r"D:\Ollama\ollama.exe",
    r"C:\Program Files\Ollama\ollama app.exe",
    r"C:\Program Files\Ollama\ollama.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama app.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
]

_start_lock = threading.Lock()
_is_starting = False
_last_attempt_time = 0.0


def is_ollama_starting() -> bool:
    """Returns True if an Ollama startup sequence is currently underway."""
    global _is_starting
    return _is_starting


def find_ollama_binary() -> Optional[str]:
    """
    Finds the Ollama executable in PATH or standard installation locations.
    Prioritizes 'ollama app.exe' (native Windows GUI runner) over 'ollama.exe' (CLI)
    to prevent console/terminal window flashing.
    """
    # 1. Check standard known paths first (prioritizes GUI app.exe)
    for path in STANDARD_OLLAMA_PATHS:
        if path and os.path.isfile(path):
            return path

    # 2. Check directory of which('ollama') for a sibling 'ollama app.exe'
    which_path = shutil.which("ollama")
    if which_path and os.path.isfile(which_path):
        dir_path = os.path.dirname(which_path)
        gui_candidate = os.path.join(dir_path, "ollama app.exe")
        if os.path.isfile(gui_candidate):
            return gui_candidate
        return which_path

    return None


from urllib.parse import urlparse
import socket

_ollama_running_cache: dict = {}
_ollama_models_cache: dict = {}
_cache_lock = threading.Lock()


def is_ollama_running(base_url: str = "http://127.0.0.1:11434", force_check: bool = False) -> bool:
    """Checks if Ollama REST server is currently responding with fast socket probing and caching."""
    clean_url = base_url.rstrip('/')
    now = time.time()

    if not force_check:
        with _cache_lock:
            if clean_url in _ollama_running_cache:
                cached_time, is_running = _ollama_running_cache[clean_url]
                if now - cached_time < 5.0:
                    return is_running

    # 1. Fast socket probe (< 0.1s) - Prevents multi-second HTTP hangs when offline
    try:
        parsed = urlparse(clean_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        sock = socket.create_connection((host, port), timeout=0.1)
        sock.close()
    except Exception:
        with _cache_lock:
            _ollama_running_cache[clean_url] = (now, False)
        return False

    # 2. Socket connected, confirm HTTP API
    try:
        r = requests.get(f"{clean_url}/api/tags", timeout=0.8)
        is_ok = (r.status_code == 200)
    except Exception:
        is_ok = False

    with _cache_lock:
        _ollama_running_cache[clean_url] = (now, is_ok)
    return is_ok


def get_installed_ollama_models(base_url: str = "http://127.0.0.1:11434", force_check: bool = False) -> List[str]:
    """Fetches list of model names currently installed in local Ollama with caching."""
    clean_url = base_url.rstrip('/')
    now = time.time()

    if not force_check:
        with _cache_lock:
            if clean_url in _ollama_models_cache:
                cached_time, models = _ollama_models_cache[clean_url]
                if now - cached_time < 10.0:
                    return models

    if not is_ollama_running(clean_url, force_check=force_check):
        return []

    try:
        r = requests.get(f"{clean_url}/api/tags", timeout=1.5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            res = [m.get("name") for m in models if m.get("name")]
            with _cache_lock:
                _ollama_models_cache[clean_url] = (now, res)
            return res
    except Exception:
        pass
    return []


def start_ollama_service(base_url: str = "http://127.0.0.1:11434", timeout_sec: int = 8) -> Tuple[bool, str]:
    """
    Automatically starts the Ollama server in the background if not already running.
    Guarantees thread-safe single invocation with no terminal or console window popup.
    Returns: (success: bool, message: str)
    """
    global _is_starting, _last_attempt_time

    # Fast-path check
    if is_ollama_running(base_url):
        models = get_installed_ollama_models(base_url)
        return True, f"Ollama is already running ({len(models)} model(s) available)"

    # If another thread is actively starting it, wait for it instead of spawning duplicate processes
    if _is_starting:
        start_wait = time.time()
        while time.time() - start_wait < timeout_sec:
            time.sleep(0.4)
            if is_ollama_running(base_url):
                models = get_installed_ollama_models(base_url)
                return True, f"Ollama is running ({len(models)} model(s) available)"
            if not _is_starting:
                break
        return is_ollama_running(base_url), "Ollama startup wait completed"

    with _start_lock:
        # Re-check inside lock
        if is_ollama_running(base_url):
            models = get_installed_ollama_models(base_url)
            return True, f"Ollama is already running ({len(models)} model(s) available)"

        # Rate-limit auto-start attempts (at most once every 10 seconds)
        now = time.time()
        if now - _last_attempt_time < 10.0 and _last_attempt_time > 0:
            return False, "Ollama startup was recently attempted. Waiting before retry."
        _last_attempt_time = now

        binary = find_ollama_binary()
        if not binary:
            return False, "Ollama executable not found. Please install Ollama from https://ollama.com"

        _is_starting = True
        try:
            # Build Windows-safe hidden process creation parameters
            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                # CREATE_NO_WINDOW (0x08000000) prevents creating a console window.
                # Do NOT combine with DETACHED_PROCESS as it causes conhost to flash a new console!
                creationflags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            is_gui_app = "app.exe" in binary.lower()
            cmd = [binary] if is_gui_app else [binary, "serve"]

            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
                startupinfo=startupinfo,
                close_fds=True
            )

            # Wait up to timeout_sec for server to respond
            start = time.time()
            while time.time() - start < timeout_sec:
                time.sleep(0.5)
                if is_ollama_running(base_url):
                    models = get_installed_ollama_models(base_url)
                    return True, f"Ollama auto-started successfully! Found models: {', '.join(models) if models else 'None'}"

            return False, f"Ollama started at {binary}, but port 11434 didn't respond within {timeout_sec}s."
        except Exception as e:
            return False, f"Failed to auto-start Ollama: {str(e)}"
        finally:
            _is_starting = False

