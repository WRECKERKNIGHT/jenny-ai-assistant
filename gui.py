"""
J.E.N.N.Y - Windows Overlay GUI
Transparent overlay with widgets, voice control, and system status
Performance optimized for low-end PCs
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import datetime
import os
import sys
import urllib.request
from pathlib import Path

SERVER_URL = "http://localhost:5000"
CHECK_INTERVAL = 10000

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class JennyOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("J.E.N.N.Y")
        self.root.geometry("420x700+50+50")
        self.root.configure(bg='#0a0a0f')
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.92)
        self.root.overrideredirect(False)

        self.is_overlay = False
        self.is_listening = False
        self.chat_history = []
        self.tts_engine = None
        self.server_connected = False

        self._setup_ui()
        self._setup_tts()
        self._start_background_tasks()
        self._center_window()

    def _center_window(self):
        w = 420
        h = 700
        x = self.root.winfo_screenwidth() - w - 20
        y = 50
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _setup_ui(self):
        self.title_frame = tk.Frame(self.root, bg='#0a0a0f', height=35)
        self.title_frame.pack(fill=tk.X, padx=10, pady=(8, 2))
        self.title_frame.pack_propagate(False)

        self.title_label = tk.Label(
            self.title_frame, text="J.E.N.N.Y",
            font=("Segoe UI", 11, "bold"), fg="#00d4ff", bg='#0a0a0f'
        )
        self.title_label.pack(side=tk.LEFT, padx=5)

        self.mode_btn = tk.Button(
            self.title_frame, text="Overlay", font=("Segoe UI", 8),
            fg="#ffffff", bg="#1a1a2e", activebackground="#16213e",
            activeforeground="#00d4ff", bd=0, padx=8, pady=2,
            command=self.toggle_mode
        )
        self.mode_btn.pack(side=tk.RIGHT, padx=3)

        self.min_btn = tk.Button(
            self.title_frame, text="_", font=("Segoe UI", 8),
            fg="#ffffff", bg="#1a1a2e", activebackground="#16213e",
            bd=0, padx=6, pady=2, command=self.minimize
        )
        self.min_btn.pack(side=tk.RIGHT, padx=2)

        self.close_btn = tk.Button(
            self.title_frame, text="X", font=("Segoe UI", 8),
            fg="#ff4757", bg="#1a1a2e", activebackground="#2d1b1b",
            bd=0, padx=6, pady=2, command=self.root.quit
        )
        self.close_btn.pack(side=tk.RIGHT, padx=2)

        self.widgets_frame = tk.Frame(self.root, bg='#0a0a0f')
        self.widgets_frame.pack(fill=tk.X, padx=10, pady=5)

        self._create_system_widget()
        self._create_weather_widget()

        separator = tk.Frame(self.root, bg='#1a1a3e', height=1)
        separator.pack(fill=tk.X, padx=15, pady=5)

        self.chat_frame = tk.Frame(self.root, bg='#0a0a0f')
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.chat_canvas = tk.Canvas(
            self.chat_frame, bg='#0a0a0f', highlightthickness=0, bd=0
        )
        self.chat_scrollbar = tk.Scrollbar(
            self.chat_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview
        )
        self.chat_inner = tk.Frame(self.chat_canvas, bg='#0a0a0f')

        self.chat_inner.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.create_window((0, 0), window=self.chat_inner, anchor="nw")
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)

        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.input_frame = tk.Frame(self.root, bg='#0a0a0f', height=50)
        self.input_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.input_frame.pack_propagate(False)

        self.input_entry = tk.Entry(
            self.input_frame, font=("Segoe UI", 10),
            bg='#1a1a2e', fg='#e0e0e0', insertbackground='#00d4ff',
            bd=0, relief=tk.FLAT
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=6, padx=(0, 5))
        self.input_entry.bind("<Return>", self._on_send)
        self.input_entry.bind("<FocusIn>", lambda e: self.input_entry.configure(bg='#16213e'))
        self.input_entry.bind("<FocusOut>", lambda e: self.input_entry.configure(bg='#1a1a2e'))

        self.send_btn = tk.Button(
            self.input_frame, text=">", font=("Segoe UI", 11, "bold"),
            fg="#00d4ff", bg="#1a1a2e", activebackground="#16213e",
            activeforeground="#00d4ff", bd=0, padx=10,
            command=self._on_send
        )
        self.send_btn.pack(side=tk.RIGHT, fill=tk.Y)

        self.mic_btn = tk.Button(
            self.input_frame, text="🎤", font=("Segoe UI", 10),
            fg="#ff6b6b", bg="#1a1a2e", activebackground="#16213e",
            bd=0, padx=6, command=self._toggle_listening
        )
        self.mic_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 3))

        self._add_system_message("J.E.N.N.Y is online. Ready for your commands, Boss!")

        self.drag_data = {"x": 0, "y": 0}
        self.title_frame.bind("<Button-1>", self._start_drag)
        self.title_frame.bind("<B1-Motion>", self._on_drag)
        self.title_label.bind("<Button-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)

    def _create_system_widget(self):
        sys_frame = tk.Frame(self.widgets_frame, bg='#12122a', bd=0, highlightthickness=0)
        sys_frame.pack(fill=tk.X, pady=3)

        header = tk.Frame(sys_frame, bg='#12122a')
        header.pack(fill=tk.X, padx=10, pady=(6, 2))
        tk.Label(header, text="System", font=("Segoe UI", 8, "bold"),
                 fg="#00d4ff", bg='#12122a').pack(side=tk.LEFT)

        self.cpu_label = tk.Label(sys_frame, text="CPU: --%",
                                   font=("Segoe UI", 8), fg="#a0a0a0", bg='#12122a')
        self.cpu_label.pack(anchor=tk.W, padx=10)

        self.ram_label = tk.Label(sys_frame, text="RAM: --%",
                                   font=("Segoe UI", 8), fg="#a0a0a0", bg='#12122a')
        self.ram_label.pack(anchor=tk.W, padx=10)

        self.disk_label = tk.Label(sys_frame, text="Disk: --%",
                                    font=("Segoe UI", 8), fg="#a0a0a0", bg='#12122a')
        self.disk_label.pack(anchor=tk.W, padx=10)

        self.net_label = tk.Label(sys_frame, text="Net: --",
                                   font=("Segoe UI", 8), fg="#a0a0a0", bg='#12122a')
        self.net_label.pack(anchor=tk.W, padx=10, pady=(0, 6))

    def _create_weather_widget(self):
        weather_frame = tk.Frame(self.widgets_frame, bg='#12122a', bd=0, highlightthickness=0)
        weather_frame.pack(fill=tk.X, pady=3)

        header = tk.Frame(weather_frame, bg='#12122a')
        header.pack(fill=tk.X, padx=10, pady=(6, 2))
        tk.Label(header, text="Weather", font=("Segoe UI", 8, "bold"),
                 fg="#00d4ff", bg='#12122a').pack(side=tk.LEFT)

        self.weather_label = tk.Label(weather_frame, text="Loading...",
                                       font=("Segoe UI", 8), fg="#a0a0a0", bg='#12122a')
        self.weather_label.pack(anchor=tk.W, padx=10, pady=(0, 6))

    def _add_chat_message(self, text, is_user=False):
        msg_frame = tk.Frame(self.chat_inner, bg='#0a0a0f')
        msg_frame.pack(fill=tk.X, pady=3, padx=5)

        if is_user:
            bg_color = '#1a3a5c'
            fg_color = '#e0e0e0'
            anchor = tk.E
        else:
            bg_color = '#1a1a3e'
            fg_color = '#00d4ff' if "boss" in text.lower() or "system" in text.lower() else '#e0e0e0'
            anchor = tk.W

        bubble = tk.Label(
            msg_frame, text=text, font=("Segoe UI", 9),
            fg=fg_color, bg=bg_color, wraplength=320,
            justify=tk.LEFT, padx=8, pady=5
        )
        bubble.pack(anchor=anchor, padx=3)

        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _add_system_message(self, text):
        msg_frame = tk.Frame(self.chat_inner, bg='#0a0a0f')
        msg_frame.pack(fill=tk.X, pady=2, padx=10)
        tk.Label(
            msg_frame, text=text, font=("Segoe UI", 8),
            fg="#666666", bg='#0a0a0f', wraplength=320, justify=tk.CENTER
        ).pack(anchor=tk.CENTER)
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _on_send(self, event=None):
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, tk.END)
        self._add_chat_message(text, is_user=True)

        threading.Thread(target=self._process_command, args=(text,), daemon=True).start()

    def _process_command(self, text):
        try:
            import urllib.request
            import urllib.parse
            req = urllib.request.Request(
                f"{SERVER_URL}/api/chat",
                data=json.dumps({"input": text}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                reply = data.get("reply", "I didn't understand that, Boss!")
                self.root.after(0, self._add_chat_message, reply, False)
                if TTS_AVAILABLE and self.tts_engine:
                    threading.Thread(target=self._speak, args=(reply,), daemon=True).start()
        except Exception as e:
            self.root.after(0, self._add_chat_message,
                          f"Connection error. Is the server running? ({e})", False)

    def _speak(self, text):
        try:
            if self.tts_engine:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
        except Exception:
            pass

    def _setup_tts(self):
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                voices = self.tts_engine.getProperty('voices')
                for v in voices:
                    if any(name in v.name.lower() for name in ['david', 'mark']):
                        self.tts_engine.setProperty('voice', v.id)
                        break
                self.tts_engine.setProperty('rate', 175)
                self.tts_engine.setProperty('volume', 0.9)
            except Exception:
                self.tts_engine = None

    def _toggle_listening(self):
        if not SR_AVAILABLE:
            self._add_system_message("Speech recognition not available. Install SpeechRecognition and pyaudio.")
            return

        if self.is_listening:
            self.is_listening = False
            self.mic_btn.configure(fg="#ff6b6b")
            self._add_system_message("Voice input stopped.")
            return

        self.is_listening = True
        self.mic_btn.configure(fg="#00ff00")
        self._add_system_message("Listening... Speak now, Boss!")
        threading.Thread(target=self._listen_voice, daemon=True).start()

    def _listen_voice(self):
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)

            text = recognizer.recognize_google(audio).lower()
            self.root.after(0, self._add_chat_message, text, True)
            self.root.after(0, self._process_command, text)

        except sr.WaitTimeoutError:
            self.root.after(0, self._add_system_message, "No speech detected. Try again, Boss!")
        except sr.UnknownValueError:
            self.root.after(0, self._add_system_message, "Couldn't understand that. Try again, Boss!")
        except Exception as e:
            self.root.after(0, self._add_system_message, f"Voice error: {e}")
        finally:
            self.is_listening = False
            self.root.after(0, lambda: self.mic_btn.configure(fg="#ff6b6b"))

    def toggle_mode(self):
        if self.is_overlay:
            self.root.attributes('-topmost', True)
            self.root.attributes('-alpha', 0.92)
            self.root.overrideredirect(False)
            self.mode_btn.configure(text="Overlay")
            self.is_overlay = False
        else:
            self.root.attributes('-topmost', True)
            self.root.attributes('-alpha', 0.75)
            self.root.overrideredirect(True)
            self.mode_btn.configure(text="Window")
            self.is_overlay = True

    def minimize(self):
        self.root.iconify()

    def _start_drag(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + (event.x - self.drag_data["x"])
        y = self.root.winfo_y() + (event.y - self.drag_data["y"])
        self.root.geometry(f"+{x}+{y}")

    def _update_system_status(self):
        try:
            if PSUTIL_AVAILABLE:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                net = psutil.net_io_counters()

                self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
                self.ram_label.configure(text=f"RAM: {mem.percent:.1f}% ({mem.used / (1024**3):.1f}/{mem.total / (1024**3):.1f} GB)")
                self.disk_label.configure(text=f"Disk: {disk.percent:.1f}% ({disk.free / (1024**3):.1f} GB free)")
                self.net_label.configure(text=f"Net: {net.bytes_recv / (1024**2):.0f} MB recv")
        except Exception:
            pass

    def _update_weather(self):
        try:
            import urllib.request
            with urllib.request.urlopen(
                "https://api.open-meteo.com/v1/forecast?latitude=26.8467&longitude=80.9462&current_weather=true&temperature_unit=celsius",
                timeout=10
            ) as resp:
                data = json.loads(resp.read().decode())
                cw = data.get("current_weather", {})
                temp = cw.get("temperature", 0)
                code = cw.get("weathercode", 0)
                codes = {0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
                        45: "Fog", 51: "Light Drizzle", 61: "Light Rain", 63: "Rain",
                        71: "Light Snow", 73: "Snow", 80: "Showers", 95: "Thunderstorm"}
                desc = codes.get(code, "Unknown")
                self.weather_label.configure(text=f"{temp}°C - {desc} - Lucknow")
        except Exception:
            self.weather_label.configure(text="Weather unavailable (offline)")

    def _get_greeting(self):
        now = datetime.datetime.now()
        hour = now.hour
        if hour < 6:
            greet = "Good night"
        elif hour < 12:
            greet = "Good morning"
        elif hour < 17:
            greet = "Good afternoon"
        elif hour < 21:
            greet = "Good evening"
        else:
            greet = "Good night"

        day = now.strftime("%A, %B %d, %Y")
        return f"{greet}, Harshit! It's {day}. All systems ready for you, Boss!"

    def _start_background_tasks(self):
        self._update_system_status()
        self._update_weather()

        self.root.after(CHECK_INTERVAL, self._periodic_update)

    def _periodic_update(self):
        self._update_system_status()
        self._update_weather()
        self.root.after(CHECK_INTERVAL, self._periodic_update)

    def run(self):
        greeting = self._get_greeting()
        self.root.after(500, self._add_system_message, greeting)

        if TTS_AVAILABLE and self.tts_engine:
            try:
                speak_text = greeting.replace("Boss!", "Boss.")
                threading.Thread(target=self._speak, args=(speak_text,), daemon=True).start()
            except Exception:
                pass

        self.root.mainloop()


class JennyMainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("J.E.N.N.Y - Windows AI Assistant")
        self.root.geometry("900x650")
        self.root.configure(bg='#0a0a0f')

        self.tts_engine = None
        self.is_listening = False
        self._setup_ui()
        self._setup_tts()
        self._load_greeting()

    def _setup_ui(self):
        left_panel = tk.Frame(self.root, bg='#0f0f1a', width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
        left_panel.pack_propagate(False)

        logo_frame = tk.Frame(left_panel, bg='#0f0f1a')
        logo_frame.pack(fill=tk.X, pady=15, padx=15)
        tk.Label(logo_frame, text="J.E.N.N.Y", font=("Segoe UI", 16, "bold"),
                 fg="#00d4ff", bg='#0f0f1a').pack(anchor=tk.W)
        tk.Label(logo_frame, text="AI Assistant", font=("Segoe UI", 9),
                 fg="#666666", bg='#0f0f1a').pack(anchor=tk.W)

        nav_items = [
            ("💬 Chat", self._show_chat),
            ("📊 System", self._show_system),
            ("📝 Notes", self._show_notes),
            ("✅ Todos", self._show_todos),
            ("🔐 Vault", self._show_vault),
            ("🌐 Web", self._show_web),
        ]

        for text, cmd in nav_items:
            btn = tk.Button(left_panel, text=text, font=("Segoe UI", 10),
                          fg="#a0a0a0", bg='#0f0f1a', activebackground='#1a1a3e',
                          activeforeground='#00d4ff', bd=0, anchor=tk.W,
                          padx=15, pady=8, command=cmd)
            btn.pack(fill=tk.X)

        tk.Label(left_panel, text="", bg='#0f0f1a').pack(expand=True)

        overlay_btn = tk.Button(
            left_panel, text="🔲 Launch Overlay",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff", bg="#1a3a5c",
            activebackground="#00d4ff", activeforeground="#000000",
            bd=0, padx=15, pady=10,
            command=self._launch_overlay
        )
        overlay_btn.pack(fill=tk.X, padx=15, pady=10)

        self.main_frame = tk.Frame(self.root, bg='#0a0a0f')
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._show_chat()

    def _clear_main(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

    def _show_chat(self):
        self._clear_main()

        header = tk.Frame(self.main_frame, bg='#0a0a0f')
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="Chat with Jenny", font=("Segoe UI", 14, "bold"),
                 fg="#00d4ff", bg='#0a0a0f').pack(side=tk.LEFT)

        chat_area = tk.Frame(self.main_frame, bg='#0a0a0f')
        chat_area.pack(fill=tk.BOTH, expand=True, padx=15)

        self.chat_canvas = tk.Canvas(chat_area, bg='#0a0a0f', highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(chat_area, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_inner = tk.Frame(self.chat_canvas, bg='#0a0a0f')
        self.chat_inner.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.create_window((0, 0), window=self.chat_inner, anchor="nw")
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        input_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        input_frame.pack(fill=tk.X, padx=15, pady=10)

        self.main_input = tk.Entry(
            input_frame, font=("Segoe UI", 11),
            bg='#1a1a2e', fg='#e0e0e0', insertbackground='#00d4ff',
            bd=0, relief=tk.FLAT
        )
        self.main_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=8, padx=(0, 8))
        self.main_input.bind("<Return>", self._on_main_send)

        tk.Button(
            input_frame, text="Send", font=("Segoe UI", 10, "bold"),
            fg="#00d4ff", bg="#1a1a2e", activebackground="#16213e",
            bd=0, padx=15, pady=8, command=self._on_main_send
        ).pack(side=tk.RIGHT)

    def _add_main_chat_msg(self, text, is_user=False):
        msg_frame = tk.Frame(self.chat_inner, bg='#0a0a0f')
        msg_frame.pack(fill=tk.X, pady=3, padx=5)

        bg = '#1a3a5c' if is_user else '#1a1a3e'
        fg = '#e0e0e0'
        anchor = tk.E if is_user else tk.W

        bubble = tk.Label(msg_frame, text=text, font=("Segoe UI", 10),
                         fg=fg, bg=bg, wraplength=500, justify=tk.LEFT, padx=10, pady=6)
        bubble.pack(anchor=anchor, padx=5)

        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _on_main_send(self, event=None):
        text = self.main_input.get().strip()
        if not text:
            return
        self.main_input.delete(0, tk.END)
        self._add_main_chat_msg(text, True)
        threading.Thread(target=self._main_process, args=(text,), daemon=True).start()

    def _main_process(self, text):
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{SERVER_URL}/api/chat",
                data=json.dumps({"input": text}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                reply = data.get("reply", "I didn't understand that, Boss!")
                self.root.after(0, self._add_main_chat_msg, reply, False)
        except Exception as e:
            self.root.after(0, self._add_main_chat_msg,
                          f"Server error: {e}", False)

    def _show_system(self):
        self._clear_main()
        header = tk.Frame(self.main_frame, bg='#0a0a0f')
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="System Monitor", font=("Segoe UI", 14, "bold"),
                 fg="#00d4ff", bg='#0a0a0f').pack(side=tk.LEFT)

        info_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        info_frame.pack(fill=tk.BOTH, expand=True, padx=15)

        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            stats = [
                f"CPU Usage: {cpu:.1f}%",
                f"CPU Cores: {psutil.cpu_count()}",
                f"RAM: {mem.percent:.1f}% ({mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} GB)",
                f"Disk: {disk.percent:.1f}% ({disk.free / (1024**3):.1f} GB free)",
                f"Uptime: {int((time.time() - psutil.boot_time()) / 3600)}h {int(((time.time() - psutil.boot_time()) % 3600) / 60)}m"
            ]

            bat = psutil.sensors_battery()
            if bat:
                stats.append(f"Battery: {bat.percent}% {'(Charging)' if bat.power_plugged else ''}")

            for stat in stats:
                tk.Label(info_frame, text=stat, font=("Consolas", 11),
                        fg="#e0e0e0", bg='#0a0a0f', anchor=tk.W).pack(fill=tk.X, pady=3)
        except Exception as e:
            tk.Label(info_frame, text=f"Error: {e}", font=("Segoe UI", 11),
                    fg="#ff4757", bg='#0a0a0f').pack(anchor=tk.W)

    def _show_notes(self):
        self._clear_main()
        header = tk.Frame(self.main_frame, bg='#0a0a0f')
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="Notes", font=("Segoe UI", 14, "bold"),
                 fg="#00d4ff", bg='#0a0a0f').pack(side=tk.LEFT)

        self.notes_text = tk.Text(
            self.main_frame, font=("Segoe UI", 10),
            bg='#12122a', fg='#e0e0e0', insertbackground='#00d4ff',
            bd=0, relief=tk.FLAT, wrap=tk.WORD
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        btn_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        tk.Button(btn_frame, text="Save", font=("Segoe UI", 9),
                 fg="#00d4ff", bg="#1a1a2e", bd=0, padx=10,
                 command=self._save_notes).pack(side=tk.LEFT, padx=3)

    def _save_notes(self):
        text = self.notes_text.get("1.0", tk.END).strip()
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{SERVER_URL}/api/notes",
                data=json.dumps({"text": text}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def _show_todos(self):
        self._clear_main()
        header = tk.Frame(self.main_frame, bg='#0a0a0f')
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="Todos", font=("Segoe UI", 14, "bold"),
                 fg="#00d4ff", bg='#0a0a0f').pack(side=tk.LEFT)

        self.todos_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        self.todos_frame.pack(fill=tk.BOTH, expand=True, padx=15)

        add_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        add_frame.pack(fill=tk.X, padx=15, pady=10)
        self.todo_input = tk.Entry(add_frame, font=("Segoe UI", 10),
                                    bg='#1a1a2e', fg='#e0e0e0', bd=0)
        self.todo_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 5))
        self.todo_input.bind("<Return>", self._add_todo)
        tk.Button(add_frame, text="+ Add", font=("Segoe UI", 9),
                 fg="#00d4ff", bg="#1a1a2e", bd=0, padx=10,
                 command=self._add_todo).pack(side=tk.RIGHT)

        self._load_todos()

    def _add_todo(self, event=None):
        text = self.todo_input.get().strip()
        if not text:
            return
        self.todo_input.delete(0, tk.END)
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{SERVER_URL}/api/todos",
                data=json.dumps({"action": "add", "text": text}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
            self._load_todos()
        except Exception:
            pass

    def _load_todos(self):
        for w in self.todos_frame.winfo_children():
            w.destroy()
        try:
            import urllib.request
            with urllib.request.urlopen(f"{SERVER_URL}/api/todos", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for i, todo in enumerate(data.get("todos", [])):
                    fg = "#666666" if todo.get("done") else "#e0e0e0"
                    prefix = "✓ " if todo.get("done") else "○ "
                    tk.Label(self.todos_frame, text=f"{prefix}{todo.get('text', '')}",
                            font=("Segoe UI", 10), fg=fg, bg='#0a0a0f',
                            anchor=tk.W).pack(fill=tk.X, pady=2)
        except Exception:
            pass

    def _show_vault(self):
        self._clear_main()
        header = tk.Frame(self.main_frame, bg='#0a0a0f')
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="Memory Vault", font=("Segoe UI", 14, "bold"),
                 fg="#00d4ff", bg='#0a0a0f').pack(side=tk.LEFT)

        vault_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        vault_frame.pack(fill=tk.BOTH, expand=True, padx=15)

        try:
            import urllib.request
            with urllib.request.urlopen(f"{SERVER_URL}/api/vault", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for entry in data.get("entries", []):
                    tk.Label(vault_frame, text=f"• {entry.get('text', '')}",
                            font=("Segoe UI", 10), fg="#e0e0e0", bg='#0a0a0f',
                            anchor=tk.W, wraplength=600).pack(fill=tk.X, pady=3)
        except Exception:
            pass

    def _show_web(self):
        self._clear_main()
        header = tk.Frame(self.main_frame, bg='#0a0a0f')
        header.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(header, text="Web Shortcuts", font=("Segoe UI", 14, "bold"),
                 fg="#00d4ff", bg='#0a0a0f').pack(side=tk.LEFT)

        shortcuts = [
            ("Google", "https://google.com"),
            ("YouTube", "https://youtube.com"),
            ("Instagram", "https://instagram.com"),
            ("GitHub", "https://github.com"),
            ("Twitter/X", "https://x.com"),
            ("Reddit", "https://reddit.com"),
            ("Spotify", "https://spotify.com"),
        ]

        shortcuts_frame = tk.Frame(self.main_frame, bg='#0a0a0f')
        shortcuts_frame.pack(fill=tk.BOTH, expand=True, padx=15)

        for name, url in shortcuts:
            btn = tk.Button(
                shortcuts_frame, text=name, font=("Segoe UI", 11),
                fg="#00d4ff", bg="#1a1a3e", activebackground="#16213e",
                activeforeground="#ffffff", bd=0, padx=15, pady=8, anchor=tk.W,
                command=lambda u=url: __import__('webbrowser').open(u)
            )
            btn.pack(fill=tk.X, pady=3)

    def _launch_overlay(self):
        overlay = JennyOverlay()
        overlay.run()

    def _setup_tts(self):
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                voices = self.tts_engine.getProperty('voices')
                for v in voices:
                    if any(name in v.name.lower() for name in ['david', 'mark']):
                        self.tts_engine.setProperty('voice', v.id)
                        break
                self.tts_engine.setProperty('rate', 175)
                self.tts_engine.setProperty('volume', 0.9)
            except Exception:
                self.tts_engine = None

    def _load_greeting(self):
        try:
            import urllib.request
            with urllib.request.urlopen(f"{SERVER_URL}/api/greeting", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                greeting = data.get("greeting", "Welcome, Boss!")
                self.root.after(500, lambda: self._show_greeting_popup(greeting))
        except Exception:
            self.root.after(500, lambda: self._show_greeting_popup(
                "Welcome to J.E.N.N.Y, Boss! Server might be starting up..."))

    def _show_greeting_popup(self, greeting):
        popup = tk.Toplevel(self.root)
        popup.title("Welcome")
        popup.geometry("500x200")
        popup.configure(bg='#0a0a0f')
        popup.attributes('-topmost', True)

        x = (popup.winfo_screenwidth() - 500) // 2
        y = (popup.winfo_screenheight() - 200) // 2
        popup.geometry(f"500x200+{x}+{y}")

        tk.Label(popup, text="J.E.N.N.Y", font=("Segoe UI", 20, "bold"),
                fg="#00d4ff", bg='#0a0a0f').pack(pady=(15, 5))
        tk.Label(popup, text=greeting, font=("Segoe UI", 10),
                fg="#e0e0e0", bg='#0a0a0f', wraplength=450, justify=tk.CENTER).pack(pady=5)
        tk.Button(popup, text="Let's Go, Boss!", font=("Segoe UI", 11, "bold"),
                 fg="#000000", bg="#00d4ff", activebackground="#00a0cc",
                 bd=0, padx=20, pady=8, command=popup.destroy).pack(pady=10)

        if self.tts_engine and greeting:
            def speak():
                try:
                    self.tts_engine.say(greeting.replace("Boss!", "Boss."))
                    self.tts_engine.runAndWait()
                except Exception:
                    pass
            threading.Thread(target=speak, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "main"

    if mode == "overlay":
        app = JennyOverlay()
        app.run()
    elif mode == "server":
        import server
    else:
        app = JennyMainApp()
        app.run()
