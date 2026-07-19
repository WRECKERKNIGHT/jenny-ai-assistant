// ================================================
// F.R.I.D.A.Y. — Core Application v4.0
// Split-Screen Holographic Layout
// ================================================

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx;
function getCtx() { if (!audioCtx) audioCtx = new AudioCtx(); return audioCtx; }

function playTone(freq, dur, type = 'sine', vol = 0.06) {
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
  click: () => playTone(1200, 0.05, 'sine', 0.04),
  hover: () => playTone(800, 0.03, 'triangle', 0.02),
  confirm: () => { playTone(600, 0.08, 'sine', 0.04); setTimeout(() => playTone(900, 0.12, 'sine', 0.04), 70); },
  error: () => { playTone(200, 0.12, 'sawtooth', 0.04); setTimeout(() => playTone(150, 0.15, 'sawtooth', 0.04), 80); },
  boot: () => {
    [261.63, 329.63, 392, 523.25].forEach((f, i) => {
      setTimeout(() => playTone(f, 0.35, 'sine', 0.04), i * 100);
    });
  },
  timer: () => {
    [880, 1100, 880].forEach((f, i) => {
      setTimeout(() => playTone(f, 0.2, 'sine', 0.06), i * 200);
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
    await sleep(70);
  }
  await sleep(250);
  subEl.classList.add('show');

  for (let i = 0; i < bootLines.length; i++) {
    barEl.style.width = Math.round(((i + 1) / bootLines.length) * 100) + '%';
    logsEl.textContent = bootLines[i];
    sfx.hover();
    await sleep(350 + Math.random() * 250);
  }

  sfx.boot();
  await sleep(500);

  document.getElementById('boot-screen').classList.add('done');
  const app = document.getElementById('main-app');
  app.style.display = 'flex';

  await sleep(100);
  const greeting = getGreeting();
  addAIMessage(greeting);
  startClock();
  startOrb();
  initSpeechWaves();
  startHoloShimmer();
  startSysMonitor();
  fetchQuota();
  setInterval(fetchQuota, 60000);
  setInterval(updateTimerDisplay, 1000);

  // Speak the greeting + intro
  await sleep(600);
  speak(greeting);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function getGreeting() {
  const h = new Date().getHours();
  const name = loadOfflineMemory().name;
  const who = name ? ` ${name}` : '';
  if (h < 12) return `Good morning${who}. I am FRIDAY, your personal assistant. All systems are operational. What are we doing today, BOSS?`;
  if (h < 17) return `Good afternoon${who}. I am FRIDAY, your personal assistant. All systems are green. What are we doing today, BOSS?`;
  return `Good evening${who}. I am FRIDAY, your personal assistant. Systems are online. What are we doing today, BOSS?`;
}

// ================================================
// HOLOGRAPHIC SHIMMER — RGB split on orb
// ================================================
function startHoloShimmer() {
  const glow = document.querySelector('.orb-rgb-glow');
  if (!glow) return;
  const r = glow.querySelector('.rgb-r');
  const g = glow.querySelector('.rgb-g');
  const b = glow.querySelector('.rgb-b');
  let t = 0;
  function animate() {
    t += 0.015;
    r.style.transform = `translate(${Math.sin(t*1.1)*6}px, ${Math.cos(t*0.9)*4}px)`;
    g.style.transform = `translate(${Math.sin(t*0.7+2)*5}px, ${-Math.cos(t*0.9)*4}px)`;
    b.style.transform = `translate(${-Math.sin(t*1.1)*6}px, ${Math.cos(t*1.3+1)*5}px)`;
    requestAnimationFrame(animate);
  }
  animate();
}

// ================================================
// SYSTEM MONITOR — Live Sparklines
// ================================================
const sparkHistory = { cpu: [], ram: [], disk: [], net: [] };
const SPARK_MAX = 40;
let lastNetBytes = 0;

function pushSpark(key, val) {
  sparkHistory[key].push(val);
  if (sparkHistory[key].length > SPARK_MAX) sparkHistory[key].shift();
}

function drawSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (data.length < 2) return;

  const step = W / (SPARK_MAX - 1);

  // Fill
  ctx.beginPath();
  ctx.moveTo(0, H);
  data.forEach((v, i) => {
    const x = i * step;
    const y = H - (v / 100) * (H - 4);
    if (i === 0) ctx.lineTo(x, y);
    else {
      const px = (i - 1) * step;
      const py = H - (data[i-1] / 100) * (H - 4);
      const cpx1 = px + step * 0.4;
      const cpx2 = x - step * 0.4;
      ctx.bezierCurveTo(cpx1, py, cpx2, y, x, y);
    }
  });
  ctx.lineTo(W, H);
  ctx.closePath();
  const fillGrad = ctx.createLinearGradient(0, 0, 0, H);
  fillGrad.addColorStop(0, color.replace(')', ',0.15)').replace('rgb', 'rgba'));
  fillGrad.addColorStop(1, color.replace(')', ',0.0)').replace('rgb', 'rgba'));
  ctx.fillStyle = fillGrad;
  ctx.fill();

  // Line
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * step;
    const y = H - (v / 100) * (H - 4);
    if (i === 0) ctx.moveTo(x, y);
    else {
      const px = (i - 1) * step;
      const py = H - (data[i-1] / 100) * (H - 4);
      const cpx1 = px + step * 0.4;
      const cpx2 = x - step * 0.4;
      ctx.bezierCurveTo(cpx1, py, cpx2, y, x, y);
    }
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Dot at end
  const lastX = (data.length - 1) * step;
  const lastY = H - (data[data.length - 1] / 100) * (H - 4);
  ctx.beginPath();
  ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

async function fetchSysStats() {
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    if (!d.success) return;

    const cpu = d.cpu?.usage || 0;
    const ram = d.ram?.usage || 0;
    const disk = d.disk?.usage || 0;

    pushSpark('cpu', cpu);
    pushSpark('ram', ram);
    pushSpark('disk', disk);

    document.getElementById('sys-cpu-val').textContent = cpu + '%';
    document.getElementById('sys-ram-val').textContent = ram + '%';
    document.getElementById('sys-disk-val').textContent = disk + '%';

    const cpuModel = d.cpu?.model || '';
    const shortModel = cpuModel.replace(/\(R\)|Core\(TM\)|CPU/g, '').replace(/\s+/g, ' ').trim();
    document.getElementById('sys-cpu-model').textContent = shortModel;
    document.getElementById('sys-ram-info').textContent = `${d.ram?.usedMB || 0} / ${d.ram?.totalMB || 0} MB`;
    document.getElementById('sys-disk-info').textContent = `${d.disk?.free || '--'} free`;

    const uptimeH = d.uptime ? Math.floor(d.uptime / 3600) : 0;
    const uptimeM = d.uptime ? Math.floor((d.uptime % 3600) / 60) : 0;
    document.getElementById('sys-uptime').textContent = `${uptimeH}h ${uptimeM}m`;
    document.getElementById('sys-battery').textContent = d.battery?.level != null ? `${Math.round(d.battery.level * 100)}%` : '--';
    document.getElementById('sys-wifi').textContent = d.hostname ? d.hostname.split('.')[0] : '--';

    drawSparkline('spark-cpu', sparkHistory.cpu, 'rgb(255,255,255)');
    drawSparkline('spark-ram', sparkHistory.ram, 'rgb(255,255,255)');
    drawSparkline('spark-disk', sparkHistory.disk, 'rgb(255,255,255)');
  } catch {}
}

function startSysMonitor() {
  fetchSysStats();
  setInterval(fetchSysStats, 3000);
}

// ================================================
// ORB CANVAS — Holographic Neural Visualizer
// ================================================
let orbState = 'idle';
let orbFrame = 0;

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

    for (let ring = 0; ring < 4; ring++) {
      const r = 70 + ring * 28;
      const segments = 64;
      const speed = isListening ? 0.025 : (isThinking ? 0.018 : (isSpeaking ? 0.012 : 0.006));
      const dir = ring % 2 === 0 ? 1 : -1;
      ctx.beginPath();
      for (let i = 0; i <= segments; i++) {
        const angle = (i / segments) * Math.PI * 2 + t * speed * dir;
        const wobble = isIdle
          ? Math.sin(t * 0.4 + ring * 1.2) * 3
          : Math.sin(t * 2 + i * 0.3) * (isSpeaking ? 12 : 6);
        const px = cx + Math.cos(angle) * (r + wobble);
        const py = cy + Math.sin(angle) * (r + wobble);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.closePath();
      const alpha = isIdle ? 0.03 + ring * 0.01 : 0.06 + ring * 0.03;
      ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
      ctx.lineWidth = isIdle ? 0.5 : 1;
      ctx.stroke();
    }

    for (let a = 0; a < 3; a++) {
      const innerR = 42 + a * 8;
      const arcSpan = isListening ? Math.PI * 1.5 : (isSpeaking ? Math.PI : Math.PI * 0.6);
      const offset = t * (0.6 + a * 0.3) * (a % 2 === 0 ? 1 : -1);
      ctx.beginPath();
      ctx.arc(cx, cy, innerR, offset, offset + arcSpan);
      ctx.strokeStyle = `rgba(255,255,255,${isIdle ? 0.08 : 0.15})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    const coreR = isIdle ? 32 : (isListening ? 38 : (isSpeaking ? 42 : 35));
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
    if (isListening) {
      grad.addColorStop(0, 'rgba(255,255,255,0.7)');
      grad.addColorStop(0.5, 'rgba(255,255,255,0.2)');
      grad.addColorStop(1, 'rgba(255,255,255,0)');
    } else if (isThinking) {
      grad.addColorStop(0, 'rgba(200,200,220,0.6)');
      grad.addColorStop(0.5, 'rgba(200,200,220,0.15)');
      grad.addColorStop(1, 'rgba(200,200,220,0)');
    } else if (isSpeaking) {
      grad.addColorStop(0, 'rgba(255,255,255,0.8)');
      grad.addColorStop(0.4, 'rgba(255,255,255,0.3)');
      grad.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.beginPath();
      ctx.arc(cx, cy, coreR + Math.sin(t * 3.5) * 5 + 10, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.fill();
    } else {
      grad.addColorStop(0, 'rgba(255,255,255,0.5)');
      grad.addColorStop(0.5, 'rgba(255,255,255,0.15)');
      grad.addColorStop(1, 'rgba(255,255,255,0)');
    }
    ctx.beginPath();
    ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    if (!isIdle) {
      const count = isSpeaking ? 12 : 6;
      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 + t * (isListening ? 1.5 : 0.8);
        const dist = 80 + Math.sin(t * 1.5 + i) * 20;
        const px = cx + Math.cos(angle) * dist;
        const py = cy + Math.sin(angle) * dist;
        const size = 1 + Math.sin(t * 2 + i) * 0.5;
        ctx.beginPath();
        ctx.arc(px, py, size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${isSpeaking ? 0.4 : 0.2})`;
        ctx.fill();
      }
    }

    requestAnimationFrame(draw);
  }
  draw();
}

function setOrbState(state) {
  orbState = state;
  const statusEl = document.getElementById('holo-status');
  const labelEl = document.getElementById('holo-label');
  const clickZone = document.getElementById('orb-click');
  if (statusEl) {
    statusEl.textContent = state.toUpperCase();
    statusEl.className = 'holo-status' + (state === 'listening' ? ' listening' : state === 'speaking' ? ' speaking' : '');
  }
  if (labelEl) {
    const labels = { idle: 'Tap the orb or type a command', listening: 'Listening...', thinking: 'Processing...', speaking: 'Speaking...' };
    labelEl.textContent = labels[state] || '';
  }
  if (clickZone) clickZone.classList.toggle('active', state === 'listening');
}

// ================================================
// SPEECH DETECTOR WAVES
// ================================================
let speechWaveBars = [];
let speechAnalyser = null;
let speechAnimFrame = null;

function initSpeechWaves() {
  const container = document.getElementById('speech-waves');
  if (!container) return;
  speechWaveBars = container.querySelectorAll('.wave-bar');
}

function startSpeechWaves(stream) {
  try {
    const ctx = getCtx();
    speechAnalyser = ctx.createAnalyser();
    speechAnalyser.fftSize = 64;
    const source = ctx.createMediaStreamSource(stream);
    source.connect(speechAnalyser);
    const data = new Uint8Array(speechAnalyser.frequencyBinCount);
    const container = document.getElementById('speech-waves');
    if (container) container.classList.add('active');
    function animate() {
      speechAnalyser.getByteFrequencyData(data);
      speechWaveBars.forEach((bar, i) => {
        bar.style.height = Math.max(2, (data[i] || 0) / 255 * 28) + 'px';
      });
      speechAnimFrame = requestAnimationFrame(animate);
    }
    animate();
  } catch {}
}

function stopSpeechWaves() {
  if (speechAnimFrame) cancelAnimationFrame(speechAnimFrame);
  const container = document.getElementById('speech-waves');
  if (container) container.classList.remove('active');
  speechWaveBars.forEach(bar => bar.style.height = '2px');
}

// ================================================
// CLOCK
// ================================================
function startClock() {
  const el = document.getElementById('hdr-clock');
  if (!el) return;
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
      if (dot) dot.style.background = 'rgba(255,255,255,0.5)';
    } else {
      badge.textContent = 'OFFLINE';
      badge.classList.remove('active');
      if (rpmEl) rpmEl.textContent = '--/--';
      if (dot) dot.style.background = 'rgba(255,0,106,0.5)';
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
    gx += (mx - gx) * 0.06;
    gy += (my - gy) * 0.06;
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
// COMMAND PARSING
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
      'activity': 'activity', 'monitor': 'activity', 'pc activity': 'activity', 'system monitor': 'activity',
      'emails': 'emails', 'email': 'emails', 'mail': 'emails', 'inbox': 'emails'
    };
    const matched = panelMap[panel] || panel;
    openPanel(matched);
    return { handled: true, response: `Opening ${matched} panel, BOSS.` };
  }

  const closeMatch = t.match(/^(?:close|dismiss|hide|shut)\s+(.+)$/i);
  if (closeMatch) { closePanel(closeMatch[1].trim()); return { handled: true, response: `Panel closed, BOSS.` }; }

  if (/^(?:close all|dismiss all|hide all)$/i.test(t)) {
    document.querySelectorAll('.panel').forEach(p => closePanel(p.dataset.panel));
    return { handled: true, response: 'All panels closed, BOSS.' };
  }

  const timerMatch = t.match(/(?:set\s+)?(?:a\s+)?timer\s+(?:for\s+|in\s+)?(\d+)\s*(seconds?|minutes?|hours?|mins?|hrs?)/i)
    || t.match(/(?:alarm|remind me)\s+(?:in\s+)?(\d+)\s*(seconds?|minutes?|hours?|mins?|hrs?)/i);
  if (timerMatch) {
    const num = parseInt(timerMatch[1], 10);
    const unit = timerMatch[2].toLowerCase();
    let secs = num;
    if (unit.startsWith('min')) secs = num * 60;
    else if (unit.startsWith('hour') || unit.startsWith('hr')) secs = num * 3600;
    const label = secs >= 3600 ? `${num} hour${num > 1 ? 's' : ''}` : secs >= 60 ? `${num} min` : `${num} sec`;
    setFrontendTimer(secs, label);
    return { handled: true, response: `Timer set for ${label}, BOSS. I'll let you know when it's done.` };
  }

  if (/^(?:timer|alarm|set timer)\s*$/i.test(t)) { setFrontendTimer(60, '1 min'); return { handled: true, response: 'Setting a 1-minute timer, BOSS.' }; }
  if (/^(?:briefing|daily briefing|morning briefing|what'?s the status|give me a briefing)/i.test(t)) { return { handled: true, response: '__FETCH_BRIEFING__' }; }

  return null;
}

// ================================================
// FRONTEND TIMER
// ================================================
let frontendTimers = [];

function setFrontendTimer(seconds, label) {
  const id = Date.now();
  frontendTimers.push({ id, label, endTime: Date.now() + seconds * 1000, seconds });
  sfx.confirm();
  toast(`Timer "${label}" started — ${formatTimerDuration(seconds)}`, 'ok');
  setTimeout(() => {
    frontendTimers = frontendTimers.filter(t => t.id !== id);
    toast(`Timer "${label}" is done!`, 'ok');
    sfx.timer();
    speak(`Timer's up, BOSS. ${label} is done.`);
  }, seconds * 1000);
}

function formatTimerDuration(secs) {
  if (secs >= 3600) return `${Math.floor(secs/3600)}h ${Math.floor((secs%3600)/60)}m`;
  if (secs >= 60) return `${Math.floor(secs/60)}m ${secs%60}s`;
  return `${secs}s`;
}

function updateTimerDisplay() {
  const pill = document.getElementById('timer-pill');
  const display = document.getElementById('timer-display');
  if (!pill || !display) return;
  const now = Date.now();
  const active = frontendTimers.filter(t => t.endTime > now);
  if (active.length === 0) { pill.classList.add('hidden'); return; }
  pill.classList.remove('hidden');
  const remaining = Math.max(0, Math.ceil((active[0].endTime - now) / 1000));
  display.textContent = `${Math.floor(remaining/60)}:${(remaining%60).toString().padStart(2,'0')}`;
}

// ================================================
// PANEL SYSTEM — Draggable Liquid Glass
// ================================================
const openPanels = new Set();

function openPanel(name) {
  if (openPanels.has(name)) { toast(`${name} already open`, 'info'); return; }

  const container = document.getElementById('panels');

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
  const parts = titleStr.split(' ');
  const iconClass = parts[0];
  const titleText = parts.slice(1).join(' ');

  panel.innerHTML = `
    <div class="panel-hdr" data-drag="true">
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

  // Make draggable
  initDraggable(panel);
}

function closePanel(name) {
  const panel = document.querySelector(`.panel[data-panel="${name}"]`);
  if (!panel) return;
  panel.classList.add('closing');
  setTimeout(() => panel.remove(), 200);
  openPanels.delete(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.remove('active');
}

function initDraggable(panel) {
  const handle = panel.querySelector('.panel-hdr');
  if (!handle) return;

  let isDragging = false;
  let startX, startY, startLeft, startTop;

  handle.addEventListener('mousedown', (e) => {
    if (e.target.closest('.panel-close')) return;
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    const rect = panel.getBoundingClientRect();
    startLeft = rect.left;
    startTop = rect.top;
    panel.style.transition = 'none';
    panel.style.transform = 'none';
    panel.style.left = startLeft + 'px';
    panel.style.top = startTop + 'px';
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    panel.style.left = (startLeft + dx) + 'px';
    panel.style.top = (startTop + dy) + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (!isDragging) return;
    isDragging = false;
    panel.style.transition = '';
  });

  // Touch support
  handle.addEventListener('touchstart', (e) => {
    if (e.target.closest('.panel-close')) return;
    isDragging = true;
    const touch = e.touches[0];
    startX = touch.clientX;
    startY = touch.clientY;
    const rect = panel.getBoundingClientRect();
    startLeft = rect.left;
    startTop = rect.top;
    panel.style.transition = 'none';
    panel.style.transform = 'none';
    panel.style.left = startLeft + 'px';
    panel.style.top = startTop + 'px';
  }, { passive: true });

  document.addEventListener('touchmove', (e) => {
    if (!isDragging) return;
    const touch = e.touches[0];
    panel.style.left = (startLeft + touch.clientX - startX) + 'px';
    panel.style.top = (startTop + touch.clientY - startY) + 'px';
  }, { passive: true });

  document.addEventListener('touchend', () => {
    if (!isDragging) return;
    isDragging = false;
    panel.style.transition = '';
  });
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

function makeCircularGauge(pct, label) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return `
    <div class="circular-gauge">
      <svg viewBox="0 0 52 52">
        <circle class="track" cx="26" cy="26" r="${r}"/>
        <circle class="fill" cx="26" cy="26" r="${r}"
          stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/>
      </svg>
      <div class="gauge-label">${pct}%</div>
    </div>
    <div class="stat-lbl">${label}</div>
  `;
}

async function loadActivityPanel(el) {
  el.innerHTML = '<div class="panel-empty">Scanning...</div>';
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Failed to load.</div>'; return; }
    const cpu = d.cpu?.usage || 0, ram = d.ram?.usage || 0, disk = d.disk?.usage || 0;
    const bat = d.battery?.level ?? 0;
    const uptimeH = d.uptime ? Math.floor(d.uptime / 3600) : 0;
    const uptimeM = d.uptime ? Math.floor((d.uptime % 3600) / 60) : 0;
    el.innerHTML = `
      <div class="panel-stat-grid">
        <div class="panel-stat-box">${makeCircularGauge(cpu, 'CPU')}</div>
        <div class="panel-stat-box">${makeCircularGauge(ram, 'RAM')}</div>
        <div class="panel-stat-box">${makeCircularGauge(disk, 'DISK')}</div>
        <div class="panel-stat-box">${makeCircularGauge(Math.round(bat*100), 'BATTERY')}</div>
      </div>
      <div class="panel-row"><span class="lbl">UPTIME</span><span class="val">${uptimeH}h ${uptimeM}m</span></div>
      <div class="panel-row"><span class="lbl">HOST</span><span class="val">${d.hostname || '---'}</span></div>
      <div class="panel-row"><span class="lbl">RAM</span><span class="val">${d.ram?.usedMB || 0} / ${d.ram?.totalMB || 0} MB</span></div>
      <div class="panel-row"><span class="lbl">DISK FREE</span><span class="val">${d.disk?.free || '--'}</span></div>
      <div class="panel-row"><span class="lbl">CPU</span><span class="val" style="font-size:8px">${d.cpu?.model || '---'}</span></div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadSystemPanel(el) {
  try {
    const res = await fetch('/api/control', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'system-info' })
    });
    const data = await res.json();
    if (!data.success) { el.innerHTML = '<div class="panel-empty">Failed.</div>'; return; }
    const i = data.info || {};
    el.innerHTML = `
      <div class="panel-row"><span class="lbl">MODEL</span><span class="val">${i.model_name || '---'}</span></div>
      <div class="panel-row"><span class="lbl">ID</span><span class="val">${i.model_identifier || '---'}</span></div>
      <div class="panel-row"><span class="lbl">CPU</span><span class="val">${i.processor_name || '---'}</span></div>
      <div class="panel-row"><span class="lbl">SPEED</span><span class="val">${i.processor_speed || '---'}</span></div>
      <div class="panel-row"><span class="lbl">RAM</span><span class="val">${i.memory || '---'}</span></div>
      <div class="panel-row"><span class="lbl">SERIAL</span><span class="val">${i.serial_number || '---'}</span></div>
      <div class="panel-row"><span class="lbl">OS</span><span class="val">${i.productname || 'macOS'} ${i.productversion || ''}</span></div>
      <div class="panel-row"><span class="lbl">BUILD</span><span class="val">${i.buildversion || '---'}</span></div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadWeatherPanel(el) {
  try {
    const res = await fetch('/api/weather');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Unavailable.</div>'; return; }
    el.innerHTML = `
      <div class="panel-row"><span class="lbl">CITY</span><span class="val">${d.city}</span></div>
      <div class="panel-row"><span class="lbl">TEMP</span><span class="val">${d.tempC}\u00B0C</span></div>
      <div class="panel-row"><span class="lbl">CONDITION</span><span class="val">${d.condition}</span></div>
      <div class="panel-row"><span class="lbl">HUMIDITY</span><span class="val">${d.humidity}%</span></div>
      <div class="panel-row"><span class="lbl">WIND</span><span class="val">${d.windKmH} km/h</span></div>
      <div class="panel-row"><span class="lbl">DAYLIGHT</span><span class="val">${d.isDay ? 'Yes' : 'No'}</span></div>
      ${d.forecast ? d.forecast.map(f => `<div class="panel-row"><span class="lbl">${f.day}</span><span class="val">${f.min}\u00B0 / ${f.max}\u00B0</span></div>`).join('') : ''}
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadEmailPanel(el) {
  el.innerHTML = '<div class="panel-empty">Fetching emails...</div>';
  try {
    const res = await fetch('/api/emails');
    const d = await res.json();
    if (!d.success || !d.emails?.length) { el.innerHTML = `<div class="panel-empty">${d.message || 'No emails found.'}</div>`; return; }
    el.innerHTML = d.emails.map(e => `
      <div class="email-item">
        <div class="email-from">${escHtml(e.from || 'Unknown')}</div>
        <div class="email-subject">${escHtml(e.subject || '(no subject)')}</div>
        <div class="email-date">${escHtml(e.date || '')}</div>
      </div>
    `).join('');
  } catch { el.innerHTML = '<div class="panel-empty">Error reading emails.</div>'; }
}

async function loadProcessPanel(el) {
  el.innerHTML = '<div class="panel-empty">Loading...</div>';
  try {
    const res = await fetch('/api/control', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'processes' })
    });
    const d = await res.json();
    if (!d.success || !d.processes?.length) { el.innerHTML = '<div class="panel-empty">None found.</div>'; return; }
    el.innerHTML = d.processes.map(p => `
      <div class="proc-item">
        <span class="pcpu">${p.cpu}%</span>
        <span style="color:rgba(255,255,255,0.2)">${p.pid}</span>
        <span class="pcmd">${escHtml(p.command)}</span>
        <button class="pk" onclick="killProc('${p.pid}')" title="Kill"><i class="fa-solid fa-xmark"></i></button>
      </div>
    `).join('');
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function killProc(pid) {
  await fetch('/api/control', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'kill-process', value: pid })
  });
  toast(`Process ${pid} killed, BOSS.`, 'ok');
  const body = document.getElementById('panel-body-processes');
  if (body) loadProcessPanel(body);
}

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
      : '<div class="panel-empty">No memories yet.</div>';
    el.innerHTML += `
      <div class="panel-input">
        <input type="text" id="vault-input" placeholder="Save a memory..." onkeydown="if(event.key==='Enter')addVault()">
        <button onclick="addVault()"><i class="fa-solid fa-plus"></i></button>
      </div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function addVault() {
  const input = document.getElementById('vault-input');
  if (!input || !input.value.trim()) return;
  await fetch('/api/vault', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: input.value.trim() }) });
  toast('Memory saved, BOSS.', 'ok');
  input.value = '';
  loadVaultPanel(document.getElementById('panel-body-vault'));
}

async function deleteVault(id) {
  await fetch(`/api/vault?id=${id}`, { method: 'DELETE' });
  toast('Memory deleted, BOSS.', 'ok');
  loadVaultPanel(document.getElementById('panel-body-vault'));
}

async function loadClipboardPanel(el) {
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'clipboard-read' }) });
    const d = await res.json();
    el.innerHTML = `
      <div class="panel-row"><span class="lbl">CLIPBOARD</span></div>
      <div style="margin-top:6px;padding:8px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);border-radius:8px;font-family:var(--mono);font-size:9px;color:rgba(255,255,255,0.5);max-height:160px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;">${escHtml(d.content || '(empty)')}</div>
      <div class="panel-input" style="margin-top:6px;">
        <input type="text" id="clip-input" placeholder="Write to clipboard..." onkeydown="if(event.key==='Enter')writeClip()">
        <button onclick="writeClip()"><i class="fa-solid fa-copy"></i></button>
      </div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function writeClip() {
  const input = document.getElementById('clip-input');
  if (!input || !input.value.trim()) return;
  try { await navigator.clipboard.writeText(input.value.trim()); } catch {}
  await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'clipboard-write', value: input.value.trim() }) });
  toast('Copied, BOSS.', 'ok');
  input.value = '';
  loadClipboardPanel(document.getElementById('panel-body-clipboard'));
}

function loadSettingsPanel(el) {
  const mem = loadOfflineMemory();
  el.innerHTML = `
    <div class="setting-row">
      <label>VOICE</label>
      <select id="voice-select" style="width:140px">
        <optgroup label="ElevenLabs">
          <option value="21m00Tcm4TlvDq8ikWAM">Rachel</option>
          <option value="EXAVITQu4vr4xnSDxMaL">Bella</option>
          <option value="MF3mGyEYCl7XYWbV9V6O">Elli</option>
          <option value="pFZP5JQG7iQjIQuC4Bku">Lily</option>
          <option value="AZnzlk1XvdvUeBnXmlld">Domi</option>
          <option value="TxGEqnHWrfWFTfGW9XjX">Josh</option>
          <option value="VR6AewLTigWG4xSOukaG">Arnold</option>
          <option value="yoZ06aMxZJJ28mfd3POQ">Sam</option>
        </optgroup>
        <optgroup label="Web Speech (Free)">
          <option value="web-samantha">Samantha (macOS)</option>
          <option value="web-karen">Karen (macOS)</option>
          <option value="web-moira">Moira (macOS)</option>
          <option value="web-tessa">Tessa (macOS)</option>
        </optgroup>
      </select>
    </div>
    <div class="setting-row">
      <label>SPEECH RATE</label>
      <input type="range" id="speech-rate" min="0.5" max="2" step="0.1" value="1.0" style="width:100px">
    </div>
    <div class="setting-row">
      <label>SPEECH PITCH</label>
      <input type="range" id="speech-pitch" min="0.5" max="2" step="0.1" value="1.0" style="width:100px">
    </div>
    <div class="setting-row">
      <label>CONTINUOUS LISTEN</label>
      <input type="checkbox" id="cont-listen" ${mem.continuousListen ? 'checked' : ''}>
    </div>
    <div class="setting-row">
      <label>YOUR NAME</label>
      <input type="text" id="name-input" value="${mem.name || ''}" placeholder="Tell me your name" style="width:130px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);color:rgba(255,255,255,0.5);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;">
    </div>
  `;

  document.getElementById('voice-select').addEventListener('change', (e) => { mem.voiceId = e.target.value; saveOfflineMemory(mem); toast('Voice updated, BOSS.', 'ok'); });
  document.getElementById('speech-rate').addEventListener('input', (e) => { mem.speechRate = parseFloat(e.target.value); saveOfflineMemory(mem); });
  document.getElementById('speech-pitch').addEventListener('input', (e) => { mem.speechPitch = parseFloat(e.target.value); saveOfflineMemory(mem); });
  document.getElementById('cont-listen').addEventListener('change', (e) => { mem.continuousListen = e.target.checked; saveOfflineMemory(mem); });
  document.getElementById('name-input').addEventListener('change', (e) => { mem.name = e.target.value.trim(); saveOfflineMemory(mem); toast(`Name set to ${mem.name}, BOSS.`, 'ok'); });

  if (mem.voiceId) document.getElementById('voice-select').value = mem.voiceId;
  if (mem.speechRate) document.getElementById('speech-rate').value = mem.speechRate;
  if (mem.speechPitch) document.getElementById('speech-pitch').value = mem.speechPitch;
}

function loadCommandsPanel(el) {
  el.innerHTML = `
    <div class="cmd-ref-item"><div class="cc">summon activity / system / weather / emails / processes / vault / clipboard / settings / commands</div><div class="cd">Open a panel</div></div>
    <div class="cmd-ref-item"><div class="cc">close [panel] / close all</div><div class="cd">Dismiss panels</div></div>
    <div class="cmd-ref-item"><div class="cc">set a timer for 5 minutes</div><div class="cd">Timer with voice alert</div></div>
    <div class="cmd-ref-item"><div class="cc">briefing / daily briefing</div><div class="cd">Full system overview</div></div>
    <div class="cmd-ref-item"><div class="cc">tell me a joke / fun fact / quote</div><div class="cd">Entertainment</div></div>
    <div class="cmd-ref-item"><div class="cc">what is 42 * 7 / calculate 100 / 3</div><div class="cd">Quick math</div></div>
    <div class="cmd-ref-item"><div class="cc">lock pc / sleep pc / screenshot</div><div class="cd">System controls</div></div>
    <div class="cmd-ref-item"><div class="cc">volume [0-100] / mute / unmute</div><div class="cd">Audio controls</div></div>
    <div class="cmd-ref-item"><div class="cc">open [app] / close [app]</div><div class="cd">Launch or quit app</div></div>
    <div class="cmd-ref-item"><div class="cc">play / pause / next / previous</div><div class="cd">Media controls</div></div>
    <div class="cmd-ref-item"><div class="cc">remember [fact]</div><div class="cd">Save to vault</div></div>
    <div class="cmd-ref-item"><div class="cc">check emails / read mail</div><div class="cd">Read Mail.app</div></div>
    <div class="cmd-ref-item"><div class="cc">shutdown / restart</div><div class="cd">Power controls</div></div>
    <div class="cmd-ref-item"><div class="cc">tell me about [topic]</div><div class="cd">Ask anything (Gemini)</div></div>
  `;
}

// ================================================
// TEXT INPUT
// ================================================
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && chatInput.value.trim()) { sendMessage(chatInput.value.trim()); chatInput.value = ''; }
});
sendBtn.addEventListener('click', () => {
  if (chatInput.value.trim()) { sendMessage(chatInput.value.trim()); chatInput.value = ''; }
});

// ================================================
// SEND MESSAGE
// ================================================
async function sendMessage(text) {
  addUserMessage(text);
  sfx.click();

  const cmd = parseCommand(text);
  if (cmd) {
    if (cmd.response === '__FETCH_BRIEFING__') {
      addTyping();
      setOrbState('thinking');
      try {
        const bRes = await fetch('/api/briefing');
        const bData = await bRes.json();
        removeTyping();
        if (bData.success && bData.briefing) {
          const b = bData.briefing;
          const briefingText = `${b.greeting}. Here's your briefing for ${b.date} at ${b.time}.\n\nWeather: ${b.weather}\nSystem: ${b.system}\nBattery: ${b.battery}\nMemories stored: ${b.vaultCount}`;
          addAIMessage(briefingText);
          speak(`${b.greeting}. It's ${b.time}. Weather is ${b.weather}. System at ${b.system}, battery ${b.battery}. You have ${b.vaultCount} memories saved, BOSS.`);
        } else { addAIMessage('Unable to fetch briefing, BOSS.'); }
      } catch { removeTyping(); addAIMessage('Briefing service unavailable, BOSS.'); }
      setOrbState('idle');
      return;
    }
    setTimeout(() => addAIMessage(cmd.response), 300);
    speak(cmd.response);
    return;
  }

  addTyping();
  setOrbState('thinking');

  try {
    const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) });
    const data = await res.json();
    removeTyping();
    if (data.success && data.reply) {
      addAIMessage(data.reply.text);
      if (data.reply.command?.action === 'vault-save') {
        await fetch('/api/vault', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: data.reply.command.value?.text || '' }) });
        toast('Saved to vault, BOSS.', 'ok');
      }
      if (data.reply.command && data.reply.command.action !== 'vault-save') {
        await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data.reply.command) });
      }
      speak(data.reply.speech || data.reply.text);
    } else {
      addAIMessage('Something went wrong, BOSS. Please try again.');
      setOrbState('idle');
    }
  } catch {
    removeTyping();
    addAIMessage('Connection error, BOSS. Please try again.');
    setOrbState('idle');
  }
}

// ================================================
// VOICE — TTS
// ================================================
function speak(text) {
  if (!text) return;
  const mem = loadOfflineMemory();
  const voiceId = mem.voiceId || '21m00Tcm4TlvDq8ikWAM';
  if (voiceId.startsWith('web-')) { speakWeb(text, voiceId.replace('web-', '')); return; }

  setOrbState('speaking');
  fetch('/api/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, voiceId }) })
    .then(async (res) => {
      const data = await res.json().catch(() => null);
      if (data && data.fallback) { speakWeb(text); }
      else {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.playbackRate = mem.speechRate || 1.0;
        audio.onended = () => setOrbState('idle');
        audio.play().catch(() => speakWeb(text));
      }
    }).catch(() => speakWeb(text));
}

function speakWeb(text, voiceName) {
  if (!('speechSynthesis' in window)) { setOrbState('idle'); return; }
  const mem = loadOfflineMemory();
  setOrbState('speaking');
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = mem.speechRate || 1.0;
  u.pitch = mem.speechPitch || 1.0;
  const voices = window.speechSynthesis.getVoices();
  if (voiceName) { const match = voices.find(v => v.name.toLowerCase().includes(voiceName)); if (match) u.voice = match; }
  if (!u.voice) { const female = voices.find(v => /female|samantha|karen|moira|tessa/i.test(v.name)) || voices[0]; if (female) u.voice = female; }
  u.onend = () => setOrbState('idle');
  window.speechSynthesis.speak(u);
}

// ================================================
// SPEECH RECOGNITION
// ================================================
let recognition = null;
let isListening = false;
let micStream = null;
const micBtn = document.getElementById('holo-mic-btn');
const orbClick = document.getElementById('orb-click');

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.continuous = false;
  r.interimResults = false;
  r.lang = 'en-US';
  r.onresult = (e) => { sendMessage(e.results[0][0].transcript); stopListening(); };
  r.onerror = () => stopListening();
  r.onend = () => stopListening();
  return r;
}

async function startListening() {
  if (!recognition) recognition = initRecognition();
  if (!recognition) { toast('Speech recognition not supported', 'err'); return; }
  isListening = true;
  micBtn.classList.add('active');
  setOrbState('listening');
  sfx.confirm();
  try { micStream = await navigator.mediaDevices.getUserMedia({ audio: true }); startSpeechWaves(micStream); } catch {}
  try { recognition.start(); } catch {}
}

function stopListening() {
  isListening = false;
  micBtn.classList.remove('active');
  if (orbState === 'listening') setOrbState('idle');
  stopSpeechWaves();
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  try { recognition?.stop(); } catch {}
}

micBtn.addEventListener('click', () => { isListening ? stopListening() : startListening(); });
orbClick.addEventListener('click', () => { isListening ? stopListening() : startListening(); });

if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

// ================================================
// DOCK
// ================================================
document.getElementById('holo-dock').addEventListener('click', (e) => {
  const btn = e.target.closest('.dock-btn');
  if (!btn) return;
  const panel = btn.dataset.panel;
  openPanels.has(panel) ? closePanel(panel) : openPanel(panel);
});

// ================================================
// INIT
// ================================================
document.addEventListener('DOMContentLoaded', runBoot);
