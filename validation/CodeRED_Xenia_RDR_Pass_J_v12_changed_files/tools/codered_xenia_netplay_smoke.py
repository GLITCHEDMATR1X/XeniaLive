#!/usr/bin/env python3
"""Code RED source-level smoke checks for the Xenia RDR netplay passes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "src/xenia/kernel/XLiveAPI.h": [
        "class XLiveAPI", "NetworkMode", "CreateHostSession",
        "BuildSessionSearchPath", "GetSessionDetails", "GetCodeRedXLiveAPI"
    ],
    "src/xenia/kernel/XLiveAPI.cc": [
        "DEFINE_int32(network_mode", "DEFINE_string(netplay_api_address",
        "DEFINE_bool(net_logging", "DEFINE_bool(netplay_udp_bootstrap",
        "DEFINE_int32(netplay_http_timeout_ms",
        "CodeRED Netplay: CreateHostSession", "RegisterPlayer",
        "PublishSession", "SearchRemoteSessions", "BuildSessionJoinPath",
        "BuildSessionLeavePath", "BuildQosPath", "GetRemoteSessionDetails", "ExtractJsonArray",
        "keyExchangeKey", "ParseCodeRedSessionKey"
    ],
    "src/xenia/kernel/xsession.h": [
        "IsSystemlinkSession", "IsNetworkSession", "struct XSessionDetails",
        "class XSessionRegistry", "MakeCodeRedSessionId", "MakeCodeRedSessionKey",
        "FillCodeRedSessionSearchResults", "kCodeRedXSessionSearchResultSize = 0x5C",
        "FillCodeRedSessionDetails"
    ],
    "src/xenia/kernel/xsession.cc": [
        "XSessionRegistry::CreateHostSession", "JoinLocalUsers",
        "StartSession", "Search", "DescribeCodeRedSessionSearchLayout",
        "StoreCodeRedXSessionSearchResult", "XSESSION_LOCAL_DETAILS=0x80",
        "FormatCodeRedSessionKey"
    ],
    "src/xenia/kernel/util/net_utils.h": [
        "GetConfiguredIPv4NetworkOrder", "MakeMachineId", "MakeStableMac"
    ],
    "src/xenia/kernel/util/http_client.h": [
        "HttpResponse", "HttpGet", "HttpPostJson", "HttpDelete"
    ],
    "src/xenia/kernel/util/http_client.cc": [
        "ParseHttpUrl", "DoHttpRequest", "Xenia-CodeRED-Netplay"
    ],
    "src/xenia/kernel/util/network_adapter_manager.h": [
        "NetworkAdapterManager", "NetworkAdapterInfo"
    ],
    "src/xenia/kernel/xam/xam_net.cc": [
        "NetDll_WSARecvFrom, kNetworking, kImplemented",
        "NetDll_XNetGetTitleXnAddr, kNetworking, kImplemented",
        "NetDll_XNetQosServiceLookup, kNetworking, kImplemented",
        "NetDll_XNetQosListen, kNetworking, kImplemented",
        "NetDll_XNetRegisterKey, kNetworking, kImplemented",
        "NetDll_XNetUnregisterKey, kNetworking, kImplemented",
        "XNetInAddrToXnAddr key", "CodeRED Netplay",
        "UDP bootstrap injected", "ShouldInjectUdpBootstrap"
    ],
    "src/xenia/kernel/xam/apps/xgi_app.cc": [
        "#include \"xenia/kernel/XLiveAPI.h\"", "XSessionCreate accepted",
        "JoinLocalUsers", "StartSession", "EndSession", "XSessionSearch", "XSessionGetDetails",
        "ReadXSessionSearchBuffer", "ReadXSessionDetailsBuffer"
    ],
    "docs/codered/rdr_netplay_profile.json": [
        "Red Dead Redemption", "System Link Free Roam"
    ],
    "docs/codered/rdr_private_host_contract.json": [
        "/players", "/title/{titleId}/sessions", "/qos"
    ],
    "docs/codered/rdr_netplay_pass_d_private_host_bridge.md": [
        "Pass D", "Private Host HTTP Bridge", "codered_rdr_private_host.py"
    ],
    "docs/codered/rdr_netplay_pass_e_session_results.md": [
        "Pass E", "Session Result Bridge", "XSessionSearch"
    ],
    "docs/codered/rdr_netplay_pass_f_session_layout.md": [
        "Pass F", "Session Layout Bridge", "XSESSION_SEARCHRESULT"
    ],
    "docs/codered/rdr_netplay_pass_g_xnet_key_bridge.md": [
        "Pass G", "XNet Key", "XNetRegisterKey", "keyExchangeKey"
    ],
    "tools/codered_rdr_private_host.py": [
        "ThreadingHTTPServer", "/players", "sessions", "qos", "refresh_slot_counts",
        "keyExchangeKey"
    ],
    "tools/codered_xenia_session_layout_probe.py": [
        "kCodeRedXSessionSearchResultSize", "XGI_SESSION_SEARCH_WEIGHTED"
    ],
    "tools/codered_collect_v12.py": [
        "CodeRED v12 RDR MP Correlation", "MP_MARKERS", "NET_MARKERS"
    ],
    "docs/codered/rdr_netplay_pass_j_v12_udp_session_bootstrap.md": [
        "Pass J", "UDP bootstrap", "netplay_udp_bootstrap"
    ],
    "tools/codered_start_rdr_private_host.bat": [
        "codered_rdr_private_host.py", "--port 36000"
    ],
}


def main() -> int:
    results = []
    for rel, needles in CHECKS.items():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [needle for needle in needles if needle not in text]
        results.append({"file": rel, "exists": path.exists(), "missing": missing,
                        "passed": path.exists() and not missing})

    summary = {"passed": all(item["passed"] for item in results),
               "results": results}
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
