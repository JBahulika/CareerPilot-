@echo off
REM First-time (or repair) setup: create .venv, install deps, copy .env, then start.
setlocal EnableExtensions
cd /d "%~dp0"

title CareerPilot setup
echo.
echo  CareerPilot - FIRST-TIME SETUP
echo  Creates .venv, installs dependencies, then starts the app.
echo  After this succeeds once, use start_careerpilot.bat day-to-day.
echo.

set "BASEPY="

if exist "%~dp0.venv\Scripts\python.exe" (
  set "BASEPY=%~dp0.venv\Scripts\python.exe"
  goto :run
)
if exist "%~dp0..\CareerPilot--main\cenv\Scripts\python.exe" (
  set "BASEPY=%~dp0..\CareerPilot--main\cenv\Scripts\python.exe"
  goto :run
)

where py >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%I in ('py -3.10 -c "import sys; print(sys.executable)" 2^>nul') do set "BASEPY=%%I"
  if defined BASEPY goto :run
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "BASEPY=%%I"
  if defined BASEPY goto :run
)

where python >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "BASEPY=%%I"
  if defined BASEPY goto :run
)

echo ERROR: Python 3.10+ is required once to set up CareerPilot.
echo.
echo 1^) Install Python from https://www.python.org/downloads/
echo    (check "Add python.exe to PATH")
echo 2^) Install Ollama from https://ollama.com
echo 3^) Double-click this file again.
echo.
echo Opening download pages...
start "" "https://www.python.org/downloads/"
start "" "https://ollama.com"
echo.
pause
exit /b 1

:run
echo Bootstrap Python: %BASEPY%
echo.
set PYTHONUNBUFFERED=1
"%BASEPY%" -m launcher.bootstrap %*
set "EC=%ERRORLEVEL%"

echo.
if not "%EC%"=="0" (
  echo Setup failed ^(exit %EC%^).
  echo Try: .venv\Scripts\python -m pip install -r requirements.txt
)
echo.
pause
exit /b %EC%
