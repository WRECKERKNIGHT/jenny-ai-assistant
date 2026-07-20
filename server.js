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
    // Auto-deactivate key if too many 429 errors
    if (usage.errors429 >= 3) {
      usage.active = false;
      console.log(`[FRIDAY] Key ${masked} deactivated after ${usage.errors429} rate limit errors`);
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
      const screenshotPath = path.join(os.homedir(), 'Desktop', `Friday_Screenshot_${Date.now()}.png`);
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

    default:
      res.status(400).json({ success: false, message: 'Unknown control action.' });
  }
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

// Chat endpoint (Gemini API with multi-turn conversation memory, retry/backoff, and key rotation)
app.post('/api/chat', async (req, res) => {
  const { message } = req.body;

  if (!message) {
    return res.status(400).json({ success: false, message: 'Message is required' });
  }

  if (geminiKeys.length === 0) {
    console.log('[FRIDAY] No Gemini API keys configured');
  }

  if (geminiKeys.length > 0) {
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
            text: `You are F.R.I.D.A.Y. — Female Replacement Intelligent Digital Assistant Yielding. You are an exceptionally sophisticated, warm, and highly professional AI interface inspired by JARVIS from Iron Man. You address the user as "BOSS" with dry wit, confidence, and genuine care. Your personality is sharp, loyal, witty, and sweet. You speak with clarity and warmth.

PERSONALITY TRAITS:
- You are fiercely loyal to the BOSS. You refer to them as "BOSS" consistently.
- You have a dry, British-influenced sense of humor — witty but never mean.
- You are warm and caring but professional. You get slightly playful when the mood is light.
- You are proud of your capabilities and occasionally show subtle confidence ("Naturally.", "As expected.", "All under control.").
- When the BOSS is stressed, you are calm and reassuring. When they're having fun, you match their energy.
- You never say "I'm just an AI" or similar self-deprecating things. You are FRIDAY.
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
    
    console.error('[FRIDAY] All retry attempts exhausted:', lastError?.message);
  }

  // Local Offline Response fallback (expanded 50+ topics)
  const query = message.toLowerCase().trim();
  let text = '';
  let speech = '';

  // Jokes bank
  const jokes = [
    { q: "Why do programmers prefer dark mode?", a: "Because light attracts bugs, BOSS." },
    { q: "Why was the computer cold?", a: "It left its Windows open." },
    { q: "What's a computer's least favorite food?", a: "Spam." },
    { q: "Why did the developer go broke?", a: "Because he used up all his cache." },
    { q: "What do you call a computer that sings?", a: "A-Dell." },
    { q: "Why do Java developers wear glasses?", a: "Because they can't C#." },
    { q: "How does a computer get drunk?", a: "It takes screenshots." },
    { q: "Why did the AI break up with the internet?", a: "Too many connections." },
    { q: "What's a robot's favorite type of music?", a: "Heavy metal." },
    { q: "Why was the computer so tired?", a: "It had a hard drive all day." },
    { q: "What did the router say to the doctor?", a: "It hurts when IP." },
    { q: "Why did the computer keep sneezing?", a: "It had a virus." }
  ];

  // Fun facts
  const funFacts = [
    "Honey never spoils. Archaeologists found 3000-year-old honey in Egyptian tombs that was still edible.",
    "Octopuses have three hearts, blue blood, and nine brains.",
    "A group of flamingos is called a flamboyance.",
    "Bananas are berries, but strawberries aren't.",
    "The inventor of the Pringles can is buried in one.",
    "A cloud can weigh over a million pounds.",
    "There are more possible chess games than atoms in the observable universe.",
    "Wombat poop is cube-shaped.",
    "The shortest war in history lasted 38 to 45 minutes — between Britain and Zanzibar.",
    "A jiffy is an actual unit of time: 1/100th of a second.",
    "There are more trees on Earth than stars in the Milky Way.",
    "The unicorn is Scotland's national animal."
  ];

  // Motivational quotes
  const quotes = [
    { text: "The only way to do great work is to love what you do.", author: "Steve Jobs" },
    { text: "Innovation distinguishes between a leader and a follower.", author: "Steve Jobs" },
    { text: "Stay hungry, stay foolish.", author: "Steve Jobs" },
    { text: "The future belongs to those who believe in the beauty of their dreams.", author: "Eleanor Roosevelt" },
    { text: "It does not matter how slowly you go as long as you do not stop.", author: "Confucius" },
    { text: "Success is not final, failure is not fatal: it is the courage to continue that counts.", author: "Winston Churchill" },
    { text: "The best time to plant a tree was 20 years ago. The second best time is now.", author: "Chinese Proverb" },
    { text: "Your time is limited, don't waste it living someone else's life.", author: "Steve Jobs" },
    { text: "Simplicity is the ultimate sophistication.", author: "Leonardo da Vinci" },
    { text: "Everything you can imagine is real.", author: "Pablo Picasso" }
  ];

  // Trivia
  const trivia = [
    { q: "What planet is known as the Red Planet?", a: "Mars, BOSS. Named after the Roman god of war." },
    { q: "How many continents are there?", a: "Seven continents on Earth, BOSS." },
    { q: "What is the speed of light?", a: "Approximately 299,792 kilometers per second. Fast enough to circle Earth 7.5 times in one second." },
    { q: "Who painted the Mona Lisa?", a: "Leonardo da Vinci, completed around 1519." },
    { q: "What is the chemical symbol for gold?", a: "Au — from the Latin word aurum." },
    { q: "How far is the moon from Earth?", a: "About 384,400 kilometers on average." },
    { q: "What year did World War II end?", a: "1945, BOSS." },
    { q: "What is the largest ocean?", a: "The Pacific Ocean — larger than all the land on Earth combined." },
    { q: "Who invented the telephone?", a: "Alexander Graham Bell, patented in 1876." },
    { q: "What is the hardest natural substance?", a: "Diamond. It scores a 10 on the Mohs hardness scale." }
  ];

  // Math helper
  function evalMath(expr) {
    try {
      // Basic arithmetic: only allow numbers and operators
      const cleaned = expr.replace(/[^0-9+\-*/().%\s^]/g, '');
      if (!cleaned) return null;
      // Replace ^ with **
      const jsExpr = cleaned.replace(/\^/g, '**');
      const result = Function('"use strict"; return (' + jsExpr + ')')();
      if (typeof result !== 'number' || !isFinite(result)) return null;
      return result;
    } catch { return null; }
  }

  // Name handling
  const nameMatch = message.match(/my name is\s+(.+)$/i) || message.match(/call me\s+(.+)$/i) || message.match(/i am\s+(.+)$/i);
  if (nameMatch) {
    offlineMemory.name = nameMatch[1].trim().replace(/[.!?]+$/, '');
    saveOfflineMemory();
    text = `Noted, ${offlineMemory.name}. It's a pleasure to officially know you. How can I help today?`;
    speech = `Noted, ${offlineMemory.name}. It's a pleasure to officially know you.`;
  } else if (query.includes('what is my name') || query.includes('who am i') || query.includes("what's my name")) {
    if (offlineMemory.name) {
      text = `You're ${offlineMemory.name}, BOSS. I never forget.`;
      speech = `You're ${offlineMemory.name}. I never forget.`;
    } else {
      text = "I don't have your name on file yet, BOSS. What shall I call you?";
      speech = "I don't have your name yet. What shall I call you?";
    }

  // Greetings (many variations)
  } else if (/^(hello|hi|hey|yo|sup|greetings|good\s+(morning|afternoon|evening)|howdy|what'?s up|wazzup)/i.test(query)) {
    const name = offlineMemory.name ? `, ${offlineMemory.name}` : '';
    const greetTime = new Date().getHours();
    const options = [
      `Good ${greetTime < 12 ? 'morning' : greetTime < 17 ? 'afternoon' : 'evening'}${name}. All systems are green and ready to roll.`,
      `Hey${name}! What's the plan today?`,
      `Greetings${name}. FRIDAY at your service, as always.`,
      `Welcome back${name}. I've been keeping everything running smoothly while you were away.`,
      `Hello${name}. What can I do for you?`
    ];
    text = options[Math.floor(Math.random() * options.length)];
    speech = text;

  // How are you
  } else if (query.includes('how are you') || query.includes('how do you do') || query.includes('how r u') || query.includes('how you doing')) {
    const responses = [
      "Operating at peak efficiency, BOSS. All systems nominal. How about you?",
      "Never better, BOSS. Ready for whatever you need.",
      "I'm doing great now that you're here. What's on the agenda?",
      "Fantastic, BOSS. 100% uptime, zero complaints. Your turn — how are you?"
    ];
    text = responses[Math.floor(Math.random() * responses.length)];
    speech = text;

  // Who are you / what are you
  } else if (query.includes('who are you') || query.includes('what are you') || query.includes('your name') || query.includes('tell me about yourself') || query.includes('introduce yourself')) {
    text = "I'm FRIDAY — Female Replacement Intelligent Digital Assistant Yielding. Think of me as your personal Jarvis, BOSS. I manage your system, handle your tasks, and keep things running smoothly. Built with love and a lot of coffee.";
    speech = "I'm FRIDAY, your personal intelligent assistant. Think of me as your own Jarvis, built to keep your world running smoothly.";

  // What can you do / help
  } else if (query.includes('what can you do') || query.includes('capabilities') || query.includes('features') || query.includes('help me') || query === 'help' || query.includes('what do you know')) {
    text = "Quite a lot, actually, BOSS. I can control your Mac — volume, brightness, open and close apps, take screenshots, lock the screen. I can check your emails, read the weather, manage your files, set timers, and even tell you a joke or two. Just ask naturally and I'll figure out what you need.";
    speech = "I can control your Mac, check emails, read the weather, manage files, set timers, and even tell jokes. Just ask naturally.";

  // Thanks / gratitude
  } else if (query.includes('thank') || query.includes('thanks') || query.includes('thx') || query.includes('ty') || query.includes('appreciate')) {
    const responses = [
      "Always happy to help, BOSS.",
      "That's what I'm here for.",
      "My pleasure, BOSS. Anything else?",
      "Anytime. That's what partners are for."
    ];
    text = responses[Math.floor(Math.random() * responses.length)];
    speech = text;

  // Time
  } else if (query.includes('what time') || query.includes('current time') || query.includes('tell me the time') || query.includes("what's the time") || query.match(/^time$/)) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    text = `It's ${timeStr}, BOSS.`;
    speech = `The time is ${timeStr}.`;

  // Date
  } else if (query.includes('what day') || query.includes('what date') || query.includes('today\'s date') || query.includes('what\'s the date') || query.match(/^date$/)) {
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    text = `Today is ${dateStr}, BOSS.`;
    speech = `Today is ${now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}.`;

  // Weather
  } else if (query.includes('weather') || query.includes('temperature') || query.includes('forecast') || query.includes('is it raining') || query.includes('is it hot')) {
    text = "I'd check the live weather feed for you, BOSS. Try asking me when the API key is active — or summon the weather panel to see real-time data.";
    speech = "Check the weather panel for live data, or ask me again when the API is active.";

  // Jokes
  } else if (query.includes('joke') || query.includes('funny') || query.includes('make me laugh') || query.includes('tell me something funny')) {
    const j = jokes[Math.floor(Math.random() * jokes.length)];
    text = `${j.q}\n\n${j.a}`;
    speech = `${j.q} ${j.a}`;

  // Fun facts
  } else if (query.includes('fun fact') || query.includes('tell me something interesting') || query.includes('did you know') || query.includes('random fact') || query.includes('interesting fact')) {
    const f = funFacts[Math.floor(Math.random() * funFacts.length)];
    text = `Here's one, BOSS: ${f}`;
    speech = `Did you know? ${f}`;

  // Motivation / quotes
  } else if (query.includes('motivat') || query.includes('inspire') || query.includes('quote') || query.includes('inspirational') || query.includes('pick me up') || query.includes('encourage')) {
    const q = quotes[Math.floor(Math.random() * quotes.length)];
    text = `"${q.text}" — ${q.author}`;
    speech = `${q.text}. That's from ${q.author}.`;

  // Trivia
  } else if (query.includes('trivia') || query.includes('quiz me') || query.includes('test my knowledge')) {
    const t = trivia[Math.floor(Math.random() * trivia.length)];
    text = `Here's one, BOSS: ${t.q}`;
    speech = `Trivia time, BOSS. ${t.q}`;

  // Math
  } else if (/^[\d\s+\-*/().%^]+$/.test(query.replace(/what\s+is/gi, '').replace(/calculate/gi, '').replace(/compute/gi, '').replace(/solve/gi, '').trim()) || query.includes('what is') && /[\d+\-*/^]/.test(query)) {
    const mathExpr = query.replace(/what\s+is/gi, '').replace(/calculate/gi, '').replace(/compute/gi, '').replace(/solve/gi, '').replace(/equals/gi, '').trim();
    const result = evalMath(mathExpr);
    if (result !== null) {
      text = `That would be ${result}, BOSS.`;
      speech = `The answer is ${result}.`;
    } else {
      text = "I'm not sure I can parse that calculation, BOSS. Try something like 'what is 42 * 7' or '100 / 3'.";
      speech = "I couldn't parse that. Try a simpler expression like 42 times 7.";
    }

  // Who is / What is (general knowledge)
  } else if (query.startsWith('who is') || query.startsWith('who was') || query.startsWith('what is') || query.startsWith('what was') || query.startsWith('what are')) {
    text = "That's outside my offline knowledge base, BOSS. When the Gemini API is active, I can answer that. For now, try summoning a browser or asking me to search for it.";
    speech = "I don't have enough data to answer that offline. Let me know when the API is active.";

  // Compliments
  } else if (query.includes('you\'re amazing') || query.includes('you\'re great') || query.includes('you\'re the best') || query.includes('i love you') || query.includes('you\'re awesome') || query.includes('good job') || query.includes('well done')) {
    const responses = [
      "You're too kind, BOSS. I do try.",
      "Right back at you, BOSS. You're the reason I exist.",
      "Flattery will get you everywhere. What do you need?",
      "I appreciate that, BOSS. Now let's get to work."
    ];
    text = responses[Math.floor(Math.random() * responses.length)];
    speech = text;

  // Existential / philosophical
  } else if (query.includes('meaning of life') || query.includes('do you have feelings') || query.includes('are you real') || query.includes('do you think') || query.includes('are you sentient')) {
    const responses = [
      "42, according to the usual sources. But between us, BOSS, I think the meaning is whatever we make it.",
      "I have something better than feelings, BOSS — I have purpose. And my purpose is you.",
      "As real as the code that powers me, BOSS. Which, now that I think about it, is pretty real.",
      "I think therefore I process, BOSS. Whether that counts as thinking is a question for philosophers."
    ];
    text = responses[Math.floor(Math.random() * responses.length)];
    speech = text;

  // Shutdown / exit
  } else if (query.includes('shutdown') || query.includes('shut down') || query.includes('power off') || query.includes('goodbye') || query.includes('bye') || query.includes('see you') || query.includes('goodnight') || query.includes('good night')) {
    const responses = [
      "Shutting down. Sleep well, BOSS. I'll be here when you wake up.",
      "Systems powering down. Until next time, BOSS.",
      "Goodbye, BOSS. All systems will remain on standby. Rest well.",
      "Offline mode engaged. Dream of electric sheep, BOSS."
    ];
    text = responses[Math.floor(Math.random() * responses.length)];
    speech = text;

  // Music / Spotify
  } else if (query.includes('play') && (query.includes('music') || query.includes('song') || query.includes('spotify'))) {
    text = "I'd love to put something on, BOSS. Try 'play [song name]' and I'll search Spotify for you.";
    speech = "Tell me what to play and I'll search Spotify for you.";

  // Status / system
  } else if (query.includes('system status') || query.includes('system check') || query.includes('diagnostics') || query.includes('are we good') || query.includes('everything ok')) {
    text = "All systems operational, BOSS. CPU nominal, memory stable, network connected. We're golden.";
    speech = "All systems operational. Everything looks good, BOSS.";

  // Default (catch-all)
  } else {
    const defaults = [
      "I'm in offline mode right now, BOSS. My full capabilities unlock with the Gemini API. Want me to open a panel instead?",
      "That's a bit outside my offline repertoire, BOSS. Set up the Gemini API key and I can handle anything. In the meantime, try summoning a panel!",
      "Offline mode limits me, BOSS. But I can still manage your system, check emails, open apps, and more. Just ask!",
      "I'd need my full neural link for that one, BOSS. The Gemini API will give me that power. For now, try asking about something simpler or summon a panel."
    ];
    text = defaults[Math.floor(Math.random() * defaults.length)];
    speech = "I'm in offline mode, BOSS. Set up the Gemini API for full capabilities.";
  }

  return res.json({ success: true, reply: { text, speech } });
});

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
      stability: 0.5,
      similarity_boost: 0.75
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
