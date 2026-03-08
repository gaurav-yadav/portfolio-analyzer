import express from 'express';
import path from 'path';
import fs from 'fs';
import chokidar from 'chokidar';

const app = express();
const PORT = 3323;
const DATA_DIR = path.resolve(__dirname, '../../data');

// SSE clients
const sseClients: express.Response[] = [];

// Static files
app.use(express.static(path.join(__dirname, '../public')));
app.use('/lib', express.static(path.join(__dirname, '../node_modules/lightweight-charts/dist')));

// --- Helpers ---
function readJsonl(filePath: string): any[] {
  if (!fs.existsSync(filePath)) return [];
  return fs.readFileSync(filePath, 'utf-8')
    .split('\n')
    .filter(l => l.trim())
    .map(l => { try { return JSON.parse(l); } catch { return null; } })
    .filter(Boolean);
}

function readJson(filePath: string): any {
  if (!fs.existsSync(filePath)) return null;
  try { return JSON.parse(fs.readFileSync(filePath, 'utf-8')); } catch { return null; }
}

function listJsonFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => f.endsWith('.json'));
}

// --- API Routes ---

// Technical analysis summaries
app.get('/api/technical', (_req, res) => {
  const dir = path.join(DATA_DIR, 'technical');
  const files = listJsonFiles(dir);
  const results = files.map(f => {
    const data = readJson(path.join(dir, f));
    return { symbol: f.replace('.json', ''), ...data };
  }).filter(Boolean);
  res.json(results);
});

app.get('/api/technical/:symbol', (req, res) => {
  const file = path.join(DATA_DIR, 'technical', `${req.params.symbol}.json`);
  const data = readJson(file);
  if (!data) return res.status(404).json({ error: 'not found' });
  res.json(data);
});

// Individual TA indicators for a symbol
app.get('/api/ta/:symbol', (req, res) => {
  const dir = path.join(DATA_DIR, 'ta');
  if (!fs.existsSync(dir)) return res.json({});
  const prefix = req.params.symbol + '_';
  const files = fs.readdirSync(dir).filter(f => f.startsWith(prefix) && f.endsWith('.json'));
  const indicators: Record<string, any> = {};
  for (const f of files) {
    const name = f.replace(prefix, '').replace('.json', '');
    indicators[name] = readJson(path.join(dir, f));
  }
  res.json({ symbol: req.params.symbol, indicators });
});

// Suggestions
app.get('/api/suggestions', (_req, res) => {
  const ledger = readJsonl(path.join(DATA_DIR, 'suggestions', 'ledger.jsonl'));
  res.json(ledger);
});

app.get('/api/suggestions/outcomes', (_req, res) => {
  const dir = path.join(DATA_DIR, 'suggestions', 'outcomes');
  if (!fs.existsSync(dir)) return res.json([]);
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.jsonl'));
  const all = files.flatMap(f => readJsonl(path.join(dir, f)));
  res.json(all);
});

app.get('/api/suggestions/stats', (_req, res) => {
  const ledger = readJsonl(path.join(DATA_DIR, 'suggestions', 'ledger.jsonl'));
  const outDir = path.join(DATA_DIR, 'suggestions', 'outcomes');
  const outcomes: Record<string, any> = {};
  if (fs.existsSync(outDir)) {
    const files = fs.readdirSync(outDir).filter(f => f.endsWith('.jsonl'));
    for (const f of files) {
      for (const o of readJsonl(path.join(outDir, f))) {
        outcomes[o.suggestion_id] = o;
      }
    }
  }

  const total = ledger.length;
  const resolved = Object.values(outcomes).filter((o: any) => ['won', 'lost', 'expired'].includes(o.status));
  const won = resolved.filter((o: any) => o.status === 'won').length;
  const lost = resolved.filter((o: any) => o.status === 'lost').length;
  const expired = resolved.filter((o: any) => o.status === 'expired').length;
  const open = total - resolved.length;
  const winRate = resolved.length > 0 ? (won / resolved.length * 100) : 0;
  const avgPnl = resolved.length > 0
    ? resolved.reduce((s: number, o: any) => s + (o.pnl_pct || 0), 0) / resolved.length : 0;

  // By confidence
  const byConfidence: Record<string, any> = {};
  for (const entry of ledger) {
    const conf = entry.confidence || '?';
    if (!byConfidence[conf]) byConfidence[conf] = { total: 0, won: 0, lost: 0, expired: 0, open: 0, pnls: [] };
    byConfidence[conf].total++;
    const o = outcomes[entry.id];
    if (o?.status === 'won') { byConfidence[conf].won++; byConfidence[conf].pnls.push(o.pnl_pct); }
    else if (o?.status === 'lost') { byConfidence[conf].lost++; byConfidence[conf].pnls.push(o.pnl_pct); }
    else if (o?.status === 'expired') { byConfidence[conf].expired++; byConfidence[conf].pnls.push(o.pnl_pct); }
    else byConfidence[conf].open++;
  }
  for (const k of Object.keys(byConfidence)) {
    const b = byConfidence[k];
    const r = b.won + b.lost + b.expired;
    b.winRate = r > 0 ? (b.won / r * 100) : 0;
    b.avgPnl = b.pnls.length > 0 ? b.pnls.reduce((a: number, b: number) => a + b, 0) / b.pnls.length : 0;
    delete b.pnls;
  }

  // By strategy
  const byStrategy: Record<string, any> = {};
  for (const entry of ledger) {
    const strat = entry.strategy || '?';
    if (!byStrategy[strat]) byStrategy[strat] = { total: 0, won: 0, lost: 0, expired: 0, open: 0, pnls: [] };
    byStrategy[strat].total++;
    const o = outcomes[entry.id];
    if (o?.status === 'won') { byStrategy[strat].won++; byStrategy[strat].pnls.push(o.pnl_pct); }
    else if (o?.status === 'lost') { byStrategy[strat].lost++; byStrategy[strat].pnls.push(o.pnl_pct); }
    else if (o?.status === 'expired') { byStrategy[strat].expired++; byStrategy[strat].pnls.push(o.pnl_pct); }
    else byStrategy[strat].open++;
  }
  for (const k of Object.keys(byStrategy)) {
    const b = byStrategy[k];
    const r = b.won + b.lost + b.expired;
    b.winRate = r > 0 ? (b.won / r * 100) : 0;
    b.avgPnl = b.pnls.length > 0 ? b.pnls.reduce((a: number, b: number) => a + b, 0) / b.pnls.length : 0;
    delete b.pnls;
  }

  res.json({ total, won, lost, expired, open, winRate: +winRate.toFixed(1), avgPnl: +avgPnl.toFixed(2), byConfidence, byStrategy });
});

// Prices - batch fetch via yfinance
let priceCache: Record<string, {price: number, change_pct: number, ts: number}> = {};
const PRICE_TTL = 300_000; // 5 min cache

app.get('/api/prices', async (req, res) => {
  const symbols = (req.query.symbols as string || '').split(',').filter(Boolean);
  if (!symbols.length) return res.json({});
  
  // Return cached if fresh
  const now = Date.now();
  const stale = symbols.filter(s => !priceCache[s] || (now - priceCache[s].ts) > PRICE_TTL);
  
  if (stale.length) {
    try {
      const { execSync } = require('child_process');
      const script = `
import yfinance as yf, json, sys
symbols = sys.argv[1].split(',')
data = yf.download(symbols, period='5d', auto_adjust=True, progress=False, group_by='ticker')
result = {}
for s in symbols:
    try:
        df = data[s] if len(symbols) > 1 else data
        if df.empty: continue
        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2]) if len(df) > 1 else price
        change = (price - prev) / prev * 100
        result[s] = {'price': round(price, 2), 'change_pct': round(change, 2)}
    except: pass
print(json.dumps(result))
`;
      const pyResult = execSync(
        `cd ${path.resolve(__dirname, '../..')} && uv run python -c "${script.replace(/"/g, '\\"')}" "${stale.join(',')}"`,
        { timeout: 30000, encoding: 'utf-8' }
      ).trim();
      const prices = JSON.parse(pyResult);
      for (const [sym, data] of Object.entries(prices) as any) {
        priceCache[sym] = { ...data, ts: now };
      }
    } catch (e) {
      console.error('Price fetch error:', e);
    }
  }
  
  const result: Record<string, any> = {};
  for (const s of symbols) {
    if (priceCache[s]) result[s] = priceCache[s];
  }
  res.json(result);
});

// OHLCV data from cached parquet files
const CACHE_DIR = path.resolve(__dirname, '../../cache/ohlcv');
const ohlcvCache: Record<string, { data: any[], ts: number }> = {};
const OHLCV_TTL = 600_000; // 10 min

app.get('/api/ohlcv/:symbol', (req, res) => {
  const symbol = req.params.symbol;
  const parquetFile = path.join(CACHE_DIR, `${symbol}.parquet`);
  if (!fs.existsSync(parquetFile)) return res.status(404).json({ error: 'no OHLCV data' });

  const now = Date.now();
  if (ohlcvCache[symbol] && (now - ohlcvCache[symbol].ts) < OHLCV_TTL) {
    return res.json(ohlcvCache[symbol].data);
  }

  try {
    const { execSync } = require('child_process');
    const script = `
import pandas as pd, json, sys
df = pd.read_parquet(sys.argv[1])
records = []
for idx, row in df.iterrows():
    records.append({
        'time': idx.strftime('%Y-%m-%d'),
        'open': round(float(row['Open']), 2),
        'high': round(float(row['High']), 2),
        'low': round(float(row['Low']), 2),
        'close': round(float(row['Close']), 2),
        'volume': int(row['Volume'])
    })
print(json.dumps(records))
`;
    const result = execSync(
      `cd ${path.resolve(__dirname, '../..')} && uv run python -c "${script.replace(/"/g, '\\"')}" "${parquetFile}"`,
      { timeout: 15000, encoding: 'utf-8' }
    ).trim();
    const data = JSON.parse(result);
    ohlcvCache[symbol] = { data, ts: now };
    res.json(data);
  } catch (e) {
    console.error('OHLCV read error:', e);
    res.status(500).json({ error: 'failed to read OHLCV' });
  }
});

// Portfolios
app.get('/api/portfolios', (_req, res) => {
  const dir = path.join(DATA_DIR, 'portfolios');
  const files = listJsonFiles(dir);
  res.json(files.map(f => ({ id: f.replace('.json', ''), data: readJson(path.join(dir, f)) })));
});

// Watchlists
app.get('/api/watchlists', (_req, res) => {
  const dir = path.join(DATA_DIR, 'watchlists');
  const files = listJsonFiles(dir);
  res.json(files.map(f => ({ id: f.replace('.json', ''), data: readJson(path.join(dir, f)) })));
});

app.get('/api/watchlist/events', (_req, res) => {
  res.json(readJsonl(path.join(DATA_DIR, 'watchlist_events.jsonl')));
});

// SSE
app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.write('data: connected\n\n');
  sseClients.push(res);
  req.on('close', () => {
    const idx = sseClients.indexOf(res);
    if (idx >= 0) sseClients.splice(idx, 1);
  });
});

// Watch data dir for changes
if (fs.existsSync(DATA_DIR)) {
  chokidar.watch(DATA_DIR, { ignoreInitial: true }).on('all', (event, filePath) => {
    const msg = JSON.stringify({ event, file: path.relative(DATA_DIR, filePath), ts: Date.now() });
    for (const client of sseClients) {
      client.write(`data: ${msg}\n\n`);
    }
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Dashboard running at http://localhost:${PORT}`);
});
