@echo off
setlocal
cd /d "%~dp0"
set TARGET=%CD%
if exist "..\xenia_canary.exe" set TARGET=%CD%\..
if exist "%CD%\xenia_canary.exe" set TARGET=%CD%

echo [Code RED] Restoring profile pass 5 config backups from: %TARGET%
for %%F in (xenia-canary.config.toml xenia.config.toml xenia-canary-config.toml) do (
  if exist "%TARGET%\%%F.codered_profile_pass5_bak" (
    copy /Y "%TARGET%\%%F.codered_profile_pass5_bak" "%TARGET%\%%F" >nul
    echo   restored %%F
  )
)
pause
