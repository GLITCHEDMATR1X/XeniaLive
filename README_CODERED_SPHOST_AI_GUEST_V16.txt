# CodeRED Xenia RDR SPHost AI Guest v16

This pass adds a safe, script-controlled AI Guest control layer to the existing Xenia Canary/RDR SPHost launcher set.

## What changed

- Updated CodeRED_RDR_Bootstrap_Menu_v9.bat with new AI Guest entries.
- Added CodeRED_AI_Guest_Menu_v16.bat for subcommands.
- Added CodeRED_Start_AI_Guest_v16.bat for one-number bodyguard spawning.
- Added tools/codered_ai_guest_controller_v16.py.
- Added data/codered/rdr_sphost_ai_guest_profile_v16.json.
- Added docs/codered/rdr_sphost_ai_guest_v16.md.

## Main menu numbers

11. AI Guest Control Menu v16
12. Spawn AI Guest Bodyguard now
13. AI Guest Status
14. Exit

## AI subcommands

2. Spawn AI Guest: Bodyguard / Follow-Defend
3. Follow player
4. Guard position
5. Attack hostiles
6. Idle / Hold fire
7. Regroup / Warp requested
8. Dismiss
9. Status
10. Open AI state JSON

## What this proves

This pass proves the AI guest can be spawned and controlled by script state. It writes:

scratch/codered_ai_guest_state.json
scratch/codered_ai_guest_commands.jsonl
logs/codered_ai_guest_v16.log

The controller also makes a short best-effort POST to the local BootstrapHost at http://127.0.0.1:36000, but it does not require that host to support AI endpoints yet. If no endpoint exists, the local state still works and becomes the contract for the next bridge pass.

## Important limitation

This pass does not yet guarantee a visible in-world RDR actor. It creates the script-control bridge and spawn request that a later RDR/game bridge can consume.

Safe next pass:

Make codered_rdr_bootstrap_host_v9.py read scratch/codered_ai_guest_state.json and expose/consume an AI guest endpoint. Then connect that state to the best available RDR actor/spawn/follow mechanism.
