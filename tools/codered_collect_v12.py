#!/usr/bin/env python3
r"""Collect small CodeRED v14 logs and correlate RDR MP/network evidence."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import zipfile

MP_MARKERS = {
    "freemode": ["freemode", "freemode.csc"],
    "mp_idle": ["mp_idle", "mp_idle.csc"],
    "multiplayer_system_thread": ["multiplayer_system_thread"],
    "multiplayer_update_thread": ["multiplayer_update_thread"],
    "deathmatch": ["deathmatch", "deathmatch.csc"],
    "ctf": ["ctf_base_game", "ctf"],
}

NET_MARKERS = [
    "SinglePlayerHost advertise",
    "blocked saved-game",
    "PublishSession",
    "XNetGetTitleXnAddr",
    "UDP bootstrap injected",
    "sendto",
    "recvfrom",
    "WSARecvFrom",
    "XSessionCreate",
    "XSessionSearch",
    "XNetRegisterKey",
    "UDP inbound #",
    "WSAGetLastError: 10035",
]


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def root_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def read_text(path: pathlib.Path, limit: int = 8 * 1024 * 1024) -> str:
    try:
        if path.stat().st_size > limit:
            with path.open("rb") as f:
                f.seek(max(0, path.stat().st_size - limit))
                data = f.read(limit)
            return data.decode("utf-8", "replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_index(root: pathlib.Path) -> dict:
    index_path = root / "logs" / "codered_rdr_content_mp_index_v11.json"
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def correlate(root: pathlib.Path) -> tuple[str, dict]:
    log_paths = [
        root / "logs" / "codered_rdr_bootstrap_guard_v9.log",
        root / "logs" / "codered_udp_bootstrap_v14.log",
        root / "logs" / "codered_udp_bootstrap_v12.log",
        root / "build" / "bin" / "Windows" / "Release" / "xenia.log",
    ]
    log_paths.extend(sorted((root / "logs").glob("xenia_codered_v14*.log")))
    log_paths = list(dict.fromkeys(log_paths))
    texts = {str(path): read_text(path) for path in log_paths if path.exists()}
    combined = "\n".join(texts.values()).lower()

    mp_hits = {}
    for marker, needles in MP_MARKERS.items():
        hits = [needle for needle in needles if needle.lower() in combined]
        mp_hits[marker] = {"observed": bool(hits), "matched": hits}

    net_hits = {}
    for marker in NET_MARKERS:
        count = sum(len(re.findall(re.escape(marker.lower()), text.lower())) for text in texts.values())
        net_hits[marker] = count

    index = load_index(root)
    summary = index.get("summary", {}) if isinstance(index, dict) else {}
    payload = {
        "time": stamp(),
        "mp_markers": mp_hits,
        "net_markers": net_hits,
        "content_index_reference": summary,
        "logs_used": list(texts.keys()),
    }

    lines = [
        "CodeRED v14 RDR MP Correlation",
        f"Time: {payload['time']}",
        "",
        "Network Evidence:",
    ]
    for marker, count in net_hits.items():
        lines.append(f"  {marker}: {count}")
    lines.extend(["", "MP Script Correlation:"])
    for marker, data in mp_hits.items():
        state = "observed" if data["observed"] else "not observed in current logs"
        lines.append(f"  {marker}: {state}")
    lines.extend(["", "v11 Content Index Reference:"])
    if summary:
        for key in sorted(summary):
            lines.append(f"  {key}: {summary[key]}")
    else:
        lines.append("  No v11 JSON index found.")
    return "\n".join(lines) + "\n", payload


def copy_small_logs(root: pathlib.Path, out_dir: pathlib.Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    candidates = [
        root / "logs",
        root / "build" / "bin" / "Windows" / "Release",
    ]
    for base in candidates:
        if not base.exists():
            continue
        for path in base.glob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".dmp":
                continue
            if path.stat().st_size > 8 * 1024 * 1024:
                continue
            target = out_dir / f"{base.name}_{path.name}"
            shutil.copy2(path, target)
            copied += 1
    return copied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    root = root_dir()
    logs = root / "logs"
    text, payload = correlate(root)
    report = logs / "codered_v14_mp_correlation.txt"
    report.write_text(text, encoding="utf-8")
    (logs / "codered_v14_mp_correlation.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    send_dir = pathlib.Path(args.out) if args.out else logs / "CODERED_SEND_THESE_V14"
    if send_dir.exists():
        shutil.rmtree(send_dir, ignore_errors=True)
    copied = copy_small_logs(root, send_dir)
    zip_path = logs / f"codered_v14_small_logs_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in send_dir.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(send_dir))
    print(report)
    print(zip_path)
    print(f"copied={copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
