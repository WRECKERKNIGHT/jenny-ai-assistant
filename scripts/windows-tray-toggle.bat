@echo off
:: JENNY AI ASSISTANT - Windows Taskbar / System Tray Trigger Script
:: Double click or pin to Windows Taskbar to toggle Jenny's microphone instantly!

powershell -Command "Invoke-RestMethod -Uri 'http://localhost:3000/api/toggle-mic' -Method Get" >nul 2>&1
echo [JENNY AI] Mic toggle triggered from Windows System Tray / Taskbar.
