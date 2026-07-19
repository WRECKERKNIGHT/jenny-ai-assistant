// ================================================
// F.R.I.D.A.Y. — Core Application v2.5
// ================================================

// AUDIO
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx;
function getCtx() { if (!audioCtx) audioCtx = new AudioCtx(); return audioCtx; }

function playTone(freq, dur, type = 'sine', vol = 0.08) {
  const ctx = getCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(vol, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + dur);
}

const sfx = {
  click: () => playTone(1200, 0.06, 'sine', 0.05),
  hover: () => playTone(800, 0.04, 'triangle', 0.03),
  confirm: () => { playTone(600, 0.1, 'sine', 0.06); setTimeout(() => playTone(900, 0.15, 'sine', 0.06), 80); },
  error: () => { playTone(200, 0.15, 'sawtooth', 0.06); setTimeout(() => playTone(150, 0.2, 'sawtooth', 0.06), 100); },
  boot: () => {
    [261.63, 329.63, 392, 523.25].forEach((f, i) => {
      setTimeout(() => playTone(f, 0.4, 'sine', 0.05), i * 120);
    });
  }
};

// ================================================
// BOOT SEQUENCE
// ================================================
const bootLines = [
  'Initializing neural acoustic core...',
  'Loading voice synthesis modules...',
  'Connecting to sensor array...',
  'Calibrating holographic display...',
  'Loading secure memory vault...',
  'Establishing encrypted channels...',
  'System diagnostics: ALL PASS',
  'Welcome, BOSS.'
];

async function runBoot() {
  const titleEl = document.getElementById('boot-title');
  const subEl = document.getElementById('boot-sub');
  const barEl = document.getElementById('boot-bar');
  const logsEl = document.getElementById('boot-logs');

  const title = 'F.R.I.D.A.Y.';
  for (let i = 0; i < title.length; i++) {
    titleEl.textContent += title[i];
    await sleep(80);
  }
  await sleep(300);
  subEl.classList.add('show');

  for (let i = 0; i < bootLines.length; i++) {
    const pct = Math.round(((i + 1) / bootLines.length) * 100);
    barEl.style.width = pct + '%';
    logsEl.textContent = bootLines[i];
    sfx.hover();
    await sleep(400 + Math.random() * 300);
  }

  sfx.boot();
  await sleep(600);

  document.getElementById('boot-screen').classList.add('done');
  document.getElementById('main-app').style.display = 'flex';

  await sleep(100);
  addAIMessage(getGreeting());
  startClock();
  startOrb();
  fetchQuota();
  setInterval(fetchQuota, 60000);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function getGreeting() {
  const h = new Date().getHours();
  const name = loadOfflineMemory().name;
  const who = name ? ` ${name}` : '';
  if (h < 12) return `Good morning${who}. I am FRIDAY, your personal assistant. All systems are operational. What are we doing today?`;
  if (h < 17) return `Good afternoon${who}. I am FRIDAY, your personal assistant. All systems are green. What are we doing today?`;
  return `Good evening${who}. I am FRIDAY, your personal assistant. Systems are online. What are we doing today?`;
}

// ================================================
// ORB CANVAS — Siri-style Neural Visualizer
// ================================================
let orbState = 'idle'; // idle | listening | thinking | speaking
let orbFrame = 0;
let orbAnalyserData = new Uint8Array(64).fill(128);

function startOrb() {
  const canvas = document.getElementById('orb-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;

  function draw() {
    orbFrame++;
    ctx.clearRect(0, 0, W, H);

    const t = orbFrame * 0.016;
    const isIdle = orbState === 'idle';
    const isListening = orbState === 'listening';
    const isThinking = orbState === 'thinking';
    const isSpeaking = orbState === 'speaking';

    // Core glow
    const coreRadius = isIdle ? 28 : (isListening ? 32 : (isSpeaking ? 36 : 30));
    const coreAlpha = isIdle ? 0.6 : 0.9;

    // Outer rings
    for (let ring = 0; ring < 3; ring++) {
      const r = 50 + ring * 22;
      const segments = 48;
      const speed = isListening ? 0.02 : (isThinking ? 0.015 : 0.008);
      const direction = ring % 2 === 0 ? 1 : -1;

      ctx.beginPath();
      for (let i = 0; i <= segments; i++) {
        const angle = (i / segments) * Math.PI * 2 + t * speed * direction;
        const dataIdx = Math.floor((i / segments) * orbAnalyserData.length) % orbAnalyserData.length;
        const amp = (orbAnalyserData[dataIdx] - 128) / 128;
        const wobble = isIdle ? Math.sin(t * 0.5 + ring) * 2 : amp * (isSpeaking ? 18 : 10);
        const px = cx + Math.cos(angle) * (r + wobble);
        const py = cy + Math.sin(angle) * (r + wobble);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();

      const alpha = isIdle ? 0.08 + ring * 0.03 : 0.15 + ring * 0.06;
      const color = isListening ? `rgba(0,229,255,${alpha})` :
                    isSpeaking ? `rgba(0,229,255,${alpha})` :
                    isThinking ? `rgba(255,0,106,${alpha})` :
                    `rgba(0,229,255,${alpha})`;
      ctx.strokeStyle = color;
      ctx.lineWidth = isIdle ? 0.8 : 1.5;
      ctx.stroke();
    }

    // Inner rotating arc
    const innerR = 38;
    const arcSpan = isListening ? Math.PI * 1.2 : (isSpeaking ? Math.PI * 0.8 : Math.PI * 0.5);
    ctx.beginPath();
    ctx.arc(cx, cy, innerR, t * 0.8, t * 0.8 + arcSpan);
    ctx.strokeStyle = isThinking ? 'rgba(255,0,106,0.3)' : 'rgba(0,229,255,0.3)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Core orb
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius);
    if (isListening) {
      grad.addColorStop(0, 'rgba(0,229,255,0.9)');
      grad.addColorStop(0.5, 'rgba(0,229,255,0.4)');
      grad.addColorStop(1, 'rgba(0,229,255,0)');
    } else if (isThinking) {
      grad.addColorStop(0, 'rgba(255,0,106,0.8)');
      grad.addColorStop(0.5, 'rgba(255,0,106,0.3)');
      grad.addColorStop(1, 'rgba(255,0,106,0)');
    } else if (isSpeaking) {
      const pulseR = coreRadius + Math.sin(t * 4) * 4;
      grad.addColorStop(0, 'rgba(0,229,255,1)');
      grad.addColorStop(0.4, 'rgba(0,229,255,0.5)');
      grad.addColorStop(1, 'rgba(0,229,255,0)');
      ctx.beginPath();
      ctx.arc(cx, cy, pulseR + 6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,229,255,0.06)';
      ctx.fill();
    } else {
      grad.addColorStop(0, `rgba(0,229,255,${coreAlpha})`);
      grad.addColorStop(0.5, `rgba(0,229,255,${coreAlpha * 0.4})`);
      grad.addColorStop(1, 'rgba(0,229,255,0)');
    }
    ctx.beginPath();
    ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    // Particles (when active)
    if (!isIdle) {
      const particleCount = isSpeaking ? 8 : 4;
      for (let i = 0; i < particleCount; i++) {
        const angle = (i / particleCount) * Math.PI * 2 + t * (isListening ? 2 : 1);
        const dist = 60 + Math.sin(t * 2 + i) * 15;
        const px = cx + Math.cos(angle) * dist;
        const py = cy + Math.sin(angle) * dist;
        ctx.beginPath();
        ctx.arc(px, py, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = isThinking ? 'rgba(255,0,106,0.5)' : 'rgba(0,229,255,0.5)';
        ctx.fill();
      }
    }

    requestAnimationFrame(draw);
  }

  draw();
}

function setOrbState(state) {
  orbState = state;
  const statusEl = document.getElementById('orb-status');
  const labelEl = document.getElementById('orb-label');
  if (statusEl) {
    statusEl.textContent = state.toUpperCase();
    statusEl.style.color = state === 'thinking' ? 'var(--pink)' : 'var(--cyan)';
  }
  if (labelEl) {
    const labels = {
      idle: 'Say something or type a command',
      listening: 'Listening...',
      thinking: 'Processing...',
      speaking: 'Speaking...'
    };
    labelEl.textContent = labels[state] || '';
  }
}

// ================================================
// CLOCK
// ================================================
function startClock() {
  const el = document.getElementById('clock');
  function tick() {
    el.textContent = new Date().toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  tick();
  setInterval(tick, 1000);
}

// ================================================
// QUOTA COUNTER
// ================================================
async function fetchQuota() {
  try {
    const res = await fetch('/api/gemini-quota');
    const d = await res.json();
    if (!d.success) return;
    const badge = document.getElementById('mode-badge');
    const rpmEl = document.getElementById('quota-rpm');
    const dot = document.getElementById('status-dot');

    if (d.isKeyPresent) {
      badge.textContent = d.model.toUpperCase();
      badge.classList.add('active');
      if (rpmEl) rpmEl.textContent = `${d.rpm.current}/${d.rpm.max}`;
      if (dot) dot.style.background = 'var(--cyan)';
    } else {
      badge.textContent = 'OFFLINE';
      badge.classList.remove('active');
      if (rpmEl) rpmEl.textContent = '--/--';
      if (dot) dot.style.background = 'var(--pink)';
    }
  } catch {}
}

// ================================================
// MOUSE GLOW
// ================================================
(function initGlow() {
  const glow = document.getElementById('mouse-glow');
  if (!glow) return;
  let mx = 0, my = 0, gx = 0, gy = 0;
  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
  (function anim() {
    gx += (mx - gx) * 0.07;
    gy += (my - gy) * 0.07;
    glow.style.left = gx + 'px';
    glow.style.top = gy + 'px';
    requestAnimationFrame(anim);
  })();
})();

// ================================================
// TOASTS
// ================================================
function toast(msg, type = 'ok') {
  const c = document.getElementById('toasts');
  const icons = { ok: 'fa-circle-check', err: 'fa-circle-xmark', info: 'fa-circle-info' };
  const t = document.createElement('div');
  t.className = `toast t-${type}`;
  t.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, 3000);
}

// ================================================
// CHAT SYSTEM
// ================================================
function addUserMessage(text) {
  const msgs = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg msg-user';
  d.innerHTML = `<div class="msg-bubble">${escHtml(text)}</div>`;
  msgs.appendChild(d);
  scrollChat();
}

function addAIMessage(text) {
  const msgs = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg msg-ai';
  d.innerHTML = `<div class="msg-label">F.R.I.D.A.Y.</div><div class="msg-bubble">${formatAI(text)}</div>`;
  msgs.appendChild(d);
  scrollChat();
  return d;
}

function addTyping() {
  const msgs = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg msg-ai msg-typing';
  d.id = 'typing-indicator';
  d.innerHTML = `<div class="msg-label">F.R.I.D.A.Y.</div><div class="msg-bubble"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
  msgs.appendChild(d);
  scrollChat();
  return d;
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function scrollChat() {
  const area = document.getElementById('chat-area');
  setTimeout(() => area.scrollTop = area.scrollHeight, 50);
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function formatAI(text) {
  return escHtml(text).replace(/\n/g, '<br>');
}

// ================================================
// OFFLINE MEMORY
// ================================================
function loadOfflineMemory() {
  try { return JSON.parse(localStorage.getItem('friday_memory') || '{}'); } catch { return {}; }
}
function saveOfflineMemory(mem) {
  localStorage.setItem('friday_memory', JSON.stringify(mem));
}

// ================================================
// COMMAND PARSING (client-side)
// ================================================
function parseCommand(text) {
  const t = text.toLowerCase().trim();

  const summonMatch = t.match(/^(?:summon|open|show|launch|display)\s+(.+)$/i);
  if (summonMatch) {
    const panel = summonMatch[1].trim();
    const panelMap = {
      'system': 'system', 'system info': 'system', 'sysinfo': 'system',
      'weather': 'weather', 'forecast': 'weather',
      'processes': 'processes', 'process': 'processes', 'procs': 'processes', 'task manager': 'processes',
      'vault': 'vault', 'memory': 'vault', 'memories': 'vault', 'save': 'vault',
      'clipboard': 'clipboard', 'clip': 'clipboard', 'copy': 'clipboard',
      'settings': 'settings', 'config': 'settings', 'preferences': 'settings',
      'commands': 'commands', 'cmds': 'commands', 'help': 'commands',
      'activity': 'activity', 'monitor': 'activity', 'pc activity': 'activity',
      'emails': 'emails', 'email': 'emails', 'mail': 'emails', 'inbox': 'emails'
    };
    const matched = panelMap[panel] || panel;
    openPanel(matched);
    return { handled: true, response: `Opening ${matched} panel.` };
  }

  const closeMatch = t.match(/^(?:close|dismiss|hide|shut)\s+(.+)$/i);
  if (closeMatch) {
    const panel = closeMatch[1].trim();
    closePanel(panel);
    return { handled: true, response: `Closing ${panel} panel.` };
  }

  if (/^(?:close all|dismiss all|hide all)$/i.test(t)) {
    document.querySelectorAll('.panel').forEach(p => closePanel(p.dataset.panel));
    return { handled: true, response: 'All panels closed.' };
  }

  return null;
}

// ================================================
// PANEL SYSTEM
// ================================================
const openPanels = new Set();

function openPanel(name) {
  if (openPanels.has(name)) {
    toast(`${name} panel already open`, 'info');
    return;
  }

  const container = document.getElementById('panels');
  container.querySelectorAll('.panel').forEach(p => {
    closePanel(p.dataset.panel);
  });

  const panel = document.createElement('div');
  panel.className = 'panel';
  panel.dataset.panel = name;

  const titles = {
    'activity': 'fa-chart-line PC ACTIVITY',
    'system': 'fa-microchip SYSTEM INFO',
    'weather': 'fa-cloud-sun WEATHER',
    'emails': 'fa-envelope EMAILS',
    'processes': 'fa-list-ol PROCESS MANAGER',
    'vault': 'fa-database MEMORY VAULT',
    'clipboard': 'fa-clipboard CLIPBOARD',
    'settings': 'fa-gear CONFIGURATION',
    'commands': 'fa-terminal COMMANDS'
  };

  const titleStr = titles[name] || `fa-circle ${name.toUpperCase()}`;
  const iconClass = titleStr.split(' ')[0];
  const titleText = titleStr.split(' ').slice(1).join(' ');

  panel.innerHTML = `
    <div class="panel-hdr">
      <h3><i class="fa-solid ${iconClass}"></i> ${titleText}</h3>
      <button class="panel-close" onclick="closePanel('${name}')">&times;</button>
    </div>
    <div class="panel-body" id="panel-body-${name}">
      <div class="panel-empty">Loading...</div>
    </div>
  `;

  container.appendChild(panel);
  openPanels.add(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.add('active');
  loadPanelContent(name);
  sfx.confirm();
  toast(`${name} panel opened`, 'ok');
}

function closePanel(name) {
  const panel = document.querySelector(`.panel[data-panel="${name}"]`);
  if (!panel) return;
  panel.classList.add('closing');
  setTimeout(() => panel.remove(), 250);
  openPanels.delete(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.remove('active');
  sfx.click();
}

async function loadPanelContent(name) {
  const body = document.getElementById(`panel-body-${name}`);
  if (!body) return;

  switch (name) {
    case 'activity': return loadActivityPanel(body);
    case 'system': return loadSystemPanel(body);
    case 'weather': return loadWeatherPanel(body);
    case 'emails': return loadEmailPanel(body);
    case 'processes': return loadProcessPanel(body);
    case 'vault': return loadVaultPanel(body);
    case 'clipboard': return loadClipboardPanel(body);
    case 'settings': return loadSettingsPanel(body);
    case 'commands': return loadCommandsPanel(body);
  }
}

// ================================================
// PANEL LOADERS
// ================================================

// --- Activity Panel (CPU, RAM, active apps, gauges) ---
async function loadActivityPanel(el) {
  el.innerHTML = '<div class="panel-empty">Scanning system...</div>';
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Failed to load activity.</div>'; return; }

    const cpuPct = d.cpu?.usage || 0;
    const ramPct = d.ram?.usage || 0;
    const batPct = d.battery?.level ?? '--';
    const batChg = d.battery?.charging;
    const diskPct = d.disk?.usage || 0;
    const diskFree = d.disk?.free || '--';
    const uptimeH = d.uptime ? Math.floor(d.uptime / 3600) : 0;
    const uptimeM = d.uptime ? Math.floor((d.uptime % 3600) / 60) : 0;

    el.innerHTML = `
      <div class="panel-stat-grid">
        <div class="panel-stat-box">
          <div class="stat-num">${cpuPct}%</div>
          <div class="stat-lbl">CPU</div>
          <div class="gauge"><div class="gauge-fill g-cyan" style="width:${cpuPct}%"></div></div>
        </div>
        <div class="panel-stat-box">
          <div class="stat-num">${ramPct}%</div>
          <div class="stat-lbl">RAM</div>
          <div class="gauge"><div class="gauge-fill g-pink" style="width:${ramPct}%"></div></div>
        </div>
        <div class="panel-stat-box">
          <div class="stat-num">${batPct}${typeof batPct === 'number' ? '%' : ''}</div>
          <div class="stat-lbl">${batChg ? 'CHARGING' : 'BATTERY'}</div>
          <div class="gauge"><div class="gauge-fill g-gold" style="width:${typeof batPct === 'number' ? batPct : 0}%"></div></div>
        </div>
        <div class="panel-stat-box">
          <div class="stat-num">${diskPct}%</div>
          <div class="stat-lbl">DISK ${diskFree}</div>
          <div class="gauge"><div class="gauge-fill g-cyan" style="width:${diskPct}%"></div></div>
        </div>
      </div>
      <div class="panel-row"><span class="lbl">UPTIME</span><span class="val">${uptimeH}h ${uptimeM}m</span></div>
      <div class="panel-row"><span class="lbl">HOSTNAME</span><span class="val">${d.hostname || '---'}</span></div>
      <div class="panel-row"><span class="lbl">PLATFORM</span><span class="val">${d.platform || '---'}</span></div>
      <div class="panel-row"><span class="lbl">RAM USED</span><span class="val">${d.ram?.usedMB || 0} / ${d.ram?.totalMB || 0} MB</span></div>
      <div class="panel-row"><span class="lbl">CPU CORES</span><span class="val">${d.cpu?.cores || '--'}</span></div>
      <div class="panel-row"><span class="lbl">CPU MODEL</span><span class="val" style="font-size:10px">${d.cpu?.model || '---'}</span></div>
    `;
  } catch {
    el.innerHTML = '<div class="panel-empty">Error loading activity data.</div>';
  }
}

// --- System Panel ---
async function loadSystemPanel(el) {
  try {
    const res = await fetch('/api/control', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'system-info' })
    });
    const data = await res.json();
    if (!data.success) { el.innerHTML = '<div class="panel-empty">Failed to load system info.</div>'; return; }
    const i = data.info || {};
    el.innerHTML = `
      <div class="panel-row"><span class="lbl">MODEL</span><span class="val">${i.model_name || '---'}</span></div>
      <div class="panel-row"><span class="lbl">IDENTIFIER</span><span class="val">${i.model_identifier || '---'}</span></div>
      <div class="panel-row"><span class="lbl">PROCESSOR</span><span class="val">${i.processor_name || '---'}</span></div>
      <div class="panel-row"><span class="lbl">SPEED</span><span class="val">${i.processor_speed || '---'}</span></div>
      <div class="panel-row"><span class="lbl">MEMORY</span><span class="val">${i.memory || '---'}</span></div>
      <div class="panel-row"><span class="lbl">SERIAL</span><span class="val">${i.serial_number || '---'}</span></div>
      <div class="panel-row"><span class="lbl">OS</span><span class="val">${i.productname || 'macOS'} ${i.productversion || ''}</span></div>
      <div class="panel-row"><span class="lbl">BUILD</span><span class="val">${i.buildversion || '---'}</span></div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error loading system info.</div>'; }
}

// --- Weather Panel ---
async function loadWeatherPanel(el) {
  try {
    const res = await fetch('/api/weather');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Weather data unavailable.</div>'; return; }
    el.innerHTML = `
      <div class="panel-row"><span class="lbl">CITY</span><span class="val">${d.city}</span></div>
      <div class="panel-row"><span class="lbl">TEMPERATURE</span><span class="val">${d.tempC}\u00B0C</span></div>
      <div class="panel-row"><span class="lbl">CONDITION</span><span class="val">${d.condition}</span></div>
      <div class="panel-row"><span class="lbl">HUMIDITY</span><span class="val">${d.humidity}%</span></div>
      <div class="panel-row"><span class="lbl">WIND</span><span class="val">${d.windKmH} km/h</span></div>
      <div class="panel-row"><span class="lbl">DAYLIGHT</span><span class="val">${d.isDay ? 'Yes' : 'No'}</span></div>
      ${d.forecast ? d.forecast.map(f => `
        <div class="panel-row"><span class="lbl">${f.day}</span><span class="val">${f.min}\u00B0 / ${f.max}\u00B0</span></div>
      `).join('') : ''}
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error loading weather.</div>'; }
}

// --- Emails Panel (Mail.app) ---
async function loadEmailPanel(el) {
  el.innerHTML = '<div class="panel-empty">Fetching emails from Mail.app...</div>';
  try {
    const res = await fetch('/api/emails');
    const d = await res.json();
    if (!d.success || !d.emails?.length) {
      el.innerHTML = `<div class="panel-empty">${d.message || 'No emails found. Make sure Mail.app is configured.'}</div>`;
      return;
    }
    el.innerHTML = d.emails.map(e => `
      <div class="email-item">
        <div class="email-from">${escHtml(e.from || 'Unknown')}</div>
        <div class="email-subject">${escHtml(e.subject || '(no subject)')}</div>
        <div class="email-date">${escHtml(e.date || '')}</div>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div class="panel-empty">Error reading emails. Mail.app may need Full Disk Access.</div>';
  }
}

// --- Processes Panel ---
async function loadProcessPanel(el) {
  el.innerHTML = '<div class="panel-empty">Loading processes...</div>';
  try {
    const res = await fetch('/api/control', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'processes' })
    });
    const d = await res.json();
    if (!d.success || !d.processes?.length) { el.innerHTML = '<div class="panel-empty">No processes found.</div>'; return; }
    el.innerHTML = d.processes.map(p => `
      <div class="proc-item">
        <span class="pcpu">${p.cpu}%</span>
        <span style="color:var(--txt2)">${p.pid}</span>
        <span class="pcmd">${escHtml(p.command)}</span>
        <button class="pk" onclick="killProc('${p.pid}')" title="Kill"><i class="fa-solid fa-xmark"></i></button>
      </div>
    `).join('');
  } catch { el.innerHTML = '<div class="panel-empty">Error loading processes.</div>'; }
}

async function killProc(pid) {
  await fetch('/api/control', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'kill-process', value: pid })
  });
  toast(`Process ${pid} terminated`, 'ok');
  const body = document.getElementById('panel-body-processes');
  if (body) loadProcessPanel(body);
}

// --- Vault Panel ---
async function loadVaultPanel(el) {
  try {
    const res = await fetch('/api/vault');
    const d = await res.json();
    const items = d.data || [];
    el.innerHTML = items.length
      ? items.map(v => `
        <div class="vault-item">
          <span class="vt">${escHtml(v.text)}</span>
          <span class="vd">${v.date || ''}</span>
          <button class="vx" onclick="deleteVault('${v.id}')"><i class="fa-solid fa-xmark"></i></button>
        </div>
      `).join('')
      : '<div class="panel-empty">No memories saved yet.</div>';
    el.innerHTML += `
      <div class="panel-input">
        <input type="text" id="vault-input" placeholder="Save a memory..." onkeydown="if(event.key==='Enter')addVault()">
        <button onclick="addVault()"><i class="fa-solid fa-plus"></i></button>
      </div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error loading vault.</div>'; }
}

async function addVault() {
  const input = document.getElementById('vault-input');
  if (!input || !input.value.trim()) return;
  await fetch('/api/vault', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: input.value.trim() })
  });
  toast('Memory saved', 'ok');
  input.value = '';
  loadVaultPanel(document.getElementById('panel-body-vault'));
}

async function deleteVault(id) {
  await fetch(`/api/vault?id=${id}`, { method: 'DELETE' });
  toast('Memory deleted', 'ok');
  loadVaultPanel(document.getElementById('panel-body-vault'));
}

// --- Clipboard Panel ---
async function loadClipboardPanel(el) {
  try {
    const res = await fetch('/api/control', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'clipboard-read' })
    });
    const d = await res.json();
    el.innerHTML = `
      <div class="panel-row"><span class="lbl">CLIPBOARD</span></div>
      <div style="margin-top:8px;padding:10px;background:rgba(255,255,255,0.025);border:1px solid var(--border);border-radius:8px;font-family:var(--mono);font-size:11px;color:var(--txt);max-height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;">${escHtml(d.content || '(empty)')}</div>
      <div class="panel-input" style="margin-top:10px;">
        <input type="text" id="clip-input" placeholder="Write to clipboard..." onkeydown="if(event.key==='Enter')writeClip()">
        <button onclick="writeClip()"><i class="fa-solid fa-copy"></i></button>
      </div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error reading clipboard.</div>'; }
}

async function writeClip() {
  const input = document.getElementById('clip-input');
  if (!input || !input.value.trim()) return;
  try { await navigator.clipboard.writeText(input.value.trim()); } catch {}
  await fetch('/api/control', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'clipboard-write', value: input.value.trim() })
  });
  toast('Text copied to clipboard', 'ok');
  input.value = '';
  loadClipboardPanel(document.getElementById('panel-body-clipboard'));
}

// --- Settings Panel ---
function loadSettingsPanel(el) {
  const mem = loadOfflineMemory();
  el.innerHTML = `
    <div class="setting-row">
      <label>VOICE</label>
      <select id="voice-select" style="width:140px">
        <option value="21m00Tcm4TlvDq8ikWAM">Rachel (Default)</option>
        <option value="EXAVITQu4vr4xnSDxMaL">Bella</option>
        <option value="MF3mGyEYCl7XYWbV9V6O">Elli</option>
        <option value="pFZP5JQG7iQjIQuC4Bku">Lily</option>
      </select>
    </div>
    <div class="setting-row">
      <label>SPEECH RATE</label>
      <input type="range" id="speech-rate" min="0.5" max="2" step="0.1" value="1.0" style="width:120px">
    </div>
    <div class="setting-row">
      <label>SPEECH PITCH</label>
      <input type="range" id="speech-pitch" min="0.5" max="2" step="0.1" value="1.0" style="width:120px">
    </div>
    <div class="setting-row">
      <label>CONTINUOUS LISTEN</label>
      <input type="checkbox" id="cont-listen" ${mem.continuousListen ? 'checked' : ''}>
    </div>
    <div class="setting-row">
      <label>YOUR NAME</label>
      <input type="text" id="name-input" value="${mem.name || ''}" placeholder="Tell me your name" style="width:140px;background:rgba(255,255,255,0.025);border:1px solid var(--border);color:var(--txt);border-radius:6px;padding:4px 8px;font-family:var(--mono);font-size:11px;">
    </div>
  `;

  document.getElementById('voice-select').addEventListener('change', (e) => {
    mem.voiceId = e.target.value;
    saveOfflineMemory(mem);
    toast('Voice updated', 'ok');
  });
  document.getElementById('speech-rate').addEventListener('input', (e) => {
    mem.speechRate = parseFloat(e.target.value);
    saveOfflineMemory(mem);
  });
  document.getElementById('speech-pitch').addEventListener('input', (e) => {
    mem.speechPitch = parseFloat(e.target.value);
    saveOfflineMemory(mem);
  });
  document.getElementById('cont-listen').addEventListener('change', (e) => {
    mem.continuousListen = e.target.checked;
    saveOfflineMemory(mem);
  });
  document.getElementById('name-input').addEventListener('change', (e) => {
    mem.name = e.target.value.trim();
    saveOfflineMemory(mem);
    toast(`Name set to ${mem.name}`, 'ok');
  });

  if (mem.voiceId) document.getElementById('voice-select').value = mem.voiceId;
  if (mem.speechRate) document.getElementById('speech-rate').value = mem.speechRate;
  if (mem.speechPitch) document.getElementById('speech-pitch').value = mem.speechPitch;
}

// --- Commands Panel ---
function loadCommandsPanel(el) {
  el.innerHTML = `
    <div class="cmd-ref-item"><div class="cc">summon activity / system / weather / emails / processes / vault / clipboard / settings / commands</div><div class="cd">Open a panel</div></div>
    <div class="cmd-ref-item"><div class="cc">close [panel] / close all</div><div class="cd">Dismiss panels</div></div>
    <div class="cmd-ref-item"><div class="cc">lock pc / sleep pc / screenshot</div><div class="cd">System controls</div></div>
    <div class="cmd-ref-item"><div class="cc">volume [0-100] / mute / unmute</div><div class="cd">Audio controls</div></div>
    <div class="cmd-ref-item"><div class="cc">brightness [0-100]</div><div class="cd">Display brightness</div></div>
    <div class="cmd-ref-item"><div class="cc">open [app name]</div><div class="cd">Launch macOS app</div></div>
    <div class="cmd-ref-item"><div class="cc">play / pause / next / previous</div><div class="cd">Media controls</div></div>
    <div class="cmd-ref-item"><div class="cc">shutdown / restart</div><div class="cd">Power controls</div></div>
    <div class="cmd-ref-item"><div class="cc">screenshot</div><div class="cd">Capture screen</div></div>
    <div class="cmd-ref-item"><div class="cc">remember [fact]</div><div class="cd">Save to vault</div></div>
    <div class="cmd-ref-item"><div class="cc">what time is it / what's the date</div><div class="cd">Time & date</div></div>
    <div class="cmd-ref-item"><div class="cc">check emails / read mail</div><div class="cd">Read emails from Mail.app</div></div>
    <div class="cmd-ref-item"><div class="cc">weather / what's the weather</div><div class="cd">Get weather info</div></div>
    <div class="cmd-ref-item"><div class="cc">tell me about [topic]</div><div class="cd">Ask anything</div></div>
  `;
}

// ================================================
// TEXT INPUT
// ================================================
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && chatInput.value.trim()) {
    sendMessage(chatInput.value.trim());
    chatInput.value = '';
  }
});
sendBtn.addEventListener('click', () => {
  if (chatInput.value.trim()) {
    sendMessage(chatInput.value.trim());
    chatInput.value = '';
  }
});

// ================================================
// SEND MESSAGE
// ================================================
async function sendMessage(text) {
  addUserMessage(text);
  sfx.click();

  const cmd = parseCommand(text);
  if (cmd) {
    setTimeout(() => addAIMessage(cmd.response), 300);
    speak(cmd.response);
    return;
  }

  const typing = addTyping();
  setOrbState('thinking');

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    removeTyping();

    if (data.success && data.reply) {
      addAIMessage(data.reply.text);

      if (data.reply.command?.action === 'vault-save') {
        await fetch('/api/vault', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: data.reply.command.value?.text || '' })
        });
        toast('Saved to vault', 'ok');
      }

      if (data.reply.command && data.reply.command.action !== 'vault-save') {
        await fetch('/api/control', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data.reply.command)
        });
      }

      speak(data.reply.speech || data.reply.text);
    } else {
      addAIMessage('Something went wrong, BOSS. Please try again.');
      setOrbState('idle');
    }
  } catch (e) {
    removeTyping();
    addAIMessage('Connection error. Please try again, BOSS.');
    setOrbState('idle');
  }
}

// ================================================
// VOICE — TTS
// ================================================
function speak(text) {
  if (!text) return;
  const mem = loadOfflineMemory();
  setOrbState('speaking');

  fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: text,
      voiceId: mem.voiceId || '21m00Tcm4TlvDq8ikWAM'
    })
  }).then(async (res) => {
    const data = await res.json().catch(() => null);
    if (data && data.fallback) {
      speakWeb(text);
    } else {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.playbackRate = mem.speechRate || 1.0;
      audio.onended = () => setOrbState('idle');
      audio.play().catch(() => speakWeb(text));
    }
  }).catch(() => speakWeb(text));
}

function speakWeb(text) {
  if (!('speechSynthesis' in window)) { setOrbState('idle'); return; }
  const mem = loadOfflineMemory();
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = mem.speechRate || 1.0;
  u.pitch = mem.speechPitch || 1.0;
  const voices = window.speechSynthesis.getVoices();
  const female = voices.find(v => /female|samantha|karen|moira|tessa/i.test(v.name)) || voices[0];
  if (female) u.voice = female;
  u.onend = () => setOrbState('idle');
  window.speechSynthesis.speak(u);
}

// ================================================
// SPEECH RECOGNITION (Mic)
// ================================================
let recognition = null;
let isListening = false;
const micBtn = document.getElementById('mic-btn');

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.continuous = false;
  r.interimResults = false;
  r.lang = 'en-US';
  r.onresult = (e) => {
    const text = e.results[0][0].transcript;
    sendMessage(text);
    stopListening();
  };
  r.onerror = () => stopListening();
  r.onend = () => stopListening();
  return r;
}

micBtn.addEventListener('click', () => {
  if (isListening) stopListening();
  else startListening();
});

function startListening() {
  if (!recognition) recognition = initRecognition();
  if (!recognition) { toast('Speech recognition not supported', 'err'); return; }
  isListening = true;
  micBtn.classList.add('active');
  setOrbState('listening');
  sfx.confirm();
  try { recognition.start(); } catch {}
}

function stopListening() {
  isListening = false;
  micBtn.classList.remove('active');
  if (orbState === 'listening') setOrbState('idle');
  try { recognition?.stop(); } catch {}
}

if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

// ================================================
// DOCK BUTTONS
// ================================================
document.getElementById('dock').addEventListener('click', (e) => {
  const btn = e.target.closest('.dock-btn');
  if (!btn) return;
  const panel = btn.dataset.panel;
  if (openPanels.has(panel)) closePanel(panel);
  else openPanel(panel);
});

// ================================================
// INIT
// ================================================
document.addEventListener('DOMContentLoaded', runBoot);
