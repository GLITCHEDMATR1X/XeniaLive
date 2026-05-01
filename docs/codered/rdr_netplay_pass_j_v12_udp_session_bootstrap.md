# CodeRED RDR Netplay Pass J / v12

## Goal

Break the remaining RDR multiplayer stall where the title has a local XNet identity but repeatedly polls UDP and receives only `WSAEWOULDBLOCK` / `10035`.

## Changes

- Added `netplay_udp_bootstrap` cvar under `[Netplay]`.
- Added emulator-side UDP bootstrap injection in `xam_net.cc`.
  - Applies only when `network_mode != 0`, `netplay_udp_bootstrap = true`, and `recvfrom` / `WSARecvFrom` would otherwise return `10035`.
  - Injects a small local discovery packet every controlled interval rather than every poll.
  - Logs `CodeRED Netplay: UDP bootstrap injected ... preview=...`.
- Strengthened the Python bootstrap host UDP responder.
  - Logs to `logs\codered_udp_bootstrap_v12.log`.
  - Replies directly to observed UDP peers and keeps beacons to local/broadcast targets.
- Strengthened launch target safety in the v9 guard.
  - Ignores paths containing `system.manifest`, `su20076000_00000000`, `FFFE07DF`, and system/update/dashboard `default.xex` targets.
- Added v12 MP correlation collector.
  - `tools\codered_collect_v12.py`
  - `CodeRED_Collect_Small_Logs_v12.bat`
  - Produces `logs\codered_v12_mp_correlation.txt/json`.

## Expected Proof Lines

- Private bootstrap:
  `CodeRED Netplay: XNetGetTitleXnAddr mode=2 ... guest_port=3074`
- True LAN:
  `CodeRED Netplay: XNetGetTitleXnAddr mode=1 ... guest_port=3074`
- UDP bootstrap:
  `CodeRED Netplay: UDP bootstrap injected api=recvfrom ...`
  or
  `CodeRED Netplay: UDP bootstrap injected api=WSARecvFrom ...`
- External responder:
  `UDP inbound #... preview=...`
- Session path:
  `XSessionCreate`, `XSessionSearch`, `XNetRegisterKey`

## Safety

This pass does not edit dashboard/system-update XEX or PIRS files. It stays on the emulator/tooling side.
