@echo off
setlocal
title J.E.N.N.Y. Launcher
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem  J.E.N.N.Y. - one-click launcher (Windows)
rem  Kills any stale server on :3005, starts fresh, waits for health,
rem  then opens the dashboard in the default browser.
rem ---------------------------------------------------------------

set PYTHON=C:\Users\harsh\AppData\Local\Programs\Python\Python314\python.exe
if not exist "%PYTHON%" set PYTHON=python

if not exist logs mkdir logs
set LOG_OUT=logs\jenny_server.log
set LOG_ERR=logs\jenny_server.err.log

echo.
echo  ================================================
echo   J.E.N.N.Y. NEURAL CORE  -  STARTING
echo  ================================================
echo.

rem --- kill anything already holding :3005 ------------------------
echo  [1/4] Freeing port 3005...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :3005 ^| findstr LISTENING') do (
  echo        killing PID %%p
  taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul

rem --- start the server (hidden, logging to logs\) -----------------
echo  [2/4] Booting neural core...
start "JENNY-SERVER" /min "%PYTHON%" server.py
timeout /t 1 /nobreak >nul >nul

rem --- wait for /api/health ----------------------------------------
echo  [3/4] Waiting for neural link...
set /a tries=0
:waitloop
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -Uri 'http://localhost:3005/api/health' -TimeoutSec 2 -UseBasicParsing; exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 goto up
set /a tries+=1
if %tries% geq 30 (
  echo        FAILED to reach server. Check logs\jenny_server.err.log
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:up
echo  [4/4] Neural link established - launching console...
start "" "http://localhost:3005"

echo.
echo  Done. Server logs: %~dp0logs\
echo  Close this window anytime (server keeps running).
echo.
pause
endlocal