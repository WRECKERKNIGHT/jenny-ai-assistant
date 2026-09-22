# J.E.N.N.Y v2.0 — Start Menu + Desktop shortcut installer
#   - Puts J.E.N.N.Y in the Start Menu like a normal installed app
#   - Optionally adds a Desktop shortcut and/or Windows auto-start
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File make_shortcut.ps1
#   powershell -ExecutionPolicy Bypass -File make_shortcut.ps1 -Desktop
#   powershell -ExecutionPolicy Bypass -File make_shortcut.ps1 -Autostart
#   powershell -ExecutionPolicy Bypass -File make_shortcut.ps1 -Remove

param(
    [switch]$Desktop,      # also (re)create the Desktop shortcut
    [switch]$Autostart,    # also register to auto-start with Windows
    [switch]$Remove        # remove only (Start Menu + Desktop + autostart)
)

$ErrorActionPreference = "SilentlyContinue"
$Base = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$Launcher = Join-Path $Base "jenny_launcher.bat"
$Icon = Join-Path $Base "public\logo.png"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$ShName = "J.E.N.N.Y v2.0.lnk"

$ws = New-Object -ComObject WScript.Shell

function Remove-Link($path) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
}

if ($Remove) {
    Remove-Link (Join-Path $StartMenuDir $ShName)
    Remove-Link (Join-Path ([Environment]::GetFolderPath("Desktop")) $ShName)
    try {
        Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "JENNY" -ErrorAction Stop
    } catch { }
    Write-Host "[+] Removed shortcuts and auto-start entry." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path -LiteralPath $Launcher)) {
    Write-Host "[X] Launcher missing: $Launcher" -ForegroundColor Red
    exit 1
}

# ---- Start Menu shortcut (the 'installed app' entry) ----------------------
try {
    $lnk = $ws.CreateShortcut((Join-Path $StartMenuDir $ShName))
    $lnk.TargetPath = $Launcher
    $lnk.WorkingDirectory = $Base
    $lnk.IconLocation = "$Icon,0"
    $lnk.Description = "J.E.N.N.Y v2.0 - AI Assistant (starts in the background tray)"
    $lnk.WindowStyle = 7
    $lnk.Save()
    Write-Host "[+] Start Menu shortcut: $StartMenuDir\$ShName" -ForegroundColor Green
} catch {
    Write-Host "[!] Could not write Start Menu shortcut: $_" -ForegroundColor Yellow
}

# ---- Desktop shortcut ------------------------------------------------------
if ($Desktop) {
    try {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $lnk2 = $ws.CreateShortcut((Join-Path $desktop $ShName))
        $lnk2.TargetPath = $Launcher
        $lnk2.WorkingDirectory = $Base
        $lnk2.IconLocation = "$Icon,0"
        $lnk2.Description = "J.E.N.N.Y v2.0 - AI Assistant (starts in the background tray)"
        $lnk2.WindowStyle = 7
        $lnk2.Save()
        Write-Host "[+] Desktop shortcut created." -ForegroundColor Green
    } catch {
        Write-Host "[!] Could not write desktop shortcut: $_" -ForegroundColor Yellow
    }
}

# ---- Windows auto-start (registry Run key -> tray in background) -----------
if ($Autostart) {
    try {
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
        if ($py) {
            $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
            Set-ItemProperty -Path $runKey -Name "JENNY" -Value "`"$py`" -w `"$Base\tray.py`" --auto"
            Write-Host "[+] Registered to auto-start with Windows." -ForegroundColor Green
        } else {
            Write-Host "[!] Python not found on PATH — skipping auto-start." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[!] Could not write auto-start entry: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "  Done! J.E.N.N.Y is now a Start Menu app." -ForegroundColor Cyan
Write-Host "  To remove:  powershell -ExecutionPolicy Bypass -File make_shortcut.ps1 -Remove" -ForegroundColor DarkGray