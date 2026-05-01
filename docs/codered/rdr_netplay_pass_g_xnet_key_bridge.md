# Code RED Xenia RDR Netplay — Pass G XNet Key / Join Stability Bridge

## Goal

Make the RDR System Link join path more stable after the game receives a session search result. Previous passes could publish and return sessions, but the XNet key lifecycle was still placeholder-level.

## Added

- Deterministic `XNKID` / `XNKEY` lifecycle helpers.
- `XNetCreateKey` now writes a stable 8-byte session/key id and 16-byte exchange key.
- `XNetRegisterKey` now stores registered keys instead of returning through a stub.
- `XNetUnregisterKey` now removes registered keys.
- `XNetXnAddrToInAddr` now checks registered keys before falling back to the raw XNADDR.
- `XNetInAddrToXnAddr` now rebuilds an XNADDR from a registered key when possible.
- Search/detail session buffers now carry the same deterministic key that gets advertised to the private host.
- Private host session records now preserve `keyExchangeKey`.

## Why this matters for Red Dead Redemption

RDR's System Link flow can search, select, and then attempt to join a returned session. If the selected session's `XNKID`, `XNKEY`, `XNADDR`, and translated `IN_ADDR` do not stay stable across calls, the join path can collapse after the UI shows a session. This pass gives those values a consistent bridge.

## Logs to watch

```text
CodeRED Netplay: XNetCreateKey id=...
CodeRED Netplay: XNetRegisterKey id=... ip=... port=... keys=...
CodeRED Netplay: XNetXnAddrToInAddr key=... ip=... registered=...
CodeRED Netplay: XNetInAddrToXnAddr key=... ip=... registered=...
CodeRED Netplay: XNetUnregisterKey id=... removed=...
```

## Still conservative

This does not claim full Xbox Live security or encryption. It only keeps the session key material stable enough for private-host/System Link experiments.

## Next pass

Pass H should focus on RDR-specific context/property filling and title/profile matching so the sessions RDR receives look more like the exact Free Roam records it expects.
