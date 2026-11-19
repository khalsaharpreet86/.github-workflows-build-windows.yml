@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (
  echo.
  echo BUILD FAILED. Read the error above.
) else (
  echo.
  echo BUILD COMPLETED. Check the dist folder.
)
pause
endlocal
