/**
 * JENNY Viz — one small kit for every visual readout in the app.
 *
 * The panels used to be plain label/value rows, which meant a glance told you
 * nothing: you had to read each number and mentally compare it to the last one.
 * Everything here exists to make a value legible at a glance AND show how it
 * sits in a range or against a total.
 *
 * Design rules kept deliberately small:
 *   - SVG for anything that needs to be crisp at any size (rings, arcs, bars).
 *   - Canvas only for time series, where there can be hundreds of points.
 *   - Every colour comes from the active persona via --accent-rgb, so the same
 *     widget reads as JARVIS cyan or FRIDAY violet without a second code path.
 *   - Every renderer is a pure string builder (no DOM measuring), so panels can
 *     keep their current innerHTML = render(...) style.
 *   - Every animated canvas registers itself for cleanup on Viz.reset(), so
 *     closing a panel cannot leave a requestAnimationFrame loop running.
 */
(function (global) {
  'use strict';

  // ---- accent plumbing -------------------------------------------------
  // Read the persona colour once per call rather than baking a literal, so a
  // mode switch repaints every widget that is already on screen.
  function accent() {
    var v = getComputedStyle(document.body).getPropertyValue('--accent-rgb').trim();
    return v || '109, 139, 255';
  }
  function rgba(a, alpha) { return 'rgba(' + accent() + ',' + alpha + ')'; }

  // Severity ramp shared by rings/bars. Thresholds are on the value's own scale,
  // so a 70% disk and a 70% CPU both read amber rather than looking identical
  // only by accident.
  function severity(pct, warn, crit) {
    // `false` means "never recolour this". It has to be a distinct sentinel
    // rather than null, because callers that simply omit the option also pass
    // undefined/null and those SHOULD get the defaults.
    if (warn === false || crit === false) return null;
    warn = warn == null ? 60 : warn;
    crit = crit == null ? 85 : crit;
    if (pct >= crit) return '#ff5f56';
    if (pct >= warn) return '#fbbf24';
    return null; // caller falls back to the persona accent
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function clamp(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }
  function num(n, fallback) {
    var v = typeof n === 'number' ? n : parseFloat(n);
    return isFinite(v) ? v : (fallback || 0);
  }

  // Single place that turns a raw reading into 0-100. Every gauge goes through
  // it so a min/max window behaves identically on a ring, an arc and a bar.
  //
  //   opts.min/max absent -> the value is already a percentage.
  //   opts.max only        -> value / max * 100.
  //   opts.min and max     -> value is positioned inside a window, which is the
  //                            case that used to be silently wrong: a 30 of a
  //                            -20..50 window is 62.9%, not the 60% you get from
  //                            dividing by max and clamping.
  function scale(value, opts) {
    opts = opts || {};
    var v = num(value, 0);
    if (opts.min == null && opts.max == null) return clamp(v, 0, 100);
    var lo = num(opts.min, 0);
    var hi = num(opts.max, 100);
    if (hi <= lo) hi = lo + 1;
    return clamp(((v - lo) / (hi - lo)) * 100, 0, 100);
  }

  // ======================================================================
  // RING — a donut gauge with tick marks around the rim.
  // The ticks are what make it read as an instrument: a bare circle with a
  // percentage is easy to misread at a glance, a ticked dial is not.
  // ======================================================================
  function ring(value, opts) {
    opts = opts || {};
    var pct = scale(value, opts);
    var size = opts.size || 96;
    var stroke = opts.stroke || 8;
    var r = (size - stroke) / 2 - (opts.tickPad || 9);
    var c = size / 2;
    var circ = 2 * Math.PI * r;
    var dash = (pct / 100) * circ;
    var color = opts.color || severity(pct, opts.warn, opts.crit) || 'var(--accent, #6d8bff)';
    var gid = 'rg' + Math.random().toString(36).slice(2, 8);
    var ticks = '';
    var tn = opts.ticks == null ? 48 : opts.ticks;
    for (var i = 0; i < tn; i++) {
      // Every 6th tick is longer, which gives the dial a readable scale.
      var major = i % 6 === 0;
      var ang = (i / tn) * Math.PI * 2 - Math.PI / 2;
      var inner = r + stroke / 2 + 2;
      var outer = inner + (major ? 4.5 : 2.5);
      var x1 = c + Math.cos(ang) * inner, y1 = c + Math.sin(ang) * inner;
      var x2 = c + Math.cos(ang) * outer, y2 = c + Math.sin(ang) * outer;
      // Ticks past the current value are dimmed, so the dial also shows "how
      // much headroom is left" without needing a second number.
      var on = (i / tn) * 100 <= pct;
      ticks += '<line x1="' + x1.toFixed(2) + '" y1="' + y1.toFixed(2) + '" x2="' + x2.toFixed(2) + '" y2="' + y2.toFixed(2) +
        '" stroke="' + (on ? color : 'rgba(255,255,255,0.16)') + '" stroke-width="' + (major ? 1.6 : 0.9) +
        '" stroke-linecap="round" opacity="' + (on ? (major ? 0.95 : 0.5) : 0.5) + '"/>';
    }
    var label = opts.labelText != null ? opts.labelText : Math.round(pct) + '%';
    return '' +
      '<div class="viz-ring" style="--viz-size:' + size + 'px">' +
        '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '" aria-hidden="true">' +
          '<defs>' +
            '<linearGradient id="' + gid + '" x1="0" y1="0" x2="1" y2="1">' +
              '<stop offset="0%" stop-color="' + color + '" stop-opacity="1"/>' +
              '<stop offset="100%" stop-color="' + color + '" stop-opacity="0.55"/>' +
            '</linearGradient>' +
            '<filter id="' + gid + 'b" x="-60%" y="-60%" width="220%" height="220%">' +
              '<feGaussianBlur stdDeviation="2.4" result="b"/>' +
            '</filter>' +
          '</defs>' +
          // soft glow pass under the arc
          '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="' + color +
            '" stroke-width="' + (stroke + 2) + '" stroke-linecap="round" opacity="0.30" filter="url(#' + gid + 'b)"' +
            ' stroke-dasharray="' + circ.toFixed(2) + '" stroke-dashoffset="' + (circ - dash).toFixed(2) +
            '" transform="rotate(-90 ' + c + ' ' + c + ')"/>' +
          '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="' + stroke + '"/>' +
          '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="url(#' + gid + ')" stroke-width="' + stroke +
            '" stroke-linecap="round" stroke-dasharray="' + circ.toFixed(2) + '" stroke-dashoffset="' + (circ - dash).toFixed(2) +
            '" transform="rotate(-90 ' + c + ' ' + c + ')"/>' +
          ticks +
        '</svg>' +
        '<div class="viz-ring-core">' +
          '<div class="viz-ring-val">' + esc(label) + '</div>' +
          (opts.sub ? '<div class="viz-ring-sub">' + esc(opts.sub) + '</div>' : '') +
        '</div>' +
        (opts.label ? '<div class="viz-ring-lbl">' + esc(opts.label) + '</div>' : '') +
      '</div>';
  }

  // ======================================================================
  // ARC — a 240-degree sweep gauge. Used where a full ring would be too much
  // visual weight for a single value (weather temperature, one headline stat).
  // ======================================================================
  function arc(value, opts) {
    opts = opts || {};
    var pct = scale(value, opts);
    var size = opts.size || 150;
    var stroke = opts.stroke || 11;
    var r = (size - stroke) / 2 - 4;
    var c = size / 2;
    var SWEEP = 240;          // degrees of the dial we actually use
    var START = -210;         // so the gap sits at the bottom
    var circ = 2 * Math.PI * r;
    var span = (SWEEP / 360) * circ;
    var dash = (pct / 100) * span;
    var color = opts.color || severity(pct, opts.warn, opts.crit) || 'var(--accent, #6d8bff)';
    var gid = 'ac' + Math.random().toString(36).slice(2, 8);
    return '' +
      '<div class="viz-arc" style="--viz-size:' + size + 'px">' +
        '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '" aria-hidden="true">' +
          '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="1" y2="0">' +
            '<stop offset="0%" stop-color="' + color + '" stop-opacity="0.45"/>' +
            '<stop offset="100%" stop-color="' + color + '" stop-opacity="1"/>' +
          '</linearGradient></defs>' +
          '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,0.09)" stroke-width="' + stroke + '"' +
            ' stroke-dasharray="' + span.toFixed(2) + ' ' + (circ - span).toFixed(2) +
            '" stroke-linecap="round" transform="rotate(' + START + ' ' + c + ' ' + c + ')"/>' +
          '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="url(#' + gid + ')" stroke-width="' + stroke +
            '" stroke-dasharray="' + dash.toFixed(2) + ' ' + (circ - dash).toFixed(2) +
            '" stroke-linecap="round" transform="rotate(' + START + ' ' + c + ' ' + c + ')"/>' +
        '</svg>' +
        '<div class="viz-arc-core">' +
          '<div class="viz-arc-val">' + esc(opts.labelText != null ? opts.labelText : Math.round(pct) + '%') + '</div>' +
          (opts.sub ? '<div class="viz-arc-sub">' + esc(opts.sub) + '</div>' : '') +
        '</div>' +
      '</div>';
  }

  // ======================================================================
  // BAR — a labelled horizontal meter. `marker` draws a threshold line, which
  // is how the process list shows "this one is above the others" without
  // sorting the numbers into prose.
  // ======================================================================
  function bar(value, opts) {
    opts = opts || {};
    var pct = scale(value, opts);
    var color = opts.color || severity(pct, opts.warn, opts.crit) || 'var(--accent, #6d8bff)';
    var marker = opts.marker != null && isFinite(opts.marker)
      ? '<i class="viz-bar-marker" style="left:' + clamp(opts.marker, 0, 100) + '%"></i>' : '';
    return '' +
      '<div class="viz-bar-row">' +
        (opts.label ? '<span class="viz-bar-lbl">' + esc(opts.label) + '</span>' : '') +
        '<span class="viz-bar-track">' +
          '<i class="viz-bar-fill" style="width:' + pct.toFixed(2) + '%;background:linear-gradient(90deg,' +
            color + '55,' + color + ');box-shadow:0 0 10px ' + color + '99"></i>' + marker +
        '</span>' +
        '<span class="viz-bar-val">' + esc(opts.valueText != null ? opts.valueText : Math.round(pct) + '%') + '</span>' +
      '</div>';
  }

  // ======================================================================
  // STACK — one horizontal 100% bar split into proportional segments. The
  // fastest way to show "what is this whole made of" (disk by drive, CPU by
  // process, vault by type) without a legend that has to be read separately.
  // ======================================================================
  function stack(segments, opts) {
    opts = opts || {};
    var items = (segments || []).filter(function (s) { return num(s.value, 0) > 0; });
    var total = items.reduce(function (a, s) { return a + num(s.value, 0); }, 0);
    if (!total) return '<div class="viz-stack-empty">' + esc(opts.empty || 'No data yet.') + '</div>';
    var segs = '', legend = '';
    items.forEach(function (s, i) {
      var pct = (num(s.value, 0) / total) * 100;
      var color = s.color || 'hsl(' + Math.round((i / items.length) * 300) + ',72%,62%)';
      segs += '<i class="viz-stack-seg" style="width:' + pct.toFixed(2) + '%;background:' + color +
        ';box-shadow:0 0 12px ' + color + '66" title="' + esc(s.label) + ': ' + esc(s.value) + '"></i>';
      legend += '<span class="viz-legend-item"><i style="background:' + color + '"></i>' +
        esc(s.label) + ' <b>' + (opts.legendValues === false ? '' : Math.round(pct) + '%') + '</b></span>';
    });
    return '<div class="viz-stack">' + segs + '</div>' + (opts.legend === false ? '' : '<div class="viz-legend">' + legend + '</div>');
  }

  // ======================================================================
  // SPARK — canvas time series. Gradient fill under the line so a trend reads
  // as an area, not a hairline. Handles an empty/short series by drawing a
  // flat baseline instead of throwing.
  // ======================================================================
  function spark(canvasId, data, opts) {
    opts = opts || {};
    var cv = typeof canvasId === 'string' ? document.getElementById(canvasId) : canvasId;
    if (!cv) return null;
    var ctx = cv.getContext('2d');
    if (!ctx) return null;
    var values = (data || []).map(function (v) { return num(v, 0); });
    var color = opts.color || 'var(--accent, #6d8bff)';
    var accentStr = /^var\(--accent/.test(color) ? accent() : null;
    var stroke = accentStr ? 'rgba(' + accentStr + ',1)' : color;
    // Window the series is drawn against. With no explicit max the series is
    // stretched to fill the canvas; with one, the shape stays comparable
    // between refreshes instead of every redraw looking equally dramatic.
    var lo = opts.min != null ? num(opts.min, 0) : null;
    var hi = opts.max != null ? num(opts.max, null) : null;
    if (hi == null) hi = Math.max.apply(null, values.concat([1]));
    if (lo == null) lo = Math.min(0, Math.min.apply(null, values.concat([0])));
    if (hi <= lo) hi = lo + 1;
    var W = cv.width, H = cv.height;

    function draw() {
      ctx.clearRect(0, 0, W, H);
      var n = values.length;
      if (n < 2) {
        ctx.strokeStyle = 'rgba(255,255,255,0.18)';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke();
        return;
      }
      var pad = 3;
      var usable = H - pad * 2;
      var step = W / (n - 1);
      var pt = function (i) {
        return [i * step, pad + usable - clamp((values[i] - lo) / (hi - lo), 0, 1) * usable];
      };
      // area fill
      // The stroke may arrive as a hex colour or as an accent-derived rgba, so
      // build the fill stops from whichever form we ended up with.
      var grad = ctx.createLinearGradient(0, 0, 0, H);
      if (stroke.indexOf('rgba') === 0) {
        grad.addColorStop(0, stroke.replace(/,[^,]+\)$/, ',0.34)'));
        grad.addColorStop(1, stroke.replace(/,[^,]+\)$/, ',0)'));
      } else {
        grad.addColorStop(0, stroke);
        grad.addColorStop(1, 'transparent');
      }
      ctx.beginPath();
      ctx.moveTo(0, H);
      for (var i = 0; i < n; i++) { var p = pt(i); ctx.lineTo(p[0], p[1]); }
      ctx.lineTo(W, H);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
      // line
      ctx.beginPath();
      for (var j = 0; j < n; j++) { var q = pt(j); if (j === 0) ctx.moveTo(q[0], q[1]); else ctx.lineTo(q[0], q[1]); }
      ctx.strokeStyle = stroke;
      ctx.lineWidth = opts.lineWidth || 1.6;
      ctx.lineJoin = 'round';
      ctx.shadowColor = stroke;
      ctx.shadowBlur = 6;
      ctx.stroke();
      ctx.shadowBlur = 0;
      // head dot — marks "now" so the newest sample is findable
      var last = pt(n - 1);
      ctx.beginPath();
      ctx.arc(last[0] - 1.5, last[1], 2.4, 0, Math.PI * 2);
      ctx.fillStyle = stroke;
      ctx.fill();
    }
    draw();
    return { draw: draw, values: values, push: function (v) {
      values.push(num(v, 0));
      // Bounded history: a long-running dashboard would otherwise grow this
      // array forever and the redraw cost with it.
      while (values.length > (opts.limit || 60)) values.shift();
      draw();
    } };
  }

  // ======================================================================
  // EQUALISER — animated bars. Only used where the value is genuinely a live
  // signal (voice activity, network throughput) so it is not just decoration.
  // ======================================================================
  function equaliser(hostId, opts) {
    opts = opts || {};
    var host = typeof hostId === 'string' ? document.getElementById(hostId) : hostId;
    if (!host) return null;
    var bars = opts.bars || 5;
    host.innerHTML = '';
    for (var i = 0; i < bars; i++) host.appendChild(document.createElement('i'));
    var nodes = host.querySelectorAll('i');
    var t = 0;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var state = { level: 0 };
    function frame() {
      if (!state.alive) return;
      t += 0.06;
      var amp = state.level;
      for (var i = 0; i < nodes.length; i++) {
        // Two out-of-phase sines per bar, scaled by the live level, so the
        // motion looks organic instead of like a bouncing square wave.
        var v = (Math.sin(t + i * 0.7) * 0.5 + Math.sin(t * 1.7 + i * 1.3) * 0.5) * 0.5 + 0.5;
        var h = clamp((0.18 + v * 0.82) * amp + 0.12, 0.1, 1);
        nodes[i].style.height = (h * 100).toFixed(1) + '%';
      }
      state.raf = requestAnimationFrame(frame);
    }
    state.alive = true;
    if (reduce) {
      for (var k = 0; k < nodes.length; k++) nodes[k].style.height = '55%';
      state.alive = false;
    } else {
      state.raf = requestAnimationFrame(frame);
    }
    return {
      // Callers push their real signal here; 0 parks the bars flat.
      setLevel: function (l) { state.level = clamp(num(l, 0), 0, 1); },
      stop: function () {
        state.alive = false;
        if (state.raf) cancelAnimationFrame(state.raf);
      }
    };
  }

  // ======================================================================
  // RANGE — a min..max band with the current value marked on it. The right
  // shape for weather forecasts, where "28° of a 19°-31° day" is the fact a
  // person actually wants and a bare "28°" throws away.
  // ======================================================================
  function range(value, min, max, opts) {
    opts = opts || {};
    var lo = num(min, 0), hi = num(max, 1);
    if (hi <= lo) hi = lo + 1;
    var pct = clamp(((num(value, lo) - lo) / (hi - lo)) * 100, 0, 100);
    var color = opts.color || 'var(--accent, #6d8bff)';
    return '' +
      '<div class="viz-range">' +
        '<span class="viz-range-lo">' + esc(opts.minText != null ? opts.minText : Math.round(lo)) + '</span>' +
        '<span class="viz-range-track">' +
          '<i class="viz-range-band" style="left:0;width:100%;background:linear-gradient(90deg,' +
            color + '22,' + color + '66)"></i>' +
          '<i class="viz-range-knob" style="left:' + pct.toFixed(2) + '%;background:' + color +
            ';box-shadow:0 0 12px ' + color + '"></i>' +
        '</span>' +
        '<span class="viz-range-hi">' + esc(opts.maxText != null ? opts.maxText : Math.round(hi)) + '</span>' +
      '</div>';
  }

  // ======================================================================
  // WAVEFORM — a static audio-style waveform, decorative only. Used as a
  // texture behind a voice panel where there is no signal to plot yet.
  // ======================================================================
  function waveform(count, seed) {
    var n = count || 28;
    var s = seed || 7;
    var out = '';
    for (var i = 0; i < n; i++) {
      // Deterministic pseudo-noise: the same panel always looks the same, so
      // it does not shimmer every re-render.
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      var h = 18 + (s % 72);
      out += '<i style="height:' + h + '%;animation-delay:' + (i * 0.045).toFixed(2) + 's"></i>';
    }
    return '<div class="viz-wave">' + out + '</div>';
  }

  // ---- panel scaffold --------------------------------------------------
  // One place that decides how a panel's visual header is laid out, so all
  // thirteen panels open with the same rhythm instead of each inventing one.
  function hero(rings, opts) {
    opts = opts || {};
    // subHtml exists because a few call sites put markup in the sub line (a
    // status pill, an icon). sub stays escaped by default so the common case
    // cannot inject; callers that genuinely own their markup opt in explicitly.
    var sub = opts.subHtml ? (opts.sub || '') : (opts.sub ? esc(opts.sub) : '');
    return '' +
      '<div class="viz-hero glass-soft">' +
        '<div class="viz-hero-rings">' + (rings || []).join('') + '</div>' +
        (opts.title ? '<div class="viz-hero-title">' + esc(opts.title) + '</div>' : '') +
        (sub ? '<div class="viz-hero-sub">' + sub + '</div>' : '') +
      '</div>';
  }

  function section(title, body, icon) {
    return '' +
      '<div class="viz-section">' +
        '<div class="viz-section-h"><i class="fa-solid ' + (icon || 'fa-chart-simple') + '"></i> ' + esc(title) + '</div>' +
        '<div class="viz-section-b">' + body + '</div>' +
      '</div>';
  }

  global.Viz = {
    ring: ring,
    arc: arc,
    bar: bar,
    stack: stack,
    spark: spark,
    equaliser: equaliser,
    range: range,
    waveform: waveform,
    hero: hero,
    section: section,
    severity: severity,
    scale: scale,
    accent: accent,
    rgba: rgba,
    esc: esc,
    clamp: clamp,
    num: num
  };
})(window);