@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist scratch mkdir scratch

:menu
cls
echo ============================================================
echo  CodeRED SPHost AI Guest Control v17
echo ============================================================
echo Local script-controlled AI guest bridge. Does not touch real Xbox Live.
echo Start the bridge first, then spawn or command the AI while SPHost runs.
echo.
echo 1. Start AI Guest Bridge v17
echo 2. Start BootstrapHost v14 only
echo 3. Spawn AI Guest: Bodyguard / Follow-Defend
echo 4. Command AI: Follow player
echo 5. Command AI: Guard position
echo 6. Command AI: Attack hostiles
echo 7. Command AI: Defend player
echo 8. Command AI: Idle / Hold fire
echo 9. Command AI: Regroup / Warp requested
echo 10. Command AI: Mount request
echo 11. Command AI: Dismount request
echo 12. Dismiss AI Guest
echo 13. Status
echo 14. Bridge health
echo 15. Open AI state JSON
echo 16. Open AI action plan JSON
echo 17. Back to main menu
echo.
set /p AICHOICE=Choose AI command: 
if "%AICHOICE%"=="1" call CodeRED_Start_AI_Guest_Bridge_v17.bat
if "%AICHOICE%"=="2" call CodeRED_Start_RDR_BootstrapHost_v9.bat
if "%AICHOICE%"=="3" py -3 tools\codered_ai_guest_controller_v17.py spawn --behavior follow_defend || python tools\codered_ai_guest_controller_v17.py spawn --behavior follow_defend
if "%AICHOICE%"=="4" py -3 tools\codered_ai_guest_controller_v17.py command follow || python tools\codered_ai_guest_controller_v17.py command follow
if "%AICHOICE%"=="5" py -3 tools\codered_ai_guest_controller_v17.py command guard || python tools\codered_ai_guest_controller_v17.py command guard
if "%AICHOICE%"=="6" py -3 tools\codered_ai_guest_controller_v17.py command attack || python tools\codered_ai_guest_controller_v17.py command attack
if "%AICHOICE%"=="7" py -3 tools\codered_ai_guest_controller_v17.py command defend || python tools\codered_ai_guest_controller_v17.py command defend
if "%AICHOICE%"=="8" py -3 tools\codered_ai_guest_controller_v17.py command idle || python tools\codered_ai_guest_controller_v17.py command idle
if "%AICHOICE%"=="9" py -3 tools\codered_ai_guest_controller_v17.py command regroup || python tools\codered_ai_guest_controller_v17.py command regroup
if "%AICHOICE%"=="10" py -3 tools\codered_ai_guest_controller_v17.py command mount || python tools\codered_ai_guest_controller_v17.py command mount
if "%AICHOICE%"=="11" py -3 tools\codered_ai_guest_controller_v17.py command dismount || python tools\codered_ai_guest_controller_v17.py command dismount
if "%AICHOICE%"=="12" py -3 tools\codered_ai_guest_controller_v17.py dismiss || python tools\codered_ai_guest_controller_v17.py dismiss
if "%AICHOICE%"=="13" py -3 tools\codered_ai_guest_controller_v17.py status || python tools\codered_ai_guest_controller_v17.py status
if "%AICHOICE%"=="14" py -3 tools\codered_ai_guest_controller_v17.py bridge-status || python tools\codered_ai_guest_controller_v17.py bridge-status
if "%AICHOICE%"=="15" (
  if exist scratch\codered_ai_guest_state.json notepad scratch\codered_ai_guest_state.json
  if not exist scratch\codered_ai_guest_state.json echo No AI state yet. Spawn the AI first.
)
if "%AICHOICE%"=="16" (
  if exist scratch\codered_ai_guest_action_plan_v17.json notepad scratch\codered_ai_guest_action_plan_v17.json
  if not exist scratch\codered_ai_guest_action_plan_v17.json echo No AI action plan yet. Spawn or command the AI first.
)
if "%AICHOICE%"=="17" exit /b 0
pause
goto :menu
