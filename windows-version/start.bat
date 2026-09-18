@echo off
title J.E.N.N.Y v2.0 - Quick Start
cd /d "%~dp0"
echo Starting JENNY (tray + mini HUD)...
start "" "pythonw.exe" tray.py
echo.
echo === J.E.N.N.Y is running in the tray. Press any key to close this window. ===
pause >nul