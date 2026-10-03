@echo off
rem ==========================================================================
rem  J.E.N.N.Y  -  Windows Launcher
rem  Just Every Necessary Neural Yearning
rem
rem  Design notes:
rem    * ASCII art only. A .bat is decoded in the console OEM codepage (437/850),
rem      so box-drawing characters and typographic dashes render as mojibake on
rem      most machines. Plain ASCII looks identical everywhere.
rem    * The interpreter is resolved to a real sys.executable and the windowless
rem      sibling (pythonw.exe) is derived from that same directory. The previous
rem      version built its command by concatenating "%PY%w", which produced
rem      "pyw" - an executable that does not exist - so every windowed launch
rem      failed silently on machines that only had the `py` launcher.
rem    * Checks whether JENNY is already serving on the port before starting a
rem      second copy, and offers to open the browser instead.
rem ==========================================================================
title J.E.N.N.Y - Launcher
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PORT=3005"
set "JENNY_PID="
set "C_OFF="
set "C_ACCENT="
set "C_DIM="
set "C_OK="
set "C_WARN="
set "C_ERR="

rem ---- ANSI colour, but only if the console understands VT sequences ----
set "ESC="
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
if defined ESC (
    set "C_OFF=%ESC%[0m"
    set "C_ACCENT=%ESC%[38;5;51m"
    set "C_DIM=%ESC%[38;5;244m"
    set "C_OK=%ESC%[38;5;41m"
    set "C_WARN=%ESC%[38;5;214m"
    set "C_ERR=%ESC%[38;5;203m"
)

rem ==========================================================================
rem  Interpreter discovery
rem ==========================================================================
call :find_python
if not defined PYEXE goto :no_python

for %%I in ("%PYEXE%") do set "PYDIR=%%~dpI"
if exist "%PYDIR%pythonw.exe" set "PYWEXE=%PYDIR%pythonw.exe"

rem ---- First-run dependency check ----
%PYEXE% -c "import flask, waitress, webview, flask_cors, pystray, edge_tts" >nul 2>&1
if errorlevel 1 (
    echo %C_WARN%[*] First run - installing dependencies...%C_OFF%
    %PYEXE% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo %C_ERR%[X] Dependency install failed.%C_OFF%
        echo     Check your internet connection and that pip works,
        echo     then run this file again.
        pause
        exit /b 1
    )
    echo %C_OK%[+] Dependencies ready.%C_OFF%
)

:menu
cls
call :find_server
echo.
echo   %C_ACCENT%################################################%C_OFF%
echo   %C_ACCENT%##              J.E.N.N.Y  v2.0               ##%C_OFF%
echo   %C_DIM%##    Just Every Necessary Neural Yearning    ##%C_OFF%
echo   %C_ACCENT%################################################%C_OFF%
echo.
echo   %C_DIM%Python    %PYEXE%%C_OFF%
if defined PYWEXE (
    echo   %C_DIM%Console   pythonw.exe available - no window will appear%C_OFF%
) else (
    echo   %C_WARN%Console   pythonw.exe NOT found - targets will open a window%C_OFF%
)
if defined JENNY_PID (
    echo   %C_OK%Status    RUNNING on port %PORT% ^(%JENNY_PID%^)%C_OFF%
) else (
    echo   %C_DIM%Status    not running%C_OFF%
)
echo.
echo   %C_DIM%--------------------------------------------%C_OFF%
echo    %C_ACCENT%[1]%C_OFF%  Quick Start       %C_DIM%tray + Mini HUD + server + voice%C_OFF%
echo    %C_ACCENT%[2]%C_OFF%  Full Desktop App  %C_DIM%the main JENNY window%C_OFF%
echo    %C_ACCENT%[3]%C_OFF%  Open in Browser   %C_DIM%web UI on port %PORT%%C_OFF%
echo    %C_ACCENT%[4]%C_OFF%  HUD Overlay       %C_DIM%draggable holographic HUD%C_OFF%
echo    %C_ACCENT%[5]%C_OFF%  Voice Only        %C_DIM%wake word listener, no UI%C_OFF%
echo    %C_ACCENT%[6]%C_OFF%  Server Only       %C_DIM%console server, no window%C_OFF%
echo    %C_ACCENT%[7]%C_OFF%  Debug Launcher    %C_DIM%verbose logging to run.log%C_OFF%
echo   %C_DIM%--------------------------------------------%C_OFF%
echo    %C_DIM%[S]  Start        [O]  Open browser%C_OFF%
echo    %C_DIM%[K]  Kill JENNY   [Q]  Quit%C_OFF%
echo.
set "CHOICE="
set /p "CHOICE=   Select: "

if /i "%CHOICE%"=="1" goto :launch_tray
if /i "%CHOICE%"=="2" goto :launch_app
if /i "%CHOICE%"=="3" goto :open_browser
if /i "%CHOICE%"=="4" goto :launch_hud
if /i "%CHOICE%"=="5" goto :launch_voice
if /i "%CHOICE%"=="6" goto :launch_server
if /i "%CHOICE%"=="7" goto :launch_debug
if /i "%CHOICE%"=="O" goto :open_browser
if /i "%CHOICE%"=="S" goto :launch_tray
if /i "%CHOICE%"=="K" goto :kill
if /i "%CHOICE%"=="Q" goto :quit
echo %C_ERR%   [!] Unknown choice "%CHOICE%".%C_OFF%
timeout /t 1 >nul
goto :menu

rem ==========================================================================
rem  Actions
rem ==========================================================================
:launch_tray
call :confirm_free "Quick Start"
if errorlevel 1 goto :menu
echo %C_OK%[*] Starting JENNY - tray icon and Mini HUD...%C_OFF%
start "" "%PYEXE%" tray.py
goto :done

:launch_app
call :confirm_free "Full Desktop App"
if errorlevel 1 goto :menu
echo %C_OK%[*] Starting the JENNY desktop window...%C_OFF%
start "" "%PYEXE%" app.py
goto :done

:launch_debug
call :confirm_free "Debug Launcher"
if errorlevel 1 goto :menu
echo %C_OK%[*] Starting with verbose logging...%C_OFF%
start "" "%PYEXE%" launch_debug.py
goto :done

:launch_hud
echo %C_OK%[*] Starting the HUD overlay...%C_OFF%
call :windowless hud.py
goto :done

:launch_voice
echo %C_OK%[*] Starting the wake word listener...%C_OFF%
call :windowless scripts\wakeword.py
goto :done

:launch_server
call :confirm_free "Server Only"
if errorlevel 1 goto :menu
echo %C_OK%[*] Starting the server. Press Ctrl+C to stop.%C_OFF%
echo.
%PYEXE% server.py
goto :menu

:open_browser
call :find_server
if not defined JENNY_PID (
    echo.
    echo %C_ERR%[!] Nothing is listening on port %PORT% yet.%C_OFF%
    echo     Start JENNY first with option %C_ACCENT%1%C_OFF%.
    timeout /t 2 >nul
    goto :menu
)
echo %C_OK%[*] Opening http://localhost:%PORT%%C_OFF%
start "" "http://localhost:%PORT%"
goto :done

:kill
call :find_server
echo.
if not defined JENNY_PID (
    echo %C_DIM%[*] Nothing is listening on %PORT% - nothing to stop.%C_OFF%
    timeout /t 2 >nul
    goto :menu
)
taskkill /f /pid %JENNY_PID% >nul 2>&1
if errorlevel 1 (
    echo %C_ERR%[!] Could not stop process %JENNY_PID%.%C_OFF%
    echo     It may need Administrator rights.
) else (
    echo %C_OK%[+] Stopped JENNY ^(%JENNY_PID%^).%C_OFF%
)
timeout /t 2 >nul
goto :menu

:done
echo.
echo %C_DIM%   The launcher stays open so you can launch something else.%C_OFF%
echo %C_DIM%   [O] open the web UI     [Q] close this window%C_OFF%
echo.
set "AFTER="
set /p "AFTER=   Select: "
if /i "%AFTER%"=="O" goto :open_browser
if /i "%AFTER%"=="Q" goto :quit
goto :menu

:quit
echo.
echo %C_DIM%   Bye.%C_OFF%
timeout /t 1 >nul
exit /b 0

rem ==========================================================================
rem  Subroutines
rem ==========================================================================

rem Sets JENNY_PID to the pid listening on %PORT%, or clears it.
:find_server
set "JENNY_PID="
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /r /c:":%PORT% .*LISTENING" 2^>nul') do (
    rem Keep the first hit: several lines can match when a socket is bound to
    more than one interface, and they all resolve to the same owning pid.
    if not defined JENNY_PID set "JENNY_PID=%%p"
)
exit /b 0

rem Refuses to start a second server. Leaves errorlevel 1 so the caller can
rem bounce back to the menu. %~1 is the name of the thing being started.
:confirm_free
call :find_server
if not defined JENNY_PID exit /b 0
echo.
echo %C_WARN%[!] %~1: JENNY is already running on port %PORT% ^(%JENNY_PID%^).%C_OFF%
echo     A second copy would fight over the port.
echo.
set "SUB="
set /p "SUB=     [O] open it   [K] stop it   [C] cancel: "
if /i "%SUB%"=="O" (
    start "" "http://localhost:%PORT%"
    goto :menu
)
if /i "%SUB%"=="K" goto :kill
exit /b 1

rem Usage: call :windowless <script.py>
rem Prefers pythonw.exe so the target gets no console window, and falls back to
rem the console interpreter so it still runs rather than failing silently.
:windowless
if defined PYWEXE (
    start "" "%PYWEXE%" %~1
) else (
    start "" "%PYEXE%" %~1
)
exit /b 0

rem Try `python`, then the `py` launcher. Both report a real sys.executable,
rem which is what makes finding pythonw.exe reliable.
:find_python
if defined PYEXE exit /b 0
for %%C in (python py) do (
    if not defined PYEXE (
        for /f "usebackq delims=" %%v in (`%%C -c "import sys;print(sys.executable)" 2^>nul`) do (
            if exist "%%v" set "PYEXE=%%v"
        )
    )
)
if not defined PYEXE exit /b 1
exit /b 0

:no_python
echo.
echo %C_ERR%[X] Python 3.10 or newer is required and was not found on PATH.%C_OFF%
echo.
echo     1. Install Python from https://www.python.org/downloads/
echo     2. Tick "Add python.exe to PATH" on the first installer screen
echo     3. Open a NEW terminal window and run this file again
echo.
pause
exit /b 1
