@echo off
setlocal
cd /d "%~dp0"
set TARGET=%CD%
if exist "..\xenia_canary.exe" set TARGET=%CD%\..
if exist "%CD%\xenia_canary.exe" set TARGET=%CD%

echo [Code RED] Installing profile/save config first-test files to: %TARGET%
for %%F in (xenia-canary.config.toml xenia.config.toml xenia-canary-config.toml) do (
  if exist "%TARGET%\%%F" (
    copy /Y "%TARGET%\%%F" "%TARGET%\%%F.codered_profile_pass5_bak" >nul
  )
  if exist "%CD%\dropin_config_first_test\%%F" (
    copy /Y "%CD%\dropin_config_first_test\%%F" "%TARGET%\%%F" >nul
    echo   installed %%F
  )
)
echo.
echo Done. Close Xenia fully, reopen, then test Free Roam again.
echo If it still hangs, send the new xenia.log.
pause
