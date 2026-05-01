@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  CodeRED Xenia Canary Safe Root Cleanup v15
echo ============================================================
echo This removes old loose root-level CodeRED backups and obsolete
 echo helper versions. It does NOT delete source, tools, patches, games,
echo saves, or the current v14/v9 launcher set.
echo.
set /p CONFIRM=Type CLEAN to continue: 
if /I not "%CONFIRM%"=="CLEAN" (
  echo Cancelled.
  exit /b 0
)

if not exist logs mkdir logs
set "REPORT=logs\codered_safe_root_cleanup_v15.txt"
echo CodeRED safe root cleanup v15 > "%REPORT%"
echo Started: %date% %time% >> "%REPORT%"
echo. >> "%REPORT%"

for %%F in (
  "xenia.config.toml.codered_*_bak_*"
  "xenia-canary.config.toml.codered_*_bak_*"
  "xenia-canary-config.toml.codered_*_bak_*"
  "CodeRED_Apply_RelaunchGuard_v7.bat"
  "CodeRED_Build_RDRMP_World_Manifest_v8.bat"
  "CodeRED_Build_Xenia_RelaunchGuard_v7.bat"
  "CodeRED_Collect_Small_Logs_v6.bat"
  "CodeRED_Collect_Small_Logs_v9.bat"
  "CodeRED_Collect_Small_Logs_v12.bat"
  "CodeRED_Easy_RDR_Netplay_Menu.bat"
  "CodeRED_Launch_RDR.bat"
  "CodeRED_RDRMP_World_Salvage_Menu_v8.bat"
  "CodeRED_RDR_Multiplayer_CrashGuard_Menu_v6.bat"
  "CodeRED_Run_RDR_LAN_Disc2_Safe_v6.bat"
  "CodeRED_Run_RDR_LAN_Disc2_Safe_v8.bat"
  "CodeRED_Run_RDR_Offline_Disc2_Safe_v6.bat"
  "CodeRED_Run_RDR_PrivateHost_Disc1_Safe_v6.bat"
  "CodeRED_Run_RDR_PrivateHost_Disc2_Bare_v6.bat"
  "CodeRED_Run_RDR_PrivateHost_Disc2_Safe_v6.bat"
  "CodeRED_Run_RDR_PrivateWorldHost_Disc2_Safe_v8.bat"
  "CodeRED_Start_Private_Host.bat"
  "CodeRED_Start_Private_Host_v6.bat"
  "CodeRED_Start_RDR_WorldHost_v8.bat"
  "CodeRED_Write_Netplay_Config_v3.bat"
  "README_CODERED_RDRMP_WORLD_SALVAGE_V8.txt"
  "README_CODERED_RDR_CRASH_GUARD_V5.txt"
  "README_CODERED_RDR_CRASH_GUARD_V6.txt"
  "README_CODERED_RDR_EASY_TEST.txt"
  "README_CODERED_RDR_EASY_TEST_V3.txt"
  "README_CODERED_RDR_RELAUNCH_GUARD_V7.txt"
  "README_CodeRED_Easy_RDR_Netplay_v2.txt"
  "zng_test.obj"
) do (
  for %%G in (%%~F) do (
    if exist "%%~G" (
      echo Deleting %%~G
      echo deleted: %%~G >> "%REPORT%"
      del /f /q "%%~G" >nul 2>nul
    )
  )
)

if exist "logs\CODERED_SEND_THESE_V12" (
  echo Removing stale logs\CODERED_SEND_THESE_V12
  echo removed folder: logs\CODERED_SEND_THESE_V12 >> "%REPORT%"
  rmdir /s /q "logs\CODERED_SEND_THESE_V12"
)
if exist "logs\CODERED_SEND_THESE_V14" (
  echo Removing stale logs\CODERED_SEND_THESE_V14
  echo removed folder: logs\CODERED_SEND_THESE_V14 >> "%REPORT%"
  rmdir /s /q "logs\CODERED_SEND_THESE_V14"
)

echo. >> "%REPORT%"
echo Finished: %date% %time% >> "%REPORT%"
echo.
echo Safe root cleanup complete.
echo Report: %CD%\%REPORT%
echo.
echo Optional manual space cleanup only after backup:
echo   build\obj, build\CMakeFiles, cache, cache0, cache1, cache_host
pause
