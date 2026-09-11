# ⚡ J.E.N.N.Y. AI ASSISTANT

> **Just Every Necessary Neural Yearning** — Autonomous AI System Assistant & macOS Desktop Companion inspired by JARVIS & FRIDAY.

---

## ✨ Key Capabilities & Features

### 🎙️ 1. 100% Female Voice Core & Instant Streaming Latency
* **Female Voice Engine**: Exclusively 100% female voices (Primary default token: **Tia Mirza**).
* **0ms Text Output Rendering**: Streaming speech synthesis with zero delay.
* **Voice Dictation Formatting**: Speak `"new line"`, `"comma"`, `"period"`, `"question mark"`, `"clear input"`, or `"send message"`.

### 🔮 2. Translucent Glassmorphism UI & High-Contrast Design System
* **Visual Palette**: Strict luxury styling using **Deep Black**, **Pure White**, **Metallic Silver**, and **Luxury Gold**.
* **Crystal Glass Panels**: All floating cards, process managers, and file explorers feature translucent glass backgrounds (`backdrop-filter: blur(30px)`).

### 🖥️ 3. Unrestricted macOS System Controls
* **Full Shell Access**: `/api/execute-shell` executes arbitrary zsh/bash commands securely.
* **Hardware Controls**: Volume, brightness, display sleep/wake, RAM purge (`/usr/bin/purge`), Wi-Fi toggle, battery health, and screenshot capture.
* **Process & Window Manager**: Kill processes, switch active apps, toggle dark mode, and open files.

### 📱 4. Android Mobile Remote Control Companion App & PWA
* **Mobile Remote UI**: Access `http://<YOUR_MAC_IP>:3000/mobile.html` from any phone on your network.
* **🚗 "On My Way Home" Workflow**: Remote wake display, caffeinate Mac, set volume to 80%, and open YouTube.
* **PWA & APK Builder**: Install directly to Android Home Screen or package using `./scripts/build-android-apk.sh`.

### 🤖 5. Autonomous Multi-Step Agentic Workflow Engine
* Execute complex multi-step instructions autonomously:
  * *"Open Antigravity, click on screen-time project, polish the UI, generate a README, and push to GitHub."*
  * *"Organize desktop, purge RAM, and run system report."*

### 🧠 6. AI Training Hub & Personal Preference Memory
* **Visual Training Hub**: Manage custom rules, macros, facts, user names, and assistant tone (`Witty`, `Formal`, `Friendly`, `Executive Jarvis`).
* **Custom Rules**: Speak `"train rule [trigger] -> [action/reply]"`.
* **Voice Macros**: Speak `"train macro [trigger] = [cmd1, cmd2]"`.

---

## 🚀 Quick Start & Installation

### Prerequisites
* macOS 12+ (Monterey, Ventura, Sonoma, Sequoia)
* Node.js 18+

### Setup Commands

```bash
# 1. Clone repository
git clone https://github.com/WRECKERKNIGHT/jenny-ai-assistant.git
cd jenny-ai-assistant

# 2. Install dependencies
npm install

# 3. Start JENNY Server & macOS Native Apps
npm start
```

---

## 📱 Mobile Remote App (Android)

1. Open **Chrome** on your Android phone.
2. Navigate to: `http://<YOUR_MAC_IP>:3000/mobile.html`
3. Tap **Options Menu** $\rightarrow$ **"Add to Home Screen"** or **"Install App"**.

---

## 📄 License
MIT License. Developed with ❤️ for advanced autonomous desktop & mobile AI control.
