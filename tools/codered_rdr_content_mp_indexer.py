#!/usr/bin/env python3
r"""CodeRED RDR Content Multiplayer Indexer v11.

Purpose:
  Build a safe, non-mutating index of RDR content.zip / content tree files,
  especially multiplayer, freemode, action-area, gringo, vehicle, and update
  scripts. The tool avoids Python zipfile's central-directory dependency by
  streaming ZIP local file headers, which is safer for odd RDR/content archives.

Outputs:
  logs/codered_rdr_content_mp_index_v11.json
  logs/codered_rdr_content_mp_index_v11.txt

Notes:
  This is a research/indexing tool. It does not edit .csc, .sco, .xex, .rpf,
  PIRS, or package files.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import re
import struct
import sys
import time
import zlib
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

LOCAL_FILE_HEADER = b"PK\x03\x04"
CENTRAL_DIR_HEADER = b"PK\x01\x02"
END_CENTRAL_DIR = b"PK\x05\x06"

ASCII_RE = re.compile(rb"[A-Za-z0-9_./\\:$#@+\- ]{4,}")

INTEREST_TERMS = [
    "multiplayer", "freemode", "mp_idle", "system_thread", "update_thread",
    "pr_multiplayer", "playground", "actionarea", "action_area", "deathmatch",
    "ctf", "coop", "spectator", "tutorial", "session", "xsession", "xnet",
    "systemlink", "system_link", "network", "netdll", "host", "join", "lobby",
    "player", "gamemode", "spawn", "region", "rotation", "population", "ambient",
    "gringo", "vehicle", "wagon", "coach", "cart", "car", "horse", "train",
    "long_update_thread", "medium_update_thread", "short_update_thread",
]

CORE_MP_NAMES = {
    "content/release/multiplayer/freemode/freemode.csc",
    "content/release/multiplayer/mp_idle.csc",
    "content/release/multiplayer/multiplayer_system_thread.csc",
    "content/release/multiplayer/multiplayer_update_thread.csc",
    "content/release/multiplayer/pr_multiplayer.csc",
    "content/release/multiplayer/deathmatch/deathmatch.csc",
    "content/release/multiplayer/ctf/ctf_base_game.csc",
}

@dataclasses.dataclass
class LocalZipEntry:
    name: str
    compression: int
    compressed_size: int
    uncompressed_size: int
    flags: int
    crc32: int
    local_header_offset: int
    data_offset: int
    mtime: int
    mdate: int

    @property
    def is_dir(self) -> bool:
        return self.name.endswith("/") or self.uncompressed_size == 0 and self.compressed_size == 0


def iter_local_zip_entries(path: Path) -> Iterator[LocalZipEntry]:
    """Stream ZIP local headers without relying on central directory parsing."""
    with path.open("rb") as f:
        while True:
            pos = f.tell()
            sig = f.read(4)
            if not sig:
                return
            if sig in (CENTRAL_DIR_HEADER, END_CENTRAL_DIR):
                return
            if sig != LOCAL_FILE_HEADER:
                # Some archives may have trailing data. Stop rather than failing hard.
                return
            header = f.read(26)
            if len(header) != 26:
                return
            (
                _version_needed,
                flags,
                compression,
                mtime,
                mdate,
                crc32,
                compressed_size,
                uncompressed_size,
                name_len,
                extra_len,
            ) = struct.unpack("<HHHHHIIIHH", header)
            raw_name = f.read(name_len)
            try:
                name = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                name = raw_name.decode("cp437", errors="replace")
            f.read(extra_len)
            data_offset = f.tell()
            if flags & 0x08:
                raise RuntimeError(
                    f"Unsupported ZIP data-descriptor entry at {name!r}. "
                    "Repack the archive or extract this file manually first."
                )
            yield LocalZipEntry(
                name=name,
                compression=compression,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
                flags=flags,
                crc32=crc32,
                local_header_offset=pos,
                data_offset=data_offset,
                mtime=mtime,
                mdate=mdate,
            )
            f.seek(compressed_size, os.SEEK_CUR)


def read_zip_entry(path: Path, entry: LocalZipEntry, max_uncompressed: int = 2_000_000) -> bytes:
    if entry.is_dir:
        return b""
    if entry.uncompressed_size > max_uncompressed:
        return b""
    with path.open("rb") as f:
        f.seek(entry.data_offset)
        raw = f.read(entry.compressed_size)
    if entry.compression == 0:
        return raw
    if entry.compression == 8:
        return zlib.decompress(raw, -15)
    return b""


def iter_tree_entries(root: Path) -> Iterator[Tuple[str, int, Path]]:
    for p in root.rglob("*"):
        if p.is_file():
            try:
                rel = p.relative_to(root).as_posix()
                yield rel, p.stat().st_size, p
            except OSError:
                continue


def normalize_path(name: str) -> str:
    return name.replace("\\", "/").lower()


def categorize(path: str) -> List[str]:
    p = normalize_path(path)
    cats: List[str] = []
    if p in CORE_MP_NAMES:
        cats.append("mp_core")
    if "/release/multiplayer/" in p:
        cats.append("release_multiplayer")
    if "/release/multiplayer/freemode/" in p or p.endswith("freemode.csc"):
        cats.append("mp_freemode")
    if "/release/multiplayer/action_areas/" in p:
        cats.append("mp_action_area")
    if "/release/multiplayer/playground/" in p:
        cats.append("mp_playground")
    if "/release/multiplayer/regions/" in p:
        cats.append("mp_region")
    if "/release/multiplayer/rotations/" in p:
        cats.append("mp_rotation")
    if "/release/multiplayer/support/" in p:
        cats.append("mp_support")
    if "/release/multiplayer/tutorial/" in p:
        cats.append("mp_tutorial")
    if "/release/multiplayer/spectator/" in p:
        cats.append("mp_spectator")
    if "/ctf/" in p or "ctf" in Path(p).name:
        cats.append("mode_ctf")
    if "/deathmatch/" in p or "deathmatch" in Path(p).name:
        cats.append("mode_deathmatch")
    if "/coop/" in p or "coop" in Path(p).name:
        cats.append("mode_coop")
    if "/scripting/gringo/" in p or "/gringo/" in p or "gringo" in p:
        cats.append("gringo")
    if any(t in p for t in ("vehicle", "wagon", "coach", "cart", "car", "horse", "train")):
        cats.append("vehicle_or_mount_related")
    if "long_update_thread" in p or "medium_update_thread" in p or "short_update_thread" in p:
        cats.append("update_thread")
    if "/init/pop/" in p or "population" in p:
        cats.append("population")
    if "/ambient/" in p:
        cats.append("ambient")
    if "/debug/" in p:
        cats.append("debug")
    return sorted(set(cats))


def extract_strings(data: bytes, limit: int = 80) -> List[str]:
    out: List[str] = []
    for m in ASCII_RE.finditer(data):
        s = m.group(0).decode("latin-1", errors="replace").strip()
        if len(s) >= 4 and not all(ch in "0123456789ABCDEFabcdefx" for ch in s):
            out.append(s)
            if len(out) >= limit:
                break
    return out


def term_hits(path: str, strings: Sequence[str]) -> Dict[str, int]:
    hay = normalize_path(path) + "\n" + "\n".join(s.lower() for s in strings[:200])
    return {term: hay.count(term) for term in INTEREST_TERMS if term in hay}


def short_record(path: str, size: int, strings: Optional[Sequence[str]] = None) -> Dict[str, object]:
    cats = categorize(path)
    rec: Dict[str, object] = {
        "path": path,
        "size": size,
        "categories": cats,
    }
    if strings is not None:
        rec["strings_sample"] = list(strings[:30])
        hits = term_hits(path, strings)
        if hits:
            rec["term_hits"] = hits
    return rec


def scan_zip(path: Path, max_scan_entries: int) -> Dict[str, object]:
    entries = list(iter_local_zip_entries(path))
    reports: List[Dict[str, object]] = []
    category_counts: collections.Counter[str] = collections.Counter()
    ext_counts: collections.Counter[str] = collections.Counter()
    total_uncompressed = 0
    scan_count = 0

    for e in entries:
        total_uncompressed += e.uncompressed_size
        p = normalize_path(e.name)
        ext = Path(p).suffix.lower() or "<none>"
        ext_counts[ext] += 1
        cats = categorize(e.name)
        for c in cats:
            category_counts[c] += 1
        if cats and not e.is_dir:
            strings: List[str] = []
            if scan_count < max_scan_entries and e.uncompressed_size <= 750_000:
                try:
                    strings = extract_strings(read_zip_entry(path, e), limit=60)
                except Exception as exc:
                    strings = [f"<scan error: {exc}>"]
                scan_count += 1
            reports.append(short_record(e.name, e.uncompressed_size, strings))

    return build_result(path, "zip", len(entries), total_uncompressed, ext_counts, category_counts, reports)


def scan_tree(root: Path, max_scan_entries: int) -> Dict[str, object]:
    reports: List[Dict[str, object]] = []
    category_counts: collections.Counter[str] = collections.Counter()
    ext_counts: collections.Counter[str] = collections.Counter()
    total_size = 0
    entry_count = 0
    scan_count = 0
    for rel, size, p in iter_tree_entries(root):
        entry_count += 1
        total_size += size
        ext_counts[Path(rel).suffix.lower() or "<none>"] += 1
        cats = categorize(rel)
        for c in cats:
            category_counts[c] += 1
        if cats:
            strings: List[str] = []
            if scan_count < max_scan_entries and size <= 750_000:
                try:
                    strings = extract_strings(p.read_bytes(), limit=60)
                except Exception as exc:
                    strings = [f"<scan error: {exc}>"]
                scan_count += 1
            reports.append(short_record(rel, size, strings))
    return build_result(root, "tree", entry_count, total_size, ext_counts, category_counts, reports)


def build_result(
    input_path: Path,
    input_kind: str,
    entry_count: int,
    total_size: int,
    ext_counts: collections.Counter[str],
    category_counts: collections.Counter[str],
    reports: List[Dict[str, object]],
) -> Dict[str, object]:
    reports_sorted = sorted(
        reports,
        key=lambda r: (
            0 if "mp_core" in r.get("categories", []) else 1,
            0 if "release_multiplayer" in r.get("categories", []) else 1,
            str(r.get("path", "")),
        ),
    )
    core = [r for r in reports_sorted if "mp_core" in r.get("categories", [])]
    action = [r for r in reports_sorted if "mp_action_area" in r.get("categories", [])]
    regions = [r for r in reports_sorted if "mp_region" in r.get("categories", [])]
    vehicles = [r for r in reports_sorted if "vehicle_or_mount_related" in r.get("categories", [])]
    gringos = [r for r in reports_sorted if "gringo" in r.get("categories", [])]
    recommended_flow = [
        "Use Disc 1 as default GOTY/RDR base launch target, with Disc 2 as Undead/MP fallback.",
        "Do not assume content/world files are missing; multiplayer scripts are present locally.",
        "Keep Xenia focus on UDP/System Link/session bootstrap until XSessionCreate/Search/RegisterKey logs appear.",
        "Use this index to correlate loading-screen stalls with multiplayer_system_thread, multiplayer_update_thread, mp_idle, freemode, and pr_multiplayer.",
        "Do not bulk patch .csc/.sco content. Use copied archives and one controlled experiment at a time.",
    ]
    return {
        "tool": "codered_rdr_content_mp_indexer_v11",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input": str(input_path),
        "input_kind": input_kind,
        "summary": {
            "entry_count": entry_count,
            "total_uncompressed_or_file_bytes": total_size,
            "ext_counts": dict(ext_counts.most_common(30)),
            "category_counts": dict(category_counts.most_common()),
            "mp_core_count": len(core),
            "mp_action_area_count": len(action),
            "mp_region_count": len(regions),
            "vehicle_or_mount_related_count": len(vehicles),
            "gringo_count": len(gringos),
        },
        "recommended_flow": recommended_flow,
        "important_groups": {
            "mp_core": core[:30],
            "mp_action_areas": action[:80],
            "mp_regions": regions[:120],
            "vehicle_or_mount_related": vehicles[:120],
            "gringo": gringos[:120],
        },
        "all_relevant_reports": reports_sorted,
    }


def write_text_report(result: Dict[str, object], path: Path) -> None:
    s = result["summary"]
    lines: List[str] = []
    lines.append("CodeRED RDR Content Multiplayer Index v11")
    lines.append(f"Time: {result['timestamp']}")
    lines.append(f"Input: {result['input']}")
    lines.append(f"Input kind: {result['input_kind']}")
    lines.append("")
    lines.append("Summary:")
    lines.append(f"  entries/files: {s['entry_count']}")
    lines.append(f"  total bytes: {s['total_uncompressed_or_file_bytes']}")
    lines.append("  categories:")
    for k, v in s["category_counts"].items():
        lines.append(f"    {k}: {v}")
    lines.append("")
    lines.append("Interpretation:")
    for item in result["recommended_flow"]:
        lines.append(f"  - {item}")
    lines.append("")
    groups = result["important_groups"]
    for group_name in ["mp_core", "mp_action_areas", "mp_regions", "vehicle_or_mount_related", "gringo"]:
        lines.append("=" * 72)
        lines.append(group_name)
        for rec in groups.get(group_name, []):
            lines.append(f"- {rec['path']} ({rec['size']} bytes) [{', '.join(rec.get('categories', []))}]")
            hits = rec.get("term_hits")
            if hits:
                compact = ", ".join(f"{k}:{v}" for k, v in list(hits.items())[:10])
                lines.append(f"    hits: {compact}")
            strs = rec.get("strings_sample") or []
            if strs:
                joined = "; ".join(strs[:8])
                lines.append(f"    strings: {joined}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="CodeRED RDR content multiplayer indexer v11")
    ap.add_argument("--input", required=True, help="content.zip or extracted content folder")
    ap.add_argument("--out", default="logs", help="output folder")
    ap.add_argument("--max-scan-entries", type=int, default=500, help="max relevant files to string-scan")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not inp.exists():
        raise SystemExit(f"Input not found: {inp}")

    if inp.is_dir():
        result = scan_tree(inp, args.max_scan_entries)
    else:
        result = scan_zip(inp, args.max_scan_entries)

    json_path = out_dir / "codered_rdr_content_mp_index_v11.json"
    txt_path = out_dir / "codered_rdr_content_mp_index_v11.txt"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_text_report(result, txt_path)
    print(f"Wrote: {json_path}")
    print(f"Wrote: {txt_path}")
    return 0


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
