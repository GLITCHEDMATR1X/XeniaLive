#!/usr/bin/env python3
r"""CodeRED RDRMP World Salvage v8.

Builds a small world/session manifest from RDRMP docs without extracting the
whole archive. RDRMP is PC-only, so this is reference data for CodeRED/Xenia,
not a drop-in Xbox 360 server world.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys
import zlib

TARGETS = {
    "RDRMP-Docs-main/page/f.a.q.md": "faq",
    "RDRMP-Docs-main/page/game_reference/sectors.md": "sectors",
    "RDRMP-Docs-main/page/game_reference/actors.md": "actors",
    "RDRMP-Docs-main/page/game_reference/weathers.md": "weathers",
    "RDRMP-Docs-main/page/core_reference/events.md": "events",
    "RDRMP-Docs-main/page/core_reference/event/trigger_on_server.md": "trigger_on_server",
    "RDRMP-Docs-main/page/core_reference/event/trigger_on_client.md": "trigger_on_client",
}


def root_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def read_targets_from_zip(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open("rb") as f:
        count = 0
        while len(out) < len(TARGETS) and count < 100000:
            sig = f.read(4)
            if sig == b"PK\x03\x04":
                hdr = f.read(26)
                if len(hdr) != 26:
                    break
                _ver, flag, comp, _mtime, _mdate, _crc, csize, _usize, nlen, elen = struct.unpack("<HHHHHIIIHH", hdr)
                name = f.read(nlen).decode("utf-8", "replace")
                f.read(elen)
                count += 1
                if flag & 0x08:
                    raise RuntimeError(f"Unsupported streaming zip entry with data descriptor: {name}")
                if name in TARGETS:
                    raw = f.read(csize)
                    if comp == 0:
                        data = raw
                    elif comp == 8:
                        data = zlib.decompress(raw, -15)
                    else:
                        data = b""
                    out[TARGETS[name]] = data.decode("utf-8", "replace")
                else:
                    f.seek(csize, 1)
            elif sig == b"PK\x01\x02":
                break
            elif not sig:
                break
            else:
                break
    return out


def quoted_items(text: str) -> list[str]:
    return re.findall(r'"([A-Za-z0-9_\-]+)"', text)


def table_names(text: str) -> list[str]:
    names = []
    for line in text.splitlines():
        m = re.match(r"\|\s*([A-Z][A-Z0-9_]+)\s*\|\s*\d+\s*\|", line.strip())
        if m:
            names.append(m.group(1))
    return names


def build_manifest(texts: dict[str, str]) -> dict:
    sector_items = quoted_items(texts.get("sectors", ""))
    world: list[str] = []
    child: list[str] = []
    for item in sector_items:
        low = item.lower()
        if low.startswith(("blk_", "arm_", "beh_", "mac_", "chu_", "rth_", "tum_", "tes_")) or "props" in low or "_int" in low:
            child.append(item)
        else:
            if len(world) < 140:
                world.append(item)
            else:
                child.append(item)

    actor_pairs = re.findall(r'\["([A-Za-z0-9_]+)"\]\s*=\s*(\d+)', texts.get("actors", ""))
    actor_names = [name for name, _id in actor_pairs]
    vehicles = [
        a for a in actor_names
        if any(k in a.lower() for k in ("horse", "wagon", "coach", "cart", "car", "truck", "train", "vehicle", "mule", "donkey", "bull", "ox"))
    ]
    weathers = table_names(texts.get("weathers", ""))
    events = sorted(set(re.findall(r"core:[a-z_]+", texts.get("events", ""))))

    return {
        "schema": "codered.rdrmp_world_manifest.v8",
        "source": "RDRMP-Docs-main from uploaded world salvage zip",
        "assessment": {
            "direct_xbox360_server_world": False,
            "direct_xenia_runtime_server": False,
            "reason": "RDRMP docs identify it as a PC Red Dead Redemption custom multiplayer project and state it is not designed for Xbox 360/other platforms.",
            "usable_for_xenia": "Reference data only: sector names, actor/model names, weather names, event vocabulary, and native/hash references can seed CodeRED private-host/world metadata and future script/content patches.",
        },
        "counts": {
            "world_sector_candidates": len(world),
            "child_sector_candidates": len(child),
            "actors": len(actor_names),
            "vehicle_related_actors": len(vehicles),
            "weathers": len(weathers),
            "core_events": len(events),
        },
        "world_sector_candidates": world[:160],
        "child_sector_candidates": child[:220],
        "vehicle_related_actors": vehicles[:180],
        "weather_candidates": weathers[:80],
        "core_events": events,
        "server_world_seed": {
            "default_sector": "blackwater" if "blackwater" in world else (world[0] if world else ""),
            "fallback_sector": "wilderness" if "wilderness" in world else "",
            "default_weather": "CLEAR" if "CLEAR" in weathers else (weathers[0] if weathers else ""),
            "session_name": "CodeRED RDRMP World Salvage v8",
            "strict_match": ["title_id", "media_id", "title_update", "dlc_state", "region"],
        },
        "next_engine_targets": [
            "Keep using v6/v7 because it reaches the loading screen.",
            "Add a true LAN/private split so launchers cannot accidentally mix mode=1 and mode=2.",
            "Capture whether RDR reaches XSessionCreate/Search or only UDP recvfrom polling.",
            "Only after XSessionSearch/Join is proven should world manifest metadata be wired into the emulator bridge.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", nargs="?", default="xenia-rdrmp world salvage v6 base.zip")
    ap.add_argument("--out", default="data/codered/rdrmp_world_manifest_v8.json")
    args = ap.parse_args()
    root = root_dir()
    candidates = [pathlib.Path(args.zip), root / args.zip, root.parent / args.zip, pathlib.Path(r"D:\Games\Red Dead Redemption") / args.zip]
    zip_path = next((p for p in candidates if p.exists()), None)
    if not zip_path:
        print("Could not find RDRMP docs zip. Put it next to this Xenia source folder or pass its path.")
        return 2
    texts = read_targets_from_zip(zip_path)
    manifest = build_manifest(texts)
    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
