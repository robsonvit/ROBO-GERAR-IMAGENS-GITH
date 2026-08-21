chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
    /* ignore if API unavailable */
  });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
    /* ignore */
  });
});

/* ── MAIN world React fiber submit ───────────────────────────────────
 * chrome.scripting.executeScript with world:"MAIN" bypasses the page's
 * CSP and runs in the same JS context as React / Slate.
 *
 * The content script marks the target button with a data attribute,
 * then asks us to find and invoke the real submission handler from
 * the React fiber tree.
 * ---------------------------------------------------------------- */

/**
 * Injected into the page's MAIN world via chrome.scripting.executeScript.
 * Must be fully self-contained — no closures over service-worker scope.
 */
function reactFiberSubmit(token, markerAttr, mode) {
  var el = document.querySelector("[" + markerAttr + '="' + token + '"]');
  if (!el) return { ok: false, reason: "element not found in MAIN world" };

  // Find React fiber key
  var fiberKey = Object.keys(el).find(function (k) {
    return (
      k.startsWith("__reactFiber$") ||
      k.startsWith("__reactInternalInstance$")
    );
  });
  if (!fiberKey) return { ok: false, reason: "no React fiber on element" };

  // Walk the fiber tree and collect the nearest handler of each kind
  var handlers = {}; // name -> { fn, depth }
  var HANDLER_NAMES = ["onClick", "onPointerDown", "onMouseDown", "onPointerUp", "onMouseUp"];

  var fiber = el[fiberKey];
  var depth = 0;
  while (fiber && depth < 30) {
    var props = fiber.memoizedProps;
    if (props) {
      for (var h = 0; h < HANDLER_NAMES.length; h++) {
        var name = HANDLER_NAMES[h];
        if (!handlers[name] && typeof props[name] === "function") {
          handlers[name] = { fn: props[name], depth: depth };
        }
      }
    }
    fiber = fiber.return;
    depth++;
  }

  // Also check __reactProps$ for direct handlers
  var propsKey = Object.keys(el).find(function (k) {
    return k.startsWith("__reactProps$");
  });
  if (propsKey) {
    var directProps = el[propsKey];
    for (var d = 0; d < HANDLER_NAMES.length; d++) {
      var dn = HANDLER_NAMES[d];
      if (!handlers[dn] && typeof directProps[dn] === "function") {
        handlers[dn] = { fn: directProps[dn], depth: -1 };
      }
    }
  }

  // Skip onSubmit() — calling it with a non-Event arg makes Flow run
  // empty-prompt validation. onClick on the Create button submits correctly.

  var rect = el.getBoundingClientRect();
  function fakeEvent(type) {
    return {
      type: type,
      target: el,
      currentTarget: el,
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      button: 0,
      buttons: type === "pointerdown" || type === "mousedown" ? 1 : 0,
      pointerId: 1,
      pointerType: "mouse",
      isTrusted: true,
      detail: 1,
      preventDefault: function () {},
      stopPropagation: function () {},
      isPropagationStopped: function () { return false; },
      isDefaultPrevented: function () { return false; },
      nativeEvent: { type: type, isTrusted: true },
    };
  }

  // mode "press": popover/dropdown triggers open on pointer-down, not click —
  // fire the whole press sequence, each handler that exists.
  if (mode === "press") {
    var seq = [
      ["onPointerDown", "pointerdown"],
      ["onMouseDown",   "mousedown"],
      ["onPointerUp",   "pointerup"],
      ["onMouseUp",     "mouseup"],
      ["onClick",       "click"],
    ];
    var invoked = [];
    for (var s = 0; s < seq.length; s++) {
      var entry = handlers[seq[s][0]];
      if (entry) {
        try { entry.fn(fakeEvent(seq[s][1])); invoked.push(seq[s][0]); } catch (e) { /* keep going */ }
      }
    }
    if (invoked.length) return { ok: true, method: invoked.join("+"), depth: 0 };
    return { ok: false, reason: "no press handlers found in fiber tree" };
  }

  // default mode: onClick only (proven path for the Create button)
  var click = handlers.onClick;
  if (click) {
    try {
      click.fn(fakeEvent("click"));
      return { ok: true, method: "onClick", depth: click.depth };
    } catch (e) {
      return { ok: false, reason: "onClick threw: " + e.message };
    }
  }

  return { ok: false, reason: "onClick not found in fiber tree" };
}

// Simple main-world click for toggle buttons (no fiber needed)
function mainWorldAgentClick() {
  var btn = Array.from(document.querySelectorAll("button[aria-pressed]"))
    .find(function(b) { return /agent/i.test(b.textContent); });
  if (!btn) return { ok: false, reason: "Agent button not found" };
  if (btn.getAttribute("aria-pressed") !== "true") return { ok: true, skipped: true };
  btn.click();
  return { ok: true };
}

/**
 * Injects REAL mouse events (isTrusted:true) using chrome.debugger API.
 * This is the only reliable way to open context menus in Google Flow,
 * which guards its interactive elements with event.isTrusted checks.
 *
 * Flow:
 *   1. Move mouse over image → overlay (♥/🔄/⋮) appears
 *   2. Move mouse to ⋮ → click it → context menu opens
 *   3. Move mouse to "Baixar" → submenu (1K/2K/4K) appears
 *   4. Move mouse to "2K" → click it → download starts
 */
async function debugger2KDownload(tabId, imgSrc) {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const target = { tabId };

  // Helper: run a function in the ISOLATED world and return its result
  async function exec(fn, args) {
    const res = await chrome.scripting.executeScript({ target, func: fn, args: args || [] });
    return res?.[0]?.result;
  }

  // Helper: inject real mouse move
  async function move(x, y) {
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mouseMoved", x: Math.round(x), y: Math.round(y), button: "none", buttons: 0,
      pointerType: "mouse", modifiers: 0,
    });
  }

  // Helper: inject real left click (press + release)
  async function click(x, y) {
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mousePressed", x: Math.round(x), y: Math.round(y),
      button: "left", buttons: 1, clickCount: 1, pointerType: "mouse",
    });
    await sleep(80);
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mouseReleased", x: Math.round(x), y: Math.round(y),
      button: "left", buttons: 0, clickCount: 1, pointerType: "mouse",
    });
  }

  // Helper: find element rect by CSS selector + text condition, returns {cx,cy,text} or null
  async function findElemRect(selector, textTest) {
    return exec(function(sel, test) {
      // Reversing the array ensures we check the deepest children first
      var els = Array.from(document.querySelectorAll(sel)).reverse();
      var found = els.find(function(el) {
        var s = window.getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden') return false;
        if (parseFloat(s.opacity || '1') < 0.05) return false;
        var r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        var t = (el.textContent || '').trim().toLowerCase();
        return new RegExp(test).test(t);
      });
      if (!found) return null;
      var r = found.getBoundingClientRect();
      return { cx: r.left + r.width/2, cy: r.top + r.height/2, text: (found.textContent||'').trim().slice(0,30) };
    }, [selector, textTest]);
  }

  // Helper: find ⋮ button near image (spatial — EXACTLY at top-right corner of the image)
  async function findDotsBtn(imgLeft, imgTop, imgRight, imgBottom) {
    return exec(function(l, t, r, b) {
      var btns = Array.from(document.querySelectorAll('button'));
      var near = btns.filter(function(btn) {
        var s = window.getComputedStyle(btn);
        if (s.display === 'none' || s.visibility === 'hidden') return false;
        if (parseFloat(s.opacity||'1') < 0.05) return false;
        
        var rc = btn.getBoundingClientRect();
        if (rc.width === 0 || rc.height === 0) return false;
        var cx = rc.left + rc.width/2; 
        var cy = rc.top + rc.height/2;
        
        // CAIXA ESTRITA: Apenas botões no canto superior direito da imagem
        // cx deve estar perto da borda direita (r)
        // cy deve estar perto da borda superior (t)
        return cx >= r - 150 && cx <= r + 15 && cy >= t - 15 && cy <= t + 60;
      });
      if (!near.length) return null;
      
      // Ordena do mais à direita para o mais à esquerda
      near.sort(function(a, b2) { return b2.getBoundingClientRect().left - a.getBoundingClientRect().left; });
      var btn = near[0];
      var rc = btn.getBoundingClientRect();
      return { cx: rc.left+rc.width/2, cy: rc.top+rc.height/2, count: near.length, text: (btn.textContent||'').trim().slice(0,20) };
    }, [imgLeft, imgTop, imgRight, imgBottom]);
  }

  try {
    await chrome.debugger.attach(target, "1.3");
    await sleep(200);

    // ── Step 1: Get image position ──
    const imgRect = await exec(function(src) {
      var img = Array.from(document.querySelectorAll('img')).find(function(i) { return i.src === src; });
      if (!img) return null;
      var r = img.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, cx: r.left+r.width/2, cy: r.top+r.height/2 };
    }, [imgSrc]);

    if (!imgRect) return { ok: false, reason: 'img not found' };

    // ── Step 2: Move mouse over image to reveal overlay ──
    await move(imgRect.cx, imgRect.cy);
    await sleep(800);

    // ── Step 3: Find ⋮ button (poll up to 5s) ──
    let dotsInfo = null;
    for (let i = 0; i < 10; i++) {
      dotsInfo = await findDotsBtn(imgRect.left, imgRect.top, imgRect.right, imgRect.bottom);
      if (dotsInfo) break;
      // nudge mouse to re-trigger hover
      await move(imgRect.cx + (i % 2 === 0 ? 2 : -2), imgRect.cy);
      await sleep(400);
    }

    if (!dotsInfo) return { ok: false, reason: 'overlay buttons not found after hover' };

    // ── Step 4: Move to ⋮ and click ──
    await move(dotsInfo.cx, dotsInfo.cy);
    await sleep(350);
    await click(dotsInfo.cx, dotsInfo.cy);
    await sleep(600);

    // ── Step 5: Find "Baixar" in context menu (poll up to 3s) ──
    let baixarInfo = null;
    let menuSelector = 'li, [role="menuitem"], [role="option"], .mat-mdc-menu-item';
    for (let i = 0; i < 15; i++) {
      await sleep(200);
      baixarInfo = await findElemRect(menuSelector, 'baixar|download');
      if (baixarInfo) break;
    }

    if (!baixarInfo) {
      // Diagnostic: what's in DOM?
      const cands = await exec(function(sel) {
        return Array.from(document.querySelectorAll(sel))
          .filter(function(el) { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
          .slice(0,10).map(function(el) { return (el.textContent||'').trim().slice(0,30); });
      }, [menuSelector]);
      return { ok: false, reason: 'Baixar not found', dotsText: dotsInfo.text, domCandidates: cands };
    }

    // ── Step 6: Move to "Baixar" → submenu appears ──
    await move(baixarInfo.cx, baixarInfo.cy);
    await sleep(700);

    // ── Step 7: Find "2K" button in submenu (poll up to 5s) ──
    let btn2kInfo = null;
    for (let j = 0; j < 20; j++) {
      await sleep(250);
      btn2kInfo = await findElemRect(menuSelector, '2k');
      if (btn2kInfo) break;
      // re-nudge over Baixar to keep submenu open
      if (j % 8 === 7) {
        await move(baixarInfo.cx + 1, baixarInfo.cy);
        await sleep(100);
        await move(baixarInfo.cx, baixarInfo.cy);
      }
    }

    if (!btn2kInfo) return { ok: false, reason: '2K btn not found', baixarText: baixarInfo.text };

    // ── Step 8: Move to "2K" and click ──
    await move(btn2kInfo.cx, btn2kInfo.cy);
    await sleep(300);
    await click(btn2kInfo.cx, btn2kInfo.cy);
    await sleep(1500);

    return { ok: true, dotsText: dotsInfo.text, baixarText: baixarInfo.text, btn2kText: btn2kInfo.text };

  } catch(e) {
    return { ok: false, reason: 'debugger error: ' + (e?.message || String(e)) };
  } finally {
    try { await chrome.debugger.detach(target); } catch(_) {}
  }
}





/**
 * Fires onMouseEnter/onPointerEnter handlers with isTrusted:true on every
 * ancestor of the marked element. This reveals CSS+React hover overlays
 * (e.g. the ♥/🔄/⋮ action buttons on Google Flow image tiles) which only
 * appear in response to real (trusted) pointer entry events.
 */
function reactFiberHover(token, markerAttr) {
  var el = document.querySelector("[" + markerAttr + '="' + token + '"]');
  if (!el) return { ok: false, reason: "element not found" };

  var HOVER_HANDLERS = ["onMouseEnter", "onPointerEnter", "onMouseOver", "onPointerOver", "onMouseMove"];
  var fired = 0;

  function fakeHoverEvent(type, target, rect) {
    return {
      type: type,
      target: target,
      currentTarget: target,
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      pointerId: 1,
      pointerType: "mouse",
      button: -1,
      buttons: 0,
      isTrusted: true,
      bubbles: true,
      cancelable: false,
      relatedTarget: null,
      preventDefault: function() {},
      stopPropagation: function() {},
      isPropagationStopped: function() { return false; },
      isDefaultPrevented: function() { return false; },
      nativeEvent: { type: type, isTrusted: true },
    };
  }

  // Walk UP from element through all ancestors, firing hover handlers
  var node = el;
  while (node && node !== document.body) {
    var rect = (node.getBoundingClientRect ? node.getBoundingClientRect() : { left: 0, top: 0, width: 1, height: 1 });

    // Check __reactProps$ (direct props)
    var propsKey = Object.keys(node).find(function(k) { return k.startsWith("__reactProps$"); });
    if (propsKey) {
      var props = node[propsKey];
      for (var i = 0; i < HOVER_HANDLERS.length; i++) {
        var hName = HOVER_HANDLERS[i];
        if (typeof props[hName] === "function") {
          try { props[hName](fakeHoverEvent(hName.replace(/^on/, "").toLowerCase(), node, rect)); fired++; } catch(e) {}
        }
      }
    }

    // Also walk fiber chain from this node
    var fiberKey = Object.keys(node).find(function(k) {
      return k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$");
    });
    if (fiberKey) {
      var fiber = node[fiberKey];
      var depth = 0;
      while (fiber && depth < 20) {
        var fProps = fiber.memoizedProps;
        if (fProps) {
          for (var fi = 0; fi < HOVER_HANDLERS.length; fi++) {
            var fName = HOVER_HANDLERS[fi];
            if (typeof fProps[fName] === "function") {
              try { fProps[fName](fakeHoverEvent(fName.replace(/^on/, "").toLowerCase(), node, rect)); fired++; } catch(e) {}
            }
          }
        }
        fiber = fiber.return;
        depth++;
      }
    }

    node = node.parentElement;
  }

  return { ok: fired > 0, fired: fired };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "MAIN_WORLD_AGENT_CLICK") {
    const tabId = sender.tab?.id;
    if (!tabId) { sendResponse({ ok: false, reason: "no tab id" }); return; }
    chrome.scripting
      .executeScript({ target: { tabId }, world: "MAIN", func: mainWorldAgentClick })
      .then(results => sendResponse(results?.[0]?.result || { ok: false, reason: "no result" }))
      .catch(e => sendResponse({ ok: false, reason: String(e?.message || e) }));
    return true;
  }

  if (msg?.type === "REACT_FIBER_HOVER") {
    const tabId = sender.tab?.id;
    if (!tabId) { sendResponse({ ok: false, reason: "no tab id" }); return; }
    chrome.scripting
      .executeScript({
        target: { tabId },
        world: "MAIN",
        func: reactFiberHover,
        args: [msg.token, msg.markerAttr],
      })
      .then(results => sendResponse(results?.[0]?.result || { ok: false, reason: "no result" }))
      .catch(e => sendResponse({ ok: false, reason: String(e?.message || e) }));
    return true;
  }

  if (msg?.type === "DEBUGGER_2K_DOWNLOAD") {
    const tabId = sender.tab?.id;
    if (!tabId) { sendResponse({ ok: false, reason: "no tab id" }); return; }
    debugger2KDownload(tabId, msg.imgSrc)
      .then(result => sendResponse(result))
      .catch(e => sendResponse({ ok: false, reason: String(e?.message || e) }));
    return true;
  }

  if (msg?.type !== "REACT_FIBER_CLICK") return;

  const tabId = sender.tab?.id;
  if (!tabId) {
    sendResponse({ ok: false, reason: "no tab id" });
    return;
  }

  chrome.scripting
    .executeScript({
      target: { tabId },
      world: "MAIN",
      func: reactFiberSubmit,
      args: [msg.token, msg.markerAttr, msg.mode || "click"],
    })
    .then((results) => {
      const val = results?.[0]?.result;
      sendResponse(val || { ok: false, reason: "no result from injection" });
    })
    .catch((e) => {
      sendResponse({ ok: false, reason: String(e?.message || e) });
    });

  return true; // async sendResponse
});
