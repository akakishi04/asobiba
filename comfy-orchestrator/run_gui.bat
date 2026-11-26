@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

rem Prefer the same interpreter as the documented "python -m" launch.
set "PY_CMD=python"
%PY_CMD% -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if not errorlevel 1 goto check_preview
set "PY_CMD=py -3"
%PY_CMD% -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 goto failed

:check_preview
%PY_CMD% -c "import sys; print('GUI Python:', sys.executable)"
rem Check the binding without starting libVLC. Native VLC is still optional.
%PY_CMD% -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('vlc') else 1)" >nul 2>nul
if not errorlevel 1 goto launch
echo.
echo Embedded video preview requires python-vlc in this Python environment.
choice /C YN /N /M "Install python-vlc now? [Y/N] "
if not "%errorlevel%"=="1" goto launch
%PY_CMD% -m pip install "python-vlc>=3.0.21203,<4"
if errorlevel 1 echo Installation failed. Generation and external playback remain available.

:launch
%PY_CMD% -m comfy_orchestrator.gui
if not errorlevel 1 exit /b 0

:failed
echo.
echo GUI startup failed. Check that Python 3.11+ with tkinter is installed.
pause
exit /b 1
