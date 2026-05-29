# Code RED Xenia/RDR profile pass 6 findings

## What the uploaded logs prove

The profile is being discovered and auto-loaded:

```text
FindProfiles: Adding profile E03000004156EF97 to profile list
logged_profile_slot_0_xuid = "E03000004156EF97"
```

The profile check also found the profile/content files under:

```text
content\E03000004156EF97\FFFE07D1\00010000\E03000004156EF97\5454082B.gpd
content\E03000004156EF97\5454082B\00000001\RDR2MPSAVE.SAV
```

The game is not simply stuck at the old sign-in wall. It is reaching the MP/free-roam loading stack and repeatedly asking XAM/network APIs.

## Biggest config issue still present in Release.zip

The release configs still had:

```toml
license_mask = 0
net_logging = false
flush_log = false
netplay_disable_saves = true
disable_saves = true
```

For RDR Free Roam testing this is bad because the log shows RDR enumerating/opening MP save content such as `RDR2MPSAVE.SAV`.

Pass 6 sets:

```toml
license_mask = -1
net_logging = true
flush_log = true
netplay_disable_saves = false
disable_saves = false
logged_profile_slot_0_xuid = "E03000004156EF97"
```

## Build issue

The uploaded build log did not fail because of Code RED logic. It failed because the Xenia source tree is incomplete:

```text
CMake Error at CMakeLists.txt:313 (add_subdirectory):
  add_subdirectory given source "third_party" which is not an existing directory.
```

Run `git submodule update --init --recursive` or re-clone Xenia with `--recursive` before building.

## XAM source patch target

The Xenia functions that matter for this lane are in:

```text
src/xenia/kernel/xam/xam_user.cc
```

Patch targets:

```text
XamUserGetXUID_entry
XamUserGetSigninState_entry
XamUserGetSigninInfo_entry
XamUserCheckPrivilege_entry
```

The goal is to make the selected local profile consistently appear as a Live-capable signed-in local profile to RDR while staying offline/local to Xenia. This does not authenticate with official services.

## Why this is the next pass

The log repeatedly grants privilege checks already, but RDR keeps cycling network checks and save/profile enumeration. Making XAM identity consistent at the source level is cleaner than trying to edit the profile selector UI domain field.
