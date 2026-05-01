#!/usr/bin/env python3
r"""
CodeRED XEX / Package Viewer v10.

Purpose:
  - Identify Xbox 360 XEX2 executables, PIRS/LIVE/CON packages, and manifest-like files.
  - Audit Red Dead Redemption GOTY folders so CodeRED launchers don't accidentally run
    dashboard/system-update default.xex files instead of the intended game ISO/XEX.
  - Produce small JSON/TXT reports for debugging and handoff.

This is a read-only tool. It does not decrypt, patch, modify, or bypass XEX security.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import time
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable, Iterator, Optional

PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")
INTERESTING_STRING_RE = re.compile(
    r"(\.xex$|\.lex$|\.xzp$|\.cab$|\.xma$|default|avatar|guide|dash|live|xam|"
    r"xnet|xsession|session|system|update|manifest|rdr|red|redemption|"
    r"multiplayer|freeroam|network|titlelauncher)",
    re.IGNORECASE,
)

XEX_OPTIONAL_HEADER_NAMES = {
    0x000002FF: "resource_info",
    0x000003FF: "base_file_format",
    0x00000405: "base_reference",
    0x000005FF: "delta_patch_descriptor",
    0x000080FF: "bounding_path",
    0x000081FF: "device_id",
    0x00010001: "original_base_address",
    0x00010100: "entry_point",
    0x00010201: "image_base_address",
    0x000103FF: "import_libraries",
    0x00018002: "checksum_timestamp",
    0x00018102: "enabled_for_callcap",
    0x00018200: "enabled_for_fastcap",
    0x000183FF: "original_pe_name",
    0x000200FF: "static_libraries",
    0x00020104: "tls_info",
    0x00020200: "default_stack_size",
    0x00020301: "default_filesystem_cache_size",
    0x00020401: "default_heap_size",
    0x00028002: "page_heap_size_and_flags",
    0x00030000: "page_descriptor_table",
    0x00040006: "system_flags",
    0x00040310: "execution_info",
    0x00040404: "service_id_list",
    0x000405FF: "title_workspace_size",
    0x000406FF: "game_ratings",
    0x000407FF: "lan_key",
    0x00040801: "xbox360_logo",
    0x000E1040: "multidisc_media_ids",
}

DASHBOARD_HINTS = [
    "AvatarEditor.xex",
    "Guide.AvatarMiniCreator.xex",
    "Xam.Community.xex",
    "Xam.LiveMessenger.xex",
    "Xna_TitleLauncher.xex",
    "dash.firstuse.xex",
    "dashnui.xex",
    "livepack.xex",
    "natalsu.xex",
    "nuihud.xex",
]

SYSTEM_UPDATE_HINTS = [
    "system.manifest",
    "su20076000_00000000",
    "FFFE07DF",
    "AvatarAssetPack",
    "dash",
    "Xam.",
]

GAME_TARGET_HINTS = [
    "red dead redemption",
    "game of the year",
    "disc 1",
    "disc1",
    "disc 2",
    "disc2",
    "undead nightmare",
    "multiplayer",
]

DEFAULT_RECURSIVE_EXCLUDE_DIRS = {
    ".git",
    "build",
    "cache",
    "logs",
    "third_party",
}

@dataclass
class ScanIssue:
    severity: str
    message: str

@dataclass
class FileReport:
    path: str
    container: Optional[str]
    size: int
    sha1: str
    magic_hex: str
    kind: str
    warnings: list[ScanIssue]
    xex: Optional[dict] = None
    package: Optional[dict] = None
    manifest: Optional[dict] = None
    strings: Optional[list[str]] = None


def read_be32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        return 0
    return struct.unpack_from(">I", data, offset)[0]


def stream_sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stream_sha1_zip(zf: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha1()
    with zf.open(name, "r") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_head_file(path: Path, limit: int = 512 * 1024) -> bytes:
    with path.open("rb") as f:
        return f.read(limit)


def read_head_zip(zf: zipfile.ZipFile, name: str, limit: int = 512 * 1024) -> bytes:
    with zf.open(name, "r") as f:
        return f.read(limit)


def extract_interesting_strings(data: bytes, limit: int = 120) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in PRINTABLE_RE.finditer(data):
        try:
            s = match.group(0).decode("ascii", errors="ignore")
        except Exception:
            continue
        if not INTERESTING_STRING_RE.search(s):
            continue
        s = s.strip("\x00 ")
        if len(s) < 4 or s in seen:
            continue
        seen.add(s)
        values.append(s)
        if len(values) >= limit:
            break
    return values


def classify_magic(data: bytes, name: str = "") -> str:
    magic = data[:4]
    if magic == b"XEX2":
        return "XEX2"
    if magic in {b"PIRS", b"LIVE", b"CON "}:
        return magic.decode("ascii", errors="replace").strip()
    if magic == b"XMNP":
        return "XMNP_manifest"
    suffix = name.lower()
    if suffix.endswith(".xex"):
        return "maybe_xex_unknown_magic"
    if suffix.endswith(".manifest"):
        return "manifest_unknown_magic"
    return "unknown"


def parse_xex(data: bytes) -> dict:
    # XEX2 header fields are big-endian.
    module_flags = read_be32(data, 0x04)
    pe_data_offset = read_be32(data, 0x08)
    reserved = read_be32(data, 0x0C)
    security_info_offset = read_be32(data, 0x10)
    optional_header_count = read_be32(data, 0x14)

    headers = []
    entry_point = None
    image_base = None
    for i in range(min(optional_header_count, 256)):
        off = 0x18 + i * 8
        if off + 8 > len(data):
            break
        key = read_be32(data, off)
        value = read_be32(data, off + 4)
        name = XEX_OPTIONAL_HEADER_NAMES.get(key, "unknown")
        headers.append(
            {
                "index": i,
                "id_hex": f"0x{key:08X}",
                "name": name,
                "value_hex": f"0x{value:08X}",
                "value": value,
            }
        )
        if key == 0x00010100:
            entry_point = value
        elif key == 0x00010201:
            image_base = value

    return {
        "module_flags_hex": f"0x{module_flags:08X}",
        "pe_data_offset_hex": f"0x{pe_data_offset:08X}",
        "reserved_hex": f"0x{reserved:08X}",
        "security_info_offset_hex": f"0x{security_info_offset:08X}",
        "optional_header_count": optional_header_count,
        "entry_point_hex": f"0x{entry_point:08X}" if entry_point is not None else None,
        "image_base_hex": f"0x{image_base:08X}" if image_base is not None else None,
        "optional_headers": headers,
    }


def parse_package(data: bytes) -> dict:
    # STFS/PIRS parsing here is intentionally lightweight and read-only.
    strings = extract_interesting_strings(data, limit=80)
    return {
        "magic": data[:4].decode("ascii", errors="replace"),
        "likely_package_family": "Xbox 360 STFS/PIRS/LIVE/CON package",
        "interesting_strings": strings,
    }


def parse_manifest(data: bytes) -> dict:
    strings = extract_interesting_strings(data, limit=160)
    dashboard_matches = [s for s in strings if any(h.lower() in s.lower() for h in DASHBOARD_HINTS)]
    return {
        "magic": data[:4].decode("ascii", errors="replace"),
        "interesting_strings": strings,
        "dashboard_module_matches": dashboard_matches,
        "dashboard_module_count": len(dashboard_matches),
    }


def build_warnings(path_text: str, kind: str, data: bytes, strings: list[str]) -> list[ScanIssue]:
    warnings: list[ScanIssue] = []
    lower_path = path_text.lower()
    joined = "\n".join(strings)
    lower_strings = joined.lower()

    if Path(path_text).name.lower() == "default.xex":
        if any(h.lower() in lower_strings for h in DASHBOARD_HINTS) or "system.manifest" in lower_path:
            warnings.append(
                ScanIssue(
                    "high",
                    "default.xex appears related to dashboard/system-update content; do not auto-launch as RDR.",
                )
            )
        else:
            warnings.append(
                ScanIssue(
                    "medium",
                    "default.xex found. Verify it is the intended game executable, not a nearby system update executable.",
                )
            )

    if any(h.lower() in lower_path for h in ["su20076000", "system.manifest", "fffe07df"]):
        warnings.append(
            ScanIssue(
                "high",
                "System update / dashboard support content detected. Keep as reference only; avoid extraction into active launch folders.",
            )
        )

    if any(h.lower() in lower_strings for h in DASHBOARD_HINTS):
        warnings.append(
            ScanIssue(
                "high",
                "Dashboard/avatar/guide module names detected. This is reference material, not the RDR multiplayer world.",
            )
        )

    if kind == "maybe_xex_unknown_magic":
        warnings.append(ScanIssue("high", "File extension is .xex but magic is not XEX2."))

    return warnings


def make_file_report(path_text: str, size: int, sha1: str, data: bytes, container: Optional[str] = None) -> FileReport:
    kind = classify_magic(data, path_text)
    strings = extract_interesting_strings(data, limit=160)
    warnings = build_warnings(path_text, kind, data, strings)
    xex = None
    package = None
    manifest = None

    if kind == "XEX2":
        xex = parse_xex(data)
    elif kind in {"PIRS", "LIVE", "CON"}:
        package = parse_package(data)
    elif kind == "XMNP_manifest" or path_text.lower().endswith(".manifest"):
        manifest = parse_manifest(data)

    return FileReport(
        path=path_text,
        container=container,
        size=size,
        sha1=sha1,
        magic_hex=data[:16].hex(" ").upper(),
        kind=kind,
        warnings=warnings,
        xex=xex,
        package=package,
        manifest=manifest,
        strings=strings[:80],
    )


def is_candidate_name(path: Path | PurePosixPath) -> bool:
    name = path.name.lower()
    return (
        name.endswith(".xex")
        or name.endswith(".manifest")
        or name.startswith("su")
        or name in {"default.xex", "system.manifest"}
        or any(
            token in name
            for token in [
                "fffe07df",
                "avatar",
                "dash",
                "guide",
                "livepack",
                "titlelauncher",
                "xam",
            ]
        )
    )


def iter_filesystem(path: Path, recursive: bool, exclude_dirs: Iterable[str] = ()) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    exclude = {name.lower() for name in exclude_dirs}
    if not recursive:
        for child in path.iterdir():
            if child.is_file() and is_candidate_name(child):
                yield child
        return
    for current, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d.lower() not in exclude]
        current_path = Path(current)
        for filename in filenames:
            child = current_path / filename
            if is_candidate_name(child):
                yield child


def scan_filesystem(path: Path, recursive: bool, exclude_dirs: Iterable[str] = ()) -> list[FileReport]:
    reports: list[FileReport] = []
    for item in iter_filesystem(path, recursive, exclude_dirs=exclude_dirs):
        try:
            head = read_head_file(item)
            sha1 = stream_sha1_file(item)
            reports.append(make_file_report(str(item), item.stat().st_size, sha1, head))
        except Exception as exc:
            reports.append(
                FileReport(
                    path=str(item),
                    container=None,
                    size=0,
                    sha1="",
                    magic_hex="",
                    kind="error",
                    warnings=[ScanIssue("high", f"Failed to scan: {exc}")],
                )
            )
    return reports


def scan_zip(path: Path) -> list[FileReport]:
    reports: list[FileReport] = []
    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir() or not is_candidate_name(PurePosixPath(info.filename)):
                continue
            try:
                head = read_head_zip(zf, info.filename)
                sha1 = stream_sha1_zip(zf, info.filename)
                reports.append(
                    make_file_report(
                        info.filename,
                        info.file_size,
                        sha1,
                        head,
                        container=str(path),
                    )
                )
            except Exception as exc:
                reports.append(
                    FileReport(
                        path=info.filename,
                        container=str(path),
                        size=info.file_size,
                        sha1="",
                        magic_hex="",
                        kind="error",
                        warnings=[ScanIssue("high", f"Failed to scan zip member: {exc}")],
                    )
                )
    return reports


def risk_summary(reports: list[FileReport]) -> dict:
    counts: dict[str, int] = {}
    for report in reports:
        counts[report.kind] = counts.get(report.kind, 0) + 1
    default_xex = [r for r in reports if PurePosixPath(r.path).name.lower() == "default.xex"]
    high_warnings = [
        {"path": r.path, "message": w.message}
        for r in reports
        for w in r.warnings
        if w.severity == "high"
    ]
    likely_system_update = [
        r.path
        for r in reports
        if any(
            token in r.path.lower() or any(token in s.lower() for s in (r.strings or []))
            for token in ["system.manifest", "su20076000", "avatoreditor", "avatareditor", "xam.community", "livepack"]
        )
    ]
    return {
        "counts_by_kind": counts,
        "default_xex_count": len(default_xex),
        "high_warning_count": len(high_warnings),
        "high_warnings": high_warnings[:50],
        "likely_system_update_or_dashboard_paths": likely_system_update[:50],
        "launcher_guard_advice": [
            "Prefer ISO/XEX paths explicitly selected by launcher options, not blind default.xex discovery.",
            "Ignore folders containing system.manifest, su20076000_00000000, or FFFE07DF during RDR launch-target search.",
            "Disc 1 should be default for RDR GOTY tests; Disc 2 remains available for Undead Nightmare/multiplayer fallback.",
        ],
    }


def write_text_report(path: Path, result: dict) -> None:
    lines: list[str] = []
    lines.append("CodeRED XEX / Package Viewer v10")
    lines.append(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Root/input: {result['input']}")
    lines.append("")
    summary = result["summary"]
    lines.append("Summary:")
    for k, v in summary["counts_by_kind"].items():
        lines.append(f"  {k}: {v}")
    lines.append(f"  default.xex count: {summary['default_xex_count']}")
    lines.append(f"  high warnings: {summary['high_warning_count']}")
    lines.append("")

    for report in result["reports"]:
        lines.append("=" * 72)
        lines.append(f"Path: {report['path']}")
        if report.get("container"):
            lines.append(f"Container: {report['container']}")
        lines.append(f"Kind: {report['kind']}")
        lines.append(f"Size: {report['size']}")
        lines.append(f"SHA1: {report['sha1']}")
        lines.append(f"Magic: {report['magic_hex']}")
        if report.get("xex"):
            xex = report["xex"]
            lines.append("XEX:")
            lines.append(f"  PE/data offset: {xex.get('pe_data_offset_hex')}")
            lines.append(f"  security info offset: {xex.get('security_info_offset_hex')}")
            lines.append(f"  optional header count: {xex.get('optional_header_count')}")
            lines.append(f"  entry point: {xex.get('entry_point_hex')}")
            lines.append(f"  image base: {xex.get('image_base_hex')}")
            lines.append("  optional headers:")
            for h in xex.get("optional_headers", [])[:64]:
                lines.append(f"    {h['id_hex']} {h['name']} -> {h['value_hex']}")
        if report.get("manifest"):
            manifest = report["manifest"]
            lines.append("Manifest:")
            lines.append(f"  dashboard module matches: {manifest.get('dashboard_module_count')}")
            for s in manifest.get("dashboard_module_matches", [])[:30]:
                lines.append(f"    {s}")
        if report.get("package"):
            lines.append("Package:")
            lines.append(f"  {report['package'].get('likely_package_family')}")
        if report.get("warnings"):
            lines.append("Warnings:")
            for w in report["warnings"]:
                lines.append(f"  [{w['severity']}] {w['message']}")
        if report.get("strings"):
            lines.append("Interesting strings:")
            for s in report["strings"][:30]:
                lines.append(f"  {s}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", errors="replace")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CodeRED read-only XEX/PIRS/manifest viewer and launch-target auditor.")
    parser.add_argument("--path", required=True, help="File, folder, or .zip to scan.")
    parser.add_argument("--recursive", action="store_true", help="Recursively scan folders.")
    parser.add_argument("--json-out", default="logs/codered_xex_audit_v10.json", help="JSON report path.")
    parser.add_argument("--text-out", default="logs/codered_xex_audit_v10.txt", help="Text report path.")
    parser.add_argument("--strict-launch-guard", action="store_true", help="Exit nonzero if dashboard/system update default.xex risk is found.")
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to skip during recursive folder scans. Can be repeated.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.path)
    if not input_path.exists():
        print(f"ERROR: path not found: {input_path}", file=sys.stderr)
        return 2

    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        reports = scan_zip(input_path)
    else:
        exclude_dirs = list(args.exclude_dir)
        if args.recursive and not exclude_dirs:
            exclude_dirs = sorted(DEFAULT_RECURSIVE_EXCLUDE_DIRS)
        reports = scan_filesystem(input_path, recursive=args.recursive, exclude_dirs=exclude_dirs)

    result = {
        "tool": "codered_xex_viewer_v10",
        "input": str(input_path),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": risk_summary(reports),
        "reports": [asdict(r) for r in reports],
    }

    json_path = Path(args.json_out)
    text_path = Path(args.text_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_text_report(text_path, result)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote text: {text_path}")
    print(f"Scanned files: {len(reports)}")
    print(f"High warnings: {result['summary']['high_warning_count']}")

    if args.strict_launch_guard and result["summary"]["high_warning_count"]:
        print("Strict launch guard found high-risk dashboard/system update content.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
