# CodeRED Xenia Canary Cleanup Pass v15

## Purpose

This package cleans the loose root-level clutter that accumulated during the RDR/Xenia netplay passes while keeping the currently useful launch/config/build helpers.

The uploaded messy loose-file zip mostly contained duplicate config backups, old helper versions, and repeated launch wrappers. This cleaned package keeps the current reliable set and removes older loose versions from the overlay.

## Use

1. Copy everything inside `CLEAN_ROOT_OVERLAY` into the root of your Xenia Canary folder.
2. Run `CodeRED_RDR_Bootstrap_Menu_v9.bat` for the current launcher menu.
3. Use options 2 or 3 for the current v14 singleplayer-host tests.
4. Run `CodeRED_Safe_Root_Cleanup_v15.bat` only when you want to remove old root-level backup/config/script clutter from your existing folder.

## Kept intentionally

- Current project/build files: `CMakeLists.txt`, `CMakePresets.json`, `xb`, `xb.bat`, `xb.ps1`, `xenia-build.py`.
- Current config trio: `xenia.config.toml`, `xenia-canary.config.toml`, `xenia-canary-config.toml`.
- Current v14 singleplayer-host launchers.
- v9 private/LAN/offline fallback launchers still referenced by the menu.
- v10 XEX/package viewer helpers.
- v11 content multiplayer indexer helpers.
- v14 small-log collection helper.
- v3 release build helper.
- README files for the kept diagnostic helpers.

## Removed from the overlay

- Old config backup copies: `*.codered_*_bak_*`.
- Old v6/v7/v8 launchers and relaunch/crash/world-host wrappers.
- Old Easy RDR Netplay v2/v3 wrappers.
- Old duplicate crash-guard READMEs.
- Loose test object: `zng_test.obj`.

## Not removed automatically

This pass does not auto-delete game folders, saves, source code, tools, docs, patches, or the compiled build output. The folder list shows heavy generated areas such as `build`, `cache`, `cache0`, `cache1`, `cache_host`, `logs/CODERED_SEND_THESE_*`, and save/content folders. Those are space-cleanup candidates, but deleting them blindly can remove the ready-to-run executable, shader caches, logs, or saves.

For source cleanliness, the safe cleanup script only targets old loose root files and stale generated send-back bundles. Delete full folders manually only after backing up saves and confirming you do not need the existing compiled exe.

## Current direction

The current functional experiment is still the v14 singleplayer host path. LAN/private/public Free Roam connection is not considered solved in this cleanup pass.
