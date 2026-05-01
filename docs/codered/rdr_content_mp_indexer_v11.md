# CodeRED RDR Content Multiplayer Indexer v11

## Goal

Create a safe, non-mutating index of `content.zip` / `content/` to identify the local multiplayer script tree that should become active when Xenia's System Link/private-host bootstrap succeeds.

## Current interpretation

The latest logs show RDR receiving a local network identity and then repeatedly polling `recvfrom` with `WSAGetLastError: 10035`. That points to a missing UDP/session response, not missing world data.

## What this pass indexes

- `content/release/multiplayer/freemode/freemode.csc`
- `content/release/multiplayer/mp_idle.csc`
- `content/release/multiplayer/multiplayer_system_thread.csc`
- `content/release/multiplayer/multiplayer_update_thread.csc`
- `content/release/multiplayer/pr_multiplayer.csc`
- action areas such as Fort Mercer, Gaptooth Breach, Nosalida, Pike's Basin, Solomon's Folly, Tesoro Azul, Tumbleweed, Twin Rocks, wilderness animal areas
- CTF/deathmatch/coop/region scripts
- playground/rotation/support/tutorial/spectator scripts
- gringo/common scripts
- vehicle/wagon/cart/coach/car/horse/train path references
- population/ambient/update-thread leads

## Safety rules

- Do not modify content directly from this pass.
- Do not use content script patching as a replacement for Xenia session bootstrap work.
- Keep Disc 1 as the default test target, Disc 2 as the MP/Undead fallback.
- If testing patch experiments later, use copied archives only and verify reopen/proof JSON.

## Next Xenia pass after this

The likely next emulator-side pass remains UDP/System Link bootstrap:

- stronger `WSASendTo`/`WSARecvFrom` tracing
- packet echo / discovery responder
- session beacon data
- route to `XSessionCreate`, `XSessionSearch`, `XNetRegisterKey`

