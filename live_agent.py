#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧠 LIVE-THINKING — ALL-IN-ONE (library + coding agent + GUI)
======================================================================

THIS MODULE GIVES YOU THREE CAPABILITIES:

1) A GUI CODING AGENT — run standalone or within the IDE:
       python live_agent.py
   → live thinking stream + LIVE FILE ACTIVITY: a bar always shows which file
     the agent is currently ANALYZING / CREATING / EDITING / RUNNING,
     plus a side panel listing every file it has touched so far.

2) A SIMPLE CHAT LIBRARY — import into YOUR program:
       from live_agent import LiveThinkingChat
       bot = LiveThinkingChat("qwen3:4b")
       answer, thinking = bot.ask("why is the sky blue?")

3) A HEADLESS CODING AGENT — import into YOUR program (no GUI):
       from live_agent import CodingAgent
       agent = CodingAgent("qwen3:4b", workdir="my_folder", allow_shell=False)
       final = agent.run("create hello.py that prints the current time")

SAFETY: the agent can only touch files inside its work folder, and
shell commands only run if you allow them.
"""

import difflib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html import escape as _esc
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# GUI libraries — optional (file still imports fine without them)
try:
    from PySide6.QtCore import Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QFont
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
        QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit,
        QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget, QFrame
    )
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

# ─────────────────────────── settings ───────────────────────────
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:4b"                 # bigger = better agent
MODEL_CHOICES = [
    "Auto Router",
    "Pareto 26.9 (Union Alpha)",
    "qwen3:4b",
    "qwen3:8b",
    "qwen3:14b",
    "deepseek-r1:7b",
    "qwen2.5-coder:7b",
    "DeepSeek R1",
    "Qwen 2.5 Coder 32B",
    "Mistral Codestral 22B",
    "Google Gemini 2.0 Flash",
]
TEMPERATURE = 0.4
NUM_CTX = 8192
MAX_STEPS = 40                         # agent loop limit (supports multi-file & full projects)
READ_LIMIT = 32000                     # max chars read_file returns
CMD_TIMEOUT = 90                       # seconds per shell command

SYSTEM_PROMPT = "You are an autonomous expert coding assistant. Build and modify projects step by step using tools."

TOOLS = {"list_dir", "find_files", "read_file", "write_file", "replace_in_file", "run_command"}

AGENT_PROMPT = """You are an autonomous expert software engineering agent. You work inside this folder:
__FOLDER__

You build, modify, debug, and manage codebases step by step using tools.

CRITICAL INSTRUCTIONS FOR FILE OPERATIONS:
1. You MUST call tools to inspect, create, or modify files. Plain text or markdown code blocks DO NOT create files on disk.
2. NEVER merely say "I will create index.html" without invoking the write_file tool.
3. To call a tool, output ONE block in this exact format:
<tool>{"name": "tool_name", "args": { ... }}</tool>

AVAILABLE TOOLS:
- list_dir        {"path": "."}
      List files and folders in a directory.
- find_files      {"path": ".", "pattern": "*.*"}
      Recursively search for files matching a pattern (e.g. "*.py", "*.html", "*.css", "*.js").
- read_file       {"path": "main.py", "offset": 0, "limit": 32000}
      Read content of a text file (supports optional offset and limit for large files).
- write_file      {"path": "index.html", "content": "<!DOCTYPE html>\\n..."}
      Create or overwrite a file with its FULL content. Automatically creates parent directories.
- replace_in_file {"path": "main.py", "old": "...", "new": "..."}
      Replace exact text inside a file ('old' must match exactly).
- run_command     {"command": "python hello.py"}
      Run a shell command in the work folder (90s timeout).
      run_command is: __SHELL__

RULES FOR LARGE & MULTI-FILE PROJECTS:
- When asked to build a project, website, or application (e.g. HTML, CSS, JavaScript, backend, tests):
  DO NOT STOP after creating just one file! You must create ALL necessary files sequentially, one tool call per turn.
- Step-by-step workflow:
  1. Inspect existing files if relevant (list_dir or find_files).
  2. Create or update each file using write_file (always provide complete, functional, production-ready code — NO placeholders).
  3. Verify files (re-read or run commands if shell is enabled).
- ONLY when all files in the project are created, tested, and verified on disk, reply with your final completion summary as plain text with NO <tool> block."""

# chat-view colors (GUI)
C_THINK, C_ANS, C_USER = "#818cf8", "#e2e8f0", "#38bdf8"
C_FAINT, C_ACC, C_OK, C_ERR = "#64748b", "#00D1FF", "#10b981", "#f43f5e"
C_TOOL, C_RES = "#fbbf24", "#2dd4bf"

HTML_WELCOME = (
    '<div style="margin:6px">'
    f'<span style="color:{C_ACC}; font-size:16px; font-weight:bold">🧠 Live-Thinking Autonomous Coding Agent</span><br>'
    '<span style="color:#94a3b8">The gray/indigo italic block is the agent\'s '
    '<b>live chain-of-thought reasoning</b>. It can <b>list, read, write and edit '
    'files</b> (and run shell commands if permitted).</span><br>'
    f'<span style="color:{C_TOOL}">🔧 yellow = tool calls</span> · '
    f'<span style="color:{C_RES}">📄 teal = tool results</span> · '
    'the bar above shows <b>which file it is working on right now</b><br>'
    f'<span style="color:{C_FAINT}">Sandboxed to the workspace folder.</span></div>'
)

HTML_SERVER_DOWN = (
    f'<div style="margin:8px; color:{C_ERR}">⚠ Cannot reach Ollama at {OLLAMA_URL}</div>'
    '<div style="margin-left:8px; color:#94a3b8">'
    '1. Install Ollama → https://ollama.com/download<br>'
    '2. Start it → run <b>ollama serve</b> (or open the Ollama desktop app)<br>'
    f'3. Pull a model → <b>ollama pull {DEFAULT_MODEL}</b><br>'
    f'<span style="color:{C_FAINT}">Tip: Or select a Cloud model in the model dropdown if API keys are configured in Settings.</span></div>'
)


class OllamaError(RuntimeError):
    """Any problem talking to model provider. str(e) is already human-friendly."""


def server_version(url: str = OLLAMA_URL, timeout: float = 2.5) -> Optional[str]:
    """Return the Ollama version string, or None if unreachable."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/version")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace")).get("version")
    except Exception:
        return None


# ─────────────────── parse reasoning while streaming ───────────────────
class ThinkParser:
    """Splits a streamed reply into (thinking, answer) pieces.
    The <think> ... </think> tags can arrive split across network chunks."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.state = "start"          # start → thinking → answer
        self.buf = ""

    def feed(self, text: str) -> Tuple[str, str]:
        think, ans = "", ""
        self.buf += text
        while True:
            if self.state == "start":
                self.buf = self.buf.lstrip()
                if not self.buf:
                    break
                if len(self.buf) < len(self.OPEN) and self.OPEN.startswith(self.buf):
                    break              # maybe a partial tag → wait
                if self.buf.startswith(self.OPEN):
                    self.buf = self.buf[len(self.OPEN):]
                    self.state = "thinking"
                    continue
                self.state = "answer"  # no thinking block
                continue
            if self.state == "thinking":
                i = self.buf.find(self.CLOSE)
                if i != -1:
                    think += self.buf[:i]
                    self.buf = self.buf[i + len(self.CLOSE):]
                    self.state = "answer"
                    continue
                hold = self._partial_suffix(self.buf, self.CLOSE)
                if hold:
                    think += self.buf[:-hold]
                    self.buf = self.buf[-hold:]
                else:
                    think += self.buf
                    self.buf = ""
                break
            ans += self.buf            # state == "answer"
            self.buf = ""
            break
        return think, ans

    def flush(self) -> Tuple[str, str]:
        rest, self.buf = self.buf, ""
        if self.state == "thinking":
            return rest, ""
        self.state = "answer"
        return "", rest

    @staticmethod
    def _partial_suffix(buf: str, tag: str) -> int:
        for k in range(min(len(buf), len(tag) - 1), 0, -1):
            if tag.startswith(buf[-k:]):
                return k
        return 0


# ─────────────── parse <tool>{...}</tool> blocks in the answer ───────────────
class ToolParser:
    """Splits the model's visible answer from tool-call blocks.
    Emits plain text live; collects each <tool>…</tool> JSON whole."""

    OPEN, CLOSE = "<tool>", "</tool>"

    def __init__(self):
        self.state = "text"
        self.buf = ""
        self.tool = ""

    def feed(self, text: str) -> Tuple[str, Optional[str]]:
        vis, done_tool = "", None
        self.buf += text
        while True:
            if self.state == "text":
                i = self.buf.find(self.OPEN)
                if i != -1:
                    vis += self.buf[:i]
                    self.buf = self.buf[i + len(self.OPEN):]
                    self.state = "tool"
                    continue
                hold = self._partial_suffix(self.buf, self.OPEN)
                if hold:
                    vis += self.buf[:-hold]
                    self.buf = self.buf[-hold:]
                else:
                    vis += self.buf
                    self.buf = ""
                break
            # state == "tool"
            i = self.buf.find(self.CLOSE)
            if i != -1:
                self.tool += self.buf[:i]
                self.buf = self.buf[i + len(self.CLOSE):]
                done_tool, self.tool = self.tool, ""
                self.state = "text"
                continue
            hold = self._partial_suffix(self.buf, self.CLOSE)
            if hold:
                self.tool += self.buf[:-hold]
                self.buf = self.buf[-hold:]
            else:
                self.tool += self.buf
                self.buf = ""
            break
        return vis, done_tool

    def flush(self) -> Tuple[str, Optional[str]]:
        if self.state == "tool":       # unterminated block → return what we have
            t = self.tool + self.buf
            self.tool, self.buf = "", ""
            self.state = "text"
            return "", t
        vis, self.buf = self.buf, ""
        return vis, None

    @staticmethod
    def _partial_suffix(buf: str, tag: str) -> int:
        for k in range(min(len(buf), len(tag) - 1), 0, -1):
            if tag.startswith(buf[-k:]):
                return k
        return 0


# ─────────────────────────── multi-provider streaming ───────────────────────────
def _get_cloud_credentials(model: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (provider, api_key, endpoint_model) if available in database or env."""
    try:
        from database.db_manager import get_db
        db = get_db()
    except Exception:
        db = None

    def get_key(k: str) -> str:
        if db:
            val = db.get_setting(k, "") or ""
            if val.strip():
                return val.strip()
        return os.environ.get(k.upper(), "").strip()

    m_lower = model.lower()

    # 1. Explicit provider prefixes
    if m_lower.startswith("groq/"):
        groq_key = get_key("groq_api_key")
        if groq_key:
            return "groq", groq_key, model.split("/", 1)[1]
    if m_lower.startswith("nvidia/"):
        nvidia_key = get_key("nvidia_api_key")
        if nvidia_key:
            return "nvidia", nvidia_key, model.split("/", 1)[1]
    if m_lower.startswith("gemini/") or m_lower.startswith("google/"):
        gemini_key = get_key("gemini_api_key")
        if gemini_key:
            g_mod = model.split("/", 1)[1]
            return "gemini", gemini_key, g_mod if "gemini" in g_mod else "gemini-2.0-flash"

    # 2. OpenRouter (primary multi-model cloud provider)
    openrouter_key = get_key("openrouter_api_key")
    if openrouter_key:
        # Normalize deprecated :free slugs or aliases to active versions
        slug = model
        if slug in ("unbiased/union-alpha", "openrouter/pareto-code"):
            slug = "unbiased/pareto"
        elif slug.endswith(":free"):
            base_slug = slug[:-5]
            if base_slug in (
                "deepseek/deepseek-r1",
                "qwen/qwen-2.5-coder-32b-instruct",
                "deepseek/deepseek-chat",
                "meta-llama/llama-3.3-70b-instruct",
            ):
                slug = base_slug

        # Check Union Alpha / Pareto recognition
        if "union" in m_lower or "pareto" in m_lower:
            return "openrouter", openrouter_key, "unbiased/pareto"

        # If a provider-qualified model ID was provided directly (e.g. deepseek/deepseek-r1, qwen/qwen-2.5-coder-32b-instruct)
        if "/" in slug and not slug.startswith("ollama/"):
            return "openrouter", openrouter_key, slug

        if "qwen" in m_lower:
            return "openrouter", openrouter_key, "qwen/qwen-2.5-coder-32b-instruct"
        if "r1" in m_lower:
            return "openrouter", openrouter_key, "deepseek/deepseek-r1"
        if "deepseek" in m_lower:
            return "openrouter", openrouter_key, "deepseek/deepseek-chat"
        if "claude" in m_lower:
            return "openrouter", openrouter_key, "anthropic/claude-3.5-sonnet"
        if "codestral" in m_lower:
            return "openrouter", openrouter_key, "mistralai/codestral-2501"
        if "llama" in m_lower:
            return "openrouter", openrouter_key, "meta-llama/llama-3.3-70b-instruct"

        # Default OpenRouter coding model (top benchmark performer)
        configured_or = get_key("openrouter_model")
        return "openrouter", openrouter_key, configured_or if configured_or and "/" in configured_or else "qwen/qwen-2.5-coder-32b-instruct"

    # 3. Groq (only if openrouter not present or groq explicitly matched)
    groq_key = get_key("groq_api_key")
    if groq_key and ("groq" in m_lower or "llama" in m_lower):
        return "groq", groq_key, "llama-3.3-70b-versatile"

    # 4. NVIDIA
    nvidia_key = get_key("nvidia_api_key")
    if nvidia_key and ("nvidia" in m_lower or "deepseek" in m_lower):
        return "nvidia", nvidia_key, "deepseek-ai/deepseek-r1"

    # 5. Gemini
    gemini_key = get_key("gemini_api_key")
    if gemini_key and ("gemini" in m_lower or "google" in m_lower):
        return "gemini", gemini_key, "gemini-2.0-flash"

    # Fallback any configured key
    for prov, k, default_m in [
        ("openrouter", "openrouter_api_key", "qwen/qwen-2.5-coder-32b-instruct"),
        ("groq", "groq_api_key", "llama-3.3-70b-versatile"),
        ("nvidia", "nvidia_api_key", "deepseek-ai/deepseek-r1"),
        ("gemini", "gemini_api_key", "gemini-2.0-flash")
    ]:
        val = get_key(k)
        if val:
            return prov, val, default_m

    return None, None, None


def stream_chat(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    url: str = OLLAMA_URL,
    temperature: float = TEMPERATURE,
    num_ctx: int = NUM_CTX,
    should_stop=None
):
    """Core: stream one chat completion from Ollama or connected Cloud Providers.

    Yields live events:
        ("thinking", "chunk…")   the model's private reasoning
        ("answer",   "chunk…")   the visible answer
        ("done", {"tokens": int, "seconds": float})

    Raises OllamaError on any unrecoverable problem.
    """
    # Clean up model name
    clean_model = model.split("[")[0].replace("⚡", "").replace("👑", "").replace("💻", "").replace("🚀", "").replace("✨", "").replace("🧠", "").replace("🔒", "").strip()
    if clean_model.startswith("ollama/"):
        clean_model = clean_model[len("ollama/"):]

    # Resolve Ollama base URL if in Sage environment
    try:
        from database.db_manager import get_db
        configured_url = get_db().get_setting("ollama_base_url")
        if configured_url:
            url = configured_url.rstrip("/")
    except Exception:
        pass

    # Check if local Ollama is active
    ollama_online = server_version(url, timeout=1.5) is not None
    is_explicit_cloud = any(k in clean_model.lower() for k in (
        "claude", "openrouter", "groq", "gemini", "nvidia", "codestral",
        "deepseek/", "qwen/", "meta-llama/", "mistralai/", "google/",
        "anthropic/", ":free", "cerebras/", "union", "pareto"
    ))

    # 1. Stream via Ollama if online and not explicitly forced cloud
    if ollama_online and not is_explicit_cloud:
        # If model is still "Auto Router" at this layer, find a local model instead of hardcoding DEFAULT_MODEL
        if clean_model in ("Auto Router", "Auto — Best Coding Model", "Auto - Best Coding Model"):
            try:
                tag_req = urllib.request.Request(f"{url}/api/tags")
                with urllib.request.urlopen(tag_req, timeout=3) as r:
                    tags_data = json.loads(r.read().decode("utf-8", "replace"))
                    local_models = [m.get("name", "") for m in tags_data.get("models", [])]
                    target_ollama_model = local_models[0] if local_models else DEFAULT_MODEL
            except Exception:
                target_ollama_model = DEFAULT_MODEL
        else:
            target_ollama_model = clean_model
        parser = ThinkParser()
        body = json.dumps({
            "model": target_ollama_model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )

        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("error", detail)
            except Exception:
                pass
            if "not found" in detail.lower():
                detail += f" — pull it first: ollama pull {target_ollama_model}"
            raise OllamaError(f"HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise OllamaError(f"cannot reach Ollama at {url} ({e.reason})") from None

        tokens, seconds = 0, 0.0
        try:
            with resp:
                for raw_line in resp:
                    if should_stop is not None and should_stop():
                        break
                    line = raw_line.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise OllamaError(data["error"])

                    msg = data.get("message") or {}
                    if msg.get("thinking"):          # Ollama thinking field
                        yield "thinking", msg["thinking"]
                    if msg.get("content"):           # Standard content / <think> tags
                        th, ans = parser.feed(msg["content"])
                        if th:
                            yield "thinking", th
                        if ans:
                            yield "answer", ans
                    if data.get("done"):
                        tokens = data.get("eval_count") or 0
                        seconds = (data.get("eval_duration") or 0) / 1e9
                        break

            th, ans = parser.flush()
            if th:
                yield "thinking", th
            if ans:
                yield "answer", ans
        except OllamaError:
            raise
        except Exception as e:
            raise OllamaError(f"Stream errors: {type(e).__name__}: {e}") from None

        yield "done", {"tokens": tokens, "seconds": seconds}
        return

    # 2. Stream via Cloud Providers (OpenRouter, Groq, NVIDIA) if Ollama offline or cloud model requested
    prov, api_key, cloud_model = _get_cloud_credentials(clean_model)
    if prov and api_key:
        # Zero-Cost Guard Architecture: Always scan model before sending request to guarantee 0 Rs cost
        try:
            from engine.zero_cost_guard import get_zero_cost_guard
            guard = get_zero_cost_guard()
            if not guard.is_zero_cost(cloud_model, prov):
                # Request MUST NOT continue with paid model! Automatically shift to verified free one
                f_model, f_prov, _ = guard.resolve_free_model(cloud_model, task_type="coding")
                yield "thinking", f"🛡️ Free Model Scanner: Scanned model '{cloud_model}' (> 0 Rs). Automatically shifted to 100% Free model '{f_model}' ({f_prov.title()} • 0 Rs)...\n"
                cloud_model = f_model
                if f_prov != prov:
                    new_prov, new_key, _ = _get_cloud_credentials(f_prov)
                    if new_prov and new_key:
                        prov, api_key = new_prov, new_key
        except Exception:
            pass

        parser = ThinkParser()
        endpoint_map = {
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
        }
        api_url = endpoint_map.get(prov, endpoint_map["openrouter"])
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/sage-ai",
            "X-Title": "Sage AI Live-Thinking Coding Agent"
        }
        cloud_payload = {
            "model": cloud_model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        body = json.dumps(cloud_payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")

        t0 = time.time()
        tokens = 0
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            with resp:
                for raw_line in resp:
                    if should_stop is not None and should_stop():
                        break
                    line = raw_line.decode("utf-8", "replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload_str = line[5:].strip()
                    if payload_str == "[DONE]":
                        break
                    try:
                        chunk_obj = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk_obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}

                    # Check reasoning content field (DeepSeek R1 on Groq/OpenRouter)
                    r_chunk = delta.get("reasoning_content") or delta.get("reasoning")
                    if r_chunk:
                        yield "thinking", r_chunk

                    # Check standard content
                    c_chunk = delta.get("content")
                    if c_chunk:
                        tokens += 1
                        th, ans = parser.feed(c_chunk)
                        if th:
                            yield "thinking", th
                        if ans:
                            yield "answer", ans

            th, ans = parser.flush()
            if th:
                yield "thinking", th
            if ans:
                yield "answer", ans
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "replace")
            # Zero-Cost Guard: Always scan and shift to next 100% Free model if payment required or model unavailable
            is_payment_issue = (
                e.code in (402, 403, 404)
                or any(k in err_body.lower() for k in (
                    "unavailable for free", "paid version", "requires credit",
                    "can only afford", "insufficient balance", "no endpoints"
                ))
            )
            if is_payment_issue:
                try:
                    from engine.zero_cost_guard import get_zero_cost_guard
                    guard = get_zero_cost_guard()
                    free_queue = guard.get_free_waterfall_queue(task_type="coding", excluded_models=[cloud_model, clean_model, model])
                    for cand_m, cand_p, _ in free_queue:
                        if not guard.is_zero_cost(cand_m, cand_p):
                            continue
                        c_prov, c_key, _ = _get_cloud_credentials(cand_m)
                        if c_prov and c_key:
                            yield "thinking", f"🛡️ Free Model Scanner: Intercepted non-free/unavailable state on '{cloud_model}'. Automatically shifting to next 0 Rs free model '{cand_m}' ({c_prov.title()})...\n"
                            for item in stream_chat(
                                messages=messages,
                                model=cand_m,
                                url=url,
                                temperature=temperature,
                                num_ctx=num_ctx,
                                should_stop=should_stop
                            ):
                                yield item
                            return
                        elif cand_p == "ollama" and ollama_online:
                            yield "thinking", f"🛡️ Free Model Scanner: Shifting to verified 100% Free offline model '{cand_m}' on Ollama (0 Rs)...\n"
                            for item in stream_chat(
                                messages=messages,
                                model=cand_m,
                                url=url,
                                temperature=temperature,
                                num_ctx=num_ctx,
                                should_stop=should_stop
                            ):
                                yield item
                            return
                except Exception as ex:
                    pass
            elif e.code == 402:
                # Handle token budget constraints: "can only afford 9213"
                m_afford = re.search(r"can only afford (\d+)", err_body)
                if m_afford:
                    afford_tok = int(m_afford.group(1))
                    if afford_tok > 500:
                        safe_budget = min(4096, afford_tok - 200)
                        yield "thinking", f"Adjusting token budget to {safe_budget} tokens to fit balance...\n"
                        cloud_payload["max_tokens"] = safe_budget
                        retry_body = json.dumps(cloud_payload).encode("utf-8")
                        retry_req = urllib.request.Request(api_url, data=retry_body, headers=headers, method="POST")
                        try:
                            r_resp = urllib.request.urlopen(retry_req, timeout=300)
                            with r_resp:
                                for raw_line in r_resp:
                                    if should_stop is not None and should_stop():
                                        break
                                    line = raw_line.decode("utf-8", "replace").strip()
                                    if not line or not line.startswith("data:"):
                                        continue
                                    payload_str = line[5:].strip()
                                    if payload_str == "[DONE]":
                                        break
                                    try:
                                        chunk_obj = json.loads(payload_str)
                                    except json.JSONDecodeError:
                                        continue
                                    choices = chunk_obj.get("choices") or []
                                    if not choices:
                                        continue
                                    delta = choices[0].get("delta") or {}
                                    r_chunk = delta.get("reasoning_content") or delta.get("reasoning")
                                    if r_chunk:
                                        yield "thinking", r_chunk
                                    c_chunk = delta.get("content")
                                    if c_chunk:
                                        tokens += 1
                                        th, ans = parser.feed(c_chunk)
                                        if th:
                                            yield "thinking", th
                                        if ans:
                                            yield "answer", ans
                            th, ans = parser.flush()
                            if th:
                                yield "thinking", th
                            if ans:
                                yield "answer", ans
                            elapsed = time.time() - t0
                            yield "done", {"tokens": tokens, "seconds": elapsed}
                            return
                        except Exception:
                            pass
            raise OllamaError(f"Cloud {prov.title()} error ({e.code}): {err_body}") from None
        except Exception as e:
            raise OllamaError(f"Cloud provider connection errors: {e}") from None

        elapsed = time.time() - t0
        yield "done", {"tokens": tokens, "seconds": elapsed}
        return

    # 3. Neither Ollama nor Cloud available
    raise OllamaError(
        f"Cannot connect to Ollama at {url}, and no cloud API keys (OpenRouter/Groq/NVIDIA) were found. "
        f"Please start Ollama (`ollama serve`) or configure API keys in Settings."
    )


# ─────────────────── simple chat wrapper (library) ───────────────────
class LiveThinkingChat:
    """Multi-turn chat with live thinking — no tools, no GUI.

        bot = LiveThinkingChat("qwen3:4b")
        answer, thinking = bot.ask("why is the sky blue?")
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
        url: str = OLLAMA_URL,
        temperature: float = TEMPERATURE,
        num_ctx: int = NUM_CTX
    ):
        self.model = model
        self.url = url
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.messages: List[Dict[str, str]] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def reset(self):
        """Clear the conversation (keeps the system prompt)."""
        self.messages = [m for m in self.messages if m["role"] == "system"]

    def stream(self, user_message: str):
        """Send a message and yield ('thinking'|'answer'|'done', text) live."""
        self.messages.append({"role": "user", "content": user_message})
        answer_parts = []
        try:
            for event in stream_chat(
                self.messages, model=self.model, url=self.url,
                temperature=self.temperature, num_ctx=self.num_ctx
            ):
                if event[0] == "answer":
                    answer_parts.append(event[1])
                yield event
        except BaseException:
            self._drop_last_user_turn()
            raise
        answer = "".join(answer_parts)
        if answer:
            self.messages.append({"role": "assistant", "content": answer})
        else:
            self._drop_last_user_turn()

    def ask(self, user_message: str, on_thinking=None, on_answer=None) -> Tuple[str, str]:
        """Blocking helper → (answer, thinking). Optional live callbacks."""
        thinking_parts, answer_parts = [], []
        for kind, text in self.stream(user_message):
            if kind == "thinking":
                thinking_parts.append(text)
                if on_thinking:
                    on_thinking(text)
            elif kind == "answer":
                answer_parts.append(text)
                if on_answer:
                    on_answer(text)
        return "".join(answer_parts), "".join(thinking_parts)

    def _drop_last_user_turn(self):
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()


# ─────────────────── the coding agent (library & engine) ───────────────────
class CodingAgent:
    """The full coding-agent loop with live thinking and real file tools.

    Safety: file tools are sandboxed to `workdir`; run_command only
    runs when allow_shell=True. agent.stop() cancels a running task.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        workdir: str = ".",
        allow_shell: bool = False,
        url: str = OLLAMA_URL,
        temperature: float = TEMPERATURE,
        num_ctx: int = NUM_CTX,
        max_steps: int = MAX_STEPS
    ):
        self.model = model
        self.workdir = os.path.realpath(workdir)
        self.allow_shell = bool(allow_shell)
        self.url = url
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.max_steps = max_steps
        self.messages: List[Dict[str, str]] = []
        self.tokens = 0
        self.seconds = 0.0
        self.steps_used = 0
        self.last_note: Optional[str] = None
        self._stop = False
        self._on_diff_callback = None
        self._has_executed_any_file_change = False
        self._execution_retries = 0

    def stop(self):
        """Ask the agent to stop (checked between chunks, tools and steps)."""
        self._stop = True

    def set_diff_callback(self, callback):
        self._on_diff_callback = callback

    def run(
        self,
        task: str,
        on_thinking=None,
        on_answer=None,
        on_tool_call=None,
        on_tool_result=None,
        on_step=None,
        on_file_event=None
    ) -> str:
        """Run the agent on a task → final answer text (str)."""
        self._stop = False
        self.tokens, self.seconds = 0, 0.0
        self.steps_used = 0
        self.last_note = None
        self._has_executed_any_file_change = False
        self._execution_retries = 0
        self._prepare_system_prompt()
        if task:
            self.messages.append({"role": "user", "content": task})

        step = 0
        while step < self.max_steps and not self._stop:
            step += 1
            self.steps_used = step
            if on_step:
                on_step(step)

            narration, tool_json = self._call_model(on_thinking, on_answer)

            if self._stop:
                self.last_note = "stopped by user"
                return (narration or "").strip()

            # 1. If tool_json was not captured by streaming ToolParser, run fallback extractor
            if not tool_json:
                tool_json = self._extract_tool_fallback(narration)

            # 2. Execution Enforcement: check if model merely described files or showed code without calling tools
            if not tool_json:
                n_lower = (narration or "").lower()
                has_code_intent = any(k in n_lower for k in (
                    "i will create", "i'll create", "let's create", "first, create", "creating file",
                    "here is the code", "here is the html", "here's the file", "```html", "```python",
                    "```javascript", "```css", "```js", "next step", "let's start by", "i'll build",
                    "create the following", "let us create"
                ))
                task_lower = (task or "").lower()
                action_task = any(k in task_lower for k in (
                    "create", "build", "make", "write", "website", "project", "app", "code", "generate", "fix", "add"
                ))

                # If no files have been created yet, or the model is describing files it plans to create:
                if (has_code_intent or (action_task and not self._has_executed_any_file_change)) and self._execution_retries < 3:
                    self._execution_retries += 1
                    if narration.strip():
                        self.messages.append({"role": "assistant", "content": narration.strip()})
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "ACTION REQUIRED: You provided text or described files, but you DID NOT execute any tool. "
                            "Plain text in chat DOES NOT write or modify files on disk.\n"
                            "You MUST execute a tool right now to actually save the file on disk using this exact format:\n"
                            "<tool>{\"name\": \"write_file\", \"args\": {\"path\": \"<filename>\", \"content\": \"<full content>\"}}</tool>\n"
                            "Execute the tool now."
                        )
                    })
                    continue

                # Plain reply with no pending execution -> finished
                final = (narration or "").strip()
                if final:
                    self.messages.append({"role": "assistant", "content": final})
                return final or "(task complete)"

            self.messages.append({
                "role": "assistant",
                "content": ((narration.strip() + "\n") if narration.strip() else "")
                           + f"<tool>{tool_json}</tool>"
            })

            name, args, perr = self._parse_tool(tool_json)
            if perr:
                result = f"ERROR (bad tool call): {perr}"
            else:
                if on_tool_call:
                    on_tool_call(name, args)
                if on_file_event:
                    kind, target = self._file_event(name, args)
                    on_file_event(kind, target)
                if name == "run_command" and not self.allow_shell:
                    result = ("ERROR: shell commands are disabled — "
                              "use the file tools instead.")
                else:
                    result = self._run_tool(name, args)
                    if name in ("write_file", "replace_in_file") and "OK" in result:
                        self._has_executed_any_file_change = True

            if on_tool_result:
                on_tool_result(result)

            # System continuation hint for multi-file projects
            continuation_hint = ""
            if name == "write_file" and "OK" in result:
                continuation_hint = (
                    "\n[System Note: If building a multi-file project or website, proceed to create the next file "
                    "(e.g. CSS, JS, backend, assets) using <tool>{\"name\": \"write_file\", ...}</tool>. "
                    "Only stop when ALL files are written and verified on disk.]"
                )

            self.messages.append({"role": "user", "content": f"TOOL RESULT:\n{result}{continuation_hint}"})

        if self._stop:
            self.last_note = "stopped by user"
            return ""

        # Step limit reached → force a final plain answer
        self.last_note = "step limit reached"
        self.messages.append({
            "role": "user",
            "content": "STEP LIMIT REACHED — provide your final summary now as plain text. Do NOT call any tools."
        })
        narration, _tool = self._call_model(on_thinking, on_answer)
        final = (narration or "").strip()
        if final:
            self.messages.append({"role": "assistant", "content": final})
        return final or "(step limit reached)"

    @staticmethod
    def _extract_tool_fallback(text: str) -> Optional[str]:
        """Secondary extractor if streaming ToolParser didn't catch the block."""
        if not text:
            return None

        # 1. Check for standard <tool>...</tool> or unclosed <tool>...
        m_tool = re.search(r"<tool>\s*(\{.*?\})\s*(?:</tool>|$)", text, re.DOTALL)
        if m_tool:
            return m_tool.group(1).strip()

        # 2. Check for markdown code blocks with json or tool containing a tool name
        code_blocks = re.findall(r"```(?:json|tool|xml)?\s*\n?(\{.*?\})\s*```", text, re.DOTALL)
        for block in code_blocks:
            try:
                candidate = json.loads(block.strip())
                if isinstance(candidate, dict):
                    name = candidate.get("name") or candidate.get("tool") or candidate.get("action")
                    if name in TOOLS:
                        return json.dumps(candidate)
            except Exception:
                pass

        # 3. Check for bare JSON object containing tool name
        m_bare = re.search(
            r'\{\s*"(?:name|tool|action)"\s*:\s*"(list_dir|find_files|read_file|write_file|replace_in_file|run_command)"\s*,\s*"(?:args|parameters|arguments)"\s*:\s*\{.*?\}\s*\}',
            text, re.DOTALL
        )
        if m_bare:
            return m_bare.group(0).strip()

        # 4. Check for markdown file blocks: e.g. ### index.html \n ```html ... ``` or **styles.css** \n ```css ...
        file_block_m = re.search(
            r'(?:###?|\*\*|File:?|[\d]+\.|\bcreate\b|\bfile\b)?\s*[`*]*([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)[`*]*\s*:?\s*[\r\n]+```[a-zA-Z0-9_\-]*[\r\n]+(.*?)```',
            text, re.DOTALL | re.IGNORECASE
        )
        if file_block_m:
            fpath = file_block_m.group(1).strip()
            fcontent = file_block_m.group(2)
            ext = os.path.splitext(fpath)[1].lower()
            if ext in (".html", ".css", ".js", ".ts", ".py", ".json", ".sql", ".md", ".txt", ".sh", ".jsx", ".tsx"):
                synth = {"name": "write_file", "args": {"path": fpath, "content": fcontent}}
                return json.dumps(synth)

        return None

    def _call_model(self, on_thinking, on_answer) -> Tuple[str, Optional[str]]:
        """One streamed model call → (narration, tool_json or None)."""
        xp = ToolParser()
        narration: List[str] = []
        tool_json: Optional[str] = None

        def handle(ans):
            nonlocal tool_json
            vis, tj = xp.feed(ans)
            if vis:
                narration.append(vis)
                if on_answer:
                    on_answer(vis)
            if tj and tool_json is None:
                tool_json = tj

        for kind, payload in stream_chat(
            self.messages, model=self.model, url=self.url,
            temperature=self.temperature, num_ctx=self.num_ctx,
            should_stop=lambda: self._stop
        ):
            if kind == "thinking":
                if on_thinking:
                    on_thinking(payload)
            elif kind == "answer":
                handle(payload)
            elif kind == "done":
                self.tokens += payload.get("tokens") or 0
                self.seconds += payload.get("seconds") or 0.0

        vis, tj = xp.flush()
        if vis:
            narration.append(vis)
            if on_answer:
                on_answer(vis)
        if tj and tool_json is None:
            tool_json = tj
        return "".join(narration), tool_json

    def _file_event(self, name: str, args: Dict[str, Any]) -> Tuple[str, str]:
        """(kind, target) describing the LIVE activity, computed BEFORE the tool runs."""
        path = (args.get("path") or "").strip()
        if name == "list_dir":
            return "analyze", path or "."
        if name == "find_files":
            return "analyze", (args.get("pattern") or "*.*")
        if name == "read_file":
            return "analyze", path or "?"
        if name == "write_file":
            try:
                exists = os.path.isfile(self._safe_path(path))
            except Exception:
                exists = False
            return ("edit" if exists else "create"), path or "?"
        if name == "replace_in_file":
            return "edit", path or "?"
        if name == "run_command":
            return "run", (args.get("command") or "").strip() or "?"
        return "other", name

    def _prepare_system_prompt(self):
        sp = (AGENT_PROMPT
              .replace("__FOLDER__", self.workdir)
              .replace("__SHELL__",
                       "ENABLED" if self.allow_shell else
                       "DISABLED by the user — do not call it"))
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = sp
        else:
            self.messages.insert(0, {"role": "system", "content": sp})

    @staticmethod
    def _parse_tool(raw: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        s = raw.strip()
        a, b = s.find("{"), s.rfind("}")
        if a == -1 or b == -1 or b <= a:
            return None, None, "no JSON object found in the tool block"
        try:
            obj = json.loads(s[a:b + 1])
        except json.JSONDecodeError as e:
            return None, None, f"invalid JSON ({e})"
        if not isinstance(obj, dict):
            return None, None, "tool call must be a JSON object"
        name = obj.get("name") or obj.get("tool") or obj.get("action")
        if not name:
            return None, None, 'missing tool "name"'
        args = obj.get("args") or obj.get("arguments") or obj.get("parameters")
        if not isinstance(args, dict):
            args = {k: v for k, v in obj.items()
                    if k not in ("name", "tool", "action")}
        if name not in TOOLS:
            return None, None, (f"unknown tool '{name}' — available: {', '.join(sorted(TOOLS))}")
        return name, args, None

    def _run_tool(self, name: str, args: Dict[str, Any]) -> str:
        try:
            return getattr(self, "_t_" + name)(args)
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    # ── tools (all sandboxed to self.workdir) ──────────────────────
    def _safe_path(self, rel: str) -> str:
        rel = (rel or "").strip()
        if not rel:
            raise ValueError("missing 'path'")
        p = os.path.realpath(os.path.join(self.workdir, rel))
        if p != self.workdir and not p.startswith(self.workdir + os.sep):
            raise ValueError(f"'{rel}' is outside the work folder")
        return p

    def _t_list_dir(self, args: Dict[str, Any]) -> str:
        p = self._safe_path(args.get("path", "."))
        if not os.path.isdir(p):
            return f"ERROR: folder not found: {args.get('path')}"
        names = sorted(os.listdir(p))
        if not names:
            return "(empty folder)"
        lines = [f"{'[dir] ' if os.path.isdir(os.path.join(p, n)) else '[file]'}  {n}"
                 for n in names[:300]]
        if len(names) > 300:
            lines.append(f"… {len(names) - 300} more")
        return "\n".join(lines)

    def _t_find_files(self, args: Dict[str, Any]) -> str:
        import fnmatch
        base_dir = self._safe_path(args.get("path", "."))
        pattern = args.get("pattern", "*.*") or "*.*"
        matches = []
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".git")]
            for filename in files:
                if fnmatch.fnmatch(filename, pattern):
                    rel = os.path.relpath(os.path.join(root, filename), self.workdir).replace("\\", "/")
                    matches.append(rel)
                    if len(matches) >= 200:
                        break
            if len(matches) >= 200:
                break
        if not matches:
            return f"(no files matching '{pattern}' in '{args.get('path', '.')}')"
        return "\n".join(matches[:200]) + (f"\n… and {len(matches)-200} more" if len(matches) >= 200 else "")

    def _t_read_file(self, args: Dict[str, Any]) -> str:
        p = self._safe_path(args.get("path", ""))
        if not os.path.isfile(p):
            return f"ERROR: file not found: {args.get('path')}"
        offset = int(args.get("offset", 0) or 0)
        limit = int(args.get("limit", READ_LIMIT) or READ_LIMIT)
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            if offset > 0:
                f.seek(offset)
            content = f.read(limit + 1)
        if len(content) > limit:
            content = content[:limit] + f"\n… (truncated — showing {limit} chars from offset {offset})"
        return content or "(empty file)"

    def _t_write_file(self, args: Dict[str, Any]) -> str:
        p = self._safe_path(args.get("path", ""))
        content = args.get("content")
        if not isinstance(content, str):
            return "ERROR: 'content' must be a string with the FULL file content."
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)

        # Generate diff if previous file existed
        old_content = ""
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    old_content = f.read()
            except Exception:
                old_content = ""

        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

        if self._on_diff_callback:
            try:
                diff = "".join(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{args.get('path')}",
                    tofile=f"b/{args.get('path')}"
                ))
                if diff:
                    self._on_diff_callback(args.get("path"), diff)
            except Exception:
                pass

        return f"OK — wrote {len(content)} chars to {args.get('path')}"

    def _t_replace_in_file(self, args: Dict[str, Any]) -> str:
        p = self._safe_path(args.get("path", ""))
        if not os.path.isfile(p):
            return f"ERROR: file not found: {args.get('path')}"
        old, new = args.get("old"), args.get("new")
        if not isinstance(old, str) or not old:
            return "ERROR: 'old' must be a non-empty string."
        if not isinstance(new, str):
            return "ERROR: 'new' must be a string."
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        n = content.count(old)
        if n == 0:
            return "ERROR: 'old' text was not found in the file."
        new_content = content.replace(old, new)
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_content)

        if self._on_diff_callback:
            try:
                diff = "".join(difflib.unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{args.get('path')}",
                    tofile=f"b/{args.get('path')}"
                ))
                if diff:
                    self._on_diff_callback(args.get("path"), diff)
            except Exception:
                pass

        return f"OK — replaced {n} occurrence(s) in {args.get('path')}"

    def _t_run_command(self, args: Dict[str, Any]) -> str:
        cmd = args.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return "ERROR: missing 'command'."
        try:
            proc = subprocess.Popen(
                cmd, shell=True, cwd=self.workdir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        except Exception as e:
            return f"ERROR: {e}"
        deadline, killed = time.time() + CMD_TIMEOUT, None
        while proc.poll() is None:
            if self._stop:
                killed, _ = "stopped by user", proc.kill()
                break
            if time.time() > deadline:
                killed, _ = f"timed out after {CMD_TIMEOUT}s", proc.kill()
                break
            time.sleep(0.05)
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = "", ""
        text = ((out or "") + (("\n[stderr]\n" + err) if err else "")).strip()
        if len(text) > 4000:
            text = text[:4000] + "\n… (truncated)"
        if killed:
            return f"ERROR: command killed ({killed})\n{text}"
        return f"exit code {proc.returncode}\n{text or '(no output)'}"


# ═══════════════════════════ GUI Worker & Standalone Window ═══════════════════════════
if HAS_GUI:

    class LiveAgentWorker(QThread):
        """Runs CodingAgent in background and forwards events as signals."""

        thinking = Signal(str)
        answer = Signal(str)
        tool_call = Signal(str, str)        # name, args-as-JSON-text
        tool_result = Signal(str)
        file_event = Signal(str, str)        # kind, file/command — LIVE activity
        diff_emitted = Signal(str, str)      # path, diff
        stepped = Signal(int)
        done = Signal(str, dict)             # final answer, stats
        failed = Signal(str)
        errors = Signal(str)
        error = Signal(str)

        # Additional integration & compatibility signals
        thinking_started = Signal()
        thinking_chunk = Signal(str)
        thinking_finished = Signal()
        event_emitted = Signal(dict)
        status_changed = Signal(str)
        file_tracked = Signal(str, str, str)
        model_selected_signal = Signal(dict)
        log_emitted = Signal(str)

        def __init__(
            self,
            model: str,
            messages: List[Dict[str, str]],
            task: str,
            workdir: str,
            allow_shell: bool,
            fallback_models: Optional[List[str]] = None,
            parent=None
        ):
            super().__init__(parent)
            self.model = model
            self.fallback_models = list(fallback_models or [])
            self.agent = CodingAgent(model, workdir, allow_shell)
            self.agent.messages = list(messages)
            self.agent.set_diff_callback(self.diff_emitted.emit)
            self.task = task
            self._thinking_active = False

        def stop(self):
            self.agent.stop()

        def cancel(self):
            """Alias for stop() to support cancellation."""
            self.agent.stop()

        def _handle_thinking(self, chunk: str):
            if not self._thinking_active:
                self._thinking_active = True
                self.thinking_started.emit()
            self.thinking.emit(chunk)
            self.thinking_chunk.emit(chunk)

        def _handle_answer(self, chunk: str):
            if self._thinking_active:
                self._thinking_active = False
                self.thinking_finished.emit()
            self.answer.emit(chunk)

        def _handle_tool_call(self, name: str, args: dict):
            if self._thinking_active:
                self._thinking_active = False
                self.thinking_finished.emit()
            args_str = json.dumps(args, ensure_ascii=False)
            self.tool_call.emit(name, args_str)
            self.log_emitted.emit(f"Tool {name}: {args_str[:160]}")
            self.status_changed.emit("RUNNING" if name == "run_command" else "EDITING")

        def _handle_tool_result(self, result: str):
            self.tool_result.emit(result)
            self.log_emitted.emit(f"Result: {result[:160]}")

        def _handle_file_event(self, kind: str, target: str):
            self.file_event.emit(kind, target)
            self.file_tracked.emit(target, kind.upper(), "WORKING...")
            self.event_emitted.emit({"type": f"file_{kind}", "message": f"{kind} {target}", "file": target})

        def run(self):
            models_to_try = [self.model] + [m for m in self.fallback_models if m and m != self.model]
            last_err = None
            for idx, cur_m in enumerate(models_to_try):
                if self.agent._stop:
                    break
                try:
                    self.agent.model = cur_m
                    final = self.agent.run(
                        self.task,
                        on_thinking=self._handle_thinking,
                        on_answer=self._handle_answer,
                        on_tool_call=self._handle_tool_call,
                        on_tool_result=self._handle_tool_result,
                        on_step=self.stepped.emit,
                        on_file_event=self._handle_file_event
                    )
                    if self._thinking_active:
                        self._thinking_active = False
                        self.thinking_finished.emit()
                    self.status_changed.emit("COMPLETED")
                    self.done.emit(final, {
                        "tokens": self.agent.tokens,
                        "seconds": self.agent.seconds,
                        "steps": self.agent.steps_used,
                        "note": self.agent.last_note
                    })
                    return
                except OllamaError as e:
                    last_err = str(e)
                    if idx < len(models_to_try) - 1:
                        next_m = models_to_try[idx + 1]
                        self.log_emitted.emit(f"⚠️ Model '{cur_m}' failed: {e}. Switching to fallback '{next_m}'...")
                        continue
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"
                    if idx < len(models_to_try) - 1:
                        next_m = models_to_try[idx + 1]
                        self.log_emitted.emit(f"⚠️ Model '{cur_m}' error: {e}. Switching to fallback '{next_m}'...")
                        continue

            if self._thinking_active:
                self._thinking_active = False
                self.thinking_finished.emit()
            self.status_changed.emit("ERROR")
            err_text = last_err or "Unknown error"
            self.failed.emit(err_text)
            self.errors.emit(err_text)
            self.error.emit(err_text)

    class InputBox(QPlainTextEdit):
        """Chat input box: Enter to send, Shift+Enter for new line."""

        send_requested = Signal()
        returnPressed = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)

        def keyPressEvent(self, e):
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
                self.send_requested.emit()
                self.returnPressed.emit()
            else:
                super().keyPressEvent(e)

        def text(self) -> str:
            return self.toPlainText()

        def setText(self, val: str):
            self.setPlainText(val)

    class MainWindow(QMainWindow):
        """Standalone Window for live_agent.py."""

        def __init__(self):
            super().__init__()
            self.setWindowTitle("Live-Thinking Coding Agent — Sage AI")
            self.resize(1000, 700)

            self.messages = [{"role": "system", "content": AGENT_PROMPT}]
            self.worker: Optional[LiveAgentWorker] = None
            self._retired: List[LiveAgentWorker] = []
            self._buf: List[Tuple[str, str]] = []
            self._think_open = False
            self._ans_open = False
            self._turn_answer_shown = False
            self._t0 = 0.0
            self._think_t0 = None
            self._server_status = "ready"
            self._file_stats: Dict[str, Dict[str, int]] = {}

            self._build_ui()
            self._check_server()
            self._push(("raw", HTML_WELCOME))
            self._flush()

        def _build_ui(self):
            central = QWidget()
            root = QVBoxLayout(central)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)

            top = QHBoxLayout()
            top.addWidget(QLabel("Model:"))
            self.model_box = QComboBox()
            self.model_box.setEditable(True)
            self.model_box.addItems(MODEL_CHOICES)
            self.model_box.setCurrentText(DEFAULT_MODEL)
            self.model_box.setMinimumWidth(160)
            top.addWidget(self.model_box)

            top.addWidget(QLabel("Folder:"))
            self.folder = QLineEdit(os.getcwd())
            top.addWidget(self.folder, 1)

            self.btn_browse = QPushButton("…")
            self.btn_browse.setFixedWidth(34)
            self.btn_browse.clicked.connect(self._browse)
            top.addWidget(self.btn_browse)

            self.btn_new = QPushButton("＋ New")
            self.btn_new.clicked.connect(self.new_chat)
            top.addWidget(self.btn_new)

            self.btn_stop = QPushButton("■ Stop")
            self.btn_stop.setObjectName("stop")
            self.btn_stop.setEnabled(False)
            self.btn_stop.clicked.connect(self.stop_gen)
            top.addWidget(self.btn_stop)
            root.addLayout(top)

            row2 = QHBoxLayout()
            self.chk_shell = QCheckBox("Allow shell commands (run_command)")
            row2.addWidget(self.chk_shell)
            row2.addStretch(1)
            self.status = QLabel("")
            row2.addWidget(self.status)
            root.addLayout(row2)

            # LIVE ACTIVITY BAR
            self.activity = QLabel("⏳ waiting for a task…")
            self.activity.setObjectName("activity")
            self.activity.setTextFormat(Qt.RichText)
            root.addWidget(self.activity)

            # Chat View + Files Side Panel
            splitter = QSplitter(Qt.Horizontal)
            self.view = QTextBrowser()
            splitter.addWidget(self.view)

            panel = QWidget()
            panel.setMinimumWidth(180)
            panel.setMaximumWidth(320)
            pv = QVBoxLayout(panel)
            pv.setContentsMargins(0, 0, 0, 0)
            pv.setSpacing(4)
            self.files_header = QLabel("📁 Files (live)")
            pv.addWidget(self.files_header)
            self.files = QListWidget()
            self.files.setWordWrap(True)
            pv.addWidget(self.files, 1)
            splitter.addWidget(panel)

            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            splitter.setSizes([720, 250])
            root.addWidget(splitter, 1)

            bottom = QHBoxLayout()
            self.input = InputBox()
            self.input.setPlaceholderText(
                "Describe a coding task… e.g. \"create hello.py that prints "
                "the time, then run it\" (Enter to send · Shift+Enter = new line)"
            )
            self.input.setFixedHeight(76)
            self.input.send_requested.connect(self.send)
            bottom.addWidget(self.input, 1)

            self.btn_send = QPushButton("Send ➤")
            self.btn_send.setObjectName("send")
            self.btn_send.setFixedHeight(76)
            self.btn_send.clicked.connect(self.send)
            bottom.addWidget(self.btn_send)
            root.addLayout(bottom)

            self.setCentralWidget(central)
            self.apply_theme()

            self._flush_timer = QTimer(self)
            self._flush_timer.setSingleShot(True)
            self._flush_timer.setInterval(50)
            self._flush_timer.timeout.connect(self._flush)
            self.input.setFocus()

        def apply_theme(self):
            self.setStyleSheet("""
                QMainWindow, QWidget { background:#0A0F14; color:#cdd6f4; font-size:13px; }
                QTextBrowser  { background:#060913; border:1px solid #1e293b; border-radius:8px; padding:10px; }
                QPlainTextEdit{ background:#0b1322; color:#cdd6f4; border:1px solid #1e293b; border-radius:8px; padding:8px; }
                QLineEdit     { background:#0b1322; color:#cdd6f4; border:1px solid #1e293b; border-radius:6px; padding:5px 8px; }
                QComboBox     { background:#0b1322; color:#00D1FF; border:1px solid #1e293b; border-radius:6px; padding:5px 8px; }
                QComboBox QAbstractItemView { background:#0b1322; color:#cdd6f4; selection-background-color:#1e3a5f; }
                QCheckBox     { color:#94a3b8; }
                QPushButton   { background:#162033; color:#cdd6f4; border:1px solid #273449; border-radius:6px; padding:6px 12px; font-weight:bold; }
                QPushButton:hover   { background:#1e2d4a; border-color:#00D1FF; }
                QPushButton:disabled{ background:#0d1522; color:#475569; }
                QPushButton#send    { background:#00D1FF; color:#0A0F14; border:none; }
                QPushButton#send:hover    { background:#38bdf8; }
                QPushButton#send:disabled { background:#162438; color:#475569; }
                QPushButton#stop    { background:rgba(244, 63, 94, 0.2); color:#f43f5e; border:1px solid rgba(244, 63, 94, 0.4); }
                QPushButton#stop:disabled { background:#162438; color:#475569; }
                QLabel { color:#94a3b8; }
                QLabel#activity { background:#0b1322; border:1px solid #1e293b; border-radius:6px; padding:6px 10px; font-size:13px; }
                QListWidget { background:#060913; border:1px solid #1e293b; border-radius:6px; padding:4px; color:#cdd6f4; font-size:12px; }
                QListWidget::item { padding:4px; border-radius:4px; }
                QSplitter::handle { background:#1e293b; }
            """)

        def _push(self, item: Tuple[str, str]):
            self._buf.append(item)
            if not self._flush_timer.isActive():
                self._flush_timer.start()

        def _flush(self):
            if not self._buf:
                return
            items = self._buf
            self._buf = []

            sb = self.view.verticalScrollBar()
            stick = sb.value() >= sb.maximum() - 30
            cur = self.view.textCursor()
            cur.movePosition(QTextCursor.End)
            self.view.setTextCursor(cur)

            for kind, text in items:
                if kind == "raw":
                    cur.insertHtml(text)
                elif text:
                    fmt = QTextCharFormat()
                    if kind == "think":
                        fmt.setForeground(QColor(C_THINK))
                        fmt.setFontItalic(True)
                    elif kind == "ans":
                        fmt.setForeground(QColor(C_ANS))
                    else:
                        fmt.setForeground(QColor(C_USER))
                    cur.insertText(text, fmt)
            if stick:
                sb.setValue(sb.maximum())

        def _on_file_event(self, kind: str, target: str):
            if not target:
                return
            styles = {
                "analyze": ("🔍", "ANALYZING", C_ACC),
                "create":  ("➕", "CREATING",  C_OK),
                "edit":    ("✏️", "EDITING",   C_TOOL),
                "run":     ("⚙️", "RUNNING",   C_RES),
                "other":   ("🔧", "WORKING",   C_FAINT),
            }
            icon, label, color = styles.get(kind, styles["other"])
            self.activity.setText(
                f'<b style="color:{color}">{icon}&nbsp; {label}</b>'
                f'<span style="color:#cdd6f4">&nbsp;&nbsp;{_esc(target)}</span>'
            )

            if kind == "run":
                return
            st = self._file_stats.setdefault(target, {"analyze": 0, "create": 0, "edit": 0})
            if kind in st:
                st[kind] += 1
            self._refresh_files(current=target)

        def _refresh_files(self, current=None):
            self.files.clear()
            for path, st in self._file_stats.items():
                if st["create"] and st["edit"]:
                    desc = f"created, edited ×{st['edit']}"
                elif st["create"]:
                    desc = "created"
                elif st["edit"]:
                    desc = f"edited ×{st['edit']}"
                else:
                    desc = "read"
                if st["analyze"]:
                    desc += f" · read ×{st['analyze']}"
                icon = "➕" if st["create"] else ("✏️" if st["edit"] else "📖")
                item = QListWidgetItem(f"{icon}  {path}\n        {desc}")
                if path == current:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setBackground(QColor("#16243b"))
                self.files.addItem(item)
            self.files_header.setText(f"📁 Files ({len(self._file_stats)})")

        def send(self):
            if self.worker and self.worker.isRunning():
                return
            text = self.input.toPlainText().strip()
            if not text:
                return
            self.input.clear()
            model = self.model_box.currentText().strip() or DEFAULT_MODEL

            self._push(("raw", f'<div style="margin-top:12px"><b style="color:{C_OK}">You</b></div>'))
            self._push(("user", text))

            self._think_open = False
            self._ans_open = False
            self._turn_answer_shown = False
            self._t0 = time.time()
            self._think_t0 = None
            self._file_stats = {}
            self.files.clear()
            self.files_header.setText("📁 Files (live)")
            self.activity.setText(f'<b style="color:{C_ACC}">⏳</b><span style="color:#cdd6f4">&nbsp;&nbsp;starting task…</span>')
            self._set_busy(True)
            self._flush()

            if self.worker:
                self._retired.append(self.worker)
                self._retired = self._retired[-4:]

            w = LiveAgentWorker(
                model=model,
                messages=self.messages,
                task=text,
                workdir=self.folder.text().strip() or os.getcwd(),
                allow_shell=self.chk_shell.isChecked()
            )
            w.thinking.connect(self._on_thinking)
            w.answer.connect(self._on_answer)
            w.tool_call.connect(self._on_tool_call)
            w.tool_result.connect(self._on_tool_result)
            w.file_event.connect(self._on_file_event)
            w.stepped.connect(self._on_stepped)
            w.done.connect(self._on_done)
            w.failed.connect(self._on_failed)
            if hasattr(w, "errors"):
                w.errors.connect(self._on_failed)
            self.worker = w
            w.start()

        def stop_gen(self):
            if self.worker:
                self.worker.stop()

        def new_chat(self):
            if self.worker and self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(2000)
            self.worker = None
            self._buf.clear()
            self._think_open = self._ans_open = False
            self.messages = [{"role": "system", "content": AGENT_PROMPT}]
            self.view.clear()
            self._file_stats = {}
            self.files.clear()
            self.files_header.setText("📁 Files (live)")
            self.activity.setText(f'<b style="color:{C_ACC}">⏳</b><span style="color:#cdd6f4">&nbsp;&nbsp;waiting for a task…</span>')
            self._push(("raw", HTML_WELCOME))
            self._flush()
            self._set_busy(False)

        def _browse(self):
            d = QFileDialog.getExistingDirectory(self, "Choose work folder", self.folder.text() or os.getcwd())
            if d:
                self.folder.setText(d)

        def _on_stepped(self, step: int):
            self._close_thinking()
            self._ans_open = False
            self.status.setText(f"step {step}/{MAX_STEPS}…")

        def _on_thinking(self, text: str):
            if not text:
                return
            if not self._think_open:
                self._think_open = True
                self._think_t0 = time.time()
                self._push(("raw", f'<div style="margin-top:10px"><b style="color:{C_THINK}">🧠 thinking — live</b></div>'))
                self.status.setText("agent is thinking…")
            self._push(("think", text))

        def _on_answer(self, text: str):
            if not text:
                return
            if not self._ans_open:
                self._ans_open = True
                self._close_thinking()
                self._push(("raw", f'<div style="margin-top:8px"><b style="color:{C_ACC}">💬 agent</b></div>'))
            self._turn_answer_shown = True
            self._push(("ans", text))

        def _on_tool_call(self, name: str, args_json: str):
            self._close_thinking()
            self._ans_open = False
            preview = args_json if len(args_json) <= 300 else args_json[:300] + " …"
            self._push(("raw",
                        f'<div style="margin-top:8px"><b style="color:{C_TOOL}">🔧 {name}</b></div>'
                        f'<div style="color:#94a3b8; margin-left:10px">'
                        f'{_esc(preview).replace(chr(10), "<br>")}</div>'))
            self._flush()
            self.status.setText(f"running {name}…")

        def _on_tool_result(self, text: str):
            err = text.startswith("ERROR")
            color = C_ERR if err else C_RES
            preview = text if len(text) <= 600 else text[:600] + " …"
            self._push(("raw",
                        f'<div style="margin-top:4px"><b style="color:{color}">'
                        f'{"✖ error" if err else "📄 result"}</b></div>'
                        f'<div style="color:{color}; margin-left:10px">'
                        f'{_esc(preview).replace(chr(10), "<br>")}</div>'))
            self._flush()

        def _close_thinking(self):
            if self._think_open:
                self._think_open = False
                dur = time.time() - (self._think_t0 or self._t0)
                self._push(("raw", f'<div><span style="color:{C_FAINT}">— thought for {dur:.1f}s —</span></div>'))

        def _on_done(self, final: str, stats: dict):
            self._close_thinking()
            if final and not self._turn_answer_shown:
                self._ans_open = True
                self._push(("raw", f'<div style="margin-top:10px"><b style="color:{C_ACC}">💬 final answer</b></div>'))
                self._push(("ans", final))
            if stats.get("note"):
                self._push(("raw", f'<div><span style="color:{C_FAINT}">⏹ {_esc(stats["note"])}</span></div>'))

            created = sum(1 for s in self._file_stats.values() if s["create"])
            edited = sum(1 for s in self._file_stats.values() if s["edit"])
            analyzed = sum(1 for s in self._file_stats.values() if s["analyze"])
            fb = []
            if created:
                fb.append(f"{created} created")
            if edited:
                fb.append(f"{edited} edited")
            if analyzed:
                fb.append(f"{analyzed} analyzed")
            if fb:
                self._push(("raw", f'<div><span style="color:{C_FAINT}">📁 files: {" · ".join(fb)}</span></div>'))

            elapsed = time.time() - self._t0
            toks = stats.get("tokens", 0)
            secs = stats.get("seconds", 0)
            steps = stats.get("steps", 0)
            bits = []
            if toks:
                bits.append(f"{toks} tokens")
                if secs:
                    bits.append(f"{toks / secs:.1f} tok/s")
            bits.append(f"{elapsed:.1f}s")
            if steps:
                bits.append(f"{steps} step{'s' if steps != 1 else ''}")
            self._push(("raw", f'<div><span style="color:{C_FAINT}">⚡ {" · ".join(bits)}</span></div><div><br></div>'))
            self._flush()

            self.activity.setText(f'<b style="color:{C_OK}">✓</b><span style="color:#cdd6f4">&nbsp;&nbsp;task finished</span>')
            self._end_turn()

        def _on_failed(self, msg: str):
            self._close_thinking()
            self._push(("raw", f'<div style="margin-top:8px"><span style="color:{C_ERR}">{_esc(msg).replace(chr(10), "<br>")}</span></div><div><br></div>'))
            self._flush()
            self.activity.setText(f'<b style="color:{C_ERR}">✖</b><span style="color:#cdd6f4">&nbsp;&nbsp;errors — see message</span>')
            self._end_turn()

        _on_errors = _on_failed

        def _end_turn(self):
            self.worker = None
            self._set_busy(False)

        def _set_busy(self, busy: bool):
            self.btn_send.setEnabled(not busy)
            self.btn_stop.setEnabled(busy)
            self.model_box.setEnabled(not busy)
            self.folder.setEnabled(not busy)
            self.btn_browse.setEnabled(not busy)
            self.chk_shell.setEnabled(not busy)
            self.status.setText("connecting…" if busy else self._server_status)
            self.input.setFocus()

        def _check_server(self):
            v = server_version(OLLAMA_URL, timeout=2.0)
            if v:
                self._server_status = f"Ollama v{v} ✓"
            else:
                self._server_status = "Ollama offline / Cloud Ready"
                self._push(("raw", HTML_SERVER_DOWN))
            self.status.setText(self._server_status)

        def closeEvent(self, event):
            if self.worker and self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(2000)
            event.accept()

    def main():
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        win = MainWindow()
        win.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    if not HAS_GUI:
        print("PySide6 is required to run the GUI: pip install PySide6")
        sys.exit(1)
    main()
