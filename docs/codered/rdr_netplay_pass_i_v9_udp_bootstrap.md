# CodeRED Xenia RDR Netplay Pass I / v9 - UDP Bootstrap + Regression Cleanup

## Focus

This pass is conservative. It does not try to stream a PC RDRMP world into Xbox 360 RDR. RDR GOTY already has the world data locally. The logs show the current blocker is earlier: the game is polling XNet/UDP and repeatedly getting `WSAGetLastError: 10035`, meaning no packet is available.

## Regression cleanup

- Disc 1 is now the default test target.
- Disc 2 remains available as the multiplayer/Undead fallback.
- Every launch stamps the active mode into all common Canary config names and writes `logs/CODERED_ACTIVE_NETPLAY_MODE.txt`.
- LAN and Private Host scripts are separated so a private test cannot be mistaken for a LAN test.
- The old invalid Python docstring escape warning is avoided by using raw docstrings.

## Source patch

Patched:

```text
src/xenia/kernel/xam/xam_net.cc
```

Changes:

- Fixed XNADDR `wPortOnline` assignment for big-endian guest fields. The bridge now assigns the host value to `xe::be<uint16_t>` instead of pre-swapping with `htons`.
- Added payload preview logging for `sendto`, `WSASendTo`, `recvfrom`, and `WSARecvFrom`.
- Added throttled would-block logging so network traces are useful without filling logs with identical `10035` messages.
- `XNetGetTitleXnAddr` now logs both local and online IP plus the guest-visible port.

## New host/tooling

Added:

```text
tools/codered_rdr_bootstrap_host_v9.py
tools/codered_rdr_bootstrap_guard_v9.py
CodeRED_RDR_Bootstrap_Menu_v9.bat
```

The v9 BootstrapHost provides:

- HTTP private session endpoints.
- A pre-advertised default session.
- A UDP beacon/tracer on System Link port 3074.
- UDP packet logging if RDR sends discovery traffic.

The UDP beacon is deliberately labeled bootstrap/tracing. It is not a final RDR protocol implementation. Its job is to test whether the game can get beyond the endless no-packet receive loop and reveal the next required handshake.

## Recommended test order

1. `CodeRED_RDR_Bootstrap_Menu_v9.bat`
2. Option 2: Private Bootstrap - Disc 1 SAFE
3. If Disc 1 does not enter the multiplayer path, use option 3: Private Bootstrap - Disc 2 SAFE
4. Use option 4/5 only for true LAN comparison.
5. Use option 7 if the profile/sign-in overlay stops appearing.
6. Use option 8 to collect small logs.

## Proof lines to watch

Private Bootstrap should show:

```text
CodeRED Netplay: XNetGetTitleXnAddr mode=2 ... guest_port=3074
CodeRED Netplay: recvfrom ... error=10035
CodeRED Netplay: sendto ... preview=...
UDP inbound #...
XSessionCreate / XSessionSearch / XNetRegisterKey
```

True LAN should show:

```text
CodeRED Netplay: XNetGetTitleXnAddr mode=1 ... guest_port=3074
```

If the log still shows `mode=2` during a LAN test, the wrong launcher/config was used.

## Sign-in note

Not seeing the online/profile prompt is not automatically a bug. It may mean a profile is already selected or that the current launch path did not request the sign-in UI. v9 adds a profile check report so we can tell whether profile slots are empty or whether the emulator has profile-like files available.
