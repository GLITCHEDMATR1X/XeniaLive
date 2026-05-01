@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
py -3 tools\codered_collect_v12.py
if errorlevel 1 python tools\codered_collect_v12.py
echo.
echo v12 report:
echo   logs\codered_v12_mp_correlation.txt
echo   logs\codered_v12_mp_correlation.json
echo.
pause
