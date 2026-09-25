"""
Backend HTTP REST API Server.
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from backend.database import init_db, get_connection

init_db()

class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json(200, {"status": "ok", "service": "Sage Backend v6"})
        elif self.path == "/api/items":
            with get_connection() as conn:
                rows = conn.execute("SELECT * FROM items").fetchall()
                self._send_json(200, {"items": [dict(r) for r in rows]})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

def run_server(port: int = 8000):
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"Server started at http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
