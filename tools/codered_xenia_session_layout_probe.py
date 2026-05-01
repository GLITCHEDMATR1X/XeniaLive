#!/usr/bin/env python3
"""Source-level validator for the Code RED Xenia session layout bridge."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "src/xenia/kernel/xsession.h": [
        "kCodeRedXSessionInfoSize = 0x3C",
        "kCodeRedXSessionSearchResultHeaderSize = 0x8",
        "kCodeRedXSessionSearchResultSize = 0x5C",
        "kCodeRedXSessionLocalDetailsSize = 0x80",
        "FillCodeRedSessionDetails",
        "MakeCodeRedSessionKey",
    ],
    "src/xenia/kernel/xsession.cc": [
        "StoreCodeRedXSessionInfo",
        "StoreCodeRedXSessionSearchResult",
        "XSESSION_SEARCHRESULT header=0x8 result=0x5C",
        "XSESSION_LOCAL_DETAILS=0x80",
        "StoreCodeRedXnAddr",
        "FormatCodeRedSessionKey",
    ],
    "src/xenia/kernel/xam/apps/xgi_app.cc": [
        "ReadXSessionSearchBuffer",
        "ReadXSessionSearchByIdsOrWeightedBuffer",
        "ReadXSessionDetailsBuffer",
        "XGI_SESSION_SEARCH",
        "XGI_SESSION_DETAILS",
    ],
    "docs/codered/rdr_netplay_pass_f_session_layout.md": [
        "Pass F Session Layout Bridge",
        "XSESSION_SEARCHRESULT = 0x5C",
        "XGI_SESSION_SEARCH_WEIGHTED",
    ],
}


def main() -> int:
    results = []
    for rel, needles in CHECKS.items():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [needle for needle in needles if needle not in text]
        results.append({
            "file": rel,
            "exists": path.exists(),
            "missing": missing,
            "passed": path.exists() and not missing,
        })
    summary = {"passed": all(item["passed"] for item in results), "results": results}
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
