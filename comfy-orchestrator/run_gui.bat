@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m comfy_orchestrator.gui
) else (
  python -m comfy_orchestrator.gui
)
if errorlevel 1 (
  echo.
  echo GUI startup failed. Check that Python 3.11+ with tkinter is installed.
  pause
)
