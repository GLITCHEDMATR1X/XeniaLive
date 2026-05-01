# Code RED Xenia RDR Netplay - Pass C Session Bridge

## Goal

Move from only fixing XNet/System Link stubs into a compile-safe session layer that Red Dead Redemption can hit while entering Multiplayer -> System Link -> Free Roam.

## Added

- `src/xenia/kernel/xsession.cc`
- Expanded `src/xenia/kernel/xsession.h`
- Expanded `src/xenia/kernel/XLiveAPI.h/.cc`
- Wired `src/xenia/kernel/xam/apps/xgi_app.cc` into the Code RED session bridge
- Added `docs/codered/rdr_private_host_contract.json`

## Emulator-side behavior

The bridge now tracks host sessions locally with deterministic 16-character session IDs, title ID, session pointer, flags, slot counts, host IPv4, System Link port, stable generated MAC, local player list, and started/ended state.

## XGI messages now routed

- `XSessionCreate` creates a local session and logs the private-host route that should be posted later.
- `XGISessionDelete` removes local session state.
- `XGISessionJoinLocal` stores local users and private-slot flags.
- `XSessionStart` marks the local session as started.
- `XSessionEnd` marks the local session as ended.

## Safe behavior

Xbox Live-featured sessions still fail unless `network_mode = 2` is active. This avoids accidentally pretending official Xbox Live exists while still allowing the PrivateHost path for test builds.

## Next pass

Add the actual HTTP bridge for `/players`, `/title/{titleId}/sessions`, `/search`, `/details`, `/join`, `/leave`, and `/qos`. Keep it behind `network_mode = 2` and `xhttp = true` so normal Canary remains safe.
