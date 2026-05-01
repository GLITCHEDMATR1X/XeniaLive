# CodeRED Xenia RDR Pass L v14 Changelog

Date: 2026-05-01

## Summary

Added a single-player host mode for RDR Disc 1 and Disc 2. The mode advertises a deterministic local System Link session from Xenia while RDR is in single player, publishes it to the CodeRED private host, disables save writes, and reduces console/log overhead for performance testing.

## Changed Files

- `src/xenia/kernel/XLiveAPI.h`
- `src/xenia/kernel/XLiveAPI.cc`
- `src/xenia/kernel/xam/xam_net.cc`
- `src/xenia/kernel/xam/content_manager.cc`
- `tools/codered_rdr_bootstrap_guard_v9.py`
- `tools/codered_collect_v12.py`
- `tools/codered_xenia_netplay_smoke.py`
- `CodeRED_Start_RDR_BootstrapHost_v9.bat`
- `CodeRED_RDR_Bootstrap_Menu_v9.bat`
- `CodeRED_Run_RDR_SPHost_Disc1_Safe_v14.bat`
- `CodeRED_Run_RDR_SPHost_Disc2_Safe_v14.bat`
- `CodeRED_Collect_Small_Logs_v14.bat`
- `docs/codered/rdr_netplay_pass_l_v14_singleplayer_host.md`

## Test Order

1. Rebuild Release with `CodeRED_Build_Xenia_Release_v3.bat`.
2. Run `CodeRED_RDR_Bootstrap_Menu_v9.bat`.
3. Choose `Singleplayer Host - Disc 1 SAFE`.
4. If Disc 1 does not reach the desired path, choose `Singleplayer Host - Disc 2 SAFE`.
5. Run `CodeRED_Collect_Small_Logs_v14.bat`.

## Send Back If It Still Stalls

- `logs/CodeRED_Xenia_RDR_Pass_L_v14_changed_files.zip`
- `logs/codered_rdr_small_logs_v14_*.zip`
- `logs/codered_v14_mp_correlation.txt`
- `logs/CODERED_ACTIVE_NETPLAY_MODE.txt`
- `logs/xenia_codered_v14_sp-host_disc1_safe.log` or Disc 2 equivalent if present
