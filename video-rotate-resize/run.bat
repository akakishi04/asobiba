@echo off
setlocal
cd /d "%~dp0"
rem Force UTF-8 for Python subprocesses. SeedVR2 prints Unicode/emoji even during --help.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
rem launcher.py enables Drag & Drop and falls back to the normal GUI if DnD bootstrap fails.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launcher.py
) else (
  python launcher.py
)
if errorlevel 1 pause
