@echo off
cd /d "%~dp0"
rem launcher.py enables Drag & Drop and falls back to the normal GUI if DnD bootstrap fails.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launcher.py
) else (
  python launcher.py
)
if errorlevel 1 pause
