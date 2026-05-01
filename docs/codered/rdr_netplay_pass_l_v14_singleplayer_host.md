# CodeRED RDR Netplay Pass L - v14 Singleplayer Host

Date: 2026-05-01

## Goal

Let RDR run Disc 1 or Disc 2 in a single-player host test mode while another local client can attempt to discover/join the host through the existing CodeRED private session bridge. Save writes are disabled in this mode.

The active safety rule is simple: save writes stay disabled for this mode.

## What Changed

- Added `network_mode=3` / `netplay_singleplayer_host=true`.
- `XNetGetTitleXnAddr` now creates one deterministic advertised System Link session when single-player host mode is active.
- The advertised session is published to the local private host as `singleplayer-host`.
- Saved-game content create/header/thumbnail/delete writes are blocked while `netplay_disable_saves=true`.
- Existing saved-game packages mount read-only in this mode.
- Added Disc 1 and Disc 2 single-player host launchers:
  - `CodeRED_Run_RDR_SPHost_Disc1_Safe_v14.bat`
  - `CodeRED_Run_RDR_SPHost_Disc2_Safe_v14.bat`
- Single-player host configs reduce overhead:
  - `log_to_stdout=false`
  - `flush_log=false`
  - `enable_console=false`
  - `net_logging=false`
  - `netplay_udp_bootstrap=false`
  - `gpu=vulkan`
  - `vsync=true`

## Expected Proof Lines

- `CodeRED Netplay: SinglePlayerHost advertise ...`
- `CodeRED Netplay: PublishSession ...`
- `CodeRED Netplay: blocked saved-game ...` if RDR attempts to write saves
- `CODERED_ACTIVE_NETPLAY_MODE.txt` should show:
  - `mode=sp-host`
  - `network_mode=3`
  - `netplay_singleplayer_host=True`
  - `netplay_disable_saves=True`
  - `vsync=true`

## Known Limitation

This pass advertises a join target and exposes it through the private session bridge. It does not yet prove that RDR single-player code will accept a live peer into the world without title-side multiplayer scripts taking over. If the guest discovers the session but cannot load in, the next pass should hook the guest join result into the title's session details/QoS path and inspect any new XSession/XNet calls.
