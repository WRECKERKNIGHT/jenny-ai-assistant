"""
U.L.T.R.O.N. PC Control Actions
Browser + system control executed from ULTRON gestures.
Uses PyAutoGUI hotkeys and PowerShell behind the scenes.
"""
import os
import time
import subprocess
import datetime
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.03
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

_browser_proc_info = None


def _hwnd_send(key):
    if HAS_PYAUTOGUI:
        try:
            pyautogui.press(key)
            return True
        except Exception:
            pass
    return False


def _hotkey(*keys):
    if HAS_PYAUTOGUI:
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            pass
    return False


def _shell(cmd, timeout=10):
    try:
        subprocess.run(cmd, shell=True, capture_output=True,
                       timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False


def browser_open(url=None):
    """Open the default browser (optionally at a URL)."""
    target = url or "https://www.google.com"
    if _hotkey("win") or True:
        pass
    try:
        os.startfile(target)
        time.sleep(1.2)
        _hotkey("ctrl", "t")
        return True
    except Exception:
        return _shell(f"start {target}")


def browser_new_tab():
    return _hotkey("ctrl", "t")


def browser_close_tab():
    return _hotkey("ctrl", "w")


def browser_back():
    return _hotkey("alt", "left")


def browser_forward():
    return _hotkey("alt", "right")


def browser_refresh():
    return _hotkey("ctrl", "r")


def browser_search(text=""):
    query = (text or "").strip()
    goto = _hotkey("ctrl", "l")
    if not goto:
        return False
    time.sleep(0.15)
    if query:
        if HAS_PYAUTOGUI:
            pyautogui.typewrite(query, interval=0.01)
        pyautogui.press("enter")
    return True


def browser_new_window():
    return _hotkey("ctrl", "n")


def browser_reopen_tab():
    return _hotkey("ctrl", "shift", "t")


def browser_fullscreen():
    return _hotkey("f11")


def volume_up():
    return _hwnd_send("volumeup")


def volume_down():
    return _hwnd_send("volumedown")


def volume_mute():
    return _hwnd_send("volumemute")


def media_play_pause():
    return _hwnd_send("playpause")


def media_next():
    return _hwnd_send("nexttrack")


def media_prev():
    return _hwnd_send("prevtrack")


def screenshot(dest=None):
    """Save a full-screen screenshot to Desktop (or given path)."""
    if not HAS_PYAUTOGUI:
        return False
    try:
        folder = dest or str(Path.home() / "Desktop")
        path = os.path.join(
            folder,
            f"ultron_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        pyautogui.screenshot(path)
        return path
    except Exception:
        return False


def open_task_manager():
    return _hotkey("ctrl", "shift", "esc")


def show_desktop():
    return _hotkey("win", "d")


def lock_pc():
    return _hotkey("win", "l")


def toggle_browser():
    """Refocus browser; falls back to opening it."""
    opened = browser_open()
    return opened


def close_window_focused():
    return _hotkey("alt", "f4")


def open_app(name):
    apps = {
        "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
        "chrome": "chrome", "edge": "msedge", "vscode": "code",
        "spotify": "spotify", "discord": "discord", "file": "explorer.exe",
        "terminal": "wt.exe", "cmd": "cmd.exe",
        "camera": "microsoft.windows.camera:", "settings": "ms-settings:",
        "controlpanel": "control", "clipboard": "ms-settings:clipboard",
        "clock": "ms-settings:dateandtime", "alarms": "ms-clock:",
    }
    target = apps.get(str(name).lower(), name)
    return _shell(f"start {target}")


def browser_youtube():
    return browser_open("https://www.youtube.com")


def browser_gmail():
    return browser_open("https://mail.google.com")


def browser_github():
    return browser_open("https://github.com")


def speak_feedback(text):
    """Audible confirmation via Windows SAPI (used for gesture results)."""
    if not text:
        return False
    import re as _re
    safe = _re.sub(r'[^0-9a-zA-Z .,!?]', '', str(text))
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Add-Type -AssemblyName System.Speech;"
        f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.Speak('{safe}')"
    )
    return _shell(f"powershell -NoProfile -Command \"{ps}\"", timeout=8)


def lock_screen_timer(seconds=0):
    """Lock the PC now, or after a short countdown for safety."""
    if seconds and seconds > 0:
        time.sleep(min(seconds, 15))
    return lock_pc()


def _capture(cmd, timeout=15):
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace",
                              creationflags=subprocess.CREATE_NO_WINDOW)
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def _ps(script, timeout=30):
    """Run a PowerShell script safely.

    Two hazards are handled here. First, the registry actions build real
    PowerShell, and passing that inline through cmd.exe mangles quotes and
    paths, so the script goes to a utf-8-sig temp file (the BOM also stops
    PowerShell 5.1 mis-reading non-ASCII filenames as ANSI). Second, output
    goes to a FILE rather than a pipe: with shell=True, killing a timed-out
    command leaves the real powershell.exe alive holding the inherited stdout
    pipe, and reading that pipe then blocks forever. A file sidesteps the
    inherited handle entirely, and the process is killed by PID as a backstop.
    """
    stamp = f"{int(time.time() * 1000)}"
    tmp_dir = Path(os.environ.get("TEMP", "."))
    script_path = tmp_dir / f"jenny_act_{stamp}.ps1"
    out_path = tmp_dir / f"jenny_act_{stamp}.out"
    proc = None
    try:
        script_path.write_text(script, encoding="utf-8-sig")
        with open(out_path, "w", encoding="utf-8") as sink:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
                stdout=sink, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
        return out_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    finally:
        for path in (script_path, out_path):
            try:
                path.unlink()
            except Exception:
                pass


def _kill_tree(proc):
    """Kill a PowerShell process and anything it started."""
    if proc is None:
        return
    for attempt in (proc.kill,):
        try:
            attempt()
        except Exception:
            pass
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, timeout=15,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def _rows(out, sep="|"):
    rows = []
    for line in (out or "").splitlines():
        line = line.strip()
        if line:
            rows.append(line.split(sep, 1) if sep in line else [line])
    return rows


def clipboard_read():
    text = _capture('powershell -NoProfile -Command "Get-Clipboard -Raw"', timeout=12)
    if not text:
        return {"ok": False, "text": "The clipboard is empty, or it holds an image rather than text."}
    return {"ok": True, "text": text[:2000], "chars": len(text)}


def clipboard_write(text=""):
    clean = "".join(ch for ch in str(text or "") if ch >= " " or ch in "\n\t")
    if not clean.strip():
        return {"ok": False, "text": "Nothing to copy - that text was empty."}
    safe = clean.replace("'", "''")
    _ps(f"Set-Clipboard -Value '{safe}'", timeout=12)
    return {"ok": True, "text": f"Copied {len(clean)} characters to the clipboard."}


def _default_search_roots():
    home = Path.home()
    return [str(p) for p in (home / "Desktop", home / "Documents", home / "Downloads") if p.is_dir()]


def file_search(pattern="", root=None, limit=25):
    needle = str(pattern or "").strip()
    if not needle:
        return {"ok": False, "text": "Tell me what to search for."}
    roots = [str(root)] if root else _default_search_roots()
    if not roots:
        return {"ok": False, "text": "I couldn't find any folders to search."}
    # Depth-capped and scoped to the folders people actually mean. An uncapped
    # -Recurse over the whole profile took 45s, which is useless in conversation.
    safe_needle = needle.replace("'", "''")
    quoted = ",".join("'" + str(r).replace("'", "''") + "'" for r in roots)
    out = _ps(
        f"$ErrorActionPreference='SilentlyContinue';"
        f"$roots=@({quoted}); $found=@();"
        f"foreach($r in $roots){{ if(Test-Path -LiteralPath $r){{"
        f" $found += Get-ChildItem -LiteralPath $r -Recurse -Depth 4 -File -Filter '*{safe_needle}*' }} }};"
        f"$found | Sort-Object LastWriteTime -Descending | Select-Object -First {int(limit)} |"
        f" ForEach-Object {{ \"$($_.FullName)|$($_.Length)\" }}",
        timeout=30,
    )
    rows = _rows(out)
    if not rows:
        scope = str(root) if root else "Desktop, Documents and Downloads"
        return {"ok": True, "count": 0, "files": [],
                "text": f"No files matching '{needle}' in {scope}."}
    files = [{"path": r[0], "bytes": int(r[1]) if len(r) > 1 and r[1].isdigit() else None} for r in rows]
    scope = str(root) if root else "Desktop, Documents and Downloads"
    return {"ok": True, "count": len(files), "files": files,
            "text": f"Found {len(files)} file(s) matching '{needle}' in {scope}."}


def recent_files(limit=15):
    # CreateShortcut lives on WScript.Shell; Shell.Application has no such
    # method and throws "does not contain a method named 'CreateShortcut'".
    out = _ps(
        "$ErrorActionPreference='SilentlyContinue';"
        "$ws=New-Object -ComObject WScript.Shell;"
        "$dir=Join-Path $env:APPDATA 'Microsoft\\Windows\\Recent';"
        f"Get-ChildItem -LiteralPath $dir -Filter *.lnk | Sort-Object LastWriteTime -Descending |"
        f" Select-Object -First {int(limit)} | ForEach-Object {{"
        " $t=''; try { $t=$ws.CreateShortcut($_.FullName).TargetPath } catch {};"
        " if(-not $t){ $t=$_.Name };"
        " \"$($_.LastWriteTime.ToString('yyyy-MM-dd'))|$t\" }",
        timeout=45,
    )
    rows = [r for r in _rows(out) if r[0]]
    if not rows:
        return {"ok": False, "text": "Couldn't read the recent-files list."}
    files = [{"opened": r[0], "path": r[1] if len(r) > 1 else ""} for r in rows]
    return {"ok": True, "count": len(files), "files": files,
            "text": f"{len(files)} recent file(s). Most recent: {files[0]['path']}"}


def large_files(root=None, limit=10):
    roots = [str(root)] if root else _default_search_roots()
    if not roots:
        return {"ok": False, "text": "I couldn't find any folders to scan."}
    # Same scoping rationale as file_search: a depth-5 walk of the whole profile
    # took 61s and timed out, which is useless in conversation.
    quoted = ",".join("'" + str(r).replace("'", "''") + "'" for r in roots)
    out = _ps(
        f"$ErrorActionPreference='SilentlyContinue';"
        f"$roots=@({quoted}); $found=@();"
        f"foreach($r in $roots){{ if(Test-Path -LiteralPath $r){{"
        f" $found += Get-ChildItem -LiteralPath $r -Recurse -Depth 4 -File }} }};"
        f"$found | Sort-Object Length -Descending | Select-Object -First {int(limit)} |"
        f" ForEach-Object {{ \"$([math]::Round($_.Length/1MB,1))|$($_.FullName)\" }}",
        timeout=45,
    )
    rows = _rows(out)
    if not rows:
        scope = str(root) if root else "Desktop, Documents and Downloads"
        return {"ok": False, "text": f"Couldn't scan {scope} for large files."}
    files = [{"mb": r[0], "path": r[1] if len(r) > 1 else ""} for r in rows]
    return {"ok": True, "count": len(files), "files": files,
            "text": f"Largest of {len(files)} file(s): " + ", ".join(f"{f['mb']}MB" for f in files[:3])}


def list_processes(limit=15):
    try:
        import psutil
    except Exception:
        return {"ok": False, "text": "psutil isn't installed, so I can't list processes."}
    rows = []
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            info = proc.info
            rss = info["memory_info"].rss if info.get("memory_info") else 0
            rows.append((rss, info.get("name") or "?"))
        except Exception:
            continue
    rows.sort(reverse=True)
    top = [{"name": n, "mb": round(b / 1048576, 1)} for b, n in rows[: int(limit)]]
    return {"ok": True, "count": len(top), "processes": top,
            "text": f"{len(top)} heaviest processes: " + ", ".join(f"{t['name']} {t['mb']}MB" for t in top[:5])}


def startup_apps():
    out = _ps(
        "$ErrorActionPreference='SilentlyContinue';"
        "$keys=@('HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',"
        "'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run');"
        "foreach($k in $keys){ if(Test-Path $k){"
        " (Get-ItemProperty $k).PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } |"
        " ForEach-Object { \"$($_.Name)|$($_.Value)\" } } };"
        "$sd=Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Startup';"
        "Get-ChildItem -LiteralPath $sd | ForEach-Object { \"$($_.Name)|startup folder\" }",
        timeout=30,
    )
    rows = [r for r in _rows(out) if r and r[0]]
    if not rows:
        return {"ok": True, "count": 0, "startup": [], "text": "No startup entries found."}
    items = [{"name": r[0], "command": r[1] if len(r) > 1 else ""} for r in rows]
    return {"ok": True, "count": len(items), "startup": items,
            "text": f"{len(items)} startup entr(ies): " + ", ".join(i["name"] for i in items[:6])}


def system_diagnostics():
    try:
        import psutil
    except Exception:
        return {"ok": False, "text": "psutil isn't installed, so I can't read system diagnostics."}
    info = {"host": os.environ.get("COMPUTERNAME", "?")}
    try:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.4)
        info["cpu_cores"] = psutil.cpu_count()
    except Exception:
        pass
    try:
        vm = psutil.virtual_memory()
        info["ram_total_gb"] = round(vm.total / 1073741824, 1)
        info["ram_used_percent"] = vm.percent
    except Exception:
        pass
    try:
        usage = psutil.disk_usage(str(Path.home().anchor or "C:\\"))
        info["disk_total_gb"] = round(usage.total / 1073741824, 1)
        info["disk_free_gb"] = round(usage.free / 1073741824, 1)
        info["disk_percent"] = usage.percent
    except Exception:
        pass
    try:
        net = psutil.net_io_counters()
        info["net_sent_mb"] = round(net.bytes_sent / 1048576, 1)
        info["net_recv_mb"] = round(net.bytes_recv / 1048576, 1)
    except Exception:
        pass
    try:
        bat = psutil.sensors_battery()
        if bat:
            info["battery_percent"] = round(bat.percent, 1)
            info["charging"] = bool(bat.power_plugged)
    except Exception:
        pass
    try:
        info["boot_time"] = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    parts = [f"CPU {info.get('cpu_percent', '?')}%", f"RAM {info.get('ram_used_percent', '?')}%",
             f"disk {info.get('disk_free_gb', '?')}GB free"]
    if "battery_percent" in info:
        parts.append(f"battery {info['battery_percent']}%")
    return {"ok": True, "info": info, "text": f"{info['host']}: " + ", ".join(parts)}


ACTION_INDEX = {
    "clipboard_read": clipboard_read,
    "clipboard_write": clipboard_write,
    "file_search": file_search,
    "recent_files": recent_files,
    "large_files": large_files,
    "list_processes": list_processes,
    "startup_apps": startup_apps,
    "system_diagnostics": system_diagnostics,
    "browser_open": browser_open,
    "browser_new_tab": browser_new_tab,
    "browser_close_tab": browser_close_tab,
    "browser_back": browser_back,
    "browser_forward": browser_forward,
    "browser_refresh": browser_refresh,
    "browser_search": browser_search,
    "browser_new_window": browser_new_window,
    "browser_reopen_tab": browser_reopen_tab,
    "browser_fullscreen": browser_fullscreen,
    "browser_youtube": browser_youtube,
    "browser_gmail": browser_gmail,
    "browser_github": browser_github,
    "volume_up": volume_up,
    "volume_down": volume_down,
    "volume_mute": volume_mute,
    "media_play_pause": media_play_pause,
    "media_next": media_next,
    "media_prev": media_prev,
    "screenshot": screenshot,
    "task_manager": open_task_manager,
    "show_desktop": show_desktop,
    "lock_pc": lock_pc,
    "lock_screen_timer": lock_screen_timer,
    "close_window": close_window_focused,
    "open_app": open_app,
    "speak_feedback": speak_feedback,
}


def run_action(name, *args):
    fn = ACTION_INDEX.get(name)
    if fn is None:
        return False
    try:
        return fn(*args)
    except Exception:
        return False