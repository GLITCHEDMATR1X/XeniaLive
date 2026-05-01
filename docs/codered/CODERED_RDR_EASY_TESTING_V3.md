# CodeRED RDR Easy Testing v3

This kit fixes the v2 PowerShell/cmd path issue where a root path ending in `\` could be passed with a stray quote and fail `GetFullPath`.

Run `CodeRED_Run_RDR_Local_OneClick_v3.bat` from the patched Xenia Canary root.

Default RDR path:

```text
D:\Games\Red Dead Redemption\
```

The helper writes these config names so different Canary builds can find the settings:

```text
xenia-canary-config.toml
xenia-canary.config.toml
xenia.config.toml
```

It only updates `[Netplay]` and `[CodeRED]` sections and preserves the rest of the config.
