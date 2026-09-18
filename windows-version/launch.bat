@echo off
title J.E.N.N.Y v2.0
cd /d "%~dp0"
echo [*] Starting JENNY (tray + mini HUD)...
echo [*] Look for the J.E.N.N.Y icon near the clock, then double-click it.
start "" "pythonw.exe" tray.py
exit