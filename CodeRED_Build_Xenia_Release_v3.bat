@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=logs\codered_xenia_build_release_v3.log"
set "CMAKE_EXE=cmake"
where cmake >nul 2>nul
if errorlevel 1 (
  if exist "C:\Program Files\CMake\bin\cmake.exe" set "CMAKE_EXE=C:\Program Files\CMake\bin\cmake.exe"
  if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" set "CMAKE_EXE=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
  if exist "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" set "CMAKE_EXE=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)

echo ============================================================
echo  CodeRED Xenia Canary Release Build v3
echo ============================================================
echo Root: %CD%
echo Log:  %CD%\%LOG%
echo CMake: %CMAKE_EXE%
echo.

echo [%date% %time%] Build started > "%LOG%"
"%CMAKE_EXE%" --preset vs >>"%LOG%" 2>>&1
if errorlevel 1 (
  echo CMake configure failed. Open:
  echo   %CD%\%LOG%
  exit /b 1
)

"%CMAKE_EXE%" --build --preset vs-release >>"%LOG%" 2>>&1
if errorlevel 1 (
  echo CMake build failed. Open:
  echo   %CD%\%LOG%
  exit /b 1
)

if exist "build\bin\Windows\Release\xenia_canary.exe" (
  echo Build finished: %CD%\build\bin\Windows\Release\xenia_canary.exe
  echo [%date% %time%] Build finished >> "%LOG%"
  exit /b 0
)

echo Build command completed but xenia_canary.exe was not found.
echo [%date% %time%] Build completed without output exe >> "%LOG%"
exit /b 2
