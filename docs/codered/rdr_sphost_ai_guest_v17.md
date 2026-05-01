# CodeRED RDR SPHost AI Guest v17

Pass v17 adds a local AI Guest Bridge service so the numbered menu commands have a live receiver instead of only writing JSON state.

## New behavior

- Starts a local private bridge on `http://127.0.0.1:36017`.
- Menu can spawn the AI guest and send follow / guard / attack / defend / idle / regroup / mount / dismount / dismiss commands.
- Writes durable runtime files:
  - `scratch/codered_ai_guest_state.json`
  - `scratch/codered_ai_guest_bridge_state_v17.json`
  - `scratch/codered_ai_guest_action_plan_v17.json`
  - `scratch/codered_ai_guest_commands.jsonl`
  - `logs/codered_ai_guest_bridge_v17.log`
  - `logs/codered_ai_guest_v17.log`

## What it is

This is the script-control layer for the AI guest. It gives SPHost a local command/state/action-plan system that a future RDR/game bridge can consume to create a visible companion actor.

## What it is not yet

It does not guarantee a visible in-world body by itself. The action plan clearly requests one, but the next pass still needs the RDR-side bridge/hook that can turn `request_spawn_actor`, `follow_target`, and `defend_player` into real game behavior.

## Main menu entries

- `4` Singleplayer Host Disc 1 + AI Bridge v17
- `5` Singleplayer Host Disc 2 + AI Bridge v17
- `13` AI Guest Control Menu v17
- `14` Start AI Guest Bridge v17
- `15` Spawn AI Guest Bodyguard now
- `16` AI Guest Status

## Safety boundary

This pass is localhost-only and does not contact real Xbox Live.
