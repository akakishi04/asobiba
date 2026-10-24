@echo off
setlocal
cd /d "%~dp0"

rem Force UTF-8 for Python subprocesses. SeedVR2 prints Unicode/emoji during CLI startup.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ========================================
echo  Video Tool AI Environment Setup
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 ai_setup.py
) else (
  python ai_setup.py
)

if errorlevel 1 (
  echo.
  echo AI setup failed. Review the messages above.
  pause
  exit /b 1
)

echo.
echo AI setup completed.
pause
