#!/usr/bin/env python3
"""
Code RED local RDR/Xenia bootstrap host.
Private/offline helper for Xenia RDR Free Roam experiments.

This does not connect to Xbox Live or any public service. It only answers the
local HTTP endpoint configured in Xenia's Netplay section:
  http://127.0.0.1:36000/
"""
from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

TITLE_ID = "5454082B"
HOST_IP = "127.0.0.1"
PORT = 3074
SESSION_ID = "55" + uuid.uuid4().hex[:14].upper()
START_TIME = time.strftime("%Y-%m-%d %H:%M:%S")

sessions = {
    TITLE_ID: {
        "ok": True,
        "id": SESSION_ID,
        "session": SESSION_ID,
        "title_id": TITLE_ID,
        "host": HOST_IP,
        "ip": HOST_IP,
        "port": PORT,
        "public": 4,
        "private": 0,
        "mode": "codered-local-freeroam-host",
        "status": "available",
        "created_at": START_TIME,
    }
}

def _json_response(handler: BaseHTTPRequestHandler, data: dict, status: int = 200) -> None:
    payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(payload)

class Handler(BaseHTTPRequestHandler):
    server_version = "CodeREDRDRBootstrap/18"

    def log_message(self, fmt, *args):
        print("[%s] %s %s" % (time.strftime("%H:%M:%S"), self.address_string(), fmt % args), flush=True)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return {"raw": raw.decode("utf-8", "replace")}

    def do_GET(self):
        path = urlparse(self.path).path.strip("/")
        if path in ("", "health"):
            return _json_response(self, {
                "ok": True,
                "service": "codered-rdr-bootstrap-host",
                "variant": "ready-private-v18",
                "title_id": TITLE_ID,
                "sessions": list(sessions.values()),
            })

        # Accept broad session lookup paths used by experimental Xenia netplay builds.
        if "session" in path.lower() or "title" in path.lower():
            return _json_response(self, {
                "ok": True,
                "title_id": TITLE_ID,
                "sessions": list(sessions.values()),
                "session": sessions[TITLE_ID],
            })

        return _json_response(self, {"ok": True, "path": path, "sessions": list(sessions.values())})

    def do_POST(self):
        path = urlparse(self.path).path.strip("/")
        body = self._read_json()

        title = str(body.get("title_id") or body.get("title") or TITLE_ID).upper()
        if title not in sessions:
            sessions[title] = dict(sessions[TITLE_ID])
            sessions[title]["title_id"] = title

        sess = sessions[title]
        # Merge harmless fields from Xenia publish calls so later lookups see the host state.
        for key in ("host", "ip", "port", "public", "private", "session", "id", "mode", "status"):
            if key in body:
                sess[key] = body[key]
        sess["last_post_path"] = path
        sess["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")

        return _json_response(self, {"ok": True, "stored": sess, "sessions": list(sessions.values())})

if __name__ == "__main__":
    print("Code RED RDR local bootstrap host starting on http://127.0.0.1:36000/")
    print("This is local/offline only. Leave this window open while testing Free Roam.")
    ThreadingHTTPServer(("127.0.0.1", 36000), Handler).serve_forever()
