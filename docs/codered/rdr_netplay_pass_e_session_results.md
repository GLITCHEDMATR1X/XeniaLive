# Code RED Xenia RDR Netplay - Pass E Session Result Bridge

## Goal

Pass E moves the RDR System Link work from "sessions can be published and searched" toward "sessions can be consumed by game-facing session-result paths."

The previous private-host pass added the route layer. This pass adds the emulator-side pieces needed to turn private-host session JSON into compact guest-visible result snapshots and to fetch per-session details.

## Added / changed

- `XLiveAPI::GetSessionDetails(...)`
- `XLiveAPI::GetRemoteSessionDetails(...)`
- Remote search now enriches `/search` results through `/details` when available.
- JSON parsing now preserves:
  - `players[]`
  - `started`
  - `advertised`
  - public/private slot counts
  - filled/open slot counts
- `FillCodeRedSessionSearchResults(...)` writes a compact, documented guest-memory session snapshot.
- XGI session routes now include guarded handlers for:
  - `XGISessionLeaveLocal`
  - `XSessionSearch`
  - `XSessionGetDetails`
  - `XSessionSearchByIDs/Weighted` probe path
- The private host now recalculates filled/open public/private slot counts after create/join/leave.

## Conservative behavior

The result writer is intentionally guarded. If an XGI call does not expose a safe-looking guest result buffer, the handler logs discovered sessions but does not write random memory. This avoids crashing games while we confirm RDR's exact buffer layout from logs.

## Current compact snapshot layout

Header at result buffer:

```text
0x00 u32 result_count
0x04 u32 total_available
0x08 u32 result_stride
0x0C u32 first_result_guest_pointer
```

Each result is `0x80` bytes:

```text
0x00 u64 session_id
0x08 u32 flags
0x0C u32 host_ipv4_network_order
0x10 u32 port
0x14 u32 public_slots
0x18 u32 private_slots
0x1C u32 open_public_slots
0x20 u32 open_private_slots
0x24 u32 filled_public_slots
0x28 u32 filled_private_slots
0x2C u32 started
0x30 u32 advertised
0x34 u8[6] mac
0x3C u32 title_id
0x40 mirror session_id
0x48 mirror host_ipv4_network_order
0x4C mirror port
0x50 mirror open_public_slots
0x54 mirror open_private_slots
```

## RDR test focus

Use the same route as the prior pass:

```text
Single Player → Pause → Multiplayer → System Link → Free Roam
```

Watch for these log lines:

```text
CodeRED Netplay: XSessionSearch filled=...
CodeRED Netplay: XSessionSearch found ... sessions but no safe result buffer was detected
CodeRED Netplay: GetRemoteSessionDetails session=...
```

If RDR still does not list the remote session, the next pass should capture the exact XGI buffer words from the search call and replace the compact snapshot with the actual `XSESSION_SEARCHRESULT` / `XSESSION_INFO` structure expected by the title.
