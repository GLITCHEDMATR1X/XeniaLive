#!/usr/bin/env python3
"""
CodeRED SPHost AI Guest Bridge v17

Local private AI bridge for CodeRED/Xenia RDR SPHost experiments.
This service never contacts Xbox Live. It accepts local AI guest commands,
keeps durable state/action-plan JSON files, and exposes a small localhost API
that future bootstrap/game bridge code can consume.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path.cwd()
SCRATCH = ROOT / "scratch"
LOGS = ROOT / "logs"
STATE_PATH = SCRATCH / "codered_ai_guest_state.json"
BRIDGE_STATE_PATH = SCRATCH / "codered_ai_guest_bridge_state_v17.json"
ACTION_PLAN_PATH = SCRATCH / "codered_ai_guest_action_plan_v17.json"
COMMANDS_PATH = SCRATCH / "codered_ai_guest_commands.jsonl"
LOG_PATH = LOGS / "codered_ai_guest_bridge_v17.log"
PROFILE_PATH = ROOT / "data" / "codered" / "rdr_sphost_ai_guest_profile_v17.json"

ALLOWED = {
    "spawn", "follow", "guard", "attack", "defend", "idle", "regroup",
    "mount", "dismount", "dismiss", "status", "heartbeat", "stop",
}

DEFAULT_PROFILE: Dict[str, Any] = {
    "schema": "codered.ai_guest.profile.v17",
    "name": "CodeRED_AI_01",
    "display_name": "CodeRED AI Guest",
    "guest_type": "script_controlled_ai",
    "mode": "sp-host",
    "target": "local_player",
    "preferred_spawn_style": "bodyguard_companion",
    "follow": {
        "follow_distance_m": 8.0,
        "regroup_distance_m": 45.0,
        "warp_distance_m": 80.0,
        "respawn_delay_sec": 10,
    },
    "combat": {
        "defend_player": True,
        "attack_hostiles": True,
        "avoid_friendly_fire": True,
        "hold_fire_when_idle": True,
    },
    "session": {
        "fake_xuid": "0xC0DE000000000101",
        "fake_machine_id": "0xC0DEF00D00000101",
        "session_role": "ai_guest",
    },
    "bridge": {
        "host": "127.0.0.1",
        "port": 36017,
        "bootstrap_host": "http://127.0.0.1:36000",
        "safe_local_only": True,
    },
}

LOCK = threading.RLock()
STOP = threading.Event()
SERVER_STATE: Dict[str, Any] = {}


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs() -> None:
    SCRATCH.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ensure_dirs()
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"Failed to read {path}: {exc}")
    return dict(fallback)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_dirs()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_command(event: Dict[str, Any]) -> None:
    ensure_dirs()
    with COMMANDS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def load_profile() -> Dict[str, Any]:
    ensure_dirs()
    if not PROFILE_PATH.exists():
        write_json(PROFILE_PATH, DEFAULT_PROFILE)
    return read_json(PROFILE_PATH, DEFAULT_PROFILE)


def default_guest_state(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "codered.ai_guest.state.v17",
        "created_at": now(),
        "updated_at": now(),
        "active": False,
        "joined": False,
        "spawn_requested": False,
        "visible_body_confirmed": False,
        "mode": profile.get("mode", "sp-host"),
        "name": profile.get("name", "CodeRED_AI_01"),
        "display_name": profile.get("display_name", "CodeRED AI Guest"),
        "behavior": "idle",
        "target": profile.get("target", "local_player"),
        "last_command": "none",
        "command_seq": 0,
        "profile": profile,
        "bridge": {
            "running": False,
            "last_seen_at": None,
            "last_action_plan_at": None,
            "ready_for_game_bridge": True,
            "visible_actor_bridge": "pending",
            "safe_local_only": True,
        },
        "desired_game_bridge": {
            "note": "Future game/RDR bridge can consume this file to spawn/control a visible companion."
        },
    }


def normalize_command(action: str) -> str:
    action = (action or "").strip().lower().replace("command:", "")
    aliases = {"warp": "regroup", "hold": "guard", "bodyguard": "spawn"}
    action = aliases.get(action, action)
    return action if action in ALLOWED else "status"


def build_action_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    profile = state.get("profile") or load_profile()
    follow = profile.get("follow", {})
    combat = profile.get("combat", {})
    behavior = state.get("behavior", "idle")
    active = bool(state.get("active"))
    visible = bool(state.get("visible_body_confirmed"))

    plan: Dict[str, Any] = {
        "schema": "codered.ai_guest.action_plan.v17",
        "updated_at": now(),
        "active": active,
        "name": state.get("name", "CodeRED_AI_01"),
        "target": state.get("target", "local_player"),
        "behavior": behavior,
        "visible_body_confirmed": visible,
        "needs_visible_body": active and not visible,
        "safe_local_only": True,
        "steps": [],
        "game_bridge_contract": {
            "read_state": str(STATE_PATH),
            "read_action_plan": str(ACTION_PLAN_PATH),
            "write_visible_body_confirmed": True,
            "never_contact_real_xbox_live": True,
        },
    }

    steps: List[Dict[str, Any]] = plan["steps"]
    if not active:
        steps.append({"type": "despawn_or_idle", "reason": "AI guest inactive"})
        return plan

    if not visible:
        steps.append({
            "type": "request_spawn_actor",
            "spawn_style": profile.get("preferred_spawn_style", "bodyguard_companion"),
            "attach_to": state.get("target", "local_player"),
            "respawn_delay_sec": follow.get("respawn_delay_sec", 10),
        })

    if behavior in ("follow", "spawn", "defend", "follow_defend"):
        steps.append({
            "type": "follow_target",
            "target": state.get("target", "local_player"),
            "follow_distance_m": follow.get("follow_distance_m", 8.0),
            "regroup_distance_m": follow.get("regroup_distance_m", 45.0),
            "warp_distance_m": follow.get("warp_distance_m", 80.0),
        })
    elif behavior == "guard":
        steps.append({"type": "guard_position", "target": state.get("target", "local_player"), "radius_m": 12.0})
    elif behavior == "attack":
        steps.append({"type": "attack_hostiles", "target_selector": "nearest_hostile_to_player"})
    elif behavior == "idle":
        steps.append({"type": "idle_hold_fire", "hold_fire": combat.get("hold_fire_when_idle", True)})
    elif behavior == "regroup":
        steps.append({"type": "force_regroup_or_warp", "target": state.get("target", "local_player")})
    elif behavior == "mount":
        steps.append({"type": "request_mount", "target": state.get("target", "local_player")})
    elif behavior == "dismount":
        steps.append({"type": "request_dismount"})

    if behavior in ("spawn", "follow", "defend", "follow_defend", "attack") and combat.get("defend_player", True):
        steps.append({
            "type": "defend_player",
            "attack_hostiles": combat.get("attack_hostiles", True),
            "avoid_friendly_fire": combat.get("avoid_friendly_fire", True),
        })
    return plan


def update_state_with_action(state: Dict[str, Any], action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    action = normalize_command(action)
    state = dict(state)
    state["updated_at"] = now()
    state["command_seq"] = int(state.get("command_seq", 0)) + 1
    state["last_command"] = action
    state["last_command_at"] = now()
    state.setdefault("bridge", {})["running"] = True
    state["bridge"]["last_seen_at"] = now()

    if action == "spawn":
        state["active"] = True
        state["joined"] = True
        state["spawn_requested"] = True
        state["behavior"] = payload.get("behavior") or "follow_defend"
        state["target"] = payload.get("target") or state.get("target", "local_player")
    elif action == "dismiss":
        state["active"] = False
        state["joined"] = False
        state["spawn_requested"] = False
        state["behavior"] = "idle"
    elif action == "stop":
        state["behavior"] = "idle"
        STOP.set()
    elif action not in ("status", "heartbeat"):
        state["active"] = True
        state["joined"] = True
        state["behavior"] = action

    if "visible_body_confirmed" in payload:
        state["visible_body_confirmed"] = bool(payload["visible_body_confirmed"])

    plan = build_action_plan(state)
    state["bridge"]["last_action_plan_at"] = plan["updated_at"]
    state["desired_game_bridge"] = plan
    return state


def load_combined_state() -> Dict[str, Any]:
    profile = load_profile()
    state = read_json(STATE_PATH, default_guest_state(profile))
    if "schema" not in state or not str(state.get("schema", "")).endswith("v17"):
        old = dict(state)
        state = default_guest_state(profile)
        for key in ["active", "joined", "spawn_requested", "visible_body_confirmed", "name", "display_name", "behavior", "target", "last_command", "command_seq"]:
            if key in old:
                state[key] = old[key]
    state["profile"] = profile
    return state


def persist_state(state: Dict[str, Any]) -> None:
    write_json(STATE_PATH, state)
    write_json(BRIDGE_STATE_PATH, state)
    write_json(ACTION_PLAN_PATH, build_action_plan(state))


def refresh_from_disk() -> None:
    global SERVER_STATE
    with LOCK:
        current = load_combined_state()
        current.setdefault("bridge", {})["running"] = True
        current["bridge"]["last_seen_at"] = now()
        SERVER_STATE = current
        persist_state(SERVER_STATE)


def watcher_loop(tick: float) -> None:
    while not STOP.is_set():
        try:
            refresh_from_disk()
        except Exception as exc:
            log(f"watcher refresh failed: {exc}")
        STOP.wait(tick)


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeRED-AI-Guest-Bridge-v17/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log(f"HTTP {self.client_address[0]} {fmt % args}")

    def _send(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"raw": raw.decode("utf-8", errors="replace")}

    def do_GET(self) -> None:  # noqa: N802
        with LOCK:
            state = dict(SERVER_STATE or load_combined_state())
        if self.path in ("/", "/health", "/codered/health"):
            self._send(200, {"ok": True, "service": "codered_ai_guest_bridge_v17", "time": now(), "active": state.get("active")})
        elif self.path in ("/codered/ai_guest", "/ai_guest", "/state/ai_guest"):
            self._send(200, state)
        elif self.path in ("/codered/ai_guest/action_plan", "/action_plan"):
            self._send(200, build_action_plan(state))
        elif self.path in ("/codered/ai_guest/commands", "/commands"):
            lines = []
            if COMMANDS_PATH.exists():
                lines = COMMANDS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
            self._send(200, {"commands": lines, "path": str(COMMANDS_PATH)})
        else:
            self._send(404, {"ok": False, "error": "unknown endpoint", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()
        action = payload.get("action") or payload.get("command") or "status"
        nested_state = payload.get("state")
        with LOCK:
            global SERVER_STATE
            base = nested_state if isinstance(nested_state, dict) else (SERVER_STATE or load_combined_state())
            SERVER_STATE = update_state_with_action(base, action, payload)
            persist_state(SERVER_STATE)
            append_command({
                "at": now(),
                "source": "bridge_http",
                "action": normalize_command(action),
                "path": self.path,
                "seq": SERVER_STATE.get("command_seq"),
                "behavior": SERVER_STATE.get("behavior"),
            })
        self._send(200, {"ok": True, "accepted": normalize_command(action), "state": SERVER_STATE, "action_plan": build_action_plan(SERVER_STATE)})


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CodeRED SPHost AI Guest Bridge v17")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=36017)
    p.add_argument("--tick", type=float, default=1.0)
    p.add_argument("--bootstrap-host", default="http://127.0.0.1:36000")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    ensure_dirs()
    refresh_from_disk()
    log(f"Starting AI Guest Bridge v17 at http://{args.host}:{args.port} bootstrap={args.bootstrap_host}")

    watcher = threading.Thread(target=watcher_loop, args=(args.tick,), daemon=True)
    watcher.start()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)

    def stop_handler(signum: int, frame: Any) -> None:
        STOP.set()
        try:
            httpd.shutdown()
        except Exception:
            pass

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    try:
        httpd.serve_forever(poll_interval=0.25)
    finally:
        STOP.set()
        with LOCK:
            state = SERVER_STATE or load_combined_state()
            state.setdefault("bridge", {})["running"] = False
            state["bridge"]["stopped_at"] = now()
            persist_state(state)
        log("AI Guest Bridge v17 stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
