@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo  CodeRED Xenia Canary - RDR GOTY Bootstrap v17.1
echo ============================================================
echo Menu stays open. Game/host/AI controls launch in separate windows.
echo Default focus: Singleplayer Host Disc 1 first. Saves are disabled in SP Host.
echo AI Guest v17 uses a local script-control bridge on 127.0.0.1:36017.
echo.
echo 1. Start BootstrapHost v14 only  ^(separate/minimized^)
echo 2. Singleplayer Host - Disc 1 SAFE  ^(separate window^)
echo 3. Singleplayer Host - Disc 2 SAFE  ^(separate window^)
echo 4. Singleplayer Host - Disc 1 + AI Bridge v17  ^(recommended^)
echo 5. Singleplayer Host - Disc 2 + AI Bridge v17
echo 6. Private Bootstrap - Disc 1 SAFE  ^(separate window^)
echo 7. Private Bootstrap - Disc 2 SAFE  ^(separate window^)
echo 8. True LAN - Disc 1 SAFE  ^(separate window^)
echo 9. True LAN - Disc 2 SAFE  ^(separate window^)
echo 10. Offline baseline - Disc 1 SAFE  ^(separate window^)
echo 11. Profile/sign-in check
echo 12. Collect small logs/correlation v14 to send back
echo 13. Open AI Guest Control Menu v17  ^(separate window^)
echo 14. Start AI Guest Bridge v17  ^(separate/minimized^)
echo 15. Spawn AI Guest Bodyguard now
echo 16. AI Guest Status
echo 17. Exit
echo.
set /p CHOICE=Choose: 

if "%CHOICE%"=="1" start "CodeRED RDR BootstrapHost v14" /min cmd /c "CodeRED_Start_RDR_BootstrapHost_v9.bat"
if "%CHOICE%"=="2" start "CodeRED RDR SPHost Disc1 SAFE v14" cmd /k "CodeRED_Run_RDR_SPHost_Disc1_Safe_v14.bat"
if "%CHOICE%"=="3" start "CodeRED RDR SPHost Disc2 SAFE v14" cmd /k "CodeRED_Run_RDR_SPHost_Disc2_Safe_v14.bat"
if "%CHOICE%"=="4" start "CodeRED RDR SPHost Disc1 + AI Bridge v17" cmd /k "CodeRED_Run_RDR_SPHost_Disc1_AI_v17.bat"
if "%CHOICE%"=="5" start "CodeRED RDR SPHost Disc2 + AI Bridge v17" cmd /k "CodeRED_Run_RDR_SPHost_Disc2_AI_v17.bat"
if "%CHOICE%"=="6" start "CodeRED RDR PrivateBootstrap Disc1 SAFE v9" cmd /k "CodeRED_Run_RDR_PrivateBootstrap_Disc1_Safe_v9.bat"
if "%CHOICE%"=="7" start "CodeRED RDR PrivateBootstrap Disc2 SAFE v9" cmd /k "CodeRED_Run_RDR_PrivateBootstrap_Disc2_Safe_v9.bat"
if "%CHOICE%"=="8" start "CodeRED RDR LAN Disc1 SAFE v9" cmd /k "CodeRED_Run_RDR_LAN_Disc1_Safe_v9.bat"
if "%CHOICE%"=="9" start "CodeRED RDR LAN Disc2 SAFE v9" cmd /k "CodeRED_Run_RDR_LAN_Disc2_Safe_v9.bat"
if "%CHOICE%"=="10" start "CodeRED RDR Offline Disc1 SAFE v9" cmd /k "CodeRED_Run_RDR_Offline_Disc1_Safe_v9.bat"
if "%CHOICE%"=="11" call CodeRED_Profile_Check_v9.bat
if "%CHOICE%"=="12" call CodeRED_Collect_Small_Logs_v14.bat
if "%CHOICE%"=="13" start "CodeRED AI Guest Control Menu v17" cmd /k "CodeRED_AI_Guest_Menu_v17.bat"
if "%CHOICE%"=="14" start "CodeRED AI Guest Bridge v17" /min cmd /c "CodeRED_Start_AI_Guest_Bridge_v17.bat"
if "%CHOICE%"=="15" call CodeRED_Start_AI_Guest_v17.bat
if "%CHOICE%"=="16" py -3 tools\codered_ai_guest_controller_v17.py status || python tools\codered_ai_guest_controller_v17.py status
if "%CHOICE%"=="17" exit /b 0

echo.
echo If you launched a game/AI menu, it opened in a separate CMD window.
echo This main menu will stay here for more commands.
pause
goto :menu
