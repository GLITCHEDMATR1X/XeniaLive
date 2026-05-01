#!/usr/bin/env python3
"""Apply CodeRED RelaunchGuard v7 to Xenia Canary source.

Fixes the RDR multiplayer title-restart crash path by changing
XamLoaderLaunchTitle so a valid launch-data request exits cleanly after saving
launch_data.bin instead of calling TerminateTitle while JIT/game threads are
still unwinding.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    src = root / "src" / "xenia" / "kernel" / "xam" / "xam_info.cc"
    if not src.exists():
        print(f"ERROR: source file not found: {src}")
        return 2
    text = src.read_text(encoding="utf-8", errors="ignore")
    if "CodeRED RelaunchGuard v7" in text:
        print("CodeRED RelaunchGuard v7 is already applied.")
        return 0

    # Add a cvar near the existing staging_mode cvar.
    marker = '''DEFINE_bool(staging_mode, 0,
            "Enables preview mode in dashboards to render debug information.",
            "Kernel");
'''
    insert = marker + '''
DEFINE_bool(codered_clean_title_relaunch, true,
            "CodeRED/RDR: exit cleanly after XamLoaderLaunchTitle saves launch_data.bin. "
            "This avoids a JIT-thread crash during Red Dead Redemption multiplayer title relaunch tests.",
            "Netplay");
'''
    if marker not in text:
        print("ERROR: staging_mode marker not found; source version differs.")
        return 3
    text = text.replace(marker, insert, 1)

    old = '''  // Translate the launch path to a full path.
  if (raw_name_ptr && !raw_name_ptr.value().empty()) {
    loader_data.launch_path = xe::path_to_utf8(raw_name_ptr.value());
    loader_data.launch_data_present = true;
    xam->SaveLoaderData();
    title = "Title was restarted";
    message =
        "Title closed with new launch data. \\nPlease restart Xenia. "
        "Game will be loaded automatically.";
  } else {
'''
    new = '''  // Translate the launch path to a full path.
  if (raw_name_ptr && !raw_name_ptr.value().empty()) {
    loader_data.launch_path = xe::path_to_utf8(raw_name_ptr.value());
    loader_data.launch_data_present = true;
    xam->SaveLoaderData();
    XELOGI("CodeRED RelaunchGuard v7: saved launch data path='{}' flags={:08X} bytes={}",
           loader_data.launch_path, flags.value(), loader_data.launch_data.size());

    if (cvars::codered_clean_title_relaunch) {
      // Red Dead Redemption can request a title restart when entering multiplayer.
      // The stock path calls TerminateTitle after showing a dialog; in our tests
      // that leaves JIT/game threads unwinding and produces an access violation.
      // launch_data.bin has already been saved, so exit cleanly and let the v7
      // launcher restart Xenia, where LoadLoaderData will consume it.
      std::quick_exit(0);
    }

    title = "Title was restarted";
    message =
        "Title closed with new launch data. \\nPlease restart Xenia. "
        "Game will be loaded automatically.";
  } else {
'''
    if old not in text:
        print("ERROR: XamLoaderLaunchTitle block not found; source version differs.")
        return 4
    text = text.replace(old, new, 1)
    bak = src.with_suffix(src.suffix + f".codered_v7_bak_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    bak.write_text(src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    src.write_text(text, encoding="utf-8")
    print(f"Applied CodeRED RelaunchGuard v7 to: {src}")
    print(f"Backup written: {bak}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
