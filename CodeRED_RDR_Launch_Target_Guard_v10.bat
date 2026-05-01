@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs

echo ============================================================
echo  CodeRED RDR Launch Target Guard v10
echo ============================================================
echo.
echo This checks for risky default.xex files and dashboard/system-update
echo content that can confuse RDR launch scripts.
echo.

set "RDR_PATH=%~dp0"
if not "%~1"=="" set "RDR_PATH=%~1"

echo RDR path: %RDR_PATH%
echo.

py -3 tools\codered_xex_viewer.py --path "%RDR_PATH%" --recursive --strict-launch-guard --json-out logs\codered_launch_target_guard_v10.json --text-out logs\codered_launch_target_guard_v10.txt
set "ERR=%ERRORLEVEL%"
if "%ERR%"=="0" goto ok
if "%ERR%"=="3" goto warning

python tools\codered_xex_viewer.py --path "%RDR_PATH%" --recursive --strict-launch-guard --json-out logs\codered_launch_target_guard_v10.json --text-out logs\codered_launch_target_guard_v10.txt
set "ERR=%ERRORLEVEL%"
if "%ERR%"=="0" goto ok
if "%ERR%"=="3" goto warning

echo.
echo Scan failed. Check Python installation and path.
pause
exit /b %ERR%

:warning
echo.
echo High-risk launch-target content was found.
echo This is not automatically bad, but launchers should avoid those folders.
echo Check: logs\codered_launch_target_guard_v10.txt
echo.
pause
exit /b 3

:ok
echo.
echo No high-risk default.xex / system-update launch issues found.
echo Check: logs\codered_launch_target_guard_v10.txt
echo.
pause
exit /b 0
