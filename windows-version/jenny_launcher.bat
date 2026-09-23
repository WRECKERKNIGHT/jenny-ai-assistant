@echo off
title J.E.N.N.Y v2.0
cd /d "%~dp0"
rem ---- Kill any stale instance already running ----
taskkill /F /IM pythonw.exe "tray" >nul 2>&1
rem ---- Launch the full desktop app (pywebview 1440x900) ----
start "" "pythonw.exe" app.py
exit