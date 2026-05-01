@echo off
setlocal
cd /d "%~dp0"
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4.*192\.168" /C:"IPv4.*10\." /C:"IPv4.*172\."') do (
  set IP=%%A
  goto :gotip
)
:gotip
if "%IP%"=="" set IP=127.0.0.1
set IP=%IP: =%
echo Stopping stale CodeRED RDR BootstrapHost processes, if any
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'codered_rdr_bootstrap_host_v9.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul
echo Starting CodeRED RDR BootstrapHost v14 for %IP%:3074
start "CodeRED RDR BootstrapHost v14" /min cmd /c "py -3 tools\codered_rdr_bootstrap_host_v9.py --host 127.0.0.1 --port 36000 --target-ip %IP% --system-link-port 3074 --udp-port 3074 --beacon-interval 0 --trace-every 240 --log-file logs\codered_udp_bootstrap_v14.log || python tools\codered_rdr_bootstrap_host_v9.py --host 127.0.0.1 --port 36000 --target-ip %IP% --system-link-port 3074 --udp-port 3074 --beacon-interval 0 --trace-every 240 --log-file logs\codered_udp_bootstrap_v14.log"
