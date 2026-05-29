Code RED Xenia profile consistency Pass 6B

This fixes the ParserError in the old 01_INSTALL_CONFIG_FIXES_TO_RELEASE.bat.
The old BAT used a long inline PowerShell command with broken quote escaping.

Use this instead:

  01_INSTALL_CONFIG_FIXES_TO_RELEASE_FIXED.bat "D:\Games\Red Dead Redemption\xenia-canary-6de80df\build\bin\Windows\Release"

Or open Command Prompt in the folder beside xenia_canary.exe and run:

  path\to\01_INSTALL_CONFIG_FIXES_TO_RELEASE_FIXED.bat

It patches these config keys in any present Xenia config files:

  license_mask = -1
  netplay_disable_saves = false
  disable_saves = false
  net_logging = true
  flush_log = true
  logged_profile_slot_0_xuid = "E03000004156EF97"

Backups are written as *.codered_pass6b_bak_<timestamp>.
