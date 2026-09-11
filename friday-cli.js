#!/usr/bin/env node

const readline = require('readline');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Share storage paths with the Express server
const VAULT_FILE = path.join(__dirname, 'vault.json');
const OFFLINE_MEMORY_FILE = path.join(__dirname, 'offline_memory.json');

// Helper to speak using native OS speech tools (Samantha voice on mac, SAPI on Windows)
function speak(text) {
  if (!text) return;
  const cleanText = text.replace(/"/g, '\\"').replace(/\n/g, ' ');
  const platform = os.platform();
  
  if (platform === 'darwin') {
    // macOS: Use Samantha voice
    exec(`say -v Samantha "${cleanText}"`);
  } else if (platform === 'win32') {
    // Windows: Use PowerShell SAPI Synth
    const psCommand = `Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("${cleanText.replace(/"/g, '`"')}")`;
    exec(`powershell -Command "${psCommand}"`);
  }
}

// System app launcher
function openApp(appName) {
  const platform = os.platform();
  if (!/^[a-zA-Z0-9\s.\-_]+$/.test(appName)) {
    console.log('\x1b[31m[FRIDAY] Invalid application format.\x1b[0m');
    speak("Invalid application profile, BOSS.");
    return;
  }
  
  if (platform === 'darwin') {
    exec(`open -a "${appName}"`, (err) => {
      if (err) {
        console.log(`\x1b[31m[FRIDAY] Failed to open app "${appName}". Verify if installed.\x1b[0m`);
        speak(`Failed to launch ${appName}, BOSS.`);
      } else {
        console.log(`\x1b[32m[FRIDAY] Opening application: "${appName}"\x1b[0m`);
        speak(`Launching ${appName}, BOSS.`);
      }
    });
  } else if (platform === 'win32') {
    exec(`start "" "${appName}"`, (err) => {
      if (err) {
        console.log(`\x1b[31m[FRIDAY] Failed to open app "${appName}".\x1b[0m`);
        speak(`Failed to launch ${appName}.`);
      } else {
        console.log(`\x1b[32m[FRIDAY] Opening application: "${appName}"\x1b[0m`);
        speak(`Launching ${appName}, BOSS.`);
      }
    });
  }
}

// Redirect website
function openUrl(url) {
  const platform = os.platform();
  let targetUrl = url.trim();
  if (!/^https?:\/\//i.test(targetUrl)) {
    targetUrl = 'https://' + targetUrl;
  }
  
  console.log(`\x1b[32m[FRIDAY] Redirecting browser connection to: "${targetUrl}"\x1b[0m`);
  speak(`Opening website, BOSS.`);
  
  if (platform === 'darwin') {
    exec(`open "${targetUrl}"`);
  } else if (platform === 'win32') {
    exec(`start "" "${targetUrl}"`);
  } else {
    exec(`xdg-open "${targetUrl}"`);
  }
}

// Local System control wrapper (macOS AppleScript calls)
function runSystemControl(action, value) {
  const platform = os.platform();
  if (platform !== 'darwin') {
    console.log('\x1b[31m[FRIDAY] Native controls are currently optimized for macOS.\x1b[0m');
    speak("System controls unavailable on this platform.");
    return;
  }

  switch (action) {
    case 'volume':
      if (value === 'mute') {
        exec('osascript -e "set volume with output muted"', () => {
          console.log('\x1b[32m[FRIDAY] System Volume Muted\x1b[0m');
          speak("Muted, BOSS.");
        });
      } else if (value === 'unmute') {
        exec('osascript -e "set volume without output muted"', () => {
          console.log('\x1b[32m[FRIDAY] System Volume Unmuted\x1b[0m');
          speak("Unmuted, BOSS.");
        });
      } else {
        const level = parseInt(value, 10);
        exec(`osascript -e "set volume output volume ${level}"`, () => {
          console.log(`\x1b[32m[FRIDAY] System Volume Set to ${level}%\x1b[0m`);
          speak(`Volume set to ${level} percent, BOSS.`);
        });
      }
      break;

    case 'media':
      let script = '';
      if (value === 'play' || value === 'pause') {
        script = 'tell application "System Events" to key code 49';
      } else if (value === 'next') {
        script = 'tell application "System Events" to key code 124 using {control down, command down}'; // simulated next track
      } else if (value === 'previous') {
        script = 'tell application "System Events" to key code 123 using {control down, command down}'; // prev track
      }
      
      exec(`osascript -e '${script}'`, () => {
        console.log(`\x1b[32m[FRIDAY] Media control command "${value}" triggered\x1b[0m`);
        speak("Command executed.");
      });
      break;

    case 'lock':
      exec('pmset displaysleepnow', () => {
        console.log('\x1b[31m[FRIDAY] Locking screen interface...\x1b[0m');
        speak("Locking screen, BOSS.");
      });
      break;

    case 'sleep':
      exec("osascript -e 'tell application \"System Events\" to sleep'", () => {
        console.log('\x1b[31m[FRIDAY] Putting PC to sleep...\x1b[0m');
        speak("Sleeping, BOSS.");
      });
      break;

    case 'spotify':
      const sanitized = value.replace(/"/g, '\\"');
      const spotifyScript = `
        tell application "Spotify"
          activate
          delay 0.5
          play track "spotify:search:${sanitized}"
        end tell
      `;
      exec(`osascript -e '${spotifyScript}'`, (err) => {
        if (err) {
          console.log("\x1b[31m[FRIDAY] Spotify error: " + err.message + "\x1b[0m");
          speak("Spotify control error.");
        } else {
          console.log("\x1b[32m[FRIDAY] Playing \"" + value + "\" on Spotify\x1b[0m");
          speak("Playing " + value + " on Spotify, BOSS.");
        }
      });
      break;

    case 'brightness':
      const brightnessVal = parseFloat(value);
      if (isNaN(brightnessVal) || brightnessVal < 0 || brightnessVal > 100) {
        console.log('\x1b[31m[FRIDAY] Brightness must be 0 to 100%\x1b[0m');
        speak("Invalid brightness level.");
        return;
      }
      const fraction = brightnessVal / 100;
      const pythonCmd = `python3 -c "import ctypes; cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'); ds = ctypes.CDLL('/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices'); display_id = cg.CGMainDisplayID(); ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]; ds.DisplayServicesSetBrightness(display_id, ${fraction})"`;
      exec(pythonCmd, (err) => {
        if (err) {
          console.log('\x1b[31m[FRIDAY] Brightness set error: ' + err.message + '\x1b[0m');
          speak("Error adjusting brightness.");
        } else {
          console.log(`\x1b[32m[FRIDAY] System Brightness Set to ${brightnessVal}%\x1b[0m`);
          speak(`Brightness set to ${brightnessVal} percent, BOSS.`);
        }
      });
      break;

    case 'restart':
      exec("osascript -e 'tell application \"System Events\" to restart'", () => {
        console.log('\x1b[31m[FRIDAY] PC restarting...\x1b[0m');
        speak("Workstation restarting, BOSS.");
      });
      break;

    case 'shutdown':
      exec("osascript -e 'tell application \"System Events\" to shut down'", () => {
        console.log('\x1b[31m[FRIDAY] PC shutting down...\x1b[0m');
        speak("Powering down systems, BOSS.");
      });
      break;

    case 'screenshot':
      const screenshotPath = path.join(os.homedir(), 'Desktop', `Friday_Screenshot_${Date.now()}.png`);
      exec(`screencapture -x "${screenshotPath}"`, (err) => {
        if (err) {
          console.log('\x1b[31m[FRIDAY] Screenshot error: ' + err.message + '\x1b[0m');
          speak("Error taking screenshot.");
        } else {
          console.log(`\x1b[32m[FRIDAY] Screenshot saved to Desktop as ${path.basename(screenshotPath)}\x1b[0m`);
          speak("Screenshot saved to Desktop, BOSS.");
        }
      });
      break;

    case 'empty-trash':
      exec("osascript -e 'tell application \"Finder\" to empty trash'", (err) => {
        if (err) {
          console.log('\x1b[31m[FRIDAY] Trash clear error: ' + err.message + '\x1b[0m');
          speak("Error emptying trash.");
        } else {
          console.log('\x1b[32m[FRIDAY] Trash emptied successfully.\x1b[0m');
          speak("Trash emptied successfully, BOSS.");
        }
      });
      break;
  }
}

// Memory Vault Storage Operations
function loadVault() {
  try {
    if (fs.existsSync(VAULT_FILE)) {
      return JSON.parse(fs.readFileSync(VAULT_FILE, 'utf8'));
    }
  } catch (e) {
    console.error('Error reading vault database:', e);
  }
  return [];
}

function saveVault(items) {
  fs.writeFileSync(VAULT_FILE, JSON.stringify(items, null, 2), 'utf8');
}

function addToVault(text) {
  const items = loadVault();
  const newItem = {
    id: Date.now().toString(),
    text: text.trim(),
    date: new Date().toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
  };
  items.push(newItem);
  saveVault(items);
  console.log(`\x1b[32m[FRIDAY] Vault Entry Saved: "${text.trim()}"\x1b[0m`);
  speak(`Saved that to your vault, BOSS.`);
}

function listVault() {
  const items = loadVault();
  console.log('\n\x1b[33m================= SECURE MEMORY VAULT =================\x1b[0m');
  if (items.length === 0) {
    console.log('Your vault is empty, BOSS.');
  } else {
    items.forEach((item, idx) => {
      console.log(`[${item.date}] ${idx + 1}. ${item.text}`);
    });
  }
  console.log('\x1b[33m=======================================================\x1b[0m\n');
}

function clearVault() {
  saveVault([]);
  console.log('\x1b[31m[FRIDAY] Vault cleared completely.\x1b[0m');
  speak("Vault cleared, BOSS.");
}

// Offline context variables load/save
function loadMemory() {
  try {
    if (fs.existsSync(OFFLINE_MEMORY_FILE)) {
      return JSON.parse(fs.readFileSync(OFFLINE_MEMORY_FILE, 'utf8'));
    }
  } catch (e) {}
  return {};
}

function saveMemory(mem) {
  fs.writeFileSync(OFFLINE_MEMORY_FILE, JSON.stringify(mem, null, 2), 'utf8');
}

// Todo List operations
const TODO_FILE = path.join(__dirname, 'todo.json');
function loadTodos() {
  try { if (fs.existsSync(TODO_FILE)) return JSON.parse(fs.readFileSync(TODO_FILE, 'utf8')); } catch (e) {}
  return [];
}
function saveTodos(todos) { fs.writeFileSync(TODO_FILE, JSON.stringify(todos, null, 2), 'utf8'); }

function listTodos() {
  const todos = loadTodos();
  console.log('\n\x1b[36m================= ACTIVE TASK MATRIX =================\x1b[0m');
  if (todos.length === 0) {
    console.log('No pending tasks, BOSS.');
  } else {
    todos.forEach((todo, idx) => {
      const status = todo.completed ? '\x1b[32m[x]\x1b[0m' : '\x1b[31m[ ]\x1b[0m';
      console.log(`${idx + 1}. ${status} ${todo.text}`);
    });
  }
  console.log('\x1b[36m======================================================\x1b[0m\n');
}

// Real-time System Diagnostics
function checkSystem() {
  const platform = os.platform();
  console.log('\n\x1b[35m================ FRIDAY DIAGNOSTICS =================\x1b[0m');
  console.log(`Host Platform  : ${platform}`);
  console.log(`Kernel Arch    : ${os.arch()}`);
  
  // Calculate real memory usage
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const memPercent = Math.round(((totalMem - freeMem) / totalMem) * 100);
  console.log(`RAM Footprint  : ${memPercent}% (${Math.round((totalMem - freeMem)/1024/1024)}MB / ${Math.round(totalMem/1024/1024)}MB)`);
  
  if (platform === 'darwin') {
    exec('pmset -g batt', (err, stdout) => {
      if (!err && stdout) {
        const lines = stdout.split('\n');
        if (lines[1]) console.log(`Power Level    : ${lines[1].trim()}`);
      }
      console.log('\x1b[35m=====================================================\x1b[0m\n');
    });
  } else {
    console.log('\x1b[35m=====================================================\x1b[0m\n');
  }
}

// Chat integration
async function chatQuery(message) {
  // Check memory locally first for name details
  const mem = loadMemory();
  const query = message.toLowerCase();
  
  const nameMatch = message.match(/my name is\s+(.+)/i) || message.match(/call me\s+(.+)/i);
  if (nameMatch) {
    mem.name = nameMatch[1].trim();
    saveMemory(mem);
    const rep = `Understood. I will call you ${mem.name}, BOSS.`;
    console.log(`\n\x1b[33mFRIDAY:\x1b[0m ${rep}`);
    speak(rep);
    return;
  }

  // Try local Express chat server (maintains Gemini context and history)
  try {
    const response = await fetch(`http://localhost:${process.env.PORT || 3000}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await response.json();
    if (data.success) {
      console.log(`\n\x1b[33mFRIDAY:\x1b[0m ${data.reply}`);
      speak(data.reply);
      return;
    }
  } catch (_) {
    // Fallback if Express server offline
  }
  
  let reply = '';
  
  if (query.includes('what is my name') || query.includes('who am i')) {
    reply = mem.name ? `You told me your name is ${mem.name}, BOSS.` : "You haven't told me your name yet, BOSS.";
  } else if (query.includes('hello') || query.includes('hi ') || query.includes('hey')) {
    const gn = mem.name ? `, ${mem.name}` : '';
    reply = `Greetings${gn}, BOSS. Systems are functional. Ready for commands.`;
  } else if (query.includes('how are you')) {
    reply = "I am operating at peak efficiency, BOSS. Ready for your instructions.";
  } else if (query.includes('who are you') || query.includes('your name')) {
    reply = "I am FRIDAY, your personal user interface, BOSS.";
  } else if (query.includes('time')) {
    reply = `The time is currently ${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}, BOSS.`;
  } else {
    const fallbacks = [
      "Command parsed, BOSS.",
      "Standing by for next directive, BOSS.",
      "Input registered. Systems optimal."
    ];
    reply = fallbacks[Math.floor(Math.random() * fallbacks.length)];
  }
  
  console.log(`\n\x1b[33mFRIDAY:\x1b[0m ${reply}`);
  speak(reply);
}

// Logo Art
const ASCII_LOGO = `
\x1b[36m███████╗██████╗ ██╗██████╗  █████╗ ██╗   ██╗
██╔════╝██╔══██╗██║██╔══██╗██╔══██╗╚██╗ ██╔╝
█████╗  ██████╔╝██║██║  ██║███████║ ╚████╔╝ 
██╔══╝  ██╔══██╗██║██║  ██║██╔══██║  ╚██╔╝  
██║     ██║  ██║██║██████╔╝██║  ██║   ██║   
╚═╝     ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   
================ INTEGRATED AGENT INTERFACE ================
\x1b[0m`;

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

console.clear();
console.log(ASCII_LOGO);
console.log('F.R.I.D.A.Y. terminal client active. Control PC, manage vaults, or chat.');
console.log('Directives: "open AppName", "remember keys are on shelf", "list vault", "volume 60", "lock", "exit"\n');
speak("FRIDAY active. Monitoring inputs, BOSS.");

function prompt() {
  rl.question('\x1b[34mBOSS@FRIDAY:~$ \x1b[0m', async (line) => {
    const input = line.trim();
    const cmdLower = input.toLowerCase();
    
    if (cmdLower === 'exit' || cmdLower === 'shutdown' || cmdLower === 'quit') {
      speak("Understood, BOSS. Terminating shell connection.");
      rl.close();
      return;
    }
    
    if (input === '') {
      prompt();
      return;
    }
    
    // Command Router
    if (cmdLower.startsWith('open ') && !cmdLower.includes('website') && !cmdLower.includes('.')) {
      const app = input.substring(5).trim();
      openApp(app);
    } else if (cmdLower.includes('open website ') || cmdLower.includes('go to ') || (cmdLower.startsWith('open ') && cmdLower.includes('.'))) {
      let web = '';
      if (cmdLower.includes('open website ')) web = input.substring(cmdLower.indexOf('open website ') + 13);
      else if (cmdLower.includes('go to ')) web = input.substring(cmdLower.indexOf('go to ') + 6);
      else web = input.substring(5);
      openUrl(web);
    } else if (cmdLower.startsWith('volume ')) {
      const vol = input.substring(7).trim();
      runSystemControl('volume', vol);
    } else if (cmdLower === 'mute' || cmdLower === 'unmute') {
      runSystemControl('volume', cmdLower);
    } else if (cmdLower.startsWith('brightness ')) {
      const bri = input.substring(11).trim();
      runSystemControl('brightness', bri);
    } else if (cmdLower === 'lock' || cmdLower === 'lock pc' || cmdLower === 'lock screen') {
      runSystemControl('lock');
    } else if (cmdLower === 'sleep' || cmdLower === 'put pc to sleep') {
      runSystemControl('sleep');
    } else if (cmdLower === 'restart' || cmdLower === 'reboot') {
      runSystemControl('restart');
    } else if (cmdLower === 'shutdown' || cmdLower === 'power off') {
      runSystemControl('shutdown');
    } else if (cmdLower === 'screenshot' || cmdLower === 'take screenshot') {
      runSystemControl('screenshot');
    } else if (cmdLower === 'empty trash' || cmdLower === 'clear trash') {
      runSystemControl('empty-trash');
    } else if (cmdLower.includes('spotify') && (cmdLower.includes('play') || cmdLower.includes('song') || cmdLower.includes('playlist') || cmdLower.includes('music'))) {
      let query = '';
      if (cmdLower.startsWith('spotify play ')) {
        query = input.substring(13).trim();
      } else if (cmdLower.includes(' on spotify')) {
        const playIdx = cmdLower.indexOf('play ');
        const onIdx = cmdLower.indexOf(' on spotify');
        if (playIdx !== -1 && onIdx !== -1 && playIdx < onIdx) {
          query = input.substring(playIdx + 5, onIdx).trim();
        } else {
          query = input.replace(/spotify/gi, '').replace(/play/gi, '').trim();
        }
      } else {
        query = input.replace(/spotify/gi, '').replace(/play/gi, '').trim();
      }
      
      if (query) {
        runSystemControl('spotify', query);
      } else {
        console.log('\x1b[31m[FRIDAY] Please specify a song/playlist, BOSS.\x1b[0m');
        speak("Please specify a song or playlist.");
      }
    } else if (cmdLower.startsWith('remember ') || cmdLower.startsWith('save ') || cmdLower.startsWith('write down ')) {
      let fact = '';
      if (cmdLower.startsWith('remember ')) fact = input.substring(9);
      else if (cmdLower.startsWith('save ')) fact = input.substring(5);
      else fact = input.substring(11);
      addToVault(fact);
    } else if (cmdLower === 'list vault' || cmdLower === 'show vault' || cmdLower === 'vault list') {
      listVault();
    } else if (cmdLower === 'clear vault') {
      clearVault();
    } else if (cmdLower.startsWith('add todo ') || cmdLower.startsWith('add task ')) {
      const task = input.substring(9).trim();
      if (task) {
        const todos = loadTodos();
        todos.push({ text: task, completed: false });
        saveTodos(todos);
        console.log(`\x1b[32m[FRIDAY] Task registered: "${task}"\x1b[0m`);
        speak("Task registered.");
      }
    } else if (cmdLower === 'list todo' || cmdLower === 'todo list' || cmdLower === 'list tasks') {
      listTodos();
    } else if (cmdLower.startsWith('complete todo ') || cmdLower.startsWith('complete task ')) {
      const num = parseInt(input.replace(/[^\d]/g, ''), 10) - 1;
      const todos = loadTodos();
      if (todos[num]) {
        todos[num].completed = true;
        saveTodos(todos);
        console.log(`\x1b[32m[FRIDAY] Completed: "${todos[num].text}"\x1b[0m`);
        speak("Task completed.");
      }
    } else if (cmdLower === 'status' || cmdLower === 'diagnostics' || cmdLower === 'system') {
      checkSystem();
    } else {
      await chatQuery(input);
    }
    
    setTimeout(prompt, 500);
  });
}

prompt();
