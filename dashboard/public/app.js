'use strict';
// ── Data source ──────────────────────────────────────────────────────────────
const BAKED = window.BAKED_DATA || null;

const get = BAKED ? async (url) => {
  if (url === '/api/technical') return BAKED.technical || [];
  if (url.startsWith('/api/technical/')) {
    const sym = url.split('/').pop();
    return BAKED.technical?.find(s => s.symbol === sym) || null;
  }
  if (url.startsWith('/api/ta/')) {
    const sym = decodeURIComponent(url.split('/api/ta/')[1]);
    return { symbol: sym, indicators: BAKED.ta?.[sym] || {} };
  }
  if (url === '/api/suggestions/stats') return BAKED.suggestionStats || {};
  if (url === '/api/suggestions') return BAKED.suggestions || [];
  if (url === '/api/suggestions/outcomes') return BAKED.suggestionOutcomes || [];
  if (url === '/api/watchlists') return BAKED.watchlists || [];
  if (url.startsWith('/api/prices')) {
    const syms = new URL('http://x' + url).searchParams.get('symbols')?.split(',') || [];
    const out = {};
    for (const s of syms) if (BAKED.prices?.[s]) out[s] = BAKED.prices[s];
    return out;
  }
  return null;
} : url => fetch(url).then(r => r.json()).catch(() => null);

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmt(n, dec = 2) { return n == null ? '—' : (+n).toFixed(dec); }
function pct(n) { return n == null ? '—' : (n > 0 ? '+' : '') + (+n).toFixed(1) + '%'; }
function curr(s) { return s?.entry_zone?.currency === 'INR' ? '₹' : '$'; }
function yfSym(s) {
  if (!s?.ticker) return '';
  return s.market === 'IN' && !String(s.ticker).includes('.') ? s.ticker + '.NS' : s.ticker;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function titleizeWatchlist(id) {
  return (id || 'watchlist')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, ch => ch.toUpperCase());
}

function priceKeyFor(entry) {
  return entry ? yfSym(entry) : '';
}

function scopeLabel() {
  if (wlScope === 'all') return 'All Watchlists';
  const match = wlWatchlists.find(wl => wl.id === wlScope);
  return match?.name || titleizeWatchlist(wlScope);
}

function scopedStocks() {
  return wlScope === 'all'
    ? wlAllStocks
    : wlAllStocks.filter(s => s._watchlistId === wlScope);
}

// ── Global state ─────────────────────────────────────────────────────────────
let wlAllStocks = [];   // all watchlist entries (including REMOVED)
let wlWatchlists = [];  // watchlist metadata for scope switcher
let wlPrices = {};      // yf symbol -> { price, change_pct }
let wlScope = 'all';    // selected watchlist id | all
let wlFilter = 'all';   // all | IN | US | zone | stop | signal
let wlSearch = '';
let _currentStock = null; // ticker of stock currently in detail view
let _currentWatchlistId = '';

// ── Navigation ───────────────────────────────────────────────────────────────
function navigate(page, opts = {}) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const tab = document.querySelector(`.nav-tab[data-page="${page}"]`);
  if (tab) tab.classList.add('active');
  const pg = document.getElementById('page-' + page);
  if (pg) pg.classList.add('active');
  if (page === 'stock' && opts.ticker) {
    _currentStock = opts.ticker;
    _currentWatchlistId = opts.watchlistId || '';
    openStockDetail(opts.ticker, opts.watchlistId || '');
  }
}

// Hash routing
function routeFromHash() {
  const h = location.hash || '#/';
  if (h.startsWith('#/stock/')) {
    const raw = h.slice(8);
    const [tickerPart, query = ''] = raw.split('?');
    const ticker = decodeURIComponent(tickerPart);
    const watchlistId = new URLSearchParams(query).get('wl') || '';
    const stockTab = document.getElementById('tab-stock');
    stockTab.textContent = ticker;
    stockTab.classList.remove('hidden');
    navigate('stock', { ticker, watchlistId });
  } else if (h === '#/track') {
    navigate('track');
  } else {
    navigate('watchlist');
  }
}

window.addEventListener('hashchange', routeFromHash);

document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const page = tab.dataset.page;
    if (page === 'watchlist') location.hash = '#/';
    else if (page === 'track') location.hash = '#/track';
    else if (page === 'stock' && _currentStock) location.hash = '#/stock/' + _currentStock;
  });
});

// ── ProximityBar component ───────────────────────────────────────────────────
function proximityBar(s, price) {
  if (!price || !s.stop_loss || !s.target || !s.entry_zone) {
    return `<span style="color:#555">—</span>`;
  }
  const stop = s.stop_loss, target = s.target;
  const ezLow = s.entry_zone.low, ezHigh = s.entry_zone.high;
  const range = target - stop;
  if (range <= 0) return `<span style="color:#555">—</span>`;

  const toBar = v => Math.min(100, Math.max(0, (v - stop) / range * 100));
  const pricePct = toBar(price);
  const ezLowPct = toBar(ezLow);
  const ezHighPct = toBar(ezHigh);
  const zoneWidth = ezHighPct - ezLowPct;

  // Status
  const inZone = price >= ezLow && price <= ezHigh;
  const nearStop = price <= stop * 1.05;
  const nearZone = !inZone && Math.abs((price - (price < ezLow ? ezLow : ezHigh)) / price * 100) <= 5;

  let labelClass = 'watching', labelText;
  if (inZone) { labelClass = 'in-zone'; labelText = 'In Zone'; }
  else if (nearStop) { labelClass = 'near-stop'; labelText = ((price - stop) / price * 100).toFixed(1) + '% from stop'; }
  else if (nearZone && price < ezLow) { labelClass = 'near-zone'; labelText = ((ezLow - price) / price * 100).toFixed(1) + '% to entry'; }
  else if (price > ezHigh) { const a = ((price - ezHigh) / ezHigh * 100).toFixed(1); labelClass = nearZone ? 'near-zone' : 'watching'; labelText = a + '% above'; }
  else { labelText = ((ezLow - price) / price * 100).toFixed(1) + '% below'; }

  const markerColor = inZone ? '#059669' : nearStop ? '#ef4444' : '#00d4ff';
  const c = curr(s);
  const tip = `Stop: ${c}${stop} | Entry: ${c}${ezLow}–${c}${ezHigh} | Target: ${c}${target}`;

  return `<div class="prox-wrap" data-tip="${tip}">
    <div class="prox-bar">
      <div class="prox-zone" style="left:${ezLowPct}%;width:${zoneWidth}%"></div>
      <div class="prox-marker" style="left:${pricePct}%;background:${markerColor}"></div>
    </div>
    <span class="prox-label ${labelClass}">${labelText}</span>
  </div>`;
}

function proximitySort(s) {
  const p = wlPrices[priceKeyFor(s)];
  if (!p || !s.entry_zone || !s.stop_loss || !s.target) return 99;
  const price = p.price;
  const ezLow = s.entry_zone.low, ezHigh = s.entry_zone.high;
  if (price >= ezLow && price <= ezHigh) return 0;
  if (price <= s.stop_loss * 1.05) return 1;
  const dist = price < ezLow
    ? (ezLow - price) / price * 100
    : (price - ezHigh) / ezHigh * 100;
  return 2 + dist;
}

// ── Signal badge ─────────────────────────────────────────────────────────────
function getSignal(s) {
  const yf = yfSym(s);
  const ta = BAKED?.ta?.[yf] || {};
  const ep = ta.entry_points;
  const sr = ta.stoch_rsi;
  const div = ta.divergence;
  const rsiData = ta.rsi;

  // RSI oversold/overbought
  if (rsiData?.rsi != null) {
    const r = rsiData.rsi;
    if (r < 30) return { label: 'Oversold', cls: 'sig-bull', tip: `RSI: ${r.toFixed(1)} < 30 (oversold)` };
    if (r > 70) return { label: 'Overbought', cls: 'sig-bear', tip: `RSI: ${r.toFixed(1)} > 70 (overbought)` };
  }

  // StochRSI crossover
  if (sr?.crossover === 'bullish_from_oversold')
    return { label: 'StochRSI X', cls: 'sig-bull', tip: `K: ${fmt(sr.stoch_rsi_k,1)} crossed above D: ${fmt(sr.stoch_rsi_d,1)} in oversold zone` };
  if (sr?.crossover === 'bearish_from_overbought')
    return { label: 'StochRSI X', cls: 'sig-bear', tip: `K: ${fmt(sr.stoch_rsi_k,1)} crossed below D: ${fmt(sr.stoch_rsi_d,1)} in overbought zone` };

  // Divergence
  if (div?.rsi_divergence?.detected && div?.overall_bias === 'bullish')
    return { label: 'Bull Div', cls: 'sig-bull', tip: `Bullish RSI divergence, confidence: ${div.confidence_pct}%` };
  if (div?.macd_divergence?.detected && div?.overall_bias === 'bearish')
    return { label: 'Bear Div', cls: 'sig-bear', tip: `Bearish MACD divergence` };

  // Entry recommendation
  if (ep?.entry_recommendation === 'strong_buy' || ep?.entry_recommendation === 'buy')
    return { label: ep.verdict, cls: 'sig-bull', tip: `${ep.signal_counts?.bullish || 0} bullish / ${ep.signal_counts?.bearish || 0} bearish` };
  if (ep?.entry_recommendation === 'avoid_entry' || ep?.entry_recommendation === 'avoid_long_entry')
    return { label: 'Avoid', cls: 'sig-bear', tip: `${ep.signal_counts?.bullish || 0} bullish / ${ep.signal_counts?.bearish || 0} bearish` };

  return null;
}

function signalBadge(sig) {
  if (!sig) return `<span class="sig sig-none">—</span>`;
  return `<span class="sig ${sig.cls}" data-tip="${sig.tip}">${sig.label}</span>`;
}

// ── RSI display for watchlist ────────────────────────────────────────────────
function getRsiDisplay(s) {
  const yf = yfSym(s);
  const ta = BAKED?.ta?.[yf] || {};

  // Try ta.rsi first, fall back to entry_points
  if (ta.rsi?.rsi != null) {
    const r = ta.rsi.rsi;
    const sig = ta.rsi.signal || '';
    const cls = r < 30 ? 'bullish' : r > 70 ? 'bearish' : 'neutral-val';
    return `<span class="${cls}" data-tip="RSI: ${r.toFixed(1)} — oversold<30, overbought>70">${r.toFixed(0)}</span> <span style="color:#555;font-size:11px">${sig}</span>`;
  }
  if (ta.entry_points?.indicators?.rsi != null) {
    const r = ta.entry_points.indicators.rsi;
    const cls = r < 30 ? 'bullish' : r > 70 ? 'bearish' : 'neutral-val';
    return `<span class="${cls}" data-tip="RSI: ${r.toFixed(1)} — oversold<30, overbought>70">${r.toFixed(0)}</span>`;
  }
  return '<span style="color:#555">—</span>';
}

// ── Trend display ────────────────────────────────────────────────────────────
function getTrend(s) {
  const yf = yfSym(s);
  const ta = BAKED?.ta?.[yf] || {};
  if (ta.sma_stack) {
    const st = ta.sma_stack;
    const type = st.stack_type || '';
    if (type.includes('perfect_bullish') || type.includes('bullish')) {
      return `<span class="bullish" data-tip="SMA20: ${fmt(st.sma20)} / SMA50: ${fmt(st.sma50)} / SMA200: ${fmt(st.sma200)}">Bullish</span>`;
    }
    if (type.includes('perfect_bearish') || type.includes('bearish')) {
      return `<span class="bearish" data-tip="SMA20: ${fmt(st.sma20)} / SMA50: ${fmt(st.sma50)} / SMA200: ${fmt(st.sma200)}">Bearish</span>`;
    }
    return `<span style="color:#f59e0b" data-tip="SMA20: ${fmt(st.sma20)} / SMA50: ${fmt(st.sma50)} / SMA200: ${fmt(st.sma200)}">Mixed</span>`;
  }
  // Fallback: use entry_points SMA signals
  const ep = ta.entry_points;
  if (ep?.signals) {
    const smaSig = ep.signals.find(s => s.indicator === 'SMA_Stack');
    if (smaSig) {
      const isBull = smaSig.bias === 'bullish';
      return `<span class="${isBull ? 'bullish' : 'bearish'}">${isBull ? 'Bullish' : 'Bearish'}</span>`;
    }
  }
  return '<span style="color:#555">—</span>';
}

// ── Filter logic ─────────────────────────────────────────────────────────────
function passesFilter(s) {
  if (s.status === 'REMOVED') return false;
  if (wlScope !== 'all' && s._watchlistId !== wlScope) return false;
  const p = wlPrices[priceKeyFor(s)];
  if (wlFilter === 'IN' && s.market !== 'IN') return false;
  if (wlFilter === 'US' && s.market !== 'US') return false;
  if (wlFilter === 'zone') {
    if (!p || !s.entry_zone) return false;
    if (!(p.price >= s.entry_zone.low && p.price <= s.entry_zone.high)) return false;
  }
  if (wlFilter === 'stop') {
    if (!p || !s.stop_loss) return false;
    if (!(p.price <= s.stop_loss * 1.05)) return false;
  }
  if (wlFilter === 'signal') {
    if (!getSignal(s)) return false;
  }
  if (wlSearch) {
    const q = wlSearch.toLowerCase();
    if (
      !s.ticker.toLowerCase().includes(q) &&
      !(s.company_name || '').toLowerCase().includes(q) &&
      !(s._watchlistName || '').toLowerCase().includes(q)
    ) return false;
  }
  return true;
}

// ── Watchlist scope ───────────────────────────────────────────────────────────
function renderWatchlistScope() {
  const mount = document.getElementById('watchlistScope');
  if (!mount) return;

  const totalActive = wlAllStocks.filter(s => s.status !== 'REMOVED').length;
  const scopedActive = scopedStocks().filter(s => s.status !== 'REMOVED').length;
  const chips = [
    `<button class="scope-chip ${wlScope === 'all' ? 'active' : ''}" data-scope="all">
      <span class="scope-chip-label">All Watchlists</span>
      <span class="scope-chip-count">${totalActive}</span>
    </button>`,
    ...wlWatchlists.map(wl => `
      <button class="scope-chip ${wlScope === wl.id ? 'active' : ''}" data-scope="${wl.id}">
        <span class="scope-chip-label">${wl.name}</span>
        <span class="scope-chip-count">${wl.activeCount}</span>
      </button>
    `),
  ].join('');

  mount.innerHTML = `
    <div class="wl-scope-head">
      <div>
        <div class="wl-scope-kicker">Watchlist View</div>
        <div class="wl-scope-title">${scopeLabel()}</div>
      </div>
      <div class="wl-scope-meta">${wlScope === 'all'
        ? `${wlWatchlists.length} lists • ${totalActive} active entries`
        : `${scopedActive} active entries`}</div>
    </div>
    <div class="wl-scope-chips">${chips}</div>
  `;

  mount.querySelectorAll('[data-scope]').forEach(btn => {
    btn.addEventListener('click', () => {
      wlScope = btn.dataset.scope || 'all';
      renderWatchlistScope();
      renderAttnCards();
      renderWatchlist();
    });
  });
}

// ── Attention cards ───────────────────────────────────────────────────────────
function renderAttnCards() {
  const active = scopedStocks().filter(s => s.status !== 'REMOVED');
  let inZone = [], nearStop = [], hasSig = [];
  for (const s of active) {
    const p = wlPrices[priceKeyFor(s)];
    if (p && s.entry_zone && p.price >= s.entry_zone.low && p.price <= s.entry_zone.high) inZone.push(s.ticker);
    if (p && s.stop_loss && p.price <= s.stop_loss * 1.05) nearStop.push(s.ticker);
    if (getSignal(s)) hasSig.push(s.ticker);
  }
  const india = active.filter(s => s.market === 'IN');
  const us = active.filter(s => s.market === 'US');

  document.getElementById('attnCards').innerHTML = `
    <div class="attn-card ac-zone" data-attn="zone">
      <div class="ac-label">In Entry Zone</div>
      <div class="ac-value">${inZone.length}</div>
      <div class="ac-sub">${inZone.slice(0, 3).join(', ') || 'none'}</div>
    </div>
    <div class="attn-card ac-stop" data-attn="stop">
      <div class="ac-label">Near Stop Loss</div>
      <div class="ac-value">${nearStop.length}</div>
      <div class="ac-sub">${nearStop.slice(0, 3).join(', ') || 'none'}</div>
    </div>
    <div class="attn-card ac-signal" data-attn="signal">
      <div class="ac-label">Has Signal</div>
      <div class="ac-value">${hasSig.length}</div>
      <div class="ac-sub">${hasSig.slice(0, 3).join(', ') || 'none'}</div>
    </div>
    <div class="attn-card ac-watching" data-attn="all">
      <div class="ac-label">Watching</div>
      <div class="ac-value">${active.length}</div>
      <div class="ac-sub">${scopeLabel()} · IN: ${india.length}  US: ${us.length}</div>
    </div>
  `;

  document.querySelectorAll('.attn-card').forEach(card => {
    card.addEventListener('click', () => {
      const flt = card.dataset.attn;
      document.querySelectorAll('.flt').forEach(b => b.classList.remove('active'));
      document.querySelector(`.flt[data-flt="${flt}"]`)?.classList.add('active');
      wlFilter = flt;
      renderWatchlist();
    });
  });
}

// ── Watchlist table ───────────────────────────────────────────────────────────
function renderWatchlist() {
  const body = document.getElementById('wlBody');
  const empty = document.getElementById('wlEmpty');
  const filtered = wlAllStocks.filter(passesFilter);

  if (!filtered.length) {
    empty.querySelector('h3').textContent = scopeLabel();
    empty.querySelector('p').textContent = wlScope === 'all'
      ? 'No stocks on any watchlist yet.'
      : `No active stocks on ${scopeLabel()} yet.`;
    empty.style.display = 'block';
    document.getElementById('wlTable').style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  document.getElementById('wlTable').style.display = '';

  // Sort by proximity
  const sorted = filtered.slice().sort((a, b) => proximitySort(a) - proximitySort(b));

  // Group
  const inZoneGroup = sorted.filter(s => {
    const p = wlPrices[priceKeyFor(s)];
    return p && s.entry_zone && p.price >= s.entry_zone.low && p.price <= s.entry_zone.high;
  });
  const attnGroup = sorted.filter(s => {
    const p = wlPrices[priceKeyFor(s)];
    if (inZoneGroup.includes(s)) return false;
    return (p && s.stop_loss && p.price <= s.stop_loss * 1.05) || (getSignal(s)?.cls === 'sig-bear');
  });
  const watchGroup = sorted.filter(s => !inZoneGroup.includes(s) && !attnGroup.includes(s));

  let html = '';
  function addSection(label, items) {
    if (!items.length) return;
    html += `<tr class="section-header"><td colspan="9">${label}</td></tr>`;
    for (const s of items) html += buildRow(s);
  }

  addSection('In Entry Zone', inZoneGroup);
  addSection('Needs Attention', attnGroup);
  addSection('Watching', watchGroup);

  body.innerHTML = html;

  // Click rows → stock detail
  body.querySelectorAll('tr[data-ticker]').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => {
      const ticker = row.dataset.ticker;
      const watchlistId = row.dataset.watchlistId || '';
      const stockTab = document.getElementById('tab-stock');
      stockTab.textContent = ticker;
      stockTab.classList.remove('hidden');
      location.hash = '#/stock/' + encodeURIComponent(ticker) + (watchlistId ? `?wl=${encodeURIComponent(watchlistId)}` : '');
    });
  });
}

function buildRow(s) {
  const p = wlPrices[priceKeyFor(s)];
  const price = p?.price;
  const c = curr(s);

  // Price cell
  const priceCell = price != null
    ? `<span style="font-weight:600">${c}${price.toLocaleString()}</span>
       ${p.change_pct != null ? `<br><span class="${p.change_pct >= 0 ? 'pos' : 'neg'}" style="font-size:11px">${p.change_pct >= 0 ? '+' : ''}${p.change_pct.toFixed(2)}%</span>` : ''}`
    : '—';

  // Since Add
  const sinceAdd = price != null && s.price_at_add
    ? ((price - s.price_at_add) / s.price_at_add * 100)
    : null;
  const sinceAddCell = sinceAdd != null
    ? `<span class="${sinceAdd >= 0 ? 'pos' : 'neg'}" data-tip="Added at ${c}${s.price_at_add} on ${fmtDate(s.added_at)}">${pct(sinceAdd)}</span>`
    : '—';

  // R:R
  let rr = '—';
  if (price != null && s.stop_loss && s.target) {
    const risk = Math.abs(price - s.stop_loss);
    const reward = Math.abs(s.target - price);
    if (risk > 0) rr = (reward / risk).toFixed(1) + ':1';
  }

  const inZone = price != null && s.entry_zone && price >= s.entry_zone.low && price <= s.entry_zone.high;
  const nearStop = price != null && s.stop_loss && price <= s.stop_loss * 1.05;
  const rowClass = inZone ? 'row-in-zone' : nearStop ? 'row-attention' : '';

  const sig = getSignal(s);
  const sourceTag = wlWatchlists.length > 1
    ? `<span class="wl-source-pill">${s._watchlistName || titleizeWatchlist(s._watchlistId)}</span>`
    : '';
  const metaLine = [s.market, s.company_name].filter(Boolean).join(' · ');

  return `<tr class="${rowClass}" data-ticker="${s.ticker}" data-watchlist-id="${s._watchlistId || ''}">
    <td>
      <span style="font-weight:700">${s.ticker}</span>
      <div class="wl-row-meta">
        <span>${metaLine || '—'}</span>
        ${sourceTag}
      </div>
    </td>
    <td>${priceCell}</td>
    <td>${price != null ? proximityBar(s, price) : '—'}</td>
    <td>${sinceAddCell}</td>
    <td><span data-tip="Score date: ${s.score_date || '—'}">${s.score ?? '—'}</span></td>
    <td>${getRsiDisplay(s)}</td>
    <td>${getTrend(s)}</td>
    <td>${signalBadge(sig)}</td>
    <td>${rr}</td>
  </tr>`;
}

// ── Watchlist data load ───────────────────────────────────────────────────────
async function loadWatchlist() {
  const data = await get('/api/watchlists');
  wlPrices = {};
  wlAllStocks = [];
  wlWatchlists = [];
  if (data) for (const wl of data) {
    const wlId = wl.id || wl.data?.id || 'watchlist';
    const wlName = wl.data?.name || titleizeWatchlist(wlId);
    const entries = (wl.data?.watchlist || []).map((entry, idx) => ({
      ...entry,
      market: entry.market || (String(entry.ticker || '').includes('.') ? 'IN' : 'US'),
      _watchlistId: wlId,
      _watchlistName: wlName,
      _rowKey: `${wlId}:${entry.ticker || idx}:${idx}`,
    }));
    wlWatchlists.push({
      id: wlId,
      name: wlName,
      activeCount: entries.filter(entry => entry.status !== 'REMOVED').length,
    });
    wlAllStocks.push(...entries);
  }
  if (wlScope !== 'all' && !wlWatchlists.some(wl => wl.id === wlScope)) wlScope = 'all';

  // Prices from baked data
  const active = wlAllStocks.filter(s => s.status !== 'REMOVED');
  for (const s of active) {
    const yf = yfSym(s);
    if (BAKED?.prices?.[yf]) wlPrices[yf] = BAKED.prices[yf];
  }

  // If live mode, fetch prices
  if (!BAKED) {
    const yfSymbols = active.map(s => yfSym(s)).join(',');
    const priceData = await get('/api/prices?symbols=' + yfSymbols);
    if (priceData) {
      for (const s of active) {
        const yf = yfSym(s);
        if (priceData[yf]) wlPrices[yf] = priceData[yf];
      }
    }
  }

  renderWatchlistScope();
  renderAttnCards();
  renderWatchlist();
}

// Filter bar
document.querySelectorAll('.flt').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.flt').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    wlFilter = btn.dataset.flt;
    renderWatchlist();
    renderAttnCards();
  });
});

document.getElementById('wlSearch').addEventListener('input', e => {
  wlSearch = e.target.value.trim();
  renderWatchlist();
});

// ── Chart engine (from original) ─────────────────────────────────────────────
let _chart = null, _candleSeries = null, _volumeSeries = null;
let _smaLines = [], _bbLines = [];
let _ohlcvRaw = [];
let _chartRange = 90;
let _overlays = { sma: true, bb: true, vol: false, fib: false, zones: true, rsi: false, stochrsi: false, macd: false, adx: false };
let _currentTA = null;
let _currentWLEntry = null;

function computeSMA(data, period) {
  const result = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j].close;
    result.push({ time: data[i].time, value: +(sum / period).toFixed(2) });
  }
  return result;
}

function computeBB(data, period, mult) {
  const upper = [], lower = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j].close;
    const mean = sum / period;
    let sqSum = 0;
    for (let j = i - period + 1; j <= i; j++) sqSum += (data[j].close - mean) ** 2;
    const std = Math.sqrt(sqSum / period);
    upper.push({ time: data[i].time, value: +(mean + mult * std).toFixed(2) });
    lower.push({ time: data[i].time, value: +(mean - mult * std).toFixed(2) });
  }
  return { upper, lower };
}

function computeEMA(data, period) {
  if (data.length < period) return [];
  const k = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i++) sum += data[i].close;
  const result = [{ time: data[period - 1].time, value: sum / period }];
  for (let i = period; i < data.length; i++) {
    const prev = result[result.length - 1].value;
    result.push({ time: data[i].time, value: prev + k * (data[i].close - prev) });
  }
  return result;
}

function computeRSI(data, period = 14) {
  if (data.length < period + 1) return [];
  const changes = [];
  for (let i = 1; i < data.length; i++) changes.push({ time: data[i].time, change: data[i].close - data[i - 1].close });
  let avgGain = 0, avgLoss = 0;
  for (let i = 0; i < period; i++) {
    if (changes[i].change > 0) avgGain += changes[i].change;
    else avgLoss -= changes[i].change;
  }
  avgGain /= period; avgLoss /= period;
  const result = [{ time: changes[period - 1].time, value: avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2) }];
  for (let i = period; i < changes.length; i++) {
    const g = changes[i].change > 0 ? changes[i].change : 0;
    const l = changes[i].change < 0 ? -changes[i].change : 0;
    avgGain = (avgGain * (period - 1) + g) / period;
    avgLoss = (avgLoss * (period - 1) + l) / period;
    result.push({ time: changes[i].time, value: avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2) });
  }
  return result;
}

function computeMACD(data, fast = 12, slow = 26, signal = 9) {
  const emaFast = computeEMA(data, fast);
  const emaSlow = computeEMA(data, slow);
  const slowMap = {};
  for (const d of emaSlow) slowMap[d.time] = d.value;
  const macdLine = [];
  for (const d of emaFast) {
    if (slowMap[d.time] != null) macdLine.push({ time: d.time, value: +(d.value - slowMap[d.time]).toFixed(4) });
  }
  if (macdLine.length < signal) return { macdLine: [], signalLine: [], histogram: [] };
  const k = 2 / (signal + 1);
  let sum = 0;
  for (let i = 0; i < signal; i++) sum += macdLine[i].value;
  const signalLine = [{ time: macdLine[signal - 1].time, value: +(sum / signal).toFixed(4) }];
  for (let i = signal; i < macdLine.length; i++) {
    const prev = signalLine[signalLine.length - 1].value;
    signalLine.push({ time: macdLine[i].time, value: +(prev + k * (macdLine[i].value - prev)).toFixed(4) });
  }
  const sigMap = {};
  for (const d of signalLine) sigMap[d.time] = d.value;
  const histogram = [];
  for (const d of macdLine) {
    if (sigMap[d.time] != null) {
      const val = +(d.value - sigMap[d.time]).toFixed(4);
      histogram.push({ time: d.time, value: val, color: val >= 0 ? '#05966980' : '#ef444480' });
    }
  }
  return { macdLine, signalLine, histogram };
}

function computeStochRSI(data, rsiPeriod = 14, stochPeriod = 14, kSmooth = 3, dSmooth = 3) {
  const rsi = computeRSI(data, rsiPeriod);
  if (rsi.length < stochPeriod) return { k: [], d: [] };
  const raw = [];
  for (let i = stochPeriod - 1; i < rsi.length; i++) {
    let min = Infinity, max = -Infinity;
    for (let j = i - stochPeriod + 1; j <= i; j++) { min = Math.min(min, rsi[j].value); max = Math.max(max, rsi[j].value); }
    const range = max - min;
    raw.push({ time: rsi[i].time, value: range === 0 ? 50 : +((rsi[i].value - min) / range * 100).toFixed(2) });
  }
  const k = [];
  for (let i = kSmooth - 1; i < raw.length; i++) {
    let sum = 0;
    for (let j = i - kSmooth + 1; j <= i; j++) sum += raw[j].value;
    k.push({ time: raw[i].time, value: +(sum / kSmooth).toFixed(2) });
  }
  const d = [];
  for (let i = dSmooth - 1; i < k.length; i++) {
    let sum = 0;
    for (let j = i - dSmooth + 1; j <= i; j++) sum += k[j].value;
    d.push({ time: k[i].time, value: +(sum / dSmooth).toFixed(2) });
  }
  return { k, d };
}

function computeADX(data, period = 14) {
  if (data.length < period + 1) return { adx: [], plusDI: [], minusDI: [] };
  const tr = [], plusDM = [], minusDM = [];
  for (let i = 1; i < data.length; i++) {
    const high = data[i].high, low = data[i].low, prevClose = data[i-1].close;
    tr.push(Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose)));
    const upMove = data[i].high - data[i-1].high;
    const downMove = data[i-1].low - data[i].low;
    plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
  }
  let atr = 0, aPlusDM = 0, aMinusDM = 0;
  for (let i = 0; i < period; i++) { atr += tr[i]; aPlusDM += plusDM[i]; aMinusDM += minusDM[i]; }
  const plusDI = [], minusDI = [], dx = [];
  function push(i) {
    const pdi = atr === 0 ? 0 : (aPlusDM / atr * 100);
    const mdi = atr === 0 ? 0 : (aMinusDM / atr * 100);
    const sum = pdi + mdi;
    plusDI.push({ time: data[i + 1].time, value: +pdi.toFixed(2) });
    minusDI.push({ time: data[i + 1].time, value: +mdi.toFixed(2) });
    dx.push(sum === 0 ? 0 : Math.abs(pdi - mdi) / sum * 100);
  }
  push(period - 1);
  for (let i = period; i < tr.length; i++) {
    atr = atr - atr / period + tr[i];
    aPlusDM = aPlusDM - aPlusDM / period + plusDM[i];
    aMinusDM = aMinusDM - aMinusDM / period + minusDM[i];
    push(i);
  }
  const adx = [];
  if (dx.length >= period) {
    let adxVal = 0;
    for (let i = 0; i < period; i++) adxVal += dx[i];
    adxVal /= period;
    adx.push({ time: plusDI[period - 1].time, value: +adxVal.toFixed(2) });
    for (let i = period; i < dx.length; i++) {
      adxVal = (adxVal * (period - 1) + dx[i]) / period;
      adx.push({ time: plusDI[i].time, value: +adxVal.toFixed(2) });
    }
  }
  return { adx, plusDI, minusDI };
}

function sliceByRange(data, days) {
  if (!data.length) return data;
  const cutoff = new Date(data[data.length - 1].time);
  cutoff.setDate(cutoff.getDate() - days);
  const cutStr = cutoff.toISOString().slice(0, 10);
  return data.filter(d => d.time >= cutStr);
}

function destroyChart() {
  if (_chart) { _chart.remove(); _chart = null; }
  _candleSeries = null; _volumeSeries = null; _smaLines = []; _bbLines = [];
}

function formatVol(v) {
  if (v >= 1e7) return (v / 1e7).toFixed(1) + 'Cr';
  if (v >= 1e5) return (v / 1e5).toFixed(1) + 'L';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return v;
}

function renderChart() {
  destroyChart();
  const container = document.getElementById('chartContainer');
  const legend = document.getElementById('chartLegend');
  if (legend) legend.innerHTML = '';
  if (!_ohlcvRaw.length) return;

  const data = sliceByRange(_ohlcvRaw, _chartRange);
  if (!data.length) return;

  let subPanes = 0;
  if (_overlays.rsi) subPanes++;
  if (_overlays.stochrsi) subPanes++;
  if (_overlays.macd) subPanes++;
  if (_overlays.adx) subPanes++;
  const chartHeight = 500 + 150 * subPanes;
  container.style.height = chartHeight + 'px';

  _chart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: chartHeight,
    layout: { background: { type: 'solid', color: '#0f0f0f' }, textColor: '#888' },
    grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#1a1a2e' } },
    crosshair: { mode: 0 },
    rightPriceScale: { borderColor: '#2a2a3e' },
    timeScale: { borderColor: '#2a2a3e', timeVisible: false },
  });

  _candleSeries = _chart.addSeries(LightweightCharts.CandlestickSeries, {
    upColor: '#059669', downColor: '#ef4444', borderVisible: false,
    wickUpColor: '#059669', wickDownColor: '#ef4444',
  });
  _candleSeries.setData(data);

  if (_overlays.vol) {
    _volumeSeries = _chart.addSeries(LightweightCharts.HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: 'vol',
    });
    _chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    _volumeSeries.setData(data.map(d => ({
      time: d.time, value: d.volume, color: d.close >= d.open ? '#05966940' : '#ef444440',
    })));
  }

  const smaSeriesMap = {};
  if (_overlays.sma) {
    const colors = ['#00d4ff', '#f59e0b', '#a855f7'];
    [20, 50, 200].forEach((p, i) => {
      const smaData = sliceByRange(computeSMA(_ohlcvRaw, p), _chartRange);
      if (smaData.length) {
        const line = _chart.addSeries(LightweightCharts.LineSeries, { color: colors[i], lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        line.setData(smaData);
        _smaLines.push(line);
        smaSeriesMap[p] = { series: line, color: colors[i] };
      }
    });
  }

  if (_overlays.bb) {
    const bb = computeBB(_ohlcvRaw, 20, 2);
    const upperData = sliceByRange(bb.upper, _chartRange);
    const lowerData = sliceByRange(bb.lower, _chartRange);
    if (upperData.length) {
      const upper = _chart.addSeries(LightweightCharts.LineSeries, { color: '#e879f980', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      upper.setData(upperData);
      const lower = _chart.addSeries(LightweightCharts.LineSeries, { color: '#e879f980', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      lower.setData(lowerData);
      _bbLines.push(upper, lower);
    }
  }

  if (_overlays.fib && _currentTA?.fibonacci) {
    const levels = _currentTA.fibonacci.retracement_levels || _currentTA.fibonacci.levels;
    if (levels) {
      const fibColors = { '0.236': '#94a3b8', '0.382': '#f59e0b', '0.5': '#00d4ff', '0.618': '#a855f7', '0.786': '#94a3b8' };
      for (const [level, price] of Object.entries(levels)) {
        _candleSeries.createPriceLine({ price, color: fibColors[level] || '#555', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: true, title: `Fib ${level}` });
      }
    }
  }

  if (_overlays.zones && _currentWLEntry) {
    const wl = _currentWLEntry;
    if (wl.entry_zone?.low != null) {
      const zoneBase = _chart.addSeries(LightweightCharts.BaselineSeries, {
        baseValue: { type: 'price', price: wl.entry_zone.low },
        topFillColor1: '#05966925', topFillColor2: '#05966915',
        bottomFillColor1: '#05966900', bottomFillColor2: '#05966900',
        topLineColor: '#05966960', bottomLineColor: '#05966900',
        lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      zoneBase.setData(data.map(d => ({ time: d.time, value: wl.entry_zone.high })));
      _candleSeries.createPriceLine({ price: wl.entry_zone.low, color: '#059669', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'Entry Low' });
      _candleSeries.createPriceLine({ price: wl.entry_zone.high, color: '#059669', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'Entry High' });
    }
    if (wl.stop_loss != null) _candleSeries.createPriceLine({ price: wl.stop_loss, color: '#ef4444', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: true, title: 'Stop' });
    if (wl.target != null) _candleSeries.createPriceLine({ price: wl.target, color: '#00d4ff', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: true, title: 'Target' });
  }

  // Pattern + divergence markers
  const markers = [];
  if (_currentTA?.patterns?.patterns) {
    for (const p of (_currentTA.patterns.patterns || [])) {
      const isBull = p.type === 'bullish' || (p.name || '').toLowerCase().match(/bottom|inverse|bull/);
      const t = p.date || data[data.length - 1].time;
      const nearest = data.reduce((best, d) => Math.abs(new Date(d.time) - new Date(t)) < Math.abs(new Date(best.time) - new Date(t)) ? d : best, data[data.length - 1]);
      markers.push({ time: nearest.time, position: isBull ? 'belowBar' : 'aboveBar', color: isBull ? '#059669' : '#ef4444', shape: isBull ? 'arrowUp' : 'arrowDown', text: (p.name || 'Pattern').replace(/^(Potential |Possible )/i, '') });
    }
  }
  if (_currentTA?.divergence?.bullish_divergence?.detected)
    markers.push({ time: data[data.length - 1].time, position: 'belowBar', color: '#059669', shape: 'circle', text: 'Bull Div' });
  if (_currentTA?.divergence?.bearish_divergence?.detected)
    markers.push({ time: data[data.length - 1].time, position: 'aboveBar', color: '#ef4444', shape: 'circle', text: 'Bear Div' });
  if (markers.length) {
    markers.sort((a, b) => a.time < b.time ? -1 : 1);
    _candleSeries.setMarkers(markers);
  }

  let nextPane = 1;
  if (_overlays.rsi) {
    const rsiData = sliceByRange(computeRSI(_ohlcvRaw), _chartRange);
    if (rsiData.length) {
      const rsiSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#a855f7', lineWidth: 2, priceLineVisible: false, lastValueVisible: true, pane: nextPane, priceScaleId: 'rsi' });
      rsiSeries.setData(rsiData);
      rsiSeries.createPriceLine({ price: 70, color: '#ef444460', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false });
      rsiSeries.createPriceLine({ price: 30, color: '#05966960', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false });
      _chart.priceScale('rsi').applyOptions({ scaleMargins: { top: 0.05, bottom: 0.05 }, borderColor: '#2a2a3e' });
      nextPane++;
    }
  }
  if (_overlays.stochrsi) {
    const stoch = computeStochRSI(_ohlcvRaw);
    const kData = sliceByRange(stoch.k, _chartRange);
    const dData = sliceByRange(stoch.d, _chartRange);
    if (kData.length) {
      const kSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#f472b6', lineWidth: 2, priceLineVisible: false, lastValueVisible: true, pane: nextPane, priceScaleId: 'stochrsi' });
      kSeries.setData(kData);
      const dSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#818cf8', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, pane: nextPane, priceScaleId: 'stochrsi' });
      dSeries.setData(dData);
      kSeries.createPriceLine({ price: 80, color: '#ef444460', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false });
      kSeries.createPriceLine({ price: 20, color: '#05966960', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false });
      _chart.priceScale('stochrsi').applyOptions({ scaleMargins: { top: 0.05, bottom: 0.05 }, borderColor: '#2a2a3e' });
      nextPane++;
    }
  }
  if (_overlays.macd) {
    const macd = computeMACD(_ohlcvRaw);
    const macdSliced = sliceByRange(macd.macdLine, _chartRange);
    if (macdSliced.length) {
      const macdSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#00d4ff', lineWidth: 2, priceLineVisible: false, lastValueVisible: true, pane: nextPane, priceScaleId: 'macd' });
      macdSeries.setData(macdSliced);
      const sigSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, pane: nextPane, priceScaleId: 'macd' });
      sigSeries.setData(sliceByRange(macd.signalLine, _chartRange));
      const histSeries = _chart.addSeries(LightweightCharts.HistogramSeries, { priceLineVisible: false, lastValueVisible: false, pane: nextPane, priceScaleId: 'macd' });
      histSeries.setData(sliceByRange(macd.histogram, _chartRange));
      macdSeries.createPriceLine({ price: 0, color: '#555', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: false });
      _chart.priceScale('macd').applyOptions({ scaleMargins: { top: 0.05, bottom: 0.05 }, borderColor: '#2a2a3e' });
      nextPane++;
    }
  }
  if (_overlays.adx) {
    const adxData = computeADX(_ohlcvRaw);
    const adxSliced = sliceByRange(adxData.adx, _chartRange);
    if (adxSliced.length) {
      const adxSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#fb923c', lineWidth: 2, priceLineVisible: false, lastValueVisible: true, pane: nextPane, priceScaleId: 'adx' });
      adxSeries.setData(adxSliced);
      const pdiSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#059669', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, pane: nextPane, priceScaleId: 'adx' });
      pdiSeries.setData(sliceByRange(adxData.plusDI, _chartRange));
      const mdiSeries = _chart.addSeries(LightweightCharts.LineSeries, { color: '#ef4444', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, pane: nextPane, priceScaleId: 'adx' });
      mdiSeries.setData(sliceByRange(adxData.minusDI, _chartRange));
      adxSeries.createPriceLine({ price: 25, color: '#fb923c40', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false });
      _chart.priceScale('adx').applyOptions({ scaleMargins: { top: 0.05, bottom: 0.05 }, borderColor: '#2a2a3e' });
      nextPane++;
    }
  }

  _chart.timeScale().fitContent();

  // Crosshair legend
  if (legend) {
    const sym = _currentStock || '';
    const lastD = data[data.length - 1];
    const cc = lastD.close >= lastD.open ? '#059669' : '#ef4444';
    const cp = lastD.open ? ((lastD.close - lastD.open) / lastD.open * 100).toFixed(2) : '0.00';
    legend.innerHTML = `<div class="leg-row"><span class="leg-sym">${sym}</span> <span class="leg-o">O</span> ${lastD.open.toFixed(2)} <span class="leg-h">H</span> ${lastD.high.toFixed(2)} <span class="leg-l">L</span> ${lastD.low.toFixed(2)} <span class="leg-c" style="color:${cc}">C ${lastD.close.toFixed(2)} (${cp}%)</span></div>`;

    _chart.subscribeCrosshairMove(param => {
      if (!param?.time) {
        const d = data[data.length - 1];
        const c = d.close >= d.open ? '#059669' : '#ef4444';
        const p = d.open ? ((d.close - d.open) / d.open * 100).toFixed(2) : '0.00';
        legend.innerHTML = `<div class="leg-row"><span class="leg-sym">${sym}</span> <span class="leg-o">O</span> ${d.open.toFixed(2)} <span class="leg-h">H</span> ${d.high.toFixed(2)} <span class="leg-l">L</span> ${d.low.toFixed(2)} <span class="leg-c" style="color:${c}">C ${d.close.toFixed(2)} (${p}%)</span></div>`;
        return;
      }
      const candleData = param.seriesData?.get(_candleSeries);
      if (!candleData) return;
      const d = candleData;
      const c = d.close >= d.open ? '#059669' : '#ef4444';
      const p = d.open ? ((d.close - d.open) / d.open * 100).toFixed(2) : '0.00';
      let html = `<div class="leg-row"><span class="leg-sym">${sym}</span> <span class="leg-o">O</span> ${d.open.toFixed(2)} <span class="leg-h">H</span> ${d.high.toFixed(2)} <span class="leg-l">L</span> ${d.low.toFixed(2)} <span class="leg-c" style="color:${c}">C ${d.close.toFixed(2)} (${p}%)</span>`;
      if (_volumeSeries) { const vd = param.seriesData?.get(_volumeSeries); if (vd) html += ` <span class="leg-vol">Vol ${formatVol(vd.value)}</span>`; }
      html += '</div>';
      if (_overlays.sma && Object.keys(smaSeriesMap).length) {
        let smaHtml = '<div class="leg-row leg-sma">';
        for (const [p2, obj] of Object.entries(smaSeriesMap)) {
          const sv = param.seriesData?.get(obj.series);
          if (sv?.value != null) smaHtml += `<span style="color:${obj.color}">SMA${p2} ${sv.value.toFixed(2)}</span> `;
        }
        smaHtml += '</div>';
        html += smaHtml;
      }
      legend.innerHTML = html;
    });
  }

  const ro = new ResizeObserver(() => { if (_chart) _chart.applyOptions({ width: container.clientWidth }); });
  ro.observe(container);
}

// Chart controls
document.querySelectorAll('[data-range]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-range]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    _chartRange = parseInt(btn.dataset.range);
    renderChart();
  });
});

document.querySelectorAll('.overlay-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.classList.contains('btn-disabled')) return;
    const key = btn.dataset.overlay;
    _overlays[key] = !_overlays[key];
    btn.classList.toggle('active', _overlays[key]);
    renderChart();
  });
});

// ── Gauge bar ─────────────────────────────────────────────────────────────────
function gaugeBar(value, zones, min = 0, max = 100, labels = []) {
  // zones: [{min, max, color, label}]
  if (value == null) return '';
  const pct = Math.min(100, Math.max(0, (value - min) / (max - min) * 100));
  const segs = zones.map(z => {
    const w = (Math.min(z.max, max) - Math.max(z.min, min)) / (max - min) * 100;
    return `<div class="gauge-zone" style="flex:${w};background:${z.color}25;border-right:1px solid #0f0f0f15"></div>`;
  }).join('');
  const lbls = labels.map((l, i) => `<span>${l}</span>`).join('');
  return `<div class="gauge-wrap">
    <div class="gauge-track">${segs}</div>
    <div class="gauge-marker-row"><div class="gauge-dot" style="left:${pct}%"></div></div>
    <div class="gauge-labels">${lbls}</div>
  </div>`;
}

// ── Indicator cards (stock detail) ───────────────────────────────────────────
function renderIndicatorCard(name, data) {
  if (!data || typeof data !== 'object') return '';

  const sig = data.signal || data.overall_signal || data.overall_bias;
  const sigColor = sig === 'bullish' || sig === 'strong_buy' ? '#059669' : sig === 'bearish' || sig === 'strong_sell' ? '#ef4444' : '#f59e0b';
  const sigBg = sig === 'bullish' || sig === 'strong_buy' ? '#05966920' : sig === 'bearish' || sig === 'strong_sell' ? '#ef444420' : '#f59e0b20';

  const titles = { rsi: 'RSI', macd: 'MACD', stoch_rsi: 'StochRSI', adx: 'ADX', bollinger: 'Bollinger', volume: 'Volume', sma_stack: 'SMA Stack', divergence: 'Divergence', patterns: 'Patterns', fibonacci: 'Fibonacci', entry_points: 'Entry Points' };

  let body = '';

  if (name === 'rsi') {
    body = `<div class="ind-primary" style="color:${data.rsi < 30 ? '#059669' : data.rsi > 70 ? '#ef4444' : '#e0e0e0'}">${fmt(data.rsi, 1)}</div>
      ${gaugeBar(data.rsi, [{min:0,max:30,color:'#059669'},{min:30,max:70,color:'#f59e0b'},{min:70,max:100,color:'#ef4444'}], 0, 100, ['0','30','70','100'])}
      <div class="ind-row"><span class="label">Signal</span><span class="value ${data.signal}">${data.signal || '—'}</span></div>
      <div class="ind-row"><span class="label">Trend</span><span class="value">${data.trend || '—'}</span></div>
      <div class="ind-row"><span class="label">Previous</span><span class="value">${fmt(data.rsi_prev, 1)}</span></div>
      <div class="ind-row"><span class="label">5d ago</span><span class="value">${fmt(data.rsi_5d_ago, 1)}</span></div>`;
  } else if (name === 'macd') {
    const hist = data.macd_histogram ?? data.histogram;
    body = `<div class="ind-row"><span class="label">MACD</span><span class="value">${fmt(data.macd)}</span></div>
      <div class="ind-row"><span class="label">Signal</span><span class="value">${fmt(data.macd_signal ?? data.signal_line)}</span></div>
      <div class="ind-row"><span class="label">Histogram</span><span class="value ${hist > 0 ? 'bullish' : 'bearish'}">${hist > 0 ? '+' : ''}${fmt(hist)}</span></div>
      <div class="ind-row"><span class="label">Crossover</span><span class="value">${data.crossover || data.signal || '—'}</span></div>
      <div class="ind-row"><span class="label">Trend</span><span class="value">${data.trend || '—'}</span></div>`;
  } else if (name === 'stoch_rsi') {
    body = `<div class="ind-primary">${fmt(data.stoch_rsi_k, 1)} <span style="color:#818cf8;font-size:14px">/ ${fmt(data.stoch_rsi_d, 1)}</span></div>
      ${gaugeBar(data.stoch_rsi_k, [{min:0,max:20,color:'#059669'},{min:20,max:80,color:'#f59e0b'},{min:80,max:100,color:'#ef4444'}], 0, 100, ['0','20 (K)','80','100'])}
      <div class="ind-row"><span class="label">Zone</span><span class="value">${data.zone || '—'}</span></div>
      <div class="ind-row"><span class="label">Crossover</span><span class="value">${data.crossover || '—'}</span></div>
      <div class="ind-row"><span class="label">Momentum</span><span class="value">${data.momentum || '—'}</span></div>`;
  } else if (name === 'adx') {
    body = `<div class="ind-primary">${fmt(data.adx, 1)}</div>
      ${gaugeBar(data.adx, [{min:0,max:20,color:'#94a3b8'},{min:20,max:25,color:'#f59e0b'},{min:25,max:100,color:'#059669'}], 0, 60, ['0','20','25','60'])}
      <div class="ind-row"><span class="label">+DI</span><span class="value bullish">${fmt(data.plus_di, 1)}</span></div>
      <div class="ind-row"><span class="label">-DI</span><span class="value bearish">${fmt(data.minus_di, 1)}</span></div>
      <div class="ind-row"><span class="label">Trend strength</span><span class="value">${data.trend_strength || data.signal || '—'}</span></div>
      <div class="ind-row"><span class="label">Direction</span><span class="value">${data.trend_direction || '—'}</span></div>`;
  } else if (name === 'bollinger') {
    const pctb = data.percent_b ?? data.pct_b;
    body = `<div class="ind-row"><span class="label">%B</span><span class="value" data-tip="<0 = below lower band, >1 = above upper band">${fmt(pctb)}</span></div>
      <div class="ind-row"><span class="label">Upper</span><span class="value">${fmt(data.upper_band)}</span></div>
      <div class="ind-row"><span class="label">Middle</span><span class="value">${fmt(data.middle_band)}</span></div>
      <div class="ind-row"><span class="label">Lower</span><span class="value">${fmt(data.lower_band)}</span></div>
      <div class="ind-row"><span class="label">Position</span><span class="value">${data.position || data.signal || '—'}</span></div>`;
  } else if (name === 'volume') {
    body = `<div class="ind-primary">${fmt(data.volume_ratio, 2)}<span style="font-size:14px;color:#888">x</span></div>
      <div class="ind-row"><span class="label">vs 20d avg</span><span class="value ${data.volume_ratio > 2 ? 'bullish' : ''}">${data.volume_ratio > 2 ? 'High spike' : data.volume_ratio > 1 ? 'Above avg' : 'Below avg'}</span></div>
      <div class="ind-row"><span class="label">Signal</span><span class="value">${data.signal || '—'}</span></div>
      <div class="ind-row"><span class="label">Spike threshold</span><span class="value" style="color:#555">2.0x</span></div>`;
  } else if (name === 'sma_stack') {
    body = `<div class="ind-row"><span class="label">SMA20</span><span class="value">${fmt(data.sma20)}</span></div>
      <div class="ind-row"><span class="label">SMA50</span><span class="value">${fmt(data.sma50)}</span></div>
      <div class="ind-row"><span class="label">SMA200</span><span class="value">${fmt(data.sma200)}</span></div>
      <div class="ind-row"><span class="label">Alignment</span><span class="value ${data.stack_bullish ? 'bullish' : data.stack_bearish ? 'bearish' : ''}">${data.stack_type || '—'}</span></div>
      <div class="ind-row"><span class="label">vs SMA20</span><span class="value">${fmt(data.distance_from_sma20_pct, 1)}%</span></div>`;
  } else if (name === 'divergence') {
    const bd = data.bullish_divergence?.detected || (data.bullish_divergences > 0);
    const bearD = data.bearish_divergence?.detected || (data.bearish_divergences > 0);
    body = `<div style="display:flex;gap:8px;margin-bottom:10px">
      <div style="flex:1;background:${bd?'#05966920':'#0f0f0f'};border:1px solid ${bd?'#059669':'#2a2a3e'};border-radius:6px;padding:8px;text-align:center">
        <div style="font-size:11px;color:${bd?'#059669':'#555'};font-weight:600">BULLISH</div>
        <div style="font-size:20px;color:${bd?'#059669':'#555'}">${bd?'✓':'—'}</div>
      </div>
      <div style="flex:1;background:${bearD?'#ef444420':'#0f0f0f'};border:1px solid ${bearD?'#ef4444':'#2a2a3e'};border-radius:6px;padding:8px;text-align:center">
        <div style="font-size:11px;color:${bearD?'#ef4444':'#555'};font-weight:600">BEARISH</div>
        <div style="font-size:20px;color:${bearD?'#ef4444':'#555'}">${bearD?'✓':'—'}</div>
      </div>
    </div>
    <div class="ind-row"><span class="label">Overall</span><span class="value">${data.overall_signal || data.overall_bias || '—'}</span></div>
    <div class="ind-row"><span class="label">Confidence</span><span class="value">${data.confidence_pct != null ? data.confidence_pct + '%' : '—'}</span></div>`;
  } else if (name === 'patterns') {
    const pats = data.patterns || data.bullish_patterns?.concat(data.bearish_patterns || []) || [];
    const detected = data.patterns_detected || [];
    if (!detected.length && !pats.length) {
      body = `<div style="color:#555;font-size:13px;padding:8px 0">No patterns detected</div>`;
    } else {
      body = detected.map(p => {
        const isBull = p.toLowerCase().includes('bottom') || p.toLowerCase().includes('bull') || p.toLowerCase().includes('inverse');
        return `<div style="padding:4px 0;font-size:13px;color:${isBull ? '#059669' : '#ef4444'}">${p}</div>`;
      }).join('');
    }
  } else {
    // Generic: show key-value rows
    const skip = new Set(['symbol', 'indicator', 'timestamp', 'params', 'thresholds', 'signal', 'interpretation']);
    body = Object.entries(data)
      .filter(([k, v]) => !skip.has(k) && typeof v !== 'object')
      .map(([k, v]) => {
        const numV = parseFloat(v);
        const display = !isNaN(numV) ? numV.toFixed(2) : String(v);
        const cls = String(v).toLowerCase().includes('bull') ? 'bullish' : String(v).toLowerCase().includes('bear') ? 'bearish' : '';
        return `<div class="ind-row"><span class="label">${k.replace(/_/g, ' ')}</span><span class="value ${cls}">${display}</span></div>`;
      }).join('');
  }

  return `<div class="ind-card">
    <div class="ind-card-header">
      <div class="ind-title">${titles[name] || name.toUpperCase()}</div>
      ${sig ? `<span style="background:${sigBg};color:${sigColor};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700">${sig}</span>` : ''}
    </div>
    ${body}
  </div>`;
}

// ── Entry Analysis card ───────────────────────────────────────────────────────
function renderEntryCard(ep, wlEntry) {
  if (!ep) return '';
  const c = wlEntry ? curr(wlEntry) : '$';
  const verdictColor = ep.verdict?.includes('BULLISH') ? '#059669' : ep.verdict?.includes('BEARISH') ? '#ef4444' : '#f59e0b';

  const biasIcon = bias => bias === 'bullish' ? '<span style="color:#059669">✓</span>' : '<span style="color:#ef4444">✗</span>';

  const sigRows = (ep.signals || []).map(s => {
    const isBull = s.bias === 'bullish';
    return `<div class="entry-sig-row" style="border-left:2px solid ${isBull ? '#059669' : '#ef4444'}">
      ${biasIcon(s.bias)}
      <span class="es-ind">${s.indicator}</span>
      <span class="es-detail">${s.signal?.replace(/_/g, ' ')}${s.value != null ? ` (${fmt(s.value, 2)})` : ''}</span>
      <span class="es-bias ${isBull ? 'bullish' : 'bearish'}">${s.bias}</span>
    </div>`;
  }).join('');

  // Entry levels / stop / targets
  let levelsHtml = '';
  if (ep.stop_losses?.atr_2x) {
    const sl = ep.stop_losses.atr_2x;
    levelsHtml += `<div class="entry-level-box"><div class="el-label">Stop (ATR 2x)</div><div class="el-value" style="color:#ef4444">${c}${sl.price?.toFixed(0) || '—'}</div><div class="el-sub">Risk: ${fmt(sl.risk_pct, 1)}%</div></div>`;
  }
  if (ep.targets?.T1) {
    const t1 = ep.targets.T1;
    const rr1 = ep.risk_reward?.T1?.ratio;
    levelsHtml += `<div class="entry-level-box"><div class="el-label">T1</div><div class="el-value" style="color:#059669">${c}${t1.price?.toFixed(0) || '—'}</div><div class="el-sub">+${fmt(t1.gain_pct, 1)}%${rr1 ? ` · R:R ${rr1}` : ''}</div></div>`;
  }
  if (ep.targets?.T2) {
    const t2 = ep.targets.T2;
    const rr2 = ep.risk_reward?.T2?.ratio;
    levelsHtml += `<div class="entry-level-box"><div class="el-label">T2</div><div class="el-value" style="color:#059669">${c}${t2.price?.toFixed(0) || '—'}</div><div class="el-sub">+${fmt(t2.gain_pct, 1)}%${rr2 ? ` · R:R ${rr2}` : ''}</div></div>`;
  }

  // Fibonacci from entry_points
  let fibHtml = '';
  if (ep.fibonacci_levels) {
    const fl = ep.fibonacci_levels;
    fibHtml = `<div style="margin-top:12px;padding-top:12px;border-top:1px solid #2a2a3e">
      <div style="font-size:11px;color:#555;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Fibonacci</div>
      <div style="font-size:12px;color:#888">Swing H: <span style="color:#ccc">${c}${fl.swing_high?.toFixed(0)}</span> → Swing L: <span style="color:#ccc">${c}${fl.swing_low?.toFixed(0)}</span></div>
      <div style="font-size:12px;color:#888;margin-top:4px">38.2%: ${c}${fl['fib_38.2%']?.toFixed(0)} · 50%: ${c}${fl['fib_50%']?.toFixed(0)} · 61.8%: ${c}${fl['fib_61.8%']?.toFixed(0)}</div>
    </div>`;
  }

  return `<div class="entry-card">
    <h3>Entry Analysis</h3>
    <div class="entry-verdict" style="color:${verdictColor}">${ep.verdict || '—'}</div>
    <div class="entry-rec" style="color:#888">${ep.entry_recommendation?.replace(/_/g, ' ') || ''} — ${ep.signal_counts?.bullish || 0} bullish / ${ep.signal_counts?.bearish || 0} bearish</div>
    <div class="entry-signals">${sigRows}</div>
    <div class="entry-levels">${levelsHtml}</div>
    ${fibHtml}
  </div>`;
}

// ── Thesis card ───────────────────────────────────────────────────────────────
function renderThesisCard(s, wlEntry) {
  if (!wlEntry) return '';
  const c = curr(wlEntry);
  const addedPrice = wlEntry.price_at_add ? `${c}${wlEntry.price_at_add}` : '—';
  const price = wlPrices[priceKeyFor(wlEntry)]?.price;
  const sinceAdd = price && wlEntry.price_at_add ? ((price - wlEntry.price_at_add) / wlEntry.price_at_add * 100) : null;

  const cats = (wlEntry.catalysts || []).map(c2 => `<li>${c2}</li>`).join('');

  return `<div class="thesis-card">
    <h4>Thesis</h4>
    <div class="thesis-text collapsed" id="thesisText">${wlEntry.thesis || 'No thesis recorded.'}</div>
    <span class="show-more" onclick="this.previousElementSibling.classList.toggle('collapsed');this.textContent=this.textContent==='Show more'?'Show less':'Show more'">Show more</span>
    ${cats ? `<h4>Catalysts</h4><ul class="catalyst-list">${cats}</ul>` : ''}
    <h4>Parameters</h4>
    <div class="param-row"><span class="pl">Entry zone</span><span class="pv">${wlEntry.entry_zone ? `${c}${wlEntry.entry_zone.low}–${wlEntry.entry_zone.high}` : '—'}</span></div>
    <div class="param-row"><span class="pl">Stop loss</span><span class="pv" style="color:#ef4444">${wlEntry.stop_loss ? `${c}${wlEntry.stop_loss}` : '—'}</span></div>
    <div class="param-row"><span class="pl">Target</span><span class="pv" style="color:#059669">${wlEntry.target ? `${c}${wlEntry.target}` : '—'}</span></div>
    <div class="param-row"><span class="pl">Horizon</span><span class="pv">${wlEntry.horizon || '—'}</span></div>
    <div class="param-row"><span class="pl">Added at</span><span class="pv">${addedPrice} · ${fmtDate(wlEntry.added_at)}</span></div>
    ${sinceAdd != null ? `<div class="param-row"><span class="pl">Since add</span><span class="pv ${sinceAdd >= 0 ? 'pos' : 'neg'}">${pct(sinceAdd)}</span></div>` : ''}
    <div class="param-row"><span class="pl">Score</span><span class="pv">${wlEntry.score ?? '—'} <span style="color:#555;font-size:11px">${wlEntry.score_date || ''}</span></span></div>
  </div>`;
}

// ── Stock Detail ──────────────────────────────────────────────────────────────
async function openStockDetail(ticker, watchlistId = '') {
  // Find watchlist entry
  const wlEntry =
    wlAllStocks.find(s => s.ticker === ticker && (!watchlistId || s._watchlistId === watchlistId)) ||
    wlAllStocks.find(s => s.ticker === ticker) ||
    null;
  _currentWLEntry = wlEntry;
  const yf = wlEntry ? yfSym(wlEntry) : ticker;
  const price = wlEntry ? wlPrices[priceKeyFor(wlEntry)] : wlPrices[ticker];

  // Stock header
  const header = document.getElementById('stockHeader');
  const c = wlEntry ? curr(wlEntry) : '$';
  const changeHtml = price?.change_pct != null
    ? `<span class="sh-change ${price.change_pct >= 0 ? 'pos' : 'neg'}">${price.change_pct >= 0 ? '+' : ''}${price.change_pct.toFixed(2)}%</span>`
    : '';
  header.innerHTML = `
    <span class="sh-back" onclick="history.back()">← Back</span>
    <div>
      <div class="sh-sym">${ticker}</div>
      <div class="sh-name">${wlEntry?.company_name || ''} <span class="badge badge-${(wlEntry?.status || '').toLowerCase()}">${wlEntry?.status || ''}</span>${wlEntry?._watchlistName ? ` <span class="wl-source-pill">${wlEntry._watchlistName}</span>` : ''}</div>
    </div>
    ${price ? `<div class="sh-divider"></div><div><div class="sh-price">${c}${price.price.toLocaleString()}</div>${changeHtml}</div>` : ''}
    ${wlEntry?.score ? `<div class="sh-divider"></div><div class="sh-meta-item"><div class="sh-meta-label">Score</div><div class="sh-meta-value" style="color:#00d4ff">${wlEntry.score}</div></div>` : ''}
    ${wlEntry?.added_at ? `<div class="sh-meta-item"><div class="sh-meta-label">Added</div><div class="sh-meta-value" style="font-size:13px">${fmtDate(wlEntry.added_at)}</div></div>` : ''}
  `;

  // Fetch TA
  const taResp = await get(`/api/ta/${encodeURIComponent(yf)}`);
  const taInds = taResp?.indicators || {};
  _currentTA = taInds;

  // Update fib/zones overlay button states
  const fibBtn = document.querySelector('[data-overlay="fib"]');
  const hasFib = !!(taInds.fibonacci?.retracement_levels || taInds.fibonacci?.levels || taInds.entry_points?.fibonacci_levels);
  if (fibBtn) fibBtn.classList.toggle('btn-disabled', !hasFib);

  // Load chart
  _ohlcvRaw = BAKED?.ohlcv?.[yf] || [];
  if (!_ohlcvRaw.length && !BAKED) {
    const d = await fetch(`/api/ohlcv/${yf}`).then(r => r.ok ? r.json() : []).catch(() => []);
    _ohlcvRaw = d;
  }
  if (_ohlcvRaw.length) {
    document.getElementById('chartContainer').style.display = '';
    renderChart();
  } else {
    document.getElementById('chartContainer').style.display = 'none';
  }

  // Render detail content
  const detail = document.getElementById('stockDetail');
  const ep = taInds.entry_points;

  // Indicator grid (exclude entry_points — it gets its own card)
  let gridHtml = '<div class="ind-grid">';
  const gridOrder = ['rsi', 'macd', 'stoch_rsi', 'adx', 'bollinger', 'volume', 'sma_stack', 'divergence', 'patterns'];
  for (const name of gridOrder) {
    if (taInds[name]) gridHtml += renderIndicatorCard(name, taInds[name]);
  }
  gridHtml += '</div>';

  const entryHtml = renderEntryCard(ep, wlEntry);
  const thesisHtml = renderThesisCard(ticker, wlEntry);

  detail.innerHTML = `
    <div class="detail-layout">
      <div>
        ${entryHtml}
        ${gridHtml}
      </div>
      <div>${thesisHtml}</div>
    </div>
  `;
}

// ── Track Record ──────────────────────────────────────────────────────────────
async function loadTrackRecord() {
  const [stats, suggestions, outcomes] = await Promise.all([
    get('/api/suggestions/stats'), get('/api/suggestions'), get('/api/suggestions/outcomes')
  ]);

  const empty = document.getElementById('trackEmpty');
  const trackTab = document.getElementById('tab-track');

  if (!suggestions?.length) {
    empty.style.display = 'block';
    trackTab.classList.add('hidden');
    return;
  }
  trackTab.classList.remove('hidden');
  empty.style.display = 'none';

  // Stats cards
  document.getElementById('trackCards').innerHTML = `
    <div class="card"><div class="card-label">Total</div><div class="card-value">${stats?.total || 0}</div></div>
    <div class="card"><div class="card-label">Win Rate</div><div class="card-value">${stats?.winRate || 0}%</div></div>
    <div class="card"><div class="card-label">Won / Lost</div><div class="card-value" style="color:#059669">${stats?.won || 0}<span style="color:#555"> / </span><span style="color:#ef4444">${stats?.lost || 0}</span></div></div>
    <div class="card"><div class="card-label">Avg P&L</div><div class="card-value ${(stats?.avgPnl || 0) >= 0 ? 'pos' : 'neg'}">${(stats?.avgPnl || 0) > 0 ? '+' : ''}${stats?.avgPnl || 0}%</div></div>
  `;

  // Confidence × Strategy heatmap
  const byConf = stats?.byConfidence || {};
  if (Object.keys(byConf).length) {
    const tiers = Object.keys(byConf);
    let hmHtml = `<div style="font-size:13px;font-weight:600;color:#ccc;margin-bottom:8px">By Confidence</div>
      <div style="display:grid;grid-template-columns:repeat(${tiers.length},1fr);gap:4px">`;
    for (const tier of tiers) {
      const d = byConf[tier];
      const wr = d.winRate || 0;
      const intensity = Math.round(wr / 100 * 50);
      hmHtml += `<div style="background:#059669${intensity.toString(16).padStart(2,'0')};border:1px solid #059669${Math.round(intensity * 1.5).toString(16).padStart(2,'0')};border-radius:6px;padding:10px;text-align:center">
        <div style="font-size:11px;color:#888">${tier}</div>
        <div style="font-size:18px;font-weight:700;color:#e0e0e0">${wr.toFixed(0)}%</div>
        <div style="font-size:11px;color:#555">${d.total} trades</div>
      </div>`;
    }
    hmHtml += '</div>';
    document.getElementById('trackHeatmap').innerHTML = hmHtml;
  }

  // Suggestions table
  const outcomeMap = {};
  if (outcomes) for (const o of outcomes) outcomeMap[o.suggestion_id] = o;
  const tbody = document.querySelector('#sugTable tbody');
  tbody.innerHTML = '';
  for (const s of suggestions.slice().reverse()) {
    const o = outcomeMap[s.id];
    const status = o?.status || 'open';
    const pnl = o?.pnl_pct != null ? `${o.pnl_pct > 0 ? '+' : ''}${o.pnl_pct.toFixed(1)}%` : '—';
    tbody.innerHTML += `<tr>
      <td>${s.ts?.slice(0,10) || '—'}</td>
      <td style="font-weight:600">${s.symbol}</td>
      <td>${s.action}</td>
      <td><span class="badge badge-${(s.confidence||'').toLowerCase()}">${s.confidence || '—'}</span></td>
      <td>${s.score || '—'}</td>
      <td>${s.strategy || '—'}</td>
      <td><span class="badge badge-${status}">${status}</span></td>
      <td class="${o?.pnl_pct > 0 ? 'pos' : o?.pnl_pct < 0 ? 'neg' : ''}">${pnl}</td>
    </tr>`;
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────
if (BAKED) {
  const bakedAt = new Date(BAKED.bakedAt);
  const fmt2 = bakedAt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Calcutta' });
  document.getElementById('lastUpdate').textContent = 'Baked: ' + fmt2 + ' IST';
  document.getElementById('snapshotBadge').style.display = 'inline';
} else {
  document.getElementById('lastUpdate').textContent = 'Live';
  const evtSource = new EventSource('/api/events');
  evtSource.onmessage = () => { loadWatchlist(); loadTrackRecord(); };
}

// Load all data, then route
Promise.all([loadWatchlist(), loadTrackRecord()]).then(() => {
  routeFromHash();
});
