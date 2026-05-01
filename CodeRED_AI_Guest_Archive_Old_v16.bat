@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set ARCHIVE=_archive\ai_guest_v16_%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set ARCHIVE=%ARCHIVE: =0%
mkdir "%ARCHIVE%" >nul 2>nul
for %%F in (
  CodeRED_AI_Guest_Menu_v16.bat
  CodeRED_Start_AI_Guest_v16.bat
  README_CODERED_SPHOST_AI_GUEST_V16.txt
  MANIFEST_CODERED_AI_GUEST_V16.txt
) do if exist "%%F" move "%%F" "%ARCHIVE%\" >nul
if exist tools\codered_ai_guest_controller_v16.py move tools\codered_ai_guest_controller_v16.py "%ARCHIVE%\" >nul
if exist data\codered\rdr_sphost_ai_guest_profile_v16.json move data\codered\rdr_sphost_ai_guest_profile_v16.json "%ARCHIVE%\" >nul
if exist docs\codered\rdr_sphost_ai_guest_v16.md move docs\codered\rdr_sphost_ai_guest_v16.md "%ARCHIVE%\" >nul
if exist logs\CodeRED_Xenia_RDR_Pass_M_v16_AI_Guest_Changelog_2026-05-01.md move logs\CodeRED_Xenia_RDR_Pass_M_v16_AI_Guest_Changelog_2026-05-01.md "%ARCHIVE%\" >nul
if exist logs\codered_ai_guest_v16_validation.txt move logs\codered_ai_guest_v16_validation.txt "%ARCHIVE%\" >nul
echo Archived old AI Guest v16 files to %ARCHIVE%.
pause
