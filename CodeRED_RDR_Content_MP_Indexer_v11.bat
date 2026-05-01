@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set "INPUT=%~1"
if "%INPUT%"=="" set "INPUT=%~dp0content.zip"
echo ============================================================
echo  CodeRED RDR Content Multiplayer Indexer v11
echo ============================================================
echo Root:  %CD%
echo Input: %INPUT%
echo.
py -3 tools\codered_rdr_content_mp_indexer.py --input "%INPUT%" --out logs
if errorlevel 1 (
  echo.
  echo [ERROR] Indexer failed. Try dragging content.zip onto this BAT.
  pause
  exit /b 1
)
echo.
echo Reports:
echo   logs\codered_rdr_content_mp_index_v11.txt
echo   logs\codered_rdr_content_mp_index_v11.json
echo.
pause
