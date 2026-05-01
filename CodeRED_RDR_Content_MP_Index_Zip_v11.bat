@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag content.zip onto this BAT, or run:
  echo   CodeRED_RDR_Content_MP_Index_Zip_v11.bat "D:\Path\content.zip"
  pause
  exit /b 1
)
call CodeRED_RDR_Content_MP_Indexer_v11.bat "%~1"
