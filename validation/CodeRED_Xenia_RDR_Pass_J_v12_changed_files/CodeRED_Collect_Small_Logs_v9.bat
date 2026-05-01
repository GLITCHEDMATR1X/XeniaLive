@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_rdr_bootstrap_guard_v9.py collect
py -3 tools\codered_collect_v12.py
pause
