@echo off
REM Build CareerPilot.exe (optional). Place the exe in the repo root for users.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run start_careerpilot.bat once first so .venv exists.
  pause
  exit /b 1
)

.venv\Scripts\python -m pip install -q pyinstaller
.venv\Scripts\pyinstaller --noconfirm --clean ^
  --name CareerPilot ^
  --onefile ^
  --console ^
  --paths . ^
  launcher\exe_entry.py

if exist "dist\CareerPilot.exe" (
  copy /Y "dist\CareerPilot.exe" "CareerPilot.exe" >nul
  echo.
  echo Built: CareerPilot.exe ^(in project root^)
  echo Ship this next to the repo files ^(or in a Release zip with the full project^).
  echo Users still need Python + Ollama installed; first run of the exe/setup creates .venv and installs deps.
echo Day-to-day: start_careerpilot.bat ^(or the exe after setup^).
) else (
  echo Build failed.
  exit /b 1
)
pause
