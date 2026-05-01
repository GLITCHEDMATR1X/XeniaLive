@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if not exist logs mkdir logs

echo ============================================================
echo  CodeRED XEX / Package Viewer v10
echo ============================================================
echo Root: %CD%
echo.

set "DEFAULT_RDR=%~dp0"
set "SCAN_PATH=%~1"
if "%SCAN_PATH%"=="" set "SCAN_PATH=%DEFAULT_RDR%"

echo Scanning: %SCAN_PATH%
echo.

py -3 tools\codered_xex_viewer.py --path "%SCAN_PATH%" --recursive --json-out logs\codered_xex_audit_v10.json --text-out logs\codered_xex_audit_v10.txt
if errorlevel 1 (
  echo.
  echo Python scan failed. Trying python.exe fallback...
  python tools\codered_xex_viewer.py --path "%SCAN_PATH%" --recursive --json-out logs\codered_xex_audit_v10.json --text-out logs\codered_xex_audit_v10.txt
)

echo.
echo Report:
echo   logs\codered_xex_audit_v10.txt
echo   logs\codered_xex_audit_v10.json
echo.
pause
