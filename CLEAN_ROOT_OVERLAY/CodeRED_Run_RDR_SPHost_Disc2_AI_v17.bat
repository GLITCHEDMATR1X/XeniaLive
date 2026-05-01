@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
call CodeRED_Start_RDR_BootstrapHost_v9.bat
call CodeRED_Start_AI_Guest_Bridge_v17.bat
py -3 tools\codered_ai_guest_controller_v17.py spawn --behavior follow_defend || python tools\codered_ai_guest_controller_v17.py spawn --behavior follow_defend
timeout /t 2 /nobreak >nul
py -3 tools\codered_rdr_bootstrap_guard_v9.py launch --mode sp-host --disc disc2 --variant safe --x64-mask 0 --quiet-logging
if errorlevel 1 python tools\codered_rdr_bootstrap_guard_v9.py launch --mode sp-host --disc disc2 --variant safe --x64-mask 0 --quiet-logging
