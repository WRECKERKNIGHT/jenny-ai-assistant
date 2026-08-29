@echo off
cd /d "%~dp0"
echo Starting JENNY...
python app.py
echo.
echo === JENNY has exited. Press any key to close. ===
pause >nul
