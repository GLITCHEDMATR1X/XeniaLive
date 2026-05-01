@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
call CodeRED_Start_RDR_BootstrapHost_v9.bat
timeout /t 2 /nobreak >nul
py -3 tools\codered_rdr_bootstrap_guard_v9.py launch --mode sp-host --disc disc1 --variant safe --x64-mask 0 --quiet-logging
if errorlevel 1 python tools\codered_rdr_bootstrap_guard_v9.py launch --mode sp-host --disc disc1 --variant safe --x64-mask 0 --quiet-logging
