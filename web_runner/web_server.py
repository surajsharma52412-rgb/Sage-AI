"""
Dual-mode Flask and PyWebView runner for Sage AI (Lunar Engine).
Provides HTTP API endpoints and an embedded web interface.
"""
import sys
import threading
from typing import Optional
from flask import Flask, request, jsonify, render_template_string

from database.db_manager import get_db
from engine.router import FallbackRouter

app = Flask(__name__)
router = FallbackRouter()

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sage AI - Lunar Engine (Web View)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: #080b16;
            color: #f4f5fb;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            height: 100vh;
        }
        #sidebar {
            width: 260px;
            background-color: #0a0e19;
            border-right: 1px solid rgba(15, 230, 181, 0.15);
            padding: 18px 14px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .brand {
            color: #0FE6B5;
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        .sub {
            color: #626c85;
            font-size: 11px;
        }
        .btn-new {
            background: linear-gradient(135deg, #0FE6B5, #0CC99D);
            color: #080b16;
            border: none;
            padding: 10px;
            border-radius: 8px;
            font-weight: 700;
            cursor: pointer;
        }
        #main {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .bubble {
            padding: 14px 18px;
            border-radius: 12px;
            max-width: 80%;
            line-height: 1.5;
        }
        .bubble.user {
            align-self: flex-end;
            background-color: #0e1b2c;
            border: 1px solid rgba(15, 230, 181, 0.2);
        }
        .bubble.assistant {
            align-self: flex-start;
            background-color: #111627;
            border: 1px solid rgba(15, 230, 181, 0.12);
        }
        .bubble-header {
            font-size: 11px;
            font-weight: bold;
            color: #0FE6B5;
            margin-bottom: 6px;
        }
        #input-area {
            background-color: #0a0e19;
            border-top: 1px solid rgba(15, 230, 181, 0.12);
            padding: 14px 20px;
            display: flex;
            gap: 10px;
        }
        #input-box {
            flex: 1;
            background-color: #0e1b2c;
            border: 1px solid rgba(15, 230, 181, 0.2);
            color: #f4f5fb;
            border-radius: 8px;
            padding: 10px 14px;
            outline: none;
        }
        #input-box:focus { border-color: #0FE6B5; }
        .btn-send {
            background: linear-gradient(135deg, #0FE6B5, #0CC99D);
            color: #080b16;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <div class="brand"><img src="/assets/logo.png" width="28" height="28" style="vertical-align: middle; border-radius: 6px; margin-right: 8px;">SAGE AI</div>
        <div class="sub">LUNAR ENGINE DUAL-MODE</div>
        <button class="btn-new" onclick="newChat()">＋ New Chat</button>
    </div>
    <div id="main">
        <div id="messages">
            <div class="bubble assistant">
                <div class="bubble-header"><img src="/assets/logo.png" width="18" height="18" style="vertical-align: middle; margin-right: 6px;">SAGE AI • Ready</div>
                <div>Welcome to Sage AI Web Runner. Lunar Engine multi-provider waterfall routing is active.</div>
            </div>
        </div>
        <div id="input-area">
            <input type="text" id="input-box" placeholder="Ask Sage AI anything..." onkeydown="if(event.key==='Enter') sendMessage()">
            <button class="btn-send" onclick="sendMessage()">Send</button>
        </div>
    </div>
    <script>
        let currentSessionId = null;

        async function init() {
            const res = await fetch('/api/sessions');
            const data = await res.json();
            if (data.sessions && data.sessions.length > 0) {
                currentSessionId = data.sessions[0].id;
            } else {
                newChat();
            }
        }

        async function newChat() {
            const res = await fetch('/api/sessions', { method: 'POST' });
            const session = await res.json();
            currentSessionId = session.id;
            document.getElementById('messages').innerHTML = `
                <div class="bubble assistant">
                    <div class="bubble-header">SAGE AI</div>
                    <div>New session started. How can I assist your workflow today?</div>
                </div>
            `;
        }

        async function sendMessage() {
            const box = document.getElementById('input-box');
            const prompt = box.value.trim();
            if (!prompt) return;
            box.value = '';

            const container = document.getElementById('messages');
            container.innerHTML += `
                <div class="bubble user">
                    <div class="bubble-header" style="color: #a8afc2;">USER</div>
                    <div>${prompt.replace(/</g, "&lt;")}</div>
                </div>
            `;
            container.scrollTop = container.scrollHeight;

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt, session_id: currentSessionId })
            });
            const data = await res.json();

            container.innerHTML += `
                <div class="bubble assistant">
                    <div class="bubble-header">SAGE AI • ${data.model_name || 'Lunar Engine'}</div>
                    <div>${(data.text || '').replace(/\\n/g, '<br>')}</div>
                </div>
            `;
            container.scrollTop = container.scrollHeight;
        }

        init();
    </script>
</body>
</html>
"""


from flask import Flask, request, jsonify, render_template_string, send_from_directory
from pathlib import Path

app = Flask(__name__)
router = FallbackRouter()
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(ASSETS_DIR, filename)


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/status")
def status():
    return jsonify({
        "status": "online",
        "engine": "Lunar Engine v1.0",
        "providers_loaded": list(router.providers.keys())
    })


@app.route("/api/sessions", methods=["GET", "POST"])
def sessions():
    db = get_db()
    if request.method == "POST":
        sess = db.create_session("New Web Chat")
        return jsonify(sess)
    return jsonify({"sessions": db.get_sessions()})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    force_web = data.get("force_web", False)
    selected_model = data.get("model")

    db = get_db()
    if not session_id:
        sess = db.create_session(prompt[:25])
        session_id = sess["id"]

    db.add_message(session_id, "user", prompt)
    history = db.get_session_messages(session_id)

    response = router.route_and_execute(
        prompt=prompt,
        history=history[:-1],
        force_web=force_web,
        selected_model=selected_model
    )

    db.add_message(
        session_id,
        "assistant",
        response.text,
        model=response.model_name,
        sources=response.citations
    )

    return jsonify({
        "session_id": session_id,
        "text": response.text,
        "model_name": response.model_name,
        "citations": response.citations,
        "latency_ms": response.latency_ms
    })


def run_web_app(port: int = 5000, use_webview: bool = False):
    """Launches Flask server with optional pywebview native frame."""
    if use_webview:
        try:
            import webview
            t = threading.Thread(target=lambda: app.run(port=port, debug=False, use_reloader=False), daemon=True)
            t.start()
            webview.create_window("Sage AI - Lunar Engine", f"http://127.0.0.1:{port}", width=1100, height=720)
            webview.start()
            return
        except ImportError:
            print("pywebview not installed or unavailable, falling back to pure Flask server.")

    print(f"Starting Sage AI web runner on http://127.0.0.1:{port}")
    app.run(port=port, debug=False)
