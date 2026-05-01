@echo off
setlocal
cd /d "%~dp0\.."
python tools\codered_rdr_private_host.py --host 0.0.0.0 --port 36000 --verbose
