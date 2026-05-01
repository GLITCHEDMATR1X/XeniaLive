#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_RDR = Path(r"D:\Games\Red Dead Redemption")
CONFIG_NAMES = [
    "xenia-canary-config.toml",
    "xenia-canary.config.toml",
    "xenia.config.toml",
]


def normalize_path(value: str | os.PathLike[str]) -> Path:
    text = str(value).strip().strip('"')
    # Handles the PowerShell/cmd trailing-backslash quote issue from v2.
    while text.endswith('"'):
        text = text[:-1]
    return Path(text).resolve()


def log(root: Path, msg: str) -> None:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    line = f"[{_dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with (log_dir / "codered_easy_rdr_netplay.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def toml_string(value: str) -> str:
    # TOML basic string escaping.
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        key = str(p.resolve()).lower() if p.exists() else str(p).lower()
        if key not in seen:
            out.append(p)
            seen.add(key)
    return out


def find_xenia(root: Path) -> Path | None:
    candidates = [
        root / "xenia_canary.exe",
        root / "build/bin/Windows/Release/xenia_canary.exe",
        root / "build/bin/Windows/Debug/xenia_canary.exe",
        root / "build/bin/Release/xenia_canary.exe",
        root / "build/bin/Debug/xenia_canary.exe",
        root / "bin/Windows/Release/xenia_canary.exe",
        root / "bin/Release/xenia_canary.exe",
        root / "bin/xenia_canary.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for base in (root / "build", root / "bin", root):
        if base.exists():
            found = list(base.rglob("xenia_canary.exe"))
            if found:
                found.sort(key=lambda p: ("release" not in str(p).lower(), len(str(p))))
                return found[0]
    return None


def find_rdr(path: Path) -> Path | None:
    if (path / "default.xex").exists():
        return path / "default.xex"
    if not path.exists():
        return None
    found = list(path.rglob("default.xex"))
    if found:
        found.sort(key=lambda p: ("xenia" in str(p).lower(), len(str(p))))
        return found[0]
    # Xenia can also open some image/container forms, but default.xex is preferred.
    images = list(path.rglob("*.iso")) + list(path.rglob("*.xcp"))
    if images:
        images.sort(key=lambda p: len(str(p)))
        return images[0]
    return None


def strip_section(lines: list[str], name: str) -> list[str]:
    out: list[str] = []
    i = 0
    wanted = f"[{name.lower()}]"
    while i < len(lines):
        current = lines[i].strip().lower()
        if current == wanted:
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("[") and s.endswith("]"):
                    break
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def upsert_section_values(lines: list[str], section: str, values: dict[str, str]) -> list[str]:
    header = f"[{section}]"
    header_lower = header.lower()
    out = list(lines)
    start = None
    end = len(out)
    for i, line in enumerate(out):
        if line.strip().lower() == header_lower:
            start = i
            for j in range(i + 1, len(out)):
                stripped = out[j].strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    end = j
                    break
            break

    if start is None:
        if out and out[-1].strip():
            out.append("")
        out.append(header)
        start = len(out) - 1
        end = len(out)

    seen: set[str] = set()
    for i in range(start + 1, end):
        stripped = out[i].strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in values:
            comment = ""
            if "#" in out[i]:
                comment = " " + out[i].split("#", 1)[1].rstrip()
                comment = " #" + comment.lstrip()
            out[i] = f"{key} = {values[key]}{comment}"
            seen.add(key)

    insert_at = end
    for key, value in values.items():
        if key not in seen:
            out.insert(insert_at, f"{key} = {value}")
            insert_at += 1
    return out


def upsert_netplay(text: str, api: str, iface: str, mode: int, timeout_ms: int, rdr: Path) -> str:
    lines = text.splitlines()
    lines = strip_section(lines, "Netplay")
    lines = strip_section(lines, "CodeRED")
    lines = upsert_section_values(lines, "CPU", {
        "break_on_debugbreak": "false",
        "break_on_unimplemented_instructions": "false",
    })
    lines = upsert_section_values(lines, "x64", {
        "enable_host_guest_stack_synchronization": "false",
        "x64_extension_mask": "127",
    })
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        lines.append("")
    lines.extend([
        "[Netplay]",
        f"network_mode = {mode}",
        f"netplay_api_address = {toml_string(api)}",
        f"selected_network_interface = {toml_string(iface)}",
        "upnp = true",
        "xhttp = true",
        "net_logging = true",
        f"netplay_http_timeout_ms = {timeout_ms}",
        "",
        "[CodeRED]",
        f"rdr_path = {toml_string(str(rdr))}",
        "",
    ])
    return "\n".join(lines)


def config_dirs(root: Path) -> list[Path]:
    exe = find_xenia(root)
    dirs = [root]
    if exe:
        dirs.insert(0, exe.parent)
    return unique_paths(dirs)


def configure(root: Path, rdr: Path, api: str, iface: str, mode: int, timeout_ms: int) -> None:
    for d in config_dirs(root):
        d.mkdir(parents=True, exist_ok=True)
        for name in CONFIG_NAMES:
            p = d / name
            old = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
            p.write_text(upsert_netplay(old, api, iface, mode, timeout_ms, rdr), encoding="utf-8")
            log(root, f"Wrote config: {p}")


def check_host() -> str:
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:36000/health", timeout=2) as res:
            return res.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"PRIVATE_HOST_NOT_RESPONDING: {exc}"


def check(root: Path, rdr: Path) -> int:
    exe = find_xenia(root)
    target = find_rdr(rdr)
    log(root, f"Root: {root}")
    log(root, f"Xenia exe: {exe or 'NOT FOUND - build first'}")
    log(root, f"RDR folder: {rdr}")
    log(root, f"RDR target: {target or 'NOT FOUND'}")
    log(root, f"Private host health: {check_host()}")
    return 0 if exe and target else 2


def write_report(root: Path, rdr: Path) -> Path:
    report = root / "logs" / "codered_rdr_netplay_diagnose.txt"
    root.joinpath("logs").mkdir(parents=True, exist_ok=True)
    exe = find_xenia(root)
    target = find_rdr(rdr)
    lines = [
        "CodeRED RDR Netplay Diagnose v3",
        f"Time: {_dt.datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Root: {root}",
        f"Xenia exe: {exe or 'NOT FOUND'}",
        f"RDR folder: {rdr}",
        f"RDR target: {target or 'NOT FOUND'}",
        f"Private host health: {check_host()}",
        "",
        "Config files:",
    ]
    for d in config_dirs(root):
        for name in CONFIG_NAMES:
            p = d / name
            if p.exists():
                lines.append(f"--- {p}")
                lines.append(p.read_text(encoding="utf-8", errors="replace"))
    report.write_text("\n".join(lines), encoding="utf-8")
    log(root, f"Wrote diagnose report: {report}")
    return report


def launch(root: Path, rdr: Path, api: str, iface: str, mode: int, timeout_ms: int) -> int:
    configure(root, rdr, api, iface, mode, timeout_ms)
    exe = find_xenia(root)
    target = find_rdr(rdr)
    if not exe:
        log(root, "xenia_canary.exe not found. Run CodeRED_Build_Xenia_Release_v3.bat first.")
        return 2
    if not target:
        log(root, f"RDR target not found under {rdr}. Expected default.xex or a supported game image.")
        return 3
    log(root, f"Launching Xenia: {exe}")
    log(root, f"Launching RDR: {target}")
    subprocess.Popen([str(exe), str(target)], cwd=str(exe.parent))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeRED RDR/Xenia easy netplay helper v3")
    parser.add_argument("action", choices=["check", "configure", "diagnose", "launch"])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--rdr-path", default=str(DEFAULT_RDR))
    parser.add_argument("--api-address", default="http://127.0.0.1:36000/")
    parser.add_argument("--interface", default="127.0.0.1")
    parser.add_argument("--mode", type=int, default=2)
    parser.add_argument("--timeout-ms", type=int, default=1500)
    ns = parser.parse_args()

    root = normalize_path(ns.root)
    rdr = normalize_path(ns.rdr_path)

    if ns.action == "check":
        return check(root, rdr)
    if ns.action == "configure":
        configure(root, rdr, ns.api_address, ns.interface, ns.mode, ns.timeout_ms)
        return check(root, rdr)
    if ns.action == "diagnose":
        write_report(root, rdr)
        return check(root, rdr)
    return launch(root, rdr, ns.api_address, ns.interface, ns.mode, ns.timeout_ms)


if __name__ == "__main__":
    raise SystemExit(main())
