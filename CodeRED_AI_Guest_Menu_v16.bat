@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist scratch mkdir scratch

:menu
cls
echo ============================================================
echo  CodeRED SPHost AI Guest Control v16
echo ============================================================
echo This is a script-controlled AI guest state bridge for SPHost.
echo Start SPHost first or use option 1 to start the bootstrap host.
echo.
echo 1. Start BootstrapHost v14 only
echo 2. Spawn AI Guest: Bodyguard / Follow-Defend
echo 3. Command AI: Follow player
echo 4. Command AI: Guard position
echo 5. Command AI: Attack hostiles
echo 6. Command AI: Idle / Hold fire
echo 7. Command AI: Regroup / Warp requested
echo 8. Command AI: Dismiss
echo 9. Status
echo 10. Open AI state JSON
echo 11. Back to main menu
echo.
set /p AICHOICE=Choose AI command: 
if "%AICHOICE%"=="1" call CodeRED_Start_RDR_BootstrapHost_v9.bat
if "%AICHOICE%"=="2" py -3 tools\codered_ai_guest_controller_v16.py spawn --behavior follow_defend || python tools\codered_ai_guest_controller_v16.py spawn --behavior follow_defend
if "%AICHOICE%"=="3" py -3 tools\codered_ai_guest_controller_v16.py command follow || python tools\codered_ai_guest_controller_v16.py command follow
if "%AICHOICE%"=="4" py -3 tools\codered_ai_guest_controller_v16.py command guard || python tools\codered_ai_guest_controller_v16.py command guard
if "%AICHOICE%"=="5" py -3 tools\codered_ai_guest_controller_v16.py command attack || python tools\codered_ai_guest_controller_v16.py command attack
if "%AICHOICE%"=="6" py -3 tools\codered_ai_guest_controller_v16.py command idle || python tools\codered_ai_guest_controller_v16.py command idle
if "%AICHOICE%"=="7" py -3 tools\codered_ai_guest_controller_v16.py command regroup || python tools\codered_ai_guest_controller_v16.py command regroup
if "%AICHOICE%"=="8" py -3 tools\codered_ai_guest_controller_v16.py dismiss || python tools\codered_ai_guest_controller_v16.py dismiss
if "%AICHOICE%"=="9" py -3 tools\codered_ai_guest_controller_v16.py status || python tools\codered_ai_guest_controller_v16.py status
if "%AICHOICE%"=="10" (
  if exist scratch\codered_ai_guest_state.json notepad scratch\codered_ai_guest_state.json
  if not exist scratch\codered_ai_guest_state.json echo No AI state yet. Spawn the AI first.
)
if "%AICHOICE%"=="11" exit /b 0
pause
goto :menu
