# J.E.N.N.Y — Windows Distribution Builder
# Packages the Python runtime into a portable folder + zip launcher.
# Usage:  powershell -ExecutionPolicy Bypass -File build-win-dist.ps1 [-SkipZip]

param(
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dist    = Join-Path $Root "dist\jenny-windows"
$SrcMap  = @(
    "server.py", "app.py", "hud.py",
    "gesture_controller.py", "pc_actions.py",
    "agency_client.py", "requirements.txt",
    "public"
)

Write-Host "============================================="
Write-Host "  J.E.N.N.Y - Windows Distribution Builder"
Write-Host "============================================="

if (Test-Path $Dist) { Remove-Item -Recurse -Force $Dist }
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

foreach ($item in $SrcMap) {
    $src = Join-Path $Root $item
    if (-not (Test-Path $src)) {
        Write-Host "  [!] Missing source: $item" -ForegroundColor Yellow
        continue
    }
    Copy-Item -Recurse -Force $src (Join-Path $Dist $item)
    Write-Host "  [+] Copied $item"
}

$scripts = Join-Path $Dist "scripts"
New-Item -ItemType Directory -Force -Path $scripts | Out-Null
foreach ($s in (Get-ChildItem (Join-Path $Root "scripts") -File)) {
    Copy-Item -Force $s.FullName (Join-Path $scripts $s.Name)
}
Write-Host "  [+] Copied scripts\"

$launcher = Join-Path $Dist "start-jenny.bat"
@"
@echo off
cd /d "%~dp0"
echo Starting J.E.N.N.Y v2.0 Windows server...
echo Dashboard: http://localhost:3005/modes.html
start "" http://localhost:3005/modes.html
python server.py
"@ | Set-Content -Encoding ASCII $launcher
Write-Host "  [+] Created start-jenny.bat"

$readme = Join-Path $Dist "README.txt"
@"
J.E.N.N.Y v2.0 - Windows Edition
--------------------------------
1. Install Python 3.10+ and run:  pip install -r requirements.txt
2. Double-click start-jenny.bat (server boots on port 3005)
3. Open one of:
   - Dashboard     http://localhost:3005/modes.html
   - HUD overlay   python hud.py
   - Wake word     python scripts\wakeword.py
"@ | Set-Content -Encoding ASCII $readme
Write-Host "  [+] Created README.txt"

if (-not $SkipZip) {
    $zip = Join-Path $Root "dist\jenny-windows.zip"
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Compress-Archive -Path $Dist -DestinationPath $zip -CompressionLevel Optimal
    Write-Host "  [+] Archive: $zip"
}

Write-Host "============================================="
Write-Host "  Build complete. Output: $Dist"
Write-Host "============================================="