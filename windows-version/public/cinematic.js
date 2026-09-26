/**
 * JENNY Cinematic Intro — real space video
 *
 * Real-video-first engine — no coded particle shows:
 *   1. Local bundled /intro.mp4 (real NASA-style space footage, ships with
 *      the app) plays FULLSCREEN immediately — zero network dependency, so
 *      the intro can never degrade into "coded" static fallback again.
 *   2. If online, a random NASA space video replaces it via a YouTube embed
 *      (muted autoplay, looped, no chrome) for variety.
 *   3. Last resort -> a calm static logo fade so the app never hard-locks.
 *
 * The JENNY wordmark + phase line sit on top of the footage; the piece
 * auto-finishes after ~13s (or instantly on click / skip). Reduced-motion
 * skips straight to done.
 */
(function () {
  const REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Official NASA space footage — verifiable, embeddable, real. Random each run.
  const SPACE_VIDEOS = [
    'oFDeNcu3mnc',   // NASA — Ultra High Definition (4K) View of Planet Earth
    '7fYKMCCPh28',   // NASA — The Earth (4K Extended Edition)
    'UOT4VwhVukA',   // NASA — Earth in 4K (ISS Expedition 67)
    'M3HKLzjvKPc',   // NASA — Live Video from the ISS (official)
  ];

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

  function playScore() {
    const ctx = ensureAudio();
    if (!ctx) return;
    if (ctx.state === 'suspended') ctx.resume();
    const t0 = ctx.currentTime;
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

    // Cinematic sub-boom near the middle of the reveal
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
    ov.style.cssText = 'position:fixed;inset:0;z-index:10000;background:#050508;display:flex;align-items:center;justify-content:center;opacity:1;transition:opacity 1.1s cubic-bezier(0.16,1,0.3,1);overflow:hidden';
    ov.innerHTML =
      '<div id="jenny-cine-media" style="position:absolute;inset:0"></div>' +
      '<div id="jenny-cine-vig" style="position:absolute;inset:0;background:radial-gradient(ellipse at center,transparent 30%,rgba(0,0,0,0.62) 100%);pointer-events:none"></div>' +
      '<div id="jenny-cine-logo" style="position:relative;z-index:5;display:flex;flex-direction:column;align-items:center;text-align:center;opacity:0;transform:translateY(24px) scale(0.96);transition:opacity 1.1s cubic-bezier(0.16,1,0.3,1),transform 1.1s cubic-bezier(0.16,1,0.3,1)">' +
        '<div style="position:relative">' +
          '<img src="/logo.png" alt="JENNY" style="width:min(38vh,300px);height:auto;display:block;filter:drop-shadow(0 0 34px rgba(34,211,238,0.45)) drop-shadow(0 0 70px rgba(168,85,247,0.4));animation:cine-float 4.2s ease-in-out infinite" onerror="this.style.display=\'none\'">' +
          '<div class="cine-scan" style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 0%,rgba(157,180,255,0.16) 44%,rgba(34,211,238,0.35) 50%,rgba(157,180,255,0.16) 56%,transparent 100%);background-size:100% 140%;background-position:0 -140%;animation:cine-scan 2.6s ease-in-out infinite;mix-blend-mode:screen;border-radius:14px;pointer-events:none"></div>' +
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

  // ---- media helpers ----
  function playYoutube(mediaEl, videoId, onState) {
    const iframe = document.createElement('iframe');
    iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture');
    iframe.setAttribute('allowfullscreen', '');
    iframe.style.cssText = 'width:100%;height:100%;border:0;position:absolute;inset:0';
    iframe.src =
      'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(videoId) +
      '?autoplay=1&mute=1&controls=0&disablekb=1&fs=0&iv_load_policy=3' +
      '&loop=1&modestbranding=1&playlist=' + encodeURIComponent(videoId) +
      '&playsinline=1&rel=0&showinfo=0&start=0';
    // A YouTube clip REPLACES the local clip - clear the local <video> so the
    // two never stack (iframe on top of video looks like a broken overlay).
    mediaEl.innerHTML = '';
    mediaEl.appendChild(iframe);
    iframe.addEventListener('load', function () {
      iframe.__loaded = true;
      onState && onState(true);
    });
    iframe.addEventListener('error', function () { onState && onState(false); });
    // If the embed never fires a load (offline, blocked, slow), report failure
    // after a beat so callers can put the local clip back.
    setTimeout(function () {
      if (!iframe.__loaded) onState && onState(false);
    }, 4000);
    return iframe;
  }

  function playLocalMp4(mediaEl, onState) {
    const vid = document.createElement('video');
    vid.playsInline = true;
    vid.muted = true;
    vid.loop = true;
    vid.src = '/intro.mp4';
    vid.style.cssText = 'width:100%;height:100%;object-fit:cover;position:absolute;inset:0';
    vid.addEventListener('canplay', function () {
      vid.play().catch(function () {});
      onState && onState(true);
    });
    vid.addEventListener('error', function () { onState && onState(false); });
    mediaEl.appendChild(vid);
  }

  // ---- main flow ----
  window.runJennyCinematic = function (opts) {
    opts = opts || {};
    const onDone = typeof opts.onDone === 'function' ? opts.onDone : function () {};

    if (REDUCED) { onDone(); return; }

    const ov = buildOverlay();
    const mediaEl = ov.querySelector('#jenny-cine-media');
    const logo = ov.querySelector('#jenny-cine-logo');
    const phaseEl = ov.querySelector('#jenny-cine-phase');
    const skipBtn = ov.querySelector('#jenny-cine-skip');

    let finished = false;
    let mediaStarted = false;

    function finish() {
      if (finished) return;
      finished = true;
      stopScore();
      ov.style.opacity = '0';
      ov.style.pointerEvents = 'none';
      setTimeout(function () { ov.remove(); onDone(); window.dispatchEvent(new CustomEvent('intro:done')); }, 1100);
    }
    skipBtn.addEventListener('click', finish);
    skipBtn.addEventListener('mouseenter', function () { skipBtn.style.background = 'rgba(109,139,255,0.14)'; skipBtn.style.color = '#fff'; skipBtn.style.borderColor = '#6d8bff'; });
    skipBtn.addEventListener('mouseleave', function () { skipBtn.style.background = 'rgba(255,255,255,0.04)'; skipBtn.style.color = 'rgba(255,255,255,0.7)'; skipBtn.style.borderColor = 'rgba(109,139,255,0.4)'; });
    ov.addEventListener('click', function (e) { if (e.target !== skipBtn) finish(); });
    window.addEventListener('keydown', function onKey(e) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') { window.removeEventListener('keydown', onKey); finish(); }
    });

    function markStarted() {
      if (mediaStarted) return;
      mediaStarted = true;
      logo.style.opacity = '1';
      logo.style.transform = 'translateY(0) scale(1)';
      playScore();
      if (phaseEl) phaseEl.textContent = 'ORBIT ACQUIRED';
    }

    // Primary: the bundled local space video — guaranteed real footage that
    // always plays instantly with zero network, so the intro can never look
    // like a broken "coded" fallback. If we're online, swap in a NASA YouTube
    // clip for variety once the local clip is already running.
    var localStarted = false;
    playLocalMp4(mediaEl, function (ok) {
      localStarted = true;
      if (ok) markStarted();
    });
    const nav = navigator.onLine !== false;
    if (nav) {
      setTimeout(function () {
        if (!localStarted || finished) return;
        const picked = SPACE_VIDEOS[Math.floor(Math.random() * SPACE_VIDEOS.length)];
        playYoutube(mediaEl, picked, function (ok) {
          // If the embed failed to load, put the guaranteed local clip back.
          if (!ok && !finished) {
            mediaEl.innerHTML = '';
            playLocalMp4(mediaEl, function (lok) { if (lok) markStarted(); });
          }
        });
      }, 2500);
    } else {
      // Offline: local clip already playing — nothing more to do.
    }

    // Safety net: if the local video somehow fails to load at all (file
    // missing / format unsupported), still mark the intro live so the UI is
    // never left on an un-started overlay.
    setTimeout(function () {
      if (!mediaStarted) {
        mediaEl.style.background =
          'radial-gradient(ellipse at 50% 40%, #0a0f2e 0%, #050508 55%, #000 100%)';
        markStarted();
      }
    }, 5000);

    // Auto-finish: the video itself is ambient; land the plane on the beat.
    setTimeout(function () { if (!finished) finish(); }, 13000);
    // Hard safety: never let the intro hang on a broken network.
    setTimeout(function () { if (!finished) finish(); }, 16000);
  };
})();