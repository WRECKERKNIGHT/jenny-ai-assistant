@echo off
title J.E.N.N.Y v2.0 - Quick Start
cd /d "%~dp0"

rem ---- resolve a real interpreter, prefer the windowless pythonw ----
set "PYW=pythonw.exe"
set "PYEXE="
for /f "usebackq delims=" %%v in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%v"
if not defined PYEXE goto :launch
for %%I in ("%PYEXE%") do set "PYDIR=%%~dpI"
if exist "%PYDIR%pythonw.exe" set "PYW=%PYDIR%pythonw.exe"
if exist "%PYDIR%pythonw.exe" goto :launch
if exist "%PYEXE%" set "PYW=%PYEXE%"

:launch
rem ---- no pause: the console closes itself, the tray keeps running ----
start "" "%PYW%" tray.py
exit /b 0
