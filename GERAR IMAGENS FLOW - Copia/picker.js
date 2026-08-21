// Flow Auto-Generator — Content Script (reconstruído)
if (window.__flowLoaded) {
  // already loaded
} else {
window.__flowLoaded = true;

const CARDS_CONTAINER_XPATH = '/html/body/div[1]/div[1]/div[4]/div[1]/div/div/div[2]';
const INPUT_CONTAINER_XPATH = '/html/body/div[1]/div[1]/div[5]/div/div';
const REF_ATTR = 'data-flow-ref-card';

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function xpathNode(xpath, context) {
  return document.evaluate(
    xpath, context || document, null,
    XPathResult.FIRST_ORDERED_NODE_TYPE, null
  ).singleNodeValue;
}

function promptFieldKeywordHits(s) {
  const hay = String(s || '').toLowerCase();
  const keys = [
    'prompt', 'describe', 'descreva', 'instru', 'pergunta', 'gerar', 'generate',
    'creat', 'crear', 'mensagem', 'message', 'digite', 'type', 'enter', 'what',
    'o que', 'tell', 'cont', 'escr', 'write', 'imagine', 'imagina',
  ];
  return keys.some((k) => hay.includes(k));
}

function isReasonablePromptFieldRect(r) {
  if (!r || r.width < 96 || r.height < 20 || r.height > 900) return false;
  if (r.bottom < 36 || r.top > window.innerHeight + 80) return false;
  return true;
}

/** Campo de texto principal (XPath fixo do Flow quebra quando a árvore muda). */
function scorePromptField(el) {
  if (!el || el.nodeType !== 1 || !el.isConnected) return -1;
  const st = getComputedStyle(el);
  if (st.display === 'none' || st.visibility === 'hidden' || st.pointerEvents === 'none') return -1;
  const tag = el.tagName;
  if (tag !== 'TEXTAREA' && tag !== 'INPUT' && !el.isContentEditable) return -1;
  if (tag === 'INPUT' && el.type !== 'text' && el.type !== 'search') return -1;
  if (el.disabled || el.getAttribute('aria-disabled') === 'true') return -1;
  if (el.readOnly) return -1;
  const r = el.getBoundingClientRect();
  if (!isReasonablePromptFieldRect(r)) return -1;
  let score = 0;
  const ph = el.getAttribute('placeholder') || '';
  const al = el.getAttribute('aria-label') || '';
  const ti = el.getAttribute('title') || '';
  if (promptFieldKeywordHits(ph) || promptFieldKeywordHits(al) || promptFieldKeywordHits(ti)) score += 220;
  if (tag === 'TEXTAREA') score += 50;
  if (tag === 'INPUT') score += 20;
  if (el.isContentEditable) score += 35;
  score += Math.min(r.width / 22, 110);
  const midY = (r.top + r.bottom) / 2;
  if (midY > window.innerHeight * 0.38) score += 45;
  if (r.width > 240) score += 28;
  return score;
}

function findPromptInputElement() {
  const legacyRoot = xpathNode(INPUT_CONTAINER_XPATH);
  if (legacyRoot) {
    const inner =
      legacyRoot.querySelector('[contenteditable="true"]') ||
      legacyRoot.querySelector('textarea:not([readonly])') ||
      legacyRoot.querySelector('input[type="text"]:not([readonly])') ||
      legacyRoot.querySelector('input[type="search"]:not([readonly])');
    if (inner && scorePromptField(inner) >= 0) return inner;
    if (legacyRoot instanceof HTMLElement && scorePromptField(legacyRoot) >= 0) return legacyRoot;
  }

  const seen = new Set();
  const cands = [];
  const roots = document.querySelectorAll('main, [role="main"], body');
  for (const root of roots) {
    const sel = 'textarea, [contenteditable="true"], input[type="text"], input[type="search"]';
    for (const el of root.querySelectorAll(sel)) {
      if (seen.has(el)) continue;
      seen.add(el);
      const sc = scorePromptField(el);
      if (sc < 0) continue;
      cands.push({ el, sc });
    }
  }
  cands.sort((a, b) => b.sc - a.sc);
  if (cands.length) return cands[0].el;

  let best = null;
  let bestArea = 0;
  for (const el of document.querySelectorAll('textarea, [contenteditable="true"]')) {
    if (!el.isConnected || el.readOnly || el.disabled) continue;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 160 || r.height < 22 || r.top < 60) continue;
    if (r.bottom > window.innerHeight + 120) continue;
    const area = r.width * r.height;
    if (area > bestArea) {
      bestArea = area;
      best = el;
    }
  }
  return best;
}

function measureCenter(el) {
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
}

function rectCenter(el) {
  el.scrollIntoView({ block: 'center', inline: 'center' });
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
}

/**
 * Onde soltar o drag da referência: ponto no interior do campo/composer (não na borda superior).
 * O background.js ainda faz micro-movimentos para “entrar” antes do mouseup.
 */
function referenceDropPointForPrompt(el) {
  if (!el || !el.isConnected) return rectCenter(el);
  el.scrollIntoView({ block: 'center', inline: 'center' });
  const r = el.getBoundingClientRect();
  const edge = 12;
  const narrow = window.innerWidth < 640;
  const cx = Math.round(Math.min(Math.max(r.left + r.width * 0.5, edge + 6), window.innerWidth - edge - 6));
  const fracY = narrow ? 0.46 : 0.44;
  let cy = Math.round(r.top + r.height * fracY);

  for (let n = el.parentElement, d = 0; n && d < 14; d++, n = n.parentElement) {
    const b = n.getBoundingClientRect();
    if (b.width < r.width * 1.04) continue;
    if (b.height > 520 || b.height < r.height + 16) continue;
    const innerY = Math.round(b.top + b.height * 0.4);
    cy = Math.round((cy * 2 + innerY) / 3);
    break;
  }

  const yMin = Math.round(r.top + r.height * 0.22);
  const yMax = Math.round(r.bottom - 12);
  cy = Math.min(Math.max(cy, yMin), yMax);
  cy = Math.min(Math.max(cy, edge + 4), window.innerHeight - edge - 4);
  return { x: cx, y: cy };
}

const FLOW_EDIT_UUID_RE = /\/edit\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i;

function escapeForAttrSelector(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

function uuidFromFlowHrefString(h) {
  if (!h || typeof h !== 'string') return null;
  const m = h.match(FLOW_EDIT_UUID_RE);
  return m ? m[1].toLowerCase() : null;
}

function uuidFromAnyText(s) {
  if (!s || typeof s !== 'string') return null;
  const m = s.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
  return m ? m[1].toLowerCase() : null;
}

function absoluteHref(a) {
  if (!a) return '';
  try {
    const raw = a.getAttribute('href') || '';
    return (a.href || new URL(raw, location.href).href || raw).toLowerCase();
  } catch (_) {
    return (a.getAttribute('href') || '').toLowerCase();
  }
}

/** UUID em `/edit/<uuid>` no link do tile (href relativo ou absoluto). */
function findGenerationUuidForCard(card) {
  if (!card || card.nodeType !== 1) return null;
  const tryLink = (a) => {
    if (!a) return null;
    const u = uuidFromFlowHrefString(absoluteHref(a));
    if (u) return u;
    return uuidFromFlowHrefString(a.getAttribute('href') || '');
  };

  const cardTile = card.closest?.('[data-tile-id]') || (card.matches?.('[data-tile-id]') ? card : null);
  const tileUuid = uuidFromAnyText(cardTile?.getAttribute?.('data-tile-id') || '');
  if (tileUuid) return tileUuid;

  const localLinks = card.querySelectorAll?.('a[href*="/edit/"]') || [];
  for (const a of localLinks) {
    const u = tryLink(a);
    if (!u) continue;
    if (!cardTile) return u;
    const linkTile = a.closest('[data-tile-id]');
    const linkTileUuid = uuidFromAnyText(linkTile?.getAttribute?.('data-tile-id') || '');
    if (!linkTile || !linkTileUuid || linkTileUuid === u) return u;
  }

  const localAnchor = card.closest?.('a[href*="/edit/"]');
  if (localAnchor) {
    const u = tryLink(localAnchor);
    if (u) return u;
  }
  return null;
}

/**
 * Âncora estável: UUID em `/edit/...` do link do tile.
 * Fallback: `data-tile-id` (pode mudar se o Flow reciclar o atributo — prefira o link).
 */
function extractCardAnchor(card) {
  const gen = findGenerationUuidForCard(card);
  if (gen) return { kind: 'generation', value: gen };
  let el = card;
  for (let d = 0; el && d < 24; d++, el = el.parentElement) {
    if (el.nodeType !== 1) continue;
    const tile = el.getAttribute('data-tile-id');
    if (tile) {
      const v = tile.trim();
      const u = uuidFromAnyText(v);
      if (u) return { kind: 'generation', value: u };
      if (v.length > 4) return { kind: 'data-tile-id', value: v };
    }
  }
  return null;
}

function pickSmallestTileWithImg(candidates) {
  let best = null;
  let bestArea = Infinity;
  for (const tile of candidates) {
    if (!tile || !tile.isConnected) continue;
    const media =
      tile.tagName === 'IMG' || tile.tagName === 'VIDEO'
        ? tile
        : tile.querySelector('img,video');
    if (!media) continue;
    const r = tile.getBoundingClientRect();
    if (r.width < 20 || r.height < 20) continue;
    const area = r.width * r.height;
    if (area < bestArea) {
      bestArea = area;
      best = tile;
    }
  }
  return best;
}

/** Melhor mídia arrastável: <img> maior; senão <video> (tiles só-vídeo no Flow). */
function bestDragMediaForTileRoot(root) {
  if (!root || !root.isConnected) return null;
  if (root.tagName === 'IMG' || root.tagName === 'VIDEO') return root;
  let best = null;
  let bestScore = 0;
  for (const img of root.querySelectorAll('img')) {
    const nw = img.naturalWidth || img.width || 0;
    const nh = img.naturalHeight || img.height || 0;
    const br = img.getBoundingClientRect();
    const w = nw || br.width || 0;
    const h = nh || br.height || 0;
    if (w < 20 || h < 20) continue;
    const score = w * h;
    if (score > bestScore) {
      bestScore = score;
      best = img;
    }
  }
  if (best) return best;
  for (const v of root.querySelectorAll('video')) {
    const br = v.getBoundingClientRect();
    const w = br.width || v.videoWidth || 0;
    const h = br.height || v.videoHeight || 0;
    if (w < 24 || h < 24) continue;
    const score = w * h;
    if (score > bestScore) {
      bestScore = score;
      best = v;
    }
  }
  if (best) return best;
  return root.querySelector('img') || root.querySelector('video');
}

function generationLinkMatchesUuid(a, uuid) {
  if (!a || !uuid) return false;
  const h = absoluteHref(a);
  const raw = (a.getAttribute('href') || '').toLowerCase();
  if (uuidFromFlowHrefString(h) === uuid || uuidFromFlowHrefString(raw) === uuid) return true;
  if (!h.includes(uuid) && !raw.includes(uuid)) return false;
  return h.includes('/edit/') || h.includes('edit/') || h.includes('generation') || h.includes('flow');
}

function queryElementByAnchor(anchor) {
  if (!anchor || !anchor.value) return null;
  try {
    if (anchor.kind === 'generation') {
      const uuid = anchor.value.toLowerCase();
      const tiles = new Set();

      const strictSelectors = [
        `a[href*="/edit/${uuid}"]`,
        `a[href$="/edit/${uuid}"]`,
      ];
      for (const sel of strictSelectors) {
        for (const a of document.querySelectorAll(sel)) {
          if (!generationLinkMatchesUuid(a, uuid)) continue;
          const tile = a.closest('[data-tile-id]') || a.closest('[role="button"]') || a.parentElement;
          if (tile) tiles.add(tile);
        }
      }

      let cap = 0;
      for (const el of document.querySelectorAll('[data-tile-id]')) {
        if (++cap > 900) break;
        const v = (el.getAttribute('data-tile-id') || '').toLowerCase();
        if (uuidFromAnyText(v) === uuid || v.includes(uuid)) tiles.add(el);
      }

      if (!tiles.size) {
        for (const a of document.querySelectorAll('a[href]')) {
          if (!generationLinkMatchesUuid(a, uuid)) continue;
          const tile = a.closest('[data-tile-id]') || a.closest('[role="button"]') || a.parentElement;
          if (tile) tiles.add(tile);
        }
      }

      return pickSmallestTileWithImg(tiles);
    }
    if (anchor.kind === 'data-tile-id') {
      const raw = String(anchor.value || '').trim();
      const escaped = escapeForAttrSelector(raw);
      let list = document.querySelectorAll(`[data-tile-id="${escaped}"]`);
      if (!list.length && raw.length >= 8) {
        const loose = [];
        let cap = 0;
        for (const el of document.querySelectorAll('[data-tile-id]')) {
          if (++cap > 900) break;
          const v = (el.getAttribute('data-tile-id') || '').trim();
          if (v === raw || v.includes(raw)) loose.push(el);
        }
        list = loose;
      }
      const arr = Array.from(list);
      return pickSmallestTileWithImg(arr) || arr[0] || null;
    }
  } catch (_) {}
  return null;
}

function wrapperFromAnchorRoot(root, used) {
  if (!root || !root.isConnected) return null;
  const img = bestDragMediaForTileRoot(root);
  if (!img) return null;
  const wrap = wrapperForRefDrag(img);
  if (used.has(wrap)) return null;
  const r = wrap.getBoundingClientRect();
  if (r.width < 36 || r.height < 36) return null;
  return wrap;
}

function resolveWrapperByAnchor(entry, used) {
  if (!entry || !entry.anchor) return null;
  return wrapperFromAnchorRoot(queryElementByAnchor(entry.anchor), used);
}

function fingerprintFromCard(card) {
  return { anchor: extractCardAnchor(card) };
}

function anchorsMatch(a, b) {
  const ka = anchorKey(a);
  const kb = anchorKey(b);
  return !!ka && ka === kb;
}

function canonicalizeAnchor(anchor) {
  if (!anchor || !anchor.kind || !anchor.value) return null;
  const kind = String(anchor.kind);
  const value = String(anchor.value).trim();
  if (!value) return null;
  const uuid = uuidFromAnyText(value);
  if (uuid) return { kind: 'generation', value: uuid };
  if (kind === 'generation') return null;
  if (kind === 'data-tile-id') return { kind: 'data-tile-id', value };
  return null;
}

function anchorKey(anchor) {
  const a = canonicalizeAnchor(anchor);
  if (!a) return '';
  const value = String(a.value).trim().toLowerCase();
  return `${a.kind}:${value}`;
}

function normalizeRefEntries(entries) {
  if (!Array.isArray(entries) || entries.length === 0) return [];
  const out = [];
  const seen = new Set();
  for (const e of entries) {
    if (!e || !e.anchor) continue;
    const a = canonicalizeAnchor(e.anchor);
    if (!a) continue;
    const k = anchorKey(a);
    if (!k || seen.has(k)) continue;
    seen.add(k);
    out.push({ ...e, anchor: a });
  }
  return out;
}

async function captureCardPreview(card) {
  const img = card.querySelector('img') || (card.tagName === 'IMG' ? card : null);
  if (!img) return '';
  if (!img.complete || !(img.naturalWidth || img.width)) {
    await new Promise((resolve) => {
      const done = () => resolve();
      img.addEventListener('load', done, { once: true });
      img.addEventListener('error', done, { once: true });
      setTimeout(done, 1000);
    });
  }
  try {
    const max = 64;
    const w = img.naturalWidth || img.width || 1;
    const h = img.naturalHeight || img.height || 1;
    const scale = Math.min(1, max / w, max / h);
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w * scale));
    c.height = Math.max(1, Math.round(h * scale));
    const ctx = c.getContext('2d');
    ctx.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', 0.82);
  } catch (_) {
    return '';
  }
}

async function getRefEntries() {
  const s = await chrome.storage.local.get('flowRefEntries');
  if (!Array.isArray(s.flowRefEntries) || !s.flowRefEntries.length) return [];
  const filtered = s.flowRefEntries.filter((e) => {
    if (!e || !e.anchor || typeof e.anchor.value !== 'string' || e.anchor.value.length < 4) return false;
    return e.anchor.kind === 'generation' || e.anchor.kind === 'data-tile-id';
  });
  return normalizeRefEntries(filtered);
}

async function persistRefEntries(entries) {
  const normalized = normalizeRefEntries(entries);
  await chrome.storage.local.set({
    flowCardSelected: normalized.length > 0,
    flowRefEntries: normalized,
    flowRefThumbUrls: [],
    flowRefThumbUrl: '',
  });
}

function resolveWrapperFromEntryVisible(entry, used) {
  return resolveWrapperByAnchor(entry, used);
}

function isScrollableY(el) {
  if (!el || el.nodeType !== 1) return false;
  const st = getComputedStyle(el);
  const oy = st.overflowY;
  if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') return false;
  return el.scrollHeight > el.clientHeight + 36;
}

function isScrollableX(el) {
  if (!el || el.nodeType !== 1) return false;
  const st = getComputedStyle(el);
  const ox = st.overflowX;
  if (ox !== 'auto' && ox !== 'scroll' && ox !== 'overlay') return false;
  return el.scrollWidth > el.clientWidth + 36;
}

function isScrollHost(el) {
  return isScrollableY(el) || isScrollableX(el);
}

function overflowAllowsProgrammaticScroll(o) {
  return o === 'auto' || o === 'scroll' || o === 'overlay' || o === 'hidden';
}

function fireScrollEvent(el) {
  if (!el || el.nodeType !== 1) return;
  el.dispatchEvent(new Event('scroll', { bubbles: true }));
}

/** Primeiro ancestral com scroll real (Virtuoso / galeria). */
function captureScrollHintFromCard(card) {
  if (!card || card.nodeType !== 1) return null;
  for (let e = card, d = 0; e && d < 72; d++, e = e.parentElement) {
    const st = getComputedStyle(e);
    const oy = st.overflowY;
    const ox = st.overflowX;
    const yOk =
      e.scrollHeight > e.clientHeight + 12 &&
      overflowAllowsProgrammaticScroll(oy) &&
      oy !== 'visible';
    const xOk =
      e.scrollWidth > e.clientWidth + 12 &&
      overflowAllowsProgrammaticScroll(ox) &&
      ox !== 'visible';
    if (!yOk && !xOk) continue;
    return {
      top: e.scrollTop,
      left: e.scrollLeft,
      sh: e.scrollHeight,
      ch: e.clientHeight,
      sw: e.scrollWidth,
      cw: e.clientWidth,
    };
  }
  return null;
}

function hostMatchesScrollHint(host, hint) {
  if (!hint || typeof hint.sh !== 'number' || typeof hint.ch !== 'number') return false;
  const dsh = Math.abs(host.scrollHeight - hint.sh);
  const dch = Math.abs(host.clientHeight - hint.ch);
  if (dsh > 520 && dsh / Math.max(hint.sh, 1) > 0.28) return false;
  if (dch > 160 && dch / Math.max(hint.ch, 1) > 0.24) return false;
  return true;
}

function applyScrollHintToHosts(hosts, hint) {
  if (!hint || typeof hint.top !== 'number') return;
  for (const host of hosts) {
    if (!hostMatchesScrollHint(host, hint)) continue;
    const maxY = Math.max(0, host.scrollHeight - host.clientHeight);
    const maxX = Math.max(0, host.scrollWidth - host.clientWidth);
    host.scrollTop = Math.max(0, Math.min(Number(hint.top) || 0, maxY));
    host.scrollLeft = Math.max(0, Math.min(Number(hint.left) || 0, maxX));
    fireScrollEvent(host);
  }
}

/**
 * React Virtuoso: priorizar scrollers com overflow:auto antes de hidden;
 * ignorar overflow:visible (altura “virtual” sem scroll real).
 */
function pushVirtuosoGalleryScrollHosts(seen, out) {
  const scored = [];
  const consider = (el, depth) => {
    if (!el || el.nodeType !== 1) return;
    const st = getComputedStyle(el);
    const oy = st.overflowY;
    const ox = st.overflowX;
    const yUse =
      el.scrollHeight > el.clientHeight + 12 &&
      overflowAllowsProgrammaticScroll(oy) &&
      oy !== 'visible';
    const xUse =
      el.scrollWidth > el.clientWidth + 12 &&
      overflowAllowsProgrammaticScroll(ox) &&
      ox !== 'visible';
    if (!yUse && !xUse) return;
    const yHidden = oy === 'hidden' ? 1 : 0;
    const xHidden = ox === 'hidden' ? 1 : 0;
    scored.push({ el, depth, rank: yHidden + xHidden + depth * 0.001 });
  };

  for (const list of document.querySelectorAll('[data-testid="virtuoso-item-list"]')) {
    let depth = 0;
    for (let e = list; e && depth < 56; e = e.parentElement, depth++) consider(e, depth);
  }
  for (const sc of document.querySelectorAll('[data-virtuoso-scroller="true"]')) {
    consider(sc, 0);
    let d = 0;
    for (let e = sc.parentElement; e && d < 16; d++, e = e.parentElement) consider(e, d + 1);
  }
  scored.sort((a, b) => a.rank - b.rank || a.depth - b.depth);
  for (const { el } of scored) {
    if (seen.has(el)) continue;
    seen.add(el);
    out.push(el);
  }
}

/** Mais scrollers candidatos (subárvore main), ordenados por área rolável. */
function pushDeepScrollHosts(seen, out, maxNodes) {
  const cap = maxNodes ?? 4200;
  const scored = [];
  let n = 0;
  const roots = document.querySelectorAll('[role="main"], main, body');
  outer: for (const root of roots) {
    if (!root || !root.querySelectorAll) continue;
    for (const el of root.querySelectorAll('*')) {
      if (++n > cap) break outer;
      if (seen.has(el)) continue;
      if (!isScrollHost(el)) continue;
      const range = Math.max(
        el.scrollHeight - el.clientHeight,
        el.scrollWidth - el.clientWidth,
        0
      );
      scored.push({ el, range });
    }
  }
  scored.sort((a, b) => b.range - a.range);
  const take = Math.min(64, scored.length);
  for (let i = 0; i < take; i++) {
    const { el } = scored[i];
    if (seen.has(el)) continue;
    seen.add(el);
    out.push(el);
  }
}

/**
 * Painéis roláveis: ancestrais do container do Flow + candidatos comuns + documento.
 * Lista virtual às vezes está num div que não aparece no XPath fixo.
 */
function galleryScrollHostsAll() {
  const seen = new Set();
  const priority = [];
  pushVirtuosoGalleryScrollHosts(seen, priority);

  const out = [];
  const push = (el) => {
    if (!el || seen.has(el) || !isScrollHost(el)) return;
    seen.add(el);
    out.push(el);
  };
  const anchor = xpathNode(CARDS_CONTAINER_XPATH);
  let e = anchor;
  for (let d = 0; e && d < 32; d++, e = e.parentElement) push(e);
  let scanned = 0;
  for (const el of document.querySelectorAll('main,section,article,aside,div')) {
    if (scanned++ > 900) break;
    push(el);
  }
  const root = document.scrollingElement || document.documentElement;
  push(root);
  pushDeepScrollHosts(seen, out);
  out.sort(
    (a, b) =>
      Math.max(b.scrollHeight - b.clientHeight, b.scrollWidth - b.clientWidth) -
      Math.max(a.scrollHeight - a.clientHeight, a.scrollWidth - a.clientWidth)
  );
  return [...priority, ...out];
}

async function scrollOneHostForTile(host, tryOnce, stepWin) {
  const maxY = Math.max(0, host.scrollHeight - host.clientHeight);
  const maxX = Math.max(0, host.scrollWidth - host.clientWidth);
  const savedY = host.scrollTop;
  const savedX = host.scrollLeft;
  const settleMs = () => (maxY > 6000 || maxX > 6000 ? 360 : maxY > 2000 ? 300 : 240);

  const setScrollY = async (y) => {
    host.scrollTop = y;
    fireScrollEvent(host);
    await stepWin();
    await stepWin();
    await sleep(settleMs());
  };
  const setScrollX = async (x) => {
    host.scrollLeft = x;
    fireScrollEvent(host);
    await stepWin();
    await stepWin();
    await sleep(Math.max(200, settleMs() - 40));
  };

  if (maxY < 1 && maxX < 1) {
    await sleep(120);
    return tryOnce() || null;
  }

  const offsetsFor = (step) => [0, Math.floor(step / 2), Math.floor(step / 4)];

  const probeDenseY = async () => {
    if (maxY < 1) return null;
    const steps = maxY > 3500 ? 56 : maxY > 1200 ? 36 : 0;
    if (steps < 1) return null;
    const ys = new Set();
    for (let i = 0; i <= steps; i++) ys.add(Math.floor((maxY * i) / steps));
    ys.add(maxY);
    const sorted = [...ys].sort((a, b) => a - b);
    for (const y of sorted) {
      await setScrollY(Math.min(y, maxY));
      const hit = tryOnce();
      if (hit) return hit;
    }
    return null;
  };

  const sweepY = async (step) => {
    if (maxY < 1) return null;
    const stepClamped = Math.max(22, Math.min(100, Math.round(step)));
    for (const offset of offsetsFor(stepClamped)) {
      for (let y = offset; y <= maxY + stepClamped; y += stepClamped) {
        await setScrollY(Math.min(y, maxY));
        const hit = tryOnce();
        if (hit) return hit;
      }
    }
    return null;
  };

  const sweepX = async (step) => {
    if (maxX < 1) return null;
    const stepClamped = Math.max(22, Math.min(100, Math.round(step)));
    for (const offset of offsetsFor(stepClamped)) {
      for (let x = offset; x <= maxX + stepClamped; x += stepClamped) {
        await setScrollX(Math.min(x, maxX));
        const hit = tryOnce();
        if (hit) return hit;
      }
    }
    return null;
  };

  let hit = await probeDenseY();
  if (hit) return hit;

  let stepY = Math.max(38, Math.min(92, Math.floor(host.clientHeight * 0.13)));
  hit = await sweepY(stepY);
  if (hit) return hit;
  hit = await sweepY(Math.max(24, Math.floor(stepY * 0.55)));
  if (hit) return hit;

  host.scrollTop = savedY;
  host.scrollLeft = savedX;
  fireScrollEvent(host);
  await stepWin();
  await sleep(120);

  let stepX = Math.max(38, Math.min(92, Math.floor(host.clientWidth * 0.16)));
  hit = await sweepX(stepX);
  if (hit) return hit;
  hit = await sweepX(Math.max(24, Math.floor(stepX * 0.55)));
  if (hit) return hit;

  host.scrollTop = savedY;
  host.scrollLeft = savedX;
  fireScrollEvent(host);
  await stepWin();
  await sleep(140);
  return tryOnce() || null;
}

async function scrollSearchForEntryWrapper(entry, used) {
  const stepWin = () => new Promise((r) => requestAnimationFrame(r));
  const tryOnce = () => resolveWrapperByAnchor(entry, used);

  for (let round = 0; round < 3; round++) {
    if (round > 0) await sleep(480);
    const hosts = galleryScrollHostsAll();
    if (round === 0 && entry.scrollHint) {
      applyScrollHintToHosts(hosts, entry.scrollHint);
      await sleep(420);
      const hinted = tryOnce();
      if (hinted) return hinted;
    }
    for (const host of hosts) {
      const hit = await scrollOneHostForTile(host, tryOnce, stepWin);
      if (hit) return hit;
    }
  }
  return null;
}

async function resolveWrapperForEntry(entry, used, allowScroll) {
  let w = resolveWrapperFromEntryVisible(entry, used);
  if (w) return w;
  if (!allowScroll) return null;
  return scrollSearchForEntryWrapper(entry, used);
}

function cardIdLabel(entry) {
  const a = entry?.anchor;
  if (!a?.value) return '(sem âncora)';
  if (a.kind === 'generation') return `geração /edit/${a.value}`;
  if (a.kind === 'data-tile-id') return `data-tile-id="${a.value}"`;
  return String(a.value);
}

function wrapperForRefDrag(img) {
  if (!img || !img.isConnected) return img;
  const dragBtn =
    img.closest?.('[role="button"][aria-roledescription="draggable"]') ||
    img.closest?.('[role="button"]');
  if (dragBtn) {
    const r = dragBtn.getBoundingClientRect();
    if (r.width >= 48 && r.height >= 48 && r.width < window.innerWidth * 0.8) return dragBtn;
  }

  const tile = img.closest?.('[data-tile-id]');
  if (tile) {
    const media = bestDragMediaForTileRoot(tile);
    if (media) return media;
    const tr = tile.getBoundingClientRect();
    if (tr.width >= 70 && tr.height >= 70 && tr.width <= Math.max(520, window.innerWidth * 0.78)) {
      return tile;
    }
  }
  return img;
}

async function ensureVisibleAndLayoutForCard(card) {
  card.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
  await new Promise((r) => requestAnimationFrame(r));
  await new Promise((r) => requestAnimationFrame(r));
  await sleep(120);
  const img =
    card.querySelector('img') ||
    card.querySelector('video') ||
    (card.tagName === 'IMG' || card.tagName === 'VIDEO' ? card : null);
  if (img && img.tagName === 'IMG' && !img.complete) {
    await new Promise((resolve) => {
      const done = () => resolve();
      img.addEventListener('load', done, { once: true });
      img.addEventListener('error', done, { once: true });
      setTimeout(done, 2800);
    });
  }
  if (img && typeof img.decode === 'function') {
    try {
      await img.decode();
    } catch (_) {}
  }
  card.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
  await sleep(90);
}

async function getRefCardPositionsAsync() {
  const entries = await getRefEntries();
  if (entries.length === 0) {
    throw new Error('Nenhuma referência. Use 🎯 no tile (precisa do link /edit/<uuid> ou data-tile-id).');
  }
  const positions = [];
  const used = new Set();
  for (let i = 0; i < entries.length; i++) {
    const w = await resolveWrapperForEntry(entries[i], used, true);
    if (!w) {
      throw new Error(
        `Não encontrei ${cardIdLabel(entries[i])} após rolar a galeria (tile fora do DOM ou URL mudou).`
      );
    }
    used.add(w);
    await ensureVisibleAndLayoutForCard(w);
    positions.push(measureCenter(w));
    await sleep(55);
  }
  return positions;
}

async function getRefCardPositionAsync() {
  const positions = await getRefCardPositionsAsync();
  return positions[0];
}

async function getRefCardPositionAtIndexAsync(index) {
  const entries = await getRefEntries();
  const i = Number(index);
  if (!Number.isInteger(i) || i < 0 || i >= entries.length) {
    throw new Error(`Índice de referência inválido: ${index}`);
  }
  const used = new Set();
  const w = await resolveWrapperForEntry(entries[i], used, true);
  if (!w) {
    throw new Error(
      `Não encontrei ${cardIdLabel(entries[i])} após rolar a galeria (tile fora do DOM ou URL mudou).`
    );
  }
  await ensureVisibleAndLayoutForCard(w);
  return measureCenter(w);
}

function outlineForRefIndex(i) {
  return `3px solid hsl(${148 + i * 36}, 62%, 52%)`;
}

async function syncDomMarkersFromEntries(entries, allowScroll) {
  document.querySelectorAll(`[${REF_ATTR}]`).forEach((el) => {
    el.removeAttribute(REF_ATTR);
    if (pickerHighlighted !== el) el.style.outline = el._prevOutline || '';
  });
  const used = new Set();
  for (let i = 0; i < entries.length; i++) {
    const w = await resolveWrapperForEntry(entries[i], used, allowScroll);
    if (!w) continue;
    used.add(w);
    w.setAttribute(REF_ATTR, String(i));
    w._prevOutline = w.style.outline;
    w.style.outline = outlineForRefIndex(i);
  }
}

async function toggleRefCard(card) {
  if (toggleRefCard._busy) return;
  toggleRefCard._busy = true;
  try {
  const fp = fingerprintFromCard(card);
  if (!fp.anchor) {
    chrome.runtime.sendMessage({
      action: 'refPickError',
      text: 'Não achei link /edit/… no tile (clique na área da imagem ou do card com o <a>). Sem isso, só data-tile-id é usado como fallback.',
    }).catch(() => {});
    return;
  }
  let entries = normalizeRefEntries(await getRefEntries());
  const pickedUuid = uuidFromAnyText(fp.anchor.value || '');
  const isSamePickedCard = (entry) => {
    if (!entry || !entry.anchor) return false;
    if (anchorsMatch(entry.anchor, fp.anchor)) return true;
    if (!pickedUuid) return false;
    return uuidFromAnyText(entry.anchor.value || '') === pickedUuid;
  };
  const hadMatch = entries.some(isSamePickedCard);
  entries = entries.filter((e) => !isSamePickedCard(e));
  if (!hadMatch) {
    const previewDataUrl = await captureCardPreview(card);
    const scrollHint = captureScrollHintFromCard(card);
    entries = [{
      anchor: fp.anchor,
      previewDataUrl: previewDataUrl || '',
      ...(scrollHint ? { scrollHint } : {}),
    }];
  }
  entries = normalizeRefEntries(entries);
  await persistRefEntries(entries);
  await syncDomMarkersFromEntries(entries, true);
  chrome.runtime.sendMessage({ action: 'refsUpdated', count: entries.length }).catch(() => {});
  } finally {
    toggleRefCard._busy = false;
  }
}
toggleRefCard._busy = false;

let pickerHighlighted = null;
let lastPickTs = 0;
let lastPickAnchorKey = '';

function rectContainsPoint(r, x, y) {
  if (!r) return false;
  return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
}

function isLikelySingleCardTile(el, x, y) {
  if (!el || el.nodeType !== 1) return false;
  const r = el.getBoundingClientRect();
  if (!rectContainsPoint(r, x, y)) return false;
  if (r.width < 70 || r.height < 70) return false;
  if (r.width > Math.max(430, window.innerWidth * 0.7)) return false;
  if (r.height > Math.max(520, window.innerHeight * 0.8)) return false;
  const hasMedia = !!(el.querySelector('img,video') || el.tagName === 'IMG' || el.tagName === 'VIDEO');
  if (!hasMedia) return false;
  const hasAnchor = !!(el.querySelector('a[href*="/edit/"]') || el.closest('a[href*="/edit/"]'));
  const hasTileId = !!el.getAttribute('data-tile-id');
  return hasAnchor || hasTileId;
}

function candidateTileFromElement(el, x, y) {
  if (!el || el.nodeType !== 1) return null;
  const cands = [];
  const push = (n) => {
    if (!n || cands.includes(n)) return;
    cands.push(n);
  };

  push(el.closest('[data-tile-id]'));
  const a = el.closest('a[href*="/edit/"]');
  if (a) {
    push(a.closest('[data-tile-id]'));
    push(a.parentElement);
  }
  if (el.matches?.('[data-tile-id]')) push(el);

  let best = null;
  let bestArea = Infinity;
  for (const c of cands) {
    if (!isLikelySingleCardTile(c, x, y)) continue;
    const r = c.getBoundingClientRect();
    const area = r.width * r.height;
    if (area < bestArea) {
      bestArea = area;
      best = c;
    }
  }
  return best;
}

function cardAtPoint(x, y) {
  const els = document.elementsFromPoint(x, y);
  let best = null;
  let bestArea = Infinity;
  for (const el of els) {
    if (el === document.documentElement || el === document.body) continue;
    const tile = candidateTileFromElement(el, x, y);
    if (!tile) continue;
    const r = tile.getBoundingClientRect();
    const area = r.width * r.height;
    if (area < bestArea) {
      bestArea = area;
      best = tile;
    }
  }
  return best;
}

function clearPickerHighlight() {
  if (!pickerHighlighted) return;
  if (pickerHighlighted._flowHoverOutline !== undefined) {
    pickerHighlighted.style.outline = pickerHighlighted._flowHoverOutline;
    delete pickerHighlighted._flowHoverOutline;
  } else if (!pickerHighlighted.hasAttribute(REF_ATTR)) {
    pickerHighlighted.style.outline = pickerHighlighted._prevOutline || '';
  }
  pickerHighlighted = null;
}

function onPickerMove(e) {
  const card = cardAtPoint(e.clientX, e.clientY);
  if (card === pickerHighlighted) return;
  clearPickerHighlight();
  if (card) {
    card._prevOutline = card.style.outline;
    if (card.hasAttribute(REF_ATTR)) {
      card._flowHoverOutline = card.style.outline;
      card.style.outline = '3px solid #fbbf24';
    } else {
      card.style.outline = '3px solid #a78bfa';
    }
    pickerHighlighted = card;
  }
}

function onPickerClick(e) {
  const card = cardAtPoint(e.clientX, e.clientY);
  if (!card) return;
  e.stopPropagation();
  e.preventDefault();
  const anchor = extractCardAnchor(card);
  const now = Date.now();
  const k = anchorKey(anchor);
  if (k && k === lastPickAnchorKey && now - lastPickTs < 380) return;
  lastPickAnchorKey = k;
  lastPickTs = now;
  toggleRefCard(card).catch(() => {});
}

function onPickerKey(e) {
  if (e.key === 'Escape') {
    detachPickerListeners();
    chrome.runtime.sendMessage({ action: 'pickerCancelled' });
  }
}

function detachPickerListeners() {
  document.removeEventListener('mousemove', onPickerMove, true);
  document.removeEventListener('click', onPickerClick, true);
  document.removeEventListener('keydown', onPickerKey, true);
  clearPickerHighlight();
}

function activatePicker() {
  document.addEventListener('mousemove', onPickerMove, true);
  document.addEventListener('click', onPickerClick, true);
  document.addEventListener('keydown', onPickerKey, true);
}

function focusEditableElement(el) {
  if (!el || !el.isConnected) return null;

  el.scrollIntoView({ block: 'center', inline: 'center' });
  el.click();
  el.focus();

  if (el.isContentEditable) {
    const range = document.createRange();
    const sel = window.getSelection();
    range.selectNodeContents(el);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
  } else if (typeof el.setSelectionRange === 'function') {
    const len = (el.value || '').length;
    el.setSelectionRange(len, len);
  }

  const r = el.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), isContentEditable: el.isContentEditable };
}

function focusEditableIn(container) {
  if (!container) return null;
  const el =
    container.querySelector('[contenteditable="true"]') ||
    container.querySelector('textarea:not([readonly])') ||
    container.querySelector('input[type="text"]:not([readonly])') ||
    container.querySelector('input[type="search"]:not([readonly])') ||
    container;
  return focusEditableElement(el);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action === 'ping') {
    sendResponse({ ok: true });
    return;
  }

  if (msg.action === 'checkCardSelected') {
    (async () => {
      const entries = await getRefEntries();
      const selected = entries.length > 0 || document.querySelectorAll(`[${REF_ATTR}]`).length > 0;
      sendResponse({ ok: true, selected, count: entries.length });
    })();
    return true;
  }

  if (msg.action === 'startPicker') {
    activatePicker();
    sendResponse({ ok: true });
    return;
  }

  if (msg.action === 'cancelPicker') {
    detachPickerListeners();
    sendResponse({ ok: true });
    return;
  }

  if (msg.action === 'getRefCardPosition') {
    (async () => {
      try {
        const pos = await getRefCardPositionAsync();
        sendResponse({ ok: true, ...pos });
      } catch (e) {
        sendResponse({ ok: false, error: e.message || String(e) });
      }
    })();
    return true;
  }

  if (msg.action === 'getRefCardPositions') {
    (async () => {
      try {
        const positions = await getRefCardPositionsAsync();
        sendResponse({ ok: true, positions });
      } catch (e) {
        sendResponse({ ok: false, error: e.message || String(e) });
      }
    })();
    return true;
  }

  if (msg.action === 'getRefCount') {
    (async () => {
      const entries = await getRefEntries();
      sendResponse({ ok: true, count: entries.length });
    })();
    return true;
  }

  if (msg.action === 'getRefCardPositionAtIndex') {
    (async () => {
      try {
        const pos = await getRefCardPositionAtIndexAsync(msg.index);
        sendResponse({ ok: true, ...pos });
      } catch (e) {
        sendResponse({ ok: false, error: e.message || String(e) });
      }
    })();
    return true;
  }

  if (msg.action === 'clearRefCards') {
    (async () => {
      document.querySelectorAll(`[${REF_ATTR}]`).forEach((el) => {
        el.removeAttribute(REF_ATTR);
        el.style.outline = el._prevOutline || '';
      });
      await chrome.storage.local.set({
        flowCardSelected: false,
        flowRefEntries: [],
        flowRefThumbUrls: [],
        flowRefThumbUrl: '',
      });
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (msg.action === 'removeRefEntryAtIndex') {
    (async () => {
      let entries = await getRefEntries();
      const i = Number(msg.index);
      if (Number.isInteger(i) && i >= 0 && i < entries.length) entries.splice(i, 1);
      await persistRefEntries(entries);
      await syncDomMarkersFromEntries(entries, false);
      sendResponse({ ok: true, count: entries.length });
    })();
    return true;
  }

  if (msg.action === 'getElementPosition') {
    let el = msg.xpath ? xpathNode(msg.xpath) : null;
    if (!el) el = findPromptInputElement();
    if (!el) {
      sendResponse({
        ok: false,
        error:
          'Campo de prompt não encontrado. Abre o painel de texto do Flow (textarea ou caixa editável) e tenta de novo.',
      });
      return;
    }
    setTimeout(() => sendResponse({ ok: true, ...referenceDropPointForPrompt(el) }), 220);
    return true;
  }

  if (msg.action === 'getGenerateButtonPosition') {
    const icon = [...document.querySelectorAll('i.google-symbols')].find(i => i.textContent.trim() === 'arrow_forward');
    const btn = icon?.closest('button');
    if (!btn) { sendResponse({ ok: false, error: 'Botão gerar não encontrado' }); return; }
    setTimeout(() => sendResponse({ ok: true, ...rectCenter(btn) }), 220);
    return true;
  }

  if (msg.action === 'focusInput') {
    let res = null;
    if (msg.xpath) {
      const container = xpathNode(msg.xpath);
      if (container) res = focusEditableIn(container);
    }
    if (!res) {
      const el = findPromptInputElement();
      if (el) res = focusEditableElement(el);
    }
    if (!res) {
      sendResponse({ ok: false, error: 'Campo de prompt não encontrado para focar.' });
      return;
    }
    setTimeout(() => sendResponse({ ok: true, ...res }), 150);
    return true;
  }

  // Ações de download/exclusão ficam como placeholders nesta restauração rápida.
  if (
    msg.action === 'getAllCardsForDownload' ||
    msg.action === 'trimDownloadQueue' ||
    msg.action === 'dequeueCard' ||
    msg.action === 'waitForSuccessToast' ||
    msg.action === 'checkDownloadToast' ||
    msg.action === 'getNewestCardPosition' ||
    msg.action === 'getBaixarPosition' ||
    msg.action === 'clickBaixar' ||
    msg.action === 'clickQuality' ||
    msg.action === 'getExcluirPosition' ||
    msg.action === 'clickExcluir' ||
    msg.action === 'clickConfirmDeleteIfPresent'
  ) {
    sendResponse({ ok: false, error: 'Fluxo de download/exclusão não restaurado nesta versão rápida.' });
    return;
  }
});

console.log('[Flow] content script ready');
}
