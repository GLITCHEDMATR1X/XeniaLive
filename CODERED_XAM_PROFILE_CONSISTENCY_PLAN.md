
# Code RED XAM profile consistency plan

This release already contains Code RED profile/netplay hooks, but the log shows one important mismatch:

```text
logged_profile_slot_0_xuid = "E03000004156EF97"
XamUserGetXUID(...) sometimes returns 0000000000000000
```

That means the local profile is loaded, but at least one XAM query path can still return a zero/anonymous/online XUID.
For Red Dead Redemption Free Roam, that can leave the game in the loading/session stage even after menu auth is bypassed.

The next source rebuild should make the local Code RED slot-0 profile consistent across these XAM calls:

```text
XamUserGetXUID
XamUserGetSigninInfo
XamUserGetSigninState
XamUserGetSubscriptionType
XamUserGetMembershipTier
XamUserIsOnlineEnabled
XamUserGetOnlineXUIDFromOfflineXUID
XamUserGetUserFlagsFromXUID
XamUserReadProfileSettings
```

Intended local/offline-only behavior:

```text
slot 0 local XUID      = E03000004156EF97
slot 0 online XUID     = E03000004156EF97
live enabled           = true/local-emulated
subscription/membership = Gold-equivalent
online domain fallback = xbox.com
```

Do not connect to real Xbox Live. This is for local Xenia/Code RED profile consistency only.
