@echo off
REM Everyday start: model picker + API + Streamlit. No pip reinstall.
setlocal EnableExtensions
cd /d "%~dp0"

title CareerPilot
echo.
echo  CareerPilot - start
echo  (model picker: pick a number, or wait 10s to keep last model)
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
  echo No .venv yet — running first-time setup...
  echo.
  call "%~dp0setup_careerpilot.bat" %*
  exit /b %ERRORLEVEL%
)

set PYTHONUNBUFFERED=1
"%~dp0.venv\Scripts\python.exe" -m launcher.main %*
set "EC=%ERRORLEVEL%"

echo.
if not "%EC%"=="0" (
  echo Start failed ^(exit %EC%^).
  echo If dependencies are broken, run setup_careerpilot.bat once.
)
echo.
pause
exit /b %EC%
