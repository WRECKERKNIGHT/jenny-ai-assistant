<#
    J.E.N.N.Y v2.0 - One-click Windows Setup & Workflow Automation

    Fixes, installs, and fully automates the assistant on this PC:

      1. Detects Python and installs every dependency (requirements.txt)
      2. Prompts for your Groq API key (used for online AI + Whisper STT)
         and stores it ONLY in the git-ignored data/keys.json
      3. Registers JENNY to auto-start with Windows (registry Run key)
      4. Creates a Desktop shortcut for the one-click launcher
      5. Runs a dependency + microphone diagnostic report
      6. Optionally launches the assistant right away

    Usage:
      powershell -ExecutionPolicy Bypass -File install.ps1            # full setup
      powershell -ExecutionPolicy Bypass -File install.ps1 -Silent     # deps + autostart only
#>

param(
    [switch]$Silent,
    [switch]$NoAutostart,
    [switch]$SkipDeps
)

$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location -LiteralPath $PSScriptRoot

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host "        J.E.N.N.Y v2.0 - Windows Setup & Automation" -ForegroundColor Cyan
Write-Host "        Just Every Necessary Neural Yearning" -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 0. Locate Python
# ---------------------------------------------------------------------------
function Find-Python {
    foreach ($cand in @("python", "py")) {
        try {
            $v = & $cand -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) { return "$v" }
        } catch { }
    }
    return $null
}

$PY = Find-Python
if (-not $PY) {
    Write-Host "  [X] Python not found. Install Python 3.10+ (add to PATH) and re-run." -ForegroundColor Red
    exit 1
}

Write-Host "  [i] Python: $PY" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------
if (-not $SkipDeps) {
    Write-Host "  [*] Installing dependencies..." -ForegroundColor Yellow
    & $PY -m pip install --upgrade pip | Out-Null
    & $PY -m pip install -r "$PSScriptRoot\requirements.txt"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [X] Dependency install failed. Check your internet connection." -ForegroundColor Red
        exit 1
    }
    Write-Host "  [+] Dependencies installed." -ForegroundColor Green
} else {
    Write-Host "  [i] Skipping dependency install (SkipDeps)." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 2. Groq API key -> data/keys.json (git-ignored, never committed)
# ---------------------------------------------------------------------------
$keysJson = "$PSScriptRoot\data\keys.json"
if (-not $Silent) {
    $existing = ""
    if (Test-Path -LiteralPath $keysJson) {
        try { $existing = (Get-Content -Raw -LiteralPath $keysJson | ConvertFrom-Json).grok_api_key } catch { }
    }
    if ($existing) {
        Write-Host "  [i] Groq key already configured ($($existing.Substring(0,7))...). Leave blank to keep it." -ForegroundColor Green
    }
    $key = Read-Host "  [>] Enter your Groq API key (gsk_...) [Enter to skip]"
    if ([string]::IsNullOrWhiteSpace($key)) { $key = $existing }
} else {
    $key = $existing = ""
    if (Test-Path -LiteralPath $keysJson) {
        try { $key = (Get-Content -Raw -LiteralPath $keysJson | ConvertFrom-Json).grok_api_key } catch { }
    }
}

New-Item -ItemType Directory -Path "$PSScriptRoot\data" -Force | Out-Null
$obj = @{ grok_api_key = $key }
if (Test-Path -LiteralPath $keysJson) {
    try { $obj = (Get-Content -Raw -LiteralPath $keysJson | ConvertFrom-Json) | ForEach-Object { $_ } ; $obj | Add-Member -NotePropertyName grok_api_key -NotePropertyValue $key -Force } catch { }
}
if (Test-Path -LiteralPath $keysJson) {
    try { $cur = Get-Content -Raw -LiteralPath $keysJson | ConvertFrom-Json; $cur.grok_api_key = $key; $cur | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $keysJson -Encoding UTF8 } catch { $obj | ConvertTo-Json | Set-Content -LiteralPath $keysJson -Encoding UTF8 }
} else {
    $obj | ConvertTo-Json | Set-Content -LiteralPath $keysJson -Encoding UTF8
}
if ($key) { Write-Host "  [+] Groq API key stored in data\keys.json" -ForegroundColor Green }

# ---------------------------------------------------------------------------
# 3. Auto-start with Windows (registry Run key -> pythonw tray.py --auto)
# ---------------------------------------------------------------------------
if (-not $NoAutostart) {
    try {
        $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
        $batTarget = "`"$PY`" -w `"$PSScriptRoot\tray.py`" --auto"
        Set-ItemProperty -Path $runKey -Name "JENNY" -Value $batTarget
        Write-Host "  [+] JENNY set to auto-start with Windows (registry Run key)." -ForegroundColor Green
    } catch {
        Write-Host "  [!] Could not write registry Run key: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [i] Skipping auto-start (NoAutostart)." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 4. Start Menu + Desktop shortcut (make JENNY a normal installed app)
# ---------------------------------------------------------------------------
try {
    $StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $ShName = "J.E.N.N.Y v2.0.lnk"
    $Icon = Join-Path $PSScriptRoot "public\logo.png"
    $Launcher = Join-Path $PSScriptRoot "Jenny.bat"
    $wsh = New-Object -ComObject WScript.Shell

    # Start Menu entry (primary - appears in Windows Search / Start)
    $smLnk = $wsh.CreateShortcut((Join-Path $StartMenuDir $ShName))
    $smLnk.TargetPath = $Launcher
    $smLnk.WorkingDirectory = $PSScriptRoot
    $smLnk.IconLocation = "$Icon,0"
    $smLnk.Description = "J.E.N.N.Y v2.0 - AI Assistant"
    $smLnk.WindowStyle = 7
    $smLnk.Save()
    Write-Host "  [+] Start Menu app created." -ForegroundColor Green

    # Desktop shortcut (optional convenience)
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnk = $wsh.CreateShortcut("$desktop\J.E.N.N.Y v2.0.lnk")
    $lnk.TargetPath = $Launcher
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = "$Icon,0"
    $lnk.Description = "J.E.N.N.Y v2.0 - AI Assistant"
    $lnk.WindowStyle = 7
    $lnk.Save()
    Write-Host "  [+] Desktop shortcut created." -ForegroundColor Green
} catch {
    Write-Host "  [!] Could not create shortcuts: $_" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 5. Diagnostics
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  --- J.E.N.N.Y diagnostics ---" -ForegroundColor Cyan
& $PY -c @"
import importlib
mods = ['flask','flask_cors','psutil','pyttsx3','requests','webview','waitress','qrcode','PIL','speech_recognition','sounddevice','groq','pycaw','comtypes','edge_tts','pystray','pyautogui']
ok = True
for m in mods:
    try:
        importlib.import_module(m)
        print(f'[OK]   {m}')
    except Exception as e:
        ok = False
        print(f'[FAIL] {m}: {e}')
import sys
print('EXIT', 'OK' if ok else 'FAIL', 'python='+sys.version.split()[0])
"@

& $PY -c @"
try:
    import sounddevice as sd
    devs = sd.query_devices()
    mics = [d for d in devs if d.get('max_input_channels', 0) > 0]
    print(f'[MIC] {len(mics)} microphone(s) detected: ' + (', '.join(d['name'] for d in mics)[:120] or 'none'))
except Exception as e:
    print(f'[MIC] none detected ({type(e).__name__})')
"@

# ---------------------------------------------------------------------------
# 6. Launch
# ---------------------------------------------------------------------------
if (-not $Silent) {
    $go = Read-Host "`n  [>] Launch J.E.N.N.Y now? (y/N)"
    if ($go -match "^(y|yes)$") {
        & $PY -w "$PSScriptRoot\tray.py" --auto
    }
}

Write-Host ""
Write-Host "  Done! Launch J.E.N.N.Y from the Start Menu or double-click the desktop shortcut." -ForegroundColor Green
Write-Host "  To remove auto-start later: run: python scripts\startup.py --uninstall" -ForegroundColor DarkGray
Write-Host ""