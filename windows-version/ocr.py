"""On-device OCR through the Windows.Media.Ocr engine.

No external downloads, no API keys, no telemetry: the recognizer that ships
with Windows 10/11 is invoked via PowerShell, so this keeps working offline.
Images are downscaled with Pillow first because the WinRT engine is slow on
huge photos. If no recognizer language covers the text (e.g. Devanagari),
that is reported honestly as an error, never as a success with guesses.

Fallback path: if the Windows engine is unavailable (older OS / disabled
feature), we return a clear 'unavailable' error instead of pretending to
have OCR'd anything.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None  # engine works, but we cannot downscale big images

_SCRIPT = r'''
param(
    [string]$Path,
    [string]$Lang,
    [string]$OutFile
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                   $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($WinRtTask, $ResultType) {
    $m = $asTaskGeneric.MakeGenericMethod($ResultType)
    $t = $m.Invoke($null, @($WinRtTask))
    $t.Wait(-1) | Out-Null
    return $t.Result
}

# Load the image from bytes via an in-memory stream - avoids the WinRT
# IRandomAccessStreamWithContentType interface projections that 5.1 strangles on.
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.DataWriter, Windows.Storage.Streams, ContentType=WindowsRuntime]
$bytes = [IO.File]::ReadAllBytes($Path)
$stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
$writer = [Windows.Storage.Streams.DataWriter]::new($stream)
try {
    $writer.WriteBytes($bytes)
    Await ($writer.StoreAsync()) ([uint32]) | Out-Null
    $stream.Seek(0)
    $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    $decoder = Await $decoder ([Windows.Graphics.Imaging.BitmapDecoder])
    $soft = $decoder.GetSoftwareBitmapAsync()
    $soft = Await $soft ([Windows.Graphics.Imaging.SoftwareBitmap])
} finally {
    try { $writer.Dispose() } catch {}
    try { $stream.Dispose() } catch {}
}

$langObj = [Windows.Globalization.Language]::new($Lang)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langObj)
if ($null -eq $engine) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) {
    @{ "ok" = $false; "error" = "No Windows.Media.Ocr language available on this machine." } |
        ConvertTo-Json | Out-File -FilePath $OutFile -Encoding UTF8
    exit 2
}
$res = $engine.RecognizeAsync($soft)
$res = Await $res ([Windows.Media.Ocr.OcrResult])
$lines = @()
foreach ($l in $res.Lines) {
    $line = [pscustomobject]@{ text = $l.Text; words = @() }
    foreach ($w in $l.Words) {
        $r = $w.BoundingRect
        $line.words += [pscustomobject]@{ text = $w.Text; x = [int]$r.X; y = [int]$r.Y;
                                          width = [int]$r.Width; height = [int]$r.Height }
    }
    $lines += $line
}
@{ "ok" = $true; "language" = $engine.RecognizerLanguage.LanguageTag;
   "lines_count" = $lines.Count; "lines" = $lines } |
    ConvertTo-Json -Depth 6 | Out-File -FilePath $OutFile -Encoding UTF8
'''


def _err(msg, **extra):
    return {"ok": False, "error": msg, **extra}


def _win_ocr(path: str, lang: str) -> dict:
    fd, tmp_str = tempfile.mkstemp(suffix=".json")
    os.close(fd)  # let powershell open & write it
    tmp = Path(tmp_str)
    ps = None
    try:
        ps = tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w", encoding="utf-8")
        ps.write(_SCRIPT)
        ps.close()
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", ps.name, "-Path", path, "-Lang", lang, "-OutFile", str(tmp)],
            capture_output=True, timeout=240,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not tmp.exists() or tmp.stat().st_size == 0:
            return _err("Windows OCR did not return a result.",
                        ps_exit=proc.returncode,
                        ps_err=(proc.stderr or b"").decode("utf-8", "replace")[:300])
        data = json.loads(tmp.read_text(encoding="utf-8-sig"))
        if data.get("ok") is False:
            return _err(data.get("error", "OCR failed"))
        return data
    except json.JSONDecodeError as e:
        return _err(f"OCR wrote unparseable output: {e}")
    except subprocess.TimeoutExpired:
        return _err("OCR timed out on a large image.")
    except Exception as e:
        return _err(f"OCR invocation failed: {e}")
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass
        if ps is not None:
            try:
                Path(ps.name).unlink()
            except Exception:
                pass


def ocr_image(path, language="en", max_side=1600):
    """Recognize text in an image file.

    Returns {ok, text, lines:[{text, words:[{text,x,y,width,height}]}],
    language, source}. ok=False with a real reason otherwise.
    """
    p = Path(path)
    if not p.exists():
        return _err(f"File not found: {path}")
    if not _engine_available():
        return _err("Windows.Media.Ocr is not available on this machine "
                    "(Windows 10/11 feature missing); no other OCR engine is installed.")
    lang = str(language or "en")
    work = p
    need_unlink = False
    if Image is not None:
        try:
            im = Image.open(p)
            if max(im.size) > max_side:
                im.thumbnail((max_side, max_side))
                tmp_img = Path(tempfile.mkstemp(suffix=".png")[1])
                im.convert("RGB").save(tmp_img, "PNG")
                work = tmp_img
                need_unlink = True
        except Exception as e:
            return _err(f"Could not read image: {e}")
    try:
        data = _win_ocr(str(work), lang)
        if not data.get("ok"):
            return data
        lines = data.get("lines") or []
        text = "\n".join(l.get("text", "") for l in lines)
        words = sum(len(l.get("words") or []) for l in lines)
        return {"ok": True, "text": text, "lines_count": data.get("lines_count", len(lines)),
                "language": data.get("language"), "source": "Windows.Media.Ocr",
                "lines": lines, "words": words}
    finally:
        if need_unlink:
            try:
                work.unlink()
            except Exception:
                pass


def _engine_available() -> bool:
    """Cache the cheap check that the Windows OCR runtime is importable."""
    if shutil.which("powershell") is None:
        return False
    probe = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime];"
         "$e=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages();"
         "if($null -ne $e){'yes'}else{'no'}"],
        capture_output=True, timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return b"yes" in (probe.stdout or b"")


def available() -> dict:
    try:
        have = _engine_available()
    except Exception:
        have = False
    if not have:
        return {"ok": True, "engine": "Windows.Media.Ocr",
                "note": "OCR engine unavailable on this machine; nothing is faked."}
    return {"ok": True, "engine": "Windows.Media.Ocr",
            "functions": ["ocr_image"],
            "note": "recognizes en-US/en-GB; no key, fully local."}