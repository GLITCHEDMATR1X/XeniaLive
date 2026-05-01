@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist scratch mkdir scratch
call CodeRED_Start_AI_Guest_Bridge_v17.bat
py -3 tools\codered_ai_guest_controller_v17.py spawn --behavior follow_defend || python tools\codered_ai_guest_controller_v17.py spawn --behavior follow_defend
pause
