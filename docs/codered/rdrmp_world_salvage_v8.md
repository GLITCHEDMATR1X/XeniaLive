# CodeRED RDRMP World Salvage / Super v6 v8

This kit keeps the v6 launch path because v6 reached the multiplayer loading screen, then adds a world-aware private host and RDRMP documentation salvage.

## Finding

The uploaded RDRMP package is documentation/reference material for the PC RDRMP project. It is not a drop-in Xbox 360 System Link server. The useful pieces are sector names, actor/model names, weather names, event vocabulary, and native/hash references.

## Practical use

Use RDRMP data as a world manifest for CodeRED private-host metadata and future patches. It should not be expected to stream a world into Xbox 360 RDR by itself.

## Test order

1. Run `CodeRED_RDRMP_World_Salvage_Menu_v8.bat`.
2. Choose `3. Private WorldHost - Disc 2 - SAFE CPU`.
3. If it reaches the loading screen but waits forever, choose `4. True LAN - Disc 2 - SAFE CPU` and compare logs.
4. Collect logs with option 6.

## Files

- `tools/codered_rdrmp_world_salvage_v8.py` builds `data/codered/rdrmp_world_manifest_v8.json` from the RDRMP docs zip.
- `tools/codered_rdr_world_host_v8.py` starts a private host with normal session endpoints plus `/world` and `/world/manifest`.
- `data/codered/rdrmp_world_manifest_v8.json` is a compact manifest generated from the uploaded docs.
