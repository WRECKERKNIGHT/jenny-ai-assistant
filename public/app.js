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
  timer: () => { [880, 1100, 880].forEach((f, i) => { setTimeout(() => playTone(f, 0.2, 'sine', 0.06), i * 200); }); }
};

// ================================================
// PARTICLE BACKGROUND
// ================================================
function startParticles() {
  const container = document.getElementById('particle-bg');
  if (!container) return;
  const particles = [];
  const count = 30;
  for (let i = 0; i < count; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const size = 1 + Math.random() * 2;
    p.style.cssText = `
      position:absolute; width:${size}px; height:${size}px;
      border-radius:50%; background:rgba(255,255,255,${0.05 + Math.random() * 0.1});
      left:${Math.random() * 100}%; top:${Math.random() * 100}%;
      opacity:${0.3 + Math.random() * 0.5};
      pointer-events:none;
    `;
    container.appendChild(p);
    particles.push({ el: p, x: parseFloat(p.style.left), y: parseFloat(p.style.top), vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3 });
  }
  function anim() {
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > 100) p.vx *= -1;
      if (p.y < 0 || p.y > 100) p.vy *= -1;
      p.el.style.left = p.x + '%';
      p.el.style.top = p.y + '%';
    });
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

// Star field
let bootStarsFrame = 0;
let bootStarsRafId = null;
function initBootStars() {
  const canvas = document.getElementById('boot-stars');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const stars = [];
  const count = 200;
  for (let i = 0; i < count; i++) {
    stars.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      size: Math.random() * 1.5 + 0.3,
      speed: Math.random() * 0.5 + 0.1,
      brightness: Math.random(),
      twinkleSpeed: Math.random() * 0.02 + 0.005
    });
  }
  function draw() {
    if (document.getElementById('boot-screen')?.classList.contains('done')) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    bootStarsFrame++;
    stars.forEach(s => {
      const alpha = 0.3 + Math.sin(bootStarsFrame * s.twinkleSpeed) * 0.3 + s.brightness * 0.2;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${alpha})`;
      ctx.fill();
      s.y += s.speed;
      if (s.y > canvas.height) { s.y = 0; s.x = Math.random() * canvas.width; }
    });
    ctx.strokeStyle = 'rgba(255,255,255,0.015)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i < stars.length; i++) {
      for (let j = i + 1; j < stars.length; j++) {
        const dx = stars[i].x - stars[j].x;
        const dy = stars[i].y - stars[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 80) {
          ctx.beginPath();
          ctx.moveTo(stars[i].x, stars[i].y);
          ctx.lineTo(stars[j].x, stars[j].y);
          ctx.stroke();
        }
      }
    }
    bootStarsRafId = requestAnimationFrame(draw);
  }
  draw();
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
    if (document.getElementById('boot-screen')?.classList.contains('done')) {
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
  const titleEl = document.getElementById('boot-title');
  const subEl = document.getElementById('boot-sub');
  const barEl = document.getElementById('boot-bar');
  const pctEl = document.getElementById('boot-percentage');
  const logsEl = document.getElementById('boot-logs');
  const termEl = document.getElementById('boot-terminal');
  const flashEl = document.getElementById('boot-flash');
  const bootScreen = document.getElementById('boot-screen');

  // Initialize visual layers
  initBootStars();
  initDataStreams();

  // Apply saved dark mode immediately
  const savedMem = loadOfflineMemory();
  applyDarkMode(savedMem.darkMode !== false);

  // Phase 0: Dramatic pause — let rings and core materialize
  await sleep(1800);

  // Phase 1: Title typewriter with glitch
  const title = 'J.E.N.N.Y.';
  titleEl.classList.add('glitching');
  for (let i = 0; i < title.length; i++) {
    titleEl.textContent += title[i];
    await sleep(80);
  }
  await sleep(200);
  titleEl.classList.remove('glitching');

  // Phase 2: Subtitle fade in
  await sleep(300);
  subEl.classList.add('show');

  // Phase 3: Show terminal
  await sleep(400);
  termEl.classList.add('show');

  // Phase 4: Run through boot phases
  let logIndex = 0;
  for (const phase of bootPhases) {
    for (const log of phase.logs) {
      await sleep(200 + Math.random() * 200);
      const line = document.createElement('div');
      line.className = 'log-line';
      let html = '';
      if (log.prefix) html += `<span class="log-prefix">${log.prefix}</span>`;
      html += `<span class="log-${log.type}">${log.text}</span>`;
      if (log.suffix) html += `<span class="log-prefix">${log.suffix}</span>`;
      line.innerHTML = html;
      logsEl.appendChild(line);
      logsEl.scrollTop = logsEl.scrollHeight;
      sfx.hover();
    }
    barEl.style.width = phase.progress + '%';
    pctEl.textContent = phase.progress + '%';
  }

  // Phase 5: Flash + energy burst
  await sleep(300);
  flashEl.classList.add('fire');
  sfx.boot();

  // Phase 6: Dramatic exit
  await sleep(400);
  bootScreen.classList.add('exiting');
  await sleep(800);
  bootScreen.classList.add('done');
  const app = document.getElementById('main-app');
  app.style.display = 'flex';

  await sleep(100);
  restoreChatHistory();
  const greeting = getGreeting();
  if (document.getElementById('msgs').children.length === 0) addAIMessage(greeting);
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

  document.querySelectorAll('.welcome-card').forEach(card => {
    card.addEventListener('click', () => {
      const cmd = card.dataset.cmd;
      if (cmd) { sendMessage(cmd); sfx.click(); }
    });
  });

  await sleep(600);
  speak(greeting);
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
  ctx.beginPath();
  ctx.moveTo(0, H);
  data.forEach((v, i) => {
    const x = i * step;
    const y = H - (v / 100) * (H - 4);
    if (i === 0) ctx.lineTo(x, y);
    else {
      const px = (i - 1) * step;
      const py = H - (data[i-1] / 100) * (H - 4);
      ctx.bezierCurveTo(px + step * 0.4, py, x - step * 0.4, y, x, y);
    }
  });
  ctx.lineTo(W, H);
  ctx.closePath();
  const fillGrad = ctx.createLinearGradient(0, 0, 0, H);
  fillGrad.addColorStop(0, color.replace(')', ',0.15)').replace('rgb', 'rgba'));
  fillGrad.addColorStop(1, color.replace(')', ',0.0)').replace('rgb', 'rgba'));
  ctx.fillStyle = fillGrad;
  ctx.fill();
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * step;
    const y = H - (v / 100) * (H - 4);
    if (i === 0) ctx.moveTo(x, y);
    else {
      const px = (i - 1) * step;
      const py = H - (data[i-1] / 100) * (H - 4);
      ctx.bezierCurveTo(px + step * 0.4, py, x - step * 0.4, y, x, y);
    }
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
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
    document.getElementById('sys-battery').textContent = d.battery?.level != null ? `${Math.round(d.battery.level)}%` : '--';
    document.getElementById('sys-wifi').textContent = d.hostname ? d.hostname.split('.')[0] : '--';
    drawSparkline('spark-cpu', sparkHistory.cpu, 'rgb(255,255,255)');
    drawSparkline('spark-ram', sparkHistory.ram, 'rgb(255,255,255)');
    drawSparkline('spark-disk', sparkHistory.disk, 'rgb(255,255,255)');
    updateWelcomeVitals(cpu, ram, d.battery?.level, d.uptime);
  } catch {}
}

function startSysMonitor() { fetchSysStats(); setInterval(fetchSysStats, 3000); }

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
        const wobble = isIdle ? Math.sin(t * 0.4 + ring * 1.2) * 3 : Math.sin(t * 2 + i * 0.3) * (isSpeaking ? 12 : 6);
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
    if (isListening) { grad.addColorStop(0, 'rgba(255,255,255,0.7)'); grad.addColorStop(0.5, 'rgba(255,255,255,0.2)'); grad.addColorStop(1, 'rgba(255,255,255,0)'); }
    else if (isThinking) { grad.addColorStop(0, 'rgba(200,200,220,0.6)'); grad.addColorStop(0.5, 'rgba(200,200,220,0.15)'); grad.addColorStop(1, 'rgba(200,200,220,0)'); }
    else if (isSpeaking) { grad.addColorStop(0, 'rgba(255,255,255,0.8)'); grad.addColorStop(0.4, 'rgba(255,255,255,0.3)'); grad.addColorStop(1, 'rgba(255,255,255,0)'); ctx.beginPath(); ctx.arc(cx, cy, coreR + Math.sin(t * 3.5) * 5 + 10, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,0.03)'; ctx.fill(); }
    else { grad.addColorStop(0, 'rgba(255,255,255,0.5)'); grad.addColorStop(0.5, 'rgba(255,255,255,0.15)'); grad.addColorStop(1, 'rgba(255,255,255,0)'); }
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
    const res = await fetch('/api/gemini-quota');
    const d = await res.json();
    if (!d.success) return;
    quotaData = d;
    const badge = document.getElementById('mode-badge');
    const rpmEl = document.getElementById('quota-rpm');
    const dot = document.getElementById('status-dot');
    const stext = document.getElementById('status-text');
    if (d.isKeyPresent) {
      const keyInfo = d.keysCount > 1 ? ` [${d.activeKeys}/${d.keysCount}]` : '';
      badge.textContent = `${d.model.toUpperCase()}${keyInfo}`;
      badge.classList.add('active');
      if (rpmEl) rpmEl.textContent = `${d.rpm.current}/${d.rpm.max}`;
      if (d.activeKeys > 0) {
        if (dot) dot.style.background = 'rgba(52,211,153,0.7)';
        if (stext) stext.textContent = 'online';
      } else {
        if (dot) dot.style.background = 'rgba(251,191,36,0.7)';
        if (stext) stext.textContent = 'quota cooldown';
      }
    } else {
      badge.textContent = 'OFFLINE';
      badge.classList.remove('active');
      if (rpmEl) rpmEl.textContent = '--/--';
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
  try {
    const res = await fetch('/api/permissions-check');
    const d = await res.json();
    if (!d.success || d.platform !== 'darwin') return;
    
    const missing = Object.entries(d.permissions)
      .filter(([_, v]) => v.status === 'missing')
      .map(([name, info]) => ({ name, ...info }));
    
    if (missing.length > 0) {
      // Show permissions guide modal after a delay
      setTimeout(() => showPermissionsModal(missing), 2000);
    }
  } catch {}
}

function showPermissionsModal(missing) {
  const existing = document.getElementById('permissions-modal');
  if (existing) return;
  
  const modal = document.createElement('div');
  modal.id = 'permissions-modal';
  modal.style.cssText = `
    position:fixed; inset:0; z-index:10000; display:flex; align-items:center; justify-content:center;
    background:rgba(0,0,0,0.7); backdrop-filter:blur(10px);
  `;
  
  const iconMap = {
    accessibility: 'fa-hand-pointer',
    automation: 'fa-gear',
    fullDiskAccess: 'fa-hard-drive'
  };
  
  const steps = missing.map(p => `
    <div style="margin-bottom:16px; padding:12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:10px;">
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
        <i class="fa-solid ${iconMap[p.name] || 'fa-lock'}" style="color:rgba(255,255,0,0.8); font-size:12px;"></i>
        <span style="font-family:var(--mono); font-size:10px; font-weight:600; color:var(--txt); letter-spacing:1px; text-transform:uppercase;">${p.name.replace(/([A-Z])/g, ' $1')}</span>
      </div>
      <div style="font-size:10px; color:var(--txt2); margin-bottom:6px;">${p.message}</div>
      <div style="font-size:9px; color:var(--txt3); font-family:var(--mono);">${p.fix}</div>
    </div>
  `).join('');
  
  modal.innerHTML = `
    <div style="width:420px; max-width:90vw; background:rgba(20,20,25,0.95); border:1px solid rgba(255,255,255,0.1); border-radius:16px; padding:24px; box-shadow:0 24px 80px rgba(0,0,0,0.6);">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
        <i class="fa-solid fa-shield-halved" style="color:rgba(255,200,0,0.8); font-size:18px;"></i>
        <span style="font-family:var(--mono); font-size:12px; font-weight:700; color:var(--txt); letter-spacing:2px;">PERMISSIONS REQUIRED</span>
      </div>
      <div style="font-size:11px; color:var(--txt2); margin-bottom:16px; line-height:1.5;">
        JENNY needs macOS permissions to control your system. Grant these in System Settings:
      </div>
      ${steps}
      <div style="display:flex; gap:8px; margin-top:16px;">
        <button onclick="openSystemSettings()" style="flex:1; padding:10px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:8px; color:var(--txt); font-family:var(--mono); font-size:10px; cursor:pointer; transition:all 0.2s;">
          <i class="fa-solid fa-gear"></i> Open System Settings
        </button>
        <button onclick="dismissPermissions()" style="flex:1; padding:10px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:8px; color:var(--txt2); font-family:var(--mono); font-size:10px; cursor:pointer; transition:all 0.2s;">
          Dismiss
        </button>
      </div>
      <div style="font-size:8px; color:var(--txt3); margin-top:10px; text-align:center;">
        You can check permissions anytime by typing "check permissions"
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  sfx.error();
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
    case 'commands': return loadCommandsPanel(body);
    case 'files': return loadFilesPanel(body);
    case 'notes': return loadNotesPanel(body);
  }
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
  el.innerHTML = `<div class="cmd-ref-item"><div class="cc">summon activity / system / weather / emails / processes / vault / clipboard / settings / commands / files / notes</div><div class="cd">Open a panel</div></div><div class="cmd-ref-item"><div class="cc">close [panel] / close all</div><div class="cd">Dismiss panels</div></div><div class="cmd-ref-item"><div class="cc">set a timer for 5 minutes</div><div class="cd">Timer with voice alert</div></div><div class="cmd-ref-item"><div class="cc">briefing / daily briefing</div><div class="cd">Full system overview</div></div><div class="cmd-ref-item"><div class="cc">tell me a joke / fun fact / quote</div><div class="cd">Entertainment</div></div><div class="cmd-ref-item"><div class="cc">what is 42 * 7 / calculate 100 / 3</div><div class="cd">Quick math</div></div><div class="cmd-ref-item"><div class="cc">lock pc / sleep pc / screenshot</div><div class="cd">System controls</div></div><div class="cmd-ref-item"><div class="cc">volume [0-100] / mute / unmute</div><div class="cd">Audio controls</div></div><div class="cmd-ref-item"><div class="cc">open [app] / close [app]</div><div class="cd">Launch or quit app</div></div><div class="cmd-ref-item"><div class="cc">play / pause / next / previous</div><div class="cd">Media controls</div></div><div class="cmd-ref-item"><div class="cc">remember [fact]</div><div class="cd">Save to vault</div></div><div class="cmd-ref-item"><div class="cc">check emails / read mail</div><div class="cd">Read Mail.app</div></div><div class="cmd-ref-item"><div class="cc">shutdown / restart</div><div class="cd">Power controls</div></div><div class="cmd-ref-item"><div class="cc">tell me about [topic]</div><div class="cd">Ask anything (Gemini)</div></div><div class="cmd-ref-item"><div class="cc">Keyboard: Esc = close panels, Cmd+K = focus input</div><div class="cd">Shortcuts</div></div>`;
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
      if (data.reply.command && data.reply.command.action !== 'vault-save') { await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data.reply.command) }); }
      speak(data.reply.speech || data.reply.text);
    } else { addAIMessage('Something went wrong, BOSS. Please try again.'); setOrbState('idle'); }
  } catch { removeTyping(); addAIMessage('Connection error, BOSS. Please try again.'); setOrbState('idle'); }
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
  orbClick.classList.add('active');
  setOrbState('listening');
  sfx.confirm();
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
// INIT
// ================================================
document.addEventListener('DOMContentLoaded', runBoot);
