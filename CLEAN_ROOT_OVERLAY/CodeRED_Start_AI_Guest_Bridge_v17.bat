@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist scratch mkdir scratch

echo Stopping stale CodeRED AI Guest Bridge v17 processes, if any...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'codered_ai_guest_bridge_v17.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

echo Starting CodeRED AI Guest Bridge v17 on 127.0.0.1:36017
start "CodeRED AI Guest Bridge v17" /min cmd /c "py -3 tools\codered_ai_guest_bridge_v17.py --host 127.0.0.1 --port 36017 --bootstrap-host http://127.0.0.1:36000 || python tools\codered_ai_guest_bridge_v17.py --host 127.0.0.1 --port 36017 --bootstrap-host http://127.0.0.1:36000"
timeout /t 1 /nobreak >nul
py -3 tools\codered_ai_guest_controller_v17.py bridge-status || python tools\codered_ai_guest_controller_v17.py bridge-status
exit /b 0
