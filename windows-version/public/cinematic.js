/**
 * JENNY Cinematic Intro — deep blue-violet hologram
 *
 * Hybrid engine:
 *   1. If /intro.mp4 exists  -> play it fullscreen (real video intro).
 *   2. Else (or on video end) -> live canvas sequence:
 *        energy core -> orbital rings + particle streams -> humanoid silhouette
 *        crystallizes into the letter "J" -> title reveal + WebAudio score.
 *   3. Emits 'intro:done' on window and calls opts.onDone().
 *
 * Performance rules (per project skills):
 *   - no shadowBlur inside the render loop (pre-baked radial gradients instead)
 *   - animate transform/opacity on DOM, only the canvas moves pixels
 *   - honors prefers-reduced-motion (skips straight to done)
 */
(function () {
  const REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- WebAudio sci-fi score (procedural, no assets) ----
  let audioCtx = null, masterGain = null;
  function ensureAudio() {
    if (audioCtx) { if (audioCtx.state === 'suspended') audioCtx.resume(); return audioCtx; }
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AC();
      masterGain = audioCtx.createGain();
      masterGain.gain.value = 0.0;
      masterGain.connect(audioCtx.destination);
    } catch (e) { audioCtx = null; }
    return audioCtx;
  }

  // Autoplay policy: webviews may block audio until a user gesture. Unlock on
  // the first interaction (click/key) and again whenever playScore starts.
  function armAudioUnlock() {
    const resume = () => { ensureAudio(); };
    window.addEventListener('pointerdown', resume, { once: true });
    window.addEventListener('keydown', resume, { once: true });
  }
  armAudioUnlock();

  // Pre-baked glows (avoid per-frame gradient churn): rebuild only on resize.
  function makeGlow(ctx, w, h) {
    const cx = w / 2, cy = h / 2;
    const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(w, h) * 0.22);
    core.addColorStop(0, 'rgba(109,139,255,0.95)');
    core.addColorStop(0.35, 'rgba(139,92,246,0.55)');
    core.addColorStop(0.7, 'rgba(168,85,247,0.18)');
    core.addColorStop(1, 'rgba(168,85,247,0)');
    const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(w, h) * 0.55);
    halo.addColorStop(0, 'rgba(109,139,255,0.30)');
    halo.addColorStop(0.5, 'rgba(168,85,247,0.10)');
    halo.addColorStop(1, 'rgba(34,211,238,0)');
    return { core, halo };
  }

  function playScore() {
    const ctx = ensureAudio();
    if (!ctx) return;
    if (ctx.state === 'suspended') ctx.resume();
    const t0 = ctx.currentTime;
    // Slow riser: ascending chord + sub pulse + shimmering arpeggio
    const chords = [
      [110, 164.81, 220],     // A2  major feel
      [146.83, 220, 293.66],  // D3
      [164.81, 246.94, 329.63]// E3
    ];
    masterGain.gain.cancelScheduledValues(t0);
    masterGain.gain.setValueAtTime(0.0, t0);
    masterGain.gain.linearRampToValueAtTime(0.5, t0 + 3.5);
    masterGain.gain.linearRampToValueAtTime(0.35, t0 + 9.0);
    masterGain.gain.linearRampToValueAtTime(0.0, t0 + 12.5);

    chords.forEach((ch, i) => {
      ch.forEach((f) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'sawtooth';
        o.frequency.value = f;
        const lfo = ctx.createOscillator(), lg = ctx.createGain();
        lfo.frequency.value = 0.15 + i * 0.05; lg.gain.value = f * 0.004;
        lfo.connect(lg).connect(o.frequency);
        const filt = ctx.createBiquadFilter();
        filt.type = 'lowpass'; filt.frequency.value = 700 + i * 260; filt.Q.value = 6;
        const start = t0 + i * 3.0;
        g.gain.setValueAtTime(0.0, start);
        g.gain.linearRampToValueAtTime(0.16, start + 1.4);
        g.gain.linearRampToValueAtTime(0.0, start + 3.4);
        o.connect(filt).connect(g).connect(masterGain);
        o.start(start); o.stop(start + 3.5);
        lfo.start(start); lfo.stop(start + 3.5);
      });
    });

    // Shimmer arpeggio (holographic sparkle)
    [523.25, 659.25, 783.99, 1046.5, 1318.51, 1046.5, 1567.98].forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'triangle'; o.frequency.value = f;
      const s = t0 + 1.2 + i * 0.42;
      g.gain.setValueAtTime(0.0, s);
      g.gain.linearRampToValueAtTime(0.06, s + 0.06);
      g.gain.exponentialRampToValueAtTime(0.0005, s + 0.7);
      o.connect(g).connect(masterGain);
      o.start(s); o.stop(s + 0.75);
    });

    // Cinematic sub-boom at the J reveal
    const boom = ctx.createOscillator(), bg = ctx.createGain();
    boom.type = 'sine'; boom.frequency.setValueAtTime(70, t0 + 5.2);
    boom.frequency.exponentialRampToValueAtTime(38, t0 + 6.4);
    bg.gain.setValueAtTime(0.0, t0 + 5.2);
    bg.gain.linearRampToValueAtTime(0.5, t0 + 5.35);
    bg.gain.exponentialRampToValueAtTime(0.001, t0 + 7.2);
    boom.connect(bg).connect(masterGain);
    boom.start(t0 + 5.2); boom.stop(t0 + 7.3);
  }

  function stopScore() {
    if (masterGain && audioCtx) {
      try {
        const t = audioCtx.currentTime;
        masterGain.gain.cancelScheduledValues(t);
        masterGain.gain.setValueAtTime(masterGain.gain.value, t);
        masterGain.gain.linearRampToValueAtTime(0.0, t + 1.2);
      } catch (e) {}
    }
  }

  // ---- overlay DOM ----
  function buildOverlay() {
    const ov = document.createElement('div');
    ov.id = 'jenny-cinematic';
    ov.style.cssText = 'position:fixed;inset:0;z-index:10000;background:radial-gradient(ellipse at 50% 40%, #0a0f2e 0%, #050508 55%, #000 100%);display:flex;align-items:center;justify-content:center;opacity:1;transition:opacity 1.1s cubic-bezier(0.16,1,0.3,1);overflow:hidden';
    ov.innerHTML =
      '<canvas id="jenny-cine-canvas" style="position:absolute;inset:0;width:100%;height:100%"></canvas>' +
      '<video id="jenny-cine-vid" playsinline style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none"></video>' +
      '<div id="jenny-cine-vig" style="position:absolute;inset:0;background:radial-gradient(ellipse at center,transparent 35%,rgba(0,0,0,0.72) 100%);pointer-events:none"></div>' +
      '<div id="jenny-cine-logo" style="position:relative;z-index:5;display:flex;flex-direction:column;align-items:center;text-align:center;opacity:0;transform:translateY(24px) scale(0.96);transition:opacity 1.1s cubic-bezier(0.16,1,0.3,1),transform 1.1s cubic-bezier(0.16,1,0.3,1)">' +
        '<div style="position:relative">' +
          '<img src="/logo.png" alt="JENNY" style="width:min(40vh,320px);height:auto;display:block;filter:drop-shadow(0 0 34px rgba(34,211,238,0.45)) drop-shadow(0 0 70px rgba(168,85,247,0.4));animation:cine-float 4.2s ease-in-out infinite" onerror="this.style.display=\'none\'">' +
          '<div class="cine-scan" style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 0%,rgba(157,180,255,0.16) 44%,rgba(34,211,238,0.35) 50%,rgba(157,180,255,0.16) 56%,transparent 100%);background-size:100% 140%;background-position:0 -140%;animation:cine-scan 2.6s ease-in-out infinite;mix-blend-mode:screen;border-radius:14px"></div>' +
        '</div>' +
        '<div class="cine-word" style="font-family:Orbitron,sans-serif;font-weight:900;font-size:clamp(28px,6vw,64px);letter-spacing:0.32em;background:linear-gradient(135deg,#22d3ee,#a78bfa,#f0abfc);-webkit-background-clip:text;background-clip:text;color:transparent;margin-top:28px;text-shadow:none">J.E.N.N.Y</div>' +
        '<div class="cine-sub" style="font-family:Share Tech Mono,monospace;font-size:clamp(9px,1.4vw,13px);letter-spacing:0.55em;color:rgba(167,199,255,0.7);margin-top:14px;text-transform:uppercase">Just A Neural Network Yielding Intelligence</div>' +
        '<div id="jenny-cine-phase" style="font-family:Share Tech Mono,monospace;font-size:10px;letter-spacing:0.4em;color:rgba(168,85,247,0.85);margin-top:34px;min-height:16px;text-transform:uppercase"></div>' +
        '<button id="jenny-cine-skip" style="margin-top:40px;background:rgba(255,255,255,0.04);border:1px solid rgba(109,139,255,0.4);color:rgba(255,255,255,0.7);font-family:Orbitron,sans-serif;font-size:10px;letter-spacing:0.3em;padding:11px 30px;border-radius:10px;cursor:pointer;transition:all 0.2s cubic-bezier(0.16,1,0.3,1)">SKIP INTRO</button>' +
      '</div>' +
      '<style>@keyframes cine-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}@keyframes cine-scan{0%{background-position:0 -140%}55%{background-position:0 10%}100%{background-position:0 120%}}@media (prefers-reduced-motion: reduce){.cine-float,.cine-scan{animation:none!important}}</style>';
    document.body.appendChild(ov);
    return ov;
  }

  // ---- canvas sequence ----
  function runCanvas(canvas, phaseEl, onDone) {
    const ctx = canvas.getContext('2d');
    let w, h, glow, raf, start = performance.now();
    const DPR = Math.min(window.devicePixelRatio || 1, 2);

    function size() {
      w = canvas.width = Math.floor(window.innerWidth * DPR);
      h = canvas.height = Math.floor(window.innerHeight * DPR);
      glow = makeGlow(ctx, w, h);
    }
    size();
    window.addEventListener('resize', size);

    const DURATION = 11500; // ms
    const phases = [
      [0,    'NEURAL CORE IGNITING'],
      [2200, 'ENERGY FIELD STABILIZING'],
      [4600, 'HUMANOID MATRIX SYNTHESIZING'],
      [6800, 'IDENTITY LOCK: J'],
      [9000, 'SYSTEMS ONLINE']
    ];
    let phaseIdx = -1;

    // Particle streams: spiral into center (pre-allocated, no per-frame growth)
    const N = Math.min(320, Math.floor((window.innerWidth * window.innerHeight) / 5200));
    const parts = [];
    for (let i = 0; i < N; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = (Math.random() * 0.5 + 0.5) * Math.max(w, h) * 0.5;
      parts.push({
        a, r, baseR: r, spd: 0.15 + Math.random() * 0.5,
        sz: (Math.random() * 2.2 + 0.7) * DPR,
        hue: Math.random() < 0.6 ? 0 : (Math.random() < 0.5 ? 1 : 2)
      });
    }
    const COLORS = ['109,139,255', '168,85,247', '34,211,238'];

    // Pre-computed orbital ring paths
    function ringPath(cx, cy, R, tilt, squash, phase, t) {
      const pts = [];
      for (let i = 0; i <= 64; i++) {
        const ang = (i / 64) * Math.PI * 2 + phase + t * 0.3;
        const rx = R * Math.cos(ang);
        const ry = R * Math.sin(ang) * squash;
        pts.push([
          cx + rx * Math.cos(tilt) - ry * Math.sin(tilt),
          cy + rx * Math.sin(tilt) + ry * Math.cos(tilt)
        ]);
      }
      return pts;
    }

    // Humanoid silhouette -> letter J: parametric points for head/shoulders + J strokes
    function drawHumanoidJ(ctx, cx, cy, s, alpha) {
      if (alpha <= 0) return;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // Wireframe humanoid head + shoulders (left of the J reads as the figure)
      const hy = cy - s * 0.42;
      ctx.strokeStyle = 'rgba(157,180,255,0.55)';
      ctx.lineWidth = 2.2 * DPR;
      ctx.beginPath();
      ctx.ellipse(cx, hy, s * 0.16, s * 0.19, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.30, cy + s * 0.30);
      ctx.quadraticCurveTo(cx - s * 0.30, hy + s * 0.24, cx, hy + s * 0.26);
      ctx.quadraticCurveTo(cx + s * 0.30, hy + s * 0.24, cx + s * 0.30, cy + s * 0.30);
      ctx.stroke();

      // Circuit nodes on the figure
      const nodes = [[0, hy - s * 0.19], [-s * 0.30, cy + s * 0.30], [s * 0.30, cy + s * 0.30]];
      ctx.fillStyle = 'rgba(34,211,238,0.9)';
      nodes.forEach(([nx, ny]) => {
        ctx.beginPath();
        ctx.arc(cx + nx, ny, 3 * DPR, 0, Math.PI * 2);
        ctx.fill();
      });

      // The crystallizing letter J (strokes)
      ctx.strokeStyle = 'rgba(196,181,253,0.98)';
      ctx.lineWidth = s * 0.11;
      ctx.beginPath();
      ctx.moveTo(cx, cy - s * 0.5);   // top of stem
      ctx.lineTo(cx, cy + s * 0.30);  // stem down
      ctx.arcTo(cx, cy + s * 0.55, cx - s * 0.34, cy + s * 0.55, s * 0.25); // hook left
      ctx.lineTo(cx - s * 0.30, cy + s * 0.55);
      ctx.stroke();
      // serif foot
      ctx.lineWidth = s * 0.07;
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.44, cy - s * 0.5);
      ctx.lineTo(cx, cy - s * 0.5);
      ctx.stroke();

      ctx.restore();
    }

    function frame(now) {
      const t = (now - start) / 1000;
      const p = Math.min(1, (now - start) / DURATION);
      ctx.clearRect(0, 0, w, h);

      // phase labels
      for (let i = phases.length - 1; i >= 0; i--) {
        if (now - start >= phases[i][0]) {
          if (phaseIdx !== i) {
            phaseIdx = i;
            if (phaseEl) {
              phaseEl.style.opacity = '0';
              setTimeout(() => { phaseEl.textContent = phases[i][1]; phaseEl.style.opacity = '1'; }, 180);
            }
          }
          break;
        }
      }

      const cx = w / 2, cy = h * 0.46;

      // halo (pre-baked), breathes via globalAlpha only
      ctx.save();
      ctx.globalAlpha = 0.5 + 0.3 * Math.sin(t * 1.6);
      ctx.fillStyle = glow.halo;
      ctx.fillRect(0, 0, w, h);
      ctx.globalAlpha = 0.55 + 0.25 * Math.sin(t * 2.3);
      ctx.fillStyle = glow.core;
      ctx.fillRect(0, 0, w, h);
      ctx.restore();

      // orbital rings (3 tilts, rotating with time)
      const rings = [
        { R: Math.min(w, h) * 0.30, tilt: 0.32, sq: 0.34, ph: t * 0.35, col: '109,139,255', lw: 2.0 },
        { R: Math.min(w, h) * 0.24, tilt: -0.5, sq: 0.42, ph: -t * 0.5, col: '168,85,247', lw: 1.6 },
        { R: Math.min(w, h) * 0.34, tilt: 1.1, sq: 0.22, ph: t * 0.22, col: '34,211,238', lw: 1.2 }
      ];
      ctx.save();
      rings.forEach((rg) => {
        const pts = ringPath(cx, cy, rg.R, rg.tilt, rg.sq, rg.ph, t);
        ctx.strokeStyle = `rgba(${rg.col},${0.30 + 0.22 * Math.sin(t + rg.R)})`;
        ctx.lineWidth = rg.lw * DPR;
        ctx.beginPath();
        pts.forEach((pt, i) => i ? ctx.lineTo(pt[0], pt[1]) : ctx.moveTo(pt[0], pt[1]));
        ctx.closePath();
        ctx.stroke();
        // orbiting node
        const idx = Math.floor((t * 40) % pts.length);
        ctx.fillStyle = `rgba(${rg.col},0.95)`;
        ctx.beginPath();
        ctx.arc(pts[idx][0], pts[idx][1], 3.5 * DPR, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();

      // particle streams spiraling inward
      ctx.save();
      const converge = Math.min(1, Math.max(0, (t - 3.5) / 3)); // pull in later
      parts.forEach((pt) => {
        pt.a += pt.spd * 0.016;
        const rr = pt.baseR * (1 - converge * 0.75) + Math.sin(t * 2 + pt.baseR) * 6 * DPR;
        const x = cx + Math.cos(pt.a) * rr;
        const y = cy + Math.sin(pt.a) * rr * 0.85;
        ctx.fillStyle = `rgba(${COLORS[pt.hue]},${0.35 + 0.4 * Math.sin(t * 3 + pt.a)})`;
        ctx.beginPath();
        ctx.arc(x, y, pt.sz, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();

      // Humanoid + J forms in the second half, scales up
      const form = Math.min(1, Math.max(0, (t - 4.5) / 3.5));
      if (form > 0) {
        const s = Math.min(w, h) * 0.5 * (0.6 + form * 0.4);
        drawHumanoidJ(ctx, cx, cy, s, form * (0.75 + 0.25 * Math.sin(t * 3)));
      }

      // converge: pull rings/J into a single flash near the end
      if (t > 9.6) {
        const k = Math.min(1, (t - 9.6) / 1.2);
        ctx.save();
        ctx.globalAlpha = k;
        ctx.fillStyle = glow.core;
        ctx.fillRect(0, 0, w, h);
        ctx.restore();
      }

      if (now - start < DURATION) {
        raf = requestAnimationFrame(frame);
      } else {
        onDone();
      }
    }
    raf = requestAnimationFrame(frame);

    return function teardown() {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', size);
    };
  }

  // ---- main flow ----
  window.runJennyCinematic = function (opts) {
    opts = opts || {};
    const onDone = typeof opts.onDone === 'function' ? opts.onDone : function () {};

    if (REDUCED) { onDone(); return; }

    const ov = buildOverlay();
    const canvas = ov.querySelector('#jenny-cine-canvas');
    const vid = ov.querySelector('#jenny-cine-vid');
    const logo = ov.querySelector('#jenny-cine-logo');
    const phaseEl = ov.querySelector('#jenny-cine-phase');
    const skipBtn = ov.querySelector('#jenny-cine-skip');

    let finished = false;
    let teardown = function () {};

    function finish() {
      if (finished) return;
      finished = true;
      teardown();
      stopScore();
      ov.style.opacity = '0';
      ov.style.pointerEvents = 'none';
      setTimeout(() => { ov.remove(); onDone(); window.dispatchEvent(new CustomEvent('intro:done')); }, 1100);
    }
    skipBtn.addEventListener('click', finish);
    skipBtn.addEventListener('mouseenter', () => { skipBtn.style.background = 'rgba(109,139,255,0.14)'; skipBtn.style.color = '#fff'; skipBtn.style.borderColor = '#6d8bff'; });
    skipBtn.addEventListener('mouseleave', () => { skipBtn.style.background = 'rgba(255,255,255,0.04)'; skipBtn.style.color = 'rgba(255,255,255,0.7)'; skipBtn.style.borderColor = 'rgba(109,139,255,0.4)'; });

    // Try the hybrid MP4 first
    let usedVideo = false;
    try {
      vid.src = '/intro.mp4';
      vid.addEventListener('canplay', function onCan() {
        vid.removeEventListener('canplay', onCan);
        usedVideo = true;
        canvas.style.display = 'none';
        logo.style.display = 'none';
        playScore();
        vid.play().catch(() => {});
      });
      vid.addEventListener('ended', function () { if (usedVideo) finish(); });
      vid.addEventListener('error', function () { if (!usedVideo) startCanvas(); });
      // kick the load; if it 404s -> error -> canvas
      vid.load();
    } catch (e) { startCanvas(); }

    // safety: if video never loads (404 may be slow), start canvas after 900ms
    setTimeout(function () { if (!usedVideo && !finished) startCanvas(); }, 900);

    function startCanvas() {
      if (usedVideo || finished || teardown !== function(){}) {}
      if (usedVideo) return;
      // avoid double-start
      if (canvas.dataset.started === '1') return;
      canvas.dataset.started = '1';
      logo.style.opacity = '1';
      logo.style.transform = 'translateY(0) scale(1)';
      playScore();
      teardown = runCanvas(canvas, phaseEl, finish);
      // reveal logo earlier in the sequence
      setTimeout(function () {
        if (finished) return;
        logo.style.opacity = '1';
        logo.style.transform = 'translateY(0) scale(1)';
      }, 5200);
    }

    // If reduced-motion slips through or something hangs, force-skip after 16s
    setTimeout(function () { if (!finished) finish(); }, 16000);
  };
})();