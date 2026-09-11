@echo off
setlocal enabledelayedexpansion
title J.E.N.N.Y v2.0 - Launcher
cd /d "%~dp0"

echo ==========================================================
echo        J.E.N.N.Y v2.0 - Windows Launcher
echo        Just Every Necessary Neural Yearning
echo ==========================================================
echo.

set "PY=python"
where %PY% >nul 2>&1
if errorlevel 1 set "PY=py"
where %PY% >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)
%PY% --version

for /f "delims=" %%v in ('%PY% -c "import flask, waitress, webview, flask_cors; print(1)" 2^>nul') do set "DEPS=%%v"
if not defined DEPS (
    echo [*] Installing dependencies, first run...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [X] Dependency install failed. Check your internet connection.
        pause
        exit /b 1
    )
)

:menu
echo.
echo   [1] Full Desktop App   - main JENNY window
echo   [2] HUD Overlay        - transparent always-on-top HUD
echo   [3] Voice Assistant    - wake word "Hey Jenny" / "Hey Friday"
echo   [4] Server Only        - web UI on port 3005 (no window)
echo   [5] Debug Launcher     - verbose logs to run.log
echo   [Q] Quit
echo.
set /p "CHOICE=Select: "

if "%CHOICE%"=="1" (
    start "" "%PY%"w app.py
) else if "%CHOICE%"=="2" (
    start "" "%PY%"w hud.py
) else if "%CHOICE%"=="3" (
    start "" "%PY%" scripts\wakeword.py
) else if "%CHOICE%"=="4" (
    "%PY%" server.py
) else if "%CHOICE%"=="5" (
    start "" "%PY%"w launch_debug.py
) else if /i "%CHOICE%"=="Q" (
    exit /b 0
) else (
    echo [X] Invalid choice.
    goto menu
)
goto menu