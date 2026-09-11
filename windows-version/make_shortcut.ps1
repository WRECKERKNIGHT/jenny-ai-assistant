$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'J.E.N.N.Y v2.0.lnk'
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = "C:\Users\harsh\Downloads\jenny-ai-assistant-main\windows-version\jenny_launcher.bat"
$lnk.WorkingDirectory = "C:\Users\harsh\Downloads\jenny-ai-assistant-main\windows-version"
$lnk.Description = "J.E.N.N.Y v2.0 - Open the AI Assistant"
$lnk.IconLocation = "C:\Windows\System32\shell32.dll,21"
$lnk.Save()
Write-Output "Shortcut created: $lnkPath"
