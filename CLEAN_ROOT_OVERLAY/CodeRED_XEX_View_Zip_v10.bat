@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs

echo ============================================================
echo  CodeRED XEX / Package Viewer v10 - ZIP scan
echo ============================================================
echo.

set "ZIP_PATH=%~1"
if "%ZIP_PATH%"=="" (
  echo Drag a .zip onto this BAT, or run:
  echo   CodeRED_XEX_View_Zip_v10.bat "D:\path\file.zip"
  echo.
  pause
  exit /b 1
)

py -3 tools\codered_xex_viewer.py --path "%ZIP_PATH%" --json-out logs\codered_xex_zip_audit_v10.json --text-out logs\codered_xex_zip_audit_v10.txt
if errorlevel 1 python tools\codered_xex_viewer.py --path "%ZIP_PATH%" --json-out logs\codered_xex_zip_audit_v10.json --text-out logs\codered_xex_zip_audit_v10.txt

echo.
echo Report:
echo   logs\codered_xex_zip_audit_v10.txt
echo   logs\codered_xex_zip_audit_v10.json
echo.
pause
