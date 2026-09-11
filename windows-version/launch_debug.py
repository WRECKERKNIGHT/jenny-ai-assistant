import sys, os, threading, time, traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG = str(BASE_DIR / "run.log")

def wlog(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

try:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("=== LAUNCH ===\n")
except Exception:
    pass

def start_server():
    try:
        from waitress import serve
        sys.path.insert(0, str(BASE_DIR))
        import server
        wlog("server imported OK")
        threading.Thread(target=server.update_telemetry, daemon=True).start()
        wlog("telemetry started")
        wlog(f"waitress {getattr(serve, '__module__', '')}")
        serve(server.app, host="0.0.0.0", port=3005, threads=8)
    except Exception as e:
        wlog(f"SERVER EXC: {traceback.format_exc()}")

wlog("starting server thread")
t = threading.Thread(target=start_server, daemon=True)
t.start()

time.sleep(4)

import urllib.request
for i in range(20):
    try:
        urllib.request.urlopen("http://127.0.0.1:3005/modes.html", timeout=3)
        wlog("server up")
        break
    except Exception:
        time.sleep(0.5)

wlog("importing webview")
import webview
wlog(f"webview ok {getattr(webview,'__version__','?')}")

window = webview.create_window(
    "J.E.N.N.Y v2.0",
    "http://127.0.0.1:3005/modes.html",
    width=1440, height=900,
    min_size=(1200, 750),
    background_color="#000000",
    text_select=True,
)
wlog("window created, calling start")

try:
    webview.start(debug=False)
    wlog("webview.start returned (window closed normally)")
except Exception as e:
    wlog(f"WEBVIEW EXC: {traceback.format_exc()}")

wlog("LAUNCHER EXITING")
