#!/usr/bin/env python3
"""Code RED minimal private host for Xenia RDR System Link experiments.

Routes: /players, /players/find, /title/{titleId}/sessions, /title/{titleId}/sessions/search, /qos.

This is a dependency-free, local-first bridge that mirrors the route shape used
by the uploaded Xenia WebServices extension closely enough for Canary test
passes. It is intentionally small: it stores players, sessions, joins/leaves,
and QoS blobs so two local/LAN Xenia instances can discover the same advertised
session without needing MongoDB or a full NestJS service.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field, asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_STATE = Path("scratch/codered_private_host_state.json")


@dataclass
class Player:
    xuid: str
    machineId: str = "0000000000000000"
    hostAddress: str = "127.0.0.1"
    macAddress: str = "02:58:7F:00:00:01"
    keyExchangeKey: str = "00000000000000000000000000000000"
    port: int = 3074
    titleId: str = "5454082B"
    sessionId: str = "0000000000000000"


@dataclass
class Session:
    id: str
    sessionId: str
    titleId: str
    flags: int = 0
    publicSlotsCount: int = 0
    privateSlotsCount: int = 0
    openPublicSlotsCount: int = 0
    openPrivateSlotsCount: int = 0
    filledPublicSlotsCount: int = 0
    filledPrivateSlotsCount: int = 0
    hostAddress: str = "127.0.0.1"
    macAddress: str = "02:58:7F:00:00:01"
    keyExchangeKey: str = "00000000000000000000000000000000"
    port: int = 3074
    started: bool = False
    advertised: bool = True
    reason: str = "create"
    players: list[dict[str, Any]] = field(default_factory=list)
    qos: str = ""

    def public_view(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("qos", None)
        return data


    def refresh_slot_counts(self) -> None:
        filled_private = sum(1 for player in self.players if bool(player.get("privateSlot", False)))
        filled_public = max(0, len(self.players) - filled_private)
        self.filledPublicSlotsCount = filled_public
        self.filledPrivateSlotsCount = filled_private
        self.openPublicSlotsCount = max(0, self.publicSlotsCount - filled_public)
        self.openPrivateSlotsCount = max(0, self.privateSlotsCount - filled_private)

class PrivateHostState:
    def __init__(self, path: Path):
        self.path = path
        self.players: dict[str, Player] = {}
        self.sessions: dict[str, dict[str, Session]] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.players = {
            key: Player(**value) for key, value in raw.get("players", {}).items()
        }
        self.sessions = {}
        for title_id, sessions in raw.get("sessions", {}).items():
            self.sessions[title_id.upper()] = {
                session_id.upper(): Session(**value)
                for session_id, value in sessions.items()
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "players": {key: asdict(value) for key, value in self.players.items()},
            "sessions": {
                title: {sid: asdict(sess) for sid, sess in sessions.items()}
                for title, sessions in self.sessions.items()
            },
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def upsert_player(self, data: dict[str, Any], fallback_ip: str) -> Player:
        xuid = str(data.get("xuid") or data.get("id") or "0000000000000000").upper()
        player = Player(
            xuid=xuid,
            machineId=str(data.get("machineId") or "0000000000000000").upper(),
            hostAddress=str(data.get("hostAddress") or fallback_ip),
            macAddress=str(data.get("macAddress") or "02:58:7F:00:00:01"),
            keyExchangeKey=str(data.get("keyExchangeKey") or data.get("key_exchange") or "00000000000000000000000000000000").upper(),
            port=int(data.get("port") or 3074),
            titleId=str(data.get("titleId") or "5454082B").upper(),
            sessionId=str(data.get("sessionId") or "0000000000000000").upper(),
        )
        self.players[xuid] = player
        self.save()
        return player

    def upsert_session(self, title_id: str, data: dict[str, Any], fallback_ip: str) -> Session:
        title_id = title_id.upper()
        session_id = str(data.get("sessionId") or data.get("id") or "0000000000000000").upper()
        players = data.get("players") if isinstance(data.get("players"), list) else []
        session = Session(
            id=session_id,
            sessionId=session_id,
            titleId=title_id,
            flags=int(data.get("flags") or 0),
            publicSlotsCount=int(data.get("publicSlotsCount") or 0),
            privateSlotsCount=int(data.get("privateSlotsCount") or 0),
            openPublicSlotsCount=int(data.get("openPublicSlotsCount") or data.get("publicSlotsCount") or 0),
            openPrivateSlotsCount=int(data.get("openPrivateSlotsCount") or data.get("privateSlotsCount") or 0),
            filledPublicSlotsCount=int(data.get("filledPublicSlotsCount") or 0),
            filledPrivateSlotsCount=int(data.get("filledPrivateSlotsCount") or 0),
            hostAddress=str(data.get("hostAddress") or fallback_ip),
            macAddress=str(data.get("macAddress") or "02:58:7F:00:00:01"),
            keyExchangeKey=str(data.get("keyExchangeKey") or data.get("key_exchange") or "00000000000000000000000000000000").upper(),
            port=int(data.get("port") or 3074),
            started=bool(data.get("started") or False),
            advertised=bool(data.get("advertised", True)),
            reason=str(data.get("reason") or "create"),
            players=players,
        )
        session.refresh_slot_counts()
        self.sessions.setdefault(title_id, {})[session_id] = session
        for player in players:
            xuid = str(player.get("xuid", "")).upper()
            if xuid in self.players:
                self.players[xuid].sessionId = session_id
        self.save()
        return session

    def get_session(self, title_id: str, session_id: str) -> Session | None:
        return self.sessions.get(title_id.upper(), {}).get(session_id.upper())

    def search_sessions(self, title_id: str, limit: int) -> list[dict[str, Any]]:
        sessions = list(self.sessions.get(title_id.upper(), {}).values())
        return [session.public_view() for session in sessions if session.advertised][:limit]

    def join_session(self, title_id: str, session_id: str, xuids: list[str]) -> Session | None:
        session = self.get_session(title_id, session_id)
        if not session:
            return None
        known = {str(player.get("xuid", "")).upper() for player in session.players}
        for xuid in [str(item).upper() for item in xuids]:
            if xuid and xuid not in known:
                session.players.append({"xuid": xuid, "privateSlot": False})
                known.add(xuid)
            if xuid in self.players:
                self.players[xuid].sessionId = session.sessionId
        session.refresh_slot_counts()
        self.save()
        return session

    def leave_session(self, title_id: str, session_id: str, xuids: list[str]) -> Session | None:
        session = self.get_session(title_id, session_id)
        if not session:
            return None
        leaving = {str(item).upper() for item in xuids}
        session.players = [
            player for player in session.players
            if str(player.get("xuid", "")).upper() not in leaving
        ]
        for xuid in leaving:
            if xuid in self.players:
                self.players[xuid].sessionId = "0000000000000000"
        session.refresh_slot_counts()
        self.save()
        return session


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeREDRDRPrivateHost/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    @property
    def state(self) -> PrivateHostState:
        return self.server.state  # type: ignore[attr-defined]

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {"_raw": raw.decode("utf-8", errors="replace")}

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.strip("/").split("/")
        if path == ["health"]:
            self.send_json({"ok": True, "service": "codered-rdr-private-host"})
            return
        if path == ["whoami"]:
            self.send_json({"address": self.client_address[0]})
            return
        if len(path) >= 4 and path[0] == "title" and path[2] == "sessions":
            title_id = path[1].upper()
            session_id = path[3].upper()
            session = self.state.get_session(title_id, session_id)
            if not session:
                self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                return
            if len(path) == 5 and path[4] == "qos":
                raw = session.qos.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            self.send_json(session.public_view())
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.strip("/").split("/")
        body = self.read_json()
        fallback_ip = self.client_address[0]
        if path == ["players"]:
            player = self.state.upsert_player(body, fallback_ip)
            self.send_json(asdict(player), HTTPStatus.CREATED)
            return
        if path == ["players", "find"]:
            host = str(body.get("hostAddress") or "")
            for player in self.state.players.values():
                if player.hostAddress == host:
                    self.send_json(asdict(player))
                    return
            self.send_json({"error": "player not found"}, HTTPStatus.NOT_FOUND)
            return
        if len(path) >= 3 and path[0] == "title" and path[2] == "sessions":
            title_id = path[1].upper()
            if len(path) == 3:
                session = self.state.upsert_session(title_id, body, fallback_ip)
                self.send_json(session.public_view(), HTTPStatus.CREATED)
                return
            if len(path) == 4 and path[3] == "search":
                limit = int(body.get("resultsCount") or body.get("limit") or 16)
                self.send_json(self.state.search_sessions(title_id, limit))
                return
            if len(path) >= 5:
                session_id = path[3].upper()
                action = path[4]
                xuids = body.get("xuids") if isinstance(body.get("xuids"), list) else []
                if action == "join":
                    session = self.state.join_session(title_id, session_id, xuids)
                    if not session:
                        self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                        return
                    self.send_json(session.public_view())
                    return
                if action == "leave":
                    session = self.state.leave_session(title_id, session_id, xuids)
                    if not session:
                        self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                        return
                    self.send_json(session.public_view())
                    return
                if action == "modify":
                    session = self.state.get_session(title_id, session_id)
                    if not session:
                        self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                        return
                    for key in ("flags", "publicSlotsCount", "privateSlotsCount"):
                        if key in body:
                            setattr(session, key, int(body[key]))
                    self.state.save()
                    self.send_json(session.public_view())
                    return
                if action == "qos":
                    session = self.state.get_session(title_id, session_id)
                    if not session:
                        self.send_json({"error": "session not found"}, HTTPStatus.NOT_FOUND)
                        return
                    session.qos = json.dumps(body)
                    self.state.save()
                    self.send_json({"ok": True})
                    return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.strip("/").split("/")
        if len(path) == 4 and path[0] == "title" and path[2] == "sessions":
            title_id = path[1].upper()
            session_id = path[3].upper()
            removed = self.state.sessions.get(title_id, {}).pop(session_id, None)
            self.state.save()
            self.send_json({"removed": bool(removed)})
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=36000)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    state = PrivateHostState(args.state)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = state  # type: ignore[attr-defined]
    server.verbose = args.verbose  # type: ignore[attr-defined]
    print(f"Code RED RDR private host listening on http://{args.host}:{args.port}/")
    print(f"State: {args.state}")
    try:
      server.serve_forever()
    except KeyboardInterrupt:
      print("\nStopped private host.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
