#!/usr/bin/env python3
"""CodeRED Xenia RDR Multiplayer Relaunch Guard v7.

v7 builds on v7 and adds a title-relaunch loop.
When RDR calls XamLoaderLaunchTitle to jump into multiplayer/launch data, the patched source exits cleanly and this launcher restarts Xenia automatically.
"""
from __future__ import annotations

import argparse
import datetime as dt
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
DEFAULT_RDR = pathlib.Path(r"D:\Games\Red Dead Redemption")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def root_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def log(root: pathlib.Path, msg: str) -> None:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    line = f"[{stamp()}] {msg}"
    print(line)
    with (logs / "codered_rdr_crash_guard_v7.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_exe(root: pathlib.Path) -> pathlib.Path | None:
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


def _score_target(path: pathlib.Path, disc: str) -> tuple[int, int, str]:
    name = path.name.lower()
    s = 100
    if disc == "disc2":
        if "disc 2" in name:
            s -= 70
        if "multiplayer" in name:
            s -= 30
        if "undead" in name:
            s -= 5
    elif disc == "disc1":
        if "disc 1" in name:
            s -= 80
        if "game of the year" in name:
            s -= 5
    elif disc == "xex":
        if name == "default.xex":
            s -= 100
        elif path.suffix.lower() == ".xex":
            s -= 60
    else:
        if "disc 2" in name and "multiplayer" in name:
            s -= 90
        elif "disc 1" in name:
            s -= 60
        elif name == "default.xex":
            s -= 50
    return (s, len(str(path)), str(path))


def find_rdr_target(root: pathlib.Path, rdr: pathlib.Path, disc: str) -> pathlib.Path | None:
    roots: list[pathlib.Path] = []
    for p in (rdr, root):
        if p.exists() and p not in roots:
            roots.append(p)
    patterns_by_disc = {
        "disc2": ["*Disc 2*Multiplayer*.iso", "*Disc 2*.iso", "*Undead*Multiplayer*.iso", "*.iso"],
        "disc1": ["*Disc 1*.iso", "*Game of the Year*Disc 1*.iso", "*.iso"],
        "xex": ["default.xex", "*.xex"],
        "auto": ["*Disc 2*Multiplayer*.iso", "*Disc 2*.iso", "*Disc 1*.iso", "default.xex", "*.xex", "*Red Dead*.iso", "*.iso"],
    }
    matches: list[pathlib.Path] = []
    for base in roots:
        for pattern in patterns_by_disc.get(disc, patterns_by_disc["auto"]):
            matches.extend(base.rglob(pattern))
    uniq = sorted(set(matches), key=lambda p: _score_target(p, disc))
    return uniq[0] if uniq else None


def split_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {"__root__": []}
    order = ["__root__"]
    current = "__root__"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]") and len(s) > 2:
            current = s[1:-1]
            if current not in sections:
                sections[current] = []
                order.append(current)
            sections[current].append(line)
        else:
            sections.setdefault(current, []).append(line)
    return sections, order


def fmt(key: str, value: object) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, int):
        return f"{key} = {value}"
    if isinstance(value, float):
        return f"{key} = {value}"
    return f'{key} = "{str(value).replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"'


def update_toml(text: str, updates: dict[str, dict[str, object]]) -> str:
    sections, order = split_sections(text)
    for section, values in updates.items():
        if section not in sections:
            sections[section] = [f"[{section}]"]
            order.append(section)
        seen: set[str] = set()
        out: list[str] = []
        for line in sections[section]:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in values:
                    out.append(fmt(key, values[key]))
                    seen.add(key)
                    continue
            out.append(line)
        for key, value in values.items():
            if key not in seen:
                out.append(fmt(key, value))
        sections[section] = out
    lines: list[str] = []
    for section in order:
        block = sections.get(section, [])
        if not block:
            continue
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
    return "\n".join(lines).rstrip() + "\n"


def local_ipv4_guess() -> str:
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


def windows_short_path(path: pathlib.Path) -> str:
    text = str(path)
    if os.name != "nt":
        return text
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetShortPathNameW(text, buf, len(buf))
        if n and n < len(buf):
            return buf.value
    except Exception:
        pass
    return text


def write_configs(root: pathlib.Path, exe: pathlib.Path | None, args: argparse.Namespace, target: pathlib.Path | None) -> pathlib.Path:
    mode_id = {"offline": 0, "lan": 1, "private": 2}[args.mode]
    log_path = root / "logs" / f"xenia_codered_v7_{args.mode}_{args.disc}_{args.variant}.log"
    selected_iface = args.interface or local_ipv4_guess()
    apply_patches = args.variant not in {"nopatches", "bare"}
    apply_title_update = args.variant not in {"notu", "bare"}
    updates = {
        "CPU": {
            "break_on_debugbreak": False,
            "break_on_unimplemented_instructions": False,
            "disable_context_promotion": True,
            "enable_early_precompilation": False,
            "ignore_undefined_externs": True,
            "validate_hir": False,
        },
        "x64": {
            "x64_extension_mask": args.x64_mask,
            "enable_host_guest_stack_synchronization": True,
            "delay_via_maybeyield": False,
        },
        "General": {"discord": False, "apply_patches": apply_patches, "allow_plugins": False},
        "Kernel": {"apply_title_update": apply_title_update, "allow_incompatible_title_update": True, "ignore_thread_affinities": True},
        "Logging": {"enable_console": True, "flush_log": True, "log_file": str(log_path), "log_level": 3, "log_mask": 0, "log_to_stdout": True},
        "Netplay": {
            "network_mode": mode_id,
            "netplay_api_address": f"http://{args.host}:{args.port}/",
            "selected_network_interface": selected_iface,
            "upnp": True,
            "xhttp": args.mode == "private",
            "net_logging": True,
            "netplay_http_timeout_ms": 4000,
        },
        "CodeRED": {
            "rdr_path": str(args.rdr),
            "rdr_target": str(target or ""),
            "crash_guard_version": "v7",
            "crash_guard_mode": args.mode,
            "crash_guard_disc": args.disc,
            "crash_guard_variant": args.variant,
            "selected_network_interface_note": "v7 defaults XNADDR to real local IPv4, not 127.0.0.1, unless --interface is provided",
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
                bak = path.with_suffix(path.suffix + f".codered_v7_bak_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
                try:
                    shutil.copy2(path, bak)
                except OSError:
                    pass
            path.write_text(update_toml(original, updates), encoding="utf-8")
            log(root, f"Wrote v7 config: {path}")
    return log_path


def health(host: str, port: int, timeout: float = 1.0) -> str:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"PRIVATE_HOST_NOT_RESPONDING: {e}"


def start_private_host(root: pathlib.Path, host: str, port: int) -> bool:
    current = health(host, port, 0.75)
    if "codered-rdr-private-host" in current or '"ok"' in current:
        log(root, f"Private host already healthy: {current}")
        return True
    script = root / "tools" / "codered_rdr_private_host.py"
    if not script.exists():
        log(root, f"ERROR: private host script missing: {script}")
        return False
    cmd = [sys.executable, str(script), "--host", host, "--port", str(port), "--verbose"]
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    log(root, "Starting private host: " + " ".join(cmd))
    subprocess.Popen(cmd, cwd=str(root), creationflags=flags)
    deadline = time.time() + 12.0
    last = ""
    while time.time() < deadline:
        time.sleep(0.75)
        last = health(host, port, 1.0)
        if "codered-rdr-private-host" in last or '"ok"' in last:
            log(root, f"Private host healthy: {last}")
            return True
    log(root, f"ERROR: private host did not become healthy: {last}")
    return False


def _launch_data_paths(root: pathlib.Path, exe: pathlib.Path) -> list[pathlib.Path]:
    return [exe.parent / "launch_data.bin", root / "launch_data.bin"]


def _has_launch_data(root: pathlib.Path, exe: pathlib.Path) -> bool:
    return any(p.exists() for p in _launch_data_paths(root, exe))


def launch(args: argparse.Namespace) -> int:
    root = pathlib.Path(args.root).resolve()
    rdr = pathlib.Path(args.rdr).resolve()
    exe = find_exe(root)
    if not exe:
        log(root, "ERROR: xenia_canary.exe was not found. Build first.")
        return 2
    target = find_rdr_target(root, rdr, args.disc)
    if not target:
        log(root, f"ERROR: RDR target not found. Root={root} RDR={rdr} Disc={args.disc}")
        return 3
    log_path = write_configs(root, exe, args, target)
    if args.mode == "private" and not start_private_host(root, args.host, args.port):
        log(root, "ERROR: stopped before launch because private host is not healthy.")
        return 4
    exe_arg = windows_short_path(exe)
    log_arg = windows_short_path(log_path)
    target_arg = windows_short_path(target)
    base_cmd = [exe_arg, f"--log_file={log_arg}", "--log_level=3", target_arg]
    log(root, "Launching Xenia: " + str(exe))
    log(root, "Launching RDR target: " + str(target))
    log(root, "Launching RDR target arg: " + target_arg)
    log(root, "Xenia log target: " + str(log_path))

    max_runs = max(1, args.relaunches + 1)
    run_index = 0
    while run_index < max_runs:
        run_index += 1
        cmd = base_cmd if run_index == 1 else [exe_arg, f"--log_file={log_arg}", "--log_level=3"]
        log(root, f"Starting Xenia run {run_index}/{max_runs}: " + " ".join(cmd))
        proc = subprocess.Popen(cmd, cwd=str(exe.parent))
        if not args.wait:
            return 0
        code = proc.wait()
        log(root, f"Xenia run {run_index} exited with code {code}")
        if run_index < max_runs and _has_launch_data(root, exe):
            log(root, "launch_data.bin detected after title restart; relaunching Xenia automatically.")
            time.sleep(1.0)
            continue
        break
    return 0


def collect(root: pathlib.Path) -> pathlib.Path:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    send_dir = logs / "CODERED_SEND_THESE_V7"
    if send_dir.exists():
        shutil.rmtree(send_dir, ignore_errors=True)
    send_dir.mkdir(parents=True, exist_ok=True)
    wanted = {".log", ".txt", ".toml", ".json"}
    bases = [root, logs, logs / "xenia_crash_dumps"]
    copied = 0
    for base in bases:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part.upper().startswith("CODERED_SEND_THESE") for part in p.parts):
                continue
            if p.suffix.lower() == ".dmp":
                continue
            if p.suffix.lower() not in wanted and "stack" not in p.name.lower():
                continue
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = pathlib.Path(p.name)
            dest = send_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(p, dest)
                copied += 1
            except OSError:
                pass
    summary = send_dir / "README_SEND_THIS_FOLDER.txt"
    summary.write_text(
        "Upload this folder or the ZIP next to it. Crash .dmp files are intentionally excluded. Previous CODERED_SEND_THESE folders are skipped.\n"
        f"Created: {stamp()}\nFiles copied: {copied}\n",
        encoding="utf-8",
    )
    out = logs / f"codered_rdr_small_logs_v7_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in send_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(send_dir.parent))
    try:
        with zipfile.ZipFile(out, "r") as z:
            bad = z.testzip()
        if bad:
            log(root, f"WARNING: zip validation reported first bad file: {bad}")
        else:
            log(root, f"Validated small logs zip: {out}")
    except Exception as e:
        log(root, f"WARNING: zip validation failed: {e}; send folder instead: {send_dir}")
    print(out)
    print(send_dir)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["launch", "collect", "host", "config"])
    ap.add_argument("--root", default=str(root_dir()))
    ap.add_argument("--rdr", default=str(DEFAULT_RDR))
    ap.add_argument("--mode", choices=["private", "lan", "offline"], default="private")
    ap.add_argument("--disc", choices=["auto", "disc1", "disc2", "xex"], default="disc2")
    ap.add_argument("--variant", choices=["normal", "safe", "nopatches", "notu", "bare"], default="safe")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=36000)
    ap.add_argument("--interface", default="")
    ap.add_argument("--x64-mask", type=int, default=0)
    ap.add_argument("--wait", action="store_true", help="Wait for Xenia to exit so launch_data restarts can be detected")
    ap.add_argument("--relaunches", type=int, default=2, help="Number of automatic restarts after launch_data.bin is created")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve()
    if args.action == "collect":
        collect(root)
        return 0
    if args.action == "host":
        return 0 if start_private_host(root, args.host, args.port) else 1
    if args.action == "config":
        target = find_rdr_target(root, pathlib.Path(args.rdr).resolve(), args.disc)
        write_configs(root, find_exe(root), args, target)
        return 0
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
