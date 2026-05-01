# CodeRED RDR XEX / Package Viewer v10

## Scope

This pass adds a read-only viewer/auditor for Xbox 360 executable and package files:

- `XEX2` executable containers
- `PIRS`, `LIVE`, and `CON` package containers
- manifest-like files such as `system.manifest`

It is designed to prevent a specific regression discovered during the RDR/Xenia multiplayer work:
system-update/dashboard reference folders may contain their own `default.xex`, and those can confuse
launcher scripts that search blindly for `default.xex`.

## Added files

```text
tools/codered_xex_viewer.py
CodeRED_XEX_View_And_Audit_v10.bat
CodeRED_XEX_View_Zip_v10.bat
CodeRED_RDR_Launch_Target_Guard_v10.bat
README_CODERED_XEX_VIEWER_V10.txt
```

## What the viewer reports

For XEX files:

```text
magic
size
SHA1
module flags
PE/data offset
security info offset
optional header count
entry point, when present
image base, when present
optional header IDs and values
interesting module/string hints
```

For PIRS/LIVE/CON packages:

```text
magic
size
SHA1
interesting strings
system-update/dashboard warnings where applicable
```

For manifests:

```text
magic
interesting strings
dashboard/avatar/guide module names
system-update warnings
```

## Read-only rule

This tool does not decrypt or patch XEX files. XEX editing remains risky and should not be part of
the normal RDR multiplayer bootstrap path.

## Launcher guard rule

Launchers should avoid choosing `default.xex` from folders/files that include:

```text
system.manifest
su20076000_00000000
FFFE07DF
AvatarEditor.xex
Guide.AvatarMiniCreator.xex
Xam.Community.xex
Xam.LiveMessenger.xex
Xna_TitleLauncher.xex
dash.firstuse.xex
dashnui.xex
livepack.xex
```

Disc 1 should remain the default RDR GOTY launch target, with Disc 2 available as the
Undead Nightmare / multiplayer fallback.

## Relationship to the current multiplayer blocker

This pass does not claim to solve the `recvfrom` / `WSAGetLastError: 10035` loop. That loop still
points to missing UDP/session discovery response. This pass helps prevent a different regression:
accidentally launching dashboard/system-update XEX content while testing RDR.
