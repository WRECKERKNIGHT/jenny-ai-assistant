// ================================================
// J.E.N.N.Y. — Core Application v1.0
// ================================================

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx;
let masterGain;
function getCtx() {
  if (!audioCtx) {
    audioCtx = new AudioCtx();
    masterGain = audioCtx.createGain();
    masterGain.gain.value = 1;
    masterGain.connect(audioCtx.destination);
  }
  return audioCtx;
}
// Duck (lower) all synthesized SFX volume while the assistant is speaking,
// then restore it — so sounds never clash with the voice output.
function duckSfx(active) {
  try {
    if (!masterGain) getCtx();
    if (!masterGain) return;
    getCtx();
    const t = audioCtx.currentTime;
    masterGain.gain.cancelScheduledValues(t);
    masterGain.gain.setValueAtTime(masterGain.gain.value, t);
    masterGain.gain.linearRampToValueAtTime(active ? 0.22 : 1, t + 0.2);
  } catch (e) {}
}

function playTone(freq, dur, type = 'sine', vol = 0.06, attack = 0.012, release = 0.04) {
  const ctx = getCtx();
  const t0 = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  // Soft attack avoids clicks; exponential release tails the note smoothly.
  gain.gain.setValueAtTime(0, t0);
  gain.gain.linearRampToValueAtTime(vol, t0 + attack);
  gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur - release);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + dur);
}

// Rich, detuned multi-oscillator note for a fuller 'cinematic' output voice feel.
function playChord(freq, dur = 2.6, type = 'sine', vol = 0.05) {
  const ctx = getCtx();
  const t0 = ctx.currentTime;
  [1, 1.005, 0.995, 2].forEach((m, i) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq * m;
    const a = t0 + i * 0.02;
    gain.gain.setValueAtTime(0, a);
    gain.gain.linearRampToValueAtTime(vol * (i === 3 ? 0.25 : 1), a + 0.06);
    gain.gain.exponentialRampToValueAtTime(0.001, a + dur);
    osc.connect(gain).connect(masterGain || ctx.destination);
    osc.start(a);
    osc.stop(a + dur);
  });
}

let isSending = false;

const sfx = {
  click: () => playTone(1200, 0.05, 'sine', 0.04),
  hover: () => playTone(800, 0.03, 'triangle', 0.02),
  confirm: () => { playTone(600, 0.08, 'sine', 0.04); setTimeout(() => playTone(900, 0.12, 'sine', 0.04), 70); },
  error: () => { playTone(200, 0.12, 'sawtooth', 0.04); setTimeout(() => playTone(150, 0.15, 'sawtooth', 0.04), 80); },
  boot: () => {
    // Energized power-on: quick riser arpeggio into a confident triad stab.
    [220, 277.18, 329.63, 440, 554.37].forEach((f, i) => { setTimeout(() => playTone(f, 0.22, 'sine', 0.05, 0.008, 0.05), i * 55); });
    setTimeout(() => { playChord(523.25, 1.4, 'sine', 0.05); }, 340);
  },
  timer: () => { [880, 1100, 880].forEach((f, i) => { setTimeout(() => playTone(f, 0.2, 'sine', 0.06), i * 200); }); },
  jarvis: () => { [784, 987.77, 1174.66].forEach((f, i) => { setTimeout(() => playTone(f, 0.12, 'sine', 0.05), i * 80); }); },
  startupMusic: () => {
    // Cinematic HER-style swell: warm low pad builds up and resolves upward.
    const ctx = getCtx();
    const t0 = ctx.currentTime;
    [130.81, 196.0, 261.63].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = 'sine';
      o.frequency.value = f;
      const start = t0 + i * 0.12;
      g.gain.setValueAtTime(0, start);
      g.gain.linearRampToValueAtTime(0.055, start + 1.1);
      g.gain.exponentialRampToValueAtTime(0.001, start + 3.4);
      o.connect(g).connect(masterGain || ctx.destination);
      o.start(start);
      o.stop(start + 3.4);
    });
    [261.63, 329.63, 392.0, 523.25, 659.25].forEach((f, i) => {
      setTimeout(() => playTone(f, 0.5, 'triangle', 0.035, 0.02, 0.12), 900 + i * 120);
    });
    setTimeout(() => playChord(659.25, 1.8, 'sine', 0.045), 1720);
  },
  modeStartup: (mode) => {
    if (mode === 'ultron') {
      // Aggressive, mechanical descending stab motif.
      [392, 311.13, 246.94, 196].forEach((f, i) => setTimeout(() => playTone(f, 0.16, 'sawtooth', 0.05, 0.008, 0.06), i * 60));
      setTimeout(() => playTone(98, 0.8, 'sine', 0.06, 0.02, 0.3), 300);
    } else if (mode === 'jarvis') {
      // Polite, refined rising arpeggio — a gentleman's boot.
      [523.25, 659.25, 783.99].forEach((f, i) => setTimeout(() => playTone(f, 0.14, 'triangle', 0.04, 0.01, 0.05), i * 90));
      setTimeout(() => playTone(1046.5, 0.4, 'sine', 0.045, 0.03, 0.15), 280);
    } else {
      // FRIDAY — warm, cheerful major arpeggio with a sparkle on top.
      [523.25, 659.25, 783.99, 1046.5, 1318.51].forEach((f, i) => setTimeout(() => playTone(f, 0.16, 'sine', 0.04, 0.012, 0.06), i * 70));
      setTimeout(() => playChord(1046.5, 1.2, 'sine', 0.035), 300);
    }
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
    requestAnimationFrame(anim);
    if (document.hidden) return;
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

  const parentEl = canvas.parentElement;
  let rafId = null;
  let hop = false;
  function steps() {
    // Backgrounded, or the parent was torn down (boot-screen 'done'): stop the
    // loop entirely (saves CPU/battery). main-stars' parent is <body>, so it
    // stays live as dashboard ambience; boot-stars' parent is boot-screen,
    // which gets 'done' and halts it.
    if (document.hidden || (parentEl !== document.body && parentEl.classList.contains('done'))) {
      rafId = null;
      return;
    }
    // Alternating frames -> ~30 FPS, plenty for twinkle.
    hop = !hop;
    if (hop) { rafId = requestAnimationFrame(steps); return; }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const w = canvas.width, h = canvas.height;
    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];
      s.phase += s.speed;
      const alpha = 0.25 + Math.sin(s.phase) * 0.65;
      ctx.fillStyle = `${starColor}${alpha})`;
      if (s.size <= 1.2) {
        // fillRect avoids per-star path allocation (fast on large canvases)
        if (s.x < w && s.y < h) ctx.fillRect(s.x, s.y, 1, 1);
      } else {
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    rafId = requestAnimationFrame(steps);
  }
  function onVis() {
    if (!document.hidden && !rafId && !parentEl.classList.contains('done')) {
      rafId = requestAnimationFrame(steps);
    }
  }
  document.addEventListener('visibilitychange', onVis);
  rafId = requestAnimationFrame(steps);
  const starfield = {
    destroy: () => {
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', onVis);
      if (rafId) cancelAnimationFrame(rafId);
      rafId = null;
    }
  };
  activeStarfields.push(starfield);
  return starfield;
}

function initBootStars() {
  initTwinklingStars('boot-stars', 'rgba(139, 104, 255,');
  initTwinklingStars('main-stars', 'rgba(139, 104, 255,');
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
    if (document.hidden) {
      bootStreamsRafId = requestAnimationFrame(draw);
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

// Every subsystem the dashboard needs, started in one place. Both entry paths
// repeated this identical 15-call block, which made it easy for one of them to
// quietly miss a subsystem.
function startAllSubsystems() {
  startClock(); startOrb(); initSpeechWaves(); startHoloShimmer();
  startSysMonitor(); startAmbientBar(); startParticles(); startPingMonitor();
  startInputStats(); fetchQuota(); setInterval(fetchQuota, 60000);
  setInterval(updateTimerDisplay, 1000); checkPermissions();
  startConnectionMonitor(); initPhoneLinkManager(); initWakeWord();
}

function bindWelcomeCards() {
  document.querySelectorAll('.welcome-card').forEach(card => {
    card.addEventListener('click', () => { const cmd = card.dataset.cmd; if (cmd) sendMessage(cmd); });
  });
}

// A mode pick opens a clean output window: the previous conversation is dropped
// rather than replayed, so the dashboard reflects the mode just chosen. The
// welcome screen is deliberately left up so the mode's starters are waiting
// instead of an empty bubble area.
function startFreshSession() {
  try { localStorage.removeItem('jenny_chat_history'); } catch (e) {}
  const msgs = document.getElementById('msgs');
  if (msgs) msgs.innerHTML = '';
}

async function revealDashboard({ fresh }) {
  const app = document.getElementById('main-app');
  if (!app) return;
  app.style.display = 'flex';
  try { if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume(); } catch(e) {}
  if (fresh) startFreshSession();
  else restoreChatHistory();
  bindWelcomeCards();
  await loadMode();
  if (currentMode === 'friday') initFridayDashboard();
  greetAfterBoot();
}

async function runBoot() {
  const savedMem = loadOfflineMemory();
  applyDarkMode(savedMem.darkMode !== false);

  const bootScreen = document.getElementById('boot-screen');

  // The intro and the mode pick already ran in modes.html, so arriving from
  // there means a mode was just chosen and the dashboard should simply appear.
  // Playing the boot cinematic here was a second intro running straight after
  // the first one, skipped only because modes.html happened to have set
  // jenny_booted already - so cleared storage or a direct load of / brought the
  // whole splash back. jenny_from_modes states the intent explicitly.
  const fromModes = localStorage.getItem('jenny_from_modes') === '1';
  const alreadyBooted = localStorage.getItem('jenny_booted') === '1';
  localStorage.removeItem('jenny_from_modes');

  if (fromModes || alreadyBooted) {
    localStorage.setItem('jenny_booted', '1');
    if (bootScreen) bootScreen.style.display = 'none';
    try { initBootStars(); } catch(e) {}
    try { initDataStreams(); } catch(e) {}
    startAllSubsystems();
    refreshConversations();
    await revealDashboard({ fresh: fromModes });
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
    [35, 'WAKING HOLOGRAPHIC DISPLAY...'],
    [55, 'ESTABLISHING ENCRYPTED CHANNEL...'],
    [75, 'CALIBRATING VOICE SYNTHESIS...'],
    [90, 'LOADING MEMORY VAULT...'],
    [100, 'ALL SYSTEMS: PASS'],
  ];
  for (const [pct, msg] of steps) {
    if (loadFill) loadFill.style.width = pct + '%';
    if (loadText) loadText.textContent = msg;
    await sleep(300 + Math.random() * 220);
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
  startAllSubsystems();
  refreshConversations();
  await revealDashboard({ fresh: false });
}

async function greetAfterBoot() {
  // Greetings are gated behind an actual mode selection: modes.html sets the
  // jenny_greet_after_mode flag right before redirecting to the dashboard, so
  // the intro video + mode pick ALWAYS finish BEFORE any greeting plays — and
  // plain app launches never speak a greeting out of order. Restored chat
  // history must NOT suppress it either: the flag alone is the gate, otherwise
  // the greeting silently never happens after a fresh mode selection.
  const greetFlag = localStorage.getItem('jenny_greet_after_mode');
  if (!greetFlag) return;
  localStorage.removeItem('jenny_greet_after_mode');
  // modes.html stores the chosen mode in this flag, so the dashboard can say
  // out loud which personality it just switched into.
  const modeName = String(greetFlag).toUpperCase();
  let text = getGreeting();
  let speech = text;
  let serverSpoke = false;
  try {
    const r = await fetch('/api/greeting', { cache: 'no-store' });
    const d = await r.json();
    if (d.success) {
      text = d.text || text;
      speech = d.speech || speech;
      serverSpoke = !!d.boot_greeted;
    }
  } catch(e) {}
  // Announce the mode coming up before the greeting itself, so the dashboard
  // opens by saying what it is now running instead of jumping into chat. The
  // speech queue serialises, so the two come out in order. The activation
  // line is SPOKEN but never written into the chat output box — entering a
  // mode should leave the conversation area clean (no greeting clutter).
  const activation = modeName ? `Activating ${modeName} mode.` : '';
  if (window.__bootGreeted) return;
  window.__bootGreeted = true;
  // Single-voice rule: if the server's proactive thread already spoke the
  // boot greeting, the UI only shows the text - never speaks over it.
  if (serverSpoke) return;
  // Cinematic opening: warm swell first, spoken greeting rides on top.
  setTimeout(() => { try { sfx.startupMusic(); } catch(e) {} }, 120);
  setTimeout(() => {
    if (typeof speak !== 'function') return;
    if (activation) speak(activation);
    speak(speech);
  }, 2100);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function getGreeting() {
  const mem = loadOfflineMemory();
  const name = mem.name ? ` ${mem.name}` : '';
  const hour = new Date().getHours();
  const mode = document.body.classList.contains('mode-jarvis') ? 'jarvis'
    : document.body.classList.contains('mode-ultron') ? 'ultron' : 'friday';
  let timeOfDay;
  if (hour >= 5 && hour < 12) timeOfDay = 'morning';
  else if (hour >= 12 && hour < 17) timeOfDay = 'afternoon';
  else if (hour >= 17 && hour < 21) timeOfDay = 'evening';
  else timeOfDay = 'night';
  if (mode === 'jarvis') {
    return `Good ${timeOfDay}${name}, sir. I am JARVIS, at your service. All systems are operational. How may I assist you this ${timeOfDay}?`;
  }
  if (mode === 'ultron') {
    return `ULTRON online. ${timeOfDay.toUpperCase()} protocols engaged. State your directive, Boss.`;
  }
  const items = [
    `Hey${name}!, FRIDAY online and ready. All systems are green — so what are we getting into today, Boss?`,
    `Good ${timeOfDay}${name}! FRIDAY's up and running. I tried to keep it quiet but the fans are excited. What's the plan for today?`,
    `Hey${name}, welcome back! Systems are green, coffee's figurative, and I'm fully charged. What are we doing first today, Boss?`,
  ];
  return items[Math.floor(Math.random() * items.length)];
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
  let t = 0, last = 0;
  function animate(now) {
    requestAnimationFrame(animate);
    if (document.hidden) return;
    if (now - last < 33) return; // ~30fps; still GPU-transform-cheap, no paint/layout
    last = now;
    t += 0.015;
    r.style.transform = `translate(${Math.sin(t*1.1)*6}px, ${Math.cos(t*0.9)*4}px)`;
    g.style.transform = `translate(${Math.sin(t*0.7+2)*5}px, ${-Math.cos(t*0.9)*4}px)`;
    b.style.transform = `translate(${-Math.sin(t*1.1)*6}px, ${Math.cos(t*1.3+1)*5}px)`;
  }
  requestAnimationFrame(animate);
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

function startOrb() {
  const canvas = document.getElementById('orb-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  let rafId = null;
  let lastDrawTime = 0;
  let orbStartTime = performance.now();
  function onOrbVis() {
    if (!document.hidden && !rafId) rafId = requestAnimationFrame(draw);
  }
  document.addEventListener('visibilitychange', onOrbVis);
  function draw() {
    const now = performance.now();
    rafId = null;
    if (document.hidden) return; // pause loop when backgrounded
    if (now - lastDrawTime < 33) { rafId = requestAnimationFrame(draw); return; } // ~30 FPS cap
    lastDrawTime = now;

    ctx.clearRect(0, 0, W, H);
    const t = (now - orbStartTime) / 1000;
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
      ctx.strokeStyle = `rgba(109,139,255,${alpha})`;
      ctx.lineWidth = isIdle ? 0.6 : 1.2;
      ctx.stroke();
    }
    for (let a = 0; a < 3; a++) {
      const innerR = 42 + a * 8;
      const arcSpan = isListening ? Math.PI * 1.5 : (isSpeaking ? Math.PI : Math.PI * 0.6);
      const offset = t * (0.6 + a * 0.3) * (a % 2 === 0 ? 1 : -1);
      ctx.beginPath();
      ctx.arc(cx, cy, innerR, offset, offset + arcSpan);
      ctx.strokeStyle = `rgba(109,139,255,${isIdle ? 0.12 : 0.3})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    const coreR = isIdle ? 32 : (isListening ? 38 : (isSpeaking ? 42 : 35));
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
    if (isListening) { grad.addColorStop(0, 'rgba(255,255,255,0.85)'); grad.addColorStop(0.5, 'rgba(109,139,255,0.3)'); grad.addColorStop(1, 'rgba(109,139,255,0)'); }
    else if (isThinking) { grad.addColorStop(0, 'rgba(109,139,255,0.5)'); grad.addColorStop(0.5, 'rgba(109,139,255,0.15)'); grad.addColorStop(1, 'rgba(109,139,255,0)'); }
    else if (isSpeaking) { grad.addColorStop(0, 'rgba(109,139,255,0.85)'); grad.addColorStop(0.4, 'rgba(109,139,255,0.3)'); grad.addColorStop(1, 'rgba(109,139,255,0)'); ctx.beginPath(); ctx.arc(cx, cy, coreR + Math.sin(t * 3.5) * 5 + 10, 0, Math.PI * 2); ctx.fillStyle = 'rgba(109,139,255,0.04)'; ctx.fill(); }
    else { grad.addColorStop(0, 'rgba(109,139,255,0.35)'); grad.addColorStop(0.5, 'rgba(109,139,255,0.12)'); grad.addColorStop(1, 'rgba(109,139,255,0)'); }
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
        ctx.fillStyle = `rgba(109,139,255,${isSpeaking ? 0.65 : 0.3})`;
        ctx.fill();
      }
    }
  rafId = requestAnimationFrame(draw);
  }
  onOrbVis();
}

function setOrbState(state) {
  orbState = state;
  const statusEl = document.getElementById('holo-status');
  const labelEl = document.getElementById('holo-label');
  const clickZone = document.getElementById('orb-click');
  const jdStatus = document.getElementById('jd-status');
  if (jdStatus) {
    const map = { idle: 'ONLINE', listening: 'LISTENING', thinking: 'PROCESSING', speaking: 'SPEAKING' };
    jdStatus.textContent = map[state] || 'ONLINE';
  }
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
      for (let i = 0; i < speechWaveBars.length; i++) {
        const b = speechWaveBars[i];
        if (b) { const v = Math.max(0.08, (data[i] || 0) / 255); b.style.transform = `scaleY(${v})`; }
      }
      speechAnimFrame = requestAnimationFrame(animate);
    }
    animate();
  } catch {}
}

function stopSpeechWaves() {
  if (speechAnimFrame) cancelAnimationFrame(speechAnimFrame);
  const container = document.getElementById('speech-waves');
  if (container) container.classList.remove('active');
  speechWaveBars.forEach(bar => { if (bar) bar.style.transform = 'scaleY(0.08)'; });
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

function startAmbientBar() { fetchAmbientData(); fetchSpotifyStatus(); setInterval(fetchAmbientData, 8000); setInterval(fetchSpotifyStatus, 10000); }

async function fetchSpotifyStatus() {
  try {
    const res = await fetch('/api/spotify/status', { cache: 'no-store' });
    const d = await res.json();
    if (!d) return;
    const chip = document.getElementById('ambient-spotify');
    const txt = document.getElementById('ambient-spotify-text');
    if (!chip || !txt) return;
    const running = !!(d.running || d.connected);
    txt.textContent = running ? 'Spotify connected' : 'Spotify offline';
    chip.style.borderColor = running ? 'rgba(29,185,84,0.45)' : 'rgba(255,255,255,0.08)';
    chip.style.background = running ? 'rgba(29,185,84,0.08)' : '';
    const icon = chip.querySelector('i');
    if (icon) icon.style.color = running ? '#1db954' : '';
    chip.title = d.message || '';
  } catch {}
}

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
      if (d.success && d.speed) {
        netEl.textContent = d.speed;
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
    const [res, hres] = await Promise.all([
      fetch('/api/groq-usage', { cache: 'no-store' }),
      fetch('/api/health', { cache: 'no-store' }),
    ]);
    const d = await res.json();
    let health = null;
    try { health = await hres.json(); } catch {}
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

    const reallyOnline = health && health.online && d.key_set;
    if (reallyOnline) {
      badge.textContent = (d.model || 'groq').toUpperCase();
      badge.classList.add('active');
      if (rpmEl) rpmEl.textContent = d.rpm.current;
      if (rpmMaxEl) rpmMaxEl.textContent = d.rpm.max;
      if (fill) fill.style.width = Math.round((d.bar || 0) * 100) + '%';
      if (pill) pill.classList.toggle('warn', (d.bar || 0) > 0.8);
      if (dot) dot.style.background = 'rgba(52,211,153,0.7)';
      if (stext) stext.textContent = (health && health.degraded) ? 'degraded' : 'online';
    } else if (d.key_set || (health && health.key_set)) {
      badge.textContent = 'ONLINE';
      badge.classList.add('active');
      // Key exists: the server is up and speaking/chat still work. A slow Groq
      // probe must NEVER read as OFFLINE - only as "degraded" or "connecting".
      if (rpmEl) rpmEl.textContent = d.rpm.current;
      if (rpmMaxEl) rpmMaxEl.textContent = d.rpm.max;
      if (fill) fill.style.width = Math.round((d.bar || 0) * 100) + '%';
      if (dot) dot.style.background = (health && health.degraded) ? 'rgba(255,170,60,0.8)' : 'rgba(255,170,60,0.8)';
      if (stext) stext.textContent = (health && health.degraded) ? 'degraded' : 'connecting';
      if (pill) pill.classList.toggle('warn', (d.bar || 0) > 0.8);
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
  let mx = 0, my = 0, gx = 0, gy = 0, raf = null, last = 0;
  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; }, { passive: true });
  // Transform-based, throttled to ~30fps: never touch left/top (layout thrash).
  function anim() {
    raf = requestAnimationFrame(anim);
    const now = performance.now();
    if (now - last < 33) return;
    last = now;
    if (document.hidden) return;
    gx += (mx - gx) * 0.06; gy += (my - gy) * 0.06;
    glow.style.transform = `translate3d(${gx - glow.offsetWidth / 2}px, ${gy - glow.offsetHeight / 2}px, 0)`;
  }
  anim();
})();

// ================================================
// TOASTS
// ================================================
function toast(msg, type = 'ok') {
  const c = document.getElementById('toasts');
  if (!c) return;
  // Dedupe: identical toasts collapse into the newest one instead of stacking.
  const existing = Array.from(c.children).find(el => el.dataset.msg === msg);
  if (existing) existing.remove();
  const icons = { ok: 'fa-circle-check', err: 'fa-circle-xmark', info: 'fa-circle-info' };
  const t = document.createElement('div');
  t.className = `toast t-${type}`;
  t.dataset.msg = msg;
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

let _chatScrollRaf = null;
function scrollChat() {
  const area = document.getElementById('chat-scroll');
  if (!area) return;
  if (_chatScrollRaf) return;
  _chatScrollRaf = requestAnimationFrame(() => { _chatScrollRaf = null; area.scrollTop = area.scrollHeight; });
}

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
  if (/^agency(?:\s+(?:status|dashboard|overview|brief|briefing|report|monitor))?$/i.test(t) || /^(?:business|leads?|outreach|missions?)\s+(?:status|overview|report|dashboard|briefing)$/i.test(t)) {
    openPanel('agency');
    return { handled: true, response: 'Agency OS dashboard open. Monitoring your agents and leads live, boss.' };
  }
  if (/^agency\s+(?:new\s+)?mission$/i.test(t) || /^launch\s+(?:a\s+)?(?:new\s+)?mission$/i.test(t)) {
    openPanel('agency');
    return { handled: true, response: 'Use the NEW MISSION form in the Agency OS panel — set city, category and lead limit, boss.' };
  }
  if (/^agency\s+outreach$/i.test(t) || /^(?:review|pending|send)\s+(?:outreach|leads)$/i.test(t)) {
    openPanel('agency');
    return { handled: true, response: 'Outreach queue is in the Agency OS panel under PIPELINE and AGENT ROSTER, boss.' };
  }
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
    'notes': 'fa-note-sticky NOTES',
    'agency': 'fa-building AGENCY OS',
    'agent': 'fa-robot VISION AGENT'
  };
  const titleStr = titles[name] || `fa-circle ${name.toUpperCase()}`;
  const parts = titleStr.split(' ');
  const iconClass = parts[0];
  const titleText = parts.slice(1).join(' ');
  // Maximize sits next to close: a 420px panel cannot show a process table or a
  // week of weather properly, so the wide layout has to be reachable from the
  // panel itself. PanelWin owns the geometry, this button just calls it.
  panel.innerHTML = `<div class="panel-hdr" data-drag="true"><h3><i class="fa-solid ${iconClass}"></i> ${titleText}</h3><div class="panel-hdr-tools"><button class="panel-max" aria-pressed="false" title="Maximize panel" onclick="event.stopPropagation();PanelWin.toggle('${name}')"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></button><button class="panel-close" onclick="closePanel('${name}')" title="Close panel">&times;</button></div></div><div class="panel-body" id="panel-body-${name}"><div class="panel-empty">Loading...</div></div>`;
  container.appendChild(panel);
  openPanels.add(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.add('active');
  loadPanelContent(name);
  sfx.confirm();
  initDraggable(panel);
  const panelSpeak = { weather: 'Opening the weather panel, Boss.', system: 'Opening the system info panel, Boss.', processes: 'Opening the process monitor, Boss.', emails: 'Opening your emails, Boss.', vault: 'Opening the memory vault, Boss.', clipboard: 'Opening the clipboard panel, Boss.', settings: 'Opening settings, Boss.', commands: 'Here is everything I can do, Boss.', activity: 'Opening PC activity monitor, Boss.', files: 'Opening the file explorer, Boss.', notes: 'Opening your notes, Boss.', agency: 'Opening Agency OS, Boss.', agent: 'Vision agent on standby. Give me a goal, Boss.' };
  if (panelSpeak[name] && typeof speakTrigger === 'function') speakTrigger(panelSpeak[name]);
}

function closePanel(name) {
  const panel = document.querySelector(`.panel[data-panel="${name}"]`);
  if (!panel) return;
  const cleanup = dragCleanupFns.get(panel);
  if (cleanup) { cleanup(); dragCleanupFns.delete(panel); }
  // Stop this panel's poller explicitly. The sweep in stopPanelTimerFor only
  // runs when some panel closes and cannot catch a timer whose body node is
  // about to be detached along with the panel itself.
  stopPanelTimer(name);
  delete panelState[name];
  // The agency poller lives outside panelTimers, so it needs stopping here too.
  // Without this it keeps hitting /api/agency once a second until pollAgency
  // notices its body node is gone.
  if (name === 'agency' && agencyPollTimer) { clearInterval(agencyPollTimer); agencyPollTimer = null; }
  if (name === 'agency') agencyLeadHistory = [];
  // Drop the maximized state too, otherwise the next panel to open would be
  // refused as "one at a time" by a window that no longer exists.
  if (typeof PanelWin !== 'undefined') PanelWin.forget(panel);
  panel.classList.add('closing');
  setTimeout(() => panel.remove(), 200);
  openPanels.delete(name);
  document.querySelector(`.dock-btn[data-panel="${name}"]`)?.classList.remove('active');
  // Sweep any timer whose panel has since gone, so a crash in one loader
  // cannot leave the whole set running.
  stopPanelTimerFor();
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
    // Never start a drag from a header control, and never drag a maximized
    // panel: it is pinned to the viewport, so a drag would silently move it
    // away from the full-bleed geometry PanelWin just applied.
    if (e.target.closest('.panel-close, .panel-max')) return;
    if (typeof PanelWin !== 'undefined' && PanelWin.isMaximized(panel)) return;
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
    if (e.target.closest('.panel-close, .panel-max')) return;
    if (typeof PanelWin !== 'undefined' && PanelWin.isMaximized(panel)) return;
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
    case 'agency': return loadAgencyPanel(body);
    case 'agent': return loadAgentPanel(body);
  }
}

// ================================================
// AGENCY OS PANEL (Jarvis business monitoring)
// ================================================
let agencyPollTimer = null;
// Rolling total-leads samples for the agency trend sparkline. Module scoped so
// it survives the 4s re-render, and cleared whenever the panel opens or closes.
let agencyLeadHistory = [];

function toggleAgencyPanel(show) {
  if (show) {
    if (!openPanels.has('agency')) openPanel('agency');
  } else {
    if (openPanels.has('agency')) closePanel('agency');
  }
}

async function loadAgencyPanel(el) {
  el.innerHTML = '<div class="panel-empty">Connecting to Agency OS...</div>';
  if (agencyPollTimer) clearInterval(agencyPollTimer);
  // Leads history belongs to the panel, not the page: reopening the panel
  // starts a fresh trend rather than resurrecting a stale one from last time.
  agencyLeadHistory = [];
  await pollAgency();
  agencyPollTimer = setInterval(pollAgency, 4000);
}

async function pollAgency() {
  const el = document.getElementById('panel-body-agency');
  if (!el) { if (agencyPollTimer) clearInterval(agencyPollTimer); return; }
  try {
    const res = await fetch('/api/agency');
    const d = await res.json();
    if (!d.success || !d.state) {
      el.innerHTML = `<div class="panel-empty">Agency OS is offline.<br><span style="font-size:9px;color:var(--txt3);margin-top:6px;display:inline-block;">Start the agency-os server (localhost:3200) to resume monitoring.</span></div>`;
      return;
    }
    renderAgencyPanel(el, d.state);
  } catch(e) {
    el.innerHTML = '<div class="panel-empty">Agency OS unreachable.</div>';
  }
}

function renderAgencyPanel(el, state) {
  const stats = state.stats || {};
  const missions = state.missions || [];
  const logs = state.logs || [];
  const runs = state.agentRuns || [];
  const byStage = stats.byStage || {};

  const n = (v) => (typeof v === 'number' && isFinite(v) ? v : 0);

  // ---- headline rings ----------------------------------------------------
  // The old panel opened on eight number cards, all the same shape, none of
  // them saying anything about proportion. Four rings that encode "how full is
  // this" get the same information across in far less space.
  const online = n(stats.agentsOnline);
  const working = n(stats.agentsWorking);
  const leadsToday = n(stats.leadsToday);
  const totalLeads = n(stats.totalLeads);
  const pending = n(stats.pendingApproval);
  const sent = n(stats.sentOutreach);
  const runningMissions = missions.filter(m => (m.status || '').toLowerCase() === 'running').length;

  // Outreach outcomes as a funnel: contacted -> sent, and whatever is still
  // sitting in approval. Shows the drop-off, not just the totals.
  const outreachAll = state.outreach || [];
  const byOutreachStatus = (st) => outreachAll.filter(o => (o.status || '').toLowerCase() === st).length;
  const outreachTouched = outreachAll.length || 1;
  const replied = byOutreachStatus('replied') + byOutreachStatus('responded');

  const hero = Viz.hero([
    Viz.ring(online ? Math.min(100, (working / online) * 100) : 0, {
      label: 'AGENTS BUSY', labelText: working + '/' + online, warn: false, crit: false
    }),
    Viz.ring(leadsToday ? Math.min(100, (leadsToday / Math.max(totalLeads, leadsToday)) * 100) : 0, {
      label: 'TODAY OF TOTAL', labelText: leadsToday + '/' + totalLeads, warn: false, crit: false
    }),
    Viz.ring((replied / outreachTouched) * 100, {
      label: 'REPLY RATE', labelText: Math.round((replied / outreachTouched) * 100) + '%', warn: false, crit: false
    }),
    Viz.ring(outreachTouched ? (pending / outreachTouched) * 100 : 0, {
      // This one IS a queue that can back up, so it keeps the severity ramp.
      label: 'AWAITING YOU', labelText: String(pending), warn: 25, crit: 60
    })
  ], {
    title: 'AGENCY OS',
    sub: online ? (working ? working + ' agent' + (working === 1 ? '' : 's') + ' working, ' + runningMissions + ' mission' + (runningMissions === 1 ? '' : 's') + ' running' : 'all agents idle') : 'no agents reporting'
  });

  const stat = (label, val, icon, color) => `
    <div style="flex:1;min-width:84px;padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.03);border:1px solid rgba(139,104,255,0.18);text-align:center;">
      <div style="font-family:var(--orbitron);font-size:16px;color:${color};text-shadow:0 0 14px ${color};">${Viz.esc(val)}</div>
      <div style="font-family:var(--mono);font-size:7px;color:var(--txt3);letter-spacing:1px;margin-top:2px;"><i class="fa-solid ${icon}"></i> ${label}</div>
    </div>`;

  const stageNames = { 'lead_finder':'LEAD FINDER','outreach_writer':'OUTREACH WRITER','contact_builder':'CONTACT BUILDER','response_manager':'RESPONSE MGR','app_checker':'APP CHECKER','researcher':'RESEARCHER' };
  const stageKeys = Object.keys(byStage);
  // One stacked bar instead of a hand-rolled row per stage: the point of this
  // data is the shape of the pipeline, and a stack shows the shape directly.
  const pipeline = stageKeys.length
    ? Viz.stack(stageKeys.map((k, i) => ({
        label: stageNames[k] || k.toUpperCase(),
        value: n(byStage[k]),
        color: 'hsl(' + Math.round((i / stageKeys.length) * 300) + ',70%,62%)'
      })))
    : '<div class="panel-empty" style="padding:8px;">No pipeline data yet.</div>';

  // Per-stage detail is still useful, but as meters against the busiest stage
  // so the bars are comparable instead of each scaled to its own value.
  const stageMax = Math.max(1, ...stageKeys.map(k => n(byStage[k])));
  const stageRows = stageKeys.map(k => {
    const v = n(byStage[k]);
    return Viz.bar(v, {
      max: stageMax,
      label: stageNames[k] || k.toUpperCase(),
      valueText: String(v),
      warn: false, crit: false
    });
  }).join('');

  const agentRows = runs.slice(0, 12).map(r => {
    const st = (r.status || 'idle').toLowerCase();
    const color = st === 'working' ? 'var(--gold)' : st === 'error' ? '#ff5f56' : st === 'done' ? '#4ade80' : 'var(--txt3)';
    const name = String(r.agent_id || 'agent').split('_').map(w => (w[0] || '').toUpperCase() + w.slice(1)).join(' ');
    const stage = stageNames[r.stage] || (r.stage || '').toUpperCase();
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-radius:6px;background:rgba(255,255,255,0.02);margin-bottom:4px;">
      <div style="font-family:var(--mono);font-size:9px;color:var(--txt2);">${Viz.esc(name)} ${stage ? `<span style="color:var(--txt3);font-size:7px;">· ${Viz.esc(stage)}</span>` : ''}</div>
      <span style="font-family:var(--mono);font-size:7px;letter-spacing:1px;color:${color};"><i class="fa-solid fa-circle" style="font-size:5px;vertical-align:middle;"></i> ${Viz.esc(st.toUpperCase())}</span>
    </div>`;
  }).join('') || '<div style="font-size:9px;color:var(--txt3);padding:4px 0;">No agent runs recorded yet.</div>';

  const missionRows = missions.slice(0, 6).map(m => {
    const st = (m.status || '').toLowerCase();
    const color = st === 'running' ? 'var(--gold)' : st === 'done' ? '#4ade80' : st === 'error' ? '#ff5f56' : 'var(--txt3)';
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px;background:rgba(255,255,255,0.02);margin-bottom:3px;">
      <div style="font-family:var(--mono);font-size:8px;color:var(--txt2);">#${Viz.esc(m.id)} ${Viz.esc(m.city || '—')} <span style="color:var(--txt3);">· ${Viz.esc(m.category || '')} · n=${Viz.esc(m.limit_n || 0)}</span></div>
      <span style="font-family:var(--mono);font-size:7px;color:${color};">${Viz.esc(st.toUpperCase())}</span>
    </div>`;
  }).join('') || '<div style="font-size:9px;color:var(--txt3);padding:4px 0;">No missions yet.</div>';

  const logRows = logs.slice(0, 7).map(l => {
    const txt = l.message || l.log || l.text || JSON.stringify(l).slice(0, 90) || '';
    const time = l.timestamp || l.time || '';
    return `<div style="font-family:var(--mono);font-size:8px;color:var(--txt2);padding:3px 0;border-bottom:1px dashed rgba(255,255,255,0.05);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
      ${time ? `<span style="color:var(--txt3);">${Viz.esc(String(time).slice(11, 19) || time)}</span> ` : ''}${Viz.esc(txt)}
    </div>`;
  }).join('') || '<div style="font-size:9px;color:var(--txt3);padding:4px 0;">No recent activity.</div>';

  const errorAgents = runs.filter(r => (r.status || '').toLowerCase() === 'error').map(r => r.agent_id).join(', ');

  const pendingOutreach = outreachAll.filter(o => (o.status || '').toLowerCase() === 'pending_approval');
  const outreachRows = pendingOutreach.slice(0, 4).map(o => {
    const channelIcon = o.channel === 'whatsapp' ? 'fa-comment-dots' : o.channel === 'linkedin' ? 'fa-linkedin' : 'fa-envelope';
    const preview = o.subject ? `${o.subject} — ` : '';
    return `<div style="padding:6px 8px;border-radius:6px;background:rgba(251,191,36,0.05);border:1px solid rgba(251,191,36,0.25);margin-bottom:5px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
        <span style="font-family:var(--mono);font-size:8px;color:var(--gold);"><i class="fa-solid ${channelIcon}"></i> #${Viz.esc(o.id)} · ${Viz.esc((o.channel || '').toUpperCase())} · inst #${Viz.esc(o.institution_id)}</span>
        <span style="font-family:var(--mono);font-size:7px;color:var(--txt3);">${Viz.esc(String(o.created_at || '').slice(0, 10))}</span>
      </div>
      <div style="font-family:var(--mono);font-size:8px;color:var(--txt2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(preview)}${escHtml((o.body || '').slice(0, 110))}</div>
      <div style="display:flex;gap:6px;margin-top:5px;">
        <button onclick="agencyOutreachAction(${Viz.esc(o.id)},'approve')" style="flex:1;padding:3px 0;background:rgba(74,222,128,0.15);border:1px solid rgba(74,222,128,0.3);border-radius:4px;color:#4ade80;font-family:var(--mono);font-size:7px;font-weight:700;cursor:pointer;">APPROVE</button>
        <button onclick="agencyOutreachAction(${Viz.esc(o.id)},'reject')" style="flex:1;padding:3px 0;background:rgba(255,95,86,0.15);border:1px solid rgba(255,95,86,0.3);border-radius:4px;color:#ff5f56;font-family:var(--mono);font-size:7px;font-weight:700;cursor:pointer;">REJECT</button>
        <button onclick="agencyOutreachAction(${Viz.esc(o.id)},'send')" style="flex:1;padding:3px 0;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);border-radius:4px;color:#38bdf8;font-family:var(--mono);font-size:7px;font-weight:700;cursor:pointer;">SEND</button>
      </div>
    </div>`;
  }).join('') || '<div style="font-size:9px;color:var(--txt3);padding:4px 0;">Queue clear — nothing awaiting approval.</div>';

  el.innerHTML = hero +
    '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">' +
      stat('AGENTS', stats.agentsOnline ?? '—', 'fa-microchip', 'var(--gold)') +
      stat('WORKING', stats.agentsWorking ?? '—', 'fa-sync fa-spin', 'var(--gold)') +
      stat('LEADS TODAY', stats.leadsToday ?? '—', 'fa-bullseye', '#4ade80') +
      stat('TOTAL LEADS', stats.totalLeads ?? '—', 'fa-database', '#4ade80') +
      stat('PENDING', stats.pendingApproval ?? '—', 'fa-clock', '#fbbf24') +
      stat('SENT', stats.sentOutreach ?? '—', 'fa-paper-plane', 'var(--silver)') +
      stat('MISSIONS', runningMissions, 'fa-route', '#38bdf8') +
      stat('MEETINGS', stats.meetings ?? '—', 'fa-handshake', '#c084fc') +
    '</div>' +
    (errorAgents ? `<div style="margin-bottom:8px;padding:6px 8px;border-radius:6px;background:rgba(255,95,86,0.08);border:1px solid rgba(255,95,86,0.3);font-family:var(--mono);font-size:8px;color:#ff5f56;"><i class="fa-solid fa-triangle-exclamation"></i> AGENTS ERRORING: ${Viz.esc(errorAgents)}</div>` : '') +

    Viz.section('LEADS OVER TIME', '<canvas id="agency-lead-spark" width="520" height="64"></canvas>', 'fa-chart-line') +
    Viz.section('PIPELINE BY STAGE', pipeline + (stageRows ? '<div style="margin-top:12px">' + stageRows + '</div>' : ''), 'fa-chart-simple') +
    Viz.section('OUTREACH FUNNEL', Viz.stack([
      { label: 'Sent', value: sent, color: '#38bdf8' },
      { label: 'Awaiting approval', value: pending, color: '#fbbf24' },
      { label: 'Replied', value: replied, color: '#4ade80' },
      { label: 'Other', value: Math.max(0, outreachAll.length - sent - pending - replied), color: 'rgba(255,255,255,0.22)' }
    ], { empty: 'No outreach recorded yet.' }), 'fa-funnel') +
    Viz.section('AGENT ROSTER', agentRows, 'fa-robot') +
    Viz.section('ACTIVE MISSIONS', missionRows, 'fa-route') +
    Viz.section('OUTREACH REVIEW (' + pendingOutreach.length + ')', outreachRows, 'fa-envelope-open-text') +
    Viz.section('LIVE ACTIVITY', logRows, 'fa-wave-square') +

    `<div style="display:flex;gap:8px;">
      <button onclick="agencyRefresh()" style="flex:1;padding:7px;background:rgba(139,104,255,0.14);border:1px solid rgba(139,104,255,0.3);border-radius:6px;color:var(--gold);font-family:var(--mono);font-size:8px;font-weight:700;cursor:pointer;"><i class="fa-solid fa-rotate"></i> REFRESH</button>
      <button onclick="document.getElementById('agency-mission-form').style.display = document.getElementById('agency-mission-form').style.display==='none'?'block':'none'" style="flex:1;padding:7px;background:rgba(56,189,248,0.14);border:1px solid rgba(56,189,248,0.3);border-radius:6px;color:#38bdf8;font-family:var(--mono);font-size:8px;font-weight:700;cursor:pointer;"><i class="fa-solid fa-bullseye"></i> NEW MISSION</button>
    </div>
    <div id="agency-mission-form" style="display:none;margin-top:10px;padding:10px;border:1px solid rgba(56,189,248,0.3);border-radius:8px;background:rgba(56,189,248,0.06);">
      <div style="display:flex;gap:6px;margin-bottom:6px;">
        <input id="ag-city" placeholder="City" value="Patna" style="flex:1;padding:5px 7px;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.12);color:#fff;font-family:var(--mono);font-size:9px;border-radius:6px;">
        <input id="ag-cat" placeholder="Category" value="School" style="flex:1;padding:5px 7px;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.12);color:#fff;font-family:var(--mono);font-size:9px;border-radius:6px;">
        <input id="ag-limit" type="number" placeholder="Limit" value="10" style="width:60px;padding:5px 7px;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.12);color:#fff;font-family:var(--mono);font-size:9px;border-radius:6px;">
      </div>
      <button onclick="agencySubmitMission()" style="width:100%;padding:6px;background:rgba(56,189,248,0.85);border:none;border-radius:6px;color:#04141f;font-family:var(--mono);font-size:9px;font-weight:800;cursor:pointer;">LAUNCH MISSION</button>
    </div>`;

  // The leads trend accumulates across polls rather than being redrawn from
  // scratch, so the line actually grows instead of resetting every 4 seconds.
  // Redraw from the full history each time (the canvas is recreated with the
  // panel body) but only append a sample when the total actually moved.
  agencyLeadHistory = agencyLeadHistory || [];
  const lastSample = agencyLeadHistory[agencyLeadHistory.length - 1];
  if (lastSample !== totalLeads) {
    agencyLeadHistory.push(totalLeads);
    while (agencyLeadHistory.length > 40) agencyLeadHistory.shift();
  }
  Viz.spark('agency-lead-spark', agencyLeadHistory, { limit: 40 });
}

function agencyRefresh() {
  pollAgency();
  sfx?.click && sfx.click();
}

async function agencySubmitMission() {
  const city = document.getElementById('ag-city')?.value.trim() || 'Patna';
  const category = document.getElementById('ag-cat')?.value.trim() || 'School';
  const limit = parseInt(document.getElementById('ag-limit')?.value, 10) || 10;
  try {
    const res = await fetch('/api/agency/mission', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city, category, limit })
    });
    const d = await res.json();
    if (d.success) {
      toast(`Mission launched in ${city}`, 'ok');
      const f = document.getElementById('agency-mission-form'); if (f) f.style.display = 'none';
      pollAgency();
    } else {
      toast(d.message || 'Failed to launch mission', 'err');
    }
  } catch(e) { toast('Agency offline', 'err'); }
}

async function agencyOutreachAction(id, action) {
  try {
    const res = await fetch('/api/agency/outreach', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, action })
    });
    const d = await res.json();
    if (d.success) {
      toast(`Outreach #${id} ${action}d`, 'ok');
      pollAgency();
    } else {
      toast(d.message || 'Action failed', 'err');
    }
  } catch(e) { toast('Agency offline', 'err'); }
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
        <div class="vt"><strong style="color:var(--accent,var(--gold));">${Viz.esc(r.trigger)}</strong> &rarr; ${Viz.esc(r.reply)}</div>
        <button class="vx" onclick="deleteTrainingItem('rule',${JSON.stringify(String(r.trigger))})">&times;</button>
      </div>
    `).join('') || '<div style="font-size:9px; color:var(--txt3); padding:4px 0;">No custom rules trained yet.</div>';

    const macrosHtml = (t.macros || []).map(m => `
      <div class="vault-item">
        <div class="vt"><strong style="color:var(--silver);">${Viz.esc(m.trigger)}</strong> = [${Viz.esc((m.commands || []).join(', '))}]</div>
        <button class="vx" onclick="deleteTrainingItem('macro',${JSON.stringify(String(m.trigger))})">&times;</button>
      </div>
    `).join('') || '<div style="font-size:9px; color:var(--txt3); padding:4px 0;">No voice macros trained yet.</div>';

    el.innerHTML =
      Viz.hero([
        Viz.ring((t.rules || []).length, { max: Math.max((t.rules || []).length, 8), label: 'RULES', labelText: String((t.rules || []).length) }),
        Viz.ring((t.macros || []).length, { max: Math.max((t.macros || []).length, 8), label: 'MACROS', labelText: String((t.macros || []).length) })
      ], { title: 'AI TRAINING HUB', sub: 'teaching JENNY your language' }) +
      Viz.section('CAPACITY', Viz.stack([
        { label: 'Custom rules', value: (t.rules || []).length, color: 'var(--accent, #6d8bff)' },
        { label: 'Voice macros', value: (t.macros || []).length, color: '#22d3ee' }
      ], { empty: 'Nothing trained yet — add a rule below.' }), 'fa-brain') +
      `<div style="margin-bottom:12px; padding:10px; background:rgba(255,255,255,0.03); border:1px solid var(--accent-edge,rgba(139,104,255,0.2)); border-radius:10px;">
         <div class="setting-row">
           <label>USER NAME</label>
           <input type="text" id="train-name-input" value="${Viz.esc(t.name || '')}" placeholder="e.g. BOSS" style="width:140px; padding:4px 8px; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.12); color:#fff; font-family:var(--mono); font-size:10px; border-radius:6px;">
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
         <button onclick="saveProfileTraining()" style="margin-top:8px; width:100%; padding:6px; background:rgba(var(--accent-rgb,109,139,255),0.15); border:1px solid var(--accent-edge,rgba(139,139,255,0.3)); border-radius:6px; color:var(--accent,var(--gold)); font-family:var(--mono); font-size:9px; font-weight:700; cursor:pointer;">
           <i class="fa-solid fa-floppy-disk"></i> SAVE PROFILE TRAINING
         </button>
       </div>` +
      Viz.section('CUSTOM VOICE RULES (' + (t.rules || []).length + ')', rulesHtml, 'fa-bolt') +
      Viz.section('VOICE MACROS (' + (t.macros || []).length + ')', macrosHtml, 'fa-terminal');
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
// VISION AGENT PANEL — drive the PC by sight
// ================================================
// The panel is a monitor, not a controller: start/stop/kill are the only
// controls, and everything else it shows is what the agent actually did.
// Static chrome is built once and the poll updates fields in place, so the
// goal input never loses focus or its text while the agent is running.
let agentPendingGoal = '';
let agentFrameSeen = '';

async function loadAgentPanel(el) {
  el.innerHTML = `
    <div class="agent-shell">
      <div class="agent-head">
        <span class="agent-badge" id="agent-badge">IDLE</span>
        <span class="agent-meta" id="agent-meta">give it a goal</span>
      </div>
      <div class="agent-goal-row">
        <input type="text" id="agent-goal" class="agent-goal" autocomplete="off"
               placeholder="open my downloads folder and open the newest PDF"
               onkeydown="if(event.key==='Enter')agentStart()">
        <button class="agent-btn primary" onclick="agentStart()" title="Start the agent">
          <i class="fa-solid fa-play"></i> START</button>
      </div>
      <div class="agent-btns">
        <button class="agent-btn" onclick="agentStep()" title="Run exactly one see-think-act step">
          <i class="fa-solid fa-shoe-prints"></i> STEP</button>
        <button class="agent-btn stop" onclick="agentStop()" title="Stop after the current action">
          <i class="fa-solid fa-stop"></i> STOP</button>
        <button class="agent-btn kill" onclick="agentKill()" title="Kill switch — halts everything until re-armed">
          <i class="fa-solid fa-burst"></i> KILL</button>
        <button class="agent-btn" onclick="agentReset()" title="Clear the kill switch and re-arm">
          <i class="fa-solid fa-rotate-left"></i> ARM</button>
      </div>
      <div class="agent-screen">
        <img id="agent-frame" alt="what the agent sees" src="/api/agent/frame">
        <span class="agent-live hidden" id="agent-live"><span class="agent-live-dot"></span>SEEING</span>
      </div>
      <div class="agent-stats" id="agent-stats">step 0/0 &middot; ok 0 &middot; failed 0</div>
      <div class="agent-log" id="agent-log"><div class="panel-empty">No steps yet.</div></div>
    </div>`;
  if (agentPendingGoal) {
    const g = document.getElementById('agent-goal');
    if (g) g.value = agentPendingGoal;
    agentPendingGoal = '';
  }
  await pollAgent();
  startPanelTimer('agent', pollAgent, 1400);
}

async function pollAgent() {
  const badge = document.getElementById('agent-badge');
  if (!badge) { stopPanelTimer('agent'); return; }
  let s;
  try {
    const r = await fetch('/api/agent/status', { cache: 'no-store' });
    s = await r.json();
  } catch (e) { return; }
  if (!s || !document.getElementById('agent-badge')) return;

  const st = (s.status || 'idle').toLowerCase();
  badge.textContent = st.toUpperCase();
  badge.className = 'agent-badge agent-' + st;
  const meta = document.getElementById('agent-meta');
  if (meta) meta.textContent = s.goal
    ? `${s.goal}` + (s.killed ? '  ·  KILLED' : '')
    : (s.hotkey ? `kill switch: ${s.hotkey}` : 'give it a goal');

  const live = document.getElementById('agent-live');
  if (live) live.classList.toggle('hidden', st !== 'running');

  const stats = document.getElementById('agent-stats');
  if (stats) {
    const c = s.counts || {};
    stats.innerHTML = `step <b>${(s.steps && s.steps.done) || 0}/${(s.steps && s.steps.of) || 0}</b>`
      + ` &middot; ok <b>${c.ok || 0}</b> &middot; failed <b>${c.failed || 0}</b>`
      + (s.model ? ` &middot; <span class="agent-model">${Viz.esc(s.model)}</span>` : '')
      + (s.last_error ? ` &middot; <span class="agent-err">${Viz.esc(s.last_error)}</span>` : '');
  }

  const img = document.getElementById('agent-frame');
  if (img && s.frame_ts && s.frame_ts !== agentFrameSeen) {
    agentFrameSeen = s.frame_ts;
    img.src = '/api/agent/frame?t=' + encodeURIComponent(s.frame_ts);
  }

  const log = document.getElementById('agent-log');
  if (log) {
    const rows = (s.log || []).slice().reverse();
    log.innerHTML = rows.length
      ? rows.map(e => `<div class="agent-log-row${e.ok ? '' : ' bad'}">
            <span class="n">#${e.n | 0}</span><span class="tm">${Viz.esc(e.t || '')}</span>
            <span class="ac">${Viz.esc(e.action || '')}</span>
            <span class="nt">${Viz.esc(e.note || '')}</span></div>`).join('')
      : '<div class="panel-empty">No steps yet.</div>';
  }
}

async function agentPost(path, body) {
  try {
    const r = await fetch('/api/agent/' + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    });
    const d = await r.json();
    if (d && d.ok === false) toast(d.error || 'Agent refused that.', 'err');
    else toast(d.message || ('Agent ' + path + ' ok'), 'ok');
    pollAgent();
    return d;
  } catch (e) { toast('Agent command failed', 'err'); return null; }
}

function agentStart() {
  const g = document.getElementById('agent-goal')?.value.trim();
  if (!g) { toast('Give the agent a goal first', 'err'); return; }
  agentPost('start', { goal: g });
}

function agentStop() { agentPost('stop', { reason: 'panel' }); }
function agentKill() { agentPost('kill', { reason: 'panel' }); }
function agentReset() { agentPost('reset', {}); }

async function agentStep() {
  const g = document.getElementById('agent-goal')?.value.trim();
  if (!g) { toast('Give the agent a goal first', 'err'); return; }
  try {
    const r = await fetch('/api/agent/step', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal: g })
    });
    const d = await r.json();
    if (d && d.ok === false) toast(d.error || 'Step failed', 'err');
    agentFrameSeen = '';
    pollAgent();
  } catch (e) { toast('Step failed', 'err'); }
}

// ================================================
// PANEL LOADERS
// ================================================
// Every panel below opens on a Viz hero - a strip of dials answering "is
// anything wrong right now" - before the detail rows. The old panels were a
// flat list of label/value pairs, so a glance told you nothing and you had to
// read and compare each number by hand.
function makeCircularGauge(pct, label) {
  // Kept for the callers that still ask for the old 52px gauge; new panels use
  // Viz.ring, which carries a tick scale and a severity colour.
  return (typeof Viz !== 'undefined')
    ? Viz.ring(pct, { size: 62, stroke: 5, label: label })
    : `<div class="circular-gauge"><div class="gauge-label">${Math.round(pct)}%</div></div><div class="stat-lbl">${label}</div>`;
}

// Shared sparkline block. `series` is an array of numbers; a short or empty
// series degrades to a flat line rather than an error, because these panels
// render on first paint before any poll has come back.
function sparkBlock(caption, valueText, series, opts) {
  opts = opts || {};
  const id = 'vizspk-' + Math.random().toString(36).slice(2, 9);
  return '' +
    '<div class="viz-spark-wrap">' +
      '<div class="viz-spark-cap"><span>' + (opts.icon ? '<i class="fa-solid ' + opts.icon + '"></i> ' : '') +
        Viz.esc(caption) + '</span><b>' + Viz.esc(valueText) + '</b></div>' +
      '<canvas class="viz-spark" id="' + id + '" width="600" height="92"></canvas>' +
    '</div>';
}

// Sparklines are painted after the markup lands, so the canvas always has a
// size. Queued as a microtask: the browser has not necessarily laid out the
// freshly-assigned innerHTML yet, and drawing into a 0x0 canvas is a silent
// no-op that would leave a permanently blank chart.
function paintSparks(root, map) {
  if (typeof Viz === 'undefined' || !root) return;
  requestAnimationFrame(() => {
    Object.keys(map || {}).forEach(key => {
      const spec = map[key];
      const handle = Viz.spark(spec.id, spec.data, spec.opts);
      if (handle && spec.onHandle) spec.onHandle(handle);
    });
  });
}

async function loadActivityPanel(el) {
  el.innerHTML = '<div class="panel-empty">Scanning...</div>';
  try {
    const res = await fetch('/api/system-status');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Failed to load.</div>'; return; }
    const cpu = d.cpu?.usage || 0, ram = d.ram?.usage || 0, disk = d.disk?.usage || 0;
    const bat = d.battery?.level ?? 0;
    const charging = !!d.battery?.charging;
    const uptimeH = d.uptime ? Math.floor(d.uptime / 3600) : 0;
    const uptimeM = d.uptime ? Math.floor((d.uptime % 3600) / 60) : 0;
    const cores = d.cpu?.cores || 0;

    el.innerHTML =
      Viz.hero([
        Viz.ring(cpu, { label: 'CPU', sub: cores ? cores + 'C' : '' }),
        Viz.ring(ram, { label: 'RAM' }),
        Viz.ring(disk, { label: 'DISK' }),
        Viz.ring(Math.round(bat), {
          label: 'POWER',
          labelText: charging ? 'CHG' : Math.round(bat) + '%',
          color: charging ? '#4ade80' : undefined
        })
      ], { sub: d.hostname || '' }) +
      Viz.section('LIVE TELEMETRY', '<div id="panel-act-sparks"></div>', 'fa-wave-square') +
      Viz.section('MACHINE', [
        Viz.bar(cpu, { label: 'CPU load', valueText: cpu + '%' }),
        Viz.bar(ram, { label: 'Memory', valueText: `${d.ram?.usedMB || 0} / ${d.ram?.totalMB || 0} MB` }),
        Viz.bar(disk, { label: 'Disk used', valueText: d.disk?.free ? d.disk.free + ' free' : disk + '%' }),
      ].join(''), 'fa-microchip') +
      `<div class="panel-row"><span class="lbl">UPTIME</span><span class="val">${uptimeH}h ${uptimeM}m</span></div>
       <div class="panel-row"><span class="lbl">HOST</span><span class="val">${Viz.esc(d.hostname || '---')}</span></div>
       <div class="panel-row"><span class="lbl">PLATFORM</span><span class="val">${Viz.esc(d.platform || '---')}</span></div>
       <div class="panel-row"><span class="lbl">CPU MODEL</span><span class="val" style="font-size:8px">${Viz.esc(d.cpu?.model || '---')}</span></div>`;

    // Roll a short in-panel history so the sparklines have something to show on
    // the first visit instead of a single lonely point.
    const hist = panelHistory('activity', { cpu: [], ram: [], disk: [], net: [] }, 40);
    pushActivitySample(hist, { cpu, ram, disk, net: d.net?.usage || 0 });
    const host = document.getElementById('panel-act-sparks');
    if (host) {
      host.innerHTML =
        sparkBlock('CPU', cpu + '%', hist.cpu, { icon: 'fa-microchip' }) +
        sparkBlock('RAM', ram + '%', hist.ram, { icon: 'fa-memory' }) +
        sparkBlock('DISK', disk + '%', hist.disk, { icon: 'fa-hard-drive' }) +
        sparkBlock('NETWORK', (d.net?.speed || '--'), hist.net, { icon: 'fa-wifi' });
      paintSparks(host, {
        cpu: { id: host.querySelector('.viz-spark').id, data: hist.cpu },
        ram: { id: host.querySelectorAll('.viz-spark')[1].id, data: hist.ram },
        disk: { id: host.querySelectorAll('.viz-spark')[2].id, data: hist.disk },
        net: { id: host.querySelectorAll('.viz-spark')[3].id, data: hist.net }
      });
    }
    // Keep the history moving while the panel stays open.
    startPanelTimer('activity', async () => {
      if (!document.getElementById('panel-body-activity')) { stopPanelTimer('activity'); return; }
      await loadActivityPanel(el);
    }, 5000);
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

// Tiny per-panel scratch store. The activity panel's sparklines need a rolling
// history, but there is nowhere sensible to keep it between renders except the
// page, and leaking one key per panel would outlive the panel itself.
const panelState = {};
function panelHistory(name, seed, limit) {
  if (!panelState[name]) panelState[name] = seed;
  return panelState[name];
}
function pushActivitySample(h, s) {
  ['cpu', 'ram', 'disk', 'net'].forEach(k => {
    h[k].push(Viz.num(s[k], 0));
    while (h[k].length > 40) h[k].shift();
  });
}

// One named interval per panel, so re-opening a panel cannot leave a second
// poller running against the same DOM node.
const panelTimers = {};
function startPanelTimer(name, fn, ms) {
  stopPanelTimer(name);
  panelTimers[name] = setInterval(fn, ms);
}
function stopPanelTimer(name) {
  if (panelTimers[name]) { clearInterval(panelTimers[name]); delete panelTimers[name]; }
}
function stopPanelTimerFor(el) {
  // Best-effort sweep: any panel whose body node has gone away stops polling.
  Object.keys(panelTimers).forEach(name => {
    if (!document.getElementById('panel-body-' + name)) stopPanelTimer(name);
  });
}

async function loadSystemPanel(el) {
  el.innerHTML = '<div class="panel-empty">Reading hardware...</div>';
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'system-info' }) });
    const data = await res.json();
    if (!data.success) { el.innerHTML = '<div class="panel-empty">Failed.</div>'; return; }
    const i = data.info || {};
    // Processor and memory are the two numbers worth a dial; everything else is
    // an identifier, which a gauge cannot improve on.
    const memGb = Viz.num(String(i.memory || '').match(/([\d.]+)\s*GB/i)?.[1], 0);
    el.innerHTML =
      Viz.hero([
        Viz.ring(Viz.num(data.load, 0), { label: 'LOAD', sub: 'avg' }),
        Viz.ring(memGb, { max: 64, label: 'MEMORY', sub: memGb ? memGb + ' GB' : '' }),
      ], { title: 'HARDWARE', sub: Viz.esc(i.model_name || '') }) +
      Viz.section('PROCESSOR', [
        Viz.bar(100, { label: 'Speed', valueText: String(i.processor_speed || '---'), color: 'var(--accent, #6d8bff)' }),
      ].join(''), 'fa-microchip') +
      `<div class="panel-row"><span class="lbl">MODEL</span><span class="val">${Viz.esc(i.model_name || '---')}</span></div>
       <div class="panel-row"><span class="lbl">ID</span><span class="val" style="font-size:8px">${Viz.esc(i.model_identifier || '---')}</span></div>
       <div class="panel-row"><span class="lbl">CPU</span><span class="val" style="font-size:8px">${Viz.esc(i.processor_name || '---')}</span></div>
       <div class="panel-row"><span class="lbl">SPEED</span><span class="val">${Viz.esc(i.processor_speed || '---')}</span></div>
       <div class="panel-row"><span class="lbl">RAM</span><span class="val">${Viz.esc(i.memory || '---')}</span></div>
       <div class="panel-row"><span class="lbl">SERIAL</span><span class="val" style="font-size:8px">${Viz.esc(i.serial_number || '---')}</span></div>
       <div class="panel-row"><span class="lbl">OS</span><span class="val">${Viz.esc(i.productname || 'macOS')} ${Viz.esc(i.productversion || '')}</span></div>
       <div class="panel-row"><span class="lbl">BUILD</span><span class="val">${Viz.esc(i.buildversion || '---')}</span></div>`;
    if (typeof speakTrigger === 'function') { speakTrigger(`System info loaded, Boss. Powering ${i.processor_name || 'your PC'}.`); }
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

// Weather icon per condition code, so the panel leads with a picture rather
// than a temperature the user has to interpret.
function weatherIcon(condition, isDay) {
  const c = String(condition || '').toLowerCase();
  if (c.includes('thunder')) return 'fa-cloud-bolt';
  if (c.includes('drizzle') || c.includes('rain') || c.includes('shower')) return 'fa-cloud-rain';
  if (c.includes('snow') || c.includes('sleet') || c.includes('blizzard')) return 'fa-snowflake';
  if (c.includes('mist') || c.includes('fog') || c.includes('haze')) return 'fa-smog';
  if (c.includes('cloud')) return isDay ? 'fa-cloud-sun' : 'fa-cloud-moon';
  return isDay ? 'fa-sun' : 'fa-moon';
}

async function loadWeatherPanel(el) {
  el.innerHTML = '<div class="panel-empty">Reading the sky...</div>';
  try {
    const res = await fetch('/api/weather');
    const d = await res.json();
    if (!d.success) { el.innerHTML = '<div class="panel-empty">Unavailable.</div>'; return; }
    const temp = Viz.num(d.tempC, 0);
    // Feel-like matters more than raw temperature once you are past 30 or
    // below 10, so it earns a spot on the dial as the sub-label.
    const feels = Viz.num(d.feelsLikeC ?? d.feelsLike, NaN);
    const hum = Viz.num(d.humidity, 0);
    const wind = Viz.num(d.windKmH, 0);
    const forecast = d.forecast || [];

    el.innerHTML =
      '<div class="viz-hero glass-soft" style="text-align:center">' +
        '<div style="position:relative;z-index:1">' +
          '<div style="font-family:var(--mono);font-size:9px;letter-spacing:2px;color:rgba(255,255,255,0.5);text-transform:uppercase">' +
            Viz.esc(d.city || 'Unknown') + '</div>' +
          '<div style="display:flex;align-items:center;justify-content:center;gap:14px;margin:6px 0 2px">' +
            '<i class="fa-solid ' + weatherIcon(d.condition, d.isDay) + '" style="font-size:38px;color:var(--accent,var(--gold));filter:drop-shadow(0 0 16px rgba(var(--accent-rgb,109,139,255),0.65))"></i>' +
            Viz.arc(temp, { min: -20, max: 50, size: 138, labelText: Math.round(temp) + '°', sub: d.condition ? String(d.condition).slice(0, 18) : '' }) +
          '</div>' +
          '<div style="font-family:var(--mono);font-size:9px;color:rgba(255,255,255,0.55);letter-spacing:1px">' +
            (isFinite(feels) ? 'FEELS ' + Math.round(feels) + '° · ' : '') +
            (d.isDay ? 'DAYLIGHT' : 'NIGHT') + '</div>' +
        '</div>' +
      '</div>' +
      Viz.section('CONDITIONS', [
        Viz.bar(hum, { label: 'Humidity', valueText: hum + '%', warn: 75, crit: 92 }),
        Viz.bar(wind, { max: 60, label: 'Wind', valueText: Math.round(wind) + ' km/h', warn: 40, crit: 55 }),
        Viz.bar(d.isDay ? 100 : 0, { label: 'Daylight', valueText: d.isDay ? 'Yes' : 'No', color: d.isDay ? '#fbbf24' : '#6366f1' })
      ].join(''), 'fa-temperature-half') +
      (forecast.length ? Viz.section(
        (forecast.length > 1 ? '7' : '') + '-DAY OUTLOOK',
        // Each day is a band from its own low to its high with the midpoint
        // marked, so a warming or cooling trend is visible across the row
        // instead of being seven separate numbers to compare.
        forecast.map(f => {
          const lo = Viz.num(f.min, 0), hi = Viz.num(f.max, 0);
          return '<div style="margin-bottom:7px">' +
            '<div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:9px;color:rgba(255,255,255,0.6);margin-bottom:1px">' +
              '<span>' + Viz.esc(f.day || '') + '</span>' +
              '<span style="color:#fff"><i class="fa-solid ' + weatherIcon(f.condition, true) + '" style="font-size:8px;opacity:0.7"></i> ' +
              Math.round(lo) + '° / ' + Math.round(hi) + '°</span>' +
            '</div>' +
            Viz.range((lo + hi) / 2, lo, hi) +
          '</div>';
        }).join(''),
        'fa-calendar-days'
      ) : '') +
      `<div class="panel-row"><span class="lbl">CITY</span><span class="val">${Viz.esc(d.city)}</span></div>
       <div class="panel-row"><span class="lbl">CONDITION</span><span class="val">${Viz.esc(d.condition)}</span></div>`;

    if (typeof speakTrigger === 'function' && d.tempC !== '--') speakTrigger(`Weather in ${d.city}, ${d.condition}, ${d.tempC} degrees Celsius, wind ${d.windKmH} kilometers per hour, Boss.`);
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function loadEmailPanel(el) {
  el.innerHTML = '<div class="panel-empty">Fetching emails...</div>';
  try {
    const res = await fetch('/api/emails');
    const d = await res.json();
    if (!d.success || !d.emails?.length) { el.innerHTML = `<div class="panel-empty">${Viz.esc(d.message || 'No emails found.')}</div>`; return; }
    const emails = d.emails;
    // Bucket by rough age so the header dials say something about recency
    // rather than just restating the count.
    const now = Date.now();
    const ageDays = (m) => {
      const t = Date.parse(m || '');
      return isFinite(t) ? Math.floor((now - t) / 86400000) : null;
    };
    const today = emails.filter(e => (ageDays(e.date) === 0)).length;
    const week = emails.filter(e => { const a = ageDays(e.date); return a !== null && a >= 1 && a < 7; }).length;
    const older = emails.filter(e => { const a = ageDays(e.date); return a !== null && a >= 7; }).length;
    const unparsed = emails.filter(e => ageDays(e.date) === null).length;

    el.innerHTML =
      Viz.hero([
        // These two are already percentages of the inbox, so they must NOT also
        // pass max — that would divide by the message count a second time and
        // collapse a healthy inbox to a sliver. The count is shown as the label.
        Viz.ring(emails.length ? (today / emails.length) * 100 : 0, {
          label: 'TODAY', labelText: String(today)
        }),
        Viz.ring(emails.length ? ((today + week) / emails.length) * 100 : 0, {
          label: 'THIS WEEK', labelText: String(today + week)
        })
      ], { title: 'INBOX', sub: emails.length + ' message' + (emails.length === 1 ? '' : 's') }) +
      Viz.section('BY AGE', Viz.stack([
        { label: 'Today', value: today, color: 'var(--accent, #6d8bff)' },
        { label: 'This week', value: week, color: '#22d3ee' },
        { label: 'Older', value: older, color: 'rgba(255,255,255,0.28)' },
        { label: 'No date', value: unparsed, color: 'rgba(255,255,255,0.14)' }
      ]), 'fa-envelope-open-text') +
      Viz.section('MESSAGES', emails.map((e, idx) => {
        const a = ageDays(e.date);
        // Heat strip encodes how recent each message is - the top of the list
        // is the freshest, so recency is readable without reading the dates.
        const fresh = a === null ? 30 : a === 0 ? 100 : a < 7 ? 70 : a < 30 ? 40 : 18;
        return '<div class="email-item">' +
          '<div class="email-from"><span class="viz-pip' + (a === 0 ? '' : a === null ? ' off' : ' warn') + '"></span> ' +
            Viz.esc(e.from || 'Unknown') + '</div>' +
          '<div class="email-subject">' + Viz.esc(e.subject || '(no subject)') + '</div>' +
          '<div class="email-date">' + Viz.esc(e.date || '') + '</div>' +
          '<span class="viz-heat"><i style="width:' + fresh + '%;background:linear-gradient(90deg,var(--accent,#6d8bff),var(--accent-2,#a855f7));box-shadow:0 0 8px rgba(var(--accent-rgb,109,139,255),0.5)"></i></span>' +
        '</div>';
      }).join(''), 'fa-inbox');
  } catch { el.innerHTML = '<div class="panel-empty">Error reading emails.</div>'; }
}

async function loadProcessPanel(el) {
  el.innerHTML = '<div class="panel-empty">Loading...</div>';
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'processes' }) });
    const d = await res.json();
    if (!d.success || !d.processes?.length) { el.innerHTML = '<div class="panel-empty">None found.</div>'; return; }
    const procs = d.processes.slice();
    const top = procs[0];
    const totalCpu = procs.reduce((a, p) => a + Viz.num(p.cpu, 0), 0) || 1;
    const avg = totalCpu / procs.length;
    const hottest = Math.max(...procs.map(p => Viz.num(p.cpu, 0)));

    el.innerHTML =
      Viz.hero([
        Viz.ring(hottest, { label: 'PEAK', sub: 'single proc' }),
        Viz.ring(Math.min(100, avg * 4), { label: 'AVERAGE', sub: 'scaled' })
      ], { title: 'PROCESS MANAGER', sub: procs.length + ' tracked' }) +
      Viz.section('TOP CONSUMERS', procs.slice(0, 12).map(p => {
        const cpu = Viz.num(p.cpu, 0);
        return '<div class="proc-item" style="display:grid;grid-template-columns:44px 54px 1fr auto;align-items:center;gap:8px">' +
          '<span class="pcpu" style="color:' + (cpu > 25 ? '#ff5f56' : cpu > 10 ? '#fbbf24' : '#fff') + '">' + cpu + '%</span>' +
          '<span style="color:rgba(255,255,255,0.4);font-family:var(--mono);font-size:9px">' + Viz.esc(p.pid) + '</span>' +
          '<span class="pcmd" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + Viz.esc(p.command) + '</span>' +
          '<button class="pk" onclick="killProc(' + JSON.stringify(String(p.pid)) + ')" title="Kill process"><i class="fa-solid fa-xmark"></i></button>' +
        '</div>' +
        '<div style="margin:-2px 0 6px">' + Viz.bar(cpu, { max: Math.max(hottest, 10), color: cpu > 25 ? '#ff5f56' : cpu > 10 ? '#fbbf24' : undefined, valueText: '' }) + '</div>';
      }).join(''), 'fa-fire') +
      Viz.section('LOAD SHARING', Viz.stack(procs.slice(0, 6).map((p, i) => ({
        label: String(p.command || 'proc').slice(0, 18),
        value: Viz.num(p.cpu, 0),
        color: `hsl(${Math.round((i / 6) * 300)},72%,62%)`
      }))), 'fa-chart-pie');
  } catch { el.innerHTML = '<div class="panel-empty">Error.</div>'; }
}

async function killProc(pid) {
  await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'kill-process', value: pid }) });
  toast(`Process ${pid} killed, BOSS.`, 'ok');
  const body = document.getElementById('panel-body-processes');
  if (body) loadProcessPanel(body);
}

async function loadVaultPanel(el) {
  el.innerHTML = '<div class="panel-empty">Opening the vault...</div>';
  try {
    const res = await fetch('/api/vault');
    const d = await res.json();
    const items = d.data || [];
    if (!items.length) {
      el.innerHTML = Viz.hero([Viz.ring(0, { label: 'STORED', labelText: '0' })], { title: 'MEMORY VAULT', sub: 'nothing saved yet' }) +
        '<div class="panel-empty">No memories yet.</div>' +
        `<div class="panel-input"><input type="text" id="vault-input" placeholder="Save a memory..." onkeydown="if(event.key==='Enter')addVault()"><button onclick="addVault()"><i class="fa-solid fa-plus"></i></button></div>`;
      return;
    }
    // Age the memories into buckets. A vault is mostly useful when you can see
    // what is recent versus what has been sitting there for months.
    const now = Date.now();
    const ageDays = (dt) => {
      const t = Date.parse(dt || '');
      return isFinite(t) ? Math.floor((now - t) / 86400000) : null;
    };
    const buckets = { today: 0, week: 0, month: 0, older: 0, undated: 0 };
    items.forEach(v => {
      const a = ageDays(v.date);
      if (a === null) buckets.undated++;
      else if (a === 0) buckets.today++;
      else if (a < 7) buckets.week++;
      else if (a < 30) buckets.month++;
      else buckets.older++;
    });
    const words = items.reduce((a, v) => a + String(v.text || '').trim().split(/\s+/).filter(Boolean).length, 0);
    const recent = (today + week) || 0;

    el.innerHTML =
      Viz.hero([
        Viz.ring(items.length, { max: Math.max(items.length, 10), label: 'STORED', labelText: String(items.length) }),
        Viz.ring((recent / items.length) * 100, { label: 'FRESH', sub: '≤ 7 days' })
      ], { title: 'MEMORY VAULT', sub: words.toLocaleString() + ' words on file' }) +
      Viz.section('BY AGE', Viz.stack([
        { label: 'Today', value: buckets.today, color: 'var(--accent, #6d8bff)' },
        { label: 'This week', value: buckets.week, color: '#22d3ee' },
        { label: 'This month', value: buckets.month, color: '#a855f7' },
        { label: 'Older', value: buckets.older, color: 'rgba(255,255,255,0.24)' },
        { label: 'No date', value: buckets.undated, color: 'rgba(255,255,255,0.12)' }
      ]), 'fa-hourglass-half') +
      Viz.section('MEMORIES', items.map(v => {
        const a = ageDays(v.date);
        const fresh = a === null ? 25 : a === 0 ? 100 : a < 7 ? 72 : a < 30 ? 45 : 18;
        return `<div class="vault-item"><span class="vt">${escHtml(v.text)}</span><span class="vd">${escHtml(v.date || '')}</span><button class="vx" onclick="deleteVault(${JSON.stringify(String(v.id))})"><i class="fa-solid fa-xmark"></i></button></div>` +
          `<span class="viz-heat" style="margin:-4px 6px 6px"><i style="width:${fresh}%;background:linear-gradient(90deg,var(--accent,#6d8bff),var(--accent-2,#a855f7));box-shadow:0 0 8px rgba(var(--accent-rgb,109,139,255),0.5)"></i></span>`;
      }).join(''), 'fa-database') +
      `<div class="panel-input"><input type="text" id="vault-input" placeholder="Save a memory..." onkeydown="if(event.key==='Enter')addVault()"><button onclick="addVault()"><i class="fa-solid fa-plus"></i></button></div>`;
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
  el.innerHTML = '<div class="panel-empty">Reading clipboard...</div>';
  try {
    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'clipboard-read' }) });
    const d = await res.json();
    const content = String(d.content || '');
    // Character / word / line counts are the numbers people actually want from a
    // clipboard grab, and they cost nothing to compute.
    const chars = content.length;
    const words = content.trim() ? content.trim().split(/\s+/).length : 0;
    const lines = content ? content.split('\n').length : 0;
    // Rough read time at 200 words per minute, floored at 1s so a short snippet
    // never claims "0s".
    const readSec = words ? Math.max(1, Math.round(words / 200 * 60)) : 0;
    const kind = /^(https?:\/\/|www\.)\S+$/i.test(content.trim()) ? ['LINK', 'fa-link']
      : /^-?\d+(\.\d+)?$/.test(content.trim()) ? ['NUMBER', 'fa-hashtag']
      : /[\n]/.test(content) ? ['TEXT', 'fa-align-left']
      : words > 12 ? ['PARAGRAPH', 'fa-paragraph'] : ['SNIPPET', 'fa-scissors'];

    el.innerHTML =
      Viz.hero([
        Viz.ring(Math.min(100, words * 100 / 500), { label: 'WORDS', labelText: String(words) }),
        Viz.ring(Math.min(100, chars * 100 / 2000), { label: 'CHARS', labelText: chars > 999 ? (chars / 1000).toFixed(1) + 'k' : String(chars) })
      ], { title: 'CLIPBOARD', sub: '<i class="fa-solid ' + kind[1] + '"></i> ' + kind[0] }) +
      Viz.section('SIZE', [
        Viz.bar(Math.min(100, chars * 100 / 2000), { label: 'Characters', valueText: chars.toLocaleString() }),
        Viz.bar(Math.min(100, words * 100 / 500), { label: 'Words', valueText: words.toLocaleString() }),
        Viz.bar(Math.min(100, lines * 100 / 50), { label: 'Lines', valueText: String(lines) })
      ].join(''), 'fa-ruler-horizontal') +
      `<div class="panel-row"><span class="lbl">READ TIME</span><span class="val">${readSec ? readSec + 's' : '--'}</span></div>
       <div class="panel-row"><span class="lbl">DETECTED</span><span class="val">${kind[0]}</span></div>` +
      Viz.section('CONTENT', '<div style="padding:10px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;font-family:var(--mono);font-size:9px;color:var(--txt);max-height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;">' +
        (escHtml(content || '(empty)')) + '</div>', 'fa-clipboard') +
      `<div class="panel-input"><input type="text" id="clip-input" placeholder="Write to clipboard..." onkeydown="if(event.key==='Enter')writeClip()"><button onclick="writeClip()"><i class="fa-solid fa-copy"></i></button></div>`;
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

  // ---- setup gauges ------------------------------------------------------
  // Settings used to open as a wall of dropdowns with no indication of what was
  // actually configured, so the first thing you learned was from a toast after
  // something failed. These rings repaint as the async key/location/service
  // loads below resolve, and start as "unknown" rather than claiming a state we
  // have not fetched yet.
  const SETUP_SLOTS = 6; // keys, location, email, discord, whatsapp, agency
  const setupState = { keys: 0, location: false, email: false, discord: false, whatsapp: false, agency: false };
  const paintSetup = () => {
    const host = document.getElementById('setup-gauges');
    if (!host) return;
    const done = (setupState.keys > 0 ? 1 : 0) + (setupState.location ? 1 : 0) +
      ['email', 'discord', 'whatsapp', 'agency'].filter(k => setupState[k]).length;
    const pct = Math.round((done / SETUP_SLOTS) * 100);
    const sub = document.getElementById('setup-sub');
    if (sub) {
      sub.textContent = pct === 100 ? 'everything is configured, BOSS'
        : (SETUP_SLOTS - done) + ' item' + (SETUP_SLOTS - done === 1 ? '' : 's') + ' still to configure';
    }
    host.innerHTML =
      // A setup meter is progress, not danger: amber/red here would read as a
      // fault when it just means "not done yet".
      Viz.ring(pct, { label: 'SETUP', labelText: pct + '%', warn: false, crit: false }) +
      Viz.ring(setupState.keys, { max: Math.max(setupState.keys, 4), label: 'API KEYS', labelText: String(setupState.keys), warn: false, crit: false }) +
      Viz.ring(mem.continuousListen ? 100 : 0, {
        label: 'LISTEN', labelText: mem.continuousListen ? 'ON' : 'OFF',
        color: mem.continuousListen ? 'var(--accent, #6d8bff)' : 'rgba(255,255,255,0.22)',
        warn: false, crit: false
      });
  };

  const hero =
    '<div class="viz-hero glass-soft">' +
      '<div class="viz-hero-rings" id="setup-gauges"></div>' +
      '<div class="viz-hero-title">CONFIGURATION</div>' +
      '<div class="viz-hero-sub" id="setup-sub">checking what is configured...</div>' +
    '</div>';

  // ---- voice preview -----------------------------------------------------
  // Rate and pitch were two bare sliders whose effect you could only judge by
  // speaking afterwards. The waveform plus the two meters give an immediate
  // visual of which of them you just moved.
  const preview = `
    <div class="viz-section">
      <div class="viz-section-h"><i class="fa-solid fa-wave-square"></i> VOICE PREVIEW</div>
      <div class="viz-section-b">
        <div id="voice-wave">${Viz.waveform(34, 11)}</div>
        <div style="margin-top:10px" id="voice-meters"></div>
        <div style="margin-top:8px;font-family:var(--mono);font-size:8px;letter-spacing:1px;color:var(--txt3)" id="voice-hint">
          Move rate or pitch, then press TEST VOICE.
        </div>
      </div>
    </div>
  `;

  const paintVoiceMeters = () => {
    const host = document.getElementById('voice-meters');
    if (!host) return;
    const r = parseFloat((document.getElementById('speech-rate') || {}).value || 1);
    const p = parseFloat((document.getElementById('speech-pitch') || {}).value || 1);
    // Both sliders run 0.5-2.0; show them as a position in that window rather
    // than as a percentage of 100, which would make every value look tiny.
    host.innerHTML =
      Viz.bar(r, { min: 0.5, max: 2, label: 'Rate', valueText: r.toFixed(1) + '×', warn: false, crit: false }) +
      Viz.bar(p, { min: 0.5, max: 2, label: 'Pitch', valueText: p.toFixed(1) + '×', warn: false, crit: false });
    const hint = document.getElementById('voice-hint');
    if (hint) {
      const slow = r < 0.9, fast = r > 1.3, deep = p < 0.9, high = p > 1.2;
      const words = [slow ? 'slow' : fast ? 'fast' : '', deep ? 'deeper' : high ? 'higher' : ''].filter(Boolean);
      hint.textContent = words.length ? 'Currently set ' + words.join(' and ') + '.' : 'Currently set to natural pace and pitch.';
    }
  };

  // Build settings HTML
  let html = hero + preview + Viz.section('VOICE', `
    <div class="setting-row"><label>VOICE</label><select id="voice-select" style="width:140px"><optgroup label="ElevenLabs"><option value="21m00Tcm4TlvDq8ikWAM">Rachel</option><option value="EXAVITQu4vr4xnSDxMaL">Bella</option><option value="MF3mGyEYCl7XYWbV9V6O">Elli</option><option value="pFZP5JQG7iQjIQuC4Bku">Lily</option><option value="AZnzlk1XvdvUeBnXmlld">Domi</option><option value="TxGEqnHWrfWFTfGW9XjX">Josh</option><option value="VR6AewLTigWG4xSOukaG">Arnold</option><option value="yoZ06aMxZJJ28mfd3POQ">Sam</option></optgroup><optgroup label="Web Speech (Free)"><option value="web-samantha">Samantha (macOS)</option><option value="web-karen">Karen (macOS)</option><option value="web-moira">Moira (macOS)</option><option value="web-tessa">Tessa (macOS)</option></optgroup></select></div>
    <div class="setting-row"><label>TTS ENGINE</label><select id="engine-select" style="width:140px"><option value="auto">Auto (best available)</option><option value="bark">Bark (neural, needs torch)</option><option value="edge-tts">Edge-TTS (neural)</option><option value="sapi">Windows SAPI (offline)</option></select></div>
    <div class="setting-row"><label>SPEECH RATE</label><input type="range" id="speech-rate" min="0.5" max="2" step="0.1" value="${(typeof mem.speechRate === 'number' ? mem.speechRate : 1.0)}" style="width:100px"></div>
    <div class="setting-row"><label>SPEECH PITCH</label><input type="range" id="speech-pitch" min="0.5" max="2" step="0.1" value="${(typeof mem.speechPitch === 'number' ? mem.speechPitch : 1.0)}" style="width:100px"></div>
    <div class="setting-row"><label></label><button id="test-voice-btn" style="padding:4px 10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:6px;color:var(--txt2);font-family:var(--mono);font-size:9px;cursor:pointer;"><i class="fa-solid fa-volume-high"></i> TEST VOICE</button></div>
    <div class="setting-row"><label>CONTINUOUS LISTEN</label><input type="checkbox" id="cont-listen" ${mem.continuousListen ? 'checked' : ''}></div>
    <div class="setting-row"><label>YOUR NAME</label><input type="text" id="name-input" value="${mem.name || ''}" placeholder="Tell me your name" style="width:130px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
  `, 'fa-microphone-lines');
  
  // Dark mode toggle
  const isDark = mem.darkMode !== false; // default dark
  html += `<div class="setting-row"><label>DARK MODE</label><input type="checkbox" id="dark-mode-toggle" ${isDark ? 'checked' : ''}></div>`;
  
  // Location settings
  html += Viz.section('LOCATION', `
      <div class="setting-row"><label>CITY NAME</label><input type="text" id="city-name-input" placeholder="New Delhi, IN" style="width:130px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>LATITUDE</label><input type="number" id="lat-input" step="0.0001" style="width:80px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>LONGITUDE</label><input type="number" id="lon-input" step="0.0001" style="width:80px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label></label><button id="save-location-btn" style="padding:4px 10px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:6px;color:var(--txt2);font-family:var(--mono);font-size:9px;cursor:pointer;">Save Location</button></div>
      <div class="setting-row"><label></label><button id="detect-location-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Auto-detect</button></div>
  `, 'fa-location-dot');
  
  // API Keys section
  html += Viz.section('API KEYS', `
      <div id="api-keys-list" style="font-family:var(--mono); font-size:9px; color:var(--txt2);">Loading...</div>
      <div class="setting-row"><label></label><button id="show-keys-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Show Key Details</button></div>
      <div style="margin-top:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.05);">
        <div style="font-size:10px; color:var(--txt3); letter-spacing:2px; margin-bottom:8px; font-family:var(--mono);">CONFIGURE KEYS</div>
        <div style="display:flex; gap:6px; margin-bottom:6px;">
          <input id="key-gemini" type="password" placeholder="Gemini API key" style="flex:1; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:6px 10px; color:var(--txt); font-family:var(--mono); font-size:10px;">
        </div>
        <div style="display:flex; gap:6px; margin-bottom:8px;">
          <input id="key-grok" type="password" placeholder="Grok API key" style="flex:1; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:6px 10px; color:var(--txt); font-family:var(--mono); font-size:10px;">
        </div>
        <button id="save-keys-btn" style="width:100%; padding:7px; border-radius:6px; border:1px solid rgba(168,85,247,0.3); background:rgba(168,85,247,0.1); color:var(--accent); font-family:var(--mono); font-size:10px; letter-spacing:1px; cursor:pointer;">SAVE KEYS</button>
      </div>
  `, 'fa-key');
  
  // Connected services & permissions (permanent-app control center)
  html += Viz.section('CONNECTED SERVICES & PERMISSIONS', `
      <div id="services-status" style="font-family:var(--mono); font-size:9px; color:var(--txt2); margin-bottom:8px;">Loading...</div>
      <div class="setting-row"><label></label><button id="services-refresh-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">REFRESH STATUS</button></div>
      <div class="setting-row"><label>DISCORD WEBHOOK URL</label><input type="text" id="discord-webhook-input" placeholder="https://discord.com/api/webhooks/..." style="flex:1;min-width:0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>WHATSAPP NUMBER</label><input type="text" id="whatsapp-input" placeholder="+91 xxxxxxxxxx" style="flex:1;min-width:0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>AGENCY OS URL</label><input type="text" id="agency-url-input" placeholder="http://localhost:3200" style="flex:1;min-width:0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:var(--txt);border-radius:6px;padding:3px 7px;font-family:var(--mono);font-size:9px;"></div>
      <div class="setting-row"><label>AUTO-APPROVE PHONES</label><input type="checkbox" id="auto-approve-toggle"></div>
      <div class="setting-row"><label>START WITH WINDOWS</label><input type="checkbox" id="autostart-toggle"></div>
      <div class="setting-row"><label>MIC AIM</label><button id="wake-restart-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Restart Wake Listener</button></div>
      <div class="setting-row"><label></label><button id="save-services-btn" style="padding:5px 12px;background:rgba(139,104,255,0.1);border:1px solid rgba(139,104,255,0.35);border-radius:6px;color:var(--gold);font-family:var(--mono);font-size:9px;letter-spacing:1px;cursor:pointer;">SAVE SERVICES</button></div>
  `, 'fa-plug');

  // Permissions section
  html += Viz.section('SYSTEM', `
      <div class="setting-row"><label></label><button id="check-perms-btn" style="padding:4px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:var(--txt3);font-family:var(--mono);font-size:9px;cursor:pointer;">Check Permissions</button></div>
  `, 'fa-shield-halved');
  
  el.innerHTML = html;
  paintSetup();
  paintVoiceMeters();
  
  // Event listeners
  document.getElementById('voice-select').addEventListener('change', (e) => { mem.voiceId = e.target.value; saveOfflineMemory(mem); const vv = e.target.value; if (/^web-/i.test(vv)) { _cachedVoice = null; _cachedMode = null; } toast('Voice updated, BOSS.', 'ok'); });
  const engineSelect = document.getElementById('engine-select');
  if (engineSelect) {
    fetch('/api/voice-engine', { cache: 'no-store' }).then(r => r.json()).then(d => {
      if (d && d.success && d.setting) engineSelect.value = d.setting;
    }).catch(() => {});
    engineSelect.addEventListener('change', async (e) => {
      const wanted = e.target.value;
      try {
        const r = await fetch('/api/voice-engine', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine: wanted }) });
        const d = await r.json();
        if (d && d.success) {
          _cachedVoice = null; _cachedMode = null;
          if (wanted === 'bark' && d.active !== 'bark') {
            toast(`Bark unavailable (${(d.engines && d.engines.bark && d.engines.bark.reason) || 'deps missing'}). Using ${d.active}.`, 'err');
            if (d.setting) engineSelect.value = d.setting;
          } else {
            toast(`TTS engine: ${d.active}`, 'ok');
          }
          loadVoiceBadge();
        } else {
          toast('Could not set TTS engine.', 'err');
        }
      } catch (err) { toast('Could not set TTS engine.', 'err'); }
    });
  }
  const testVoiceBtn = document.getElementById('test-voice-btn');
  if (testVoiceBtn) testVoiceBtn.addEventListener('click', () => { _cachedVoice = null; _cachedMode = null; speak('Hello Boss. This is how I sound now. Does this work for you?'); });
  document.getElementById('speech-rate').addEventListener('input', (e) => { mem.speechRate = parseFloat(e.target.value); saveOfflineMemory(mem); paintVoiceMeters(); });
  document.getElementById('speech-pitch').addEventListener('input', (e) => { mem.speechPitch = parseFloat(e.target.value); saveOfflineMemory(mem); paintVoiceMeters(); });
  document.getElementById('cont-listen').addEventListener('change', (e) => { mem.continuousListen = e.target.checked; saveOfflineMemory(mem); paintSetup(); });
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
    // Feed the location slot of the setup ring from the same response.
    setupState.location = !!(d.success && d.settings && (d.settings.cityName || d.settings.latitude));
    paintSetup();
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
  
  // Connected services — status + controls
  async function refreshServicesStatus() {
    const el = document.getElementById('services-status');
    if (!el) return;
    el.innerHTML = 'Loading...';
    try {
      const res = await fetch('/api/services');
      const d = await res.json();
      if (!d.success) { el.innerHTML = `<span style="color:var(--pink)">${String(d.error||'services error').slice(0,160)}</span>`; return; }
      const s = d.services || {};
      const chip = (ok, label) => `<span style="display:inline-block;padding:2px 8px;border-radius:10px;margin:2px 4px 2px 0;border:1px solid ${ok ? 'rgba(74,222,128,0.4)' : 'rgba(255,159,28,0.4)'};color:${ok ? '#4ade80' : '#ff9f1c'};font-size:9px;letter-spacing:1px;"><i class="fa-solid fa-circle" style="font-size:5px;vertical-align:middle;"></i> ${label.toUpperCase()}</span>`;
      const rows = [
        ['Email', s.email ? (s.email.configured ? 'configured' : 'not configured') : '—'],
        ['Discord', s.discord ? (s.discord.configured ? 'configured' : 'add webhook') : '—'],
        ['WhatsApp', s.whatsapp ? (s.whatsapp.configured ? 'ready' : 'add number') : '—'],
        ['Agency OS', s.agency ? (s.agency.online ? 'online' : 'offline') : '—'],
        ['Start with Windows', s.autostart ? (s.autostart.enabled ? 'enabled' : 'off') : '—'],
        ['Wake Word', s.wake ? (s.wake.enabled ? 'on' : 'off') : '—'],
      ];
      el.innerHTML = rows.map(([n, v]) => {
        const ok = v === 'configured' || v === 'ready' || v === 'online' || v === 'enabled' || v === 'on';
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px dashed rgba(255,255,255,0.04);"><span>${n}</span>${chip(ok, v)}</div>`;
      }).join('');
      const auto = document.getElementById('auto-approve-toggle');
      if (auto) fetch('/api/settings').then(r=>r.json()).then(x => { if (x.success && x.settings) auto.checked = x.settings.auto_approve_phones !== false; }).catch(()=>{});
      const as = document.getElementById('autostart-toggle');
      if (as && s.autostart) as.checked = !!s.autostart.enabled;
      const ws = document.getElementById('whatsapp-input');
      if (ws) fetch('/api/settings').then(r=>r.json()).then(x => { if (x.success && x.settings) ws.value = x.settings.whatsapp_number || ''; }).catch(()=>{});
      const au = document.getElementById('agency-url-input');
      if (au) { au.value = (s.agency && s.agency.url) || 'http://localhost:3200'; if (!au.closest('.setting-row')) {} }
      if (s.agency && !s.agency.online && s.agency.error && el) el.innerHTML += `<div style="margin-top:6px;color:var(--pink);font-size:9px;word-break:break-word;">${String(s.agency.error).slice(0,180)}</div>`;
      // Feed the service slots of the setup ring from the same response, so the
      // ring and the status list can never disagree about what is configured.
      setupState.email = !!(s.email && s.email.configured);
      setupState.discord = !!(s.discord && s.discord.configured);
      setupState.whatsapp = !!(s.whatsapp && s.whatsapp.configured);
      setupState.agency = !!(s.agency && s.agency.online);
      paintSetup();
    } catch(e) { el.innerHTML = `<span style="color:var(--pink)">services unavailable</span>`; }
  }
  refreshServicesStatus();

  document.getElementById('services-refresh-btn').addEventListener('click', refreshServicesStatus);
  document.getElementById('wake-restart-btn').addEventListener('click', async () => {
    try {
      const r = await fetch('/api/wake/restart', { method: 'POST' });
      const d = await r.json();
      toast(d.restarted ? 'Wake listener restarted.' : 'Wake listener is off — enable it first.', d.restarted ? 'ok' : 'info');
      syncWakeStatus();
      refreshServicesStatus();
    } catch { toast('Restart failed', 'err'); }
  });
  document.getElementById('save-services-btn').addEventListener('click', async () => {
    const payload = {
      auto_approve_phones: document.getElementById('auto-approve-toggle').checked,
      autostart: document.getElementById('autostart-toggle').checked,
      agency_url: (document.getElementById('agency-url-input').value || '').trim(),
      whatsapp_number: (document.getElementById('whatsapp-input').value || '').trim(),
    };
    try {
      await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const dw = (document.getElementById('discord-webhook-input').value || '').trim();
      if (dw) await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ discord_webhook_url: dw }) });
      toast('Services saved.', 'ok');
      refreshServicesStatus();
    } catch { toast('Save failed', 'err'); }
  });

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
    setupState.keys = d.totalKeys || 0;
    paintSetup();
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

  // Wire up key save
  var saveKeysBtn = document.getElementById('save-keys-btn');
  if (saveKeysBtn) {
    saveKeysBtn.addEventListener('click', function() {
      var gemini = document.getElementById('key-gemini').value.trim();
      var grok = document.getElementById('key-grok').value.trim();
      var payload = {};
      if (gemini) payload.gemini_api_key = gemini;
      if (grok) payload.grok_api_key = grok;
      if (Object.keys(payload).length === 0) { toast('No keys entered', 'info'); return; }
      fetch('/api/settings/keys', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.success) { toast('Keys saved! Restart server to activate.', 'ok'); fetchQuota(); }
      }).catch(function() { toast('Failed to save keys', 'err'); });
    });
  }
  
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
  const dirs = files.filter(f => !f.includes('.'));
  const plain = files.filter(f => f.includes('.'));
  // Group the plain files by extension. In a mixed folder the extension split
  // is the fastest way to see what is actually in there, and it costs one pass.
  const byExt = {};
  plain.forEach(f => {
    const m = f.match(/\.([A-Za-z0-9]{1,6})$/);
    const key = (m ? m[1] : 'other').toLowerCase();
    byExt[key] = (byExt[key] || 0) + 1;
  });
  const extSegs = Object.keys(byExt)
    .sort((a, b) => byExt[b] - byExt[a])
    .slice(0, 8)
    .map((k, i) => ({ label: '.' + k, value: byExt[k], color: `hsl(${Math.round((i / 8) * 300)},70%,62%)` }));

  const item = (f, isDir) => {
    const full = (path ? path + '/' : '') + f;
    // Call the handler with a JSON literal so spaces and apostrophes in a
    // filename cannot break out of the inline onclick.
    const arg = JSON.stringify(full);
    const icon = isDir ? 'fa-folder' : 'fa-file-lines';
    const iconColor = isDir ? 'var(--accent, #a855f7)' : 'rgba(255,255,255,0.35)';
    return `<div class="vault-item" style="cursor:pointer;" onclick="${isDir ? 'navigateDir(' + arg + ')' : 'openFile(' + arg + ')'}">` +
      `<i class="fa-solid ${icon}" style="color:${iconColor};font-size:10px;margin-right:6px;${isDir ? 'filter:drop-shadow(0 0 6px rgba(var(--accent-rgb,109,139,255),0.5));' : ''}"></i>` +
      `<span class="vt">${escHtml(f)}</span>` +
      (isDir ? '<i class="fa-solid fa-chevron-right" style="margin-left:auto;font-size:8px;opacity:0.3"></i>' : '') +
      '</div>';
  };

  el.innerHTML =
    '<div style="font-family:var(--mono);font-size:8px;color:var(--txt3);padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;">' +
      '<span><i class="fa-solid fa-folder-open" style="margin-right:5px;opacity:0.6"></i>' + escHtml(path || '~/Desktop') + '</span>' +
      '<span>' + dirs.length + ' folders · ' + plain.length + ' files</span>' +
    '</div>' +
    (dirs.length ? Viz.section('FOLDERS (' + dirs.length + ')', dirs.map(f => item(f, true)).join(''), 'fa-folder') : '') +
    (plain.length ? Viz.section('FILES (' + plain.length + ')',
        (extSegs.length > 1 ? '<div style="margin-bottom:9px">' + Viz.stack(extSegs, { legendValues: false }) + '</div>' : '') +
        plain.map(f => item(f, false)).join(''), 'fa-file-lines') : '') +
    (!files.length ? '<div class="panel-empty">Empty folder</div>' : '') +
    (path ? `<div class="vault-item" style="cursor:pointer;color:var(--txt3);margin-top:6px;" onclick="navigateDir(${JSON.stringify(path.split('/').slice(0, -1).join('/'))})"><i class="fa-solid fa-arrow-left" style="font-size:10px;margin-right:6px;"></i><span class="vt">Back</span></div>` : '');
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
  const done = notes.filter(n => n.done).length;
  const open = notes.length - done;
  el.innerHTML =
    Viz.hero([
      Viz.ring(notes.length ? (done / notes.length) * 100 : 0, {
        // A completion ring is not a danger gauge: half-done tasks turning red
        // would be noise, so severity is explicitly disabled here.
        label: 'DONE', labelText: done + '/' + notes.length, warn: false, crit: false
      })
    ], {
      title: 'NOTES & TASKS',
      sub: open ? open + ' still open' : (notes.length ? 'all clear' : 'nothing on the list')
    }) +
    (notes.length ? Viz.section('PROGRESS', [
      Viz.bar((done / notes.length) * 100, { label: 'Completed', valueText: done + ' of ' + notes.length, warn: false, crit: false }),
      Viz.bar((open / notes.length) * 100, { label: 'Remaining', valueText: String(open), color: '#fbbf24', warn: false, crit: false })
    ].join(''), 'fa-list-check') : '') +
    `<div class="panel-input" style="border-top:none;border-bottom:1px solid rgba(255,255,255,0.03);padding-bottom:8px;">
       <input type="text" id="note-input" placeholder="Add a note or TODO..." onkeydown="if(event.key==='Enter')addNote()">
       <button onclick="addNote()"><i class="fa-solid fa-plus"></i></button>
     </div>
     <div id="notes-list">${renderNotes(notes)}</div>`;
}

function loadNotes() {
  try { return JSON.parse(localStorage.getItem(NOTES_KEY) || '[]'); } catch { return []; }
}

function saveNotes(notes) {
  localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
}

function renderNotes(notes) {
  if (!notes.length) return '<div class="panel-empty">No notes yet.</div>';
  // Open items first: a checklist you are working through is read top-down,
  // and buried completed items under new ones is what made this list feel
  // like an archive rather than a to-do list.
  const ordered = notes.map((n, i) => ({ n: n, i: i }))
    .sort((a, b) => (a.n.done === b.n.done ? 0 : (a.n.done ? 1 : -1)));
  return ordered.map(({ n, i }) => `
    <div class="vault-item">
      <span class="vt" style="display:flex;align-items:center;gap:6px;">
        <input type="checkbox" ${n.done ? 'checked' : ''} onchange="toggleNote(${i})" style="width:12px;height:12px;accent-color:var(--accent,#a78bfa);">
        <span style="${n.done ? 'text-decoration:line-through;color:var(--txt3);' : ''}">${escHtml(n.text)}</span>
      </span>
      ${n.date ? `<span class="vd" style="font-size:8px;color:var(--txt3);">${escHtml(n.date)}</span>` : ''}
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
  // Re-render the whole panel, not just the list: the progress ring in the hero
  // counts open items, so patching only the list would leave it stale.
  const body = document.getElementById('panel-body-notes');
  if (body) loadNotesPanel(body);
  toast('Note added, BOSS.', 'ok');
}

function toggleNote(idx) {
  const notes = loadNotes();
  if (notes[idx]) { notes[idx].done = !notes[idx].done; saveNotes(notes); }
  const body = document.getElementById('panel-body-notes');
  if (body) loadNotesPanel(body);
}

function deleteNote(idx) {
  const notes = loadNotes();
  notes.splice(idx, 1);
  saveNotes(notes);
  const body = document.getElementById('panel-body-notes');
  if (body) loadNotesPanel(body);
  toast('Note deleted.', 'ok');
}

// ================================================
// COMMAND REFERENCE
// ================================================
// Held as data rather than as a pre-baked HTML string: the panel renders a
// category breakdown and a live filter from this, so the summary can never
// drift out of sync with the list it is summarising.
const COMMAND_REF = [
  {
    title: 'System Control', icon: 'fa-sliders',
    items: [
      ['open notepad / calculator / paint / chrome / edge / vscode / discord / spotify / word / excel / powerpoint', 'Launch any app'],
      ['close notepad / chrome / any app', 'Kill any running app'],
      ['lock pc / lock screen', 'Lock Windows screen'],
      ['take screenshot / screenshot', 'Save screenshot to Desktop'],
      ['volume 50 / volume up / volume down / mute / unmute', 'Audio volume controls'],
      ['shutdown / restart / sleep', 'Power controls'],
      ['empty trash / empty recycle bin', 'Clear recycle bin'],
      ['minimize all / show desktop', 'Minimize all windows'],
      ['open terminal / open cmd', 'Open terminal or command prompt'],
    ]
  },
  {
    title: 'File & Folder Access', icon: 'fa-folder-tree',
    items: [
      ['open desktop / downloads / documents / pictures / music / videos', 'Open common folders'],
      ['browse C:\\path\\to\\folder / open folder [path]', 'Open any folder by path'],
      ['open chrome bookmarks / show bookmarks', 'Access Chrome bookmarks'],
    ]
  },
  {
    title: 'Web & Browser', icon: 'fa-globe',
    items: [
      ['open google.com / open youtube.com / open [any website]', 'Open website in Chrome'],
      ['news / headlines / top news', 'Latest news headlines'],
      ['bitcoin price / crypto prices', 'Live crypto prices'],
    ]
  },
  {
    title: 'System Info', icon: 'fa-microchip',
    items: [
      ['cpu usage / cpu info', 'Processor usage & model'],
      ['ram usage / memory info', 'RAM usage & total'],
      ['battery level / battery', 'Battery percentage & charging'],
      ['disk usage / storage / free space', 'Disk space info'],
      ['system info / about my pc / my system', 'Full system information'],
      ['uptime / how long has pc been on', 'System uptime'],
      ['wifi / network / internet status', 'Network & WiFi info'],
      ['hostname / computer name', 'PC name'],
      ['running processes / task manager', 'List running processes'],
    ]
  },
  {
    title: 'Knowledge & Chat', icon: 'fa-book',
    items: [
      ['what is AI / python / CPU / RAM / WiFi / encryption / blockchain', '50+ offline tech topics'],
      ['what time / todays date / what day / what month / what year', 'Date & time queries'],
      ['what is 42 * 7 / calculate 100 + 200 / math', 'Quick math calculator'],
      ['convert 100 F to C / convert 50 C to F', 'Temperature conversion'],
      ['25% of 200 / what is 30 percent of 150', 'Percentage calculator'],
      ['weather / temperature / forecast', 'Live weather info'],
      ['tell me a joke / something funny', 'Random jokes'],
      ['give me a quote / inspire me / motivational quote', 'Inspirational quotes'],
      ['tell me a fact / fun fact / random fact', 'Interesting facts'],
    ]
  },
  {
    title: 'Utility', icon: 'fa-toolbox',
    items: [
      ['set a timer for 5 minutes / remind me in 30 seconds', 'Timer with alert'],
      ['remember [fact] / save to vault [note]', 'Save to memory vault'],
      ['briefing / daily briefing', 'Full system overview'],
      ['who are you / your name / what can you do / capabilities', 'About JENNY'],
      ['who made you / your creator', 'Meet the creator'],
      ['hello / hi / hey / how are you', 'Greetings & small talk'],
      ['Keyboard: Esc = restore/close panel, Alt+M = maximize, Cmd+K = focus input', 'Keyboard shortcuts'],
    ]
  },
];

function loadCommandsPanel(el, filter) {
  const q = String(filter == null ? ((document.getElementById('cmd-search') || {}).value || '') : filter).trim().toLowerCase();
  // Match the phrase OR the plain-English description, so searching "joke" and
  // "random jokes" both land on the same entry.
  const match = (pair) => !q || pair[0].toLowerCase().indexOf(q) !== -1 || pair[1].toLowerCase().indexOf(q) !== -1;
  const shown = COMMAND_REF
    .map(s => ({ title: s.title, icon: s.icon, items: s.items.filter(match) }))
    .filter(s => s.items.length);
  const totalCommands = COMMAND_REF.reduce((a, s) => a + s.items.length, 0);
  const matched = shown.reduce((a, s) => a + s.items.length, 0);

  const hero = Viz.hero(
    [Viz.ring(totalCommands, {
      max: Math.max(totalCommands, 10),
      label: q ? 'MATCHED' : 'COMMANDS',
      labelText: q ? (matched + '/' + totalCommands) : String(totalCommands)
    })],
    { title: 'EVERYTHING I CAN DO', sub: COMMAND_REF.length + ' categories · say one in plain English' }
  );

  // The filter box is rebuilt without its own value on purpose: innerHTML does
  // not reset an input's live value, so keeping it out avoids the caret jumping
  // to the end on every keystroke.
  const search = q ? '' :
    '<div class="panel-input" style="border-top:none;padding:0 0 12px 0;">' +
      '<input type="text" id="cmd-search" placeholder="Filter commands..." oninput="loadCommandsPanel(document.getElementById(\'panel-body-commands\'), this.value)">' +
      '<button title="Clear filter" onclick="loadCommandsPanel(document.getElementById(\'panel-body-commands\'), \'\')"><i class="fa-solid fa-xmark"></i></button>' +
    '</div>';

  const breakdown = q ? '' : Viz.section('BY CATEGORY', Viz.stack(
    COMMAND_REF.map((s, i) => ({
      label: s.title,
      value: s.items.length,
      color: 'hsl(' + Math.round((i / COMMAND_REF.length) * 300) + ',70%,62%)'
    }))
  ), 'fa-chart-simple');

  const body = shown.length
    ? shown.map(s => Viz.section(
        s.title.toUpperCase() + ' (' + s.items.length + ')',
        s.items.map(pair =>
          '<div class="cmd-ref-item"><div class="cc">' + escHtml(pair[0]) + '</div><div class="cd">' + escHtml(pair[1]) + '</div></div>'
        ).join(''),
        s.icon
      )).join('')
    : '<div class="panel-empty">No command matches &ldquo;' + escHtml(q) + '&rdquo;.</div>';

  el.innerHTML = hero + search + breakdown + body;
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
async function refreshConversations() {
  const sel = document.getElementById('conv-list');
  if (!sel) return;
  try {
    const res = await fetch('/api/conversations', { cache: 'no-store' });
    const d = await res.json();
    if (!d.success) return;
    const cur = String(d.active_id || '');
    sel.innerHTML = (d.conversations || []).map(c =>
      `<option value="${c.id}">${escHtml(c.title || 'Untitled chat')} (${c.message_count})</option>`
    ).join('');
    if (d.conversations && d.conversations.length && cur) sel.value = cur;
  } catch(e) {}
}

async function newConversation() {
  if (typeof sendMessage === 'function' && confirm('Start a brand-new conversation?')) {
    try { await fetch('/api/conversations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch(e) {}
    refreshConversations();
    const msgs = document.getElementById('msgs');
    if (msgs) msgs.innerHTML = '';
  }
}

async function switchConversation(id) {
  if (!id) return;
  try {
    const r = await fetch('/api/conversations/' + encodeURIComponent(id) + '/switch', { method: 'POST' });
    const d = await r.json();
    if (d.success) {
      const msgs = document.getElementById('msgs');
      if (msgs) msgs.innerHTML = '';
      (d.messages || []).forEach(m => {
        if (m.role === 'user') { const u = document.createElement('div'); u.className = 'msg user'; u.innerHTML = '<div class="avatar">YOU</div><div class="bubble">' + escHtml(m.content) + '</div>'; msgs.appendChild(u); }
        else if (escHtml && m.content) { addAIMessage(m.content); }
      });
      const hs = document.getElementById('chat-scroll');
      if (hs) hs.scrollTop = hs.scrollHeight;
      refreshConversations();
    }
  } catch(e) {}
}

async function launchTray() {
  if (typeof toast !== 'function') return;
  try {
    const r = await fetch('/api/tray/launch', { method: 'POST' });
    const d = await r.json();
    toast(d && d.success ? 'MINI HUD OPENING' : ('TRAY FAILED: ' + (d && d.error || 'unknown')), d && d.success ? 'ok' : 'err');
  } catch(e) { toast('TRAY FAILED', 'err'); }
}

async function sendMessage(text) {
  if (isSending) return;
  isSending = true;
  try {
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
            const agencyLine = b.agency && b.agency.online ? `\nAgency OS: ${b.agency.brief || 'running'}` : (b.mode === 'jarvis' ? '\nAgency OS: offline' : '');
            const briefingText = `${b.greeting}. Here's your briefing for ${b.date} at ${b.time}.\n\nSystem: ${b.system}\nBattery: ${b.battery}\nMemories stored: ${b.vaultCount}${agencyLine}`;
            addAIMessage(briefingText);
            speak(`${b.greeting}. It's ${b.time}. System at ${b.system}, battery ${b.battery}. You have ${b.vaultCount} memories saved, BOSS.`);
          } else { addAIMessage('Unable to fetch briefing, BOSS.'); }
        } catch { removeTyping(); addAIMessage('Briefing service unavailable, BOSS.'); }
        setOrbState('idle');
        return;
      }
      if (cmd.response === '__CHECK_PERMISSIONS__') {
        checkPermissions();
        addAIMessage('Checking system permissions, BOSS. I\'ll show you a guide if anything is missing.');
        speak('Checking your system permissions now.');
        return;
      }
      setTimeout(() => addAIMessage(cmd.response), 300);
      speak(cmd.response);
      refreshConversations();
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
      if (data.reply.command?.action === 'vault-save') { toast('Saved to vault, BOSS.', 'ok'); }
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
      else if (data.reply.command?.action === 'email-read') {
        openPanel('emails');
        loadEmailPanel();
      }
      else if (data.reply.command?.action === 'mode') {
        const mt = (data.reply.command.value || '').toLowerCase();
        if (mt === 'ultron') window.location.href = '/ultron.html';
        else if (mt) applyMode(mt);
      }
      else if (data.reply.command) { await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data.reply.command) }); }
      speak(data.reply.speech || data.reply.text);
      refreshConversations();
    } else { addAIMessage('Something went wrong, BOSS. Please try again.'); setOrbState('idle'); }
  } catch { removeTyping(); addAIMessage('Connection error, BOSS. Please try again.'); setOrbState('idle'); }
  } finally { isSending = false; }
}

// ================================================
// VOICE — TTS (Optimized)
// ================================================
let _cachedVoice = null;
let _cachedMode = null;
let _voicesReady = false;

function ensureVoices(cb) {
  if (_voicesReady) { if (cb) cb(speechSynthesis.getVoices()); return; }
  if (!window.__voiceWaiters) window.__voiceWaiters = [];
  if (cb) window.__voiceWaiters.push(cb);
  if (window.__voiceBooted) return;
  window.__voiceBooted = true;
  const fire = () => {
    _voicesReady = true;
    const vs = speechSynthesis.getVoices();
    (window.__voiceWaiters || []).splice(0).forEach(w => { try { w(vs); } catch(e) {} });
  };
  if (speechSynthesis.getVoices().length) { fire(); }
  else { speechSynthesis.onvoiceschanged = fire; setTimeout(fire, 2500); }
}

// Prefer high-quality / natural / online voices, then mode-appropriate fallbacks.
function pickBestVoice(mode) {
  const mem = loadOfflineMemory();
  const vs = speechSynthesis.getVoices();
  if (!vs.length) return null;
  if (mem.voiceId && /^web-/i.test(mem.voiceId)) {
    const nameKey = mem.voiceId.replace(/^web-/, '').toLowerCase();
    const found = vs.find(v => v.name.toLowerCase().includes(nameKey) && /en/i.test(v.lang)) ||
                  vs.find(v => v.name.toLowerCase().includes(nameKey));
    if (found) return found;
  }
  const naturalRe = /natural|online|neural|premium|enhanced|google us english|google uk english/i;
  const femaleRe = /zira|hazel|aria|samantha|jenny|natasha|michelle|susan|ava|emma|female|woman|girl/i;
  const best = voices => voices.find(v => /en/i.test(v.lang)) || voices[0];
  if (mode === 'ultron') {
    return vs.find(v => /david|mark|guy|christopher|ryan/i.test(v.name) && naturalRe.test(v.name)) ||
           vs.find(v => /david/i.test(v.name)) ||
           vs.find(v => /daniel|mark|james/i.test(v.name)) ||
           best(vs);
  }
  if (mode === 'jarvis') {
    return vs.find(v => /george|guy|ryan/i.test(v.name) && naturalRe.test(v.name)) ||
           vs.find(v => /daniel|george|gb-eng|gb_eng|gb-english/i.test(v.name)) ||
           vs.find(v => /en-gb/i.test(v.lang)) ||
           best(vs);
  }
  return vs.find(v => femaleRe.test(v.name) && naturalRe.test(v.name)) ||
         vs.find(v => femaleRe.test(v.name) && /en/i.test(v.lang)) ||
         vs.find(v => femaleRe.test(v.name)) ||
         vs.find(v => /zira|jenny|aria/i.test(v.name)) ||
         best(vs);
}

function pickVoiceRates(mode, mem) {
  const base = { friday: { rate: 1.05, pitch: 1.1 }, jarvis: { rate: 1.0, pitch: 0.9 }, ultron: { rate: 0.85, pitch: 0.5 } }[mode] || { rate: 1.0, pitch: 1.0 };
  return {
    rate: mem.speechRate > 0 && mem.speechRate <= 2 ? mem.speechRate : base.rate,
    pitch: mem.speechPitch > 0 && mem.speechPitch <= 2 ? mem.speechPitch : base.pitch,
  };
}

function speak(text, onEndCallback) {
  if (!text) return;
  const clean = text.replace(/[*_#`~]/g, '').replace(/https?:\/\/\S+/g, '').replace(/\s+/g, ' ').trim();
  if (!clean) return;
  const spokenText = clean.slice(0, 6000);
  if (typeof setOrbState === 'function') setOrbState('speaking');
  lastSpeakStart = Date.now();
  duckSfx(true);
  // SINGLE-VOICE RULE — the PC's neural engine (edge-tts via /api/speak) is the
  // ONLY voice. The old path preferred the browser's Web Speech (robotic Zira /
  // David over SAPI) which overlapped with the server voice and caused the
  // "two voices at once" bug. Web Speech is now a last-resort crash-net only.
  queueServerSpeech(spokenText, onEndCallback);
}

function speakServer(text) {
  queueServerSpeech(text);
}

// Segment queue: /api/speak now streams edge-tts continuously, so each queued
// utterance is ONE streaming request played as a single <audio> — no gaps
// between sentences, no redundant per-sentence synthesis calls. The queue only
// exists to serialize utterances (single-voice rule) and prefetch the next one.
const serverSpeechQ = { items: [], playing: false, currentEl: null, endPending: [] };

function queueServerSpeech(text, onEndCallback) {
  if (!text) return;
  const clean = text.replace(/[*_#`~]/g, '').replace(/https?:\/\/\S+/g, '').replace(/\s+/g, ' ').trim();
  if (!clean) return;
  if (typeof setOrbState === 'function') setOrbState('speaking');
  lastSpeakStart = Date.now();
  duckSfx(true);
  serverSpeechQ.items.push({ text: clean, el: null });
  if (onEndCallback) serverSpeechQ.endPending.push(onEndCallback);
  pumpServerQueue();
}

function pumpServerQueue() {
  if (serverSpeechQ.playing) return;
  const next = serverSpeechQ.items.shift();
  if (!next) {
    serverSpeechQ.playing = false;
    const endCbs = serverSpeechQ.endPending.splice(0);
    if (typeof setOrbState === 'function' && serverSpeechQ.items.length === 0) { setOrbState('idle'); duckSfx(false); }
    endCbs.forEach(cb => { try { cb(); } catch(e) {} });
    return;
  }
  serverSpeechQ.playing = true;
  const speechUrl = (t) => `/api/speak?text=${encodeURIComponent(t)}&fmt=mp3&t=${Date.now()}`;
  // Prefetch the following utterance so there's no gap after the current one ends.
  if (serverSpeechQ.items.length) {
    const nx = serverSpeechQ.items[0];
    const nxt = new Audio(speechUrl(nx.text));
    nxt.preload = 'auto'; nxt.load();
    nx.el = nxt;
  }
  const el = next.el || new Audio(speechUrl(next.text));
  serverSpeechQ.currentEl = el;
  window.currentSpeechAudio = el;
  const stepServerQueue = () => { serverSpeechQ.playing = false; serverSpeechQ.currentEl = null; window.currentSpeechAudio = null; pumpServerQueue(); };
  el.onended = stepServerQueue;
  el.onerror = stepServerQueue;
  el.play().catch(() => {
    fetch('/api/speak/fallback', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({text: next.text}) }).catch(()=>{});
    stepServerQueue();
  });
}

function stopServerSpeech() {
  serverSpeechQ.items = [];
  serverSpeechQ.endPending = [];
  if (serverSpeechQ.currentEl) { try { serverSpeechQ.currentEl.pause(); } catch(e) {} serverSpeechQ.currentEl = null; }
  if (window.currentSpeechAudio) { try { window.currentSpeechAudio.pause(); } catch(e) {} window.currentSpeechAudio = null; }
  serverSpeechQ.playing = false;
  if (typeof setOrbState === 'function') setOrbState('idle');
  duckSfx(false);
  fetch('/api/speak/stop', { method: 'POST' }).catch(() => {});
}

function speakWeb(text) {
  speak(text);
}

async function loadVoiceBadge() {
  const badge = document.getElementById('voice-badge');
  const nameEl = document.getElementById('voice-badge-name');
  if (!badge && !nameEl) return;
  if (badge) badge.classList.add('loading');
  try {
    const r = await fetch('/api/voice-info', { cache: 'no-store' });
    if (!r.ok) throw new Error('bad status');
    const d = await r.json();
    const v = (d.voices && d.voices[currentMode]) || {};
    let label = (v.voice || '').replace(/\s*\(.*?\)\s*/g, '').trim().split(/[-\s]/).filter(Boolean).slice(0, 2).join(' ');
    if (!label) label = 'Default';
    const eng = ((d.voices && d.voices.__engine__) || {}).__engine_choice__ || '';
    nameEl.textContent = label + (v.rate ? ` \u00d7${v.rate >= 0 ? '+' + v.rate : v.rate}` : '') + (eng ? ` \u00b7 ${eng}` : '');
    if (badge) { badge.classList.remove('loading', 'error'); badge.title = 'Active TTS voice: ' + (v.voice || 'default') + (eng ? ' via ' + eng : ''); }
  } catch (e) {
    if (nameEl) nameEl.textContent = 'offline';
    if (badge) badge.classList.remove('loading'); badge.classList.add('error');
  }
}

let lastSpeakStart = 0;
let modeMotifPlayed = false;

// Throttled spoken status line: confirms UI/command events without stacking a
// long robotic queue (which is what made voices feel late/jumbled before).
let _lastTriggerTs = 0;
function speakTrigger(text, minGapMs) {
  if (!text) return;
  const now = Date.now();
  if (now - _lastTriggerTs < (minGapMs || 1600)) return;
  _lastTriggerTs = now;
  speak(text);
}

function pollSpeakStatus() {
  // UI heartbeat so the server queues (rather than locally speaks) server-
  // initiated utterances for the single browser voice pipeline.
  fetch('/api/speak/ping', { cache: 'no-store' }).catch(() => {});
  drainServerVoiceBus();
  if (typeof orbState !== 'undefined' && orbState === 'speaking') {
    // Safety: if the orb stuck in 'speaking' with no recent speech activity,
    // clear it and stop any server-side speech to avoid a stuck state.
    if (lastSpeakStart && (Date.now() - lastSpeakStart) > 60000) {
      stopServerSpeech();
      if (typeof setOrbState === 'function') setOrbState('idle');
      lastSpeakStart = 0;
    }
  }
}

let _voiceBusBusy = false;
function drainServerVoiceBus() {
  if (_voiceBusBusy) return;
  _voiceBusBusy = true;
  fetch('/api/speak/next', { cache: 'no-store' })
    .then(r => r.json())
    .then(d => {
      if (d && d.item && d.item.text) {
        queueServerSpeech(d.item.text + (d.item.text.endsWith('.') ? '' : '.'));
      }
    })
    .catch(() => {})
    .finally(() => { _voiceBusBusy = false; });
}

setInterval(pollSpeakStatus, 3000);
setInterval(drainServerVoiceBus, 2500);

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
  r.lang = (document.getElementById('sp-lang-txt') || {}).textContent === 'HI' ? 'hi-IN' : 'en-US';
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
  stopServerSpeech();
  sfx.confirm();
  isListening = true;
  dictationTranscript = '';
  if (orbClick) orbClick.classList.add('active');
  setOrbState('listening');
  showSpeechPreview('listening');
  // The server owns the microphone (never request getUserMedia here - it can
  // lock the device so the PC's own STT engine can't capture). We open a LIVE
  // streaming session instead of record-then-confirm: the preview shows the
  // transcript WHILE the user is still speaking.
  let micDeviceIndex = null;
  try {
    const mi = await fetch('/api/stt/mics', { cache: 'no-store' });
    const md = await mi.json();
    const mics = (md && md.mics) || [];
    if (mics.length === 1) micDeviceIndex = mics[0].index;
    else if (mics.length > 1) {
      const def = mics.find(m => m.default) || mics[0];
      micDeviceIndex = def.index;
    }
  } catch {}

  let sid = null;
  try {
    const res = await fetch('/api/stt/live/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({seconds: 12, device: micDeviceIndex}),
    });
    const d = await res.json();
    if (d && d.success && d.sessionId) { sid = d.sessionId; _liveSid = sid; _liveHandled = false; }
    else { toast('Mic: ' + (d.error || 'could not start'), 'err'); stopListening(); return; }
  } catch {
    // Server STT unavailable -> browser Web Speech fallback. NOTE: a
    // SpeechRecognition instance can only be started once in Chromium; reuse
    // silently does nothing, so we always build a brand-new instance here.
    try { recognition?.abort(); } catch {}
    recognition = initRecognition();
    if (!recognition) { stopListening(); toast('Speech recognition not supported', 'err'); return; }
    showSpeechPreview('listening');
    try { recognition.start(); } catch (err) { console.warn('[JENNY] WS start failed:', err); }
    return;
  }

  // Poll the live session: interim text updates the preview in real time,
  // and when it finalizes we auto-send — no confirmation screen at all.
  let finalText = '';
  let errored = false;
  const deadline = Date.now() + 15000;
  while (isListening && Date.now() < deadline) {
    try {
      const r2 = await fetch('/api/stt/live/status/' + sid, { cache: 'no-store' });
      const s = await r2.json();
      if (s && s.success) {
        if (s.interim && s.interim !== finalText) {
          finalText = s.interim;
          updateSpeechPreviewLive(finalText + ' …');
        }
        if (s.error) { errored = true; showSpeechPreview('error', String(s.error).slice(0, 80)); break; }
        if (s.done && s.final) {
          finalText = s.final.trim();
          break;
        }
        if (s.done) { if (!finalText) showSpeechPreview('error', 'No speech heard. Please speak a little louder.'); break; }
      }
    } catch {}
    // small delay keeps the preview snappy without hammering the server
    await new Promise(r => setTimeout(r, 900));
  }
  stopListening();
  if ((sid && !errored) && !_liveHandled && finalText) {
    hideSpeechPreview();
    sendMessage(finalText);
  }
  _liveSid = null;
  _liveHandled = false;
}

function stopListening() {
  isListening = false;
  if (orbClick) orbClick.classList.remove('active');
  if (orbState === 'listening') setOrbState('idle');
  stopSpeechWaves();
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  try { recognition?.stop(); } catch {}
  recognition = null;
}

// ================================================
// SPEECH RECOGNITION PREVIEW (live heard-text bar)
// ================================================
let spAutoTimer = null;
let spPendingText = '';
let _liveSid = null;
let _liveHandled = false;

function showSpeechPreview(mode, text = '') {
  const pv = document.getElementById('speech-preview');
  if (!pv) return;
  pv.classList.remove('hidden');
  const stateEl = document.getElementById('sp-state');
  const textEl = document.getElementById('sp-text');
  if (!stateEl || !textEl) return;
  loadSttLangBadge();
  if (mode === 'listening') {
    stateEl.textContent = 'LISTENING... SPEAK NOW';
    stateEl.className = 'sp-state listening';
    textEl.textContent = 'Speak now';
  } else if (mode === 'thinking') {
    stateEl.textContent = 'PROCESSING...';
    stateEl.className = 'sp-state';
    textEl.textContent = 'Recognizing speech';
  } else if (mode === 'error') {
    stateEl.textContent = 'NOT HEARD';
    stateEl.className = 'sp-state';
    textEl.textContent = text || 'Could not recognize speech.';
    setTimeout(() => { if (!isListening) hideSpeechPreview(); }, 1600);
  }
}

function updateSpeechPreviewLive(text) {
  const pv = document.getElementById('speech-preview');
  if (!pv) return;
  pv.classList.remove('hidden');
  const stateEl = document.getElementById('sp-state');
  const textEl = document.getElementById('sp-text');
  if (!stateEl || !textEl) return;
  stateEl.textContent = 'LIVE — SPEAKING';
  stateEl.className = 'sp-state listening';
  textEl.textContent = text || '…';
}

function hideSpeechPreview() {
  const pv = document.getElementById('speech-preview');
  if (pv) pv.classList.add('hidden');
  if (spAutoTimer) { clearInterval(spAutoTimer); spAutoTimer = null; }
  spPendingText = '';
}

async function stopListeningAndSend() {
  // Tap the orb again while listening: finalize whatever was heard and send it
  // right away (no confirmation). No-op when not listening.
  if (!isListening) return;
  const sid = _liveSid;
  _liveHandled = true;
  stopListening();
  if (sid) {
    try { await fetch('/api/stt/live/stop/' + sid, { method: 'POST' }).catch(() => {}); } catch {}
    try {
      const st = await fetch('/api/stt/live/status/' + sid, { cache: 'no-store' });
      const sd = await st.json();
      const t = (sd && sd.final || '').trim();
      if (t) { hideSpeechPreview(); sendMessage(t); }
      else hideSpeechPreview();
    } catch { hideSpeechPreview(); }
  }
  _liveSid = null;
  _liveHandled = false;
}

function cancelSpeechPreview() {
  if (isListening) {
    // Cancel without sending while a live session is active; the poll loop in
    // startListening() notices isListening flipped and exits without sending.
    stopListening();
  }
  hideSpeechPreview();
  toast('Command cancelled.', 'info');
}

async function toggleSttLang() {
  const current = (document.getElementById('sp-lang-txt') || {}).textContent === 'HI' ? 'hi' : 'en';
  const next = current === 'en' ? 'hi' : 'en';
  try {
    await fetch('/api/stt/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: next }),
    });
    loadSttLangBadge(next);
    toast(`Speech language: ${next === 'hi' ? 'हिन्दी (Hindi)' : 'English'}`, 'ok');
  } catch (e) {
    toast('Language switch failed.', 'err');
  }
}

async function loadSttLangBadge(force) {
  const el = document.getElementById('sp-lang-txt');
  if (!el) return;
  if (force) { el.textContent = force.toUpperCase(); return; }
  try {
    const res = await fetch('/api/stt/language');
    const d = await res.json();
    if (d.success) el.textContent = (d.language === 'hi' ? 'HI' : 'EN');
  } catch (e) {
    el.textContent = 'EN';
  }
}

orbClick.addEventListener('click', () => { isListening ? stopListeningAndSend() : startListening(); });

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
    // A maximized panel is restored before anything else happens. Closing it
    // outright would throw away the wide layout the user just asked for, and
    // one Escape should mean "back one step", not "all the way out".
    const maxPanel = typeof PanelWin !== 'undefined' ? PanelWin.current() : null;
    if (maxPanel) { PanelWin.restore(maxPanel); return; }
    if (openPanels.size > 0) {
      const last = [...openPanels].pop();
      closePanel(last);
    } else {
      chatInput.blur();
    }
    return;
  }

  // Alt+M: maximize / restore the focused panel. Same affordance as the button
  // in the header, for people who drive JENNY from the keyboard.
  if (e.altKey && (e.key === 'm' || e.key === 'M')) {
    e.preventDefault();
    const maxPanel = typeof PanelWin !== 'undefined' ? PanelWin.current() : null;
    const target = maxPanel || document.querySelector('.panel:last-of-type');
    if (target && target.dataset && target.dataset.panel) PanelWin.toggle(target.dataset.panel);
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

function setPhoneQrUrl(targetUrl) {
  const qrImg = document.getElementById('phone-qr-img');
  if (!qrImg) return;
  const data = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&color=d08400&bgcolor=ffffff&data=${encodeURIComponent(targetUrl)}`;
  qrImg.src = data;
  qrImg.onerror = () => {
    qrImg.style.display = 'none';
    const wrap = qrImg.closest('.qr-container-box') || qrImg.parentElement;
    wrap.innerHTML = '<div class="qr-offline-fallback"><i class="fa-solid fa-mobile-screen-button"></i><div class="qr-offline-title">OPEN ON YOUR PHONE</div><div class="qr-offline-url">' + targetUrl + '</div></div>';
  };
}

async function remoteLinkStatus() {
  try {
    const r = await fetch('/api/remote/tunnel/status');
    const d = await r.json();
    const btnTxt = document.getElementById('remote-link-btn-txt');
    const statusEl = document.getElementById('remote-link-status');
    const urlEl = document.getElementById('remote-link-url');
    const togg = document.getElementById('remote-link-toggle');
    const urlPub = document.getElementById('phone-url-pub');
    const pubRow = document.getElementById('phone-url-pub-row');
    if (d && d.running && d.url) {
      const mobileUrl = `${d.url}/mobile.html`;
      if (btnTxt) btnTxt.textContent = 'TURN OFF LINK';
      if (statusEl) { statusEl.textContent = 'ACTIVE'; statusEl.style.color = '#7dffa1'; }
      if (urlEl) urlEl.textContent = d.url;
      if (togg) togg.classList.add('active');
      if (urlPub) urlPub.textContent = mobileUrl;
      if (pubRow) pubRow.style.opacity = '1';
      setPhoneQrUrl(`${d.url}/mobile.html`);
    } else if (d && d.busy) {
      if (btnTxt) btnTxt.textContent = 'CONNECTING...';
      if (statusEl) { statusEl.textContent = 'CONNECTING'; statusEl.style.color = '#ffd27a'; }
      if (togg) togg.classList.add('busy');
    } else {
      if (btnTxt) btnTxt.textContent = 'CREATE LINK';
      if (statusEl) { statusEl.textContent = d && d.last_url ? 'UNLINKED' : 'STANDBY'; statusEl.style.color = ''; }
      const last = (d && d.last_url) || '&mdash;';
      if (urlEl) urlEl.innerHTML = last;
      if (togg) { togg.classList.remove('active'); togg.classList.remove('busy'); }
      if (urlPub && String(urlPub.textContent).includes('trycloudflare')) {
        urlPub.textContent = 'LAN only — use Local URL';
        if (pubRow) pubRow.style.opacity = '0.5';
      }
    }
  } catch (e) {
    /* desktop browser offline — keep last state */
  }
}

async function toggleRemoteLink() {
  try {
    const r = await fetch('/api/remote/tunnel/status');
    const d = await r.json();
    if (d && d.running) {
      await fetch('/api/remote/tunnel/stop', { method: 'POST' });
      toast('Public link turned off. Phone can still connect on Local Wi-Fi.', 'ok');
    } else {
      await fetch('/api/remote/tunnel/start', { method: 'POST' });
      toast('Creating public link — getting your secure URL...', 'info');
    }
    remoteLinkStatus();
    setTimeout(remoteLinkStatus, 3000);
  } catch (e) {
    toast('Remote link error — is the assistant server running?', 'err');
  }
}

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

  let locUrl = '';
  try {
    const rIp = await fetch('/api/local-ip');
    const dIp = await rIp.json();
    locUrl = (dIp.mobileUrl && !String(dIp.mobileUrl).includes('127.0.0.1') && !String(dIp.mobileUrl).includes('localhost'))
      ? dIp.mobileUrl
      : `${window.location.protocol}//${window.location.hostname}:${window.location.port || 3005}/mobile.html`;
    if (urlLoc) urlLoc.textContent = locUrl;
  } catch (e) {
    locUrl = `${window.location.protocol}//${window.location.hostname}:${window.location.port || 3005}/mobile.html`;
    if (urlLoc) urlLoc.textContent = locUrl;
  }

  try {
    const rStatus = await fetch('/api/remote-status');
    const dStatus = await rStatus.json();
    if (dStatus.remoteMode && dStatus.tunnelUrl) {
      const pubUrl = `${dStatus.tunnelUrl}/mobile`;
      if (urlPub) urlPub.textContent = pubUrl;
    } else {
      // No tunnel: Local Wi-Fi IS the way to connect.
      if (urlPub) urlPub.textContent = 'LAN only — use Local URL';
      const pubRow = document.getElementById('phone-url-pub-row');
      if (pubRow) pubRow.style.opacity = '0.5';
    }

    const targetUrl = locUrl;
    setPhoneQrUrl(targetUrl);
  } catch (e) {
    console.error('[PhoneLink] Failed to load remote URLs', e);
    if (urlPub) urlPub.textContent = 'LAN only — use Local URL';
    if (urlLoc) urlLoc.textContent = locUrl;
    setPhoneQrUrl(locUrl);
    toast('Local URL ready — open it on your phone.', 'info');
  }

  setInterval(remoteLinkStatus, 6000);
  remoteLinkStatus();

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

function openMobileSite() {
  const urlLoc = document.getElementById('phone-url-loc');
  const url = urlLoc && urlLoc.textContent && String(urlLoc.textContent).startsWith('http')
    ? urlLoc.textContent
    : `${window.location.protocol}//${window.location.hostname}:${window.location.port || 3005}/mobile.html`;
  window.open(url, '_blank');
  toast('Opening mobile site...', 'info');
}

async function pollDevices() {
  try {
    const res = await fetch('/api/devices');
    const data = await res.json();
    if (!data.success || !data.devices) return;

    const devices = data.devices;
    
    const pending = devices.find(d => d.status === 'pending');
    const approved = devices.find(d => d.linked);

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
      const batTxt = approved.battery != null ? ` · 🔋 ${approved.battery}%` : '';
      const sigTxt = approved.signal ? ` · ${approved.signal}` : '';
      const liveTxt = approved.connected ? '' : ` · offline`;
      document.getElementById('linked-device-meta').textContent = `${approved.browser} · ${approved.ip}${batTxt}${sigTxt}${liveTxt}`;
      document.getElementById('linked-revoke-btn').dataset.deviceId = approved.deviceId;

      const batEl = document.getElementById('phone-stat-battery');
      if (batEl) batEl.textContent = approved.battery != null ? approved.battery + '%' : '--';
      const netEl = document.getElementById('phone-stat-network');
      if (netEl) netEl.textContent = approved.network || approved.signal || '--';

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
  
  // Ask for user input for actions that need a payload
  let finalVal = value;
  if (action === 'toast' && !value) {
    finalVal = prompt('Enter toast message for phone:', 'Hello from desktop, BOSS!');
    if (finalVal === null) return; // user cancelled
  } else if (action === 'speak' && !value) {
    finalVal = prompt('What should the phone say aloud?', 'Hello from your desktop, Boss!');
    if (finalVal === null) return;
  } else if (action === 'open-url' && !value) {
    finalVal = prompt('Enter URL to open on the phone:', 'https://www.google.com');
    if (finalVal === null) return;
    if (!/^https?:\/\//i.test(finalVal)) finalVal = 'https://' + finalVal;
  } else if (action === 'sms' && !value) {
    const num = prompt('Phone number to text:', '');
    if (num === null) return;
    const body = prompt('Message:', 'Hello from your desktop, Boss!');
    if (body === null) return;
    finalVal = JSON.stringify({ number: num.trim(), body });
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
// PHONE CALL WIDGET (PC -> PHONE "dial" + live call status)
// ================================================
let callStartedAt = 0;
let callWidgetTimerInt = null;

async function callPhone() {
  if (!currentLinkedDeviceId) {
    toast('No phone currently linked, BOSS.', 'err');
    return;
  }
  if (window.__callActive || callStartedAt) {
    toast('Call is already active, BOSS.', 'err');
    return;
  }
  try {
    const res = await fetch('/api/device/command/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId: currentLinkedDeviceId, action: 'call', value: '' })
    });
    const d = await res.json();
    if (d.success) {
      toast('Ringing the linked phone...', 'ok');
      showCallWidget('Ringing phone...', 'jenny', 'Incoming call request sent.');
    } else {
      toast('Failed to ring phone.', 'err');
    }
  } catch (err) {
    toast('Failed to ring phone.', 'err');
  }
}

async function hangUpPhone() {
  try {
    await fetch('/api/call/hangup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId: currentLinkedDeviceId })
    });
  } catch (err) {}
  hideCallWidget();
  toast('Call terminated.', 'ok');
}

function showCallWidget(label, who, txt) {
  const w = document.getElementById('call-widget');
  if (!w) return;
  w.classList.remove('hidden');
  const lbl = document.getElementById('call-widget-label');
  if (lbl) lbl.textContent = label.toUpperCase();
  if (txt && who && document.getElementById('call-widget-feed')) {
    feedCallWidget(who, txt);
  }
  const btn = document.getElementById('call-phone-btn');
  if (btn) {
    btn.innerHTML = '<i class="fa-solid fa-phone-slash"></i> HANG UP';
    btn.onclick = hangUpPhone;
  }
}

function hideCallWidget() {
  const w = document.getElementById('call-widget');
  if (!w) return;
  w.classList.add('hidden');
  const btn = document.getElementById('call-phone-btn');
  if (btn) {
    btn.innerHTML = '<i class="fa-solid fa-phone"></i> CALL PHONE';
    btn.onclick = callPhone;
  }
}

function feedCallWidget(who, txt) {
  const feed = document.getElementById('call-widget-feed');
  if (!feed) return;
  const line = document.createElement('div');
  line.className = 'call-widget-line';
  const whoEl = document.createElement('span');
  whoEl.className = 'cw-who';
  whoEl.textContent = who;
  const txtEl = document.createElement('span');
  txtEl.className = 'cw-txt';
  txtEl.textContent = String(txt).slice(0, 220);
  line.appendChild(whoEl);
  line.appendChild(txtEl);
  feed.appendChild(line);
  feed.scrollTop = feed.scrollHeight;
  while (feed.children.length > 30) feed.removeChild(feed.firstChild);
}

function updateCallTimer() {
  const el = document.getElementById('call-widget-timer');
  if (!el) return;
  if (!callStartedAt) { el.textContent = '00:00'; return; }
  const sec = Math.floor((Date.now() - callStartedAt) / 1000);
  const m = Math.floor(sec / 60), s = sec % 60;
  el.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

async function pollCallWidget() {
  const btn = document.getElementById('call-phone-btn');
  if (!btn) return;
  try {
    const res = await fetch('/api/call/status');
    const d = await res.json();
    if (d.success && d.call && d.call.active) {
      document.body.classList.add('pc-call-active');
      if (!callStartedAt) {
        callStartedAt = Date.now();
        const w = document.getElementById('call-widget');
        if (w) w.classList.remove('hidden');
      }
      if (btn.innerHTML.indexOf('HANG UP') < 0) {
        btn.innerHTML = '<i class="fa-solid fa-phone-slash"></i> HANG UP';
        btn.onclick = hangUpPhone;
      }
      if (!callWidgetTimerInt) {
        callWidgetTimerInt = setInterval(updateCallTimer, 1000);
        updateCallTimer();
      }
      const transcript = d.call.transcript || [];
      const last = transcript[transcript.length - 1];
      if (last && last.role === 'jenny') {
        // render last jenny line into feed only when it's new
        const key = d.call.transcript.length + ':' + (last.text || '').slice(0, 40);
        if (key !== window.__lastCallFeedKey) {
          window.__lastCallFeedKey = key;
          if (document.getElementById('call-widget').classList.contains('hidden')) {
            showCallWidget('LIVE CALL', 'jenny', last.text);
          } else {
            feedCallWidget('jenny', last.text);
          }
        }
      }
      // speaking indicator: idle under ~4s means JENNY is mid-utterance
      const speaking = d.call.idle != null && d.call.idle < 4 && last && last.role === 'jenny';
      const lbl = document.getElementById('call-widget-label');
      if (speaking && lbl && lbl.textContent !== 'JENNY SPEAKING...') {
        lbl.textContent = 'JENNY SPEAKING...';
      } else if (!speaking && lbl && lbl.textContent === 'JENNY SPEAKING...') {
        lbl.textContent = 'LIVE CALL WITH PHONE';
      }
    } else {
      document.body.classList.remove('pc-call-active');
      if (callStartedAt) {
        callStartedAt = 0;
        hideCallWidget();
      }
      if (callWidgetTimerInt) { clearInterval(callWidgetTimerInt); callWidgetTimerInt = null; }
      if (document.getElementById('call-widget-timer')) document.getElementById('call-widget-timer').textContent = '00:00';
    }
  } catch (err) {}
}

// Call widget poller wired in phone-link loop below if available
setInterval(pollCallWidget, 4000);

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
// MODE SYSTEM — JARVIS / FRIDAY / ULTRON
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
    greeting: 'Hey Boss! FRIDAY online and ready. What are we doing today?',
    standby: 'Ready when you are, Boss.',
    thinking: 'On it, Boss — give me a sec...',
    farewell: 'Catch you later, Boss!',
    personality: 'Casual, witty, talkative, efficient',
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
      loadVoiceBadge();
      if (!modeMotifPlayed) {
        modeMotifPlayed = true;
        setTimeout(() => { try { sfx.modeStartup(currentMode); } catch(e) {} }, 400);
      }
      return;
    }
    throw new Error('no mode');
  } catch(e) {
    // API unreachable → assume FRIDAY (the default) so the shell still renders.
    if (!document.body.classList.contains('mode-jarvis') && !document.body.classList.contains('mode-friday') && !document.body.classList.contains('mode-ultron')) {
      applyMode('friday');
    }
  }
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
  const greet = ws.querySelector('.welcome-greet');
  if (title) title.textContent = cfg.name;
  if (greet) greet.textContent = mode === 'jarvis'
    ? "Agency OS online — systems nominal, boss. At your command."
    : mode === 'ultron'
    ? "Defense systems active. State your directive."
    : "Hey Boss! FRIDAY's here — what are we doing today?";

  // Live clock row (boot back when hidden / refreshed).
  const clockrow = ws.querySelector('.welcome-clockrow');
  if (clockrow) clockrow.classList.add('ready');
  startWelcomeClock();

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

let _wcClockTimer = null;
function startWelcomeClock() {
  if (_wcClockTimer) clearInterval(_wcClockTimer);
  const timeEl = document.getElementById('wc-time');
  const dateEl = document.getElementById('wc-date');
  if (!timeEl) return;
  const tick = () => {
    const n = new Date();
    timeEl.textContent = n.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (dateEl) dateEl.textContent = n.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  };
  tick();
  _wcClockTimer = setInterval(tick, 1000);
}

function applyMode(mode) {
  currentMode = mode;
  _cachedMode = null;
  _cachedVoice = null;
  
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
  
  sfx.confirm();
  toast(`Switched to ${cfg.name} mode`, 'ok');
  
  showModeWelcome(mode);
  renderModeWelcome(mode);
  toggleAgencyPanel(mode === 'jarvis');
  loadVoiceBadge();
  // Tear down whichever dashboard we are leaving. Without this the outgoing
  // dashboard keeps polling /api/system-status forever in the background, and
  // its canvas handle keeps pointing at a hidden element.
  if (mode !== 'friday') stopFridayDashboard();
  if (mode !== 'jarvis') stopJarvisDashboard();
  // The load history is shared by both dashboards; a stale series from the
  // previous session would be drawn as if it were current.
  loadHistory.cpu.length = 0;
  loadHistory.ram.length = 0;
  loadHistory.disk.length = 0;
  if (mode === 'jarvis') initJarvisDashboard();
  if (mode === 'friday') initFridayDashboard();
}

// Stops every timer a dashboard owns. Paired with each init function so a mode
// switch cannot leave a poll loop running against a hidden panel.
function stopFridayDashboard() {
  if (fdClockTimer) { clearInterval(fdClockTimer); fdClockTimer = null; }
  if (fdRefreshTimer) { clearInterval(fdRefreshTimer); fdRefreshTimer = null; }
  if (fdLoadTimer) { clearInterval(fdLoadTimer); fdLoadTimer = null; }
  fdTrend = null;
}

function stopJarvisDashboard() {
  if (jdClockTimer) { clearInterval(jdClockTimer); jdClockTimer = null; }
  if (jdTelemetryTimer) { clearInterval(jdTelemetryTimer); jdTelemetryTimer = null; }
  jdTrend = null;
}

// ================================================
// FRIDAY WINGMATE DASHBOARD — quick look cards +
// quick runs. Lives in the FRIDAY left panel on
// top of the shared sys-monitor + orb.
// ================================================
let fdClockTimer = null;
let fdRefreshTimer = null;

const FD_RUNS = [
  { cmd: "briefing", icon: "fa-clipboard-list", label: "Briefing" },
  { cmd: "what's the weather", icon: "fa-cloud-sun", label: "Weather" },
  { cmd: "tell me a joke", icon: "fa-face-laugh", label: "Joke" },
  { cmd: "set a timer for 5 minutes", icon: "fa-stopwatch", label: "Timer" },
  { cmd: "play some music", icon: "fa-music", label: "Music" },
  { cmd: "check emails", icon: "fa-envelope", label: "Emails" },
  { cmd: "take a screenshot", icon: "fa-camera", label: "Shot" },
  { cmd: "what can you do", icon: "fa-terminal", label: "Everything" },
];

function initFridayDashboard() {
  const dash = document.getElementById('friday-dashboard');
  if (!dash) return;

  if (fdClockTimer) clearInterval(fdClockTimer);
  const clockEl = document.getElementById('fd-clock');
  const dateEl = document.getElementById('fd-date');
  const tick = () => {
    const n = new Date();
    if (clockEl) clockEl.textContent = n.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (dateEl) dateEl.textContent = n.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  };
  tick();
  fdClockTimer = setInterval(tick, 1000);

  // Quick runs grid.
  const cmdsEl = document.getElementById('fd-cmds');
  if (cmdsEl) {
    cmdsEl.innerHTML = FD_RUNS.map(d =>
      `<button class="fd-cmd" data-fd="${d.cmd}"><i class="fa-solid ${d.icon}"></i><span>${d.label}</span></button>`
    ).join('');
    cmdsEl.querySelectorAll('.fd-cmd').forEach(btn => {
      btn.onclick = () => { if (typeof sendMessage === 'function') sendMessage(btn.dataset.fd); };
    });
  }

  refreshFridayCards();
  if (fdRefreshTimer) clearInterval(fdRefreshTimer);
  fdRefreshTimer = setInterval(refreshFridayCards, 6000);
  // FRIDAY polls more often than the old 60s because the load strip and trend
  // line are now on screen; a once-a-minute refresh made them look frozen.
  if (fdLoadTimer) clearInterval(fdLoadTimer);
  fdLoadTimer = setInterval(refreshFridayLoad, 4000);
  refreshFridayLoad();

  // Casual greeting flavored by time of day.
  const greetEl = document.getElementById('fd-greet');
  if (greetEl) {
    const h = new Date().getHours();
    const openings = [
      "Firing up the engines for the day — what's the plan, Boss?",
      "Alright Boss, give it to me straight — what are we doing today?",
      "Green across the board. Point me anywhere, Boss.",
      "I'm warmed up and ready. What's today's move, Boss?",
    ];
    const period = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
    if (['morning', 'afternoon'].includes(period)) {
      greetEl.textContent = `Good ${period}, Boss! ${openings[Math.floor(Math.random() * 2)]}`;
    } else {
      greetEl.textContent = `Good ${period}, Boss! ${openings[2 + (Math.floor(Math.random() * 2))]}`;
    }
  }
}

let fdMuted = false;
let fdLoadTimer = null;

// Feeds the shared load history and repaints FRIDAY's strip + trend. Separate
// from refreshFridayCards because that one also does slow weather/vault calls.
async function refreshFridayLoad() {
  // Skip when FRIDAY is not the visible dashboard; JARVIS is already polling
  // the same endpoint and the canvas will not be on screen anyway.
  if (!document.body.classList.contains('mode-friday')) return;
  try {
    const res = await fetch('/api/system-status', { cache: 'no-store' });
    if (!res.ok) return;
    const d = await res.json();
    pushLoadSample(d);
    const setLoad = (id, pct, val) => {
      const f = document.getElementById(id + '-fill');
      const v = document.getElementById(id + '-val');
      if (f) f.style.width = Math.min(100, Math.max(0, pct)) + '%';
      if (v) v.textContent = val;
    };
    if (d.cpu) setLoad('fd-cpu', d.cpu.usage, Math.round(d.cpu.usage) + '%');
    if (d.ram) setLoad('fd-ram', d.ram.usage, Math.round(d.ram.usage) + '%');
    if (d.disk) setLoad('fd-disk', d.disk.usage, Math.round(d.disk.usage) + '%');
    if (!fdTrend) fdTrend = drawLoadTrend('fd-trend-canvas', 'fd');
    else fdTrend.draw();
  } catch(e) {}
}

function refreshMuteBtn() {
  const btn = document.getElementById('fd-ctrl-mute');
  if (!btn) return;
  const icon = btn.querySelector('i');
  const label = btn.querySelector('span');
  if (fdMuted) {
    if (icon) icon.className = 'fa-solid fa-volume-xmark';
    if (label) label.textContent = 'UNMUTE';
    btn.classList.add('fd-ctrl-muted');
  } else {
    if (icon) icon.className = 'fa-solid fa-volume-high';
    if (label) label.textContent = 'MUTE';
    btn.classList.remove('fd-ctrl-muted');
  }
}

async function fridayControl(btn, action, value) {
  if (action === 'mute-toggle') {
    fdMuted = !fdMuted;
    action = fdMuted ? 'mute' : 'unmute';
    refreshMuteBtn();
  }
  if (btn) {
    btn.style.transform = 'scale(0.92)';
    setTimeout(() => { if (btn) btn.style.transform = ''; }, 130);
  }
  try {
    const r = await fetch('/api/control', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, value: value ?? '' }),
    });
    const d = await r.json();
    const msg = (d && (d.message || d.error)) ? String(d.message || d.error) : action;
    if (d && d.success) toast(msg.toUpperCase(), 'ok');
    else toast(msg.toUpperCase(), 'err');
  } catch (e) {
    toast('CONTROL FAILED', 'err');
  }
}

async function refreshFridayCards() {
  try {
    const [sysRes, briefRes] = await Promise.all([
      fetch('/api/system-status', { cache: 'no-store' }),
      fetch('/api/briefing', { cache: 'no-store' }).catch(() => null),
    ]);
    const sys = sysRes.ok ? await sysRes.json() : {};
    const b = (briefRes && briefRes.ok) ? await briefRes.json() : {};
    b.briefing = b.briefing || {};

    // ---- gauges ----------------------------------------------------------
    // The four QUICK LOOK cards used to hold one bare number each. A ring says
    // the same number plus how full it is, which is the part you actually read
    // a dial for.
    const gauge = (id, html) => {
      const host = document.getElementById(id);
      if (host) host.innerHTML = html;
    };

    const lvl = sys.battery?.level ?? b.battery?.replace('%', '');
    const batteryPct = lvl != null && lvl !== '' && isFinite(+lvl) ? +lvl : null;
    if (batteryPct != null) {
      // Inverted thresholds: a battery at 20% is the urgent case, so the
      // severity ramp has to run the other way.
      gauge('fd-gauge-battery', Viz.ring(batteryPct, {
        label: batteryPct <= 20 ? 'LOW' : batteryPct <= 40 ? 'FAIR' : 'GOOD',
        labelText: Math.round(batteryPct) + '%',
        color: batteryPct <= 20 ? '#ff5f56' : batteryPct <= 40 ? '#fbbf24' : '#4ade80',
        warn: false, crit: false
      }));
    } else {
      gauge('fd-gauge-battery', Viz.ring(0, { label: 'NO DATA', labelText: '--', color: 'rgba(255,255,255,0.22)', warn: false, crit: false }));
    }
    const batLbl = document.getElementById('fd-battery-lbl');
    if (batLbl) batLbl.textContent = sys.battery?.charging ? 'Battery — charging' : 'Battery';

    const up = sys.uptime || 0;
    gauge('fd-gauge-uptime', Viz.ring(up ? Math.min(100, (up / 86400) * 100) : 0, {
      label: up ? (up >= 86400 ? 'OVER A DAY' : 'TODAY') : 'UNKNOWN',
      labelText: up ? `${Math.floor(up / 3600)}h ${Math.floor((up % 3600) / 60)}m` : '--',
      warn: false, crit: false
    }));

    const vaultCount = b.vaultCount;
    gauge('fd-gauge-memory', Viz.ring(vaultCount != null ? Math.min(100, vaultCount) : 0, {
      label: vaultCount ? 'STORED' : 'EMPTY',
      labelText: vaultCount != null ? String(vaultCount) : '--',
      warn: false, crit: false
    }));

    // System load strip under the gauges.
    const setLoad = (id, pct, val) => {
      const f = document.getElementById(id + '-fill');
      const v = document.getElementById(id + '-val');
      if (f) f.style.width = Math.min(100, Math.max(0, pct)) + '%';
      if (v) v.textContent = val;
    };
    if (sys.cpu) setLoad('fd-cpu', sys.cpu.usage, Math.round(sys.cpu.usage) + '%');
    if (sys.ram) setLoad('fd-ram', sys.ram.usage, Math.round(sys.ram.usage) + '%');
    if (sys.disk) setLoad('fd-disk', sys.disk.usage, Math.round(sys.disk.usage) + '%');

    // Keep the plain text nodes in sync for anything still reading them.
    const batteryEl = document.getElementById('fd-battery-val');
    if (batteryEl) batteryEl.textContent = batteryPct != null ? Math.round(batteryPct) + '%' : '--';
    const upEl = document.getElementById('fd-uptime-val');
    if (upEl) upEl.textContent = up ? `${Math.floor(up / 3600)}h ${Math.floor((up % 3600) / 60)}m` : '--';
    const memEl = document.getElementById('fd-memory-val');
    if (memEl) memEl.textContent = vaultCount != null ? vaultCount : '--';
  } catch(e) {}

  try {
    const w = await fetch('/api/weather', { cache: 'no-store' });
    const d = await w.json();
    const valEl = document.getElementById('fd-weather-val');
    const lblEl = document.getElementById('fd-weather-lbl');
    if (valEl && d.tempC != null) {
      valEl.textContent = `${d.tempC}\u00b0`;
      if (lblEl) lblEl.textContent = `${d.condition || 'Weather'}${d.city ? ' \u00b7 ' + d.city : ''}`;
      // A temperature arc reads faster than a number, and the -20..50 window
      // means 5 degrees and 35 degrees both sit recognisably off-centre.
      const whost = document.getElementById('fd-gauge-weather');
      if (whost) {
        whost.innerHTML = Viz.arc(+d.tempC, {
          min: -20, max: 50, size: 132,
          labelText: Math.round(+d.tempC) + '\u00b0',
          sub: d.city ? String(d.city).slice(0, 14) : ''
        });
      }
    }
  } catch(e) {}
}

// ================================================
// JARVIS EXECUTIVE COMMAND CENTER — dedicated
// Jarvis-only dashboard. Distinct from FRIDAY.
// ================================================
let jdClockTimer = null;
let jdTelemetryTimer = null;

const JD_DIRECTIVES = [
  { cmd: "agency briefing", icon: "fa-clipboard-list", label: "Morning Brief" },
  { cmd: "agency new mission", icon: "fa-crosshairs", label: "Launch Mission" },
  { cmd: "agency outreach", icon: "fa-envelope-open-text", label: "Review Outreach" },
  { cmd: "open notes", icon: "fa-note-sticky", label: "Notebook" },
  { cmd: "open vault", icon: "fa-database", label: "Memory Vault" },
  { cmd: "what can you do", icon: "fa-terminal", label: "All Capabilities" },
];

function initJarvisDashboard() {
  const dash = document.getElementById('jarvis-dashboard');
  if (!dash) return;

  if (jdClockTimer) clearInterval(jdClockTimer);
  const clockEl = document.getElementById('jd-clock');
  const dateEl = document.getElementById('jd-date');
  const tickClock = () => {
    const n = new Date();
    if (clockEl) clockEl.textContent = n.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (dateEl) dateEl.textContent = n.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  };
  tickClock();
  jdClockTimer = setInterval(tickClock, 1000);

  // Directives grid (always available; useful, not decorative).
  const cmdsEl = document.getElementById('jd-cmds');
  if (cmdsEl) {
    cmdsEl.innerHTML = [...JD_DIRECTIVES,
      { cmd: "", icon: "fa-microphone", label: "Speak", cls: "speak" }
    ].map(d => `<button class="jd-cmd ${d.cls || ''}" data-jd="${d.cmd}"><i class="fa-solid ${d.icon}"></i><span>${d.label}</span></button>`).join('');
    cmdsEl.querySelectorAll('.jd-cmd').forEach(btn => {
      btn.onclick = () => {
        const cmd = btn.dataset.jd;
        if (cmd) { if (typeof sendMessage === 'function') sendMessage(cmd); }
        else { if (window.isListening) stopListeningAndSend(); else startListening(); }
      };
    });
  }

  loadJarvisAgency();
  loadJarvisMemory();
  refreshJarvisTelemetry();
  if (jdTelemetryTimer) clearInterval(jdTelemetryTimer);
  jdTelemetryTimer = setInterval(refreshJarvisTelemetry, 4000);
}

async function loadJarvisAgency() {
  const opsEl = document.getElementById('jd-ops');
  if (!opsEl) return;
  try {
    const res = await fetch('/api/briefing', { cache: 'no-store' });
    const d = await res.json();
    const b = d.briefing || {};
    if (b.agency && b.agency.online) {
      const rows = [
        { v: b.agency.agents_online ?? '--', l: 'Agents Online', s: 'Live', cmd: 'agency status' },
        { v: b.agency.agents_working ?? '--', l: 'Working', s: 'Now', cmd: 'agency status' },
        { v: b.agency.leads_today ?? '--', l: 'Leads Today', s: 'Today', cmd: 'agency briefing' },
        { v: b.agency.total_leads ?? '--', l: 'Total Leads', s: 'All time', cmd: 'agency status' },
        { v: b.agency.missions_running ?? '--', l: 'Missions', s: 'Active', cmd: 'agency new mission' },
        { v: b.agency.meetings ?? 0, l: 'Meetings', s: 'Booked', cmd: 'agency briefing' }
      ];
      opsEl.innerHTML = rows.map(r => `
        <div class="jd-op" onclick="openAgencyMax()" title="Maximize Agency OS">
          <button class="jo-expand" onclick="event.stopPropagation();openAgencyMax()" title="Maximize"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></button>
          <button class="jo-chat" onclick="event.stopPropagation();agencyChat('${r.cmd}')" title="Ask JENNY"><i class="fa-solid fa-comment-dots"></i></button>
          <div class="jo-val">${r.v}</div><div class="jo-lbl">${r.l}</div><div class="jo-sub">${r.s}</div>
        </div>`).join('');
    } else {
      const sys = b.system || '--';
      opsEl.innerHTML = [
        { v: b.vaultCount ?? 0, l: 'Memories', s: 'Vault', cmd: 'vault status' },
        { v: b.battery || '--', l: 'Battery', s: 'Power', cmd: 'system status' },
        { v: sys, l: 'Load', s: 'CPU / RAM', cmd: 'system status' }
      ].map(r => `
        <div class="jd-op" onclick="openAgencyMax()" title="Open Agency OS">
          <button class="jo-expand" onclick="event.stopPropagation();openAgencyMax()" title="Maximize"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></button>
          <button class="jo-chat" onclick="event.stopPropagation();agencyChat('${r.cmd}')" title="Ask JENNY"><i class="fa-solid fa-comment-dots"></i></button>
          <div class="jo-val">${r.v}</div><div class="jo-lbl">${r.l}</div><div class="jo-sub">${r.s}</div>
        </div>`).join('');
    }
  } catch(e) {
    opsEl.innerHTML = '<div class="jd-empty" onclick="openAgencyMax()"><i class="fa-solid fa-triangle-exclamation"></i>Briefing unavailable — tap to open Agency OS</div>';
  }
}

let agencyMaxTimer = null;

function agencyChat(cmd) {
  closeAgencyMax();
  if (typeof sendMessage === 'function') {
    sendMessage(cmd);
    toast(`Command sent to JENNY: ${cmd.toUpperCase()}`, 'info');
  }
}

function openAgencyMax() {
  const ov = document.getElementById('agency-max-overlay');
  if (!ov) return;
  ov.classList.remove('hidden');
  ov.style.display = 'flex';
  pollAgencyMax();
  if (agencyMaxTimer) clearInterval(agencyMaxTimer);
  agencyMaxTimer = setInterval(pollAgencyMax, 4000);
}

function closeAgencyMax() {
  const ov = document.getElementById('agency-max-overlay');
  if (ov) { ov.classList.add('hidden'); ov.style.display = 'none'; }
  if (agencyMaxTimer) { clearInterval(agencyMaxTimer); agencyMaxTimer = null; }
}

async function pollAgencyMax() {
  const body = document.getElementById('agency-max-body');
  if (!body) return;
  if (document.getElementById('agency-max-overlay').classList.contains('hidden')) return;
  try {
    const res = await fetch('/api/agency', { cache: 'no-store' });
    const d = await res.json();
    if (!d.online || !d.summary) {
      body.innerHTML = `<div class="agency-max-offline">
        <i class="fa-solid fa-building-circle-xmark"></i>
        <div>AGENCY OS OFFLINE</div>
        <div class="am-off-sub">No server on port 3200. Start the Agency OS app, or set <b>agency_url</b> in Settings.</div>
        <button class="agency-chip" onclick="agencyChat('agency status')"><i class="fa-solid fa-comment-dots"></i>ASK JENNY IN CHAT</button>
      </div>`;
      return;
    }
    const s = d.summary;
    const byStage = s.by_stage || {};
    const stageTotal = Object.values(byStage).reduce((a, b) => a + (Number(b) || 0), 0) || 1;
    const stageRows = Object.entries(byStage).map(([k, v]) => {
      const pct = Math.round((Number(v) / stageTotal) * 100);
      return `<div class="am-stage-row"><div class="am-stage-lbl">${k.replace(/_/g, ' ').toUpperCase()}</div>
        <div class="am-stage-track"><div class="am-stage-fill" style="width:${pct}%"></div></div>
        <div class="am-stage-val">${v} · ${pct}%</div></div>`;
    }).join('');

    const stat = (icon, val, lbl) => `<div class="am-stat"><div class="am-stat-icon"><i class="fa-solid ${icon}"></i></div><div class="am-stat-val">${val}</div><div class="am-stat-lbl">${lbl}</div></div>`;

    body.innerHTML = `
      <div class="am-grid">
        ${stat('fa-robot', s.agents_online ?? '--', 'Agents Online')}
        ${stat('fa-helmet-safety', s.agents_working ?? '--', 'Working Now')}
        ${stat('fa-triangle-exclamation', s.agents_error ?? 0, 'Agents Error')}
        ${stat('fa-bullseye', s.total_leads ?? 0, 'Total Leads')}
        ${stat('fa-bolt', s.leads_today ?? 0, 'Leads Today')}
        ${stat('fa-thumbs-up', s.interested ?? 0, 'Interested')}
        ${stat('fa-question', s.curious ?? 0, 'Curious')}
        ${stat('fa-xmark', s.not_interested ?? 0, 'Not Interested')}
        ${stat('fa-calendar-check', s.meetings ?? 0, 'Meetings')}
        ${stat('fa-reply', s.replies ?? 0, 'Replies')}
        ${stat('fa-clock', s.pending_approval ?? 0, 'Pending Approval')}
        ${stat('fa-paper-plane', s.sent_outreach ?? 0, 'Sent Outreach')}
        ${stat('fa-rocket', s.missions_running ?? 0, 'Missions Running')}
        ${stat('fa-school', s.institution_count ?? 0, 'Institutions')}
      </div>
      <div class="am-section-title"><i class="fa-solid fa-chart-simple"></i> PIPELINE STAGE BREAKDOWN</div>
      <div class="am-stages">${stageRows || '<div class="am-no-pipe">No pipeline data yet.</div>'}</div>
      ${(s.error_agents && s.error_agents.length)
        ? `<div class="am-section-title"><i class="fa-solid fa-circle-exclamation"></i> AGENTS NEEDING ATTENTION</div><div class="am-errors">${s.error_agents.map(a => `<span class="am-err-chip">${a}</span>`).join('')}</div>`
        : ''}
    `;
    const live = document.getElementById('agency-max-live');
    if (live) {
      live.innerHTML = '<span class="am-live-dot"></span>BRIEFING LIVE';
      live.style.color = '';
    }
  } catch (e) {
    body.innerHTML = `<div class="agency-max-offline"><i class="fa-solid fa-unlink"></i><div>CANNOT REACH AGENCY OS</div></div>`;
  }
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !document.getElementById('agency-max-overlay').classList.contains('hidden')) {
    closeAgencyMax();
  }
});

// Rolling load samples for the JARVIS/FRIDAY trend canvases. Kept at module
// scope so the 4s poll extends the line instead of redrawing a single point.
const loadHistory = { cpu: [], ram: [], disk: [] };
const LOAD_HISTORY_MAX = 60;
let jdTrend = null;
let fdTrend = null;

function pushLoadSample(d) {
  const cpu = Viz.num(d.cpu && d.cpu.usage, 0);
  const ram = Viz.num(d.ram && d.ram.usage, 0);
  const disk = Viz.num(d.disk && d.disk.usage, 0);
  loadHistory.cpu.push(cpu);
  loadHistory.ram.push(ram);
  loadHistory.disk.push(disk);
  for (const k of ['cpu', 'ram', 'disk']) {
    while (loadHistory[k].length > LOAD_HISTORY_MAX) loadHistory[k].shift();
  }
}

// Multi-series trend plot. Viz only draws one series per canvas, and drawing
// CPU/RAM/disk into three stacked sparklines would triple the vertical space
// for a comparison the eye is better at making on one plot.
function drawLoadTrend(canvasId, handleName) {
  const cv = document.getElementById(canvasId);
  if (!cv) return null;
  const ctx = cv.getContext('2d');
  if (!ctx) return null;
  const W = cv.width, H = cv.height;
  const pad = 6;
  const usable = H - pad * 2;
  const series = [
    { key: 'cpu', color: '#00d4ff' },
    { key: 'ram', color: '#a855f7' },
    { key: 'disk', color: '#fbbf24' }
  ];
  function draw() {
    ctx.clearRect(0, 0, W, H);
    // Horizontal guides at 25/50/75% so the lines have something to be read
    // against; without them a trend is just a shape with no scale.
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (let g = 1; g < 4; g++) {
      const y = pad + usable - (g / 4) * usable;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    const n = Math.max(loadHistory.cpu.length, loadHistory.ram.length, loadHistory.disk.length);
    if (n < 2) {
      ctx.fillStyle = 'rgba(255,255,255,0.28)';
      ctx.font = '11px monospace';
      ctx.fillText('collecting samples...', 8, H / 2);
      return;
    }
    series.forEach(s => {
      const vals = loadHistory[s.key];
      if (vals.length < 2) return;
      const step = W / (vals.length - 1);
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = i * step;
        const y = pad + usable - Viz.clamp(v / 100, 0, 1) * usable;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.8;
      ctx.lineJoin = 'round';
      ctx.shadowColor = s.color;
      ctx.shadowBlur = 7;
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Head dot marks "now" on each line.
      const lx = (vals.length - 1) * step;
      const ly = pad + usable - Viz.clamp(vals[vals.length - 1] / 100, 0, 1) * usable;
      ctx.beginPath();
      ctx.arc(lx - 2, ly, 2.6, 0, Math.PI * 2);
      ctx.fillStyle = s.color;
      ctx.fill();
    });
  }
  draw();
  return { draw: draw };
}

function jarvisStatusWord(cpu, ram, disk) {
  const worst = Math.max(cpu, ram, disk);
  if (worst >= 90) return { word: 'CRITICAL', color: '#ff5f56' };
  if (worst >= 75) return { word: 'STRAINED', color: '#fbbf24' };
  if (worst >= 50) return { word: 'NOMINAL', color: '#00d4ff' };
  return { word: 'OPTIMAL', color: '#4ade80' };
}

function paintJarvisGauges(d) {
  const host = document.getElementById('jd-gauges');
  if (!host) return;
  const cpu = Viz.num(d.cpu && d.cpu.usage, 0);
  const ram = Viz.num(d.ram && d.ram.usage, 0);
  const disk = Viz.num(d.disk && d.disk.usage, 0);
  const bytes = Viz.num(d.net && d.net.bytes, 0);
  const mbs = bytes / (1024 * 1024);
  // Disk gets a higher warn threshold than CPU: a disk at 85% is a normal
  // full-ish disk, whereas CPU at 85% is a machine that is struggling.
  host.innerHTML =
    Viz.ring(cpu, { label: 'CPU', sub: d.cpu && d.cpu.cores ? d.cpu.cores + 'C' : '', warn: 75, crit: 90 }) +
    Viz.ring(ram, {
      label: 'RAM',
      sub: d.ram && d.ram.usedMB != null && d.ram.totalMB ? Math.round(d.ram.usedMB / 1024) + '/' + Math.round(d.ram.totalMB / 1024) + 'G' : '',
      warn: 80, crit: 92
    }) +
    Viz.ring(disk, {
      label: 'DISK',
      sub: d.disk && d.disk.free ? d.disk.free + ' free' : '',
      warn: false, crit: false
    }) +
    Viz.arc(mbs, { min: 0, max: 12, label: 'NET', labelText: mbs.toFixed(1), sub: 'MB/s' });

  // Reflect the worst reading in the header badge so the state of the machine
  // is visible without reading any of the four gauges.
  const st = jarvisStatusWord(cpu, ram, disk);
  const badge = document.getElementById('jd-status');
  if (badge) {
    badge.textContent = st.word;
    badge.style.color = st.color;
    badge.style.borderColor = st.color + '66';
    badge.style.boxShadow = '0 0 18px ' + st.color + '44';
  }
}

async function refreshJarvisTelemetry() {
  try {
    const res = await fetch('/api/system-status', { cache: 'no-store' });
    const d = await res.json();
    const set = (id, pct, val) => {
      const f = document.getElementById(id + '-fill');
      const v = document.getElementById(id + '-val');
      if (f) f.style.width = Math.min(100, Math.max(0, pct)) + '%';
      if (v) v.textContent = val;
    };
    if (d.cpu) set('jd-cpu', d.cpu.usage, Math.round(d.cpu.usage) + '%');
    if (d.ram) set('jd-ram', d.ram.usage, Math.round(d.ram.usage) + '%');
    if (d.disk) set('jd-disk', d.disk.usage, Math.round(d.disk.usage) + '%');
    if (d.net) {
      const bytes = d.net.bytes || 0;
      const mbs = (bytes / (1024 * 1024)).toFixed(2);
      set('jd-net', Math.min(100, mbs * 8), mbs + ' MB/s');
    }
    pushLoadSample(d);
    paintJarvisGauges(d);
    if (!jdTrend) jdTrend = drawLoadTrend('jd-trend-canvas', 'jd');
    else jdTrend.draw();
  } catch(e) {}
}

async function loadJarvisMemory() {
  const memEl = document.getElementById('jd-memory');
  if (!memEl) return;
  try {
    const r = await fetch('/api/vault', { cache: 'no-store' });
    const v = await r.json();
    const entries = (v.data || []).slice(0, 5);
    if (!entries.length) {
      memEl.innerHTML = '<div class="jd-empty"><i class="fa-solid fa-database"></i>No memories yet &mdash; say &quot;remember ...&quot;</div>';
    } else {
      memEl.innerHTML = entries.map(e =>
        `<div class="jd-mem"><i class="fa-solid fa-circle-check"></i><span>${escHtml(e.text)}</span></div>`
      ).join('');
    }
  } catch(e) {
    memEl.innerHTML = '<div class="jd-empty"><i class="fa-solid fa-database"></i>Memory offline</div>';
  }
}
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
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
      const g = { jarvis: 'Switching to Jarvis mode. At your service, Sir.', friday: 'Friday mode engaged. Ready when you are, Boss!' }[mode];
      if (g && typeof speakTrigger === 'function') speakTrigger(g, 300);
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
  const c = colors[mode] || '#6d8bff';
  
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
      if (typeof speakTrigger === 'function') speakTrigger('Gesture control activated. Show me your hands, Boss.', 300);
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
    if (typeof speakTrigger === 'function') speakTrigger('Gesture control deactivated.', 200);
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
      <div style="display:flex;gap:12px;margin-bottom:8px;">
        <div style="flex:1;text-align:center;">
          <div style="font-family:var(--orbitron);font-size:12px;color:#00d4ff;" id="gesture-hands">0</div>
          <div style="font-family:var(--mono);font-size:8px;color:rgba(255,255,255,0.4);letter-spacing:1px;">HANDS</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-family:var(--orbitron);font-size:12px;color:#ff9800;" id="gesture-mode">pointer</div>
          <div style="font-family:var(--mono);font-size:8px;color:rgba(255,255,255,0.4);letter-spacing:1px;">MODE</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-family:var(--orbitron);font-size:12px;color:#4caf50;" id="gesture-orb">OFF</div>
          <div style="font-family:var(--mono);font-size:8px;color:rgba(255,255,255,0.4);letter-spacing:1px;">ORB</div>
        </div>
      </div>
      <div style="font-family:var(--mono);font-size:9px;color:rgba(255,255,255,0.3);text-align:center;">
        Point=Move | Pinch=Click | Palm=Toggle | Fist=Pause
      </div>
      <div style="display:flex;gap:6px;margin-top:8px;">
        <button onclick="runGestureCmd('browser_open')" style="flex:1;background:rgba(255,62,62,0.06);border:1px solid rgba(255,62,62,0.25);color:#ff8a8a;font-family:var(--mono);font-size:9px;padding:6px 0;border-radius:6px;cursor:pointer;">BROWSER</button>
        <button onclick="runGestureCmd('volume_up')" style="flex:1;background:rgba(255,62,62,0.06);border:1px solid rgba(255,62,62,0.25);color:#ff8a8a;font-family:var(--mono);font-size:9px;padding:6px 0;border-radius:6px;cursor:pointer;">VOL+</button>
        <button onclick="runGestureCmd('screenshot')" style="flex:1;background:rgba(255,62,62,0.06);border:1px solid rgba(255,62,62,0.25);color:#ff8a8a;font-family:var(--mono);font-size:9px;padding:6px 0;border-radius:6px;cursor:pointer;">SHOT</button>
      </div>
    `;
    document.body.appendChild(panel);
  }
  
  const camEl = document.getElementById('gesture-cam');
  if (camEl) {
    camEl.innerHTML = '<img id="gesture-cam-img" style="width:100%;height:100%;object-fit:cover;border-radius:8px;" src="/api/gesture/frame?t=' + Date.now() + '">';
    const camImg = document.getElementById('gesture-cam-img');
    if (gestureActive) {
      setInterval(() => {
        if (!gestureActive || document.hidden) return;
        camImg.src = '/api/gesture/frame?t=' + Date.now();
      }, 300);
    }
  }
  
  pollGestureStatus();
}

function runGestureCmd(action) {
  fetch('/api/gesture/cmd', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({action: action})})
    .then(r=>r.json()).then(d => { if (d && d.success) { const n=document.getElementById('gesture-name'); if(n) n.textContent = 'OK: ' + action; } }).catch(()=>{});
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
    const handsEl = document.getElementById('gesture-hands');
    if (handsEl) handsEl.textContent = (d.num_hands) || '0';
    const modeEl = document.getElementById('gesture-mode');
    if (modeEl && d.control_mode) {
      modeEl.textContent = d.control_mode.toUpperCase();
      modeEl.style.color = d.control_mode === 'pointer' ? '#ff9800' : '#00d4ff';
    }
    const orbEl = document.getElementById('gesture-orb');
    if (orbEl) {
      orbEl.textContent = d.orb_drive ? 'ON' : 'OFF';
      orbEl.style.color = d.orb_drive ? '#0f0' : 'rgba(255,255,255,0.4)';
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
// WAKE WORD — server-side, always-on
// The listener runs inside the server (speech_stt) so "Hey Jenny" works even
// when this tab isn't focused. The button toggles it via /api/wake/toggle and
// the UI consumes /api/wake/events to render the server-driven conversation.
// ================================================
let wakeWordActive = false;
let _wakeEventsTimer = null;

const WAKE_WORDS = ['hey jenny', 'hey friday', 'hey jarvis', 'hey ultron'];

function updateWakeWordUI() {
  const btn = document.getElementById('wake-word-btn');
  if (btn) {
    btn.classList.toggle('active', wakeWordActive);
    const d = wakeDiagnostics || {};
    const bits = [];
    if (wakeWordActive) {
      bits.push('Wake word ON — Say "Hey Jenny" anytime');
      if (d.streamOpen) bits.push('MIC STREAM OPEN');
      else bits.push('MIC STREAM CLOSED');
      if (d.device) bits.push('device: ' + d.device);
      if (d.lastError) bits.push('lastError: ' + d.lastError);
    } else {
      bits.push('Wake word OFF — Click to enable');
      if (d.lastError) bits.push('lastError: ' + d.lastError);
    }
    btn.title = bits.join(' · ');
  }
}

let wakeDiagnostics = null;

async function syncWakeStatus() {
  try {
    const r = await fetch('/api/wake/status', { cache: 'no-store' });
    const d = await r.json();
    const phrases = (d && d.phrases) || WAKE_WORDS;
    const on = !!(d && d.on);
    if (d) wakeDiagnostics = { streamOpen: !!d.streamOpen, device: d.device || '', lastError: d.lastError || '' };
    if (on !== wakeWordActive) {
      wakeWordActive = on;
      updateWakeWordUI();
    } else {
      updateWakeWordUI();
    }
    if (on && !window.__wakeNotified) {
      window.__wakeNotified = true;
      toast(`Wake word active — Say "${phrases[0]}" anytime`, 'ok');
    }
  } catch {}
}

async function toggleWakeWord() {
  try {
    const r = await fetch('/api/wake/toggle', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({on: !wakeWordActive}),
    });
    const d = await r.json();
    if (d && 'on' in d) { wakeWordActive = !!d.on; updateWakeWordUI(); }
    toast(wakeWordActive ? 'Wake word ON — Say "Hey Jenny" anytime' : 'Wake word OFF', 'info');
  } catch(e) { toast('Wake toggle failed: ' + e.message, 'err'); }
}

function startWakeWord() { toggleWakeWord(); }
function stopWakeWord() { toggleWakeWord(); }
function onWakeWordDetected() {}

async function executeCommandAction(cmd) {
  if (!cmd || !cmd.action) return;
  try {
    if (cmd.action === 'email-read') { openPanel('emails'); loadEmailPanel(); }
    else if (cmd.action === 'open-folder') {
      if (cmd.value) window.open(`/api/open-folder?path=${encodeURIComponent(cmd.value)}`, '_blank');
      await fetch('/api/control', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(cmd) });
    }
    else if (cmd.action === 'open-chrome') {
      if (cmd.value) await fetch(`/api/open-chrome?url=${encodeURIComponent(cmd.value)}`);
    }
    else if (cmd.action === 'mode') {
      const mt = (cmd.value || '').toLowerCase();
      if (mt === 'ultron') window.location.href = '/ultron.html';
      else if (mt) applyMode(mt);
    }
    else if (cmd.action === 'agent-start') {
      const goal = typeof cmd.value === 'string' ? cmd.value : (cmd.value && cmd.value.goal) || '';
      agentPendingGoal = goal;
      if (!openPanels.has('agent')) openPanel('agent');
      const gi = document.getElementById('agent-goal');
      if (gi && goal) gi.value = goal;
      await agentPost('start', { goal });
    }
    else if (cmd.action === 'agent-stop') { await agentPost('stop', { reason: 'voice' }); }
    else if (cmd.action === 'agent-kill') { await agentPost('kill', { reason: 'voice' }); }
    else if (cmd.action === 'agent-reset') { await agentPost('reset', {}); }
    else if (cmd.action === 'agent-status') {
      if (!openPanels.has('agent')) openPanel('agent');
      else pollAgent();
    }
    else if (cmd.action === 'open-chrome-bookmarks') {
      const bmr = await fetch('/api/chrome-bookmarks'); const bmd = await bmr.json();
      if (bmd.success && bmd.bookmarks && bmd.bookmarks.length) {
        let t = `**Your Chrome Bookmarks** (${bmd.total} total):\n\n`;
        bmd.bookmarks.slice(0, 15).forEach((b, i) => { t += `${i+1}. **${b.name}** — ${b.url}\n`; });
        if (bmd.total > 15) t += `\n_...and ${bmd.total - 15} more._`;
        addAIMessage(t);
      } else addAIMessage('No Chrome bookmarks found, Boss.');
    }
    else if (cmd.action !== 'vault-save') {
      await fetch('/api/control', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(cmd) });
    }
  } catch(e) { console.warn('[WakeEvent] command execute failed:', e); }
}

// Poll server-side wake events so a headless "Hey Jenny" conversation shows up
// in this dashboard as normal chat bubbles (and executes command actions).
async function pollWakeEvents() {
  try {
    const r = await fetch('/api/wake/events', { cache: 'no-store' });
    const d = await r.json();
    if (!d || !d.success || !Array.isArray(d.events) || !d.events.length) return;
    for (const ev of d.events) {
      if (!ev) continue;
      if (ev.kind === 'wake') {
        addUserMessage(ev.text + ' ');
        setOrbState('listening');
        setTimeout(() => setOrbState('idle'), 600);
      } else if (ev.kind === 'user') {
        addUserMessage(ev.source === 'phone' ? '[Phone] ' + ev.text : ev.text);
      } else if (ev.kind === 'cmd') {
        // A phone control action executed on the PC — show it as a compact note.
        addAIMessage(ev.text || '');
      } else if (ev.kind === 'assistant') {
        addAIMessage(ev.text || '');
        // Phone-originated commands are already executed by the phone itself;
        // only run the command here when it came from the local wake pipeline.
        if (ev.command && ev.command.action && ev.command.action !== 'vault-save' && ev.source !== 'phone') {
          executeCommandAction(ev.command);
        }
      }
    }
  } catch {}
}

function initWakeWord() {
  syncWakeStatus();
  if (!_wakeEventsTimer) {
    _wakeEventsTimer = setInterval(pollWakeEvents, 2500);
  }
  return true;
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
  
  let lastDraw = 0;
  let rafId = null;
  function draw(now) {
    rafId = null;
    const bs = document.getElementById('boot-screen');
    if (!bs || bs.classList.contains('done')) return; // loop stops forever
    if (document.hidden) return; // pause while backgrounded; onPVis resumes
    if (now - lastDraw < 50) { rafId = requestAnimationFrame(draw); return; } // ~20fps is plenty for this ambience
    lastDraw = now;
    ctx.clearRect(0, 0, w, h);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(109,139,255,${p.alpha})`;
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
          ctx.strokeStyle = `rgba(109,139,255,${0.05 * (1 - dist / 120)})`;
          ctx.stroke();
        }
      }
    }
    rafId = requestAnimationFrame(draw);
  }
  function onPVis() {
    if (document.hidden) return;
    const bs = document.getElementById('boot-screen');
    if (bs && !bs.classList.contains('done') && !rafId) rafId = requestAnimationFrame(draw);
  }
  document.addEventListener('visibilitychange', onPVis);
  draw();
  
  window.addEventListener('resize', () => {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  });
}
