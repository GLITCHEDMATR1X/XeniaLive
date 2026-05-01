CodeRED Xenia RDR GOTY Bootstrap v9
===================================

Default target is Disc 1. Disc 2 is still included as the fallback for GOTY multiplayer/Undead paths.

Install:
1. Extract this zip over:
   D:\Games\Red Dead Redemption\xenia-canary-6de80df\
2. Allow overwrite.
3. If using the source patch, rebuild Xenia after extraction.
4. Run:
   CodeRED_RDR_Bootstrap_Menu_v9.bat

Recommended first test:
2. Private Bootstrap - Disc 1 SAFE

Fallback:
3. Private Bootstrap - Disc 2 SAFE

True LAN comparison:
4. True LAN - Disc 1 SAFE
5. True LAN - Disc 2 SAFE

Important proof:
- LAN must show mode=1 in the Xenia log.
- Private Bootstrap must show mode=2.
- Guest-visible XNADDR port should show guest_port=3074.

If profile/sign-in does not prompt:
Run option 7, then send logs\codered_profile_check_v9.txt.

If it stalls or crashes:
Run option 8 and send the generated logs\codered_rdr_small_logs_v9_*.zip.
