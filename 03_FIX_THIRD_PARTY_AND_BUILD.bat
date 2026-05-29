@echo off
setlocal EnableExtensions

REM Run from the Xenia source root.
cd /d "%~dp0"

echo [Code RED] Checking third_party...
if not exist third_party (
  echo third_party folder missing. Updating submodules recursively...
  git submodule update --init --recursive
) else (
  echo third_party exists.
)

if not exist third_party (
  echo ERROR: third_party is still missing. This is why CMake failed.
  echo Re-clone the repo with: git clone --recursive ^<your-xenia-repo-url^>
  pause
  exit /b 2
)

echo.
echo [Code RED] Configure/build using existing Xenia workflow.
echo If your repo has xb.bat, this is usually the simplest path.
if exist xb.bat (
  call xb.bat build
) else (
  echo xb.bat not found. Running generic CMake configure.
  cmake -S . -B build -G "Visual Studio 17 2022" -A x64
  cmake --build build --config Release --parallel
)

pause
