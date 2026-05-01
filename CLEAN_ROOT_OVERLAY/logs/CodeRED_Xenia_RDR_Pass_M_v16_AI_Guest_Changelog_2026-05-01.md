# CodeRED Xenia RDR Pass v16 - SPHost AI Guest Control

Date: 2026-05-01

## Goal

Add a menu-driven, script-controlled AI Guest layer for the current SPHost work without deleting notes, touching saves, or patching Xenia C++.

## Files added

- CodeRED_AI_Guest_Menu_v16.bat
- CodeRED_Start_AI_Guest_v16.bat
- tools/codered_ai_guest_controller_v16.py
- data/codered/rdr_sphost_ai_guest_profile_v16.json
- docs/codered/rdr_sphost_ai_guest_v16.md
- README_CODERED_SPHOST_AI_GUEST_V16.txt

## Files updated

- CodeRED_RDR_Bootstrap_Menu_v9.bat

## Behavior

The AI guest can be spawned from the menu and controlled with subcommands:

- spawn / follow_defend
- follow
- guard
- attack
- idle
- regroup
- dismiss
- status

## Known limitation

The pass creates the AI state/control bridge only. A later game bridge must consume scratch/codered_ai_guest_state.json to create/control a visible in-world RDR actor.
