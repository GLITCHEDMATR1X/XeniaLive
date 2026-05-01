@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist scratch mkdir scratch
call CodeRED_Start_RDR_BootstrapHost_v9.bat
timeout /t 1 /nobreak >nul
py -3 tools\codered_ai_guest_controller_v16.py spawn --behavior follow_defend || python tools\codered_ai_guest_controller_v16.py spawn --behavior follow_defend
pause
