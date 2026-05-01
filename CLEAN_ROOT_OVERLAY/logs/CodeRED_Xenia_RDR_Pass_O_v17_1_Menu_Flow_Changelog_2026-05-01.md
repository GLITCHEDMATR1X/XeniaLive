# CodeRED Xenia RDR Pass O v17.1 - Menu Flow Fix

## Goal
Prevent the main bootstrap menu from being swallowed by host/game output.

## Changed
- Updated `CodeRED_RDR_Bootstrap_Menu_v9.bat` title to v17.1.
- Launches game runners in separate CMD windows using `start ... cmd /k`.
- Launches BootstrapHost and AI Guest Bridge in separate minimized CMD windows.
- Opens AI Guest Control Menu in a separate CMD window.
- Keeps direct command/status actions in the main menu.

## Preserved
- Existing v14 SPHost launchers.
- Existing v17 AI bridge/controller scripts.
- Existing v9 LAN/private/offline fallbacks.
- Existing notes, logs, docs, patches, and scripts.

## Usage
Run `CodeRED_RDR_Bootstrap_Menu_v9.bat`, choose option 4 or 5 to launch SPHost + AI Bridge, then use option 13 or 15 for AI guest control.
