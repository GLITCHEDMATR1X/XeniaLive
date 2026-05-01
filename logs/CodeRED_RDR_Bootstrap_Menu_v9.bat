@echo off
setlocal
cd /d "%~dp0"
:menu
cls
echo ============================================================
echo  CodeRED Xenia Canary - RDR GOTY Bootstrap v9
echo ============================================================
echo Default focus: Disc 1. Use Disc 2 when GOTY multiplayer/Undead fallback is needed.
echo.
echo 1. Start BootstrapHost v9 only
echo 2. Private Bootstrap - Disc 1 SAFE  ^(default^)
echo 3. Private Bootstrap - Disc 2 SAFE  ^(fallback^)
echo 4. True LAN - Disc 1 SAFE
echo 5. True LAN - Disc 2 SAFE
echo 6. Offline baseline - Disc 1 SAFE
echo 7. Profile/sign-in check
echo 8. Collect small logs/correlation v12 to send back
echo 9. Exit
echo.
set /p CHOICE=Choose: 
if "%CHOICE%"=="1" call CodeRED_Start_RDR_BootstrapHost_v9.bat
if "%CHOICE%"=="2" call CodeRED_Run_RDR_PrivateBootstrap_Disc1_Safe_v9.bat
if "%CHOICE%"=="3" call CodeRED_Run_RDR_PrivateBootstrap_Disc2_Safe_v9.bat
if "%CHOICE%"=="4" call CodeRED_Run_RDR_LAN_Disc1_Safe_v9.bat
if "%CHOICE%"=="5" call CodeRED_Run_RDR_LAN_Disc2_Safe_v9.bat
if "%CHOICE%"=="6" call CodeRED_Run_RDR_Offline_Disc1_Safe_v9.bat
if "%CHOICE%"=="7" call CodeRED_Profile_Check_v9.bat
if "%CHOICE%"=="8" call CodeRED_Collect_Small_Logs_v12.bat
if "%CHOICE%"=="9" exit /b 0
pause
goto :menu
