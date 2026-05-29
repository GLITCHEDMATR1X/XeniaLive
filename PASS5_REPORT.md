# Code RED Xenia profile consistency Pass 5

Input release: /mnt/data/Release.zip

This pass does not binary-patch `xenia_canary.exe`. The uploaded release contains only the compiled EXE/PDB, not the source tree, and a blind binary patch to XAM identity functions would be unsafe.

What this pass does safely now:

- Keeps slot 0 profile fixed to `E03000004156EF97`.
- Enables MP save writes by setting `netplay_disable_saves=false` and `disable_saves=false`.
- Enables all licenses with `license_mask=-1`.
- Enables net logging and flush logging for the next run.
- Keeps Code RED single-player host bridge enabled.
- Adds a source patch sketch for the next rebuilt Xenia: make slot-0 online XUID mirror local XUID, return Live/Gold-capable sign-in state locally, and make Online Domain editable/persistent.

Why this pass exists:

The previous log showed:

```text
logged_profile_slot_0_xuid = "E03000004156EF97"
FindProfiles: Adding profile E03000004156EF97 to profile list
XamUserGetXUID(...) sometimes returns 0000000000000000
netplay_disable_saves = true
disable_saves = true
```

So the profile is found, but not every XAM path returns a consistent online-capable identity. This first-test package removes the save-write blocker and prepares the source-level XAM fix for the next executable build.

Test:

1. Put this folder beside `xenia_canary.exe`, or copy the three TOML files from `dropin_config_first_test/` manually.
2. Run `01_INSTALL_CONFIG_FIRST_TEST.bat`.
3. Fully close and reopen Xenia.
4. Launch the same Free Roam test.
5. If it still hangs, run `03_SCAN_NEW_LOG.bat` and send the new `xenia.log`.

Next required executable/source patch:

- `ProfileManager::LoadAccount/CreateAccount/UpdateAccount`: normalize online XUID/domain/tier.
- `XamUserGetXUID`: never return zero for slot 0 when local profile is signed in.
- `XamUserGetSigninInfo`: report local Live-capable sign-in state for slot 0.
- `XamUserIsOnlineEnabled`, `XamUserGetSubscriptionType`, `XamUserGetMembershipTier`: return local Gold-capable status for slot 0 under Code RED mode.
- `GamercardUI`: make Online Domain editable and persist `xbox.com` fallback.
