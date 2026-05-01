@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
py -3 tools\codered_rdr_bootstrap_guard_v9.py collect
if errorlevel 1 python tools\codered_rdr_bootstrap_guard_v9.py collect
if exist tools\codered_collect_v12.py py -3 tools\codered_collect_v12.py
echo.
echo v14 bundle:
echo   logs\codered_rdr_small_logs_v14_*.zip
echo.
pause
