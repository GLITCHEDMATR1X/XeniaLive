# CodeRED Xenia RDR Pass N v17 - AI Guest Bridge

Completed:

- Added `tools/codered_ai_guest_bridge_v17.py` local HTTP bridge.
- Added `tools/codered_ai_guest_controller_v17.py` controller with bridge posting and local fallback state.
- Added `CodeRED_Start_AI_Guest_Bridge_v17.bat`.
- Added `CodeRED_Start_AI_Guest_v17.bat`.
- Added `CodeRED_AI_Guest_Menu_v17.bat` with numbered subcommands.
- Added SPHost + AI launchers for Disc 1 and Disc 2.
- Updated `CodeRED_RDR_Bootstrap_Menu_v9.bat` to include AI Bridge and AI SPHost options.
- Added v17 profile, docs, README, manifest, and validation.

Validation:

- Python syntax check passed for controller and bridge.
- Controller init/status/spawn/command commands tested locally.
- Bridge started locally and accepted spawn/command/status POSTs.
- Output zip tested clean.

Known limitation:

- This creates a live AI command/action-plan bridge, not a guaranteed visible RDR actor yet. The next pass should wire the game/bootstrap side to consume the action plan.
