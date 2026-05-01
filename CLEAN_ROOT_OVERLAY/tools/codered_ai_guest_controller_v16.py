#!/usr/bin/env python3
"""
CodeRED SPHost AI Guest Controller v16

Safe script-controlled AI guest state bridge for RDR SPHost.
This does not patch Xenia C++ and does not contact Xbox Live.
"""
from __future__ import annotations

import argparse
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
LOG_PATH = LOGS / "codered_ai_guest_v16.log"
PROFILE_PATH = ROOT / "data" / "codered" / "rdr_sphost_ai_guest_profile_v16.json"

HOST_DEFAULT = "http://127.0.0.1:36000"
ENDPOINTS = (
    "/codered/ai_guest",
    "/ai_guest",
    "/api/codered/ai_guest",
    "/state/ai_guest",
)

ALLOWED_COMMANDS = {
    "follow": "Follow player and maintain bodyguard spacing.",
    "guard": "Guard current position / stay nearby.",
    "attack": "Attack hostile targets if a game bridge can consume it.",
    "idle": "Hold fire and wait.",
    "regroup": "Request a reattach/warp/regroup near player.",
    "defend": "Defend player from hostile targets.",
}

DEFAULT_PROFILE: Dict[str, Any] = {
    "schema": "codered.ai_guest.profile.v16",
    "name": "CodeRED_AI_01",
    "display_name": "CodeRED AI Guest",
    "guest_type": "script_controlled_ai",
    "mode": "sp-host",
    "behavior": "follow_defend",
    "target": "local_player",
    "spawn": {
        "requested": True,
        "method_priority": [
            "sphost_game_bridge",
            "private_host_state",
            "input_driven_second_client_future"
        ],
        "in_world_body_required_for_complete": False
    },
    "follow": {
        "follow_distance_m": 8.0,
        "regroup_distance_m": 45.0,
        "warp_distance_m": 80.0,
        "respawn_delay_sec": 10
    },
    "combat": {
        "defend_player": True,
        "attack_hostiles": True,
        "avoid_friendly_fire": True,
        "hold_fire_when_idle": True
    },
    "session": {
        "fake_xuid": "0xC0DE000000000101",
        "fake_machine_id": "0xC0DEF00D00000101",
        "session_role": "ai_guest"
    }
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


def load_profile() -> Dict[str, Any]:
    ensure_dirs()
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text(json.dumps(DEFAULT_PROFILE, indent=2), encoding="utf-8")
        return dict(DEFAULT_PROFILE)
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"Profile parse failed; using defaults: {exc}")
        return dict(DEFAULT_PROFILE)


def load_state() -> Dict[str, Any]:
    ensure_dirs()
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            log(f"State parse failed; rebuilding state: {exc}")
    profile = load_profile()
    return {
        "schema": "codered.ai_guest.state.v16",
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
        "host": {
            "base_url": HOST_DEFAULT,
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
    ensure_dirs()
    state["updated_at"] = now_stamp()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def append_command(event: Dict[str, Any]) -> None:
    ensure_dirs()
    with COMMANDS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def post_to_host(state: Dict[str, Any], action: str, host: str, timeout: float, no_post: bool) -> Tuple[str, List[str]]:
    if no_post:
        return "disabled", []
    payload = json.dumps({"action": action, "state": state}).encode("utf-8")
    errors: List[str] = []
    base = host.rstrip("/")
    for endpoint in ENDPOINTS:
        url = base + endpoint
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "CodeRED-AI-Guest-v16"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(256).decode("utf-8", errors="replace")
                return f"ok {resp.status} {endpoint} {body[:80]}", errors
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    return "no_compatible_endpoint", errors


def update_host_status(state: Dict[str, Any], post_status: str, errors: List[str]) -> None:
    host = state.setdefault("host", {})
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
        state["desired_game_bridge"] = {
            "spawn_actor": True,
            "attach_to": state["target"],
            "behavior": state["behavior"],
            "note": "A later game/RDR bridge should consume this state and create/control a visible body.",
        }
    elif action == "dismiss":
        state["active"] = False
        state["joined"] = False
        state["spawn_requested"] = False
        state["desired_game_bridge"] = {
            "despawn_actor": True,
            "note": "Dismiss requested by AI Guest menu.",
        }
    elif action.startswith("command:"):
        command = action.split(":", 1)[1]
        state["active"] = True
        state["joined"] = True
        state["behavior"] = command
        state["desired_game_bridge"] = {
            "command": command,
            "description": ALLOWED_COMMANDS.get(command, "Custom command"),
            "target": state.get("target", "local_player"),
        }
    elif action == "status":
        pass
    else:
        state["desired_game_bridge"] = {"command": action}

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
    print("\nCodeRED AI Guest v16 Status")
    print("-" * 40)
    for key in ["active", "joined", "spawn_requested", "visible_body_confirmed", "name", "behavior", "target", "last_command", "updated_at"]:
        print(f"{key:24}: {state.get(key)}")
    host = state.get("host", {})
    print(f"{'host':24}: {host.get('base_url', HOST_DEFAULT)}")
    print(f"{'host post':24}: {host.get('last_post_status')}")
    print(f"{'state path':24}: {STATE_PATH}")
    print(f"{'commands path':24}: {COMMANDS_PATH}")
    print(f"{'log path':24}: {LOG_PATH}")
    print()


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeRED SPHost AI Guest Controller v16")
    parser.add_argument("--host", default=HOST_DEFAULT, help="Local bootstrap host base URL. Default: http://127.0.0.1:36000")
    parser.add_argument("--timeout", type=float, default=0.45, help="Short POST timeout in seconds.")
    parser.add_argument("--no-post", action="store_true", help="Only write local state; do not POST to BootstrapHost.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    spawn = sub.add_parser("spawn", help="Spawn/register the AI guest state.")
    spawn.add_argument("--behavior", default="follow_defend")
    spawn.add_argument("--target", default="local_player")

    cmd = sub.add_parser("command", help="Send a behavior command to the AI guest.")
    cmd.add_argument("command", choices=sorted(ALLOWED_COMMANDS.keys()))

    sub.add_parser("dismiss", help="Dismiss/despawn the AI guest state.")
    sub.add_parser("status", help="Print current AI guest status.")
    sub.add_parser("init", help="Create default profile/state files only.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    ensure_dirs()
    state = load_state()
    state.setdefault("host", {})["base_url"] = args.host

    if args.cmd == "init":
        save_state(state)
        log("Initialized AI guest profile/state files.")
        print_status(state)
        return 0

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
    else:
        raise AssertionError(args.cmd)

    post_status, errors = post_to_host(state, state["last_command"], args.host, args.timeout, args.no_post)
    update_host_status(state, post_status, errors)
    save_state(state)
    log(f"AI guest action={state['last_command']} active={state.get('active')} behavior={state.get('behavior')} post={post_status}")
    if errors and post_status == "no_compatible_endpoint":
        log("BootstrapHost did not expose an AI endpoint yet; local state was still written for the next bridge pass.")
    print_status(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
