@echo off
setlocal
cd /d "%~dp0"
call CodeRED_Start_RDR_BootstrapHost_v9.bat
ping 127.0.0.1 -n 3 >nul
py -3 tools\codered_rdr_bootstrap_guard_v9.py launch --mode private --disc disc1 --variant safe --x64-mask 0
