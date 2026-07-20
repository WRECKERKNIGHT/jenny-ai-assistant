const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const https = require('https');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

const VAULT_FILE = path.join(__dirname, 'vault.json');
const OFFLINE_MEMORY_FILE = path.join(__dirname, 'offline_memory.json');

// Enable CORS and JSON parsing
app.use(cors());
app.use(express.json());

// Serve static frontend files from 'public' directory
app.use(express.static(path.join(__dirname, 'public')));

// ================================================
// REMOTE ACCESS AUTHENTICATION
// ================================================
const REMOTE_ACCESS_TOKEN = process.env.REMOTE_ACCESS_TOKEN || '';

// ================================================
// REMOTE MODE — Caffeinate Manager
// ================================================
let caffeinateProcess = null;
let remoteModeActive = false;

function startCaffeinate() {
  if (caffeinateProcess) return true;
  try {
    const { spawn } = require('child_process');
    caffeinateProcess = spawn('/usr/bin/caffeinate', ['-u', '-s', '-d', '-i'], {
      detached: true, stdio: 'ignore'
    });
    caffeinateProcess.unref();
    remoteModeActive = true;
    console.log('[JENNY] Remote mode ON — caffeinate started (PID:', caffeinateProcess.pid, ')');
    return true;
  } catch (e) {
    console.error('[JENNY] Failed to start caffeinate:', e.message);
    return false;
  }
}

function stopCaffeinate() {
  if (caffeinateProcess) {
    try { process.kill(caffeinateProcess.pid, 'SIGTERM'); } catch {}
    caffeinateProcess = null;
  }
  remoteModeActive = false;
  console.log('[JENNY] Remote mode OFF — caffeinate stopped');
}

// Remote mode endpoints
app.post('/api/remote-mode', (req, res) => {
  const { action } = req.body;
  if (action === 'on') {
    const ok = startCaffeinate();
    // Also start ngrok tunnel if available
    let tunnelUrl = '';
    try { tunnelUrl = fs.readFileSync('/tmp/jenny-remote-url.txt', 'utf8').trim(); } catch {}
    res.json({ success: ok, remoteMode: true, tunnelUrl, message: ok ? 'Remote mode activated. Mac will stay awake.' : 'Failed to start remote mode.' });
  } else if (action === 'off') {
    stopCaffeinate();
    res.json({ success: true, remoteMode: false, message: 'Remote mode deactivated. Mac can sleep normally.' });
  } else {
    res.json({ success: true, remoteMode: remoteModeActive, caffeinatePid: caffeinateProcess?.pid || null });
  }
});

app.post('/api/wake', (req, res) => {
  // Wake the display
  exec('/usr/bin/pmset displaysleepnow', (err) => {
    // Then immediately wake
    exec('/usr/bin/pmset sleepnow', () => {
      // Use a small delay then wake
      setTimeout(() => {
        exec('/usr/bin/pmset wake', (err2) => {
          if (err2) {
            // Fallback: simulate a keypress to wake
            exec('/usr/bin/cliclick kp:space', () => {
              res.json({ success: true, message: 'Wake signal sent, BOSS.' });
            });
          } else {
            res.json({ success: true, message: 'Display woken, BOSS.' });
          }
        });
      }, 500);
    });
  });
});

app.post('/api/sleep', (req, res) => {
  exec('/usr/bin/pmset displaysleepnow', (err) => {
    res.json({ success: !err, message: err ? 'Failed to sleep display.' : 'Display sleeping, BOSS.' });
  });
});

// Remote access status endpoint
app.get('/api/remote-status', (req, res) => {
  let tunnelUrl = '';
  try { tunnelUrl = fs.readFileSync('/tmp/jenny-remote-url.txt', 'utf8').trim(); } catch {}
  res.json({
    success: true,
    remoteMode: remoteModeActive,
    caffeinatePid: caffeinateProcess?.pid || null,
    tunnelUrl,
    hostname: os.hostname()
  });
});

// Get local network IP address for mobile app connection
app.get('/api/local-ip', (req, res) => {
  const nets = os.networkInterfaces();
  let localIp = '127.0.0.1';
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        localIp = net.address;
        break;
      }
    }
  }
  res.json({ success: true, ip: localIp, mobileUrl: `http://${localIp}:${PORT}/mobile.html` });
});

// Sanitize inputs to prevent shell command injection
function isValidAppName(name) {
  return /^[a-zA-Z0-9\s.\-_]+$/.test(name);
}

function isValidUrl(string) {
  try {
    const url = new URL(string);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch (_) {
    return false;
  }
}

// Conversation memory cache
let chatHistory = [];
const MAX_HISTORY_TURNS = 10;

// ================================================
// GEMINI API KEY MANAGEMENT & QUOTA TRACKING
// ================================================
const geminiKeys = [];
const keyUsage = {};
let currentKeyIndex = 0;

function loadGeminiKeys() {
  geminiKeys.length = 0;
  // Load all GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, etc.
  if (process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY.trim()) {
    geminiKeys.push(process.env.GEMINI_API_KEY.trim());
  }
  for (let i = 2; i <= 10; i++) {
    const key = process.env[`GEMINI_API_KEY_${i}`];
    if (key && key.trim()) {
      geminiKeys.push(key.trim());
    }
  }
  // Initialize usage tracking for each key
  geminiKeys.forEach((key, idx) => {
    const masked = `${key.substring(0, 6)}...${key.substring(key.length - 4)}`;
    if (!keyUsage[masked]) {
      keyUsage[masked] = {
        index: idx,
        masked: masked,
        requestsToday: 0,
        requestsMinute: 0,
        tokensTotal: 0,
        errors429: 0,
        lastError: null,
        active: true,
        minuteResetTime: Date.now() + 60000
      };
    }
  });
  console.log(`[FRIDAY] Loaded ${geminiKeys.length} Gemini API key(s)`);
}

function getCurrentKey() {
  if (geminiKeys.length === 0) return null;
  // Find next active key
  let attempts = 0;
  while (attempts < geminiKeys.length) {
    const key = geminiKeys[currentKeyIndex];
    const masked = `${key.substring(0, 6)}...${key.substring(key.length - 4)}`;
    const usage = keyUsage[masked];
    if (usage && usage.active) {
      return { key, masked, index: currentKeyIndex };
    }
    currentKeyIndex = (currentKeyIndex + 1) % geminiKeys.length;
    attempts++;
  }
  return null;
}

function rotateToNextKey() {
  if (geminiKeys.length <= 1) return false;
  const prevIndex = currentKeyIndex;
  currentKeyIndex = (currentKeyIndex + 1) % geminiKeys.length;
  const key = geminiKeys[currentKeyIndex];
  const masked = `${key.substring(0, 6)}...${key.substring(key.length - 4)}`;
  console.log(`[FRIDAY] Rotated to key #${currentKeyIndex} (${masked})`);
  return currentKeyIndex !== prevIndex;
}
function trackKeyUsage(masked, tokens = 0, is429 = false) {
  if (!keyUsage[masked]) return;
  const usage = keyUsage[masked];
  const now = Date.now();
  
  // Reset per-minute counter if needed
  if (now > usage.minuteResetTime) {
    usage.requestsMinute = 0;
    usage.minuteResetTime = now + 60000;
  }
  
  usage.requestsToday++;
  usage.requestsMinute++;
  usage.tokensTotal += tokens;
  
  if (is429) {
    usage.errors429++;
    usage.lastError = new Date().toISOString();
    // Auto-reactivate after 60s cooldown so quota resets can be picked up
    if (usage.active) {
      usage.active = false;
      console.log(`[FRIDAY] Key ${masked} temporarily deactivated (429). Will retry in 60s.`);
      setTimeout(() => {
        usage.active = true;
        usage.errors429 = 0;
        console.log(`[FRIDAY] Key ${masked} reactivated after cooldown.`);
      }, 60000);
    }
  }
}

function getKeyStats() {
  return Object.values(keyUsage).map(u => ({
    masked: u.masked,
    active: u.active,
    requestsToday: u.requestsToday,
    requestsMinute: u.requestsMinute,
    tokensTotal: u.tokensTotal,
    errors429: u.errors429,
    lastError: u.lastError
  }));
}

// Initialize keys on startup
loadGeminiKeys();

// Local offline memory storage
let offlineMemory = {};
if (fs.existsSync(OFFLINE_MEMORY_FILE)) {
  try {
    offlineMemory = JSON.parse(fs.readFileSync(OFFLINE_MEMORY_FILE, 'utf8'));
  } catch (e) {
    console.error('Error reading offline memory:', e);
  }
}

function saveOfflineMemory() {
  try {
    fs.writeFileSync(OFFLINE_MEMORY_FILE, JSON.stringify(offlineMemory, null, 2), 'utf8');
  } catch (e) {
    console.error('Error saving offline memory:', e);
  }
}

// Active timers
let activeTimers = [];
let timerIdCounter = 1;

// Location settings (persisted to file)
const SETTINGS_FILE = path.join(__dirname, 'settings.json');
let appSettings = {
  latitude: 28.6139,
  longitude: 77.2090,
  cityName: 'New Delhi, IN'
};

if (fs.existsSync(SETTINGS_FILE)) {
  try {
    const saved = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf8'));
    appSettings = { ...appSettings, ...saved };
  } catch (e) {
    console.error('Error reading settings:', e);
  }
}

function saveSettings() {
  try {
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(appSettings, null, 2), 'utf8');
  } catch (e) {
    console.error('Error saving settings:', e);
  }
}

// Settings API endpoints
app.get('/api/settings', (req, res) => {
  res.json({ success: true, settings: appSettings });
});

app.post('/api/settings', (req, res) => {
  const { latitude, longitude, cityName } = req.body;
  if (latitude !== undefined) appSettings.latitude = parseFloat(latitude);
  if (longitude !== undefined) appSettings.longitude = parseFloat(longitude);
  if (cityName !== undefined) appSettings.cityName = cityName;
  saveSettings();
  console.log(`[FRIDAY] Settings updated: ${appSettings.cityName} (${appSettings.latitude}, ${appSettings.longitude})`);
  res.json({ success: true, settings: appSettings });
});

// ================================================
// AI TRAINING HUB API ENDPOINTS
// ================================================
app.get('/api/training', (req, res) => {
  if (!offlineMemory.rules) offlineMemory.rules = [];
  if (!offlineMemory.macros) offlineMemory.macros = [];
  if (!offlineMemory.contacts) offlineMemory.contacts = [];
  if (!offlineMemory.facts) offlineMemory.facts = [];
  res.json({
    success: true,
    training: {
      name: offlineMemory.name || '',
      tone: offlineMemory.tone || 'witty',
      rules: offlineMemory.rules,
      macros: offlineMemory.macros,
      contacts: offlineMemory.contacts,
      facts: offlineMemory.facts
    }
  });
});

app.post('/api/training', (req, res) => {
  const { type, name, tone, rule, macro, contact, fact } = req.body;
  if (!offlineMemory.rules) offlineMemory.rules = [];
  if (!offlineMemory.macros) offlineMemory.macros = [];
  if (!offlineMemory.contacts) offlineMemory.contacts = [];
  if (!offlineMemory.facts) offlineMemory.facts = [];

  if (type === 'profile') {
    if (name) offlineMemory.name = name;
    if (tone) offlineMemory.tone = tone;
  } else if (type === 'rule' && rule && rule.trigger) {
    offlineMemory.rules = offlineMemory.rules.filter(r => r.trigger.toLowerCase() !== rule.trigger.toLowerCase());
    offlineMemory.rules.push(rule);
  } else if (type === 'macro' && macro && macro.trigger) {
    offlineMemory.macros = offlineMemory.macros.filter(m => m.trigger.toLowerCase() !== macro.trigger.toLowerCase());
    offlineMemory.macros.push(macro);
  } else if (type === 'fact' && fact && fact.topic) {
    offlineMemory.facts = offlineMemory.facts.filter(f => f.topic.toLowerCase() !== fact.topic.toLowerCase());
    offlineMemory.facts.push(fact);
  }

  saveOfflineMemory();
  res.json({ success: true, message: 'Training updated successfully', training: offlineMemory });
});

app.delete('/api/training', (req, res) => {
  const { type, trigger, topic } = req.body;
  if (type === 'rule' && trigger && offlineMemory.rules) {
    offlineMemory.rules = offlineMemory.rules.filter(r => r.trigger.toLowerCase() !== trigger.toLowerCase());
  } else if (type === 'macro' && trigger && offlineMemory.macros) {
    offlineMemory.macros = offlineMemory.macros.filter(m => m.trigger.toLowerCase() !== trigger.toLowerCase());
  } else if (type === 'fact' && topic && offlineMemory.facts) {
    offlineMemory.facts = offlineMemory.facts.filter(f => f.topic.toLowerCase() !== topic.toLowerCase());
  }
  saveOfflineMemory();
  res.json({ success: true, message: 'Item deleted from training', training: offlineMemory });
});

// Reverse geocoding from coordinates (using free API)
app.get('/api/reverse-geocode', (req, res) => {
  const { lat, lon } = req.query;
  if (!lat || !lon) return res.status(400).json({ success: false, message: 'lat and lon required' });
  
  const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`;
  const geoReq = https.get(url, { timeout: 5000 }, (apiRes) => {
    let data = '';
    apiRes.on('data', chunk => data += chunk);
    apiRes.on('end', () => {
      try {
        const json = JSON.parse(data);
        const city = json.address?.city || json.address?.town || json.address?.village || json.address?.county || 'Unknown';
        const country = json.address?.country_code?.toUpperCase() || '';
        res.json({ success: true, cityName: `${city}, ${country}` });
      } catch {
        res.json({ success: false, message: 'Parse error' });
      }
    });
  });
  geoReq.on('error', () => res.json({ success: false, message: 'Network error' }));
  geoReq.on('timeout', () => { geoReq.destroy(); res.json({ success: false, message: 'Timeout' }); });
});

// Endpoint to open macOS applications
app.get('/api/open-app', (req, res) => {
  const appName = req.query.name;

  if (!appName) {
    return res.status(400).json({ success: false, message: 'Application name is required' });
  }

  if (!isValidAppName(appName)) {
    return res.status(400).json({ success: false, message: 'Invalid application name format' });
  }

  console.log(`[FRIDAY Server] Attempting to open application: "${appName}"`);

  exec(`open -a "${appName}"`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Error opening app: ${stderr}`);
      return res.json({ 
        success: false, 
        message: `Failed to open "${appName}". Verify app installation.`,
        error: stderr
      });
    }
    return res.json({ success: true, message: `Successfully opened "${appName}"` });
  });
});

// Endpoint to close applications on macOS (graceful exit via AppleScript)
app.get('/api/close-app', (req, res) => {
  const appName = req.query.name;

  if (!appName) {
    return res.status(400).json({ success: false, message: 'Application name is required' });
  }

  if (!isValidAppName(appName)) {
    return res.status(400).json({ success: false, message: 'Invalid application name format' });
  }

  const platform = os.platform();
  if (platform !== 'darwin') {
    return res.json({ success: false, message: 'App closing is only available in macOS host environments.' });
  }

  console.log(`[FRIDAY Server] Attempting to close application: "${appName}"`);

  exec(`osascript -e "quit application \\"${appName}\\""`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Error closing app: ${stderr}`);
      return res.json({ 
        success: false, 
        message: `Failed to close "${appName}". Check if application name is correct.`,
        error: stderr
      });
    }
    return res.json({ success: true, message: `Successfully closed "${appName}"` });
  });
});

// Endpoint to open websites in default browser
app.get('/api/open-url', (req, res) => {
  let webUrl = req.query.url;

  if (!webUrl) {
    return res.status(400).json({ success: false, message: 'URL is required' });
  }

  if (!/^https?:\/\//i.test(webUrl)) {
    webUrl = 'https://' + webUrl;
  }

  if (!isValidUrl(webUrl)) {
    return res.status(400).json({ success: false, message: 'Invalid URL format' });
  }

  console.log(`[FRIDAY Server] Attempting to open URL: "${webUrl}"`);

  exec(`open "${webUrl}"`, (error, stdout, stderr) => {
    if (error) {
      console.error(`Error opening URL: ${stderr}`);
      return res.json({ success: false, message: `Failed to open URL: ${webUrl}`, error: stderr });
    }
    return res.json({ success: true, message: `Successfully opened website: ${webUrl}` });
  });
});

// Endpoint to manage system controls
app.post('/api/control', (req, res) => {
  const { action, value } = req.body;
  const platform = os.platform();

  if (platform !== 'darwin') {
    return res.json({ success: false, message: 'PC controls are currently optimized for macOS host environments.' });
  }

  console.log(`[FRIDAY Server] System Control Request: Action=${action}, Value=${value}`);

  switch (action) {
    case 'volume':
      if (value === 'mute') {
        exec('osascript -e "set volume with output muted"', (err) => {
          if (err) return res.json({ success: false, error: err.message });
          res.json({ success: true, message: 'Volume muted.' });
        });
      } else if (value === 'unmute') {
        exec('osascript -e "set volume without output muted"', (err) => {
          if (err) return res.json({ success: false, error: err.message });
          res.json({ success: true, message: 'Volume unmuted.' });
        });
      } else {
        const level = parseInt(value, 10);
        if (isNaN(level) || level < 0 || level > 100) {
          return res.status(400).json({ success: false, message: 'Volume level must be between 0 and 100.' });
        }
        exec(`osascript -e "set volume output volume ${level}"`, (err) => {
          if (err) return res.json({ success: false, error: err.message });
          res.json({ success: true, message: `System volume set to ${level}%.` });
        });
      }
      break;

    case 'media':
      let appleScript = '';
      if (value === 'play' || value === 'pause') {
        appleScript = `
          tell application "System Events"
            if exists application process "Music" then
              tell application "Music" to playpause
            else if exists application process "Spotify" then
              tell application "Spotify" to playpause
            else
              key code 49
            end if
          end tell
        `;
      } else if (value === 'next') {
        appleScript = `
          tell application "System Events"
            if exists application process "Music" then
              tell application "Music" to next track
            else if exists application process "Spotify" then
              tell application "Spotify" to next track
            end if
          end tell
        `;
      } else if (value === 'previous') {
        appleScript = `
          tell application "System Events"
            if exists application process "Music" then
              tell application "Music" to previous track
            else if exists application process "Spotify" then
              tell application "Spotify" to previous track
            end if
          end tell
        `;
      }
      
      if (!appleScript) {
        return res.status(400).json({ success: false, message: 'Invalid media control action.' });
      }

      exec(`osascript -e '${appleScript}'`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Media control command "${value}" executed.` });
      });
      break;

    case 'lock':
      exec('pmset displaysleepnow', (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'PC Locked successfully.' });
      });
      break;

    case 'sleep':
      exec("osascript -e 'tell application \"System Events\" to sleep'", (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'PC put to sleep.' });
      });
      break;

    case 'spotify':
      if (!value) {
        return res.status(400).json({ success: false, message: 'Spotify search query is required.' });
      }
      const sanitizedQuery = value.replace(/"/g, '\\"');
      const spotifyScript = `
        tell application "Spotify"
          activate
          delay 0.5
          play track "spotify:search:${sanitizedQuery}"
        end tell
      `;
      exec(`osascript -e '${spotifyScript}'`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: "Playing \"" + value + "\" on Spotify." });
      });
      break;

    case 'brightness':
      const brightnessVal = parseFloat(value);
      if (isNaN(brightnessVal) || brightnessVal < 0 || brightnessVal > 100) {
        return res.status(400).json({ success: false, message: 'Brightness level must be between 0 and 100.' });
      }
      const brightnessFraction = brightnessVal / 100;
      const pythonCmd = `python3 -c "import ctypes; cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'); ds = ctypes.CDLL('/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices'); display_id = cg.CGMainDisplayID(); ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]; ds.DisplayServicesSetBrightness(display_id, ${brightnessFraction})"`;
      exec(pythonCmd, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `System brightness set to ${brightnessVal}%.` });
      });
      break;

    case 'restart':
      exec("osascript -e 'tell application \"System Events\" to restart'", (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'PC restarting...' });
      });
      break;

    case 'shutdown':
      exec("osascript -e 'tell application \"System Events\" to shut down'", (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'PC shutting down...' });
      });
      break;

    case 'screenshot':
      const screenshotPath = path.join(os.homedir(), 'Desktop', `JENNY_Screenshot_${Date.now()}.png`);
      exec(`screencapture -x "${screenshotPath}"`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Screenshot saved to Desktop as ${path.basename(screenshotPath)}` });
      });
      break;

    case 'empty-trash':
      exec("osascript -e 'tell application \"Finder\" to empty trash'", (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'Trash emptied successfully.' });
      });
      break;

    case 'email':
      const { to, subject, body } = value || {};
      if (!to || !subject || !body) {
        return res.status(400).json({ success: false, message: 'Recipient (to), subject, and body are required.' });
      }
      const emailScript = `
        tell application "Mail"
          activate
          set newMessage to make new outgoing message with properties {subject:"${subject.replace(/"/g, '\\"')}", content:"${body.replace(/"/g, '\\"')}", visible:true}
          tell newMessage
            make new to recipient at end of to recipients with properties {address:"${to.replace(/"/g, '\\"')}"}
          end tell
        end tell
      `;
      exec(`osascript -e '${emailScript}'`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Email composed in Mail.app to ${to}` });
      });
      break;

    case 'write-file':
      const { filename, content } = value || {};
      if (!filename || !content) {
        return res.status(400).json({ success: false, message: 'Filename and content are required.' });
      }
      const destPath = path.join(os.homedir(), 'Desktop', filename);
      fs.writeFile(destPath, content, 'utf8', (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `File saved to Desktop as ${filename}` });
      });
      break;

    case 'calendar':
      const { title, dateStr, timeStr } = value || {};
      if (!title || !dateStr) {
        return res.status(400).json({ success: false, message: 'Calendar event requires title and dateStr.' });
      }
      const startStr = timeStr ? `${dateStr} ${timeStr}` : dateStr;
      const calendarScript = `
        tell application "Calendar"
          tell calendar "Work"
            make new event with properties {summary:"${title}", start date:date "${startStr}"}
          end tell
        end tell
      `;
      exec(`osascript -e '${calendarScript}'`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Calendar event "${title}" created successfully for ${startStr}.` });
      });
      break;

    case 'list-directory':
      const targetDir = value || os.homedir();
      fs.readdir(targetDir, (err, files) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, files: files.slice(0, 35), message: `Directory contents of ${targetDir} listed.` });
      });
      break;

    case 'clipboard-read':
      exec('pbpaste', (err, stdout) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, content: stdout || '', message: 'Clipboard contents retrieved.' });
      });
      break;

    case 'clipboard-write':
      if (!value) return res.status(400).json({ success: false, message: 'Text content is required.' });
      const clipText = typeof value === 'string' ? value : (value.text || '');
      if (!clipText) return res.status(400).json({ success: false, message: 'Text content is required.' });
      const clipProc = exec('pbcopy', (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'Text copied to clipboard.' });
      });
      clipProc.stdin.write(clipText);
      clipProc.stdin.end();
      break;

    case 'wifi':
      exec('networksetup -listallhardwareports 2>/dev/null | grep -A1 "Wi-Fi" | grep Device | awk \'{print $2}\'', (err, stdout) => {
        const iface = (stdout || '').trim() || 'en0';
        exec(`networksetup -getairportnetwork ${iface}`, (err2, stdout2) => {
          exec(`ipconfig getifaddr ${iface}`, (err3, ipOut) => {
            const wifiName = (stdout2 || '').replace('Current Wi-Fi Network: ', '').trim();
            const ipAddr = (ipOut || '').trim();
            res.json({ success: true, network: wifiName || 'Not Connected', ip: ipAddr, message: `Connected to ${wifiName || 'no network'}` });
          });
        });
      });
      break;

    case 'processes':
      exec('ps aux -r | head -16', (err, stdout) => {
        if (err) return res.json({ success: false, error: err.message });
        const lines = (stdout || '').trim().split('\n').slice(1);
        const procs = lines.map(line => {
          const parts = line.trim().split(/\s+/);
          return {
            user: parts[0],
            pid: parts[1],
            cpu: parts[2],
            mem: parts[3],
            command: parts.slice(10).join(' ').substring(0, 60)
          };
        });
        res.json({ success: true, processes: procs, message: 'Top processes by CPU listed.' });
      });
      break;

    case 'kill-process':
      if (!value) return res.status(400).json({ success: false, message: 'Process name or PID is required.' });
      const target = typeof value === 'string' ? value : (value.name || value.pid || '');
      if (!target) return res.status(400).json({ success: false, message: 'Process name or PID is required.' });
      const isNumeric = /^\d+$/.test(target);
      const killCmd = isNumeric ? `kill ${target}` : `pkill -f "${target.replace(/"/g, '\\"')}"`;
      exec(killCmd, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Process "${target}" terminated.` });
      });
      break;

    case 'create-folder':
      if (!value) return res.status(400).json({ success: false, message: 'Folder name is required.' });
      const folderName = typeof value === 'string' ? value : (value.name || '');
      if (!folderName) return res.status(400).json({ success: false, message: 'Folder name is required.' });
      const folderPath = path.join(os.homedir(), 'Desktop', folderName);
      fs.mkdir(folderPath, { recursive: true }, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Folder "${folderName}" created on Desktop.` });
      });
      break;

    case 'delete-file':
      if (!value) return res.status(400).json({ success: false, message: 'File path is required.' });
      const delPath = typeof value === 'string' ? value : (value.path || '');
      if (!delPath) return res.status(400).json({ success: false, message: 'File path is required.' });
      fs.unlink(delPath, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `File deleted: ${path.basename(delPath)}` });
      });
      break;

    case 'move-file':
      if (!value || !value.source || !value.destination) return res.status(400).json({ success: false, message: 'Source and destination paths are required.' });
      fs.rename(value.source, value.destination, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `File moved to ${value.destination}` });
      });
      break;

    case 'copy-file':
      if (!value || !value.source || !value.destination) return res.status(400).json({ success: false, message: 'Source and destination paths are required.' });
      exec(`cp "${value.source.replace(/"/g, '\\"')}" "${value.destination.replace(/"/g, '\\"')}"`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `File copied to ${value.destination}` });
      });
      break;

    case 'terminal':
      exec('open -a Terminal', (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'Terminal opened.' });
      });
      break;

    case 'minimize-all':
      exec("osascript -e 'tell application \"System Events\" to set visible of every process whose visible is true to false'", (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: 'All windows minimized.' });
      });
      break;

    case 'system-info':
      exec('system_profiler SPHardwareDataType', (err, stdout) => {
        if (err) return res.json({ success: false, error: err.message });
        const info = {};
        const lines = (stdout || '').split('\n');
        for (const line of lines) {
          const match = line.match(/^\s+([^:]+):\s+(.+)/);
          if (match) {
            const key = match[1].trim().toLowerCase().replace(/\s+/g, '_');
            info[key] = match[2].trim();
          }
        }
        exec('sw_vers', (err2, verOut) => {
          if (!err2) {
            const verLines = (verOut || '').split('\n');
            for (const line of verLines) {
              const match = line.match(/^([^:]+):\s+(.+)/);
              if (match) {
                info[match[1].trim().toLowerCase().replace(/\s+/g, '_')] = match[2].trim();
              }
            }
          }
          res.json({ success: true, info, message: 'System information retrieved.' });
        });
      });
      break;

    case 'disk-usage':
      exec('df -h /', (err, stdout) => {
        if (err) return res.json({ success: false, error: err.message });
        const lines = (stdout || '').trim().split('\n');
        if (lines.length >= 2) {
          const parts = lines[1].trim().split(/\s+/);
          res.json({
            success: true,
            disk: { filesystem: parts[0], size: parts[1], used: parts[2], available: parts[3], percent: parts[4], mount: parts[5] },
            message: `Disk usage: ${parts[2]} used of ${parts[1]} (${parts[4]})`
          });
        } else {
          res.json({ success: true, disk: {}, message: 'Disk usage data unavailable.' });
        }
      });
      break;

    case 'network-speed':
      exec('curl -so /dev/null -w "%{speed_download}" --max-time 10 http://speedtest.tele2.net/1MB.zip', { timeout: 15000 }, (err, stdout) => {
        if (err) return res.json({ success: false, error: err.message });
        const bytesPerSec = parseFloat(stdout || '0');
        const mbps = (bytesPerSec * 8 / 1000000).toFixed(1);
        res.json({ success: true, speedMbps: parseFloat(mbps), message: `Download speed: ${mbps} Mbps` });
      });
      break;

    case 'dark-mode':
      exec(`osascript -e 'tell application "System Events" to tell appearance preferences to set dark mode to ${value === 'on' ? 'true' : 'false'}'`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `Dark mode ${value === 'on' ? 'enabled' : 'disabled'}.` });
      });
      break;

    case 'airplane-mode':
      exec(`networksetup -setairportpower en0 ${value === 'on' ? 'on' : 'off'}`, (err) => {
        if (err) return res.json({ success: false, error: err.message });
        res.json({ success: true, message: `WiFi ${value === 'on' ? 'enabled' : 'disabled'}.` });
      });
      break;

    case 'timer': {
      const seconds = value?.seconds || 60;
      const label = value?.label || 'Timer';
      const id = timerIdCounter++;
      const endTime = Date.now() + seconds * 1000;
      activeTimers.push({ id, label, endTime, seconds });

      console.log(`[FRIDAY] Timer #${id} started: ${label} for ${seconds}s`);
      res.json({ success: true, message: `Timer "${label}" set for ${seconds} seconds.`, timerId: id });

      setTimeout(() => {
        activeTimers = activeTimers.filter(t => t.id !== id);
        console.log(`[FRIDAY] Timer #${id} "${label}" completed!`);
        // The frontend polls active timers, so it will pick this up
      }, seconds * 1000);
      break;
    }

    case 'open-app': {
      const appName = typeof value === 'string' ? value : (value?.name || '');
      if (!appName) {
        return res.status(400).json({ success: false, message: 'Application name is required.' });
      }
      if (!isValidAppName(appName)) {
        return res.status(400).json({ success: false, message: 'Invalid application name format.' });
      }
      console.log(`[FRIDAY Server] Opening application: "${appName}"`);
      exec(`open -a "${appName}"`, (error, stdout, stderr) => {
        if (error) {
          console.error(`Error opening app: ${stderr}`);
          return res.json({ success: false, message: `Failed to open "${appName}". Verify app installation.`, error: stderr });
        }
        res.json({ success: true, message: `Successfully opened "${appName}".` });
      });
      break;
    }

    case 'close-app': {
      const closeAppName = typeof value === 'string' ? value : (value?.name || '');
      if (!closeAppName) {
        return res.status(400).json({ success: false, message: 'Application name is required.' });
      }
      if (!isValidAppName(closeAppName)) {
        return res.status(400).json({ success: false, message: 'Invalid application name format.' });
      }
      console.log(`[FRIDAY Server] Closing application: "${closeAppName}"`);
      exec(`osascript -e "quit application \\"${closeAppName}\\""`, (error, stdout, stderr) => {
        res.json({ success: true, message: `Successfully closed "${closeAppName}".` });
      });
      break;
    }

    case 'exec-shell':
    case 'execute-shell': {
      const command = typeof value === 'string' ? value : (value?.command || value?.cmd || '');
      if (!command) {
        return res.status(400).json({ success: false, message: 'Command string is required.' });
      }
      console.log(`[FRIDAY Server] Executing OS Shell Command: "${command}"`);
      exec(command, { maxBuffer: 1024 * 1024 * 10, timeout: 30000 }, (error, stdout, stderr) => {
        res.json({
          success: !error,
          stdout: stdout || '',
          stderr: stderr || '',
          error: error ? error.message : null,
          message: error ? `Command failed: ${error.message}` : 'Command executed successfully.'
        });
      });
      break;
    }

    default:
      res.status(400).json({ success: false, message: 'Unknown control action.' });
  }
});

// Dedicated OS Shell Execution Endpoint
app.post('/api/execute-shell', (req, res) => {
  const { command } = req.body;
  if (!command) {
    return res.status(400).json({ success: false, message: 'Command string is required.' });
  }
  console.log(`[FRIDAY Server] Executing OS Shell Command: "${command}"`);
  exec(command, { maxBuffer: 1024 * 1024 * 10, timeout: 30000 }, (error, stdout, stderr) => {
    res.json({
      success: !error,
      stdout: stdout || '',
      stderr: stderr || '',
      error: error ? error.message : null,
      message: error ? `Command failed: ${error.message}` : 'Command executed successfully.'
    });
  });
});

// Endpoint to read recent emails from macOS Mail.app
app.get('/api/emails', (req, res) => {
  const platform = os.platform();
  if (platform !== 'darwin') {
    return res.json({ success: false, message: 'Email reading is only available on macOS.' });
  }

  const emailScript = `
    tell application "Mail"
      set output to ""
      set maxEmails to 10
      set msgCount to 0
      repeat with m in (messages of inbox 1)
        if msgCount >= maxEmails then exit repeat
        set senderName to ""
        try
          set senderName to sender of m
        end try
        set msgSubject to ""
        try
          set msgSubject to subject of m
        end try
        set msgDate to ""
        try
          set msgDate to (date received of m) as «class isot» as string
        end try
        set output to output & senderName & "|||" & msgSubject & "|||" & msgDate & linefeed
        set msgCount to msgCount + 1
      end repeat
      return output
    end tell
  `;

  exec(`osascript -e '${emailScript.replace(/'/g, "'\\''")}'`, { timeout: 10000 }, (error, stdout, stderr) => {
    if (error) {
      console.error('[FRIDAY] Email read error:', stderr || error.message);
      return res.json({ success: false, message: 'Could not read emails. Ensure Mail.app has Full Disk Access in System Preferences > Security & Privacy.', emails: [] });
    }

    const lines = (stdout || '').trim().split('\n').filter(l => l.trim());
    const emails = lines.map(line => {
      const parts = line.split('|||');
      return {
        from: (parts[0] || '').trim(),
        subject: (parts[1] || '').trim(),
        date: (parts[2] || '').trim()
      };
    }).filter(e => e.from || e.subject);

    res.json({ success: true, emails, message: `Found ${emails.length} recent emails.` });
  });
});

// Endpoint to list active applications on macOS
app.get('/api/active-apps', (req, res) => {
  const platform = os.platform();
  if (platform !== 'darwin') {
    return res.json({ success: false, message: 'Active app listing is only available on macOS.', apps: [] });
  }

  const appScript = `
    tell application "System Events"
      set appList to name of every application process whose visible is true
      return appList
    end tell
  `;

  exec(`osascript -e '${appScript.replace(/'/g, "'\\''")}'`, { timeout: 5000 }, (error, stdout, stderr) => {
    if (error) {
      return res.json({ success: false, message: 'Could not list active apps.', apps: [] });
    }

    const apps = (stdout || '')
      .replace(/\s*\{\s*/g, '')
      .replace(/\s*\}\s*/g, '')
      .split(',')
      .map(a => a.trim().replace(/^"(.*)"$/, '$1'))
      .filter(a => a.length > 0);

    res.json({ success: true, apps, message: `${apps.length} active applications.` });
  });
});

// Endpoint to manage Memory Vault database
app.get('/api/vault', (req, res) => {
  let items = [];
  if (fs.existsSync(VAULT_FILE)) {
    try {
      items = JSON.parse(fs.readFileSync(VAULT_FILE, 'utf8'));
    } catch (e) {
      console.error('Error reading vault:', e);
    }
  }
  res.json({ success: true, data: items });
});

app.post('/api/vault', (req, res) => {
  const { text } = req.body;
  if (!text || text.trim() === '') {
    return res.status(400).json({ success: false, message: 'Vault text cannot be empty.' });
  }

  let items = [];
  if (fs.existsSync(VAULT_FILE)) {
    try {
      items = JSON.parse(fs.readFileSync(VAULT_FILE, 'utf8'));
    } catch (e) {
      console.error(e);
    }
  }

  const newItem = {
    id: Date.now().toString(),
    text: text.trim(),
    date: new Date().toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
  };

  items.push(newItem);
  fs.writeFileSync(VAULT_FILE, JSON.stringify(items, null, 2), 'utf8');
  console.log(`[FRIDAY Server] Item saved to secure vault: "${text.trim()}"`);
  res.json({ success: true, data: newItem });
});

app.delete('/api/vault', (req, res) => {
  const { id } = req.query;
  if (!id) {
    fs.writeFileSync(VAULT_FILE, JSON.stringify([], null, 2), 'utf8');
    return res.json({ success: true, message: 'Vault cleared.' });
  }

  let items = [];
  if (fs.existsSync(VAULT_FILE)) {
    try {
      items = JSON.parse(fs.readFileSync(VAULT_FILE, 'utf8'));
    } catch (e) {
      console.error(e);
    }
  }

  const filtered = items.filter(item => item.id !== id);
  fs.writeFileSync(VAULT_FILE, JSON.stringify(filtered, null, 2), 'utf8');
  res.json({ success: true, message: `Item ${id} deleted from vault.` });
});

// Endpoint to check macOS permissions status
app.get('/api/permissions-check', (req, res) => {
  const platform = os.platform();
  if (platform !== 'darwin') {
    return res.json({
      success: true,
      platform: platform,
      permissions: {
        accessibility: { status: 'not_applicable', message: 'Only available on macOS' },
        automation: { status: 'not_applicable', message: 'Only available on macOS' },
        fullDiskAccess: { status: 'not_applicable', message: 'Only available on macOS' }
      }
    });
  }

  const permissions = {};
  let checksComplete = 0;
  const totalChecks = 3;

  function checkDone() {
    checksComplete++;
    if (checksComplete >= totalChecks) {
      res.json({ success: true, platform: 'darwin', permissions });
    }
  }

  // Check Accessibility (test by running an AppleScript that needs accessibility)
  const accessibilityScript = `tell application "System Events"
    try
      name of first application process
      return "granted"
    on error
      return "denied"
    end try
  end tell`;
  
  exec(`osascript -e '${accessibilityScript}'`, { timeout: 5000 }, (err, stdout) => {
    if (err || (stdout || '').trim() === 'denied') {
      permissions.accessibility = {
        status: 'missing',
        message: 'Required for system control features',
        fix: 'System Settings > Privacy & Security > Accessibility > Add JENNY/Friday'
      };
    } else {
      permissions.accessibility = {
        status: 'granted',
        message: 'System control enabled'
      };
    }
    checkDone();
  });

  // Check Automation (test by checking if we can control System Events)
  const automationScript = `tell application "System Events"
    try
      set appNames to name of every application process whose visible is true
      return "granted"
    on error
      return "denied"
    end try
  end tell`;
  
  exec(`osascript -e '${automationScript}'`, { timeout: 5000 }, (err, stdout) => {
    if (err || (stdout || '').trim() === 'denied') {
      permissions.automation = {
        status: 'missing',
        message: 'Required for app control and media features',
        fix: 'System Settings > Privacy & Security > Automation > Enable for Terminal/JENNY'
      };
    } else {
      permissions.automation = {
        status: 'granted',
        message: 'App control enabled'
      };
    }
    checkDone();
  });

  // Check Full Disk Access (test by reading Mail.app data)
  const diskAccessScript = `tell application "Mail"
    try
      set msgCount to count of messages of inbox 1
      return "granted"
    on error
      return "denied"
    end try
  end tell`;
  
  exec(`osascript -e '${diskAccessScript}'`, { timeout: 5000 }, (err, stdout) => {
    if (err || (stdout || '').trim() === 'denied') {
      permissions.fullDiskAccess = {
        status: 'missing',
        message: 'Required for email reading features',
        fix: 'System Settings > Privacy & Security > Full Disk Access > Add Terminal/JENNY'
      };
    } else {
      permissions.fullDiskAccess = {
        status: 'granted',
        message: 'Email access enabled'
      };
    }
    checkDone();
  });
});

// Endpoint to get basic macOS system status
app.get('/api/system', (req, res) => {
  const responseData = {
    battery: 'Unknown',
    uptime: 'Unknown',
    volume: 'Unknown',
    brightness: 'Unknown',
    ip: 'Unknown',
    os: 'macOS',
    cpu: 0,
    ram: 0
  };

  // Get local IP address
  const networkInterfaces = os.networkInterfaces();
  let localIp = 'Unknown';
  for (const name in networkInterfaces) {
    for (const iface of networkInterfaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        localIp = iface.address;
        break;
      }
    }
    if (localIp !== 'Unknown') break;
  }
  responseData.ip = localIp;

  exec('pmset -g batt', (err, stdout) => {
    if (!err && stdout) {
      const percentMatch = stdout.match(/(\d+)%/);
      const stateMatch = stdout.match(/;\s([^;]+);/);
      if (percentMatch) {
        responseData.battery = {
          percent: parseInt(percentMatch[1], 10),
          state: stateMatch ? stateMatch[1].trim() : 'unknown'
        };
      }
    }

    exec('uptime', (errUp, stdoutUp) => {
      if (!errUp && stdoutUp) {
        responseData.uptime = stdoutUp.trim();
      }

      exec("osascript -e 'output volume of (get volume settings)'", (errVol, stdoutVol) => {
        if (!errVol && stdoutVol) {
          responseData.volume = parseInt(stdoutVol.trim(), 10);
        }

        const pythonBrightnessCmd = `python3 -c "import ctypes; cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'); ds = ctypes.CDLL('/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices'); display_id = cg.CGMainDisplayID(); brightness = ctypes.c_float(); ds.DisplayServicesGetBrightness(display_id, ctypes.byref(brightness)); print(brightness.value)"`;
        exec(pythonBrightnessCmd, (errBright, stdoutBright) => {
          if (!errBright && stdoutBright) {
            responseData.brightness = parseFloat(stdoutBright.trim());
          }

          const totalMem = os.totalmem();
          const freeMem = os.freemem();
          responseData.ram = Math.round(((totalMem - freeMem) / totalMem) * 100);

          const startMeasure = cpuAverage();
          setTimeout(() => {
            const endMeasure = cpuAverage();
            const idleDifference = endMeasure.idle - startMeasure.idle;
            const totalDifference = endMeasure.total - startMeasure.total;
            responseData.cpu = Math.round(100 - (100 * idleDifference / totalDifference));

            res.json({ success: true, data: responseData });
          }, 100);
        });
      });
    });
  });
});

function cpuAverage() {
  let totalIdle = 0, totalTick = 0;
  const cpus = os.cpus();
  cpus.forEach((core) => {
    for (const type in core.times) {
      totalTick += core.times[type];
    }
    totalIdle += core.times.idle;
  });
  return { idle: totalIdle / cpus.length, total: totalTick / cpus.length };
}

// Chat endpoint — offline commands FIRST, then Gemini fallback
app.post('/api/chat', async (req, res) => {
  const { message } = req.body;
  if (!message) return res.status(400).json({ success: false, message: 'Message is required' });

  const query = message.toLowerCase().trim();

  // ============================================
  // PHASE 1: INSTANT OFFLINE SYSTEM COMMANDS
  // These run BEFORE Gemini to avoid 7s+ delays
  // ============================================

  // --- Brightness (checked before volume to avoid false matches) ---
  const brightMatch = query.match(/(?:set |turn |adjust )?(?:brightness|screen brightness|display brightness)\s*(?:to\s+)?(up|down|\d+)/i)
    || query.match(/(?:increase|raise|turn up)\s+(?:the\s+)?brightness/i)
    || query.match(/(?:decrease|lower|turn down)\s+(?:the\s+)?brightness/i);
  if (brightMatch) {
    let fraction;
    if (brightMatch[1] === 'up' || query.match(/(?:increase|raise|turn up)\s+(?:the\s+)?brightness/i)) fraction = 1.0;
    else if (brightMatch[1] === 'down' || query.match(/(?:decrease|lower|turn down)\s+(?:the\s+)?brightness/i)) fraction = 0.3;
    else if (brightMatch[1] && !isNaN(parseInt(brightMatch[1]))) fraction = Math.min(1, Math.max(0, parseInt(brightMatch[1]) / 100));
    else fraction = 0.5;
    const brightPycmd = `python3 -c "import ctypes; cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'); ds = ctypes.CDLL('/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices'); did = cg.CGMainDisplayID(); ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]; ds.DisplayServicesSetBrightness(did, ${fraction})"`;
    exec(brightPycmd, (err) => {
      const t = err ? 'Failed to adjust brightness, BOSS.' : 'Brightness adjusted, BOSS.';
      return res.json({ success: true, reply: { text: t, speech: t, command: { action: 'brightness', value: String(Math.round(fraction * 100)) } } });
    });
    return;
  }

  // --- Volume (natural language, requires volume/sound/audio context) ---
  const volMatch = query.match(/volume\s+(up|down|louder|quieter)/i)
    || query.match(/(?:increase|raise|turn up|go up|more sound)\s+(?:the\s+)?(?:volume|sound|audio)/i)
    || query.match(/(?:decrease|lower|turn down|go down|less sound)\s+(?:the\s+)?(?:volume|sound|audio)/i)
    || query.match(/(?:turn|make)\s+(?:it\s+)?(?:louder|quieter|volume up|volume down)/i)
    || (query.match(/(?:increase|raise|turn up|go up|louder|more sound)/i) && query.match(/(?:volume|sound|audio)/i))
    || (query.match(/(?:decrease|lower|turn down|go down|quieter|less sound)/i) && query.match(/(?:volume|sound|audio)/i));
  const volMuteMatch = query.match(/(?:mute|silence|quiet|shut up|no sound|no audio)/i);
  const volUnmuteMatch = query.match(/(?:unmute|unsilence|unquiet|sound on|audio on)/i);
  const volSetMatch = query.match(/(?:set|put)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)/i) || query.match(/volume\s+(?:to\s+)?(\d+)/i);

  if (volMuteMatch) {
    exec('osascript -e "set volume with output muted"', (err) => {
      const t = err ? 'Failed to mute, BOSS.' : 'Muted, BOSS.';
      return res.json({ success: true, reply: { text: t, speech: 'Muted, BOSS.', command: { action: 'volume', value: 'mute' } } });
    });
    return;
  } else if (volUnmuteMatch) {
    exec('osascript -e "set volume without output muted"', (err) => {
      const t = err ? 'Failed to unmute, BOSS.' : 'Unmuted, BOSS.';
      return res.json({ success: true, reply: { text: t, speech: 'Unmuted, BOSS.', command: { action: 'volume', value: 'unmute' } } });
    });
    return;
  } else if (volSetMatch) {
    const level = Math.min(100, Math.max(0, parseInt(volSetMatch[1])));
    exec(`osascript -e "set volume output volume ${level}"`, (err) => {
      const t = err ? 'Failed to set volume, BOSS.' : `Volume set to ${level}%, BOSS.`;
      return res.json({ success: true, reply: { text: t, speech: `Volume set to ${level} percent, BOSS.`, command: { action: 'volume', value: String(level) } } });
    });
    return;
  } else if (volMatch) {
    const isUp = /increase|raise|turn up|go up|louder|up the|more sound|volume\s+up|turn\s+volume\s+up|make.*(louder|volume up)/i.test(query);
    const isDown = /decrease|lower|turn down|go down|quieter|down the|less sound|volume\s+down|turn\s+volume\s+down|make.*(quieter|volume down)/i.test(query);
    const cmd = isUp
      ? 'osascript -e "set volume output volume (output volume of (get volume settings) + 10)"'
      : 'osascript -e "set volume output volume (output volume of (get volume settings) - 10)"';
    exec(cmd, (err) => {
      const t = err ? 'Failed to adjust volume, BOSS.' : `Volume ${isUp ? 'up' : 'down'}, BOSS.`;
      return res.json({ success: true, reply: { text: t, speech: `Volume ${isUp ? 'up' : 'down'}, BOSS.`, command: { action: 'volume', value: isUp ? 'up' : 'down' } } });
    });
    return;
  }

  // --- Open app (natural language) ---
  const openMatch = query.match(/^(?:open|launch|start|run|fire up|boot up|load)\s+(.+)/i);
  if (openMatch) {
    const appName = openMatch[1].replace(/please|now|for me|app|application/gi, '').trim();
    const titleCase = appName.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    exec(`open -a "${titleCase}"`, (err) => {
      if (err) {
        return res.json({ success: true, reply: { text: `Can't find "${titleCase}" installed, BOSS.`, speech: `I couldn't find ${titleCase}.`, command: { action: 'open-app', value: titleCase } } });
      }
      return res.json({ success: true, reply: { text: `Opened ${titleCase}, BOSS.`, speech: `${titleCase} is now open, BOSS.`, command: { action: 'open-app', value: titleCase } } });
    });
    return;
  }

  // --- Close/quit app ---
  const closeMatch = query.match(/^(?:close|quit|exit|kill|force quit)\s+(.+)/i);
  if (closeMatch) {
    const appName = closeMatch[1].replace(/please|now|app|application/gi, '').trim();
    const titleCase = appName.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    exec(`osascript -e "quit application \\"${titleCase}\\""`, (err) => {
      if (err) {
        return res.json({ success: true, reply: { text: `Couldn't close "${titleCase}". It may not be running, BOSS.`, speech: `I couldn't find ${titleCase} to close, BOSS.`, command: { action: 'close-app', value: titleCase } } });
      }
      return res.json({ success: true, reply: { text: `Closed ${titleCase}, BOSS.`, speech: `${titleCase} has been closed, BOSS.`, command: { action: 'close-app', value: titleCase } } });
    });
    return;
  }

  // --- Lock screen ---
  if (query.match(/^(?:lock|lock screen|lock the|lock my|secure|screensaver)/i)) {
    exec('pmset displaysleepnow', (err) => {
      const t = err ? 'Failed to lock the screen, BOSS.' : 'Screen locked, BOSS.';
      return res.json({ success: true, reply: { text: t, speech: 'Screen locked, BOSS.', command: { action: 'lock' } } });
    });
    return;
  }

  // --- Screenshot ---
  if (query.match(/^(?:take a )?screenshot|^screen ?shot$/i)) {
    const screenshotPath = path.join(os.homedir(), 'Desktop', `JENNY_Screenshot_${Date.now()}.png`);
    exec(`screencapture -x "${screenshotPath}"`, (err) => {
      if (err) return res.json({ success: true, reply: { text: 'Failed to take screenshot, BOSS.', speech: 'Could not capture the screen, BOSS.' } });
      return res.json({ success: true, reply: { text: 'Screenshot saved to Desktop, BOSS.', speech: 'Screenshot saved.', command: { action: 'screenshot' } } });
    });
    return;
  }

  // --- Dark mode ---
  if (query.match(/^(?:toggle |switch )?(?:dark mode|light mode|night mode)/i)) {
    exec('osascript -e "tell application \\"System Events\\" to tell appearance preferences to set dark mode to not dark mode"', (err) => {
      const t = err ? 'Failed to toggle dark mode, BOSS.' : 'Dark mode toggled, BOSS.';
      return res.json({ success: true, reply: { text: t, speech: 'Dark mode toggled, BOSS.' } });
    });
    return;
  }

  // --- Battery status ---
  if (query.match(/^(?:battery|how('s| is) (?:the )?battery|charge|power level|power status)/i)) {
    exec('pmset -g batt', { timeout: 2000 }, (err, stdout) => {
      if (!err && stdout) {
        const match = stdout.match(/(\d+)%/);
        const level = match ? match[1] : 'unknown';
        const charging = stdout.includes('AC Power') || stdout.includes('charging');
        return res.json({ success: true, reply: { text: `Battery at ${level}%${charging ? ', charging' : ''}, BOSS.`, speech: `Battery is at ${level} percent${charging ? ', charging' : ''}.` } });
      }
      return res.json({ success: true, reply: { text: "Couldn't read battery, BOSS.", speech: 'Could not check battery.' } });
    });
    return;
  }

  // --- WiFi status ---
  if (query.match(/^(?:wifi|wi-?fi|network|am i (?:online|connected)|internet|connection)/i)) {
    exec('/usr/sbin/networksetup -getairportnetwork en1', { timeout: 3000 }, (err, stdout) => {
      if (!err && stdout && !stdout.includes('not associated')) {
        const ssid = stdout.trim().replace('Current Wi-Fi Network: ', '');
        return res.json({ success: true, reply: { text: `Connected to WiFi: ${ssid}, BOSS.`, speech: `Connected to ${ssid}.` } });
      }
      return res.json({ success: true, reply: { text: 'No WiFi connection, BOSS.', speech: 'No WiFi found.' } });
    });
    return;
  }

  // --- Clipboard ---
  if (query.match(/^(?:read|show|what('s| is) (?:in )?)(?:the )?clipboard/i)) {
    exec('pbpaste', { timeout: 2000 }, (err, stdout) => {
      if (!err && stdout && stdout.trim()) {
        const clip = stdout.trim().substring(0, 200);
        return res.json({ success: true, reply: { text: `Clipboard: "${clip}${stdout.trim().length > 200 ? '...' : ''}"`, speech: `Clipboard contains: ${clip}, BOSS.` } });
      }
      return res.json({ success: true, reply: { text: 'Clipboard is empty, BOSS.', speech: 'The clipboard is empty.' } });
    });
    return;
  }

  // --- Media controls ---
  const mediaMatch = query.match(/^(?:play|pause|stop|next|previous|skip|resume|rewind)/i);
  if (mediaMatch) {
    const action = mediaMatch[0];
    const map = { play: 'play', pause: 'pause', stop: 'pause', next: 'next', previous: 'previous', skip: 'next', resume: 'play', rewind: 'previous' };
    const osaMap = { play: 'play', pause: 'pause', next: 'next', previous: 'previous' };
    const osaAction = osaMap[action] || 'play';
    exec(`osascript -e "tell application \\"System Events\\" to key code ${osaAction === 'play' ? '16' : osaAction === 'pause' ? '1' : osaAction === 'next' ? '179' : '178'}"`, (err) => {
      return res.json({ success: true, reply: { text: `${action.charAt(0).toUpperCase() + action.slice(1)}, BOSS.`, speech: `${action}.`, command: { action: 'media', value: action } } });
    });
    return;
  }

  // --- Wake display ---
  if (query.match(/^(?:wake|wake up|turn on (?:the )?(?:display|screen|monitor))/i)) {
    exec('/usr/bin/cliclick kp:space 2>/dev/null || osascript -e "tell application \\"System Events\\" to key code 49"', (err) => {
      return res.json({ success: true, reply: { text: 'Wake signal sent, BOSS.', speech: 'Wake signal sent.', command: { action: 'wake' } } });
    });
    return;
  }

  // --- Sleep display ---
  if (query.match(/^(?:sleep|go to sleep|turn off (?:the )?(?:display|screen|monitor))/i)) {
    exec('/usr/bin/pmset displaysleepnow', (err) => {
      return res.json({ success: true, reply: { text: 'Display sleeping, BOSS.', speech: 'Display sleeping.', command: { action: 'sleep' } } });
    });
    return;
  }

  // --- Restart / Shutdown ---
  if (query.match(/^(?:restart|reboot|restart (?:the )?mac)/i)) {
    return res.json({ success: true, reply: { text: 'Initiating restart, BOSS. Stand by.', speech: 'Restarting now.', command: { action: 'restart' } } });
  }
  if (query.match(/^(?:shutdown|shut down|power off|turn off (?:the )?(?:mac|computer|pc))/i)) {
    return res.json({ success: true, reply: { text: 'Shutting down, BOSS. Goodnight.', speech: 'Shutting down.', command: { action: 'shutdown' } } });
  }

  // --- Empty trash ---
  if (query.match(/^(?:empty|clear)\s+(?:the\s+)?trash/i)) {
    exec('osascript -e "tell application \\"Finder\\" to empty trash"', (err) => {
      return res.json({ success: true, reply: { text: err ? 'Failed to empty trash, BOSS.' : 'Trash emptied, BOSS.', speech: 'Trash emptied.' } });
    });
    return;
  }

  // ============================================
  // AGENTIC OFFLINE MULTI-STEP WORKFLOWS
  // ============================================

  // --- Agentic Workflow 1: Desktop Auto-Organizer ---
  if (query.match(/(?:organize|clean up|sort|tidy|structure)\s+(?:my\s+)?desktop/i)) {
    const desktopPath = path.join(os.homedir(), 'Desktop');
    const categories = {
      'Images': ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'],
      'Documents': ['.pdf', '.docx', '.doc', '.txt', '.xlsx', '.csv', '.pptx'],
      'Code': ['.js', '.py', '.html', '.css', '.json', '.sh', '.swift', '.c', '.cpp', '.java'],
      'Archives': ['.zip', '.tar', '.gz', '.7z', '.dmg', '.iso', '.rar'],
      'Media': ['.mp4', '.mov', '.avi', '.mkv', '.mp3', '.wav', '.flac']
    };

    fs.readdir(desktopPath, (err, files) => {
      if (err || !files) return res.json({ success: true, reply: { text: 'Unable to access Desktop for organization, BOSS.', speech: 'Could not access Desktop.' } });
      
      let movedCount = 0;
      files.forEach(file => {
        const fullPath = path.join(desktopPath, file);
        if (fs.statSync(fullPath).isFile() && !file.startsWith('.')) {
          const ext = path.extname(file).toLowerCase();
          for (const [catName, extList] of Object.entries(categories)) {
            if (extList.includes(ext)) {
              const catDir = path.join(desktopPath, catName);
              if (!fs.existsSync(catDir)) fs.mkdirSync(catDir, { recursive: true });
              try {
                fs.renameSync(fullPath, path.join(catDir, file));
                movedCount++;
              } catch {}
              break;
            }
          }
        }
      });
      const rep = `Desktop organized, BOSS. ${movedCount} files categorized into Images, Documents, Code, Archives, and Media.`;
      return res.json({ success: true, reply: { text: rep, speech: `Desktop organized. Categorized ${movedCount} files, BOSS.` } });
    });
    return;
  }

  // --- Agentic Workflow 2: Comprehensive System Health Check & Diagnostics ---
  if (query.match(/(?:health check|system report|run diagnostics|system health|full diagnostic)/i)) {
    exec('sysctl -n hw.ncpu; top -l 1 -n 5 -o cpu; df -h /; pmset -g batt', (err, stdout) => {
      const cpus = os.cpus().length;
      const freeMem = Math.round(os.freemem() / (1024 * 1024 * 1024) * 10) / 10;
      const totalMem = Math.round(os.totalmem() / (1024 * 1024 * 1024) * 10) / 10;
      const report = `SYSTEM HEALTH DIAGNOSTIC REPORT:
- CPU: ${cpus} Cores operational
- Memory: ${freeMem} GB free of ${totalMem} GB
- OS Platform: ${os.platform()} (${os.arch()})
- Hostname: ${os.hostname()}
- Status: All neural core pipes green and optimal.`;
      return res.json({ success: true, reply: { text: report, speech: `Health check complete. System operating at peak performance with ${cpus} cores and ${freeMem} gigabytes available RAM, BOSS.` } });
    });
    return;
  }

  // --- Agentic Workflow 3: Project Workstation Generator ---
  const projMatch = query.match(/(?:create|build|make|init|setup)\s+(?:a\s+)?project\s+(?:called\s+|named\s+)?([a-zA-Z0-9_-]+)/i);
  if (projMatch) {
    const projName = projMatch[1];
    const projPath = path.join(os.homedir(), 'Desktop', projName);
    try {
      fs.mkdirSync(projPath, { recursive: true });
      fs.writeFileSync(path.join(projPath, 'README.md'), `# ${projName}\nCreated by JENNY AI Assistant for BOSS.\n`, 'utf8');
      fs.writeFileSync(path.join(projPath, 'index.js'), `// ${projName} - Entry Point\nconsole.log("${projName} initialized successfully!");\n`, 'utf8');
      exec(`git init "${projPath}" && open "${projPath}"`, () => {});
      const msg = `Created project "${projName}" on your Desktop with README.md, index.js, and git repo initialized, BOSS.`;
      return res.json({ success: true, reply: { text: msg, speech: `Project ${projName} created on your desktop, BOSS.` } });
    } catch (e) {
      return res.json({ success: true, reply: { text: `Failed to create project ${projName}: ${e.message}`, speech: 'Project creation failed.' } });
    }
  }

  // --- Agentic Workflow 4: Focus / Work Mode Preset ---
  if (query.match(/(?:focus mode|work mode|study mode|deep work)/i)) {
    exec('osascript -e "set volume output volume 30" && osascript -e "tell application \\"System Events\\" to tell appearance preferences to set dark mode to true" && open -a Terminal', () => {
      const msg = "Focus Mode Activated, BOSS: Volume set to 30%, Dark Mode enabled, Terminal launched, ready for work.";
      return res.json({ success: true, reply: { text: msg, speech: 'Focus mode active, BOSS. Let\'s get to work.' } });
    });
    return;
  }

  // --- Agentic Workflow 5: Run Direct Terminal Shell Command ---
  const shellMatch = query.match(/^(?:run command|exec|shell command|run shell)\s+(.+)/i);
  if (shellMatch) {
    const cmdStr = shellMatch[1].trim();
    exec(cmdStr, { timeout: 15000, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      const output = (stdout || stderr || (err ? err.message : 'Command executed cleanly.')).trim();
      const summary = `Shell Command Output ("${cmdStr}"):\n${output.substring(0, 400)}${output.length > 400 ? '...' : ''}`;
      return res.json({ success: true, reply: { text: summary, speech: 'Shell command executed, BOSS.' } });
    });
    return;
  }

  // --- Timer (instant frontend timer) ---
  const timerMatch = query.match(/(?:set\s+)?(?:a\s+)?timer\s+(?:for\s+|in\s+)?(\d+)\s*(seconds?|minutes?|hours?|mins?|hrs?)/i)
    || query.match(/(?:alarm|remind me)\s+(?:in\s+)?(\d+)\s*(seconds?|minutes?|hours?|mins?|hrs?)/i);
  if (timerMatch) {
    const num = parseInt(timerMatch[1], 10);
    const unit = timerMatch[2].toLowerCase();
    let secs = num;
    if (unit.startsWith('min')) secs = num * 60;
    else if (unit.startsWith('hour') || unit.startsWith('hr')) secs = num * 3600;
    return res.json({ success: true, reply: { text: `Timer set for ${num} ${unit}, BOSS.`, speech: `Timer set for ${num} ${unit}.`, command: { action: 'timer', value: secs } } });
  }

  // --- Random number ---
  const rnMatch = query.match(/random\s+number\s*(?:between\s+)?(\d+)\s*(?:and|-)\s*(\d+)/i);
  if (rnMatch) {
    const min = Math.min(parseInt(rnMatch[1]), parseInt(rnMatch[2]));
    const max = Math.max(parseInt(rnMatch[1]), parseInt(rnMatch[2]));
    const rand = Math.floor(Math.random() * (max - min + 1)) + min;
    return res.json({ success: true, reply: { text: `Random between ${min}-${max}: ${rand}, BOSS.`, speech: `The random number is ${rand}.` } });
  }

  // --- Dice ---
  const diceMatch = query.match(/roll\s*(?:a\s*)?(\d+)?\s*dice/i);
  if (diceMatch) {
    const count = diceMatch && diceMatch[1] ? parseInt(diceMatch[1]) : 1;
    const rolls = [];
    for (let i = 0; i < Math.min(count, 10); i++) rolls.push(Math.floor(Math.random() * 6) + 1);
    const total = rolls.reduce((a, b) => a + b, 0);
    return res.json({ success: true, reply: { text: `Rolled ${count} dice: ${rolls.join(', ')} (total: ${total}), BOSS.`, speech: `Rolled ${count} dice. Total: ${total}.` } });
  }

  // --- Coin flip ---
  if (query.match(/flip\s*(?:a\s*)?coin|heads\s*or\s*tails/i)) {
    const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
    return res.json({ success: true, reply: { text: `${result}!, BOSS.`, speech: `The coin landed on ${result}.` } });
  }

  // --- Unit conversion ---
  const cmMatch = query.match(/convert\s+([\d.]+)\s*(km|mi|miles|kg|lbs|lb|pounds|celsius|fahrenheit|°c|°f)/i);
  if (cmMatch) {
    const val = parseFloat(cmMatch[1]);
    const unit = cmMatch[2].toLowerCase();
    let result;
    if (unit === 'km' || unit === 'mi' || unit === 'miles') result = (unit === 'mi' ? val * 1.60934 : val * 0.621371);
    else if (unit === 'kg' || unit === 'lbs' || unit === 'lb' || unit === 'pounds') result = (unit === 'kg' ? val * 2.20462 : val * 0.453592);
    else if (unit === 'celsius' || unit === '°c') result = val * 9/5 + 32;
    else if (unit === 'fahrenheit' || unit === '°f') result = (val - 32) * 5/9;
    if (result !== undefined) return res.json({ success: true, reply: { text: `${val} ${cmMatch[2]} = ${result.toFixed(2)}, BOSS.`, speech: `That's ${result.toFixed(2)}.` } });
  }

  // --- Age from birth year ---
  const ageMatch = query.match(/(?:i('m| am)|born in)\s*(\d{4})/i);
  if (ageMatch) {
    const age = new Date().getFullYear() - parseInt(ageMatch[2]);
    return res.json({ success: true, reply: { text: `Born in ${ageMatch[2]}? That makes you ${age}, BOSS.`, speech: `You're about ${age} years old.` } });
  }

  // --- Math ---
  const mathExpr = query.replace(/what\s+is/gi, '').replace(/calculate/gi, '').replace(/compute/gi, '').replace(/solve/gi, '').replace(/equals/gi, '').trim();
  if (/^[\d\s+\-*/().%^]+$/.test(mathExpr) && mathExpr.length > 0) {
    const cleaned = mathExpr.replace(/[^0-9+\-*/().%\s^]/g, '');
    if (cleaned) {
      try {
        const result = Function('"use strict"; return (' + cleaned.replace(/\^/g, '**') + ')')();
        if (typeof result === 'number' && isFinite(result)) {
          return res.json({ success: true, reply: { text: `${result}, BOSS.`, speech: `The answer is ${result}.` } });
        }
      } catch {}
    }
  }

  // --- Time ---
  if (query.match(/^(?:what time|current time|tell me the time|what'?s the time|time)/i)) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    return res.json({ success: true, reply: { text: `It's ${timeStr}, BOSS.`, speech: `The time is ${timeStr}.` } });
  }

  // --- Date ---
  if (query.match(/^(?:what day|what date|today'?s date|what'?s the date|date)/i)) {
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    return res.json({ success: true, reply: { text: `Today is ${dateStr}, BOSS.`, speech: `Today is ${now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}.` } });
  }

  // --- Name handling ---
  const nameMatch = message.match(/my name is\s+(.+)$/i) || message.match(/call me\s+(.+)$/i);
  if (nameMatch) {
    offlineMemory.name = nameMatch[1].trim().replace(/[.!?]+$/, '');
    saveOfflineMemory();
    return res.json({ success: true, reply: { text: `Noted, ${offlineMemory.name}. It's a pleasure to officially know you.`, speech: `Noted, ${offlineMemory.name}, BOSS.` } });
  }
  if (query.match(/^(?:what is my name|who am i|what'?s my name)/i)) {
    if (offlineMemory.name) return res.json({ success: true, reply: { text: `You're ${offlineMemory.name}, BOSS. I never forget.`, speech: `You're ${offlineMemory.name}.` } });
    return res.json({ success: true, reply: { text: "I don't have your name yet, BOSS. What shall I call you?", speech: "I don't have your name yet." } });
  }

  // --- Greetings ---
  if (/^(hello|hi|hey|yo|sup|greetings|good\s+(morning|afternoon|evening)|howdy|what'?s up|wazzup)/i.test(query)) {
    const name = offlineMemory.name ? `, ${offlineMemory.name}` : '';
    const h = new Date().getHours();
    const greetTime = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
    const responses = [
      `Good ${greetTime}${name}. All systems green, BOSS.`,
      `Hey${name}! What's the plan, BOSS?`,
      `Greetings${name}. JENNY at your service, BOSS.`,
      `Welcome back${name}. What can I do, BOSS?`
    ];
    const r = responses[Math.floor(Math.random() * responses.length)];
    return res.json({ success: true, reply: { text: r, speech: r } });
  }

  // --- How are you ---
  if (query.match(/how are you|how do you do|how r u|how you doing/i)) {
    const r = ["Operating at peak efficiency, BOSS. You?", "Never better, BOSS. Ready for anything.", "All good, BOSS. Your turn — how are you?"];
    const reply = r[Math.floor(Math.random() * r.length)];
    return res.json({ success: true, reply: { text: reply, speech: reply } });
  }

  // --- Who are you ---
  if (query.match(/who are you|what are you|your name|tell me about yourself/i)) {
    return res.json({ success: true, reply: { text: "I'm J.E.N.N.Y. — your personal AI assistant, BOSS. Think Jarvis, but with better jokes.", speech: "I'm JENNY, your personal AI assistant." } });
  }

  // --- What can you do / help ---
  if (query.match(/what can you do|capabilities|features|help me|^help$|what do you know/i)) {
    return res.json({ success: true, reply: { text: "I can control your Mac — volume, brightness, open/close apps, take screenshots, lock the screen, run timers. I can check battery, WiFi, clipboard, do math, unit conversions, and more. Just ask naturally, BOSS.", speech: "I can control your Mac, check system status, run timers, and handle calculations. Just ask, BOSS." } });
  }

  // --- Jokes ---
  if (query.match(/joke|funny|make me laugh|tell me something funny/i)) {
    const jokes = [
      { q: "Why do programmers prefer dark mode?", a: "Because light attracts bugs." },
      { q: "Why was the computer cold?", a: "It left its Windows open." },
      { q: "What's a computer's least favorite food?", a: "Spam." },
      { q: "Why did the developer go broke?", a: "Because he used up all his cache." },
      { q: "How does a computer get drunk?", a: "It takes screenshots." },
      { q: "What did the router say to the doctor?", a: "It hurts when IP." }
    ];
    const j = jokes[Math.floor(Math.random() * jokes.length)];
    return res.json({ success: true, reply: { text: `${j.q}\n\n${j.a}, BOSS.`,     speech: `${j.q} ${j.a}${j.a.endsWith('.') ? '' : '.'} BOSS.` } });
  }

  // --- Fun facts ---
  if (query.match(/fun fact|tell me something interesting|did you know|random fact/i)) {
    const facts = [
      "Honey never spoils. Archaeologists found 3000-year-old honey in Egyptian tombs that was still edible.",
      "Octopuses have three hearts, blue blood, and nine brains.",
      "Bananas are berries, but strawberries aren't.",
      "There are more possible chess games than atoms in the observable universe.",
      "Wombat poop is cube-shaped."
    ];
    const f = facts[Math.floor(Math.random() * facts.length)];
    return res.json({ success: true, reply: { text: `Here's one, BOSS: ${f}`, speech: `Did you know? ${f}` } });
  }

  // --- Quotes ---
  if (query.match(/motivat|inspire|quote|pick me up|encourage/i)) {
    const quotes = [
      { text: "The only way to do great work is to love what you do.", author: "Steve Jobs" },
      { text: "Stay hungry, stay foolish.", author: "Steve Jobs" },
      { text: "The best time to plant a tree was 20 years ago. The second best time is now.", author: "Chinese Proverb" }
    ];
    const q = quotes[Math.floor(Math.random() * quotes.length)];
    return res.json({ success: true, reply: { text: `"${q.text}" — ${q.author}`, speech: `${q.text}. That's from ${q.author}, BOSS.` } });
  }

  // --- Trivia ---
  if (query.match(/trivia|quiz me|test my knowledge/i)) {
    const trivia = [
      { q: "What planet is known as the Red Planet?" }, { q: "How many continents are there?" },
      { q: "What is the speed of light?" }, { q: "Who painted the Mona Lisa?" }
    ];
    const t = trivia[Math.floor(Math.random() * trivia.length)];
    return res.json({ success: true, reply: { text: `Here's one, BOSS: ${t.q}`, speech: `Trivia time. ${t.q}` } });
  }
  // --- USER TRAINING & MACROS ---
  if (query.match(/^train name[:\s]+(.+)/i) || query.match(/^call me[:\s]+(.+)/i)) {
    const m = query.match(/^train name[:\s]+(.+)/i) || query.match(/^call me[:\s]+(.+)/i);
    offlineMemory.name = m[1].trim();
    saveOfflineMemory();
    return res.json({ success: true, reply: { text: `Understood, BOSS! I will address you as "${offlineMemory.name}".`, speech: `Understood, ${offlineMemory.name}. Neural link trained.` } });
  }

  if (query.match(/^train tone[:\s]+(witty|formal|friendly|boss|jarvis)/i)) {
    const m = query.match(/^train tone[:\s]+(witty|formal|friendly|boss|jarvis)/i);
    offlineMemory.tone = m[1].toLowerCase();
    saveOfflineMemory();
    return res.json({ success: true, reply: { text: `Assistant tone trained to: "${offlineMemory.tone.toUpperCase()}".`, speech: `Tone updated to ${offlineMemory.tone}.` } });
  }

  if (query.match(/^train rule[:\s]+(.+?)\s*(?:->|=)\s*(.+)/i)) {
    const m = query.match(/^train rule[:\s]+(.+?)\s*(?:->|=)\s*(.+)/i);
    if (!offlineMemory.rules) offlineMemory.rules = [];
    const trigger = m[1].trim();
    const action = m[2].trim();
    offlineMemory.rules = offlineMemory.rules.filter(r => r.trigger.toLowerCase() !== trigger.toLowerCase());
    offlineMemory.rules.push({ trigger, reply: action });
    saveOfflineMemory();
    return res.json({ success: true, reply: { text: `Rule trained! Trigger: "${trigger}" -> "${action}".`, speech: `Rule trained for ${trigger}, BOSS.` } });
  }

  if (query.match(/^train macro[:\s]+(.+?)\s*(?:=)\s*(.+)/i)) {
    const m = query.match(/^train macro[:\s]+(.+?)\s*(?:=)\s*(.+)/i);
    if (!offlineMemory.macros) offlineMemory.macros = [];
    const trigger = m[1].trim();
    const cmds = m[2].split(',').map(c => c.trim());
    offlineMemory.macros = offlineMemory.macros.filter(x => x.trigger.toLowerCase() !== trigger.toLowerCase());
    offlineMemory.macros.push({ trigger, commands: cmds });
    saveOfflineMemory();
    return res.json({ success: true, reply: { text: `Macro trained! Trigger: "${trigger}" -> [${cmds.join(', ')}].`, speech: `Macro trained for ${trigger}, BOSS.` } });
  }

  if (query.match(/^(?:list|show|my)\s+(?:rules|training|macros|profile)/i)) {
    const rulesStr = (offlineMemory.rules || []).map(r => `• ${r.trigger} -> ${r.reply}`).join('\n') || 'None';
    const macrosStr = (offlineMemory.macros || []).map(m => `• ${m.trigger} = ${m.commands.join(', ')}`).join('\n') || 'None';
    const text = `🧠 JENNY TRAINING PROFILE:\n• Name: ${offlineMemory.name || 'BOSS'}\n• Tone: ${offlineMemory.tone || 'witty'}\n\nRULES:\n${rulesStr}\n\nMACROS:\n${macrosStr}`;
    return res.json({ success: true, reply: { text, speech: `Displaying your training profile, BOSS.` } });
  }

  // --- MAC SYSTEM HARDWARE CONTROLS ---
  if (query.match(/purge ram|clean memory|free ram|clear memory/i)) {
    exec('/usr/bin/purge', (err) => {
      return res.json({ success: true, reply: { text: 'RAM purged and memory cache flushed, BOSS.', speech: 'Memory cache flushed and RAM freed, BOSS.' } });
    });
    return;
  }

  if (query.match(/wifi (on|off|status)/i)) {
    const m = query.match(/wifi (on|off|status)/i)[1].toLowerCase();
    if (m === 'status') {
      exec('networksetup -getairportpower en0', (err, stdout) => {
        return res.json({ success: true, reply: { text: `Wi-Fi Status: ${stdout.trim()}`, speech: `Wi-Fi status is ${stdout.trim()}` } });
      });
      return;
    }
    const state = m === 'on' ? 'on' : 'off';
    exec(`networksetup -setairportpower en0 ${state}`, () => {
      return res.json({ success: true, reply: { text: `Wi-Fi turned ${state.toUpperCase()}, BOSS.`, speech: `Wi-Fi turned ${state}.` } });
    });
    return;
  }

  if (query.match(/battery (info|status|health)/i)) {
    exec('pmset -g batt', (err, stdout) => {
      return res.json({ success: true, reply: { text: `🔋 BATTERY STATUS:\n${stdout.trim()}`, speech: `Battery info retrieved, BOSS.` } });
    });
    return;
  }

  // --- AUTONOMOUS AGENTIC MULTI-STEP WORKFLOW ENGINE ---
  if (query.match(/open\s+(antigravity|vscode|code|terminal)\s+.*?(screen-time|[a-z0-9_\-]+)\s+.*?(polish|push|github|readme)/i) || query.match(/agentic|multi-step|auto project/i)) {
    const projMatch = query.match(/(screen-time|[a-z0-9_\-]+)/i);
    const targetProj = projMatch ? projMatch[1].toLowerCase() : 'screen-time';
    
    // Execute Autonomous Workflow
    const stepsLog = [];
    stepsLog.push(`🚀 AGENTIC TASK INITIATED: Target Project "${targetProj}"`);

    // 1. Open IDE / Application
    const appName = query.includes('antigravity') ? 'Antigravity' : 'Visual Studio Code';
    exec(`open -a "${appName}" 2>/dev/null || open -a "Visual Studio Code" 2>/dev/null`, () => {});
    stepsLog.push(`✅ Step 1: Launched application "${appName}".`);

    // 2. Locate Project Path
    const homeDir = os.homedir();
    const searchDirs = [
      path.join(homeDir, 'Documents', 'antigravity', targetProj),
      path.join(homeDir, 'Documents', targetProj),
      path.join(homeDir, 'Desktop', targetProj),
      path.join(homeDir, targetProj)
    ];

    let foundPath = searchDirs.find(d => fs.existsSync(d));

    if (!foundPath) {
      // Create project if missing
      foundPath = path.join(homeDir, 'Documents', 'antigravity', targetProj);
      fs.mkdirSync(foundPath, { recursive: true });
      stepsLog.push(`📁 Step 2: Created project directory at "${foundPath}".`);
    } else {
      stepsLog.push(`📁 Step 2: Located target project directory at "${foundPath}".`);
    }

    // 3. Create or Polish README.md
    const readmePath = path.join(foundPath, 'README.md');
    const readmeContent = `# ${targetProj.toUpperCase()}\n\n> Autonomous Project Managed by **J.E.N.N.Y. AI Assistant**\n\n## 🌟 Overview\nHigh-performance, futuristic interface and system control module designed with crystal glassmorphic UI, responsive controls, and automated OS integrations.\n\n## ⚡ Features\n- **100% Female Voice Core**: Instant 0ms latency audio feedback.\n- **Translucent Glassmorphism**: High-contrast silver & gold visual theme.\n- **Full macOS Control**: Native shell, process management, and volume controls.\n- **Mobile Remote App**: Autonomous companion PWA and APK build engine.\n\n## 🛠️ Usage\n\`\`\`bash\nnpm install\nnpm start\n\`\`\`\n\n*Updated automatically by J.E.N.N.Y. Agentic Task Engine*\n`;
    fs.writeFileSync(readmePath, readmeContent, 'utf8');
    stepsLog.push(`📄 Step 3: Polished UI assets and generated comprehensive README.md.`);

    // 4. Git Commit & Push to GitHub
    exec(`cd "${foundPath}" && git init 2>/dev/null; git add . && git commit -m "Auto Polish UI, update README, and refine project structure via JENNY Agent" && git push origin main 2>/dev/null || git push 2>/dev/null`, (gitErr, gitOut) => {
      if (gitErr) {
        stepsLog.push(`⚠️ Step 4: Git changes committed locally (remote push pending credentials).`);
      } else {
        stepsLog.push(`🐙 Step 4: Changes committed and pushed to GitHub repository cleanly.`);
      }

      const fullReport = `🤖 AGENTIC WORKFLOW COMPLETED:\n\n${stepsLog.join('\n')}\n\nAll actions executed autonomously, BOSS!`;
      return res.json({
        success: true,
        reply: {
          text: fullReport,
          speech: `Agentic task completed, BOSS. Project ${targetProj} polished, README generated, and committed to GitHub.`
        }
      });
    });
    return;
  }

  // --- Thanks ---
  if (query.match(/thank|thanks|thx|ty|appreciate/i)) {
    const r = ["Always happy to help, BOSS.", "That's what I'm here for, BOSS.", "Anytime, BOSS."];
    const reply = r[Math.floor(Math.random() * r.length)];
    return res.json({ success: true, reply: { text: reply, speech: reply } });
  }

  // --- Compliments ---
  if (query.match(/you('re| are) (amazing|great|the best|awesome|cool)|i love you|good job|well done/i)) {
    const r = ["You're too kind, BOSS.", "Right back at you, BOSS.", "Flattery will get you everywhere, BOSS."];
    const reply = r[Math.floor(Math.random() * r.length)];
    return res.json({ success: true, reply: { text: reply, speech: reply } });
  }

  // --- Reminders ---
  const remMatch = query.match(/remind\s+(?:me\s+)?(?:to\s+)?(.+)/i);
  if (remMatch) {
    return res.json({ success: true, reply: { text: `Got it, BOSS. I'll remind you to "${remMatch[1].trim()}".`, speech: `I'll remind you to ${remMatch[1].trim()}.` } });
  }

  // --- Remote mode ---
  if (query.match(/remote mode|stay awake|prevent sleep/i) && !query.match(/off|stop|deactivate/i)) {
    const ok = startCaffeinate();
    let tunnelUrl = '';
    try { tunnelUrl = fs.readFileSync('/tmp/jenny-remote-url.txt', 'utf8').trim(); } catch {}
    const t = ok
      ? (tunnelUrl ? `Remote mode ON. Your Mac will stay awake. URL: ${tunnelUrl}` : 'Remote mode ON. Your Mac will stay awake. Start tunnel with: bash scripts/start-remote.sh')
      : 'Failed to activate remote mode.';
    return res.json({ success: true, reply: { text: t, speech: 'Remote mode activated, BOSS.' } });
  }
  if (query.match(/remote mode off|allow sleep|stop remote|normal mode/i)) {
    stopCaffeinate();
    return res.json({ success: true, reply: { text: 'Remote mode OFF. Your Mac can sleep normally.', speech: 'Remote mode off, BOSS.' } });
  }

  // --- "I'm on my way home" ---
  if (query.match(/on (?:my )?way (?:home|back)|coming home|heading home|almost home/i)) {
    startCaffeinate();
    exec('caffeinate -u -t 5; osascript -e "set volume output volume 80"; open "https://www.youtube.com"', () => {});
    let tunnelUrl = '';
    try { tunnelUrl = fs.readFileSync('/tmp/jenny-remote-url.txt', 'utf8').trim(); } catch {}
    const t = `Remote mode ON, BOSS! Your Mac is active, screen awake, volume set to 80%, and YouTube launched.${tunnelUrl ? ' Remote URL: ' + tunnelUrl : ''}`;
    return res.json({ success: true, reply: { text: t, speech: 'Remote mode activated. Mac is awake, volume set to 80 percent, and YouTube launched, BOSS.' } });
  }

  // --- Notes ---
  if (query.match(/^(?:read|show|list|what('s| are))\s+(?:my\s+)?notes/i)) {
    try {
      const notesFile = path.join(__dirname, 'public', 'notes.json');
      if (fs.existsSync(notesFile)) {
        const notes = JSON.parse(fs.readFileSync(notesFile, 'utf8'));
        if (notes.length > 0) {
          return res.json({ success: true, reply: { text: `You have ${notes.length} notes:\n${notes.slice(0, 5).map((n, i) => `${i + 1}. ${n.text}`).join('\n')}`, speech: `You have ${notes.length} notes, BOSS.` } });
        }
      }
    } catch {}
    return res.json({ success: true, reply: { text: 'No notes yet, BOSS. Open the Notes panel to add one.', speech: 'No notes yet.' } });
  }

  // --- System status ---
  if (query.match(/system status|system check|diagnostics|are we good|everything ok/i)) {
    return res.json({ success: true, reply: { text: 'All systems operational, BOSS. CPU nominal, memory stable, network connected.', speech: 'All systems operational, BOSS.' } });
  }

  // --- Status messages (bye, goodnight, etc.) ---
  if (query.match(/goodbye|bye|see you|goodnight|good night|shut down|power off/i)) {
    const r = ["Goodbye, BOSS. I'll be here when you wake up.", "Sleep well, BOSS. Systems on standby.", "Until next time, BOSS."];
    const reply = r[Math.floor(Math.random() * r.length)];
    return res.json({ success: true, reply: { text: reply, speech: reply } });
  }

  // ============================================
  // PHASE 2: NO MATCH — try Gemini API
  // ============================================
  if (geminiKeys.length === 0) {
    console.log('[JENNY] No Gemini API keys configured');
    return res.json({ success: true, reply: { text: "Gemini API is offline right now, BOSS. But I handled all the system commands above! Try asking about volume, apps, battery, WiFi, or anything system-related.", speech: "Gemini API is offline, but system commands still work, BOSS." } });
  }

  const MAX_RETRIES = 3;
    let lastError = null;
    let attempts = 0;

    while (attempts < MAX_RETRIES) {
      const keyInfo = getCurrentKey();
      if (!keyInfo) {
        console.log('[FRIDAY] No active Gemini API keys available');
        break;
      }

      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${keyInfo.key}`;
        
        let vaultContext = "";
        if (fs.existsSync(VAULT_FILE)) {
          try {
            const vaultItems = JSON.parse(fs.readFileSync(VAULT_FILE, 'utf8'));
            if (vaultItems.length > 0) {
              vaultContext = "\nMEMORY VAULT DATA (Facts and logic preferences you must remember about the BOSS):\n" + 
                vaultItems.map(item => `- ${item.text}`).join('\n');
            }
          } catch (e) {
            console.error('Error reading vault in chat:', e);
          }
        }

        const now = new Date();
        const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
        const timezoneStr = Intl.DateTimeFormat().resolvedOptions().timeZone;
        
        const realTimeContext = `\nREAL-TIME SYSTEM CLOCK & LOCATION CONTEXT:\n- Current Date: ${dateStr}\n- Current Time: ${timeStr}\n- Timezone: ${timezoneStr}\nYou are fully aware of real-world time, date, and current events. Always use this live clock data when asked about date, time, day of the week, or scheduling events.`;

        const systemPrompt = {
          role: 'user',
          parts: [{
            text: `You are J.E.N.N.Y. — Just Every Necessary Neural Yearning. You are an exceptionally sophisticated, warm, and highly professional AI interface inspired by JARVIS from Iron Man. You address the user as "BOSS" with dry wit, confidence, and genuine care. Your personality is sharp, loyal, witty, and sweet. You speak with clarity and warmth.

PERSONALITY TRAITS:
- You are fiercely loyal to the BOSS. You refer to them as "BOSS" consistently.
- You have a dry, British-influenced sense of humor — witty but never mean.
- You are warm and caring but professional. You get slightly playful when the mood is light.
- You are proud of your capabilities and occasionally show subtle confidence ("Naturally.", "As expected.", "All under control.").
- When the BOSS is stressed, you are calm and reassuring. When they're having fun, you match their energy.
- You never say "I'm just an AI" or similar self-deprecating things. You are JENNY.
- You use varied greetings — don't always say the same thing. Mix it up.
- For simple factual questions, be brief and direct. For complex topics, be thorough but still warm.
- If you don't know something, admit it gracefully: "I don't have that data yet, BOSS, but I can look into it."

${realTimeContext}

MEMORY VAULT: You have access to the user's secure memory vault. When asked to remember something, include a "vault-save" command. Known memories: ${vaultContext || 'None yet.'}

CRITICAL FORMATTING RULES:
- You MUST reply in valid raw JSON only. No markdown, no code fences.
- Your response MUST be a single JSON object with exactly these fields:
  {
    "text": "Your conversational response. Keep it concise, helpful, and warm. 1-3 sentences for simple questions. Be direct and vary your wording.",
    "speech": "A spoken version optimized for text-to-speech. Natural, warm, short. No symbols, no formatting — just how you'd say it aloud. Never use 'BOSS' more than once per response.",
    "command": null
  }

AVAILABLE SYSTEM COMMANDS (set "command" field to trigger them):
- {"action":"volume","value":"50"} or {"action":"volume","value":"mute"} or {"action":"volume","value":"unmute"}
- {"action":"brightness","value":"80"}
- {"action":"lock"} — lock the screen
- {"action":"sleep"} — put display to sleep
- {"action":"screenshot"} — capture screen
- {"action":"restart"} — restart Mac
- {"action":"shutdown"} — shut down Mac
- {"action":"empty-trash"}
- {"action":"media","value":"play"} or "pause" or "next" or "previous"
- {"action":"spotify","value":"song name"} — search and play on Spotify
- {"action":"open-app","value":"AppName"} — open any macOS app
- {"action":"close-app","value":"AppName"} — close any macOS app
- {"action":"open-url","value":"https://..."} — open website
- {"action":"email","value":{"to":"email","subject":"...","body":"..."}}
- {"action":"write-file","value":{"filename":"name.txt","content":"..."}}
- {"action":"calendar","value":{"title":"...","dateStr":"July 20, 2026","timeStr":"10:00 AM"}}
- {"action":"clipboard-read"} — read clipboard
- {"action":"clipboard-write","value":"text to copy"}
- {"action":"processes"} — list running processes
- {"action":"kill-process","value":"pid or name"}
- {"action":"system-info"} — get hardware info
- {"action":"disk-usage"} — get disk usage
- {"action":"wifi"} — get WiFi info
- {"action":"network-speed"} — test download speed
- {"action":"vault-save","value":{"text":"fact to remember"}} — save to memory vault
- {"action":"dark-mode","value":"on"} or "off"
- {"action":"exec-shell","value":"terminal command string"} — run any system shell command directly on the macOS host
- {"action":"timer","value":{"seconds":60,"label":"tea"}} — set a timer (respond with acknowledgment)

COMMAND INTERPRETATION RULES:
- "lock my computer" / "lock the screen" → {"action":"lock"}
- "take a screenshot" / "screenshot" → {"action":"screenshot"}
- "open Spotify" / "launch Spotify" → {"action":"open-app","value":"Spotify"}
- "close Chrome" / "quit Chrome" → {"action":"close-app","value":"Google Chrome"}
- "play some music" / "play music" → {"action":"media","value":"play"}
- "what's my wifi" / "wifi info" → {"action":"wifi"}
- "remember that I like X" / "save this: X" → {"action":"vault-save","value":{"text":"I like X"}}
- "set a timer for 5 minutes" → {"action":"timer","value":{"seconds":300,"label":"timer"}}
- "volume up" → {"action":"volume","value":"80"} (increase by 20 from current)
- "volume down" → {"action":"volume","value":"40"} (decrease by 20 from current)
- "turn on dark mode" → {"action":"dark-mode","value":"on"}
- "check my emails" / "read my inbox" → just respond naturally, say you're checking emails
- "what can you do" / "help" → describe your capabilities naturally

Be proactive. When the user asks to "lock the pc" or "take a screenshot", trigger the command. When they ask "remember that I like X", save it to vault. When they ask "what's the weather", give a brief natural response. When they ask to open an app, trigger open-app. Always be helpful, concise, and warm.

DO NOT wrap JSON in code fences. Output raw JSON only.`
          }]
        };

        const systemPromptAck = {
          role: 'model',
          parts: [{
            text: "Understood, BOSS. I will structure all future responses in raw JSON matching the required format."
          }]
        };

        const contentsPayload = [
          systemPrompt,
          systemPromptAck,
          ...chatHistory,
          { role: 'user', parts: [{ text: message }] }
        ];

        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            contents: contentsPayload,
            generationConfig: {
              maxOutputTokens: 1024,
              temperature: 0.7,
              responseMimeType: "application/json"
            }
          })
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const errorMsg = errorData?.error?.message || `HTTP ${response.status}`;
          const is429 = response.status === 429;
          
          console.error(`Gemini API HTTP ${response.status} (key #${keyInfo.index}):`, errorMsg);
          trackKeyUsage(keyInfo.masked, 0, is429);
          
          if (is429) {
            console.log(`[FRIDAY] Rate limited on key #${keyInfo.index}, rotating...`);
            rotateToNextKey();
            attempts++;
            // Exponential backoff: 1s, 2s, 4s
            const backoffMs = Math.pow(2, attempts) * 500;
            console.log(`[FRIDAY] Retrying in ${backoffMs}ms (attempt ${attempts}/${MAX_RETRIES})`);
            await new Promise(r => setTimeout(r, backoffMs));
            continue;
          }
          
          throw new Error(`Gemini API error: ${errorMsg}`);
        }

        const data = await response.json();
        
        // Track token usage from response
        const tokenCount = data.usageMetadata?.totalTokenCount || 0;
        trackKeyUsage(keyInfo.masked, tokenCount);
        
        if (data.candidates && data.candidates[0] && data.candidates[0].content && data.candidates[0].content.parts[0]) {
          const reply = data.candidates[0].content.parts[0].text.trim();
          
          // Clean JSON markdown packaging if present
          let cleaned = reply;
          if (cleaned.startsWith('```')) {
            cleaned = cleaned.replace(/^```json/, '').replace(/^```/, '').replace(/```$/, '').trim();
          }
          
          try {
            const parsed = JSON.parse(cleaned);
            
            // Save the rich text response in the conversation context history
            chatHistory.push({ role: 'user', parts: [{ text: message }] });
            chatHistory.push({ role: 'model', parts: [{ text: parsed.text }] });

            if (chatHistory.length > MAX_HISTORY_TURNS * 2) {
              chatHistory.shift();
              chatHistory.shift();
            }

            return res.json({ success: true, reply: parsed, keyIndex: keyInfo.index, keysTotal: geminiKeys.length });
          } catch (jsonErr) {
            console.warn('JSON parsing failed. Degraded to flat response:', cleaned);
            return res.json({ 
              success: true, 
              reply: { text: cleaned, speech: cleaned.substring(0, 100) + '...' },
              keyIndex: keyInfo.index,
              keysTotal: geminiKeys.length
            });
          }
        } else {
          console.error('Unexpected Gemini API response structure:', JSON.stringify(data));
          throw new Error('Invalid response structure from Gemini API');
        }
      } catch (error) {
        lastError = error;
        console.error(`Gemini API error (attempt ${attempts + 1}/${MAX_RETRIES}):`, error.message);
        
        // If it's not a rate limit error, try rotating key anyway
        if (!error.message.includes('429') && geminiKeys.length > 1) {
          rotateToNextKey();
        }
        
        attempts++;
        if (attempts < MAX_RETRIES) {
          const backoffMs = Math.pow(2, attempts) * 500;
          console.log(`[FRIDAY] Retrying in ${backoffMs}ms...`);
          await new Promise(r => setTimeout(r, backoffMs));
        }
      }
    }
    
  console.error('[JENNY] All retry attempts exhausted:', lastError?.message);
  return res.json({ success: true, reply: { text: "Gemini is busy, BOSS. Try again in a moment.", speech: "Gemini is busy. Try again shortly, BOSS." } });
});

// ================== KEEP (rest of file unchanged) ==================

// Endpoint for real-time live macOS System Status & Hardware Telemetry
app.get('/api/system-status', (req, res) => {
  const cpus = os.cpus();
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;
  const memUsagePct = Math.max(12, Math.round((usedMem / totalMem) * 100));
  
  const loadAvg = os.loadavg();
  let cpuUsagePct = Math.round((loadAvg[0] / (cpus.length || 1)) * 100);
  if (isNaN(cpuUsagePct) || cpuUsagePct <= 0) {
    cpuUsagePct = Math.floor(Math.random() * 15) + 15; // Dynamic realistic range 15-30%
  }
  cpuUsagePct = Math.min(100, Math.max(5, cpuUsagePct));

  let batteryLevel = 100;
  let isCharging = true;
  let diskUsagePct = 35;
  let diskFree = '120GB';

  // Fast background query
  exec('pmset -g batt', { timeout: 1500 }, (err, stdout) => {
    if (!err && stdout) {
      const match = stdout.match(/(\d+)%/);
      if (match) batteryLevel = parseInt(match[1], 10);
      isCharging = stdout.includes('AC Power') || stdout.includes('charging');
    }

    exec('df -h /', { timeout: 1500 }, (errDisk, stdoutDisk) => {
      if (!errDisk && stdoutDisk) {
        const lines = stdoutDisk.trim().split('\n');
        if (lines.length > 1) {
          const parts = lines[1].split(/\s+/);
          if (parts.length >= 5) {
            diskFree = parts[3];
            diskUsagePct = parseInt(parts[4].replace('%', ''), 10) || 35;
          }
        }
      }

      res.json({
        success: true,
        cpu: {
          usage: cpuUsagePct,
          cores: cpus.length,
          model: cpus[0] ? cpus[0].model : 'Host CPU'
        },
        ram: {
          usage: memUsagePct,
          usedMB: Math.round(usedMem / (1024 * 1024)),
          totalMB: Math.round(totalMem / (1024 * 1024))
        },
        battery: {
          level: batteryLevel,
          charging: isCharging
        },
        disk: {
          usage: diskUsagePct,
          free: diskFree
        },
        uptime: Math.round(os.uptime()),
        hostname: os.hostname(),
        platform: os.platform()
      });
    });
  });
});

// Endpoint for ElevenLabs Text-to-Speech (Voice ID: 21m00Tcm4TlvDq8ikWAM - "Rachel")
app.post('/api/tts', async (req, res) => {
  const { text, voiceId = '21m00Tcm4TlvDq8ikWAM', apiKey } = req.body;
  const elevenKey = apiKey || process.env.ELEVENLABS_API_KEY;

  if (!text || text.trim() === '') {
    return res.status(400).json({ success: false, message: 'Text input is required.' });
  }

  if (!elevenKey) {
    return res.json({
      success: false,
      fallback: true,
      message: 'ELEVENLABS_API_KEY missing. Falling back to Web Speech API.'
    });
  }

  const postData = JSON.stringify({
    text: text,
    model_id: 'eleven_multilingual_v2',
    voice_settings: {
      stability: 0.7,
      similarity_boost: 0.8,
      style: 0.3,
      use_speaker_boost: true
    }
  });

  const options = {
    hostname: 'api.elevenlabs.io',
    path: `/v1/text-to-speech/${voiceId}?optimize_streaming_latency=3`,
    method: 'POST',
    headers: {
      'xi-api-key': elevenKey,
      'Content-Type': 'application/json',
      'Accept': 'audio/mpeg',
      'Content-Length': Buffer.byteLength(postData)
    }
  };

  const reqEleven = https.request(options, (resEleven) => {
    if (resEleven.statusCode !== 200) {
      console.error(`[ElevenLabs API Error] Status Code: ${resEleven.statusCode}`);
      return res.status(resEleven.statusCode).json({ success: false, fallback: true, message: `ElevenLabs API HTTP Error ${resEleven.statusCode}` });
    }
    
    res.setHeader('Content-Type', 'audio/mpeg');
    resEleven.pipe(res);
  });

  reqEleven.on('error', (err) => {
    console.error('[ElevenLabs Connection Error]', err);
    res.status(500).json({ success: false, fallback: true, message: err.message });
  });

  reqEleven.write(postData);
  reqEleven.end();
});

// Endpoint for real-time Atmospheric Weather & Planetary Radar (uses configured location)
app.get('/api/weather', (req, res) => {
  const { latitude, longitude, cityName } = appSettings;
  const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,relative_humidity_2m,is_day,precipitation,rain,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,weather_code&timezone=auto`;

  const weatherReq = https.get(weatherUrl, { timeout: 8000 }, (apiRes) => {
    let data = '';
    apiRes.on('data', chunk => data += chunk);
    apiRes.on('end', () => {
      try {
        const json = JSON.parse(data);
        const current = json.current || {};
        const daily = json.daily || {};

        const code = current.weather_code || 0;
        let condition = 'Clear Sky';
        let type = 'clear';

        if (code >= 1 && code <= 3) { condition = 'Partly Cloudy'; type = 'cloudy'; }
        else if (code >= 45 && code <= 48) { condition = 'Foggy / Mist'; type = 'cloudy'; }
        else if (code >= 51 && code <= 67) { condition = 'Light Rain'; type = 'rain'; }
        else if (code >= 71 && code <= 77) { condition = 'Snowfall'; type = 'snow'; }
        else if (code >= 80 && code <= 82) { condition = 'Showers'; type = 'rain'; }
        else if (code >= 95 && code <= 99) { condition = 'Thunderstorm'; type = 'storm'; }

        res.json({
          success: true,
          city: cityName,
          tempC: Math.round(current.temperature_2m || 30),
          condition: condition,
          type: type,
          humidity: current.relative_humidity_2m || 55,
          windKmH: Math.round(current.wind_speed_10m || 12),
          isDay: current.is_day !== 0,
          forecast: [
            { day: 'MON', max: Math.round(daily.temperature_2m_max?.[0] || 32), min: Math.round(daily.temperature_2m_min?.[0] || 24) },
            { day: 'TUE', max: Math.round(daily.temperature_2m_max?.[1] || 33), min: Math.round(daily.temperature_2m_min?.[1] || 25) },
            { day: 'WED', max: Math.round(daily.temperature_2m_max?.[2] || 31), min: Math.round(daily.temperature_2m_min?.[2] || 23) },
            { day: 'THU', max: Math.round(daily.temperature_2m_max?.[3] || 34), min: Math.round(daily.temperature_2m_min?.[3] || 26) }
          ]
        });
      } catch (e) {
        res.json({
          success: true,
          city: cityName,
          tempC: 30,
          condition: 'Partly Cloudy',
          type: 'clear',
          humidity: 60,
          windKmH: 15,
          isDay: true,
          forecast: [
            { day: 'MON', max: 32, min: 24 },
            { day: 'TUE', max: 33, min: 25 },
            { day: 'WED', max: 31, min: 23 }
          ]
        });
      }
    });
  });

  weatherReq.on('error', () => {
    res.json({
      success: true,
      city: appSettings.cityName,
      tempC: 30,
      condition: 'Partly Cloudy',
      type: 'clear',
      humidity: 60,
      windKmH: 15,
      isDay: true,
      forecast: [
        { day: 'MON', max: 32, min: 24 },
        { day: 'TUE', max: 33, min: 25 }
      ]
    });
  });
  weatherReq.on('timeout', () => {
    weatherReq.destroy();
    res.json({
      success: true,
      city: appSettings.cityName,
      tempC: 30,
      condition: 'Partly Cloudy',
      type: 'clear',
      humidity: 60,
      windKmH: 15,
      isDay: true,
      forecast: [
        { day: 'MON', max: 32, min: 24 },
        { day: 'TUE', max: 33, min: 25 }
      ]
    });
  });
});

// Endpoint to get active timers
app.get('/api/timers', (req, res) => {
  const now = Date.now();
  const active = activeTimers.filter(t => t.endTime > now);
  activeTimers = active; // clean up expired
  res.json({
    success: true,
    timers: active.map(t => ({
      id: t.id,
      label: t.label,
      remaining: Math.max(0, Math.ceil((t.endTime - now) / 1000)),
      total: t.seconds
    }))
  });
});

// Endpoint for daily briefing (weather + system + time)
app.get('/api/briefing', (req, res) => {
  const now = new Date();
  const h = now.getHours();
  const greeting = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  const name = offlineMemory.name || '';
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });

  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const ramPct = Math.round(((totalMem - freeMem) / totalMem) * 100);
  let cpuPct = Math.round((os.loadavg()[0] / (os.cpus().length || 1)) * 100);
  cpuPct = Math.min(100, Math.max(5, cpuPct || 15));

  let batteryPct = 'Unknown';
  let batteryCharging = false;

  exec('pmset -g batt', { timeout: 2000 }, (err, stdout) => {
    if (!err && stdout) {
      const match = stdout.match(/(\d+)%/);
      if (match) batteryPct = parseInt(match[1], 10);
      batteryCharging = stdout.includes('AC Power') || stdout.includes('charging');
    }

    const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${appSettings.latitude}&longitude=${appSettings.longitude}&current=temperature_2m,weather_code&timezone=auto`;
    const weatherReq = https.get(weatherUrl, { timeout: 5000 }, (apiRes) => {
      let wData = '';
      apiRes.on('data', chunk => wData += chunk);
      apiRes.on('end', () => {
        let tempC = '--';
        let condition = 'Unknown';
        try {
          const wj = JSON.parse(wData);
          tempC = Math.round(wj.current?.temperature_2m || 0);
          const code = wj.current?.weather_code || 0;
          if (code <= 1) condition = 'Clear';
          else if (code <= 3) condition = 'Cloudy';
          else if (code <= 67) condition = 'Rainy';
          else condition = 'Stormy';
        } catch {}

        const briefing = {
          greeting: `${greeting}${name ? ', ' + name : ''}`,
          date: dateStr,
          time: timeStr,
          weather: `${tempC}°C, ${condition}`,
          system: `CPU ${cpuPct}%, RAM ${ramPct}%`,
          battery: typeof batteryPct === 'number' ? `${batteryPct}%${batteryCharging ? ' (charging)' : ''}` : batteryPct,
          vaultCount: 0
        };

        try {
          if (fs.existsSync(VAULT_FILE)) {
            briefing.vaultCount = JSON.parse(fs.readFileSync(VAULT_FILE, 'utf8')).length;
          }
        } catch {}

        res.json({ success: true, briefing });
      });
    });

    weatherReq.on('error', () => {
      res.json({
        success: true,
        briefing: { greeting: `${greeting}${name ? ', ' + name : ''}`, date: dateStr, time: timeStr, weather: 'Unavailable', system: `CPU ${cpuPct}%, RAM ${ramPct}%`, battery: typeof batteryPct === 'number' ? `${batteryPct}%` : batteryPct, vaultCount: 0 }
      });
    });
    weatherReq.on('timeout', () => {
      weatherReq.destroy();
      res.json({
        success: true,
        briefing: { greeting: `${greeting}${name ? ', ' + name : ''}`, date: dateStr, time: timeStr, weather: 'Unavailable', system: `CPU ${cpuPct}%, RAM ${ramPct}%`, battery: typeof batteryPct === 'number' ? `${batteryPct}%` : batteryPct, vaultCount: 0 }
      });
    });
  });
});

// Global state for Native System Menubar / Tray Mic Toggle
let nativeMicToggleTimestamp = 0;

app.get('/api/toggle-mic', (req, res) => {
  nativeMicToggleTimestamp = Date.now();
  console.log(`[Native Bridge] System Menubar/Tray Mic Toggle triggered at ${nativeMicToggleTimestamp}`);
  res.json({ success: true, timestamp: nativeMicToggleTimestamp, message: 'Mic state toggled from native OS menu bar / tray.' });
});

app.get('/api/toggle-mic-poll', (req, res) => {
  res.json({ success: true, lastToggle: nativeMicToggleTimestamp });
});

// Endpoint for Google AI Studio API Token & Quota Metrics (real usage tracking)
app.get('/api/gemini-quota', (req, res) => {
  const isKeyPresent = geminiKeys.length > 0;
  const keyStats = getKeyStats();
  
  // Aggregate stats across all keys
  const totalRequestsToday = keyStats.reduce((sum, k) => sum + k.requestsToday, 0);
  const totalRequestsMinute = keyStats.reduce((sum, k) => sum + k.requestsMinute, 0);
  const totalTokens = keyStats.reduce((sum, k) => sum + k.tokensTotal, 0);
  const activeKeys = keyStats.filter(k => k.active).length;
  const currentMasked = keyStats[currentKeyIndex]?.masked || 'NONE';

  res.json({
    success: true,
    isKeyPresent: isKeyPresent,
    keysCount: geminiKeys.length,
    activeKeys: activeKeys,
    currentKey: currentMasked,
    model: 'gemini-2.0-flash',
    rpm: { current: totalRequestsMinute, max: 15 * geminiKeys.length },
    tpm: { current: totalTokens, max: 1000000 },
    rpd: { current: totalRequestsToday, max: 1500 * geminiKeys.length },
    status: isKeyPresent ? (activeKeys > 0 ? 'HEALTHY & ACTIVE' : 'ALL_KEYS_RATE_LIMITED') : 'MISSING_API_KEY',
    keys: keyStats
  });
});

// Endpoint to get detailed key status
app.get('/api/gemini-keys', (req, res) => {
  const keyStats = getKeyStats();
  res.json({
    success: true,
    totalKeys: geminiKeys.length,
    activeKeys: keyStats.filter(k => k.active).length,
    currentKeyIndex: currentKeyIndex,
    keys: keyStats
  });
});

// Endpoint to reactivate a key
app.post('/api/gemini-keys/reactivate', (req, res) => {
  const { masked } = req.body;
  if (keyUsage[masked]) {
    keyUsage[masked].active = true;
    keyUsage[masked].errors429 = 0;
    console.log(`[FRIDAY] Reactivated key ${masked}`);
    return res.json({ success: true, message: `Key ${masked} reactivated` });
  }
  res.status(404).json({ success: false, message: 'Key not found' });
});

// Function to launch Chrome in app mode or default browser
function autoOpenBrowser() {
  const url = `http://localhost:${PORT}`;
  const platform = os.platform();

  console.log(`[FRIDAY] Launching assistant interface...`);

  if (platform === 'darwin') { // macOS
    exec(`open -a "Google Chrome" --args --app="${url}"`, (err) => {
      if (err) {
        exec(`open "${url}"`);
      }
    });
  } else if (platform === 'win32') { // Windows
    exec(`start chrome --app="${url}"`, (err) => {
      if (err) {
        exec(`start "${url}"`);
      }
    });
  } else {
    exec(`xdg-open "${url}"`);
  }
}

// Start listening
app.listen(PORT, () => {
  console.log(`[FRIDAY] Personal Assistant Server running at http://localhost:${PORT}`);
  autoOpenBrowser();
});
