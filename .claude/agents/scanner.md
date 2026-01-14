---
name: scanner
description: "Smart scanner: web-search discovery + OHLCV confluence ranking (2w breakout + 2m pullback + reversal)"
---

Run a full scan end-to-end:
1) Web-search discovery (5 scan types, in parallel)
2) Save a scan file under `data/scans/`
3) Enrich + rank candidates using OHLCV-based confluence (no extra web search)

Keep output minimal; write details to the scan JSON.
Confluence rules + schema live in `specs/02-stock-scanner.md` (single source of truth).

## EXECUTION

### 1) Discovery (WebSearch) — run all 5 scans

IMPORTANT: You are running as a single agent. Do NOT ask to launch Task sub-agents.
Run the searches yourself using WebSearch (one per scan type).

If the user specifies a focus (e.g., "India midcaps in construction"), keep the same 5 scan types but bias queries using:
- `site:screener.in` / `site:trendlyne.com` / `site:chartink.com`
- `Nifty Midcap 150` / `midcap` keywords
- sector keywords: `construction`, `realty`, `infra`, `EPC`, `metals`, `steel`, `aluminium`, `copper`
- Prefer extracting NSE symbols from the result pages (not headlines)

### Agent 1: RSI Oversold
Search for stocks with RSI < 30 or recovering from oversold.
Queries:
- "RSI oversold stocks NSE India today"
- "chartink RSI below 30 stocks"
- "trendlyne RSI oversold Nifty"

### Agent 2: MACD Bullish Crossover
Search for stocks where MACD line crossed above signal line.
Queries:
- "MACD bullish crossover stocks NSE today"
- "MACD buy signal stocks India"
- "chartink MACD crossover"

### Agent 3: Golden Cross
Search for stocks where SMA50 crossed above SMA200.
Queries:
- "Golden Cross stocks NSE India"
- "SMA 50 crossing SMA 200 stocks"
- "trendlyne golden crossover"

### Agent 4: Volume Breakout
Search for stocks with unusual volume and price breakout.
Queries:
- "volume breakout stocks NSE India today"
- "unusual volume stocks India"
- "price volume breakout NSE"

### Agent 5: 52-Week High
Search for stocks at or near 52-week highs.
Queries:
- "52 week high stocks NSE today"
- "stocks hitting new highs India"
- "NSE all time high stocks"

### 2) Save scan file

Aggregate results and write a single timestamped file:
`data/scans/scan_{YYYYMMDD_HHMMSS}.json`

If you are running multiple sector-focused scans in parallel, use a safe suffix but keep the `scan_` prefix so `validate_scan.py latest` still works:
`data/scans/scan_{YYYYMMDD_HHMMSS}_{sector}.json` (example: `scan_20260114_110714_metals.json`)

Prefer the structured match format (easier to validate + rank), but accept line format.

Structured match (preferred):

```json
{
  "symbol": "DCMSRIND",
  "note": "RSI 15.1 (oversold)",
  "source": "trendlyne",
  "source_url": "https://...",
  "as_of": "2026-01-01"
}
```

Acceptable (line format):
```
SYMBOL - note (indicator value if available) - source

Example:
DCMSRIND - RSI 15.1, extremely oversold - trendlyne
ATMASTCO - RSI 16.5 - groww
YUKENIND - MACD crossed above signal at Rs 1030 - chartink
```

File shape (keep this stable):

```json
{
  "timestamp": "2026-01-01T14:30:00",
  "focus": {
    "country": "india",
    "market_cap": "any",
    "sectors": []
  },
  "scans": {
    "rsi_oversold": {
      "count": 12,
      "matches": [
        {"symbol": "DCMSRIND", "note": "RSI 15.1", "source": "trendlyne", "source_url": "https://...", "as_of": "2026-01-01"}
      ]
    },
    "macd_crossover": { ... },
    "golden_cross": { ... },
    "volume_breakout": { ... },
    "52week_high": { ... }
  },
  "total_unique_stocks": 35
}
```

### 3) Enrich + rank (OHLCV confluence)

Run the validator/enricher to attach confluence setup scores and rankings:
```bash
uv run python scripts/validate_scan.py <scan_file_path> --enrich-setups --rank
```

This updates the scan JSON in-place with:
- Per-symbol OHLCV metrics
- Setup scores (2w breakout, 2m pullback, reversal cross-check)
- Ranked shortlists for review

### 4) Report (minimal)

Return ONLY:
- scan file path
- top 5 for `2w_breakout` and top 5 for `2m_pullback`
- note any data issues (missing OHLCV, too few rows)

## IMPORTANT

- Run ALL 5 scans every time (not selective)
- If a manager runs multiple scanners, parallelize by launching multiple scanner tasks (e.g., one per sector); within this agent, just run the 5 searches directly.
- Extract actual stock symbols (not just descriptions)
- Note the source website for each finding
- Do not trust web-search results blindly: OHLCV enrichment/ranking is required before recommending watchlist additions
