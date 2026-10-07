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

rem --- start the server windowless, logging to logs\ ----------------
echo  [2/4] Booting neural core...
set "PYW="
if exist "%PYTHON:python.exe=pythonw.exe%" set "PYW=%PYTHON:python.exe=pythonw.exe%"
if not defined PYW for /f "usebackq delims=" %%v in (`where pythonw.exe 2^>nul`) do if not defined PYW set "PYW=%%v"
if defined PYW (
  start "" "%PYW%" server.py >> logs\jenny_boot.log 2>&1
) else (
  start "JENNY-SERVER" /min "%PYTHON%" server.py
)
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
echo  [4/4] Neural link established - launching dashboard...
start "" "http://localhost:3005"

rem ---- no lingering console: the server is already detached ----
echo  Done. Server logs: %~dp0logs\
exit /b 0
endlocal