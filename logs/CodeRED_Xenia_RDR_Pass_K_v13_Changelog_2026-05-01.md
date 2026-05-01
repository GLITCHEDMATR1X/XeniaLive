# CodeRED Xenia RDR Pass K / v13 Changelog

## Summary

Pass K focuses on the two problems seen in the latest RDR multiplayer test:

- LAN/System Link stayed on the loading screen.
- The UDP helper was creating a self-echo loop and heavy console/log traffic.
- RDR still had evidence of Live/profile gating despite a local profile being loaded.

## Changes

- Made the Python bootstrap host quiet/passive by default.
- Ignored CodeRED self-bootstrap UDP packets to stop recursive replies.
- Added configurable Xenia UDP bootstrap receive-poll interval.
- Set generated configs to `netplay_udp_bootstrap_interval = 240`.
- Added CodeRED netplay-only profile/Live emulation:
  - `XamUserGetSigninState` reports Live-signed-in for the auto-selected profile.
  - `XamUserGetSigninInfo` reports Live-signed-in for the auto-selected profile.
  - `XamUserCheckPrivilege` grants privileges in netplay modes.
  - Membership tier and online-enabled checks report usable online capability in netplay modes.
- Updated the menu text to v12 and made True LAN Disc 1 the recommended current test.
- Rotated the old large UDP echo-storm log into `_archive\cleanup_20260501\udp_echo_spam_pre_v13`.
- Stopped the stale `codered_rdr_private_host.py` process that was still bound to port `36000` from an older pass.

## Validation

- Python compile passed for:
  - `tools\codered_rdr_bootstrap_host_v9.py`
  - `tools\codered_rdr_bootstrap_guard_v9.py`
  - `tools\codered_xenia_netplay_smoke.py`
  - `tools\codered_collect_v12.py`
- Source smoke test passed:
  - `py -3 tools\codered_xenia_netplay_smoke.py`
- Release build completed:
  - `build\bin\Windows\Release\xenia_canary.exe`
  - Size after v13 build: `15596032`
- Active config is now LAN Disc 1:
  - `logs\CODERED_ACTIVE_NETPLAY_MODE.txt`

## Next Test

Run:

```bat
CodeRED_RDR_Bootstrap_Menu_v9.bat
```

Choose option 4 first:

```text
True LAN - Disc 1 SAFE
```

After testing, choose option 8 to collect logs.
