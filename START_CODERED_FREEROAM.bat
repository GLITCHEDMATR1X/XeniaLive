@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CodeRED_Start_Freeroam.ps1" %*
endlocal
