#!/usr/bin/env python3
"""
CodeRED SPHost AI Guest Controller v17

Sends script-controlled AI guest commands to the local AI bridge service and
keeps durable local state files for the future RDR game bridge. This never
contacts Xbox Live.
"""
from __future__ import annotations

import argparse
import os
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path.cwd()
SCRATCH = ROOT / "scratch"
LOGS = ROOT / "logs"
STATE_PATH = SCRATCH / "codered_ai_guest_state.json"
COMMANDS_PATH = SCRATCH / "codered_ai_guest_commands.jsonl"
ACTION_PLAN_PATH = SCRATCH / "codered_ai_guest_action_plan_v17.json"
LOG_PATH = LOGS / "codered_ai_guest_v17.log"
PROFILE_PATH = ROOT / "data" / "codered" / "rdr_sphost_ai_guest_profile_v17.json"

BRIDGE_DEFAULT = "http://127.0.0.1:36017"
ENDPOINTS = ("/codered/ai_guest", "/ai_guest", "/state/ai_guest")

ALLOWED_COMMANDS = {
    "follow": "Follow player and maintain bodyguard spacing.",
    "guard": "Guard current position / stay nearby.",
    "attack": "Attack hostile targets if a game bridge can consume it.",
    "idle": "Hold fire and wait.",
    "regroup": "Request a reattach/warp/regroup near player.",
    "defend": "Defend player from hostile targets.",
    "mount": "Request mount / horse behavior if bridge can consume it.",
    "dismount": "Request dismount behavior if bridge can consume it.",
}

DEFAULT_PROFILE: Dict[str, Any] = {
    "schema": "codered.ai_guest.profile.v17",
    "name": "CodeRED_AI_01",
    "display_name": "CodeRED AI Guest",
    "guest_type": "script_controlled_ai",
    "mode": "sp-host",
    "behavior": "follow_defend",
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
}


def now_stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs() -> None:
    SCRATCH.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    ensure_dirs()
    line = f"[{now_stamp()}] {message}"
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def local_ip_guess() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip or "127.0.0.1"
    except Exception:
        return "127.0.0.1"


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    ensure_dirs()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def load_profile() -> Dict[str, Any]:
    ensure_dirs()
    if not PROFILE_PATH.exists():
        write_json(PROFILE_PATH, DEFAULT_PROFILE)
        return dict(DEFAULT_PROFILE)
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"Profile parse failed; using defaults: {exc}")
        return dict(DEFAULT_PROFILE)


def load_state() -> Dict[str, Any]:
    ensure_dirs()
    profile = load_profile()
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            state["profile"] = profile
            state["schema"] = "codered.ai_guest.state.v17"
            return state
        except Exception as exc:
            log(f"State parse failed; rebuilding state: {exc}")
    return {
        "schema": "codered.ai_guest.state.v17",
        "created_at": now_stamp(),
        "updated_at": now_stamp(),
        "active": False,
        "joined": False,
        "spawn_requested": False,
        "visible_body_confirmed": False,
        "mode": profile.get("mode", "sp-host"),
        "name": profile.get("name", "CodeRED_AI_01"),
        "display_name": profile.get("display_name", "CodeRED AI Guest"),
        "behavior": profile.get("behavior", "follow_defend"),
        "target": profile.get("target", "local_player"),
        "last_command": "none",
        "command_seq": 0,
        "bridge": {
            "base_url": BRIDGE_DEFAULT,
            "last_post_status": "not_attempted",
            "last_post_at": None,
            "reachable": None,
        },
        "local": {
            "ip_guess": local_ip_guess(),
            "root": str(ROOT),
        },
        "profile": profile,
    }


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = now_stamp()
    write_json(STATE_PATH, state)


def append_command(event: Dict[str, Any]) -> None:
    ensure_dirs()
    with COMMANDS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def make_local_action_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    profile = state.get("profile") or load_profile()
    follow = profile.get("follow", {})
    behavior = state.get("behavior", "idle")
    plan: Dict[str, Any] = {
        "schema": "codered.ai_guest.action_plan.v17.local_fallback",
        "updated_at": now_stamp(),
        "active": state.get("active", False),
        "behavior": behavior,
        "target": state.get("target", "local_player"),
        "needs_visible_body": bool(state.get("active")) and not bool(state.get("visible_body_confirmed")),
        "steps": [],
    }
    if state.get("active") and not state.get("visible_body_confirmed"):
        plan["steps"].append({"type": "request_spawn_actor", "attach_to": state.get("target", "local_player")})
    if behavior in ("spawn", "follow", "follow_defend", "defend"):
        plan["steps"].append({"type": "follow_target", "follow_distance_m": follow.get("follow_distance_m", 8.0)})
    elif behavior == "guard":
        plan["steps"].append({"type": "guard_position"})
    elif behavior == "attack":
        plan["steps"].append({"type": "attack_hostiles"})
    elif behavior == "regroup":
        plan["steps"].append({"type": "force_regroup_or_warp"})
    elif behavior == "idle":
        plan["steps"].append({"type": "idle_hold_fire"})
    write_json(ACTION_PLAN_PATH, plan)
    return plan


def post_to_bridge(state: Dict[str, Any], action: str, bridge: str, timeout: float, no_post: bool) -> Tuple[str, List[str], Dict[str, Any] | None]:
    if no_post:
        return "disabled", [], None
    payload = json.dumps({"action": action, "state": state}).encode("utf-8")
    errors: List[str] = []
    base = bridge.rstrip("/")
    for endpoint in ENDPOINTS:
        url = base + endpoint
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "CodeRED-AI-Guest-v17"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body) if body else {}
                return f"ok {resp.status} {endpoint}", errors, data
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    return "bridge_not_reachable", errors, None


def get_bridge_status(bridge: str, timeout: float) -> Tuple[str, Dict[str, Any] | None]:
    try:
        with urllib.request.urlopen(bridge.rstrip("/") + "/health", timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return f"ok {resp.status}", json.loads(body) if body else {}
    except Exception as exc:
        return f"not_ready {type(exc).__name__}: {exc}", None


def update_bridge_status(state: Dict[str, Any], post_status: str, errors: List[str], bridge: str) -> None:
    host = state.setdefault("bridge", {})
    host["base_url"] = bridge
    host["last_post_status"] = post_status
    host["last_post_at"] = now_stamp()
    host["reachable"] = post_status.startswith("ok ")
    if errors:
        host["last_post_errors"] = errors[-4:]


def commit_action(state: Dict[str, Any], action: str, args: argparse.Namespace) -> Dict[str, Any]:
    state["command_seq"] = int(state.get("command_seq", 0)) + 1
    state["last_command"] = action
    state["last_command_at"] = now_stamp()
    state.setdefault("local", {})["ip_guess"] = local_ip_guess()

    if action == "spawn":
        state["active"] = True
        state["joined"] = True
        state["spawn_requested"] = True
        state["visible_body_confirmed"] = False
        state["behavior"] = getattr(args, "behavior", None) or "follow_defend"
        state["target"] = getattr(args, "target", None) or "local_player"
    elif action == "dismiss":
        state["active"] = False
        state["joined"] = False
        state["spawn_requested"] = False
        state["behavior"] = "idle"
    elif action.startswith("command:"):
        command = action.split(":", 1)[1]
        state["active"] = True
        state["joined"] = True
        state["behavior"] = command
    elif action == "confirm-visible":
        state["visible_body_confirmed"] = True
    elif action == "status":
        pass
    make_local_action_plan(state)
    event = {
        "at": now_stamp(),
        "seq": state["command_seq"],
        "action": action,
        "active": state.get("active"),
        "joined": state.get("joined"),
        "behavior": state.get("behavior"),
        "target": state.get("target"),
    }
    append_command(event)
    return state


def print_status(state: Dict[str, Any]) -> None:
    print("\nCodeRED AI Guest v17 Status")
    print("-" * 44)
    for key in ["active", "joined", "spawn_requested", "visible_body_confirmed", "name", "behavior", "target", "last_command", "updated_at"]:
        print(f"{key:25}: {state.get(key)}")
    bridge = state.get("bridge", {})
    print(f"{'bridge':25}: {bridge.get('base_url', BRIDGE_DEFAULT)}")
    print(f"{'bridge post':25}: {bridge.get('last_post_status')}")
    print(f"{'state path':25}: {STATE_PATH}")
    print(f"{'action plan':25}: {ACTION_PLAN_PATH}")
    print(f"{'commands path':25}: {COMMANDS_PATH}")
    print(f"{'log path':25}: {LOG_PATH}")
    print()


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeRED SPHost AI Guest Controller v17")
    parser.add_argument("--bridge", default=BRIDGE_DEFAULT, help="AI bridge URL. Default: http://127.0.0.1:36017")
    parser.add_argument("--timeout", type=float, default=0.55, help="Short POST timeout in seconds.")
    parser.add_argument("--no-post", action="store_true", help="Only write local state; do not POST to AI Bridge.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    spawn = sub.add_parser("spawn", help="Spawn/register the AI guest state.")
    spawn.add_argument("--behavior", default="follow_defend")
    spawn.add_argument("--target", default="local_player")

    cmd = sub.add_parser("command", help="Send a behavior command to the AI guest.")
    cmd.add_argument("command", choices=sorted(ALLOWED_COMMANDS.keys()))

    sub.add_parser("dismiss", help="Dismiss/despawn the AI guest state.")
    sub.add_parser("confirm-visible", help="Mark the in-world body as confirmed by a future bridge/test.")
    sub.add_parser("status", help="Print current AI guest status.")
    sub.add_parser("bridge-status", help="Check AI bridge health.")
    sub.add_parser("init", help="Create default profile/state/action files only.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    ensure_dirs()
    state = load_state()
    state.setdefault("bridge", {})["base_url"] = args.bridge

    if args.cmd == "init":
        save_state(state)
        make_local_action_plan(state)
        log("Initialized AI guest v17 profile/state files.")
        print_status(state)
        return 0

    if args.cmd == "bridge-status":
        status, data = get_bridge_status(args.bridge, args.timeout)
        log(f"AI bridge health: {status}")
        if data:
            print(json.dumps(data, indent=2, sort_keys=True))
        return 0 if status.startswith("ok") else 2

    if args.cmd == "status":
        state = commit_action(state, "status", args)
        save_state(state)
        print_status(state)
        return 0

    if args.cmd == "spawn":
        state = commit_action(state, "spawn", args)
    elif args.cmd == "command":
        state = commit_action(state, f"command:{args.command}", args)
    elif args.cmd == "dismiss":
        state = commit_action(state, "dismiss", args)
    elif args.cmd == "confirm-visible":
        state = commit_action(state, "confirm-visible", args)
    else:
        raise AssertionError(args.cmd)

    post_action = state["last_command"].replace("command:", "")
    post_status, errors, response = post_to_bridge(state, post_action, args.bridge, args.timeout, args.no_post)
    if response and isinstance(response.get("state"), dict):
        state = response["state"]
    update_bridge_status(state, post_status, errors, args.bridge)
    save_state(state)
    make_local_action_plan(state)
    log(f"AI guest action={state['last_command']} active={state.get('active')} behavior={state.get('behavior')} bridge={post_status}")
    if errors and post_status == "bridge_not_reachable":
        log("AI bridge is not running yet; local state/action-plan still written. Start CodeRED_Start_AI_Guest_Bridge_v17.bat.")
    print_status(state)
    return 0


if __name__ == "__main__":
    _code = main(sys.argv[1:])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(_code))
