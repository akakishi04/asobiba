@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app_ai.py
) else (
  python app_ai.py
)
if errorlevel 1 pause
