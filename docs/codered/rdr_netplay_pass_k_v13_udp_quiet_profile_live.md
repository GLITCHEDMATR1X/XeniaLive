# CodeRED RDR Netplay Pass K / v13

Date: 2026-05-01

## Purpose

Get the next RDR multiplayer test past the LAN/System Link loading stall by removing the UDP echo storm and fixing the local profile/Live capability gate in Xenia, without touching dashboard/system-update XEX files.

## What Changed

- `tools/codered_rdr_bootstrap_host_v9.py`
  - Keeps the v9 filename for launcher compatibility, but now reports v12 health.
  - Runs UDP tracing in passive mode by default.
  - Ignores CodeRED bootstrap packets (`CODERED_RDR_V9` / `CODERED_RDR_V12`) so it does not reply to itself forever.
  - Adds `--trace-every` and defaults `--beacon-interval` to `0.0`.
- `CodeRED_Start_RDR_BootstrapHost_v9.bat`
  - Starts the host without `--verbose`.
  - Forces passive UDP mode with `--beacon-interval 0 --trace-every 120`.
- `src/xenia/kernel/xam/xam_net.cc`
  - Adds `netplay_udp_bootstrap_interval` support.
  - Raises the default receive-poll injection cadence from every 45 polls to every 240 polls.
- `src/xenia/kernel/xam/xam_user.cc`
  - In CodeRED netplay modes only (`network_mode != 0`), reports a signed-in local profile as Live-signed-in.
  - Grants `XamUserCheckPrivilege` and reports Gold membership/online enabled so RDR should stop treating the selected local profile as disconnected from Live.
- `tools/codered_rdr_bootstrap_guard_v9.py`
  - Writes v12 log/config markers while preserving existing v9 batch compatibility.
  - Adds `netplay_udp_bootstrap_interval = 240` to generated configs.
  - Cleans up profile check scanning so archived bundles are not counted as active profile state.
- `CodeRED_RDR_Bootstrap_Menu_v9.bat`
  - Labels the menu as v12 and marks True LAN Disc 1 as the recommended current test.

## Current Active Test

Configured without launching:

- Mode: `lan`
- Disc: `disc1`
- Network mode: `1`
- XHTTP: `false`
- Target: Disc 1 GOTY ISO under `rdr 1`
- UDP bootstrap interval: `240`

Use menu option 4 first:

```bat
CodeRED_RDR_Bootstrap_Menu_v9.bat
```

Then choose:

```text
4. True LAN - Disc 1 SAFE
```

## Expected Proof Lines

In the new Xenia log, look for:

```text
CodeRED Netplay: XNetGetTitleXnAddr mode=1 ... guest_port=3074
CodeRED Netplay: XamUserCheckPrivilege granted user=0 mask=000000FC
```

If private bootstrap is tested after LAN, the UDP helper should no longer print continuous `direct-reply` loops to its own `CODERED_RDR_V12` packets.

## Notes

- The missing old profile picker is expected when `logged_profile_slot_0_xuid` is configured. Xenia is auto-selecting `E03000004156EF97`.
- The old 32 MB UDP echo-storm trace was moved to `_archive\cleanup_20260501\udp_echo_spam_pre_v13`.
- A stale older `codered_rdr_private_host.py` process on port `36000` was stopped so the v12 BootstrapHost can bind cleanly when private mode is tested.
- Single-player hosting is not patched into RDR content in this pass. The safer fallback remains emulator-side profile/session/network emulation unless logs prove the title exposes a single-player session path.
