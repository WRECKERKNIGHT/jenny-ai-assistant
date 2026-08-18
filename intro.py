import tkinter as tk
import math
import random
import time

class SolarSystemIntro:
    def __init__(self, on_complete=None):
        self.root = tk.Tk()
        self.root.title("J.E.N.N.Y")
        self.root.configure(bg="#050508")
        self.root.attributes("-fullscreen", True)
        self.on_complete = on_complete
        self.W = self.root.winfo_screenwidth()
        self.H = self.root.winfo_screenheight()
        self.cx = self.W // 2
        self.cy = self.H // 2
        self.running = True
        self.phase = 0
        self.alpha = 0
        self.press_alpha = 0
        self.show_press = False
        self.stars = []
        self.planets = []
        self.particles = []
        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg="#050508", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._init_stars()
        self._init_planets()
        self.root.bind("<Button-1>", self._on_click)
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<Escape>", lambda e: self._exit())
        self._animate()

    def _init_stars(self):
        for _ in range(300):
            self.stars.append({
                "x": random.randint(0, self.W), "y": random.randint(0, self.H),
                "size": random.uniform(0.5, 2.5), "brightness": random.randint(100, 255),
                "twinkle": random.uniform(0.02, 0.08), "phase": random.uniform(0, 6.28)
            })

    def _init_planets(self):
        defs = [
            {"dist": 60, "size": 4, "color": "#8B7355", "speed": 0.025},
            {"dist": 95, "size": 6, "color": "#E8CDA0", "speed": 0.018},
            {"dist": 135, "size": 7, "color": "#4A90D9", "speed": 0.015},
            {"dist": 175, "size": 5, "color": "#C1440E", "speed": 0.012},
            {"dist": 235, "size": 14, "color": "#C88B3A", "speed": 0.008},
            {"dist": 300, "size": 12, "color": "#EAD6A6", "speed": 0.006},
            {"dist": 360, "size": 9, "color": "#7EC8E3", "speed": 0.004},
            {"dist": 410, "size": 8, "color": "#3F54BA", "speed": 0.003},
        ]
        for d in defs:
            self.planets.append({**d, "angle": random.uniform(0, 6.28), "trail": []})

    def _blend(self, hex_color, factor):
        r = min(255, int(int(hex_color[1:3], 16) * factor + 5 * (1 - factor)))
        g = min(255, int(int(hex_color[3:5], 16) * factor + 5 * (1 - factor)))
        b = min(255, int(int(hex_color[5:7], 16) * factor + 5 * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_scene(self, t):
        for s in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * s["twinkle"] + s["phase"])
            b = int(s["brightness"] * tw * self.alpha)
            c = f"#{b:02x}{b:02x}{b:02x}"
            sz = s["size"] * (0.8 + 0.2 * tw)
            self.canvas.create_oval(s["x"]-sz, s["y"]-sz, s["x"]+sz, s["y"]+sz, fill=c, outline="", tags="scene")

        for p in self.planets:
            self.canvas.create_oval(
                self.cx - p["dist"]*self.alpha, self.cy - p["dist"]*self.alpha,
                self.cx + p["dist"]*self.alpha, self.cy + p["dist"]*self.alpha,
                outline="#0a0a18", width=1, dash=(2, 4), tags="scene"
            )

        glow_cols = [("#1a1000", 50), ("#2a1800", 40), ("#3a2200", 30), ("#FFA500", 20)]
        for col, sz in glow_cols:
            af = self.alpha * (0.3 + 0.1 * math.sin(t * 0.5))
            self.canvas.create_oval(self.cx-sz, self.cy-sz, self.cx+sz, self.cy+sz, fill=self._blend(col, af), outline="", tags="scene")

        br = int(255 * self.alpha)
        sc = f"#{min(255,br):02x}{min(255,int(br*0.85)):02x}{min(255,int(br*0.4)):02x}"
        self.canvas.create_oval(self.cx-18, self.cy-18, self.cx+18, self.cy+18, fill=sc, outline="#FFD700", width=1, tags="scene")

        for p in self.planets:
            p["angle"] += p["speed"]
            px = self.cx + math.cos(p["angle"]) * p["dist"] * self.alpha
            py = self.cy + math.sin(p["angle"]) * p["dist"] * 0.4 * self.alpha
            p["trail"].append((px, py))
            if len(p["trail"]) > 8:
                p["trail"].pop(0)
            for i, (tx, ty) in enumerate(p["trail"]):
                op = (i / len(p["trail"])) * 0.3 * self.alpha
                tc = self._blend(p["color"], op)
                tsz = p["size"] * 0.5 * (i / len(p["trail"]))
                self.canvas.create_oval(tx-tsz, ty-tsz, tx+tsz, ty+tsz, fill=tc, outline="", tags="scene")
            sz = p["size"] * self.alpha
            pc = self._blend(p["color"], self.alpha)
            self.canvas.create_oval(px-sz, py-sz, px+sz, py+sz, fill=pc, outline="", tags="scene")
            if "Saturn" in str(p) and sz > 4:
                rw, rh = sz*2.2, sz*0.5
                self.canvas.create_oval(px-rw, py-rh, px+rw, py+rh, outline=self._blend("#EAD6A6", self.alpha), width=1.5, tags="scene")

    def _draw_ui(self, t):
        if self.alpha > 0.3:
            ta = min(1.0, (self.alpha - 0.3) / 0.7)
            fs = int(72 * ta)
            gl = int(15 * (0.5 + 0.5 * math.sin(t * 0.8)))
            tc = f"#{min(255,gl):02x}{min(255,212+gl):02x}{min(255,255):02x}"
            self.canvas.create_text(self.cx, self.cy-80, text="J.E.N.N.Y", font=("Segoe UI", fs, "bold"), fill=tc, tags="scene")
            if ta > 0.5:
                sa = min(1.0, (ta - 0.5) / 0.5)
                gr = int(160 * sa)
                self.canvas.create_text(self.cx, self.cy-20, text="Just a Enhanced Neural Network for You", font=("Segoe UI", int(16*sa)), fill=f"#{gr:02x}{gr:02x}{min(255,gr+20):02x}", tags="scene")
                self.canvas.create_text(self.cx, self.cy+15, text="v2.0  |  Windows Desktop Edition", font=("Segoe UI", int(11*sa)), fill=f"#{int(100*sa):02x}{int(100*sa):02x}{int(110*sa):02x}", tags="scene")
        if self.show_press:
            self.press_alpha = min(1.0, self.press_alpha + 0.02)
            pulse = 0.6 + 0.4 * math.sin(t * 2)
            a = int(200 * self.press_alpha * pulse)
            self.canvas.create_text(self.cx, self.H-120, text="[ Press Anywhere to Start ]", font=("Segoe UI", 14), fill=f"#{a:02x}{a:02x}{min(255,a+30):02x}", tags="scene")

    def _animate(self):
        if not self.running:
            return
        t = time.time()
        self.canvas.delete("scene")
        if self.phase == 0:
            self.alpha = min(1.0, self.alpha + 0.008)
            if self.alpha >= 1.0:
                self.phase = 1
                self.root.after(1000, lambda: setattr(self, 'show_press', True))
        elif self.phase == 2:
            self.alpha = max(0, self.alpha - 0.03)
            if self.alpha <= 0:
                self.running = False
                self.root.destroy()
                if self.on_complete:
                    self.on_complete()
                return
        if random.random() < 0.3 and len(self.particles) < 50:
            self.particles.append({"x": random.randint(0, self.W), "y": self.H+5, "speed": random.uniform(0.5, 2), "size": random.uniform(0.5, 2), "brightness": random.randint(50, 150), "life": random.uniform(100, 300)})
        alive = []
        for p in self.particles:
            p["y"] -= p["speed"]
            p["life"] -= 1
            if p["life"] > 0 and p["y"] > -10:
                b = int(p["brightness"] * self.alpha * (p["life"]/300))
                self.canvas.create_oval(p["x"]-p["size"], p["y"]-p["size"], p["x"]+p["size"], p["y"]+p["size"], fill=f"#{min(255,b+30):02x}{min(255,b+10):02x}{b:02x}", outline="", tags="scene")
                alive.append(p)
        self.particles = alive
        self._draw_scene(t)
        self._draw_ui(t)
        self.root.after(16, self._animate)

    def _on_click(self, event):
        if self.show_press and self.phase == 1:
            self.phase = 2

    def _on_key(self, event):
        if self.show_press and self.phase == 1:
            self.phase = 2

    def _exit(self):
        self.running = False
        self.root.destroy()
        if self.on_complete:
            self.on_complete()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    intro = SolarSystemIntro(on_complete=lambda: print("Intro complete"))
    intro.run()
