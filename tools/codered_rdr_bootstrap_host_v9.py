#!/usr/bin/env python3
r"""CodeRED RDR bootstrap host v9/v12.

Provides:
- The existing private HTTP session API endpoints.
- A pre-advertised default session so searches have something to find.
- A UDP beacon/tracer that sends small discovery packets to the selected
  interface, loopback, and broadcast. This is not a final RDR protocol server;
  it is a bootstrap/tracing layer to break the endless recvfrom/10035 loop and
  reveal what RDR accepts or rejects next.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import pathlib
import random
import re
import socket
import socketserver
import struct
import threading
import time
import urllib.parse
from typing import Any

LOG_FILE: pathlib.Path | None = None
CODERED_UDP_PREFIXES = (b"CODERED_RDR_V9", b"CODERED_RDR_V12")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = f"[{stamp()}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def guess_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


def default_manifest() -> dict[str, Any]:
    return {
        "schema": "codered.rdr_bootstrap_world.v12",
        "server_world_seed": {
            "session_name": "CodeRED RDR GOTY Bootstrap v12",
            "default_sector": "blackwater",
            "default_weather": "CLEAR",
            "disc_default": "disc1",
            "disc2_fallback": True,
            "mp_script_candidates": [
                "freemode",
                "mp_idle",
                "multiplayer_system_thread",
                "multiplayer_update_thread",
                "deathmatch",
                "ctf",
            ],
        },
        "note": "RDR world data remains local to the game. This host only advertises bootstrap/session state.",
    }


class State:
    def __init__(self, title_id: str, host_ip: str, port: int, manifest: dict[str, Any]):
        self.title_id = title_id.upper()
        self.host_ip = host_ip
        self.port = port
        self.manifest = manifest
        self.players: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.next_session = random.randrange(0x5500000000000000, 0x55FFFFFFFFFFFFFF)
        self.create_default_session()

    def new_session_id(self) -> str:
        self.next_session += 1
        return f"{self.next_session:016X}"

    def recalc(self, session: dict[str, Any]) -> None:
        players = session.setdefault("players", [])
        max_pub = int(session.get("public_slots", session.get("publicSlotsCount", 16)))
        max_pri = int(session.get("private_slots", session.get("privateSlotsCount", 0)))
        filled_pub = len([p for p in players if not p.get("private") and not p.get("privateSlot")])
        filled_pri = len(players) - filled_pub
        session["public_slots"] = max_pub
        session["private_slots"] = max_pri
        session["publicSlotsCount"] = max_pub
        session["privateSlotsCount"] = max_pri
        session["filled_public_slots"] = filled_pub
        session["filled_private_slots"] = filled_pri
        session["filledPublicSlotsCount"] = filled_pub
        session["filledPrivateSlotsCount"] = filled_pri
        session["open_public_slots"] = max(0, max_pub - filled_pub)
        session["open_private_slots"] = max(0, max_pri - filled_pri)
        session["openPublicSlotsCount"] = max(0, max_pub - filled_pub)
        session["openPrivateSlotsCount"] = max(0, max_pri - filled_pri)

    def create_default_session(self) -> None:
        sid = self.new_session_id()
        seed = self.manifest.get("server_world_seed", {})
        session = {
            "session_id": sid,
            "sessionId": sid,
            "id": sid,
            "title_id": self.title_id,
            "titleId": self.title_id,
            "name": seed.get("session_name", "CodeRED RDR Bootstrap v9"),
            "host_address": self.host_ip,
            "hostAddress": self.host_ip,
            "port": self.port,
            "flags": 0x21,
            "public_slots": 16,
            "private_slots": 0,
            "players": [],
            "started": False,
            "advertised": True,
            "world": {
                "sector": seed.get("default_sector", "blackwater"),
                "weather": seed.get("default_weather", "CLEAR"),
                "source": "local RDR GOTY content; bootstrap advertisement only",
            },
        }
        self.recalc(session)
        self.sessions[sid] = session
        log(f"Pre-advertised default session {sid} title={self.title_id} host={self.host_ip}:{self.port}")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "CodeRED-RDR-BootstrapHost-v12"

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "verbose", False):
            log(f"{self.client_address[0]} {fmt % args}")

    @property
    def state(self) -> State:
        return self.server.state  # type: ignore[attr-defined]

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return {"raw": raw.decode("utf-8", "replace")}

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
            self.send_json({"ok": True, "service": "codered-rdr-bootstrap-host", "variant": "v12", "sessions": len(self.state.sessions), "host_ip": self.state.host_ip, "port": self.state.port})
            return
        if path in {"/world", "/world/manifest"}:
            self.send_json(self.state.manifest)
            return
        if path == "/sessions":
            self.send_json({"ok": True, "sessions": list(self.state.sessions.values())})
            return
        m = re.match(r"^/title/([^/]+)/sessions/([^/]+)(?:/details)?$", path)
        if m:
            sid = m.group(2).upper()
            sess = self.state.sessions.get(sid)
            self.send_json(sess or {"error": "not_found", "session_id": sid}, 200 if sess else 404)
            return
        self.send_json({"error": "not_found", "path": path}, 404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        body = self.read_json()
        if path == "/players":
            xuid = str(body.get("xuid") or body.get("player_id") or f"player-{len(self.state.players)+1}")
            self.state.players[xuid] = {**body, "xuid": xuid, "seen_at": stamp()}
            self.send_json({"ok": True, "player": self.state.players[xuid]})
            return
        m_create = re.match(r"^/title/([^/]+)/sessions$", path)
        if m_create:
            title = m_create.group(1).upper()
            sid = str(body.get("sessionId") or body.get("session_id") or body.get("id") or self.state.new_session_id()).upper()
            session = {**body, "session_id": sid, "sessionId": sid, "id": sid, "title_id": title, "titleId": title, "host_address": body.get("hostAddress") or body.get("host_address") or self.state.host_ip, "hostAddress": body.get("hostAddress") or body.get("host_address") or self.state.host_ip, "port": int(body.get("port") or self.state.port), "advertised": True}
            self.state.recalc(session)
            self.state.sessions[sid] = session
            log(f"HTTP session create/update {sid} title={title}")
            self.send_json({"ok": True, "session": session}, 201)
            return
        m_search = re.match(r"^/title/([^/]+)/sessions/search$", path)
        if m_search:
            title = m_search.group(1).upper()
            sessions = [s for s in self.state.sessions.values() if str(s.get("title_id", s.get("titleId", title))).upper() == title]
            self.send_json({"ok": True, "sessions": sessions, "world": self.state.manifest.get("server_world_seed", {})})
            return
        m_action = re.match(r"^/title/([^/]+)/sessions/([^/]+)/(join|leave|qos|details)$", path)
        if m_action:
            sid = m_action.group(2).upper()
            action = m_action.group(3)
            session = self.state.sessions.setdefault(sid, {"session_id": sid, "sessionId": sid, "id": sid, "title_id": m_action.group(1).upper(), "players": [], "public_slots": 16, "private_slots": 0, "host_address": self.state.host_ip, "hostAddress": self.state.host_ip, "port": self.state.port})
            if action == "join":
                for key in ("xuid", "player_id"):
                    if key in body:
                        xuid = str(body[key])
                        break
                else:
                    xuids = body.get("xuids") or []
                    xuid = str(xuids[0]) if xuids else f"player-{len(session['players'])+1}"
                if not any(str(p.get("xuid")) == xuid for p in session["players"]):
                    session["players"].append({"xuid": xuid, "private": bool(body.get("private", False)), "joined_at": stamp()})
                self.state.recalc(session)
                log(f"HTTP session join {sid} xuid={xuid}")
            elif action == "leave":
                xuid = str(body.get("xuid") or body.get("player_id") or "")
                session["players"] = [p for p in session.get("players", []) if str(p.get("xuid")) != xuid]
                self.state.recalc(session)
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


class UdpBootstrap(threading.Thread):
    def __init__(self, state: State, bind_host: str, bind_port: int, targets: list[tuple[str, int]], interval: float, verbose: bool, trace_every: int):
        super().__init__(daemon=True)
        self.state = state
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.targets = targets
        self.interval = interval
        self.verbose = verbose
        self.trace_every = max(1, trace_every)
        self.running = True
        self.peers: set[tuple[str, int]] = set()

    def packet(self, reason: str = "beacon") -> bytes:
        first = next(iter(self.state.sessions.values()))
        sid = int(str(first["session_id"]), 16) & 0xFFFFFFFFFFFFFFFF
        ip_parts = [int(x) for x in self.state.host_ip.split(".") if x.isdigit()]
        while len(ip_parts) < 4:
            ip_parts.append(0)
        header = b"CODERED_RDR_V12\0"
        tail = (
            f";reason={reason};mp=freemode,mp_idle,"
            "multiplayer_system_thread,multiplayer_update_thread,"
            "deathmatch,ctf;SYSTEM_LINK_BOOTSTRAP;"
        ).encode("ascii")
        return header + struct.pack(">QBBBBH", sid, *ip_parts[:4], self.state.port) + tail

    def send_packet(self, sock: socket.socket, target: tuple[str, int], reason: str) -> None:
        pkt = self.packet(reason)
        try:
            sock.sendto(pkt, target)
            if self.verbose:
                log(f"UDP {reason} {len(pkt)} bytes -> {target[0]}:{target[1]} preview={pkt[:24].hex(' ').upper()}")
        except OSError as e:
            if self.verbose:
                log(f"UDP {reason} failed -> {target}: {e}")

    def should_trace(self, count: int) -> bool:
        return self.verbose or count == 1 or (count % self.trace_every) == 0

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except OSError:
            pass
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        try:
            sock.bind((self.bind_host, self.bind_port))
            sock.settimeout(0.1)
            mode = "passive" if self.interval <= 0 else f"beacon every {self.interval:.2f}s"
            log(f"UDP tracer listening on {self.bind_host}:{self.bind_port} ({mode})")
        except OSError as e:
            log(f"UDP tracer could not bind {self.bind_host}:{self.bind_port}: {e}. Receive tracing disabled.")
            sock.settimeout(0.1)
        last_send = 0.0
        seen = 0
        self_seen = 0
        while self.running:
            now = time.time()
            if self.interval > 0 and now - last_send >= self.interval:
                for target in [*self.targets, *sorted(self.peers)]:
                    self.send_packet(sock, target, "beacon")
                last_send = now
            try:
                data, addr = sock.recvfrom(4096)
                if data.startswith(CODERED_UDP_PREFIXES):
                    self_seen += 1
                    if self.verbose and self.should_trace(self_seen):
                        preview = data[:24].hex(" ").upper()
                        log(f"UDP self-bootstrap ignored #{self_seen} {len(data)} bytes from {addr[0]}:{addr[1]} preview={preview}")
                    continue
                seen += 1
                self.peers.add((addr[0], self.state.port))
                self.peers.add((addr[0], addr[1]))
                preview = data[:24].hex(" ").upper()
                if self.should_trace(seen):
                    log(f"UDP inbound #{seen} {len(data)} bytes from {addr[0]}:{addr[1]} preview={preview}")
                self.send_packet(sock, (addr[0], addr[1]), "direct-reply")
                if addr[1] != self.state.port:
                    self.send_packet(sock, (addr[0], self.state.port), "port-3074-reply")
            except socket.timeout:
                pass
            except OSError:
                time.sleep(0.1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=36000)
    ap.add_argument("--title-id", default="5454082B")
    ap.add_argument("--target-ip", default="")
    ap.add_argument("--system-link-port", type=int, default=3074)
    ap.add_argument("--udp-bind", default="0.0.0.0")
    ap.add_argument("--udp-port", type=int, default=3074)
    ap.add_argument("--beacon-interval", type=float, default=0.0)
    ap.add_argument("--trace-every", type=int, default=120)
    ap.add_argument("--log-file", default="logs/codered_udp_bootstrap_v12.log")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    global LOG_FILE
    LOG_FILE = pathlib.Path(args.log_file)
    target_ip = args.target_ip or guess_ip()
    manifest = default_manifest()
    state = State(args.title_id, target_ip, args.system_link_port, manifest)
    targets = []
    for ip in [target_ip, "127.0.0.1", "255.255.255.255"]:
        if ip and (ip, args.system_link_port) not in targets:
            targets.append((ip, args.system_link_port))
    udp = UdpBootstrap(state, args.udp_bind, args.udp_port, targets, args.beacon_interval, args.verbose, args.trace_every)
    udp.start()

    class ReuseTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    httpd = ReuseTCPServer((args.host, args.port), Handler)
    httpd.state = state  # type: ignore[attr-defined]
    httpd.verbose = args.verbose  # type: ignore[attr-defined]
    log(f"CodeRED RDR BootstrapHost v12 HTTP listening on http://{args.host}:{args.port}/")
    log(f"Target/System Link identity: {target_ip}:{args.system_link_port}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
