@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_rdr_bootstrap_guard_v9.py launch --mode offline --disc disc1 --variant safe --x64-mask 0
