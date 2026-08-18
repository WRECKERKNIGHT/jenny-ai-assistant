import tkinter as tk
from tkinter import ttk, font, messagebox, scrolledtext
import threading
import time
import json
import math
import random
import os
import sys
import subprocess
import webbrowser
import urllib.request
import urllib.parse
import datetime
import wave
import struct
import tempfile

try:
    import pyttsx3
    HAS_PYTTSX = True
except:
    HAS_PYTTSX = False

try:
    import requests as req_lib
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

BG = "#050508"
BG2 = "#0a0a12"
BG3 = "#101018"
GOLD = "#ffd700"
GOLD_DIM = "#b8960f"
GOLD_GLOW = "#ffe44d"
WHITE = "#ffffff"
GRAY = "#888888"
GRAY_DIM = "#555555"
GREEN = "#00ff88"
RED = "#ff4444"
CYAN = "#00ccff"
PURPLE = "#aa66ff"
ORANGE = "#ff8800"
TEXT = "#cccccc"
TEXT_DIM = "#666666"
BORDER = "rgba(255,215,0,0.15)"
PANEL_BG = "#0c0c14"
PANEL_BG2 = "#0e0e16"
CANVAS_BG = "#060610"

SERVER_URL = "http://127.0.0.1:5000"

class JennyDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("J.E.N.N.Y v2.0 — Desktop AI Assistant")
        self.root.configure(bg=BG)
        self.W = 1440
        self.H = 900
        self.root.geometry(f"{self.W}x{self.H}")
        self.root.minsize(1200, 750)
        self.running = True
        self.server_running = False
        self.greeting_done = False
        self.wake_listening = False
        self.chat_history = []
        self.cpu_history = [0] * 60
        self.ram_history = [0] * 60
        self.net_sent_history = [0] * 60
        self.net_recv_history = [0] * 60
        self.viz_bars = [0] * 32
        self.system_data = {}
        self.last_greeting = 0
        self.last_activity = time.time()
        self._init_fonts()
        self._init_voice()
        self._init_ui()
        self._check_server()
        self._start_monitoring()
        self._start_wake_word()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_fonts(self):
        self.font_title = ("Segoe UI", 22, "bold")
        self.font_sub = ("Consolas", 10)
        self.font_body = ("Segoe UI", 10)
        self.font_small = ("Segoe UI", 9)
        self.font_tiny = ("Segoe UI", 8)
        self.font_code = ("Consolas", 10)
        self.font_large = ("Segoe UI", 14)
        self.font_giant = ("Segoe UI", 36, "bold")

    def _init_voice(self):
        self.voice_engine = None
        if HAS_PYTTSX:
            try:
                self.voice_engine = pyttsx3.init()
                voices = self.voice_engine.getProperty('voices')
                best = None
                for v in voices:
                    n = v.name.lower()
                    if any(k in n for k in ['zira', 'hazel', 'susan', 'female', 'aria', 'samantha']):
                        best = v; break
                if not best and voices:
                    best = voices[0]
                if best:
                    self.voice_engine.setProperty('voice', best.id)
                self.voice_engine.setProperty('rate', 180)
                self.voice_engine.setProperty('volume', 1.0)
            except:
                self.voice_engine = None

    def _speak(self, text):
        def _do():
            try:
                if self.voice_engine:
                    self.voice_engine.say(text)
                    self.voice_engine.runAndWait()
            except:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _init_ui(self):
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._build_status_bar()
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.content.columnconfigure(0, weight=3)
        self.content.columnconfigure(1, weight=5)
        self.content.columnconfigure(2, weight=3)
        self.content.rowconfigure(0, weight=1)
        self.left_frame = tk.Frame(self.content, bg=PANEL_BG, highlightbackground=GOLD_DIM, highlightthickness=1)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        self.center_frame = tk.Frame(self.content, bg=PANEL_BG, highlightbackground=GOLD_DIM, highlightthickness=1)
        self.center_frame.grid(row=0, column=1, sticky="nsew", padx=3)
        self.right_frame = tk.Frame(self.content, bg=PANEL_BG, highlightbackground=GOLD_DIM, highlightthickness=1)
        self.right_frame.grid(row=0, column=2, sticky="nsew", padx=(3, 0))
        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()
        self._build_waiting_screen()

    def _build_status_bar(self):
        bar = tk.Frame(self.main, bg=BG2, height=38, highlightbackground=GOLD_DIM, highlightthickness=1)
        bar.pack(fill=tk.X, pady=(0, 2))
        bar.pack_propagate(False)
        left = tk.Frame(bar, bg=BG2)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self.status_jenny = tk.Label(left, text="✦ J.E.N.N.Y v2.0", font=("Segoe UI", 11, "bold"), fg=GOLD, bg=BG2)
        self.status_jenny.pack(side=tk.LEFT, pady=6)
        tk.Label(left, text="  |  ", font=self.font_small, fg=GRAY_DIM, bg=BG2).pack(side=tk.LEFT)
        self.status_server = tk.Label(left, text="● Checking...", font=self.font_small, fg=GRAY, bg=BG2)
        self.status_server.pack(side=tk.LEFT, pady=6)
        self.status_time = tk.Label(bar, text="", font=self.font_small, fg=GRAY, bg=BG2)
        self.status_time.pack(side=tk.RIGHT, padx=10)
        self.status_cpu = tk.Label(bar, text="CPU: --%", font=self.font_small, fg=GRAY, bg=BG2)
        self.status_cpu.pack(side=tk.RIGHT, padx=5)
        self.status_ram = tk.Label(bar, text="RAM: --%", font=self.font_small, fg=GRAY, bg=BG2)
        self.status_ram.pack(side=tk.RIGHT, padx=5)
        self._update_clock()

    def _build_left_panel(self):
        tk.Label(self.left_frame, text="SYSTEM MONITOR", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(pady=(8, 2), anchor="w", padx=10)
        self.cpu_canvas = self._make_graph(self.left_frame, "CPU Usage", CYAN)
        self.ram_canvas = self._make_graph(self.left_frame, "RAM Usage", PURPLE)
        self.disk_canvas = self._make_disk_bar(self.left_frame)
        self.net_canvas = self._make_graph(self.left_frame, "Network I/O", GREEN)
        tk.Label(self.left_frame, text="VOICE VISUALIZER", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(pady=(10, 2), anchor="w", padx=10)
        self.viz_canvas = tk.Canvas(self.left_frame, height=60, bg=CANVAS_BG, highlightthickness=0)
        self.viz_canvas.pack(fill=tk.X, padx=8, pady=(0, 8))

    def _make_graph(self, parent, title, color):
        f = tk.Frame(parent, bg=PANEL_BG)
        f.pack(fill=tk.X, padx=8, pady=3)
        tk.Label(f, text=title, font=self.font_tiny, fg=GRAY, bg=PANEL_BG).pack(anchor="w")
        c = tk.Canvas(f, height=50, bg=CANVAS_BG, highlightthickness=0)
        c.pack(fill=tk.X)
        return c

    def _make_disk_bar(self, parent):
        f = tk.Frame(parent, bg=PANEL_BG)
        f.pack(fill=tk.X, padx=8, pady=3)
        tk.Label(f, text="Disk Usage", font=self.font_tiny, fg=GRAY, bg=PANEL_BG).pack(anchor="w")
        c = tk.Canvas(f, height=20, bg=CANVAS_BG, highlightthickness=0)
        c.pack(fill=tk.X)
        return c

    def _build_center_panel(self):
        hw_frame = tk.Frame(self.center_frame, bg=PANEL_BG)
        hw_frame.pack(fill=tk.X, padx=6, pady=(6, 3))
        tk.Label(hw_frame, text="HARDWARE SPECS", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(anchor="w", padx=4)
        self.specs_text = tk.Text(hw_frame, height=5, bg=CANVAS_BG, fg=TEXT, font=self.font_code, relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED, insertbackground=GOLD, selectbackground=GOLD_DIM)
        self.specs_text.pack(fill=tk.X, padx=4, pady=4)
        self.specs_text.configure(state=tk.NORMAL)
        self.specs_text.insert(tk.END, "Initializing...")
        self.specs_text.configure(state=tk.DISABLED)
        chat_frame = tk.Frame(self.center_frame, bg=PANEL_BG)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=3)
        tk.Label(chat_frame, text="CONVERSATION", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(anchor="w", padx=4)
        self.chat_display = tk.Text(chat_frame, bg=CANVAS_BG, fg=TEXT, font=self.font_body, relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED, insertbackground=GOLD, selectbackground=GOLD_DIM, padx=8, pady=8)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.chat_display.tag_configure("user", foreground=CYAN)
        self.chat_display.tag_configure("jenny", foreground=GOLD)
        self.chat_display.tag_configure("system", foreground=GRAY)
        self.chat_display.tag_configure("error", foreground=RED)
        input_frame = tk.Frame(self.center_frame, bg=PANEL_BG)
        input_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.user_input = tk.Entry(input_frame, bg=BG3, fg=WHITE, font=self.font_large, relief=tk.FLAT, insertbackground=GOLD)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 6))
        self.user_input.bind("<Return>", self._send_message)
        self.user_input.bind("<FocusIn>", lambda e: self._reset_idle_timer())
        send_btn = tk.Button(input_frame, text="SEND  ✦", font=("Segoe UI", 10, "bold"), bg=GOLD_DIM, fg=BG, relief=tk.FLAT, activebackground=GOLD, cursor="hand2", command=lambda: self._send_message(None))
        send_btn.pack(side=tk.RIGHT, ipady=6, ipadx=12)
        mic_btn = tk.Button(input_frame, text="🎤", font=("Segoe UI", 12), bg=BG3, fg=GOLD, relief=tk.FLAT, activebackground=BG2, cursor="hand2", command=self._voice_input)
        mic_btn.pack(side=tk.RIGHT, ipady=4, padx=(0, 6))

    def _build_right_panel(self):
        tk.Label(self.right_frame, text="MOBILE PAIRING", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(pady=(8, 2), anchor="w", padx=10)
        self.qr_frame = tk.Frame(self.right_frame, bg=CANVAS_BG)
        self.qr_frame.pack(fill=tk.X, padx=8, pady=4)
        self.qr_label = tk.Label(self.qr_frame, text="📱\nPair your phone\nvia QR code", font=self.font_small, fg=GRAY, bg=CANVAS_BG, justify=tk.CENTER)
        self.qr_label.pack(pady=20, padx=10)
        self.qr_btn = tk.Button(self.right_frame, text="Generate QR Code", font=self.font_small, bg=GOLD_DIM, fg=BG, relief=tk.FLAT, activebackground=GOLD, cursor="hand2", command=self._generate_qr)
        self.qr_btn.pack(pady=4, padx=8, fill=tk.X)
        tk.Label(self.right_frame, text="CLIPBOARD ASSISTANT", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(pady=(14, 2), anchor="w", padx=10)
        self.clip_text = tk.Text(self.right_frame, height=4, bg=CANVAS_BG, fg=TEXT, font=self.font_code, relief=tk.FLAT, wrap=tk.WORD, state=tk.NORMAL, insertbackground=GOLD, selectbackground=GOLD_DIM)
        self.clip_text.pack(fill=tk.X, padx=8, pady=4)
        clip_btn_frame = tk.Frame(self.right_frame, bg=PANEL_BG)
        clip_btn_frame.pack(fill=tk.X, padx=8, pady=2)
        tk.Button(clip_btn_frame, text="Read Clipboard", font=self.font_tiny, bg=BG3, fg=TEXT, relief=tk.FLAT, activebackground=BG2, cursor="hand2", command=self._read_clipboard).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(clip_btn_frame, text="Clear", font=self.font_tiny, bg=BG3, fg=TEXT, relief=tk.FLAT, activebackground=BG2, cursor="hand2", command=lambda: self.clip_text.delete("1.0", tk.END)).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))
        tk.Label(self.right_frame, text="QUICK ACTIONS", font=("Segoe UI", 9, "bold"), fg=GOLD_DIM, bg=PANEL_BG).pack(pady=(14, 4), anchor="w", padx=10)
        actions = [
            ("Open Gmail", "open gmail"), ("Open GitHub", "open github"),
            ("YouTube", "open youtube"), ("Weather", "weather"),
            ("News Headlines", "news"), ("System Info", "system info"),
            ("List Processes", "list processes"), ("Screenshot", "screenshot"),
        ]
        btn_grid = tk.Frame(self.right_frame, bg=PANEL_BG)
        btn_grid.pack(fill=tk.X, padx=8, pady=(0, 8))
        for i, (label, cmd) in enumerate(actions):
            r, c = divmod(i, 2)
            b = tk.Button(btn_grid, text=label, font=self.font_tiny, bg=BG3, fg=TEXT, relief=tk.FLAT, activebackground=BG2, cursor="hand2", command=lambda c=cmd: self._quick_action(c))
            b.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

    def _build_waiting_screen(self):
        self.waiting = tk.Frame(self.root, bg=BG)
        self.waiting.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.waiting_canvas = tk.Canvas(self.waiting, bg=BG, highlightthickness=0)
        self.waiting_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_waiting()

    def _draw_waiting(self):
        if not self.running:
            return
        self.waiting_canvas.delete("all")
        W = self.waiting.winfo_width() or self.W
        H = self.waiting.winfo_height() or self.H
        cx, cy = W // 2, H // 2
        t = time.time()
        for i in range(20):
            x = (math.sin(t * 0.3 + i * 0.7) * 200 + cx)
            y = (math.cos(t * 0.2 + i * 0.9) * 120 + cy)
            sz = 2 + math.sin(t + i) * 1.5
            b = int(40 + 30 * math.sin(t * 0.5 + i))
            self.waiting_canvas.create_oval(x-sz, y-sz, x+sz, y+sz, fill=f"#{b:02x}{b:02x}{int(b*1.2):02x}", outline="")
        pulse = 0.5 + 0.5 * math.sin(t * 2)
        ga = int(200 * pulse)
        self.waiting_canvas.create_text(cx, cy - 40, text="J.E.N.N.Y", font=("Segoe UI", 32, "bold"), fill=f"#{ga:02x}{min(255,212+ga//5):02x}{min(255,255):02x}")
        self.waiting_canvas.create_text(cx, cy + 10, text="Waiting for server...", font=("Segoe UI", 12), fill=GRAY)
        self.waiting_canvas.create_text(cx, cy + 40, text="Start server.py  |  python server.py", font=("Consolas", 10), fill=GRAY_DIM)
        self.waiting_canvas.create_text(cx, cy + 70, text="Or press R to retry connection", font=self.font_small, fill=GRAY_DIM)
        dot_count = int(t * 2) % 4
        dots = "." * dot_count
        self.waiting_canvas.create_text(cx, cy + 100, text=f"Connecting{dots}", font=self.font_small, fill=GOLD_DIM)
        if not self.server_running:
            self.root.after(500, self._draw_waiting)

    def _check_server(self):
        def _check():
            try:
                urllib.request.urlopen(f"{SERVER_URL}/api/system-status", timeout=3)
                self.server_running = True
                self.root.after(0, self._on_server_connected)
            except:
                self.server_running = False
                self.root.after(0, self._on_server_disconnected)
        threading.Thread(target=_check, daemon=True).start()

    def _on_server_connected(self):
        self.waiting.place_forget()
        self.status_server.config(text="● Online", fg=GREEN)
        if not self.greeting_done:
            self.greeting_done = True
            self._get_greeting()

    def _on_server_disconnected(self):
        self.waiting.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.status_server.config(text="● Offline", fg=RED)
        self.root.after(5000, self._check_server)

    def _get_greeting(self):
        def _fetch():
            try:
                r = urllib.request.urlopen(f"{SERVER_URL}/api/greeting", timeout=5)
                data = json.loads(r.read())
                g = data.get("greeting", "Hello Boss!")
                self.root.after(0, lambda: self._add_chat("jenny", g))
                self._speak(g)
            except:
                g = "Hello Boss! Server connected."
                self.root.after(0, lambda: self._add_chat("jenny", g))
                self._speak(g)
        threading.Thread(target=_fetch, daemon=True).start()

    def _add_chat(self, sender, text):
        self.chat_display.config(state=tk.NORMAL)
        ts = datetime.datetime.now().strftime("%H:%M")
        if sender == "user":
            self.chat_display.insert(tk.END, f"\n[{ts}] You: ", "user")
            self.chat_display.insert(tk.END, f"{text}\n", "user")
        elif sender == "jenny":
            self.chat_display.insert(tk.END, f"\n[{ts}] Jenny: ", "jenny")
            self.chat_display.insert(tk.END, f"{text}\n", "jenny")
        elif sender == "system":
            self.chat_display.insert(tk.END, f"{text}\n", "system")
        elif sender == "error":
            self.chat_display.insert(tk.END, f"{text}\n", "error")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_history.append({"sender": sender, "text": text, "time": ts})

    def _send_message(self, event=None):
        text = self.user_input.get().strip()
        if not text:
            return
        self.user_input.delete(0, tk.END)
        self._add_chat("user", text)
        self.last_activity = time.time()
        self._animate_viz_active()
        def _send():
            try:
                payload = json.dumps({"input": text}).encode("utf-8")
                r = urllib.request.Request(f"{SERVER_URL}/api/chat", data=payload, headers={"Content-Type": "application/json"})
                resp = urllib.request.urlopen(r, timeout=30)
                data = json.loads(resp.read())
                reply = data.get("reply", "No response, Boss.")
                self.root.after(0, lambda: self._add_chat("jenny", reply))
                self._speak(reply)
            except Exception as e:
                self.root.after(0, lambda: self._add_chat("error", f"Error: {str(e)}"))
            finally:
                self.root.after(0, self._animate_viz_idle)
        threading.Thread(target=_send, daemon=True).start()

    def _voice_input(self):
        self._add_chat("system", "🎤 Listening... (say something)")
        self._speak("I'm listening, Boss.")
        def _listen():
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio = r.listen(source, timeout=5, phrase_time_limit=10)
                text = r.recognize_google(audio)
                self.root.after(0, lambda: self._process_voice(text))
            except ImportError:
                self.root.after(0, lambda: self._add_chat("error", "Install SpeechRecognition: pip install SpeechRecognition pyaudio"))
            except Exception as e:
                self.root.after(0, lambda: self._add_chat("error", f"Voice error: {str(e)}"))
        threading.Thread(target=_listen, daemon=True).start()

    def _process_voice(self, text):
        self._add_chat("user", f"🎤 {text}")
        self.user_input.delete(0, tk.END)
        self.user_input.insert(0, text)
        self._send_message()

    def _quick_action(self, cmd):
        self.user_input.delete(0, tk.END)
        self.user_input.insert(0, cmd)
        self._send_message()

    def _read_clipboard(self):
        try:
            r = subprocess.run(['powershell', '-command', 'Get-Clipboard'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            clip = r.stdout.strip()
            if clip:
                self.clip_text.delete("1.0", tk.END)
                self.clip_text.insert(tk.END, clip[:500])
        except:
            pass

    def _generate_qr(self):
        try:
            import qrcode
            from io import BytesIO
            from PIL import Image, ImageTk
            ip = self._get_local_ip()
            qr = qrcode.QRCode(version=1, box_size=4, border=2)
            qr.add_data(f"http://{ip}:5000")
            qr.make(fit=True)
            img = qr.make_image(fill_color=GOLD, back_color=CANVAS_BG)
            bio = BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)
            self._qr_photo = ImageTk.PhotoImage(Image.open(bio))
            self.qr_label.config(image=self._qr_photo, text="")
        except ImportError:
            self.qr_label.config(text="Install qrcode: pip install qrcode[pil]")
        except Exception as e:
            self.qr_label.config(text=f"QR Error: {str(e)}")

    def _get_local_ip(self):
        try:
            s = __import__('socket').socket(__import__('socket').AF_INET, __import__('socket').SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _start_monitoring(self):
        self._update_system()
        self._update_graphs()
        self._update_viz()

    def _update_system(self):
        if not self.running:
            return
        if self.server_running:
            def _fetch():
                try:
                    r = urllib.request.urlopen(f"{SERVER_URL}/api/system-status", timeout=5)
                    data = json.loads(r.read())
                    self.system_data = data
                    self.root.after(0, lambda: self._render_system(data))
                except:
                    pass
            threading.Thread(target=_fetch, daemon=True).start()
        self.root.after(3000, self._update_system)

    def _render_system(self, d):
        cpu = d.get("cpu", 0)
        ram = d.get("ram", 0)
        disk = d.get("disk_pct", 0)
        bat = d.get("battery_pct", 100)
        self.status_cpu.config(text=f"CPU: {cpu:.0f}%", fg=CYAN if cpu < 80 else RED)
        self.status_ram.config(text=f"RAM: {ram:.0f}%", fg=PURPLE if ram < 80 else RED)
        self.cpu_history.append(cpu)
        self.cpu_history.pop(0)
        self.ram_history.append(ram)
        self.ram_history.pop(0)
        self.specs_text.config(state=tk.NORMAL)
        self.specs_text.delete("1.0", tk.END)
        lines = [
            f"Hostname : {d.get('hostname', 'N/A')}",
            f"OS       : {d.get('os', 'N/A')}",
            f"CPU      : {d.get('cpu_name', 'N/A')}",
            f"CPU Load : {cpu:.1f}%",
            f"RAM      : {d.get('ram_used', '?')} / {d.get('ram_total', '?')} GB ({ram:.1f}%)",
            f"Disk Free: {d.get('disk_free', '?')} / {d.get('disk_total', '?')} GB ({disk:.1f}%)",
            f"Battery  : {bat:.0f}% {'⚡ Charging' if d.get('battery_charging') else ''}",
            f"Uptime   : {d.get('uptime', 'N/A')}",
            f"Net Sent : {d.get('net_sent', 0)/(1024*1024):.1f} MB",
            f"Net Recv : {d.get('net_recv', 0)/(1024*1024):.1f} MB",
        ]
        self.specs_text.insert(tk.END, "\n".join(lines))
        self.specs_text.config(state=tk.DISABLED)

    def _update_graphs(self):
        if not self.running:
            return
        self._draw_line_graph(self.cpu_canvas, self.cpu_history, CYAN, 100)
        self._draw_line_graph(self.ram_canvas, self.ram_history, PURPLE, 100)
        self._draw_disk_bar_graph(self.disk_canvas)
        self._draw_line_graph(self.net_canvas, self.net_sent_history, GREEN, max(max(self.net_sent_history), max(self.net_recv_history), 1))
        self.root.after(1000, self._update_graphs)

    def _draw_line_graph(self, canvas, data, color, max_val):
        canvas.delete("all")
        w = canvas.winfo_width() or 300
        h = canvas.winfo_height() or 50
        if not data or max_val == 0:
            return
        pts = []
        for i, v in enumerate(data):
            x = (i / (len(data) - 1)) * w
            y = h - (v / max_val) * (h - 4) - 2
            pts.append((x, y))
        for i in range(len(pts) - 1):
            canvas.create_line(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], fill=color, width=2)
        if pts:
            lx, ly = pts[-1]
            canvas.create_oval(lx-3, ly-3, lx+3, ly+3, fill=color, outline="")
        cur = data[-1]
        canvas.create_text(4, 4, text=f"{cur:.1f}%", fill=color, font=self.font_tiny, anchor="nw")

    def _draw_disk_bar_graph(self, canvas):
        canvas.delete("all")
        w = canvas.winfo_width() or 300
        h = canvas.winfo_height() or 20
        pct = self.system_data.get("disk_pct", 0)
        bar_w = (pct / 100) * (w - 4)
        color = GREEN if pct < 70 else ORANGE if pct < 90 else RED
        canvas.create_rectangle(2, 2, bar_w, h - 2, fill=color, outline="")
        canvas.create_text(w // 2, h // 2, text=f"{pct:.1f}%", fill=WHITE, font=self.font_tiny)

    def _update_viz(self):
        if not self.running:
            return
        canvas = self.viz_canvas
        canvas.delete("all")
        w = canvas.winfo_width() or 300
        h = 60
        n = len(self.viz_bars)
        bw = max(2, (w - n * 2) // n)
        for i in range(n):
            x = i * (bw + 2)
            val = self.viz_bars[i]
            bh = max(2, int(val / 100 * (h - 4)))
            color_h = int(40 + val * 1.8) % 256
            c = f"#{color_h:02x}{int(color_h*0.8):02x}{GOLD[1:3]}"
            canvas.create_rectangle(x, h - bh - 2, x + bw, h - 2, fill=GOLD_DIM if val < 50 else GOLD, outline="")
        if any(v > 0 for v in self.viz_bars):
            self.viz_bars = [max(0, v - random.uniform(2, 8)) for v in self.viz_bars]
        self.root.after(80, self._update_viz)

    def _animate_viz_active(self):
        self.viz_bars = [random.uniform(30, 95) for _ in self.viz_bars]

    def _animate_viz_idle(self):
        def _decay():
            for _ in range(15):
                self.viz_bars = [max(0, v - 3) for v in self.viz_bars]
                time.sleep(0.05)
        threading.Thread(target=_decay, daemon=True).start()

    def _update_clock(self):
        now = datetime.datetime.now()
        self.status_time.config(text=now.strftime("%a, %b %d  %H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _reset_idle_timer(self):
        self.last_activity = time.time()

    def _start_wake_word(self):
        def _listen():
            while self.running:
                time.sleep(1)
                if time.time() - self.last_activity < 30:
                    continue
                try:
                    import speech_recognition as sr
                    r = sr.Recognizer()
                    with sr.Microphone() as source:
                        r.adjust_for_ambient_noise(source, duration=0.3)
                        audio = r.listen(source, timeout=1, phrase_time_limit=3)
                    text = r.recognize_google(audio).lower()
                    if any(w in text for w in ["hey jenny", "hey friday", "hello jenny"]):
                        self.root.after(0, lambda: self._on_wake_detected())
                except:
                    time.sleep(2)
        self.wake_thread = threading.Thread(target=_listen, daemon=True)
        self.wake_thread.start()

    def _on_wake_detected(self):
        self.last_activity = time.time()
        self._add_chat("system", "👋 Wake word detected! I'm listening, Boss!")
        self._speak("Yes Boss? I'm listening.")
        self._animate_viz_active()
        def _listen_command():
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.3)
                    audio = r.listen(source, timeout=5, phrase_time_limit=10)
                text = r.recognize_google(audio)
                self.root.after(0, lambda: self._process_voice(text))
            except:
                self.root.after(0, lambda: self._add_chat("system", "Didn't catch that, Boss. Try again."))
        threading.Thread(target=_listen_command, daemon=True).start()

    def _on_close(self):
        self.running = False
        if self.voice_engine:
            try: self.voice_engine.stop()
            except: pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_intro_then_dashboard():
    def on_intro_done():
        dashboard = JennyDashboard()
        dashboard.run()
    intro = SolarSystemIntro(on_complete=on_intro_done)
    intro.run()


if __name__ == "__main__":
    from intro import SolarSystemIntro
    run_intro_then_dashboard()
