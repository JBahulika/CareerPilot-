@echo off
REM Sync remote_ui → Android assets and build a debug APK (requires Android SDK / JDK 17).
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%~dp0"
set "WWW=%ROOT%mobile_android\app\src\main\assets\www"
set "UI=%ROOT%remote_ui"

echo.
echo  CareerPilot Remote — sync UI + build debug APK
echo.

if not exist "%UI%\index.html" (
  echo ERROR: remote_ui\index.html missing
  exit /b 1
)

if exist "%WWW%" rmdir /s /q "%WWW%"
mkdir "%WWW%"
copy /Y "%UI%\index.html" "%WWW%\" >nul
copy /Y "%UI%\app.js" "%WWW%\" >nul
copy /Y "%UI%\styles.css" "%WWW%\" >nul
copy /Y "%UI%\manifest.webmanifest" "%WWW%\" >nul
copy /Y "%UI%\sw.js" "%WWW%\" >nul
echo Synced remote_ui → mobile_android\app\src\main\assets\www

where java >nul 2>nul
if errorlevel 1 (
  echo.
  echo Java not on PATH. Install JDK 17+, then either:
  echo   - Open mobile_android\ in Android Studio → Build → Build APK^(s^)
  echo   - Or install Android SDK command-line tools and re-run this script
  echo.
  echo UI assets are synced; you can build from Android Studio now.
  pause
  exit /b 0
)

cd /d "%ROOT%mobile_android"

if not exist "gradlew.bat" (
  echo Gradle wrapper missing — generating...
  where gradle >nul 2>nul
  if errorlevel 1 (
    echo.
    echo Open folder mobile_android in Android Studio once ^(it will create the wrapper^),
    echo then re-run build_remote_apk.bat
    echo UI is already synced.
    pause
    exit /b 0
  )
  gradle wrapper --gradle-version 8.2
)

echo Building debug APK...
call gradlew.bat assembleDebug
if errorlevel 1 (
  echo Build failed. Prefer: open mobile_android in Android Studio → Build APK.
  pause
  exit /b 1
)

set "APK=%ROOT%mobile_android\app\build\outputs\apk\debug\app-debug.apk"
if exist "%APK%" (
  copy /Y "%APK%" "%ROOT%CareerPilot-Remote-debug.apk" >nul
  echo.
  echo Built: CareerPilot-Remote-debug.apk ^(repo root^)
  echo Also:  %APK%
  echo.
  echo Install on phone: enable Unknown sources / Install unknown apps, then open the APK.
) else (
  echo APK not found after build.
  exit /b 1
)
pause
exit /b 0
