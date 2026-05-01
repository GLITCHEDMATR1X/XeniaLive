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
echo Starting CodeRED RDR BootstrapHost v12 for %IP%:3074
start "CodeRED RDR BootstrapHost v12" cmd /k py -3 tools\codered_rdr_bootstrap_host_v9.py --host 127.0.0.1 --port 36000 --target-ip %IP% --system-link-port 3074 --udp-port 3074 --log-file logs\codered_udp_bootstrap_v12.log --verbose
