@echo off
setlocal
cd /d "%~dp0"
set LOG=%CD%\..\xenia.log
if exist "%CD%\xenia.log" set LOG=%CD%\xenia.log
python tools\scan_xenia_profile_log.py "%LOG%"
pause
