#!/usr/bin/env python3
r"""CodeRED RDR multiplayer bootstrap guard v9.

Focus:
- Disc 1 is the default GOTY launch target.
- Disc 2 remains available as a multiplayer/Undead fallback.
- Every launch stamps the active mode in configs and logs so LAN/private tests do
  not get mixed.
- Config writes preserve normal Xenia settings and only update targeted sections.
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

CONFIG_NAMES = ["xenia-canary.config.toml", "xenia-canary-config.toml", "xenia.config.toml"]
DEFAULT_RDR = pathlib.Path(__file__).resolve().parents[1]
SEARCH_SKIP_DIRS = {
    ".git",
    "build",
    "cache",
    "logs",
    "third_party",
}
UNSAFE_TARGET_TOKENS = {
    "$systemupdate",
    "$titleupdate",
    "fffe07df",
    "su20076000_00000000",
    "system.manifest",
}


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def root_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def logs_dir(root: pathlib.Path) -> pathlib.Path:
    p = root / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def log(root: pathlib.Path, msg: str) -> None:
    line = f"[{stamp()}] {msg}"
    print(line)
    with (logs_dir(root) / "codered_rdr_bootstrap_guard_v9.log").open("a", encoding="utf-8") as f:
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


def score_target(path: pathlib.Path, disc: str) -> tuple[int, int, str]:
    name = path.name.lower()
    whole = str(path).lower()
    score = 1000
    if disc == "disc1":
        if "disc 1" in name or "disc1" in name:
            score -= 500
        if "game of the year" in name:
            score -= 80
        if "undead" in name or "multiplayer" in name or "disc 2" in name:
            score += 300
        if path.suffix.lower() == ".iso":
            score -= 60
    elif disc == "disc2":
        if "disc 2" in name or "disc2" in name:
            score -= 500
        if "undead" in name:
            score -= 100
        if "multiplayer" in name:
            score -= 100
        if path.suffix.lower() == ".iso":
            score -= 60
    elif disc == "xex":
        if name == "default.xex":
            score -= 600
        elif path.suffix.lower() == ".xex":
            score -= 300
    else:
        # Auto now favors Disc 1 first because GOTY's base game should own the
        # common world/content path. Disc 2 remains one menu option away.
        if "disc 1" in name or "disc1" in name:
            score -= 500
        elif "disc 2" in name or "disc2" in name:
            score -= 350
        elif name == "default.xex":
            score -= 250
    if "red dead" in whole:
        score -= 40
    return (score, len(str(path)), str(path))


def is_safe_launch_target(path: pathlib.Path) -> bool:
    lower = str(path).lower()
    if any(token in lower for token in UNSAFE_TARGET_TOKENS):
        return False
    if path.name.lower() == "default.xex":
        parent = str(path.parent).lower()
        if any(token in parent for token in ("system", "update", "dashboard", "fffe07df")):
            return False
    return True


def find_rdr_target(root: pathlib.Path, rdr: pathlib.Path, disc: str) -> pathlib.Path | None:
    roots: list[pathlib.Path] = []
    for p in (rdr, root):
        if p.exists() and p not in roots:
            roots.append(p)
    patterns = {
        "disc1": ["*Disc 1*.iso", "*Disc1*.iso", "*Game of the Year*.iso", "*Red Dead*.iso", "*.iso"],
        "disc2": ["*Disc 2*.iso", "*Disc2*.iso", "*Undead*Multiplayer*.iso", "*Multiplayer*.iso", "*.iso"],
        "xex": ["default.xex", "*.xex"],
        "auto": ["*Disc 1*.iso", "*Disc1*.iso", "*Disc 2*.iso", "*Disc2*.iso", "default.xex", "*.xex", "*.iso"],
    }
    matches: list[pathlib.Path] = []
    for base in roots:
        for pattern in patterns.get(disc, patterns["auto"]):
            matches.extend(safe_rglob(base, pattern))
    uniq = sorted(set(matches), key=lambda p: score_target(p, disc))
    return uniq[0] if uniq else None


def safe_rglob(base: pathlib.Path, pattern: str) -> list[pathlib.Path]:
    """Recursive glob that avoids generated/build/log folders during target search."""
    if base.is_file():
        return [base] if base.match(pattern) else []
    matches: list[pathlib.Path] = []
    for current, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d.lower() not in SEARCH_SKIP_DIRS]
        current_path = pathlib.Path(current)
        for filename in filenames:
            path = current_path / filename
            if path.match(pattern) and is_safe_launch_target(path):
                matches.append(path)
    return matches


def split_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {"__root__": []}
    order = ["__root__"]
    current = "__root__"
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


def fmt_value(key: str, value: object) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, int):
        return f"{key} = {value}"
    text = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'{key} = "{text}"'


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
                    out.append(fmt_value(key, values[key]))
                    seen.add(key)
                    continue
            out.append(line)
        for key, value in values.items():
            if key not in seen:
                out.append(fmt_value(key, value))
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


def short_path(path: pathlib.Path) -> str:
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
    iface = args.interface or local_ipv4_guess()
    xhttp = args.mode == "private"
    log_file = logs_dir(root) / f"xenia_codered_v9_{args.mode}_{args.disc}_{args.variant}.log"
    updates = {
        "CPU": {
            "break_on_debugbreak": False,
            "break_on_unimplemented_instructions": False,
            "disable_context_promotion": True,
            "enable_early_precompilation": False,
            "ignore_undefined_externs": True,
            "validate_hir": False,
        },
        "x64": {"x64_extension_mask": args.x64_mask, "enable_host_guest_stack_synchronization": True},
        "General": {"discord": False, "apply_patches": args.variant != "bare", "allow_plugins": False},
        "Kernel": {"apply_title_update": args.variant != "bare", "allow_incompatible_title_update": True, "ignore_thread_affinities": True},
        "Logging": {"enable_console": True, "flush_log": True, "log_file": str(log_file), "log_level": 3, "log_mask": 0, "log_to_stdout": True},
        "Netplay": {
            "network_mode": mode_id,
            "netplay_api_address": f"http://{args.host}:{args.port}/",
            "selected_network_interface": iface,
            "upnp": True,
            "xhttp": xhttp,
            "net_logging": True,
            "netplay_udp_bootstrap": True,
            "netplay_http_timeout_ms": args.timeout_ms,
        },
        "CodeRED": {
            "rdr_path": str(args.rdr),
            "rdr_target": str(target or ""),
            "bootstrap_guard_version": "v9",
            "bootstrap_mode": args.mode,
            "bootstrap_disc": args.disc,
            "bootstrap_variant": args.variant,
            "selected_network_interface": iface,
            "disc_note": "Disc 1 is default. Use Disc 2 fallback when GOTY multiplayer/Undead content is required.",
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
                backup = path.with_suffix(path.suffix + f".codered_v9_bak_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
                try:
                    shutil.copy2(path, backup)
                except OSError:
                    pass
            path.write_text(update_toml(original, updates), encoding="utf-8")
            log(root, f"Wrote v9 config: {path}")
    marker = logs_dir(root) / "CODERED_ACTIVE_NETPLAY_MODE.txt"
    marker.write_text(
        f"time={stamp()}\nmode={args.mode}\nnetwork_mode={mode_id}\ndisc={args.disc}\ntarget={target}\ninterface={iface}\nxhttp={xhttp}\n",
        encoding="utf-8",
    )
    return log_file


def host_health(host: str, port: int) -> str:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1.5) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        return f"NOT_READY: {e}"


def cmd_configure(args: argparse.Namespace) -> int:
    root = root_dir()
    exe = find_exe(root)
    if not exe:
        log(root, "xenia_canary.exe was not found. Build first.")
        return 2
    target = find_rdr_target(root, args.rdr, args.disc)
    if not target:
        log(root, f"No RDR target found for disc={args.disc} under {args.rdr} or {root}")
        return 3
    log_file = write_configs(root, exe, args, target)
    if args.mode == "private":
        log(root, f"Private/bootstrap host health: {host_health(args.host, args.port)}")
    log(root, f"Configured mode={args.mode} disc={args.disc} target={target} without launching. Log file: {log_file}")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    root = root_dir()
    exe = find_exe(root)
    if not exe:
        log(root, "xenia_canary.exe was not found. Build first.")
        return 2
    target = find_rdr_target(root, args.rdr, args.disc)
    if not target:
        log(root, f"No RDR target found for disc={args.disc} under {args.rdr} or {root}")
        return 3
    log_file = write_configs(root, exe, args, target)
    if args.mode == "private":
        log(root, f"Private/bootstrap host health: {host_health(args.host, args.port)}")
    log(root, f"Launch mode={args.mode} disc={args.disc} target={target}")
    cmd = [short_path(exe), short_path(target)]
    log(root, "Command: " + " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=str(exe.parent))
    if args.wait:
        code = proc.wait()
        log(root, f"Xenia exited with code {code}. Log file: {log_file}")
        return int(code or 0)
    log(root, f"Xenia launched. Log file: {log_file}")
    return 0


def cmd_profile_check(args: argparse.Namespace) -> int:
    root = root_dir()
    exe = find_exe(root)
    dirs = [root]
    if exe:
        dirs.append(exe.parent)
    report = [f"CodeRED profile/sign-in check v9", f"time={stamp()}"]
    for d in dirs:
        report.append(f"\nDirectory: {d}")
        for name in CONFIG_NAMES:
            cfg = d / name
            if cfg.exists():
                text = cfg.read_text(encoding="utf-8", errors="ignore")
                profile_lines = [line for line in text.splitlines() if "logged_profile_slot" in line]
                report.append(f"  {name}: present")
                for line in profile_lines[:8]:
                    report.append(f"    {line}")
            else:
                report.append(f"  {name}: missing")
    profile_hits = []
    for pattern in ("*profile*", "*.gpd", "*.xuid"):
        profile_hits.extend(root.rglob(pattern))
    report.append(f"\nProfile-like files found: {len(profile_hits)}")
    for p in sorted(set(profile_hits))[:80]:
        report.append(f"  {p}")
    out = logs_dir(root) / "codered_profile_check_v9.txt"
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8", errors="replace"))
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    root = root_dir()
    send = logs_dir(root) / "CODERED_SEND_THESE_V9"
    if send.exists():
        shutil.rmtree(send, ignore_errors=True)
    send.mkdir(parents=True, exist_ok=True)
    patterns = ["*.log", "*.txt", "*.toml", "*.json"]
    copied = 0
    for base in [root, logs_dir(root), root / "build" / "bin" / "Windows" / "Release"]:
        if not base.exists():
            continue
        for pat in patterns:
            for src in base.glob(pat):
                if src.is_file() and src.stat().st_size < 8 * 1024 * 1024:
                    dst = send / f"{base.name}_{src.name}"
                    try:
                        shutil.copy2(src, dst)
                        copied += 1
                    except OSError:
                        pass
    zip_path = logs_dir(root) / f"codered_rdr_small_logs_v9_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for src in send.rglob("*"):
            if src.is_file():
                z.write(src, src.relative_to(send))
    log(root, f"Collected {copied} files: {zip_path}")
    print(zip_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    launch = sub.add_parser("launch")
    launch.add_argument("--mode", choices=["private", "lan", "offline"], default="private")
    launch.add_argument("--disc", choices=["disc1", "disc2", "xex", "auto"], default="disc1")
    launch.add_argument("--variant", choices=["safe", "bare"], default="safe")
    launch.add_argument("--rdr", type=pathlib.Path, default=DEFAULT_RDR)
    launch.add_argument("--interface", default="")
    launch.add_argument("--host", default="127.0.0.1")
    launch.add_argument("--port", type=int, default=36000)
    launch.add_argument("--timeout-ms", type=int, default=4000)
    launch.add_argument("--x64-mask", type=int, default=0)
    launch.add_argument("--wait", action="store_true")
    launch.set_defaults(func=cmd_launch)
    configure = sub.add_parser("configure")
    configure.add_argument("--mode", choices=["private", "lan", "offline"], default="private")
    configure.add_argument("--disc", choices=["disc1", "disc2", "xex", "auto"], default="disc1")
    configure.add_argument("--variant", choices=["safe", "bare"], default="safe")
    configure.add_argument("--rdr", type=pathlib.Path, default=DEFAULT_RDR)
    configure.add_argument("--interface", default="")
    configure.add_argument("--host", default="127.0.0.1")
    configure.add_argument("--port", type=int, default=36000)
    configure.add_argument("--timeout-ms", type=int, default=4000)
    configure.add_argument("--x64-mask", type=int, default=0)
    configure.set_defaults(func=cmd_configure)
    prof = sub.add_parser("profile-check")
    prof.set_defaults(func=cmd_profile_check)
    collect = sub.add_parser("collect")
    collect.set_defaults(func=cmd_collect)
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
