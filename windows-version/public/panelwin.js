/**
 * JENNY Panels — window behaviour for the dock panels.
 *
 * Every panel is a small floating window: draggable by its header, closable,
 * and now maximizable. Maximize is the piece that was missing — a 420px panel
 * cannot show a process table or a seven-day forecast properly, so the useful
 * content was effectively unreachable on a small panel.
 *
 * Design notes:
 *   - Maximize is a *geometry* change (position + size), not a second layout.
 *     The panel keeps its own DOM, its poll timers and its scroll position, so
 *     maximizing mid-poll never loses data or restarts a request.
 *   - The pre-maximize geometry is stashed on the element, so restore is exact
 *     even if the panel was dragged somewhere odd first.
 *   - Dragging is suspended while maximized (the header drag would fight the
 *     full-bleed size), and Escape restores before it closes, so a maximized
 *     panel is never a trap.
 *   - Only one panel maximizes at a time. Two full-bleed panels stacked on top
 *     of each other is a worse outcome than the user asked for.
 */
(function (global) {
  'use strict';

  var MAX_KEY = 'jenny_panel_max';
  var maximized = null;      // the single currently-maximized panel element
  var stashed = new WeakMap(); // panel -> {left, top, width, maxHeight, transform}

  // A maximized panel covers the viewport but leaves the dock reachable at the
  // bottom, so the user can still hop to another app without restoring first.
  function maximizedRect() {
    return {
      left: 0,
      top: 0,
      width: window.innerWidth,
      maxHeight: Math.max(240, window.innerHeight - 96)
    };
  }

  function isMaximized(panel) {
    return panel && panel.classList.contains('max');
  }

  function stash(panel) {
    stashed.set(panel, {
      left: panel.style.left,
      top: panel.style.top,
      width: panel.style.width,
      maxHeight: panel.style.maxHeight,
      transform: panel.style.transform
    });
  }

  function restoreGeometry(panel) {
    var s = stashed.get(panel);
    if (!s) return;
    panel.style.left = s.left;
    panel.style.top = s.top;
    panel.style.width = s.width;
    panel.style.maxHeight = s.maxHeight;
    panel.style.transform = s.transform;
    stashed.delete(panel);
  }

  function maximize(name) {
    var panel = document.querySelector('.panel[data-panel="' + name + '"]');
    if (!panel) return;
    // Only one at a time: fold the previous one back first.
    if (maximized && maximized !== panel) restore(maximized);

    if (isMaximized(panel)) { restore(panel); return; }

    stash(panel);
    var r = maximizedRect();
    panel.classList.add('max');
    panel.style.left = r.left + 'px';
    panel.style.top = r.top + 'px';
    panel.style.width = r.width + 'px';
    panel.style.maxHeight = r.maxHeight + 'px';
    panel.style.transform = 'none';
    maximized = panel;

    // Announce the state through the button so it never has to be inferred
    // from an icon the user may not recognise.
    var btn = panel.querySelector('.panel-max');
    if (btn) {
      btn.setAttribute('aria-pressed', 'true');
      btn.title = 'Restore panel';
      var ic = btn.querySelector('i');
      if (ic) ic.className = 'fa-solid fa-clone';
    }
    try { localStorage.setItem(MAX_KEY, name); } catch (e) {}
    // Same click cue every panel already plays on open, so maximize feels
    // like part of the panel system rather than a separate feature.
    try { if (global.sfx && typeof global.sfx.confirm === 'function') global.sfx.confirm(); } catch (e) {}
  }

  function restore(panel) {
    if (!panel || !isMaximized(panel)) return;
    panel.classList.remove('max');
    restoreGeometry(panel);
    if (maximized === panel) maximized = null;
    var btn = panel.querySelector('.panel-max');
    if (btn) {
      btn.setAttribute('aria-pressed', 'false');
      btn.title = 'Maximize panel';
      var ic = btn.querySelector('i');
      if (ic) ic.className = 'fa-solid fa-up-right-and-down-left-from-center';
    }
    try {
      if (localStorage.getItem(MAX_KEY) === panel.dataset.panel) localStorage.removeItem(MAX_KEY);
    } catch (e) {}
  }

  function toggle(name) {
    var panel = document.querySelector('.panel[data-panel="' + name + '"]');
    if (!panel) return;
    isMaximized(panel) ? restore(panel) : maximize(name);
  }

  // Keep a maximized panel correct across a window resize, and across the
  // orientation change that comes with it. The stashed geometry is left alone
  // so a restore still lands where the user put it.
  var resizeTimer = null;
  window.addEventListener('resize', function () {
    if (!maximized) return;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      if (!maximized) return;
      var r = maximizedRect();
      maximized.style.width = r.width + 'px';
      maximized.style.maxHeight = r.maxHeight + 'px';
    }, 80);
  });

  global.PanelWin = {
    maximize: maximize,
    restore: restore,
    toggle: toggle,
    isMaximized: isMaximized,
    current: function () { return maximized; },
    // Called by closePanel so a closing panel can never leave the module
    // pointing at a detached element.
    forget: function (panel) {
      if (maximized === panel) { maximized = null; stashed.delete(panel); }
      stashed.delete(panel);
    }
  };
})(window);