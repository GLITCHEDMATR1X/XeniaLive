#!/usr/bin/env python3
"""
CodeRED Xenia RDR Multiplayer Triage v4
Small helper that does not need the full build uploaded. It writes safer configs,
starts/health-checks the private host, launches Xenia with a log file, and can
collect a small diagnostics zip without the huge crash dumps.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

CONFIG_NAMES = ["xenia-canary-config.toml", "xenia-canary.config.toml", "xenia.config.toml"]


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(root: pathlib.Path, msg: str) -> None:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    line = f"[{now()}] {msg}"
    print(line)
    with (logs / "codered_rdr_multiplayer_triage_v4.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def guess_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def find_xenia_exe(root: pathlib.Path) -> pathlib.Path | None:
    candidates = [
        root / "build" / "bin" / "Windows" / "Release" / "xenia_canary.exe",
        root / "build" / "bin" / "Windows" / "Debug" / "xenia_canary.exe",
        root / "xenia_canary.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    found = list(root.rglob("xenia_canary.exe"))
    return found[0] if found else None


def find_rdr_target(root: pathlib.Path, rdr_folder: pathlib.Path) -> pathlib.Path | None:
    # Prefer the multiplayer/GOTY disc if present, then default.xex, then any RDR ISO.
    patterns = [
        "*Disc 2*Multiplayer*.iso",
        "*Disc 2*.iso",
        "default.xex",
        "*.xex",
        "*Red Dead*.iso",
        "*.iso",
    ]
    search_roots = [rdr_folder, root]
    seen: set[pathlib.Path] = set()
    for base in search_roots:
        if not base.exists() or base in seen:
            continue
        seen.add(base)
        for pattern in patterns:
            matches = sorted(base.rglob(pattern), key=lambda p: ("Disc 2" not in p.name, len(str(p))))
            if matches:
                return matches[0]
    return None


def split_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current = "__root__"
    sections[current] = []
    order.append(current)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2:
            current = stripped[1:-1]
            if current not in sections:
                sections[current] = []
                order.append(current)
            sections[current].append(line)
        else:
            sections.setdefault(current, []).append(line)
    return sections, order


def set_section_values(text: str, updates: dict[str, dict[str, object]]) -> str:
    sections, order = split_sections(text)
    for section, values in updates.items():
        if section not in sections:
            order.append(section)
            sections[section] = [f"[{section}]"]
        lines = sections[section]
        # Preserve section header; replace key assignments, append missing.
        existing_keys: set[str] = set()
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in values:
                    new_lines.append(format_assignment(key, values[key]))
                    existing_keys.add(key)
                    continue
            new_lines.append(line)
        for key, value in values.items():
            if key not in existing_keys:
                new_lines.append(format_assignment(key, value))
        sections[section] = new_lines
    output: list[str] = []
    for section in order:
        lines = sections.get(section, [])
        if not lines:
            continue
        if output and output[-1].strip():
            output.append("")
        output.extend(lines)
    return "\n".join(output).rstrip() + "\n"


def format_assignment(key: str, value: object) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, int):
        return f"{key} = {value}"
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'{key} = "{escaped}"'


def write_configs(root: pathlib.Path, exe: pathlib.Path | None, mode: str, x64_mask: int, rdr_path: pathlib.Path, host: str, port: int) -> None:
    network_mode = {"offline": 0, "lan": 1, "private": 2}[mode]
    updates = {
        "CPU": {
            "break_on_debugbreak": False,
            "break_on_unimplemented_instructions": False,
        },
        "x64": {
            "enable_host_guest_stack_synchronization": False,
            "x64_extension_mask": x64_mask,
        },
        "Logging": {
            "log_file": str(root / "logs" / f"xenia_codered_{mode}_mask{x64_mask}.log"),
            "log_to_stdout": True,
            "flush_log": True,
            "log_level": 3,
        },
        "Netplay": {
            "network_mode": network_mode,
            "netplay_api_address": f"http://{host}:{port}/",
            "selected_network_interface": "127.0.0.1" if host in {"127.0.0.1", "localhost"} else host,
            "upnp": True,
            "xhttp": True,
            "net_logging": True,
            "netplay_http_timeout_ms": 2500,
        },
        "CodeRED": {
            "rdr_path": str(rdr_path),
            "triage_mode": mode,
            "triage_x64_extension_mask": x64_mask,
        },
    }
    dirs = [root]
    if exe:
        dirs.append(exe.parent)
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        for name in CONFIG_NAMES:
            path = d / name
            original = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
            if path.exists():
                backup = path.with_suffix(path.suffix + f".codered_bak_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
                try:
                    shutil.copy2(path, backup)
                except OSError:
                    pass
            path.write_text(set_section_values(original, updates), encoding="utf-8")
            log(root, f"Wrote triage config: {path}")


def health(host: str, port: int, timeout: float = 1.5) -> str:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"PRIVATE_HOST_NOT_RESPONDING: {e}"


def start_private_host(root: pathlib.Path, host: str, port: int) -> subprocess.Popen | None:
    current = health(host, port, 0.5)
    if "codered-rdr-private-host" in current or '"ok"' in current:
        log(root, f"Private host already healthy: {current}")
        return None
    script = root / "tools" / "codered_rdr_private_host.py"
    if not script.exists():
        log(root, f"Private host script missing: {script}")
        return None
    cmd = [sys.executable, str(script), "--host", host, "--port", str(port), "--verbose"]
    log(root, "Starting private host: " + " ".join(cmd))
    # Create a separate console on Windows; no-op elsewhere.
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    p = subprocess.Popen(cmd, cwd=str(root), creationflags=creationflags)
    time.sleep(2.0)
    log(root, f"Private host health after start: {health(host, port, 1.5)}")
    return p


def launch(root: pathlib.Path, mode: str, x64_mask: int, rdr_folder: pathlib.Path, host: str, port: int) -> int:
    exe = find_xenia_exe(root)
    if not exe:
        log(root, "ERROR: xenia_canary.exe was not found. Build first.")
        return 2
    target = find_rdr_target(root, rdr_folder)
    if not target:
        log(root, f"ERROR: RDR target was not found under {rdr_folder} or {root}.")
        return 3
    write_configs(root, exe, mode, x64_mask, rdr_folder, host, port)
    if mode == "private":
        start_private_host(root, host, port)
    log_file = root / "logs" / f"xenia_codered_{mode}_mask{x64_mask}.log"
    cmd = [str(exe), f"--log_file={log_file}", "--log_level=3", str(target)]
    log(root, "Launching Xenia: " + str(exe))
    log(root, "Launching RDR: " + str(target))
    log(root, "Xenia log target: " + str(log_file))
    subprocess.Popen(cmd, cwd=str(exe.parent))
    return 0


def collect(root: pathlib.Path) -> pathlib.Path:
    out = root / "logs" / f"codered_rdr_small_logs_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    wanted_ext = {".log", ".txt", ".toml", ".json"}
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for base in [root, root / "logs", root / "logs" / "xenia_crash_dumps"]:
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() == ".dmp":
                    continue
                if p.suffix.lower() not in wanted_ext and "stack" not in p.name.lower():
                    continue
                try:
                    z.write(p, p.relative_to(root))
                except Exception:
                    pass
    log(root, f"Collected small logs: {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["private", "lan", "offline", "collect", "config"], help="Action to run")
    ap.add_argument("--root", default=str(guess_root()))
    ap.add_argument("--rdr", default=r"D:\Games\Red Dead Redemption")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=36000)
    ap.add_argument("--x64-mask", type=int, default=0, help="Use 0 for safest CPU fallback; try 127 after logs improve")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve()
    rdr = pathlib.Path(args.rdr).resolve()
    if args.action == "collect":
        print(collect(root))
        return 0
    exe = find_xenia_exe(root)
    if args.action == "config":
        write_configs(root, exe, "private", args.x64_mask, rdr, args.host, args.port)
        return 0
    return launch(root, args.action, args.x64_mask, rdr, args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
