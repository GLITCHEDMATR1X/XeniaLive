@echo off
setlocal EnableExtensions

REM Put this folder inside your Xenia source root, or pass the source root as argument.
if "%~1"=="" (
  set ROOT=%CD%
) else (
  set ROOT=%~1
)

echo [Code RED] Applying XAM source patch in: %ROOT%
python "%~dp0tools\patch_xenia_xam_identity_for_rdr.py" "%ROOT%"

echo.
echo If markers were all OK, rebuild Xenia Canary.
pause
