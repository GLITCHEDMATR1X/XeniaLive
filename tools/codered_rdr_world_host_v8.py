#!/usr/bin/env python3
r"""CodeRED RDR world-aware private host v8.

This is a private-host/session shim plus RDRMP-derived world manifest endpoints.
It does not stream a PC RDRMP world into Xbox 360 RDR. It gives Xenia's private
host bridge a richer session/world service to query in later passes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import pathlib
import random
import re
import socketserver
import sys
import urllib.parse
from typing import Any


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def root_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def load_manifest(root: pathlib.Path, explicit: str = "") -> dict[str, Any]:
    candidates = []
    if explicit:
        candidates.append(pathlib.Path(explicit))
    candidates.extend([
        root / "data" / "codered" / "rdrmp_world_manifest_v8.json",
        root / "logs" / "rdrmp_world_manifest_v8.json",
    ])
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {
        "schema": "codered.rdrmp_world_manifest.v8.empty",
        "server_world_seed": {"default_sector": "blackwater", "default_weather": "CLEAR", "session_name": "CodeRED RDR WorldHost v8"},
        "world_sector_candidates": ["blackwater", "wilderness"],
        "weather_candidates": ["CLEAR"],
        "vehicle_related_actors": [],
        "core_events": [],
    }


class State:
    def __init__(self, manifest: dict[str, Any]):
        self.manifest = manifest
        self.players: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.next_session = random.randrange(0x100000000000, 0xFFFFFFFFFFFF)

    def new_session_id(self) -> str:
        self.next_session += 1
        return f"{self.next_session:016X}"

    def slot_recalc(self, session: dict[str, Any]) -> None:
        players = session.setdefault("players", [])
        max_pub = int(session.get("public_slots", session.get("max_public_slots", 16)))
        max_pri = int(session.get("private_slots", session.get("max_private_slots", 0)))
        filled_pub = len([p for p in players if not p.get("private")])
        filled_pri = len([p for p in players if p.get("private")])
        session["filled_public_slots"] = filled_pub
        session["filled_private_slots"] = filled_pri
        session["open_public_slots"] = max(0, max_pub - filled_pub)
        session["open_private_slots"] = max(0, max_pri - filled_pri)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "CodeRED-RDR-WorldHost-v8"

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "verbose", False):
            print(f"[{stamp()}] {self.client_address[0]} {fmt % args}")

    @property
    def state(self) -> State:
        return self.server.state  # type: ignore[attr-defined]

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        try:
            return json.loads(data.decode("utf-8", "replace"))
        except Exception:
            return {"raw": data.decode("utf-8", "replace")}

    def send_json(self, obj: Any, status: int = 200) -> None:
        data = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            self.send_json({"ok": True, "service": "codered-rdr-private-host", "variant": "worldhost-v8", "sessions": len(self.state.sessions)})
        elif path in {"/world", "/world/manifest"}:
            self.send_json(self.state.manifest)
        elif path == "/sessions":
            self.send_json({"sessions": list(self.state.sessions.values())})
        else:
            m = re.match(r"^/title/([^/]+)/sessions/([^/]+)(?:/details)?$", path)
            if m:
                sid = m.group(2).upper()
                self.send_json(self.state.sessions.get(sid, {"error": "not_found", "session_id": sid}), 200 if sid in self.state.sessions else 404)
            else:
                self.send_json({"error": "not_found", "path": path}, 404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        body = self.read_json()
        if path == "/players":
            xuid = str(body.get("xuid") or body.get("player_id") or body.get("name") or f"player-{len(self.state.players)+1}")
            self.state.players[xuid] = {**body, "xuid": xuid, "seen_at": stamp()}
            self.send_json({"ok": True, "player": self.state.players[xuid]})
            return
        m_create = re.match(r"^/title/([^/]+)/sessions$", path)
        if m_create:
            title_id = m_create.group(1)
            sid = str(body.get("session_id") or body.get("id") or self.state.new_session_id()).upper()
            seed = self.state.manifest.get("server_world_seed", {})
            session = {
                "session_id": sid,
                "id": sid,
                "title_id": title_id,
                "name": body.get("name") or seed.get("session_name") or "CodeRED RDR WorldHost v8",
                "host_address": body.get("host_address") or body.get("hostAddress") or "127.0.0.1",
                "port": int(body.get("port") or 3074),
                "flags": int(body.get("flags") or 0),
                "public_slots": int(body.get("public_slots") or body.get("max_public_slots") or 16),
                "private_slots": int(body.get("private_slots") or body.get("max_private_slots") or 0),
                "players": body.get("players") or [],
                "started": bool(body.get("started", False)),
                "advertised": True,
                "world": {
                    "sector": body.get("sector") or seed.get("default_sector") or "blackwater",
                    "weather": body.get("weather") or seed.get("default_weather") or "CLEAR",
                    "source": "RDRMP manifest reference; not a streamed server world",
                },
                "raw": body,
            }
            self.state.slot_recalc(session)
            self.state.sessions[sid] = session
            self.send_json({"ok": True, "session": session}, 201)
            return
        m_search = re.match(r"^/title/([^/]+)/sessions/search$", path)
        if m_search:
            title_id = m_search.group(1)
            sessions = [s for s in self.state.sessions.values() if str(s.get("title_id")) == title_id or not s.get("title_id")]
            self.send_json({"ok": True, "sessions": sessions, "world": self.state.manifest.get("server_world_seed", {})})
            return
        m_action = re.match(r"^/title/([^/]+)/sessions/([^/]+)/(join|leave|qos|details)$", path)
        if m_action:
            sid = m_action.group(2).upper()
            action = m_action.group(3)
            session = self.state.sessions.setdefault(sid, {"session_id": sid, "id": sid, "players": [], "public_slots": 16, "private_slots": 0})
            if action == "join":
                xuid = str(body.get("xuid") or body.get("player_id") or f"player-{len(session['players'])+1}")
                if not any(str(p.get("xuid")) == xuid for p in session["players"]):
                    session["players"].append({"xuid": xuid, "private": bool(body.get("private", False)), "joined_at": stamp()})
                self.state.slot_recalc(session)
            elif action == "leave":
                xuid = str(body.get("xuid") or body.get("player_id") or "")
                session["players"] = [p for p in session.get("players", []) if str(p.get("xuid")) != xuid]
                self.state.slot_recalc(session)
            elif action == "qos":
                session["qos"] = {"ok": True, "rtt_min_in_msecs": 1, "rtt_med_in_msecs": 2, "up_bits_per_sec": 100000000, "down_bits_per_sec": 100000000, "updated_at": stamp()}
            self.send_json({"ok": True, "session": session})
            return
        self.send_json({"error": "not_found", "path": path, "body": body}, 404)

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        m = re.match(r"^/title/([^/]+)/sessions/([^/]+)$", path)
        if m:
            sid = m.group(2).upper()
            existed = sid in self.state.sessions
            self.state.sessions.pop(sid, None)
            self.send_json({"ok": True, "removed": existed, "session_id": sid})
        else:
            self.send_json({"error": "not_found", "path": path}, 404)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=36000)
    ap.add_argument("--manifest", default="")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    root = root_dir()
    manifest = load_manifest(root, args.manifest)
    class ReuseTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    httpd = ReuseTCPServer((args.host, args.port), Handler)
    httpd.state = State(manifest)  # type: ignore[attr-defined]
    httpd.verbose = args.verbose  # type: ignore[attr-defined]
    print(f"[{stamp()}] CodeRED RDR WorldHost v8 listening on http://{args.host}:{args.port}/")
    print(f"[{stamp()}] World seed: {manifest.get('server_world_seed', {})}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
