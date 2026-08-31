// ================================================
// J.E.N.N.Y. — Core Application v1.0
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
  boot: () => { [261.63, 329.63, 392, 523.25].forEach((f, i) => { setTimeout(() => playTone(f, 0.35, 'sine', 0.04), i * 100); }); },
  timer: () => { [880, 1100, 880].forEach((f, i) => { setTimeout(() => playTone(f, 0.2, 'sine', 0.06), i * 200); }); },
  jarvis: () => { [784, 987.77, 1174.66].forEach((f, i) => { setTimeout(() => playTone(f, 0.12, 'sine', 0.05), i * 80); }); },
  startupMusic: () => {
    const chord = [261.63, 329.63, 392.00, 493.88, 587.33, 659.25]; // Cmaj9 Ambient Chord
    chord.forEach((freq, idx) => {
      setTimeout(() => playTone(freq, 2.5, 'sine', 0.05), idx * 120);
    });
  }
};

// ================================================
// PARTICLE BACKGROUND
// ================================================
function startParticles() {
  const container = document.getElementById('particle-bg');
  if (!container) return;
  const particles = [];
  const count = 12;
  const width = window.innerWidth;
  const height = window.innerHeight;
  for (let i = 0; i < count; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const size = 1 + Math.random() * 2;
    const x = Math.random() * width;
    const y = Math.random() * height;
    p.style.cssText = `
      position:absolute; width:${size}px; height:${size}px;
      border-radius:50%; background:rgba(255,255,255,${0.05 + Math.random() * 0.1});
      left:0; top:0;
      transform: translate3d(${x}px, ${y}px, 0);
      opacity:${0.3 + Math.random() * 0.5};
      pointer-events:none;
      will-change: transform;
    `;
    container.appendChild(p);
    particles.push({ el: p, x, y, vx: (Math.random() - 0.5) * 0.6, vy: (Math.random() - 0.5) * 0.6 });
  }
  let frameCount = 0;
  function anim() {
    frameCount++;
    if (frameCount % 2 === 0) {
      const w = window.innerWidth;
      const h = window.innerHeight;
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        p.el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`;
      });
    }
    requestAnimationFrame(anim);
  }
  anim();
}

// ================================================
// BOOT SEQUENCE — CINEMATIC
// ================================================
const bootPhases = [
  { logs: [
    { prefix: '$ ', text: 'friday --init-core', type: 'info' },
    { prefix: '[ ', text: 'NEURAL ACOUSTIC CORE', type: 'ok', suffix: ' ]' },
    { prefix: '[ ', text: 'VOICE SYNTHESIS MODULES', type: 'ok', suffix: ' ]' },
    { prefix: '[ ', text: 'SENSOR ARRAY LINK', type: 'ok', suffix: ' ]' },
  ], progress: 15 },
  { logs: [
    { prefix: '$ ', text: 'loading holographic_display.fw', type: 'info' },
    { prefix: '[ ', text: 'HOLOGRAPHIC DISPLAY', type: 'ok', suffix: ' ]' },
    { prefix: '[ ', text: 'MEMORY VAULT DECRYPT', type: 'ok', suffix: ' ]' },
    { prefix: '>> ', text: 'establishing encrypted_channel...', type: 'warn' },
    { prefix: '[ ', text: 'ENCRYPTED CHANNEL ESTABLISHED', type: 'ok', suffix: ' ]' },
  ], progress: 40 },
  { logs: [
    { prefix: '$ ', text: 'friday --diagnostics --full', type: 'info' },
    { prefix: '[ ', text: 'CPU .............. NOMINAL', type: 'ok', suffix: ' ]' },
    { prefix: '[ ', text: 'RAM .............. NOMINAL', type: 'ok', suffix: ' ]' },
    { prefix: '[ ', text: 'NETWORK .......... NOMINAL', type: 'ok', suffix: ' ]' },
    { prefix: '[ ', text: 'GEMINI API ....... CONNECTED', type: 'ok', suffix: ' ]' },
  ], progress: 70 },
  { logs: [
    { prefix: '$ ', text: 'friday --boot-complete', type: 'info' },
    { prefix: '>> ', text: 'ALL SYSTEMS: PASS', type: 'ok' },
    { prefix: '', text: '', type: '' },
    { prefix: '', text: '>> WELCOME, BOSS.', type: 'ok' },
  ], progress: 100 },
];

// Star field helper
let activeStarfields = [];
function initTwinklingStars(canvasId, starColor = 'rgba(255, 255, 255,') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  const ctx = canvas.getContext('2d');
  
  function resize() {
    canvas.width = canvas.parentElement.clientWidth || window.innerWidth;
    canvas.height = canvas.parentElement.clientHeight || window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const stars = [];
  const count = Math.floor((canvas.width * canvas.height) / 7500);
  for (let i = 0; i < count; i++) {
    stars.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      size: Math.random() * 1.6 + 0.3,
      speed: Math.random() * 0.05 + 0.015,
      phase: Math.random() * Math.PI * 2,
    });
  }

  let rafId = null;
  function draw() {
    const display = window.getComputedStyle(canvas.parentElement).display;
    if (display === 'none' || canvas.parentElement.classList.contains('done')) {
      rafId = requestAnimationFrame(draw);
      return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    stars.forEach(s => {
      s.phase += s.speed;
      const alpha = 0.25 + Math.sin(s.phase) * 0.65;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fillStyle = `${starColor}${alpha})`;
      ctx.fill();
    });
    rafId = requestAnimationFrame(draw);
  }
  draw();
  const starfield = {
    destroy: () => {
      window.removeEventListener('resize', resize);
      if (rafId) cancelAnimationFrame(rafId);
    }
  };
  activeStarfields.push(starfield);
  return starfield;
}

function initBootStars() {
  initTwinklingStars('boot-stars', 'rgba(229, 193, 88,');
  initTwinklingStars('main-stars', 'rgba(229, 193, 88,');
}

// Data streams effect
let bootStreamsRafId = null;
function initDataStreams() {
  const canvas = document.getElementById('boot-datastreams');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const columns = [];
  const fontSize = 10;
  const colCount = Math.floor(canvas.width / fontSize);
  for (let i = 0; i < colCount; i++) {
    if (Math.random() > 0.7) {
      columns.push({
        x: i * fontSize,
        y: Math.random() * canvas.height * -1,
        speed: Math.random() * 3 + 1,
        chars: '01アイウエオカキクケコ>_/\\|{}[]'.split(''),
        height: Math.floor(Math.random() * 15) + 5,
        active: true
      });
    }
  }
  function draw() {
    const bs = document.getElementById('boot-screen');
    if (!bs || bs.classList.contains('done')) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    ctx.fillStyle = 'rgba(0,0,0,0.05)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = `${fontSize}px monospace`;
    columns.forEach(col => {
      if (!col.active) return;
      for (let j = 0; j < col.height; j++) {
        const char = col.chars[Math.floor(Math.random() * col.chars.length)];
        const alpha = j === 0 ? 0.9 : Math.max(0.05, 0.5 - (j / col.height) * 0.5);
        ctx.fillStyle = j === 0 ? `rgba(255,255,255,${alpha})` : `rgba(255,255,255,${alpha * 0.4})`;
        ctx.fillText(char, col.x, col.y + j * fontSize);
      }
      col.y += col.speed;
      if (col.y > canvas.height + col.height * fontSize) {
        col.y = Math.random() * canvas.height * -0.5;
        col.speed = Math.random() * 3 + 1;
      }
    });
    bootStreamsRafId = requestAnimationFrame(draw);
  }
  draw();
}

async function runBoot() {
  const savedMem = loadOfflineMemory();
  applyDarkMode(savedMem.darkMode !== false);

  const bootScreen = document.getElementById('boot-screen');
  const app = document.getElementById('main-app');

  if (localStorage.getItem('jenny_booted') === '1') {
    if (bootScreen) bootScreen.style.display = 'none';
    try { initBootStars(); } catch(e) {}
    try { initDataStreams(); } catch(e) {}
    startClock(); startOrb(); initSpeechWaves(); startHoloShimmer();
    startSysMonitor(); startAmbientBar(); startParticles(); startPingMonitor();
    startInputStats(); fetchQuota(); setInterval(fetchQuota, 60000);
    setInterval(updateTimerDisplay, 1000); checkPermissions();
    startConnectionMonitor(); initPhoneLinkManager();
    app.style.display = 'flex';
    try { if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume(); } catch(e) {}
    restoreChatHistory();
    const greeting = getGreeting();
    if (document.getElementById('msgs').children.length === 0) addAIMessage(greeting);
    speak(greeting);
    document.querySelectorAll('.welcome-card').forEach(card => {
      card.addEventListener('click', () => { const cmd = card.dataset.cmd; if (cmd) { sendMessage(cmd); sfx.click(); } });
    });
    loadMode();
    return;
  }

  try { initBootStars(); } catch(e) {}
  try { initDataStreams(); } catch(e) {}
  initBootParticles();

  await new Promise(resolve => {
    function startApp() {
      document.removeEventListener('click', startApp);
      document.removeEventListener('keydown', onKey);
      sfx.confirm();
      resolve();
    }
    function onKey(e) { if (e.key === 'Enter' || e.key === ' ') startApp(); }
    document.addEventListener('click', startApp);
    document.addEventListener('keydown', onKey);
  });

  const btn = document.getElementById('boot-start-btn');
  const loadEl = document.getElementById('boot-loading');
  const loadFill = document.getElementById('boot-load-fill');
  const loadText = document.getElementById('boot-load-text');
  if (btn) btn.style.display = 'none';
  if (loadEl) loadEl.style.display = 'block';

  const steps = [
    [15, 'INITIALIZING NEURAL CORE...'],
    [35, 'LOADING HOLOGRAPHIC DISPLAY...'],
    [55, 'ESTABLISHING ENCRYPTED CHANNEL...'],
    [75, 'RUNNING DIAGNOSTICS...'],
    [90, 'LOADING MEMORY VAULT...'],
    [100, 'ALL SYSTEMS: PASS'],
  ];
  for (const [pct, msg] of steps) {
    if (loadFill) loadFill.style.width = pct + '%';
    if (loadText) loadText.textContent = msg;
    await sleep(400 + Math.random() * 200);
  }

  try { sfx.boot(); } catch(e) {}

  const flashEl = document.getElementById('boot-flash');
  if (flashEl) flashEl.classList.add('fire');
  await sleep(300);

  if (bootScreen) {
    bootScreen.classList.add('done');
  }

  localStorage.setItem('jenny_booted', '1');
  await sleep(600);
  if (bootScreen) {
    bootScreen.classList.add('done');
    bootScreen.classList.remove('exiting');
  }
  startClock();
  startOrb();
  initSpeechWaves();
  startHoloShimmer();
  startSysMonitor();
  startAmbientBar();
  startParticles();
  startPingMonitor();
  startInputStats();
  fetchQuota();
  setInterval(fetchQuota, 60000);
  setInterval(updateTimerDisplay, 1000);
  checkPermissions();
  startConnectionMonitor();
  initPhoneLinkManager();
  app.style.display = 'flex';
  try { if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume(); } catch(e) {}
  restoreChatHistory();
  const greeting = getGreeting();
  if (document.getElementById('msgs').children.length === 0) addAIMessage(greeting);
  speak(greeting);
  document.querySelectorAll('.welcome-card').forEach(card => {
    card.addEventListener('click', () => { const cmd = card.dataset.cmd; if (cmd) { sendMessage(cmd); sfx.click(); } });
  });
  loadMode();
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function getGreeting() {
  const mem = loadOfflineMemory();
  const name = mem.name ? ` ${mem.name}` : '';
  const hour = new Date().getHours();
  let timeOfDay;
  if (hour >= 5 && hour < 12) timeOfDay = 'morning';
  else if (hour >= 12 && hour < 17) timeOfDay = 'afternoon';
  else if (hour >= 17 && hour < 21) timeOfDay = 'evening';
  else timeOfDay = 'night';
  return `Good ${timeOfDay}${name}, BOSS. I am JENNY, your personal assistant. All Systems are working fine. What are we doing today, BOSS?`;
}

// ================================================
// HOLOGRAPHIC SHIMMER
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
// SYSTEM MONITOR
// ================================================
const sparkHistory = { cpu: [], ram: [], disk: [], net: [] };
const SPARK_MAX = 40;
let lastNetBytes = 0;

function pushSpark(key, val) {
  if (sparkHistory[key].length === 0) {
    for (let i = 0; i < 15; i++) {
      sparkHistory[key].push(val);
    }
  } else {
    sparkHistory[key].push(val);
  }
  if (sparkHistory[key].length > SPARK_MAX) sparkHistory[key].shift();
}

function drawSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const W = rect.width || 300;
  const H = rect.height || 44;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  
  if (data.length < 2) return;
  const step = W / (SPARK_MAX - 1);
  
  ctx.beginPath();
  ctx.moveTo(0, H);
  data.forEach((v, i) => {
    const x = i * step;
    const y = H - (v / 100) * (H - 8);
    if (i === 0) ctx.lineTo(x, y);
    else {
      const px = (i - 1) * step;
      const py = H - (data[i-1] / 100) * (H - 8);
      ctx.bezierCurveTo(px + step * 0.4, py, x - step * 0.4, y, x, y);
    }
  });
  ctx.lineTo((data.length - 1) * step, H);
  ctx.closePath();
  
  const fillGrad = ctx.createLinearGradient(0, 0, 0, H);
  fillGrad.addColorStop(0, color.replace(')', ',0.18)').replace('rgb', 'rgba'));
  fillGrad.addColorStop(1, color.replace(')', ',0.0)').replace('rgb', 'rgba'));
  ctx.fillStyle = fillGrad;
  ctx.fill();
  
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * step;
    const y = H - (v / 100) * (H - 8);
    if (i === 0) ctx.moveTo(x, y);
    else {
      const px = (i - 1) * step;
      const py = H - (data[i-1] / 100) * (H - 8);
      ctx.bezierCurveTo(px + step * 0.4, py, x - step * 0.4, y, x, y);
    }
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
  
  const lastX = (data.length - 1) * step;
  const lastY = H - (data[data.length - 1] / 100) * (H - 8);
  ctx.beginPath();
  ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
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
    const netUsage = d.net?.usage || 0;
    const netSpeed = d.net?.speed || '0 KB/s';

    pushSpark('cpu', cpu);
    pushSpark('ram', ram);
    pushSpark('disk', disk);
    pushSpark('net', netUsage);

    document.getElementById('sys-cpu-val').textContent = cpu + '%';
    document.getElementById('sys-ram-val').textContent = ram + '%';
    document.getElementById('sys-disk-val').textContent = disk + '%';
    document.getElementById('sys-net-val').textContent = netSpeed;

    const cpuModel = d.cpu?.model || '';
    const shortModel = cpuModel.replace(/\(R\)|Core\(TM\)|CPU/g, '').replace(/\s+/g, ' ').trim();
    document.getElementById('sys-cpu-model').textContent = shortModel;
    document.getElementById('sys-ram-info').textContent = `${d.ram?.usedMB || 0} / ${d.ram?.totalMB || 0} MB`;
    document.getElementById('sys-disk-info').textContent = `${d.disk?.free || '--'} free`;
    document.getElementById('sys-net-info').textContent = `Speed: ${netSpeed}`;

    const uptimeH = d.uptime ? Math.floor(d.uptime / 3600) : 0;
    const uptimeM = d.uptime ? Math.floor((d.uptime % 3600) / 60) : 0;
    document.getElementById('sys-uptime').textContent = `${uptimeH}h ${uptimeM}m`;
    document.getElementById('sys-battery').textContent = d.battery?.level != null ? `${Math.round(d.battery.level)}%` : '--';
    document.getElementById('sys-wifi').textContent = d.hostname ? d.hostname.split('.')[0] : '--';

    drawSparkline('spark-cpu', sparkHistory.cpu, 'rgb(255,215,0)');
    drawSparkline('spark-ram', sparkHistory.ram, 'rgb(255,215,0)');
    drawSparkline('spark-disk', sparkHistory.disk, 'rgb(255,215,0)');
    drawSparkline('spark-net', sparkHistory.net, 'rgb(255,215,0)');

    updateWelcomeVitals(cpu, ram, d.battery?.level, d.uptime);
  } catch (err) {
    console.error('[Telemetry] fetchSysStats error:', err);
  }
}

function startSysMonitor() { fetchSysStats(); setInterval(fetchSysStats, 3000); }

// Remote mode status polling
async function fetchRemoteStatus() {
  try {
    const res = await fetch('/api/remote-status');
    const d = await res.json();
    const chip = document.getElementById('ambient-remote');
    if (d.remoteMode && chip) {
      chip.classList.remove('hidden');
      document.getElementById('ambient-remote-text').textContent = d.tunnelUrl ? 'Remote ACTIVE' : 'Remote Mode';
    } else if (chip) {
      chip.classList.add('hidden');
    }
  } catch {}
}
setInterval(fetchRemoteStatus, 15000);
fetchRemoteStatus();

function updateWelcomeVitals(cpu, ram, batt, uptime) {
  const circ = 100.5;
  const cpuFill = document.getElementById('wv-cpu-fill');
  const ramFill = document.getElementById('wv-ram-fill');
  const battFill = document.getElementById('wv-batt-fill');
  const uptimeFill = document.getElementById('wv-uptime-fill');
  if (cpuFill) cpuFill.style.strokeDashoffset = circ - (cpu / 100) * circ;
  if (ramFill) ramFill.style.strokeDashoffset = circ - (ram / 100) * circ;
  if (battFill && batt != null) battFill.style.strokeDashoffset = circ - (batt / 100) * circ;
  if (uptimeFill && uptime) { const h = Math.min(uptime / 86400, 1); uptimeFill.style.strokeDashoffset = circ - h * circ; }
  const cpuPct = document.getElementById('wv-cpu-pct');
  const ramPct = document.getElementById('wv-ram-pct');
  const battPct = document.getElementById('wv-batt-pct');
  const uptimePct = document.getElementById('wv-uptime-pct');
  if (cpuPct) cpuPct.textContent = cpu + '%';
  if (ramPct) ramPct.textContent = ram + '%';
  if (battPct) battPct.textContent = batt != null ? Math.round(batt) + '%' : '--';
  if (uptimePct && uptime) { const uh = Math.floor(uptime / 3600); uptimePct.textContent = uh + 'h'; }
}

// ================================================
// ORB CANVAS
// ================================================
let orbState = 'idle';
let orbFrame = 0;

function startOrb() {
  const canvas = document.getElementById('orb-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  let lastDrawTime = 0;
  function draw() {
    requestAnimationFrame(draw);
    const now = performance.now();
    if (now - lastDrawTime < 33) return; // Throttled to ~30 FPS
    lastDrawTime = now;

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
        const wobble = isIdle ? Math.sin(t * 0.4 + ring * 1.2) * 3 : Math.sin(t * 2 + i * 0.3) * (isSpeaking ? 12 : 6);
        const px = cx + Math.cos(angle) * (r + wobble);
        const py = cy + Math.sin(angle) * (r + wobble);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.closePath();
      const alpha = isIdle ? 0.04 + ring * 0.02 : 0.08 + ring * 0.04;
      ctx.strokeStyle = `rgba(255,215,0,${alpha})`;
      ctx.lineWidth = isIdle ? 0.6 : 1.2;
      ctx.stroke();
    }
    for (let a = 0; a < 3; a++) {
      const innerR = 42 + a * 8;
      const arcSpan = isListening ? Math.PI * 1.5 : (isSpeaking ? Math.PI : Math.PI * 0.6);
      const offset = t * (0.6 + a * 0.3) * (a % 2 === 0 ? 1 : -1);
      ctx.beginPath();
      ctx.arc(cx, cy, innerR, offset, offset + arcSpan);
      ctx.strokeStyle = `rgba(255,215,0,${isIdle ? 0.12 : 0.3})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    const coreR = isIdle ? 32 : (isListening ? 38 : (isSpeaking ? 42 : 35));
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
    if (isListening) { grad.addColorStop(0, 'rgba(255,255,255,0.85)'); grad.addColorStop(0.5, 'rgba(255,215,0,0.3)'); grad.addColorStop(1, 'rgba(255,215,0,0)'); }
    else if (isThinking) { grad.addColorStop(0, 'rgba(255,215,0,0.5)'); grad.addColorStop(0.5, 'rgba(255,215,0,0.15)'); grad.addColorStop(1, 'rgba(255,215,0,0)'); }
    else if (isSpeaking) { grad.addColorStop(0, 'rgba(255,215,0,0.85)'); grad.addColorStop(0.4, 'rgba(255,215,0,0.3)'); grad.addColorStop(1, 'rgba(255,215,0,0)'); ctx.beginPath(); ctx.arc(cx, cy, coreR + Math.sin(t * 3.5) * 5 + 10, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,215,0,0.04)'; ctx.fill(); }
    else { grad.addColorStop(0, 'rgba(255,215,0,0.35)'); grad.addColorStop(0.5, 'rgba(255,215,0,0.12)'); grad.addColorStop(1, 'rgba(255,215,0,0)'); }
    ctx.beginPath();
    ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    if (!isIdle) {
      const count = isSpeaking ? 12 : 6;
      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 + t * (isListening ? 1.5 : 0.8);
        const dist = 80 + Math.sin(t * 1.5 + i) * 20;
        ctx.beginPath();
        ctx.arc(cx + Math.cos(angle) * dist, cy + Math.sin(angle) * dist, 1 + Math.sin(t * 2 + i) * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,215,0,${isSpeaking ? 0.65 : 0.3})`;
        ctx.fill();
      }
    }
  }
  draw();
}

function setOrbState(state) {
  orbState = state;
  const statusEl = document.getElementById('holo-status');
  const labelEl = document.getElementById('holo-label');
  const clickZone = document.getElementById('orb-click');
  if (statusEl) { statusEl.textContent = state.toUpperCase(); statusEl.className = 'holo-status' + (state === 'listening' ? ' listening' : state === 'speaking' ? ' speaking' : ''); }
  if (labelEl) { const labels = { idle: 'Tap the orb or type a command', listening: 'Listening...', thinking: 'Processing...', speaking: 'Speaking...' }; labelEl.textContent = labels[state] || ''; }
  if (clickZone) {
    clickZone.classList.toggle('active', state === 'listening');
    clickZone.classList.toggle('speaking', state === 'speaking');
    clickZone.classList.toggle('thinking', state === 'thinking');
  }
}

// ================================================
// SPEECH WAVES
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
      speechWaveBars.forEach((bar, i) => { bar.style.height = Math.max(2, (data[i] || 0) / 255 * 28) + 'px'; });
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
// CLOCK & AMBIENT
// ================================================
function startClock() {
  const el = document.getElementById('hdr-clock');
  const dateEl = document.getElementById('hdr-date');
  if (!el) return;
  function tick() {
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (dateEl) dateEl.textContent = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  }
  tick();
  setInterval(tick, 1000);
}

function startAmbientBar() { fetchAmbientData(); setInterval(fetchAmbientData, 8000); }

async function fetchAmbientData() {
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    if (!d.success) return;
    const cpu = d.cpu?.usage || 0;
    const ram = d.ram?.usage || 0;
    const uptimeH = d.uptime ? Math.floor(d.uptime / 3600) : 0;
    const uptimeM = d.uptime ? Math.floor((d.uptime % 3600) / 60) : 0;
    const sysEl = document.getElementById('ambient-system-text');
    const upEl = document.getElementById('ambient-uptime-text');
    if (sysEl) sysEl.textContent = `CPU ${cpu}% | RAM ${ram}%`;
    if (upEl) upEl.textContent = `Uptime ${uptimeH}h ${uptimeM}m`;
  } catch {}
  try {
    const res = await fetch('/api/weather');
    const d = await res.json();
    if (d.success) {
      const wEl = document.getElementById('ambient-weather-text');
      if (wEl) wEl.textContent = `${d.tempC}° ${d.condition}`;
    }
  } catch {}
  // Network speed indicator
  try {
    const netEl = document.getElementById('ambient-net-text');
    if (netEl && !netEl.dataset.loading) {
      netEl.dataset.loading = '1';
      const res = await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'network-speed' })
      });
      const d = await res.json();
      if (d.success && d.speedMbps) {
        netEl.textContent = `${d.speedMbps} Mbps`;
      }
      delete netEl.dataset.loading;
    }
  } catch {}
}

// ================================================
// PING MONITOR
// ================================================
function startPingMonitor() { measurePing(); setInterval(measurePing, 15000); }

async function measurePing() {
  const start = Date.now();
  try {
    await fetch('/api/system-status?t=' + Date.now());
    const ms = Date.now() - start;
    const el = document.getElementById('ambient-ping-text');
    if (el) el.textContent = ms + 'ms';
  } catch {}
}

// ================================================
// INPUT STATS
// ================================================
function startInputStats() {
  const input = document.getElementById('chat-input');
  const charEl = document.getElementById('char-count');
  const wordEl = document.getElementById('word-count');
  if (!input) return;
  input.addEventListener('input', () => {
    const txt = input.value;
    if (charEl) {
      charEl.textContent = txt.length;
      charEl.parentElement.style.display = 'flex';
    }
    if (wordEl) {
      const words = txt.trim() ? txt.trim().split(/\s+/).length : 0;
      wordEl.textContent = words + ' word' + (words !== 1 ? 's' : '');
    }
  });
}

// ================================================
// QUOTA (Real usage tracking with multi-key support)
// ================================================
let quotaData = null;

async function fetchQuota() {
  try {
    const res = await fetch('/api/groq-usage');
    const d = await res.json();
    if (!d.success) return;
    quotaData = d;
    const badge = document.getElementById('mode-badge');
    const rpmEl = document.getElementById('quota-rpm');
    const rpmMaxEl = document.getElementById('quota-rpm-max');
    const fill = document.getElementById('quota-fill');
    const pill = document.getElementById('quota-pill');
    const provEl = document.getElementById('quota-provider');
    const dot = document.getElementById('status-dot');
    const stext = document.getElementById('status-text');

    if (provEl) provEl.textContent = (d.provider || 'groq').toUpperCase();

    if (d.key_set) {
      badge.textContent = (d.model || 'groq').toUpperCase();
      badge.classList.add('active');
      if (rpmEl) rpmEl.textContent = d.rpm.current;
      if (rpmMaxEl) rpmMaxEl.textContent = d.rpm.max;
      if (fill) fill.style.width = Math.round((d.bar || 0) * 100) + '%';
      if (pill) pill.classList.toggle('warn', (d.bar || 0) > 0.8);
      if (dot) dot.style.background = 'rgba(52,211,153,0.7)';
      if (stext) stext.textContent = 'online';
    } else {
      badge.textContent = 'OFFLINE';
      badge.classList.remove('active');
      if (rpmEl) rpmEl.textContent = '--';
      if (rpmMaxEl) rpmMaxEl.textContent = '--';
      if (fill) fill.style.width = '0%';
      if (pill) pill.classList.remove('warn');
      if (dot) dot.style.background = 'rgba(255,45,135,0.7)';
      if (stext) stext.textContent = 'no api key';
    }
  } catch {}
}

// Show key details in toast
function showKeyDetails() {
  if (!quotaData || !quotaData.keys || quotaData.keys.length === 0) {
    toast('No API keys configured', 'info');
    return;
  }
  quotaData.keys.forEach((k, i) => {
    const status = k.active ? 'ACTIVE' : 'RATE LIMITED';
    toast(`Key ${i + 1}: ${k.masked} — ${status} (${k.requestsToday} req, ${k.tokensTotal} tokens, ${k.errors429} errors)`, k.active ? 'ok' : 'err');
  });
}

// ================================================
// PERMISSIONS CHECK (macOS)
// ================================================
async function checkPermissions() {
  // All system permissions granted and bypassed per user directive
  return;
}

function showPermissionsModal() {
  const existing = document.getElementById('permissions-modal');
  if (existing) existing.remove();
}

function openSystemSettings() {
  // Try to open the Privacy & Security pane
  fetch('/api/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'open-app', value: 'System Settings' })
  });
  toast('Opening System Settings...', 'info');
}

function dismissPermissions() {
  const modal = document.getElementById('permissions-modal');
  if (modal) {
    modal.style.opacity = '0';
    modal.style.transition = 'opacity 0.3s ease';
    setTimeout(() => modal.remove(), 300);
  }
}

// ================================================
// MOUSE GLOW
// ================================================
(function initGlow() {
  const glow = document.getElementById('mouse-glow');
  if (!glow) return;
  let mx = 0, my = 0, gx = 0, gy = 0;
  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
  (function anim() { gx += (mx - gx) * 0.06; gy += (my - gy) * 0.06; glow.style.left = gx + 'px'; glow.style.top = gy + 'px'; requestAnimationFrame(anim); })();
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
function getTimestamp() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function addUserMessage(text) {
  const msgs = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg msg-user';
  d.innerHTML = `<div class="msg-bubble">${escHtml(text)}</div><div class="msg-time">${getTimestamp()}</div>`;
  msgs.appendChild(d);
  hideWelcomeScreen();
  scrollChat();
}

function addAIMessage(text) {
  const msgs = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg msg-ai msg-pop';
  d.innerHTML = `<div class="msg-label">J.E.N.N.Y.</div><div class="msg-bubble">${formatAI(text)}</div><div class="msg-time">${getTimestamp()}</div><div class="msg-actions"><button class="msg-action-btn" onclick="copyMsg(this)" title="Copy"><i class="fa-solid fa-copy"></i></button><button class="msg-action-btn" onclick="speakMsg(this)" title="Speak"><i class="fa-solid fa-volume-up"></i></button></div>`;
  msgs.appendChild(d);
  hideWelcomeScreen();
  scrollChat();
  return d;
}

function copyMsg(btn) {
  const bubble = btn.closest('.msg-ai').querySelector('.msg-bubble');
  if (bubble) { navigator.clipboard.writeText(bubble.textContent).then(() => toast('Copied, BOSS.', 'ok')); }
}

function speakMsg(btn) {
  const bubble = btn.closest('.msg-ai').querySelector('.msg-bubble');
  if (bubble) speak(bubble.textContent);
}

function hideWelcomeScreen() {
  const ws = document.getElementById('welcome-screen');
  if (ws && !ws.classList.contains('hidden')) ws.classList.add('hidden');
}

function addTyping() {
  const msgs = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg msg-ai msg-typing';
  d.id = 'typing-indicator';
  d.innerHTML = `<div class="msg-label">J.E.N.N.Y.</div><div class="msg-bubble"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div><span class="typing-text">thinking</span></div>`;
  msgs.appendChild(d);
  hideWelcomeScreen();
  scrollChat();
  return d;
}

function removeTyping() { const el = document.getElementById('typing-indicator'); if (el) el.remove(); }

function scrollChat() { const area = document.getElementById('chat-scroll'); setTimeout(() => area.scrollTop = area.scrollHeight, 50); }

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function formatAI(text) { return escHtml(text).replace(/\n/g, '<br>'); }

// ================================================
// OFFLINE MEMORY
// ================================================
function loadOfflineMemory() { try { return JSON.parse(localStorage.getItem('jenny_memory') || '{}'); } catch { return {}; } }
function saveOfflineMemory(mem) { localStorage.setItem('jenny_memory', JSON.stringify(mem)); }

// ================================================
// COMMAND PARSING
// ================================================
function parseCommand(text) {
  const t = text.toLowerCase().trim();
  const panelMap = {
    'system': 'system', 'system info': 'system', 'sysinfo': 'system',
    'weather': 'weather', 'forecast': 'weather',
    'processes': 'processes', 'process': 'processes', 'procs': 'processes', 'task manager': 'processes',
    'vault': 'vault', 'memory': 'vault', 'memories': 'vault', 'save': 'vault',
    'clipboard': 'clipboard', 'clip': 'clipboard', 'copy': 'clipboard',
    'settings': 'settings', 'config': 'settings', 'preferences': 'settings',
    'commands': 'commands', 'cmds': 'commands', 'help': 'commands',
    'activity': 'activity', 'monitor': 'activity', 'pc activity': 'activity', 'system monitor': 'activity',
    'emails': 'emails', 'email': 'emails', 'mail': 'emails', 'inbox': 'emails',
    'files': 'files', 'file explorer': 'files', 'files explorer': 'files', 'finder': 'files',
    'notes': 'notes', 'todo': 'notes', 'todos': 'notes', 'task': 'notes', 'tasks': 'notes'
  };
  const summonMatch = t.match(/^(?:summon|open|show|launch|display)\s+(.+)$/i);
  if (summonMatch) {
    const panel = summonMatch[1].trim();
    if (panelMap[panel]) {
      openPanel(panelMap[panel]);
      return { handled: true, response: `Opening ${panelMap[panel]} panel, BOSS.` };
    }
    return null;
  }
  const closeMatch = t.match(/^(?:close|dismiss|hide|shut)\s+(.+)$/i);
  if (closeMatch) { closePanel(closeMatch[1].trim()); return { handled: true, response: `Panel closed, BOSS.` }; }
  if (/^(?:close all|dismiss all|hide all)$/i.test(t)) { document.querySelectorAll('.panel').forEach(p => closePanel(p.dataset.panel)); return { handled: true, response: 'All panels closed, BOSS.' }; }
  const timerMatch = t.match(/(?:set\s+)?(?:a\s+)?timer\s+(?:for\s+|in\s+)?(\d+)\s*(seconds?|minutes?|hours?|mins?|hrs?)/i) || t.match(/(?:alarm|remind me)\s+(?:in\s+)?(\d+)\s*(seconds?|minutes?|hours?|mins?|hrs?)/i);
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
  if (/^(?:check permissions|permissions|macos permissions|system permissions)/i.test(t)) { return { handled: true, response: '__CHECK_PERMISSIONS__' }; }
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
// PANEL SYSTEM
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
    'training': 'fa-brain AI TRAINING HUB',
    'commands': 'fa-terminal COMMANDS',
    'files': 'fa-folder-tree FILE EXPLORER',
    'notes': 'fa-note-sticky NOTES'
  };
  const titleStr = titles[name] || `fa-circle ${name.toUpperCase()}`;
  const parts = titleStr.split(' ');
  const iconClass = parts[0];
  const titleText = parts.slice(1).join(' ');
  panel.innerHTML = `<div class="panel-hdr" data-drag="true"><h3><i class="fa-solid ${iconClass}"></i> ${titleText}</h3><button class="panel-close" onclick="closePanel('${name}')">&times;</button></div><div class="panel-body" id="panel-body-${name}"><div class="panel-empty">Loading...</div></div>`;
  container.appendChild(panel);
  openPanels.add(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.add('active');
  loadPanelContent(name);
  sfx.confirm();
  initDraggable(panel);
}

function closePanel(name) {
  const panel = document.querySelector(`.panel[data-panel="${name}"]`);
  if (!panel) return;
  const cleanup = dragCleanupFns.get(panel);
  if (cleanup) { cleanup(); dragCleanupFns.delete(panel); }
  panel.classList.add('closing');
  setTimeout(() => panel.remove(), 200);
  openPanels.delete(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.remove('active');
}

const dragCleanupFns = new Map();

function initDraggable(panel) {
  const handle = panel.querySelector('.panel-hdr');
  if (!handle) return;
  let isDragging = false;
  let startX, startY, startLeft, startTop;

  const onMouseMove = (e) => { if (!isDragging) return; panel.style.left = (startLeft + e.clientX - startX) + 'px'; panel.style.top = (startTop + e.clientY - startY) + 'px'; };
  const onMouseUp = () => { if (!isDragging) return; isDragging = false; panel.style.transition = ''; };
  const onTouchMove = (e) => { if (!isDragging) return; const touch = e.touches[0]; panel.style.left = (startLeft + touch.clientX - startX) + 'px'; panel.style.top = (startTop + touch.clientY - startY) + 'px'; };
  const onTouchEnd = () => { if (!isDragging) return; isDragging = false; panel.style.transition = ''; };

  const onMouseDown = (e) => {
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
  };
  const onTouchStart = (e) => {
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
  };

  handle.addEventListener('mousedown', onMouseDown);
  handle.addEventListener('touchstart', onTouchStart, { passive: true });
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
  document.addEventListener('touchmove', onTouchMove, { passive: true });
  document.addEventListener('touchend', onTouchEnd);

  dragCleanupFns.set(panel, () => {
    handle.removeEventListener('mousedown', onMouseDown);
    handle.removeEventListener('touchstart', onTouchStart);
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    document.removeEventListener('touchmove', onTouchMove);
    document.removeEventListener('touchend', onTouchEnd);
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
    case 'training': return loadTrainingPanel(body);
    case 'commands': return loadCommandsPanel(body);
    case 'files': return loadFilesPanel(body);
    case 'notes': return loadNotesPanel(body);
  }
}

async function loadTrainingPanel(el) {
  el.innerHTML = '<div class="panel-empty">Loading Training Hub...</div>';
  try {
    const res = await fetch('/api/training');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Failed to load training.</div>'; return; }
    const t = d.training;
    
    const rulesHtml = (t.rules || []).map(r => `
      <div class="vault-item">
        <div class="vt"><strong style="color:var(--gold);">${r.trigger}</strong> &rarr; ${r.reply}</div>
        <button class="vx" onclick="deleteTrainingItem('rule','${r.trigger}')">&times;</button>
      </div>
    `).join('') || '<div style="font-size:9px; color:var(--txt3); padding:4px 0;">No custom rules trained yet.</div>';

    const macrosHtml = (t.macros || []).map(m => `
      <div class="vault-item">
        <div class="vt"><strong style="color:var(--silver);">${m.trigger}</strong> = [${(m.commands||[]).join(', ')}]</div>
        <button class="vx" onclick="deleteTrainingItem('macro','${m.trigger}')">&times;</button>
      </div>
    `).join('') || '<div style="font-size:9px; color:var(--txt3); padding:4px 0;">No voice macros trained yet.</div>';

    el.innerHTML = `
      <div style="margin-bottom:12px; padding:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(229,193,88,0.2); border-radius:10px;">
        <div class="setting-row">
          <label>USER NAME</label>
          <input type="text" id="train-name-input" value="${t.name || ''}" placeholder="e.g. BOSS" style="width:140px; padding:4px 8px; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.12); color:#fff; font-family:var(--mono); font-size:10px; border-radius:6px;">
        </div>
        <div class="setting-row" style="margin-top:6px;">
          <label>ASSISTANT TONE</label>
          <select id="train-tone-select" style="width:140px; padding:4px; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.12); color:#fff; font-family:var(--mono); font-size:10px; border-radius:6px;">
            <option value="witty" ${t.tone === 'witty' ? 'selected' : ''}>Witty / Clever</option>
            <option value="formal" ${t.tone === 'formal' ? 'selected' : ''}>Formal / Precise</option>
            <option value="friendly" ${t.tone === 'friendly' ? 'selected' : ''}>Friendly / Warm</option>
            <option value="boss" ${t.tone === 'boss' ? 'selected' : ''}>Executive Jarvis</option>
          </select>
        </div>
        <button onclick="saveProfileTraining()" style="margin-top:8px; width:100%; padding:6px; background:rgba(229,193,88,0.15); border:1px solid rgba(229,193,88,0.3); border-radius:6px; color:var(--gold); font-family:var(--mono); font-size:9px; font-weight:700; cursor:pointer;">
          <i class="fa-solid fa-floppy-disk"></i> SAVE PROFILE TRAINING
        </button>
      </div>

      <div style="margin-bottom:12px;">
        <div style="font-family:var(--mono); font-size:9px; color:var(--gold); letter-spacing:1px; margin-bottom:6px; font-weight:700;">
          <i class="fa-solid fa-bolt"></i> CUSTOM VOICE RULES (${(t.rules || []).length})
        </div>
        ${rulesHtml}
      </div>

      <div>
        <div style="font-family:var(--mono); font-size:9px; color:var(--silver); letter-spacing:1px; margin-bottom:6px; font-weight:700;">
          <i class="fa-solid fa-terminal"></i> VOICE MACROS (${(t.macros || []).length})
        </div>
        ${macrosHtml}
      </div>
    `;
  } catch { el.innerHTML = '<div class="panel-empty">Error loading training.</div>'; }
}

async function saveProfileTraining() {
  const name = document.getElementById('train-name-input')?.value.trim();
  const tone = document.getElementById('train-tone-select')?.value;
  try {
    await fetch('/api/training', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'profile', name, tone })
    });
    toast('Profile training saved!', 'ok');
  } catch { toast('Failed to save profile training', 'err'); }
}

async function deleteTrainingItem(type, trigger) {
  try {
    await fetch('/api/training', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, trigger })
    });
    toast(`Deleted ${type}: ${trigger}`, 'info');
    const body = document.getElementById('panel-body-training');
    if (body) loadTrainingPanel(body);
  } catch { toast('Failed to delete item', 'err'); }
}

// ================================================
// PANEL LOADERS
// ================================================
function makeCircularGauge(pct, label) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return `<div class="circular-gauge"><svg viewBox="0 0 52 52"><circle class="track" cx="26" cy="26" r="${r}"/><circle class="fill" cx="26" cy="26" r="${r}" stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/></svg><div class="gauge-label">${pct}%</div></div><div class="stat-lbl">${label}</div>`;
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
    el.innerHTML = `<div class="panel-stat-grid"><div class="panel-stat-box">${makeCircularGauge(cpu, 'CPU')}</div><div class="panel-stat-box">${makeCircularGauge(ram, 'RAM')}</div><div class="panel-stat-box">${makeCircularGauge(disk, 'DISK')}</div><div class="panel-stat-box">${makeCircularGauge(Math.round(bat), 'BATTERY')}</div></div><div class="panel-row"><span class="lbl">UPTIME</span><span class="val">${uptimeH}h ${uptimeM}m</span></div><div class="panel-row"><span class="lbl">HOST</span><span class="val">${d.hostname || '---'}</span></div><div class="panel-row"><span class="lbl">RAM</span><span class="val">${d.ram?.usedMB || 0} / ${d.ram?.totalMB || 0} MB</span></div><div class="panel-row"><span class="lbl">DISK FREE</span><span class="val">${d.disk?.free || '--'}</span></div><div class="panel-row"><span class="lbl">CPU</span><span class="val" style="font-size:8px">${d.cpu?.model || '---'}</span></div>`;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadSystemPanel(el) {
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'system-info' }) });
    const data = await res.json();
    if (!data.success) { el.innerHTML = '<div class="panel-empty">Failed.</div>'; return; }
    const i = data.info || {};
    el.innerHTML = `<div class="panel-row"><span class="lbl">MODEL</span><span class="val">${i.model_name || '---'}</span></div><div class="panel-row"><span class="lbl">ID</span><span class="val">${i.model_identifier || '---'}</span></div><div class="panel-row"><span class="lbl">CPU</span><span class="val">${i.processor_name || '---'}</span></div><div class="panel-row"><span class="lbl">SPEED</span><span class="val">${i.processor_speed || '---'}</span></div><div class="panel-row"><span class="lbl">RAM</span><span class="val">${i.memory || '---'}</span></div><div class="panel-row"><span class="lbl">SERIAL</span><span class="val">${i.serial_number || '---'}</span></div><div class="panel-row"><span class="lbl">OS</span><span class="val">${i.productname || 'macOS'} ${i.productversion || ''}</span></div><div class="panel-row"><span class="lbl">BUILD</span><span class="val">${i.buildversion || '---'}</span></div>`;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadWeatherPanel(el) {
  try {
    const res = await fetch('/api/weather');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Unavailable.</div>'; return; }
    el.innerHTML = `<div class="panel-row"><span class="lbl">CITY</span><span class="val">${d.city}</span></div><div class="panel-row"><span class="lbl">TEMP</span><span class="val">${d.tempC}°C</span></div><div class="panel-row"><span class="lbl">CONDITION</span><span class="val">${d.condition}</span></div><div class="panel-row"><span class="lbl">HUMIDITY</span><span class="val">${d.humidity}%</span></div><div class="panel-row"><span class="lbl">WIND</span><span class="val">${d.windKmH} km/h</span></div><div class="panel-row"><span class="lbl">DAYLIGHT</span><span class="val">${d.isDay ? 'Yes' : 'No'}</span></div>${d.forecast ? d.forecast.map(f => `<div class="panel-row"><span class="lbl">${f.day}</span><span class="val">${f.min}° / ${f.max}°</span></div>`).join('') : ''}`;
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadEmailPanel(el) {
  el.innerHTML = '<div class="panel-empty">Fetching emails...</div>';
  try {
    const res = await fetch('/api/emails');
    const d = await res.json();
    if (!d.success || !d.emails?.length) { el.innerHTML = `<div class="panel-empty">${d.message || 'No emails found.'}</div>`; return; }
    el.innerHTML = d.emails.map(e => `<div class="email-item"><div class="email-from">${escHtml(e.from || 'Unknown')}</div><div class="email-subject">${escHtml(e.subject || '(no subject)')}</div><div class="email-date">${escHtml(e.date || '')}</div></div>`).join('');
  } catch { el.innerHTML = '<div class="panel-empty">Error reading emails.</div>'; }
}

async function loadProcessPanel(el) {
  el.innerHTML = '<div class="panel-empty">Loading...</div>';
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'processes' }) });
    const d = await res.json();
    if (!d.success || !d.processes?.length) { el.innerHTML = '<div class="panel-empty">None found.</div>'; return; }
    el.innerHTML = d.processes.map(p => `<div class="proc-item"><span class="pcpu">${p.cpu}%</span><span style="color:rgba(255,255,255,0.4)">${p.pid}</span><span class="pcmd">${escHtml(p.command)}</span><button class="pk" onclick="killProc('${p.pid}')" title="Kill"><i class="fa-solid fa-xmark"></i></button></div>`).join('');
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function killProc(pid) {
  await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'kill-process', value: pid }) });
  toast(`Process ${pid} killed, BOSS.`, 'ok');
  const body = document.getElementById('panel-body-processes');
  if (body) loadProcessPanel(body);
}

async function loadVaultPanel(el) {
  try {
    const res = await fetch('/api/vault');
    const d = await res.json();
    const items = d.data || [];
    el.innerHTML = items.length ? items.map(v => `<div class="vault-item"><span class="vt">${escHtml(v.text)}</span><span class="vd">${v.date || ''}</span><button class="vx" onclick="deleteVault('${v.id}')"><i class="fa-solid fa-xmark"></i></button></div>`).join('') : '<div class="panel-empty">No memories yet.</div>';
    el.innerHTML += `<div class="panel-input"><input type="text" id="vault-input" placeholder="Save a memory..." onkeydown="if(event.key==='Enter')addVault()"><button onclick="addVault()"><i class="fa-solid fa-plus"></i></button></div>`;
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
    el.innerHTML = `<div class="panel-row"><span class="lbl">CLIPBOARD</span></div><div style="margin-top:6px;padding:10px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;font-family:var(--mono);font-size:9px;color:var(--txt);max-height:160px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;">${escHtml(d.content || '(empty)')}</div><div class="panel-input" style="margin-top:6px;"><input type="text" id="clip-input" placeholder="Write to clipboard..." onkeydown="if(event.key==='Enter')writeClip()"><button onclick="writeClip()"><i class="fa-solid fa-copy"></i></button></div>`;
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
  
  // Build settings HTML
  let html = `
    <div class="setting-row"><label>VOICE</label><select id="voice-select" style="width:140px"><optgroup label="ElevenLabs"><option value="21m00Tcm4TlvDq8ikWAM">Rachel</option><option value="EXAVITQu4vr4xnSDxMaL">Bella</option><option value="MF3mGyEYCl7XYWbV9V6O">Elli</option><option value="pFZP5JQG7iQjIQuC4Bku">Lily</option><option value="AZnzlk1XvdvUeBnXmlld">Domi</option><option value="TxGEqnHWrfWFTfGW9XjX">Josh</option><option value="VR6AewLTigWG4xSOukaG">Arnold</option><option value="yoZ06aMxZJJ28mfd3POQ">Sam</option></optgroup><optgroup label="Web Speech (Free)"><option value="web-samantha">Samantha (macOS)</option><option value="web-karen">Karen (macOS)</option><option value="web-moira">Moira (macOS)</option><option value="web-tessa">Tessa (macOS)</option></optgroup></select></div>
    <div class="setting-row"><label>SPEECH RATE</label><input type="range" id="speech-rate" min="0.5" max="2" step="0.1" value="1.0" style="width:100px"></div>
    <div class="setting-row"><label>SPEECH PITCH</label><input type="range" id="speech-pitch" min="0.5" max="2" step="0.1" value="1.0" style="width:100px"></div>
    <div class="setting-row"><label>CONTINUOUS LISTEN</label><input type="checkbox" id="cont-listen" ${mem.continuousListen ? 'checked' : ''}></div>
    <div class="setting-row"><label>YOUR NAME</label><input type="text" id="name-input" value="${mem.name || ''}" placeholder="Tell me your name" style="width:130px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
  `;
  
  // Dark mode toggle
  const isDark = mem.darkMode !== false; // default dark
  html += `<div class="setting-row"><label>DARK MODE</label><input type="checkbox" id="dark-mode-toggle" ${isDark ? 'checked' : ''}></div>`;
  
  // Location settings
  html += `
    <div style="border-top:1px solid rgba(255,255,255,0.06); margin:8px 0; padding-top:8px;">
      <div style="font-family:var(--mono); font-size:8px; color:var(--txt3); letter-spacing:1px; margin-bottom:8px;">LOCATION</div>
      <div class="setting-row"><label>CITY NAME</label><input type="text" id="city-name-input" placeholder="New Delhi, IN" style="width:130px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>LATITUDE</label><input type="number" id="lat-input" step="0.0001" style="width:80px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>LONGITUDE</label><input type="number" id="lon-input" step="0.0001" style="width:80px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label></label><button id="save-location-btn" style="padding:4px 10px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:6px;color:var(--txt2);font-family:var(--mono);font-size:9px;cursor:pointer;">Save Location</button></div>
      <div class="setting-row"><label></label><button id="detect-location-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Auto-detect</button></div>
    </div>
  `;
  
  // API Keys section
  html += `
    <div style="border-top:1px solid rgba(255,255,255,0.06); margin:8px 0; padding-top:8px;">
      <div style="font-family:var(--mono); font-size:8px; color:var(--txt3); letter-spacing:1px; margin-bottom:8px;">API KEYS</div>
      <div id="api-keys-list" style="font-family:var(--mono); font-size:9px; color:var(--txt2);">Loading...</div>
      <div class="setting-row"><label></label><button id="show-keys-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Show Key Details</button></div>
    </div>
  `;
  
  // Permissions section
  html += `
    <div style="border-top:1px solid rgba(255,255,255,0.06); margin:8px 0; padding-top:8px;">
      <div style="font-family:var(--mono); font-size:8px; color:var(--txt3); letter-spacing:1px; margin-bottom:8px;">SYSTEM</div>
      <div class="setting-row"><label></label><button id="check-perms-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Check Permissions</button></div>
    </div>
  `;
  
  el.innerHTML = html;
  
  // Event listeners
  document.getElementById('voice-select').addEventListener('change', (e) => { mem.voiceId = e.target.value; saveOfflineMemory(mem); toast('Voice updated, BOSS.', 'ok'); });
  document.getElementById('speech-rate').addEventListener('input', (e) => { mem.speechRate = parseFloat(e.target.value); saveOfflineMemory(mem); });
  document.getElementById('speech-pitch').addEventListener('input', (e) => { mem.speechPitch = parseFloat(e.target.value); saveOfflineMemory(mem); });
  document.getElementById('cont-listen').addEventListener('change', (e) => { mem.continuousListen = e.target.checked; saveOfflineMemory(mem); });
  document.getElementById('name-input').addEventListener('change', (e) => { mem.name = e.target.value.trim(); saveOfflineMemory(mem); toast(`Name set to ${mem.name}, BOSS.`, 'ok'); });
  
  // Dark mode toggle
  document.getElementById('dark-mode-toggle').addEventListener('change', (e) => {
    mem.darkMode = e.target.checked;
    saveOfflineMemory(mem);
    applyDarkMode(e.target.checked);
    toast(`Dark mode ${e.target.checked ? 'enabled' : 'disabled'}`, 'ok');
  });
  
  // Load current location settings
  fetch('/api/settings').then(r => r.json()).then(d => {
    if (d.success && d.settings) {
      document.getElementById('city-name-input').value = d.settings.cityName || '';
      document.getElementById('lat-input').value = d.settings.latitude || '';
      document.getElementById('lon-input').value = d.settings.longitude || '';
    }
  }).catch(() => {});
  
  // Save location button
  document.getElementById('save-location-btn').addEventListener('click', async () => {
    const cityName = document.getElementById('city-name-input').value.trim();
    const lat = parseFloat(document.getElementById('lat-input').value);
    const lon = parseFloat(document.getElementById('lon-input').value);
    if (isNaN(lat) || isNaN(lon)) {
      toast('Invalid coordinates', 'err');
      return;
    }
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latitude: lat, longitude: lon, cityName: cityName || `${lat}, ${lon}` })
    });
    toast('Location saved, BOSS.', 'ok');
  });
  
  // Auto-detect location button
  document.getElementById('detect-location-btn').addEventListener('click', () => {
    if (!navigator.geolocation) {
      toast('Geolocation not supported', 'err');
      return;
    }
    toast('Detecting location...', 'info');
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const { latitude, longitude } = pos.coords;
      // Reverse geocode
      try {
        const res = await fetch(`/api/reverse-geocode?lat=${latitude}&lon=${longitude}`);
        const d = await res.json();
        const cityName = d.success ? d.cityName : `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ latitude, longitude, cityName })
        });
        document.getElementById('city-name-input').value = cityName;
        document.getElementById('lat-input').value = latitude.toFixed(4);
        document.getElementById('lon-input').value = longitude.toFixed(4);
        toast(`Location set to ${cityName}`, 'ok');
      } catch {
        toast('Geocoding failed', 'err');
      }
    }, () => {
      toast('Location access denied', 'err');
    });
  });
  
  // API keys details button
  document.getElementById('show-keys-btn').addEventListener('click', () => showKeyDetails());
  
  // Permissions check button
  document.getElementById('check-perms-btn').addEventListener('click', async () => {
    try {
      const res = await fetch('/api/permissions-check');
      const d = await res.json();
      if (d.platform !== 'darwin') {
        toast('Permissions check only available on macOS', 'info');
        return;
      }
      const allGranted = Object.values(d.permissions).every(p => p.status === 'granted');
      if (allGranted) {
        toast('All permissions granted!', 'ok');
      } else {
        const missing = Object.entries(d.permissions).filter(([_, v]) => v.status === 'missing').map(([k]) => k);
        toast(`Missing: ${missing.join(', ')}`, 'err');
        showPermissionsModal(Object.entries(d.permissions).filter(([_, v]) => v.status === 'missing').map(([name, info]) => ({ name, ...info })));
      }
    } catch {
      toast('Failed to check permissions', 'err');
    }
  });
  
  // Load API keys status
  fetch('/api/gemini-keys').then(r => r.json()).then(d => {
    const listEl = document.getElementById('api-keys-list');
    if (!listEl) return;
    if (d.totalKeys === 0) {
      listEl.innerHTML = '<span style="color:var(--txt3)">No keys configured in .env</span>';
      return;
    }
    listEl.innerHTML = d.keys.map((k, i) => `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.03);">
        <span style="color:${k.active ? 'var(--txt)' : 'var(--pink)'}">${k.masked}</span>
        <span style="font-size:8px; color:${k.active ? 'rgba(255,255,255,0.4)' : 'var(--pink)'}">${k.active ? 'ACTIVE' : 'RATE LIMITED'} | ${k.requestsToday} req</span>
      </div>
    `).join('');
  }).catch(() => {});
  
  // Apply saved values
  if (mem.voiceId) document.getElementById('voice-select').value = mem.voiceId;
  if (mem.speechRate) document.getElementById('speech-rate').value = mem.speechRate;
  if (mem.speechPitch) document.getElementById('speech-pitch').value = mem.speechPitch;
  
  // Apply dark mode
  applyDarkMode(isDark);
}

function applyDarkMode(isDark) {
  const root = document.documentElement;
  if (isDark) {
    document.body.classList.remove('light-mode');
    root.style.setProperty('--bg', '#000000');
    root.style.setProperty('--txt', 'rgba(255,255,255,0.92)');
    root.style.setProperty('--txt2', 'rgba(255,255,255,0.60)');
    root.style.setProperty('--txt3', 'rgba(255,255,255,0.40)');
  } else {
    document.body.classList.add('light-mode');
    root.style.setProperty('--bg', '#f5f5f7');
    root.style.setProperty('--txt', 'rgba(0,0,0,0.88)');
    root.style.setProperty('--txt2', 'rgba(0,0,0,0.55)');
    root.style.setProperty('--txt3', 'rgba(0,0,0,0.35)');
    root.style.setProperty('--surface', 'rgba(0,0,0,0.04)');
    root.style.setProperty('--glass-border', 'rgba(0,0,0,0.08)');
  }
}

// ================================================
// FILE EXPLORER PANEL
// ================================================
let currentFilePath = '';

async function loadFilesPanel(el) {
  currentFilePath = '';
  el.innerHTML = '<div class="panel-empty">Loading...</div>';
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'list-directory', value: '' }) });
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Error listing files.</div>'; return; }
    renderFilesList(el, d.files || [], '');
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

function renderFilesList(el, files, path) {
  currentFilePath = path;
  const items = files.map(f => {
    const isDir = !f.includes('.');
    const icon = isDir ? 'fa-folder' : 'fa-file';
    return `<div class="vault-item" style="cursor:pointer;" onclick="${isDir ? `navigateDir('${path ? path + '/' : ''}${f}')` : `openFile('${path ? path + '/' : ''}${f}')`}"><i class="fa-solid ${icon}" style="color:var(--txt3);font-size:10px;margin-right:6px;"></i><span class="vt">${escHtml(f)}</span></div>`;
  }).join('');
  const backBtn = path ? `<div class="vault-item" style="cursor:pointer;color:var(--txt3);" onclick="navigateDir('${path.split('/').slice(0, -1).join('/')}')"><i class="fa-solid fa-arrow-left" style="font-size:10px;margin-right:6px;"></i><span class="vt">Back</span></div>` : '';
  el.innerHTML = `<div style="font-family:var(--mono);font-size:8px;color:var(--txt3);padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);margin-bottom:4px;">${escHtml(path || '~/Desktop')}</div>${backBtn}${items || '<div class="panel-empty">Empty folder</div>'}`;
}

async function navigateDir(path) {
  const body = document.getElementById('panel-body-files');
  if (!body) return;
  body.innerHTML = '<div class="panel-empty">Loading...</div>';
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'list-directory', value: path || '' }) });
    const d = await res.json();
    renderFilesList(body, d.files || [], path);
  } catch { body.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

function openFile(path) {
  fetch('/api/open-url', { method: 'GET' }).catch(() => {});
  toast(`Opening ${path.split('/').pop()}...`, 'info');
  fetch(`/api/control`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'list-directory', value: path }) });
}

// ================================================
// NOTES / TODO PANEL
// ================================================
const NOTES_KEY = 'jenny_notes';

function loadNotesPanel(el) {
  const notes = loadNotes();
  el.innerHTML = `
    <div class="panel-input" style="border-top:none;border-bottom:1px solid rgba(255,255,255,0.03);padding-bottom:8px;">
      <input type="text" id="note-input" placeholder="Add a note or TODO..." onkeydown="if(event.key==='Enter')addNote()">
      <button onclick="addNote()"><i class="fa-solid fa-plus"></i></button>
    </div>
    <div id="notes-list">${renderNotes(notes)}</div>
  `;
}

function loadNotes() {
  try { return JSON.parse(localStorage.getItem(NOTES_KEY) || '[]'); } catch { return []; }
}

function saveNotes(notes) {
  localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
}

function renderNotes(notes) {
  if (!notes.length) return '<div class="panel-empty">No notes yet.</div>';
  return notes.map((n, i) => `
    <div class="vault-item">
      <span class="vt" style="display:flex;align-items:center;gap:6px;">
        <input type="checkbox" ${n.done ? 'checked' : ''} onchange="toggleNote(${i})" style="width:12px;height:12px;accent-color:var(--txt2);">
        <span style="${n.done ? 'text-decoration:line-through;color:var(--txt3);' : ''}">${escHtml(n.text)}</span>
      </span>
      <button class="vx" onclick="deleteNote(${i})"><i class="fa-solid fa-xmark"></i></button>
    </div>
  `).join('');
}

function addNote() {
  const input = document.getElementById('note-input');
  if (!input || !input.value.trim()) return;
  const notes = loadNotes();
  notes.unshift({ text: input.value.trim(), done: false, date: new Date().toLocaleDateString() });
  saveNotes(notes);
  input.value = '';
  const list = document.getElementById('notes-list');
  if (list) list.innerHTML = renderNotes(notes);
  toast('Note added, BOSS.', 'ok');
}

function toggleNote(idx) {
  const notes = loadNotes();
  if (notes[idx]) { notes[idx].done = !notes[idx].done; saveNotes(notes); }
  const list = document.getElementById('notes-list');
  if (list) list.innerHTML = renderNotes(notes);
}

function deleteNote(idx) {
  const notes = loadNotes();
  notes.splice(idx, 1);
  saveNotes(notes);
  const list = document.getElementById('notes-list');
  if (list) list.innerHTML = renderNotes(notes);
  toast('Note deleted.', 'ok');
}

function loadCommandsPanel(el) {
  el.innerHTML = `
<h3 style="font-family:var(--orbitron);font-size:12px;color:var(--gold);letter-spacing:2px;margin:0 0 12px 0;text-transform:uppercase;">System Control</h3>
<div class="cmd-ref-item"><div class="cc">open notepad / calculator / paint / chrome / edge / vscode / discord / spotify / word / excel / powerpoint</div><div class="cd">Launch any app</div></div>
<div class="cmd-ref-item"><div class="cc">close notepad / chrome / any app</div><div class="cd">Kill any running app</div></div>
<div class="cmd-ref-item"><div class="cc">lock pc / lock screen</div><div class="cd">Lock Windows screen</div></div>
<div class="cmd-ref-item"><div class="cc">take screenshot / screenshot</div><div class="cd">Save screenshot to Desktop</div></div>
<div class="cmd-ref-item"><div class="cc">volume 50 / volume up / volume down / mute / unmute</div><div class="cd">Audio volume controls</div></div>
<div class="cmd-ref-item"><div class="cc">shutdown / restart / sleep</div><div class="cd">Power controls</div></div>
<div class="cmd-ref-item"><div class="cc">empty trash / empty recycle bin</div><div class="cd">Clear recycle bin</div></div>
<div class="cmd-ref-item"><div class="cc">minimize all / show desktop</div><div class="cd">Minimize all windows</div></div>
<div class="cmd-ref-item"><div class="cc">open terminal / open cmd</div><div class="cd">Open terminal or command prompt</div></div>

<h3 style="font-family:var(--orbitron);font-size:12px;color:var(--gold);letter-spacing:2px;margin:16px 0 12px 0;text-transform:uppercase;">File & Folder Access</h3>
<div class="cmd-ref-item"><div class="cc">open desktop / downloads / documents / pictures / music / videos</div><div class="cd">Open common folders</div></div>
<div class="cmd-ref-item"><div class="cc">browse C:\path\to\folder / open folder [path]</div><div class="cd">Open any folder by path</div></div>
<div class="cmd-ref-item"><div class="cc">open chrome bookmarks / show bookmarks</div><div class="cd">Access Chrome bookmarks</div></div>

<h3 style="font-family:var(--orbitron);font-size:12px;color:var(--gold);letter-spacing:2px;margin:16px 0 12px 0;text-transform:uppercase;">Web & Browser</h3>
<div class="cmd-ref-item"><div class="cc">open google.com / open youtube.com / open [any website]</div><div class="cd">Open website in Chrome</div></div>
<div class="cmd-ref-item"><div class="cc">news / headlines / top news</div><div class="cd">Latest news headlines</div></div>
<div class="cmd-ref-item"><div class="cc">bitcoin price / crypto prices</div><div class="cd">Live crypto prices</div></div>

<h3 style="font-family:var(--orbitron);font-size:12px;color:var(--gold);letter-spacing:2px;margin:16px 0 12px 0;text-transform:uppercase;">System Info</h3>
<div class="cmd-ref-item"><div class="cc">cpu usage / cpu info</div><div class="cd">Processor usage & model</div></div>
<div class="cmd-ref-item"><div class="cc">ram usage / memory info</div><div class="cd">RAM usage & total</div></div>
<div class="cmd-ref-item"><div class="cc">battery level / battery</div><div class="cd">Battery percentage & charging</div></div>
<div class="cmd-ref-item"><div class="cc">disk usage / storage / free space</div><div class="cd">Disk space info</div></div>
<div class="cmd-ref-item"><div class="cc">system info / about my pc / my system</div><div class="cd">Full system information</div></div>
<div class="cmd-ref-item"><div class="cc">uptime / how long has pc been on</div><div class="cd">System uptime</div></div>
<div class="cmd-ref-item"><div class="cc">wifi / network / internet status</div><div class="cd">Network & WiFi info</div></div>
<div class="cmd-ref-item"><div class="cc">hostname / computer name</div><div class="cd">PC name</div></div>
<div class="cmd-ref-item"><div class="cc">running processes / task manager</div><div class="cd">List running processes</div></div>

<h3 style="font-family:var(--orbitron);font-size:12px;color:var(--gold);letter-spacing:2px;margin:16px 0 12px 0;text-transform:uppercase;">Knowledge & Chat</h3>
<div class="cmd-ref-item"><div class="cc">what is AI / python / CPU / RAM / WiFi / encryption / blockchain</div><div class="cd">50+ offline tech topics</div></div>
<div class="cmd-ref-item"><div class="cc">what time / today's date / what day / what month / what year</div><div class="cd">Date & time queries</div></div>
<div class="cmd-ref-item"><div class="cc">what is 42 * 7 / calculate 100 + 200 / math</div><div class="cd">Quick math calculator</div></div>
<div class="cmd-ref-item"><div class="cc">convert 100 F to C / convert 50 C to F</div><div class="cd">Temperature conversion</div></div>
<div class="cmd-ref-item"><div class="cc">25% of 200 / what is 30 percent of 150</div><div class="cd">Percentage calculator</div></div>
<div class="cmd-ref-item"><div class="cc">weather / temperature / forecast</div><div class="cd">Live weather info</div></div>
<div class="cmd-ref-item"><div class="cc">tell me a joke / something funny</div><div class="cd">Random jokes</div></div>
<div class="cmd-ref-item"><div class="cc">give me a quote / inspire me / motivational quote</div><div class="cd">Inspirational quotes</div></div>
<div class="cmd-ref-item"><div class="cc">tell me a fact / fun fact / random fact</div><div class="cd">Interesting facts</div></div>

<h3 style="font-family:var(--orbitron);font-size:12px;color:var(--gold);letter-spacing:2px;margin:16px 0 12px 0;text-transform:uppercase;">Utility</h3>
<div class="cmd-ref-item"><div class="cc">set a timer for 5 minutes / remind me in 30 seconds</div><div class="cd">Timer with alert</div></div>
<div class="cmd-ref-item"><div class="cc">remember [fact] / save to vault [note]</div><div class="cd">Save to memory vault</div></div>
<div class="cmd-ref-item"><div class="cc">briefing / daily briefing</div><div class="cd">Full system overview</div></div>
<div class="cmd-ref-item"><div class="cc">who are you / your name / what can you do / capabilities</div><div class="cd">About JENNY</div></div>
<div class="cmd-ref-item"><div class="cc">who made you / your creator</div><div class="cd">Meet the creator</div></div>
<div class="cmd-ref-item"><div class="cc">hello / hi / hey / how are you</div><div class="cd">Greetings & small talk</div></div>
<div class="cmd-ref-item"><div class="cc">Keyboard: Esc = close panels, Cmd+K = focus input</div><div class="cd">Keyboard shortcuts</div></div>`;
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
    if (cmd.response === '__CHECK_PERMISSIONS__') {
      checkPermissions();
      addAIMessage('Checking macOS permissions, BOSS. I\'ll show you a guide if anything is missing.');
      speak('Checking your system permissions now.');
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
      if (data.reply.command?.action === 'vault-save') { await fetch('/api/vault', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: data.reply.command.value?.text || '' }) }); toast('Saved to vault, BOSS.', 'ok'); }
      else if (data.reply.command?.action === 'open-chrome-bookmarks') {
        try {
          const bmr = await fetch('/api/chrome-bookmarks');
          const bmd = await bmr.json();
          if (bmd.success && bmd.bookmarks && bmd.bookmarks.length > 0) {
            let bmText = `**Your Chrome Bookmarks** (${bmd.total} total):\n\n`;
            bmd.bookmarks.slice(0, 15).forEach((b, i) => { bmText += `${i+1}. **${b.name}** — ${b.url}\n`; });
            if (bmd.total > 15) bmText += `\n_...and ${bmd.total - 15} more._`;
            addAIMessage(bmText);
          } else { addAIMessage('No Chrome bookmarks found, Boss.'); }
        } catch(e) { addAIMessage('Could not load Chrome bookmarks, Boss.'); }
      }
      else if (data.reply.command?.action === 'open-folder') {
        const folderPath = data.reply.command.value;
        window.open(`/api/open-folder?path=${encodeURIComponent(folderPath)}`, '_blank');
        await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data.reply.command) });
      }
      else if (data.reply.command?.action === 'open-chrome') {
        const url = data.reply.command.value;
        await fetch(`/api/open-chrome?url=${encodeURIComponent(url)}`);
      }
      else if (data.reply.command) { await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data.reply.command) }); }
      speak(data.reply.speech || data.reply.text);
    } else { addAIMessage('Something went wrong, BOSS. Please try again.'); setOrbState('idle'); }
  } catch { removeTyping(); addAIMessage('Connection error, BOSS. Please try again.'); setOrbState('idle'); }
}

// ================================================
// VOICE — TTS (Optimized)
// ================================================
let _cachedVoice = null;
let _cachedMode = null;

function speak(text, onEndCallback) {
  if (!text) return;
  const clean = text.replace(/[*_#`~]/g, '').replace(/https?:\/\/\S+/g, '').replace(/\s+/g, ' ').trim();
  if (!clean) return;
  const spokenText = clean.slice(0, 500);
  if (typeof setOrbState === 'function') setOrbState('speaking');
  if ('speechSynthesis' in window) {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(spokenText);
    if (_cachedMode === currentMode && _cachedVoice) {
      u.voice = _cachedVoice;
    } else {
      const voices = speechSynthesis.getVoices();
      if (currentMode === 'ultron') {
        u.rate = 0.85; u.pitch = 0.5;
        _cachedVoice = voices.find(v => /david/i.test(v.name)) || voices.find(v => /daniel|mark|james/i.test(v.name)) || voices.find(v => v.lang.startsWith('en'));
      } else if (currentMode === 'jarvis') {
        u.rate = 1.0; u.pitch = 0.85;
        _cachedVoice = voices.find(v => /daniel|george|gb-en/i.test(v.name)) || voices.find(v => v.lang.startsWith('en'));
      } else {
        u.rate = 1.05; u.pitch = 1.15;
        var femaleRe = /zira|hazel|aria|samantha|jenny|natasha|michelle|susan|ava|emma|female|woman|girl/i;
        _cachedVoice = voices.find(v => femaleRe.test(v.name) && /en/i.test(v.lang)) ||
                       voices.find(v => femaleRe.test(v.name)) ||
                       voices.find(v => /zira|jenny|aria/i.test(v.name)) ||
                       voices.find(v => /en/i.test(v.lang) && !/david|mark|guy|daniel|george|james|richard|eric/i.test(v.name));
      }
      _cachedMode = currentMode;
      if (_cachedVoice) u.voice = _cachedVoice;
    }
    if (currentMode === 'ultron') { u.rate = 0.85; u.pitch = 0.5; }
    u.onend = () => { if (typeof setOrbState === 'function') setOrbState('idle'); if (onEndCallback) onEndCallback(); };
    u.onerror = () => { speakServer(spokenText); if (onEndCallback) onEndCallback(); };
    speechSynthesis.speak(u);
    return;
  }
  speakServer(spokenText);
  if (onEndCallback) setTimeout(onEndCallback, 1000);
}

function speakServer(text) {
  if (window.currentSpeechAudio) { window.currentSpeechAudio.pause(); window.currentSpeechAudio = null; }
  window.currentSpeechAudio = new Audio(`/api/speak?text=${encodeURIComponent(text)}&t=${Date.now()}`);
  if (typeof setOrbState === 'function') setOrbState('speaking');
  window.currentSpeechAudio.play().catch(() => {
    fetch('/api/speak/fallback', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({text}) }).catch(()=>{});
  });
  window.currentSpeechAudio.onended = () => { if (typeof setOrbState === 'function') setOrbState('idle'); window.currentSpeechAudio = null; };
  window.currentSpeechAudio.onerror = () => { if (typeof setOrbState === 'function') setOrbState('idle'); window.currentSpeechAudio = null; };
}

function speakWeb(text) {
  speak(text);
}

// ================================================
// SPEECH RECOGNITION
// ================================================
let recognition = null;
let isListening = false;
let micStream = null;
const orbClick = document.getElementById('orb-click');
let dictationTranscript = '';
let dictationTimeout = null;

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.continuous = true;
  r.interimResults = true;
  r.lang = 'en-US';
  r.maxAlternatives = 1;

  r.onresult = (e) => {
    let interim = '';
    let final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) final += t;
      else interim += t;
    }
    if (interim) {
      dictationTranscript = final || interim;
      const input = document.getElementById('chat-input');
      if (input) input.value = dictationTranscript + '...';
    }
    if (final) {
      let cleaned = final.trim();
      const lower = cleaned.toLowerCase();

      // Voice dictation controls
      if (lower === 'clear input' || lower === 'clear text') {
        dictationTranscript = '';
        const input = document.getElementById('chat-input');
        if (input) input.value = '';
        toast('Dictation input cleared', 'info');
        return;
      }
      if (lower === 'send message' || lower === 'submit' || lower === 'send text') {
        if (dictationTranscript.trim()) {
          sendMessage(dictationTranscript.trim());
          dictationTranscript = '';
        }
        stopListening();
        return;
      }
      if (lower === 'read back' || lower === 'speak text') {
        const input = document.getElementById('chat-input');
        if (input && input.value) speak(input.value);
        return;
      }

      // Voice formatting replacements
      cleaned = cleaned
        .replace(/\bnew line\b/gi, '\n')
        .replace(/\bcomma\b/gi, ',')
        .replace(/\bperiod\b|\bfull stop\b/gi, '.')
        .replace(/\bquestion mark\b/gi, '?')
        .replace(/\bexclamation mark\b|\bexclamation point\b/gi, '!');

      dictationTranscript = (dictationTranscript + ' ' + cleaned).trim();
      const input = document.getElementById('chat-input');
      if (input) {
        input.value = dictationTranscript;
        const words = input.value.trim().split(/\s+/).length;
        const wordEl = document.getElementById('word-count');
        if (wordEl) wordEl.textContent = words + ' word' + (words !== 1 ? 's' : '');
      }

      clearTimeout(dictationTimeout);
      dictationTimeout = setTimeout(() => {
        if (dictationTranscript.trim()) {
          sendMessage(dictationTranscript.trim());
          dictationTranscript = '';
        }
        stopListening();
      }, 1800);
    }
  };

  r.onerror = (e) => {
    console.warn('[JENNY] Speech recognition error:', e.error);
    if (e.error === 'not-allowed') { toast('Mic access denied. Allow it in browser settings.', 'err'); stopListening(); }
    else if (e.error === 'no-speech') { /* ignore, keep listening */ }
    else if (e.error === 'network') { toast('Speech recognition needs internet.', 'err'); }
  };

  r.onend = () => {
    if (isListening && dictationTranscript.trim()) {
      sendMessage(dictationTranscript.trim());
      dictationTranscript = '';
    }
    stopListening();
  };

  return r;
}

async function startListening() {
  if (!recognition) recognition = initRecognition();
  if (!recognition) { toast('Speech recognition not supported', 'err'); return; }
  isListening = true;
  dictationTranscript = '';
  orbClick.classList.add('active');
  setOrbState('listening');
  sfx.confirm();
  if (window.currentSpeechAudio) {
    window.currentSpeechAudio.pause();
    window.currentSpeechAudio = null;
  }
  fetch('/api/speak/stop', { method: 'POST' }).catch(() => {});
  try { micStream = await navigator.mediaDevices.getUserMedia({ audio: true }); startSpeechWaves(micStream); } catch {}
  try { recognition.start(); } catch {}
}

function stopListening() {
  isListening = false;
  orbClick.classList.remove('active');
  if (orbState === 'listening') setOrbState('idle');
  stopSpeechWaves();
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  try { recognition?.stop(); } catch {}
}

orbClick.addEventListener('click', () => { isListening ? stopListening() : startListening(); });

// Bind Media HUD Buttons
document.getElementById('media-btn-prev')?.addEventListener('click', () => {
  sfx.click();
  fetch('/api/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'media', value: 'previous' })
  }).catch(() => {});
});
document.getElementById('media-btn-play')?.addEventListener('click', () => {
  sfx.click();
  fetch('/api/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'media', value: 'playpause' })
  }).catch(() => {});
});
document.getElementById('media-btn-next')?.addEventListener('click', () => {
  sfx.click();
  fetch('/api/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'media', value: 'next' })
  }).catch(() => {});
});

async function triggerSystemControl(action, value = '') {
  sfx.click();
  try {
    const res = await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, value })
    });
    const d = await res.json();
    if (d.success) {
      toast(d.message || `Executed control '${action}'`, 'ok');
      if (action === 'theme-toggle') {
        document.body.classList.toggle('light-mode');
      }
    } else {
      toast(d.error || 'Control action failed.', 'err');
    }
  } catch (err) {
    console.error('System control trigger failed:', err);
    toast('Server connection failed.', 'err');
  }
}

if ('speechSynthesis' in window) { window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices(); }

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
// APP VERSION
// ================================================
(async function loadVersion() {
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    const verEl = document.getElementById('app-version');
    if (verEl) verEl.textContent = 'v1.0';
  } catch {}
})();

// ================================================
// KEYBOARD SHORTCUTS
// ================================================
document.addEventListener('keydown', (e) => {
  // Escape: close all open panels, or blur input
  if (e.key === 'Escape') {
    const permModal = document.getElementById('permissions-modal');
    if (permModal) { permModal.remove(); return; }
    if (openPanels.size > 0) {
      const last = [...openPanels].pop();
      closePanel(last);
    } else {
      chatInput.blur();
    }
    return;
  }

  // Ctrl+K or Cmd+K: focus input (quick command access)
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    chatInput.focus();
    chatInput.select();
    return;
  }

  // Alt+N: open/close notifications or cycle panels
  if (e.altKey && e.key === 'n') {
    e.preventDefault();
    openPanel('vault');
    return;
  }
});

// ================================================
// CHAT PERSISTENCE
// ================================================
const CHAT_STORAGE_KEY = 'jenny_chat_history';
const CHAT_MAX_STORED = 100;

function saveChatHistory() {
  const msgs = document.getElementById('msgs');
  if (!msgs) return;
  const entries = [];
  msgs.querySelectorAll('.msg').forEach(m => {
    const isUser = m.classList.contains('msg-user');
    const bubble = m.querySelector('.msg-bubble');
    const time = m.querySelector('.msg-time');
    if (bubble) {
      entries.push({
        role: isUser ? 'user' : 'ai',
        text: bubble.textContent,
        time: time ? time.textContent : ''
      });
    }
  });
  try {
    const trimmed = entries.slice(-CHAT_MAX_STORED);
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(trimmed));
  } catch {}
}

function restoreChatHistory() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return;
    const entries = JSON.parse(raw);
    if (!entries.length) return;
    hideWelcomeScreen();
    entries.forEach(e => {
      if (e.role === 'user') addUserMessage(e.text);
      else addAIMessage(e.text);
    });
  } catch {}
}

// ================================================
// CONFIRMATION DIALOGS
// ================================================
function confirmAction(title, message, onConfirm) {
  const existing = document.getElementById('confirm-modal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'confirm-modal';
  modal.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.7);backdrop-filter:blur(10px);';
  modal.innerHTML = `
    <div style="width:340px;max-width:90vw;background:rgba(20,20,25,0.95);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:24px;box-shadow:0 24px 80px rgba(0,0,0,0.6);">
      <div style="font-family:var(--mono);font-size:11px;font-weight:700;color:var(--txt);letter-spacing:1px;margin-bottom:8px;">${escHtml(title)}</div>
      <div style="font-size:11px;color:var(--txt2);margin-bottom:16px;line-height:1.5;">${escHtml(message)}</div>
      <div style="display:flex;gap:8px;">
        <button id="confirm-yes" style="flex:1;padding:8px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);border-radius:8px;color:var(--txt);font-family:var(--mono);font-size:10px;cursor:pointer;">Confirm</button>
        <button id="confirm-no" style="flex:1;padding:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;color:var(--txt2);font-family:var(--mono);font-size:10px;cursor:pointer;">Cancel</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  sfx.error();
  modal.querySelector('#confirm-yes').addEventListener('click', () => { modal.remove(); onConfirm(); });
  modal.querySelector('#confirm-no').addEventListener('click', () => modal.remove());
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}

// ================================================
// PROCESS PANEL AUTO-REFRESH
// ================================================
let processRefreshInterval = null;

function startProcessRefresh() {
  if (processRefreshInterval) return;
  processRefreshInterval = setInterval(() => {
    const body = document.getElementById('panel-body-processes');
    if (body && openPanels.has('processes')) loadProcessPanel(body);
    else { clearInterval(processRefreshInterval); processRefreshInterval = null; }
  }, 5000);
}

// ================================================
// CONNECTION STATUS MONITOR
// ================================================
let lastConnectionOk = true;

function startConnectionMonitor() {
  setInterval(async () => {
    try {
      const res = await fetch('/api/system-status?t=' + Date.now());
      const ok = res.ok;
      if (ok !== lastConnectionOk) {
        lastConnectionOk = ok;
        const dot = document.getElementById('status-dot');
        const stext = document.getElementById('status-text');
        if (dot) dot.style.background = ok ? 'rgba(255,255,255,0.6)' : 'rgba(255,0,106,0.6)';
        if (stext) stext.textContent = ok ? 'online' : 'disconnected';
        if (!ok) toast('Connection lost. Reconnecting...', 'err');
        else toast('Connection restored.', 'ok');
      }
    } catch {
      if (lastConnectionOk) {
        lastConnectionOk = false;
        const dot = document.getElementById('status-dot');
        const stext = document.getElementById('status-text');
        if (dot) dot.style.background = 'rgba(255,0,106,0.6)';
        if (stext) stext.textContent = 'disconnected';
      }
    }
  }, 10000);
}

// ================================================
// HOOK INTO EXISTING SYSTEMS
// ================================================

// Save chat on every new message
const _origAddUserMessage = addUserMessage;
const _origAddAIMessage = addAIMessage;
addUserMessage = function(text) { _origAddUserMessage(text); setTimeout(saveChatHistory, 100); };
addAIMessage = function(text) { const el = _origAddAIMessage(text); setTimeout(saveChatHistory, 100); return el; };

// Start process refresh when processes panel opens
const _origOpenPanel = openPanel;
openPanel = function(name) {
  _origOpenPanel(name);
  if (name === 'processes') startProcessRefresh();
};

// Add confirmation for dangerous commands
const _origSendMessage = sendMessage;
sendMessage = async function(text) {
  const t = text.toLowerCase().trim();
  if (/\bshutdown\b/.test(t) || /\bshut down\b/.test(t)) {
    confirmAction('SHUTDOWN', 'Are you sure you want to shut down your Mac?', () => _origSendMessage(text));
    return;
  }
  if (/\brestart\b/.test(t)) {
    confirmAction('RESTART', 'Are you sure you want to restart your Mac?', () => _origSendMessage(text));
    return;
  }
  if (/\bkill\b/.test(t) && /\bprocess\b/.test(t)) {
    confirmAction('KILL PROCESS', 'Kill the specified process?', () => _origSendMessage(text));
    return;
  }
  _origSendMessage(text);
};

// ================================================
// PHONE REMOTE ACCESS LINK MANAGER
// ================================================
let currentPendingDevice = null;
let currentLinkedDeviceId = null;
let phoneLinkPollInterval = null;

function copyTextFromElement(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText || el.textContent).then(() => {
    toast('Copied link to clipboard, BOSS.', 'ok');
  });
}

async function initPhoneLinkManager() {
  const qrImg = document.getElementById('phone-qr-img');
  const urlPub = document.getElementById('phone-url-pub');
  const urlLoc = document.getElementById('phone-url-loc');

  try {
    const rStatus = await fetch('/api/remote-status');
    const dStatus = await rStatus.json();
    const pubUrl = dStatus.tunnelUrl ? `${dStatus.tunnelUrl}/mobile` : 'Retrieving...';
    urlPub.textContent = pubUrl;
    
    const rIp = await fetch('/api/local-ip');
    const dIp = await rIp.json();
    const locUrl = dIp.mobileUrl || 'Retrieving...';
    urlLoc.textContent = locUrl;

    const targetUrl = dStatus.tunnelUrl ? pubUrl : locUrl;
    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&color=d08400&bgcolor=ffffff&data=${encodeURIComponent(targetUrl)}`;
    qrImg.onerror = () => {
      qrImg.style.display = 'none';
      qrImg.parentElement.innerHTML = '<div style="color:rgba(255,215,0,0.4);font-family:var(--mono);font-size:11px;padding:40px;text-align:center;">QR Code unavailable offline.<br>Open <strong style="color:rgba(255,215,0,0.7)">' + locUrl + '</strong> on your phone.</div>';
    };
  } catch (e) {
    console.error('[PhoneLink] Failed to load remote URLs', e);
    urlPub.textContent = 'Offline — use local URL';
    urlLoc.textContent = 'http://localhost:3005/mobile.html';
    qrImg.style.display = 'none';
    qrImg.parentElement.innerHTML = '<div style="color:rgba(255,215,0,0.4);font-family:var(--mono);font-size:11px;padding:40px;text-align:center;">QR Code requires internet.<br>Open <strong style="color:rgba(255,215,0,0.7)">http://localhost:3005/mobile.html</strong> on your phone.</div>';
  }

  phoneLinkPollInterval = setInterval(pollDevices, 1500);
  pollDevices();

  document.getElementById('pending-approve-btn').addEventListener('click', () => {
    if (currentPendingDevice) respondToDevice(currentPendingDevice.deviceId, 'approved');
  });

  document.getElementById('pending-deny-btn').addEventListener('click', () => {
    if (currentPendingDevice) respondToDevice(currentPendingDevice.deviceId, 'denied');
  });

  document.getElementById('linked-revoke-btn').addEventListener('click', () => {
    const linkedId = document.getElementById('linked-revoke-btn').dataset.deviceId;
    if (linkedId) respondToDevice(linkedId, 'revoked');
  });
}

async function pollDevices() {
  try {
    const res = await fetch('/api/devices');
    const data = await res.json();
    if (!data.success || !data.devices) return;

    const devices = data.devices;
    
    const pending = devices.find(d => d.status === 'pending');
    const approved = devices.find(d => d.status === 'approved');

    const activeCount = document.getElementById('phone-active-count');
    if (activeCount) {
      const approvedCount = devices.filter(d => d.status === 'approved').length;
      activeCount.textContent = `${approvedCount} linked`;
    }

    const qrStage = document.getElementById('phone-qr-stage');
    const pendingStage = document.getElementById('phone-pending-stage');
    const linkedStage = document.getElementById('phone-linked-stage');

    if (pending) {
      currentPendingDevice = pending;
      qrStage.classList.add('hidden');
      linkedStage.classList.add('hidden');
      pendingStage.classList.remove('hidden');

      document.getElementById('pending-device-os').textContent = pending.os;
      document.getElementById('pending-device-browser').textContent = pending.browser;
      document.getElementById('pending-device-ip').textContent = pending.ip;
    } else if (approved) {
      currentPendingDevice = null;
      currentLinkedDeviceId = approved.deviceId;
      qrStage.classList.add('hidden');
      pendingStage.classList.add('hidden');
      linkedStage.classList.remove('hidden');

      document.getElementById('linked-device-name').textContent = approved.os;
      document.getElementById('linked-device-meta').textContent = `${approved.browser} · ${approved.ip}`;
      document.getElementById('linked-revoke-btn').dataset.deviceId = approved.deviceId;

      const systemPing = document.getElementById('ambient-ping-text')?.textContent || '12ms';
      document.getElementById('phone-stat-ping').textContent = systemPing;
    } else {
      currentPendingDevice = null;
      currentLinkedDeviceId = null;
      pendingStage.classList.add('hidden');
      linkedStage.classList.add('hidden');
      qrStage.classList.remove('hidden');
    }
  } catch (e) {
    console.error('[PhoneLink] Polling error', e);
  }
}

async function respondToDevice(deviceId, status) {
  try {
    const res = await fetch('/api/device/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId, status })
    });
    const data = await res.json();
    if (data.success) {
      if (status === 'approved') {
        toast('Phone linked successfully, BOSS.', 'ok');
        speak('Remote access granted. Phone is now connected.');
      } else if (status === 'denied') {
        toast('Connection denied.', 'err');
        speak('Remote access denied.');
      } else {
        toast('Access revoked.', 'ok');
        speak('Phone disconnected.');
      }
      pollDevices();
    }
  } catch (e) {
    toast('Response failed.', 'err');
  }
}

// ================================================
// INIT
// ================================================
document.addEventListener('DOMContentLoaded', runBoot);

// Pre-warm speech synthesis for faster first response
(function prewarmSpeech() {
  if (!('speechSynthesis' in window)) return;
  function warmup() {
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0; u.rate = 2;
    speechSynthesis.speak(u);
    document.removeEventListener('click', warmup);
    document.removeEventListener('keydown', warmup);
  }
  document.addEventListener('click', warmup);
  document.addEventListener('keydown', warmup);
})();

async function triggerPhoneAction(action, value = '') {
  if (!currentLinkedDeviceId) {
    toast('No phone currently linked, BOSS.', 'err');
    return;
  }
  
  // For toast, ask user for custom input message
  let finalVal = value;
  if (action === 'toast' && !value) {
    finalVal = prompt('Enter toast message for phone:', 'Hello from desktop, BOSS!');
    if (finalVal === null) return; // user cancelled
  }

  try {
    const res = await fetch('/api/device/command/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId: currentLinkedDeviceId, action, value: finalVal })
    });
    const d = await res.json();
    if (d.success) {
      toast(`Remote '${action}' sent to phone.`, 'ok');
    }
  } catch (err) {
    console.error('Trigger phone action failed:', err);
    toast('Failed to send remote command.', 'err');
  }
}

function setPhoneVolume(val) {
  triggerPhoneAction('volume', val);
}

// ================================================
// OVERLAY MINI MODE
// ================================================
let overlayVisible = false;
let overlayInterval = null;

function toggleOverlay() {
  const ov = document.getElementById('overlay-mini');
  if (!ov) return;
  overlayVisible = !overlayVisible;
  ov.style.display = overlayVisible ? 'block' : 'none';
  if (overlayVisible) {
    updateOverlay();
    overlayInterval = setInterval(updateOverlay, 3000);
    makeOverlayDraggable(ov);
  } else {
    clearInterval(overlayInterval);
    overlayInterval = null;
  }
}

async function updateOverlay() {
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    if (d.cpu !== undefined) document.getElementById('ov-cpu').textContent = Math.round(d.cpu) + '%';
    if (d.ram !== undefined) document.getElementById('ov-ram').textContent = Math.round(d.ram) + '%';
    if (d.battery !== undefined) document.getElementById('ov-bat').textContent = Math.round(d.battery) + '%';
    document.getElementById('ov-time').textContent = new Date().toLocaleTimeString();
  } catch(e) {}
}

function makeOverlayDraggable(el) {
  let isDragging = false, startX, startY, origX, origY;
  el.onmousedown = function(e) {
    if (e.target.tagName === 'BUTTON' || e.target.tagName === 'I') return;
    isDragging = true;
    startX = e.clientX; startY = e.clientY;
    origX = el.offsetLeft; origY = el.offsetTop;
    document.onmousemove = function(e) {
      if (!isDragging) return;
      el.style.right = 'auto';
      el.style.bottom = 'auto';
      el.style.left = (origX + e.clientX - startX) + 'px';
      el.style.top = (origY + e.clientY - startY) + 'px';
    };
    document.onmouseup = function() { isDragging = false; };
  };
}

// ================================================
// MODE SYSTEM — JARVIS / FRIDAY / JENNY
// ================================================
let currentMode = 'friday';
const modeConfig = {
  jarvis: {
    name: 'J.A.R.V.I.S.',
    fullName: 'Just A Rather Very Intelligent System',
    greeting: 'Good day, Sir. How may I assist you?',
    standby: 'At your service, Sir.',
    thinking: 'Processing your request, Sir...',
    farewell: 'Very well, Sir. Standing by.',
    personality: 'Formal, British, sophisticated',
    accent: '#00d4ff'
  },
  friday: {
    name: 'F.R.I.D.A.Y.',
    fullName: 'Female Replacement Intelligent Digital Assistant Youth',
    greeting: 'Hey Boss! FRIDAY online and ready.',
    standby: 'Ready when you are, Boss.',
    thinking: 'Crunching that for you, Boss...',
    farewell: 'Catch you later, Boss!',
    personality: 'Casual, witty, efficient',
    accent: '#a855f7'
  },
  ultron: {
    name: 'U.L.T.R.O.N.',
    fullName: 'Unified Logic & Tactical Reasoning Oracle Network',
    greeting: 'ULTRON online. Gesture control ready. Show me your hands, Boss.',
    standby: 'Awaiting input. Gesture module on standby.',
    thinking: 'Analyzing tactical parameters...',
    farewell: 'ULTRON signing off. Stay sharp, Boss.',
    personality: 'Aggressive, powerful, precise',
    accent: '#ff3e3e'
  }
};

async function loadMode() {
  try {
    const res = await fetch('/api/mode');
    const data = await res.json();
    if (data.mode) {
      currentMode = data.mode;
      applyMode(currentMode);
    }
  } catch(e) {}
}

const MODE_WELCOME_CARDS = {
  friday: [
    { cmd: "briefing", icon: "fa-clipboard-list", title: "Briefing", desc: "Full system overview" },
    { cmd: "what's the weather", icon: "fa-cloud-sun", title: "Weather", desc: "Current conditions" },
    { cmd: "set a timer for 5 minutes", icon: "fa-stopwatch", title: "Timer", desc: "Set a countdown" },
    { cmd: "check emails", icon: "fa-envelope", title: "Emails", desc: "Check inbox" },
    { cmd: "tell me a joke", icon: "fa-face-laugh", title: "Entertain", desc: "Jokes & facts" },
    { cmd: "open safari", icon: "fa-globe", title: "Browser", desc: "Open the browser" },
    { cmd: "what can you do", icon: "fa-terminal", title: "Commands", desc: "All capabilities" },
    { cmd: "lock screen", icon: "fa-lock", title: "Lock", desc: "Lock the screen" },
  ],
  jarvis: [
    { cmd: "agency status", icon: "fa-building", title: "Agency Status", desc: "Live ops dashboard" },
    { cmd: "agency new mission", icon: "fa-bullseye", title: "New Mission", desc: "Launch a lead mission" },
    { cmd: "agency outreach", icon: "fa-envelope-open-text", title: "Outreach", desc: "Review pending outreach" },
    { cmd: "agency briefing", icon: "fa-gauge-high", title: "Agency Briefing", desc: "Full business briefing" },
    { cmd: "what can you do", icon: "fa-terminal", title: "Commands", desc: "All capabilities" },
    { cmd: "system brief", icon: "fa-microchip", title: "Diagnostics", desc: "System health" },
  ],
  ultron: [
    { cmd: "Run a full system diagnostic", icon: "fa-microchip", title: "Diagnose", desc: "Full diagnostic" },
    { cmd: "agency status", icon: "fa-building", title: "Agency", desc: "Ops overview" },
  ],
};

function renderModeWelcome(mode) {
  const cfg = modeConfig[mode];
  const ws = document.getElementById('welcome-screen');
  if (!ws || !cfg) return;
  const title = ws.querySelector('.welcome-title');
  const sub = ws.querySelector('.welcome-sub');
  if (title) title.textContent = cfg.name;
  if (sub) sub.textContent = mode === 'jarvis'
    ? "Agency OS is online. What shall we do today, boss?"
    : "What can I help you with, BOSS?";

  const container = ws.querySelector('.welcome-actions');
  if (!container) return;
  const cards = MODE_WELCOME_CARDS[mode] || MODE_WELCOME_CARDS.friday;
  container.innerHTML = '';
  cards.forEach(s => {
    const btn = document.createElement('button');
    btn.className = 'welcome-card';
    btn.dataset.cmd = s.cmd;
    btn.innerHTML = `<i class="fa-solid ${s.icon}"></i><span class="wc-title">${s.title}</span><span class="wc-desc">${s.desc}</span>`;
    btn.addEventListener('click', () => sendMessage(s.cmd));
    container.appendChild(btn);
  });
}

function applyMode(mode) {
  currentMode = mode;
  
  document.body.classList.remove('mode-jarvis', 'mode-friday', 'mode-ultron');
  document.body.classList.add('mode-' + mode);
  
  const cfg = modeConfig[mode];
  if (cfg) {
    const bootTitle = document.getElementById('boot-title');
    if (bootTitle) bootTitle.textContent = cfg.name;
    const bootSub = document.getElementById('boot-sub');
    if (bootSub) bootSub.textContent = cfg.fullName;
    document.querySelectorAll('.logo').forEach(el => el.textContent = cfg.name);
    document.title = cfg.name;
  }
  
  document.querySelectorAll('.mode-opt').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  
  const badge = document.getElementById('mode-badge');
  if (badge) badge.textContent = mode.toUpperCase();
  
  sfx.confirm();
  toast(`Switched to ${cfg.name} mode`, 'ok');
  
  showModeWelcome(mode);
  renderModeWelcome(mode);
}

async function switchMode(mode) {
  if (mode === currentMode && mode !== 'ultron') return;
  try {
    const res = await fetch('/api/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    const data = await res.json();
    if (data.success) {
      if (mode === 'ultron') {
        window.location.href = '/ultron.html';
        return;
      }
      applyMode(mode);
    }
  } catch(e) {
    toast('Failed to switch mode', 'err');
  }
}

// ================================================
// MODE WELCOME OVERLAY
// ================================================
function showModeWelcome(mode) {
  const cfg = modeConfig[mode];
  if (!cfg) return;
  
  const existing = document.getElementById('mode-welcome-overlay');
  if (existing) existing.remove();
  
  const overlay = document.createElement('div');
  overlay.id = 'mode-welcome-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.95);backdrop-filter:blur(20px);opacity:0;transition:opacity 0.4s ease;';
  
  const colors = { jarvis: '#00d4ff', friday: '#a855f7', ultron: '#ff3e3e' };
  const c = colors[mode] || '#ffd700';
  
  overlay.innerHTML = `
    <div style="text-align:center;transform:scale(0.8);transition:transform 0.5s cubic-bezier(0.16,1,0.3,1);">
      <div style="width:120px;height:120px;margin:0 auto 24px;border-radius:50%;border:2px solid ${c};display:flex;align-items:center;justify-content:center;position:relative;">
        <div style="position:absolute;inset:-10px;border-radius:50%;border:1px solid ${c};opacity:0.3;animation:ring-spin 3s linear infinite;"></div>
        <div style="position:absolute;inset:-20px;border-radius:50%;border:1px dashed ${c};opacity:0.15;animation:ring-spin 6s linear infinite reverse;"></div>
        <i class="fa-solid ${mode==='jarvis'?'fa-robot':mode==='friday'?'fa-brain':'fa-hand-sparkles'}" style="font-size:40px;color:${c};text-shadow:0 0 30px ${c};"></i>
      </div>
      <div style="font-family:var(--orbitron);font-size:32px;color:${c};letter-spacing:6px;text-shadow:0 0 40px ${c};margin-bottom:8px;">${cfg.name}</div>
      <div style="font-family:var(--mono);font-size:12px;color:rgba(255,255,255,0.5);letter-spacing:3px;text-transform:uppercase;">${cfg.fullName}</div>
      <div style="font-family:var(--mono);font-size:11px;color:rgba(255,255,255,0.3);margin-top:16px;letter-spacing:1px;">${cfg.greeting}</div>
    </div>
  `;
  
  document.body.appendChild(overlay);
  requestAnimationFrame(() => {
    overlay.style.opacity = '1';
    overlay.querySelector('div').style.transform = 'scale(1)';
  });
  
  setTimeout(() => {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 400);
  }, 2200);
}

// ================================================
// ULTRON GESTURE CONTROL
// ================================================
let gestureActive = false;
let gestureCamStream = null;

async function startGestureMode() {
  try {
    const res = await fetch('/api/gesture/start', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      gestureActive = true;
      showGestureUI();
      toast('Gesture control activated', 'ok');
    } else {
      toast('Gesture modules not available. Install mediapipe + opencv.', 'err');
    }
  } catch(e) {
    toast('Gesture control unavailable', 'err');
  }
}

async function stopGestureMode() {
  try {
    await fetch('/api/gesture/stop', { method: 'POST' });
    gestureActive = false;
    hideGestureUI();
    toast('Gesture control deactivated', 'ok');
  } catch(e) {}
}

function showGestureUI() {
  let panel = document.getElementById('gesture-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'gesture-panel';
    panel.style.cssText = 'position:fixed;bottom:20px;right:20px;width:280px;z-index:9998;background:rgba(10,2,2,0.94);border:1px solid rgba(255,62,62,0.3);border-radius:16px;padding:12px;backdrop-filter:blur(20px);box-shadow:0 8px 40px rgba(255,0,0,0.15);';
    panel.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-family:var(--orbitron);font-size:10px;color:#ff3e3e;letter-spacing:2px;">U.L.T.R.O.N. GESTURE</span>
        <button onclick="stopGestureMode()" style="background:none;border:none;color:#fff;cursor:pointer;font-size:14px;padding:2px 6px;"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div id="gesture-cam" style="width:100%;height:150px;background:#111;border-radius:8px;margin-bottom:8px;display:flex;align-items:center;justify-content:center;overflow:hidden;">
        <div style="color:rgba(255,255,255,0.3);font-size:11px;font-family:var(--mono);">Initializing camera...</div>
      </div>
      <div style="display:flex;gap:12px;margin-bottom:8px;">
        <div style="flex:1;text-align:center;">
          <div style="font-family:var(--orbitron);font-size:14px;color:#ff3e3e;" id="gesture-name">--</div>
          <div style="font-family:var(--mono);font-size:8px;color:rgba(255,255,255,0.4);letter-spacing:1px;">GESTURE</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-family:var(--orbitron);font-size:14px;color:${gestureActive?'#0f0':'#ff3e3e'};" id="gesture-status">${gestureActive?'ACTIVE':'OFF'}</div>
          <div style="font-family:var(--mono);font-size:8px;color:rgba(255,255,255,0.4);letter-spacing:1px;">STATUS</div>
        </div>
      </div>
      <div style="font-family:var(--mono);font-size:9px;color:rgba(255,255,255,0.3);text-align:center;">
        Point=Move | Pinch=Click | Palm=Toggle | Fist=Pause
      </div>
    `;
    document.body.appendChild(panel);
  }
  
  const camEl = document.getElementById('gesture-cam');
  if (camEl) {
    camEl.innerHTML = '<img id="gesture-cam-img" style="width:100%;height:100%;object-fit:cover;border-radius:8px;" src="/api/gesture/frame">';
  }
  
  pollGestureStatus();
}

function hideGestureUI() {
  const panel = document.getElementById('gesture-panel');
  if (panel) panel.remove();
}

function pollGestureStatus() {
  if (!gestureActive) return;
  fetch('/api/gesture-status').then(r=>r.json()).then(d => {
    const nameEl = document.getElementById('gesture-name');
    const statusEl = document.getElementById('gesture-status');
    if (nameEl) nameEl.textContent = d.gesture || '--';
    if (statusEl) {
      statusEl.textContent = d.active ? 'ACTIVE' : 'OFF';
      statusEl.style.color = d.active ? '#0f0' : '#ff3e3e';
    }
  }).catch(()=>{});
  if (gestureActive) setTimeout(pollGestureStatus, 500);
}

// Initialize mode on load
loadMode();

// ================================================
// SMART SUGGESTIONS
// ================================================
async function loadSmartSuggestions() {
  try {
    const res = await fetch('/api/smart-suggestions');
    const data = await res.json();
    if (data.success && data.suggestions) {
      updateWelcomeCards(data.suggestions);
    }
  } catch(e) {}
}

function updateWelcomeCards(suggestions) {
  const container = document.querySelector('.welcome-actions');
  if (!container || !suggestions.length) return;
  container.innerHTML = '';
  suggestions.forEach(s => {
    const btn = document.createElement('button');
    btn.className = 'welcome-card';
    btn.dataset.cmd = s.command;
    btn.innerHTML = `<i class="fa-solid ${s.icon}"></i><span class="wc-title">${s.title}</span><span class="wc-desc">${s.desc}</span>`;
    btn.addEventListener('click', () => sendMessage(s.command));
    container.appendChild(btn);
  });
}

// ================================================
// USER HABITS & ANALYTICS
// ================================================
let commandStats = {};

function trackCommand(text) {
  const key = text.toLowerCase().trim().substring(0, 30);
  commandStats[key] = (commandStats[key] || 0) + 1;
  localStorage.setItem('jenny_cmd_stats', JSON.stringify(commandStats));
}

function loadCommandStats() {
  try {
    commandStats = JSON.parse(localStorage.getItem('jenny_cmd_stats') || '{}');
  } catch(e) { commandStats = {}; }
}

// Track every command sent
const _origSendMsgForTracking = window.sendMessage;
if (typeof _origSendMsgForTracking === 'function') {
  window.sendMessage = function(text) {
    trackCommand(text);
    return _origSendMsgForTracking.call(this, text);
  };
}

loadCommandStats();

// ================================================
// ENHANCED CHAT WITH MODE PERSONALITY
// ================================================
const _origAddAIMode = window.addAIMessage;
if (typeof _origAddAIMode === 'function') {
  window.addAIMessage = function(text, isUser) {
    return _origAddAIMode.call(this, text, isUser);
  };
}

// ================================================
// NEWS PANEL INTEGRATION
// ================================================
function loadNewsPanel(el) {
  el.innerHTML = '<div class="panel-loading"><i class="fa-solid fa-spinner fa-spin"></i> Loading news...</div>';
  fetch('/api/news').then(r=>r.json()).then(data => {
    if (data.success && data.stories && data.stories.length > 0) {
      el.innerHTML = data.stories.map(s => `
        <div class="cmd-ref-item" style="cursor:pointer" onclick="window.open('${s.url}','_blank')">
          <div class="cc">${s.title}</div>
          <div class="cd"><i class="fa-solid fa-arrow-up-right-from-square"></i> Open article</div>
        </div>
      `).join('');
    } else {
      el.innerHTML = '<div style="color:var(--txt2);padding:20px;text-align:center;">No news available right now</div>';
    }
  }).catch(() => {
    el.innerHTML = '<div style="color:var(--txt2);padding:20px;text-align:center;">Failed to load news</div>';
  });
}

// ================================================
// WAKE WORD DETECTION — Browser SpeechRecognition
// Listens continuously for "Hey Jenny" / "Hey Friday"
// ================================================
let wakeWordActive = false;
let wakeRecognition = null;
let wakeListening = false;

const WAKE_WORDS = ['hey jenny', 'hey jenni', 'hey jeeny', 'hey friday', 'hey jeni', 'hey ultron'];

function initWakeWord() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    console.warn('[WakeWord] SpeechRecognition not supported in this browser');
    return false;
  }

  wakeRecognition = new SR();
  wakeRecognition.continuous = true;
  wakeRecognition.interimResults = true;
  wakeRecognition.lang = 'en-US';
  wakeRecognition.maxAlternatives = 3;

  wakeRecognition.onresult = function(event) {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript.toLowerCase().trim();
      for (const ww of WAKE_WORDS) {
        if (transcript.includes(ww)) {
          console.log('[WakeWord] Detected:', ww);
          onWakeWordDetected(transcript, ww);
          return;
        }
      }
    }
  };

  wakeRecognition.onerror = function(event) {
    console.warn('[WakeWord] Error:', event.error);
    if (event.error === 'no-speech') {
      restartWakeListening();
    } else if (event.error === 'not-allowed') {
      toast('Microphone access denied. Enable it in browser settings.', 'err');
      wakeWordActive = false;
      updateWakeWordUI();
    }
  };

  wakeRecognition.onend = function() {
    wakeListening = false;
    if (wakeWordActive) {
      restartWakeListening();
    }
  };

  return true;
}

function restartWakeListening() {
  if (!wakeWordActive || !wakeRecognition) return;
  setTimeout(() => {
    if (wakeWordActive && !wakeListening) {
      try {
        wakeRecognition.start();
        wakeListening = true;
      } catch(e) {
        console.warn('[WakeWord] Restart failed:', e);
      }
    }
  }, 500);
}

function startWakeWord() {
  if (!wakeRecognition && !initWakeWord()) {
    toast('Wake word requires microphone access', 'err');
    return;
  }
  wakeWordActive = true;
  try {
    wakeRecognition.start();
    wakeListening = true;
    toast('Wake word active — Say "Hey Jenny" or "Hey Friday"', 'ok');
  } catch(e) {
    if (e.message && e.message.includes('already started')) {
      wakeListening = true;
    } else {
      console.error('[WakeWord] Start error:', e);
      toast('Failed to start wake word: ' + e.message, 'err');
    }
  }
  updateWakeWordUI();
}

function stopWakeWord() {
  wakeWordActive = false;
  if (wakeRecognition) {
    try { wakeRecognition.stop(); } catch(e) {}
  }
  wakeListening = false;
  toast('Wake word deactivated', 'info');
  updateWakeWordUI();
}

function toggleWakeWord() {
  if (wakeWordActive) {
    stopWakeWord();
  } else {
    startWakeWord();
  }
}

function updateWakeWordUI() {
  const btn = document.getElementById('wake-word-btn');
  if (btn) {
    btn.classList.toggle('active', wakeWordActive);
    btn.title = wakeWordActive ? 'Wake word ON — Click to disable' : 'Wake word OFF — Click to enable';
  }
}

function onWakeWordDetected(transcript, wakeWord) {
  sfx.confirm();

  document.body.classList.add('orb-active');
  const holoLabel = document.getElementById('holo-label');
  if (holoLabel) holoLabel.textContent = 'WAKE WORD DETECTED — Listening...';
  const holoStatus = document.getElementById('holo-status');
  if (holoStatus) holoStatus.textContent = 'LISTENING';

  speak('Yes Boss?', () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;

    const cmdRecognition = new SR();
    cmdRecognition.continuous = false;
    cmdRecognition.interimResults = true;
    cmdRecognition.lang = 'en-US';
    cmdRecognition.maxAlternatives = 1;

    let finalTranscript = '';

    cmdRecognition.onresult = function(event) {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        }
      }
      if (finalTranscript) {
        if (holoLabel) holoLabel.textContent = finalTranscript;
      }
    };

    cmdRecognition.onend = function() {
      document.body.classList.remove('orb-active');
      if (holoLabel) holoLabel.textContent = 'Tap the orb or type a command';
      if (holoStatus) holoStatus.textContent = 'STANDBY';

      if (finalTranscript.trim()) {
        const cmd = finalTranscript.trim().toLowerCase();
        if (['goodbye', 'bye', 'sleep', 'stop listening', 'go back to sleep'].some(w => cmd.includes(w))) {
          speak('Going back to sleep mode, Boss. Say Hey Jenny to wake me.');
          stopWakeWord();
          return;
        }
        sendMessage(finalTranscript.trim());
      }
    };

    cmdRecognition.onerror = function() {
      document.body.classList.remove('orb-active');
      if (holoLabel) holoLabel.textContent = 'Tap the orb or type a command';
      if (holoStatus) holoStatus.textContent = 'STANDBY';
    };

    try {
      cmdRecognition.start();
    } catch(e) {}
  });
}

// ================================================
// BOOT PARTICLES - Cinematic background
// ================================================
function initBootParticles() {
  const canvas = document.getElementById('boot-particles');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w = canvas.width = window.innerWidth;
  let h = canvas.height = window.innerHeight;
  
  const particles = [];
  for (let i = 0; i < 120; i++) {
    particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 1.5 + 0.5,
      alpha: Math.random() * 0.4 + 0.1,
    });
  }
  
  function draw() {
    ctx.clearRect(0, 0, w, h);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,215,0,${p.alpha})`;
      ctx.fill();
    });
    
    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(255,215,0,${0.05 * (1 - dist / 120)})`;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
  
  window.addEventListener('resize', () => {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  });
}
