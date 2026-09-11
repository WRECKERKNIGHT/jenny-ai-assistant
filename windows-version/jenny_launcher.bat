@echo off
title J.E.N.N.Y v2.0
cd /d "%~dp0"
rem ---- Kill any stale instance already running ----
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE ne J.E.N.N.Y v2.0*" >nul 2>&1

rem ---- Launch the app hidden (pythonw = no console window) ----
start "" "pythonw.exe" app.py
exit
