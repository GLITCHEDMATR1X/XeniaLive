@echo off
setlocal EnableExtensions

REM Usage:
REM   01_INSTALL_CONFIG_FIXES_TO_RELEASE_FIXED.bat
REM or:
REM   01_INSTALL_CONFIG_FIXES_TO_RELEASE_FIXED.bat "D:\Games\Red Dead Redemption\xenia-canary-6de80df\build\bin\Windows\Release"

set XUID=E03000004156EF97

if "%~1"=="" (
  set TARGET=%CD%
) else (
  set TARGET=%~1
)

echo [Code RED] Applying RDR/Xenia profile config fixes...
echo Target: %TARGET%

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\apply_xenia_profile_config_fixes.ps1" -Root "%TARGET%" -Xuid "%XUID%"
if errorlevel 1 (
  echo.
  echo ERROR: Config patch failed. Check the target folder path.
  pause
  exit /b 1
)

echo.
echo Done. Fully close Xenia before testing.
pause
