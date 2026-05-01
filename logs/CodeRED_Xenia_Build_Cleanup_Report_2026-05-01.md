# CodeRED Xenia Build Cleanup Report - 2026-05-01

## Current Build

- Active source folder: `D:\Games\Red Dead Redemption\xenia-canary-6de80df`
- Built executable: `D:\Games\Red Dead Redemption\xenia-canary-6de80df\build\bin\Windows\Release\xenia_canary.exe`
- Executable size: `15,582,208` bytes
- Executable timestamp: `2026-04-30 21:51:49`
- No `xenia_canary.exe` process was running after this cleanup pass.
- The folder is not currently a Git worktree, so CodeRED patch provenance is preserved by the local patch/log files rather than Git metadata.

## Game Targets

- Disc 1 target:
  `D:\Games\Red Dead Redemption\xenia-canary-6de80df\rdr 1\Red Dead Redemption - Game of the Year Edition (USA, Europe) (En,Fr,De,Es,It) (Disc 1) (Red Dead Redemption Single Player).iso`
- Disc 2 target:
  `D:\Games\Red Dead Redemption\xenia-canary-6de80df\rdr 2\Red Dead Redemption - Game of the Year Edition (USA, Europe) (En,Fr,De,Es,It) (Disc 2) (Undead Nightmare and Multiplayer).iso`
- Confirmed active `rdr 1` / `rdr 2` folders contain `0` `.xex` files after the user removed them.
- The old active-mode target path under `D:\Games\Red Dead Redemption\rdr 1` was stale and invalid. It has been replaced with the valid in-source Disc 1 ISO path.

## Changes Made

- Updated `tools\codered_rdr_bootstrap_guard_v9.py`.
  - Default RDR search root is now the current Xenia source folder, not `D:\Games\Red Dead Redemption`.
  - Target search skips generated folders: `.git`, `build`, `cache`, `logs`, `third_party`.
  - Added `configure`, a no-launch command that writes current CodeRED/Xenia config and active-mode files.
- Updated `tools\codered_xex_viewer.py`.
  - Recursive scans now skip generated folders by default.
  - Candidate selection no longer treats every file under the parent `Red Dead Redemption` path as interesting.
- Updated `CodeRED_RDR_Launch_Target_Guard_v10.bat`.
  - Default scan path is now the Xenia source folder.
- Updated `CodeRED_XEX_View_And_Audit_v10.bat`.
  - Default scan path is now the Xenia source folder.
- Updated `build\bin\Windows\Release\recent.toml`.
  - Replaced the stale 8.3 top-level ISO path with the valid Disc 1 ISO path.
- Ran `tools\codered_rdr_bootstrap_guard_v9.py configure --mode private --disc disc1 --variant safe --x64-mask 0`.
  - Rewrote root and Release config files.
  - Rewrote `logs\CODERED_ACTIVE_NETPLAY_MODE.txt`.
  - Private host health returned `ok`.

## Cleanup Moves

- Moved old nested diagnostic bundles out of active logs:
  `D:\Games\Red Dead Redemption\xenia-canary-6de80df\_archive\cleanup_20260501\logs_send_bundles`
- Moved old v6 logs/zip out of active logs:
  `D:\Games\Red Dead Redemption\xenia-canary-6de80df\_archive\cleanup_20260501\old_v6_logs`
- Moved stale top-level v2 netplay scripts out of the main Red Dead folder:
  `D:\Games\Red Dead Redemption\_archive\cleanup_20260501\stale_top_level_v2_netplay`

## Validation

- Disc target resolution:
  - `disc1` resolves to the valid Disc 1 ISO under `xenia-canary-6de80df\rdr 1`.
  - `disc2` resolves to the valid Disc 2 ISO under `xenia-canary-6de80df\rdr 2`.
- XEX launch target guard:
  - Report: `logs\codered_launch_target_guard_v10.txt`
  - Scanned files: `44`
  - High warnings: `0`
- Source-level netplay smoke:
  - Command: `py -3 tools\codered_xenia_netplay_smoke.py`
  - Result: `passed: true`

## Remaining Cleanup Candidates

- `build\bin\Windows\Release\xenia.log` is still about `105 MB`. Keep it until the next failed launch is understood, then rotate/archive it.
- Root still contains older v5/v6/v7/v8 launcher/readme files. They are no longer the active path, but were left in place because they may still be useful for comparison.
- `rdr 1` and `rdr 2` still contain `rdr2_layer0.rpf` and `rdr2_layer1.rpf` reference files next to the ISOs. They do not affect the explicit ISO launch path, but should be moved to a reference folder later if they are not needed beside the discs.

## Next Test

Use `CodeRED_RDR_Bootstrap_Menu_v9.bat`, then select the private Disc 1 safe path first. If it still reports Xbox Live sign-in/connectivity trouble, send back:

- `D:\Games\Red Dead Redemption\xenia-canary-6de80df\logs\CODERED_ACTIVE_NETPLAY_MODE.txt`
- `D:\Games\Red Dead Redemption\xenia-canary-6de80df\logs\codered_rdr_bootstrap_guard_v9.log`
- `D:\Games\Red Dead Redemption\xenia-canary-6de80df\build\bin\Windows\Release\xenia.log`
- A screenshot or exact text of the in-game System Link/Xbox Live message.
