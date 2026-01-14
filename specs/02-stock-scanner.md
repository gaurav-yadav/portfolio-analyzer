# SPEC: Stock Scanner (Web Search Based)

## Overview

Discover **new investment opportunities** by:
1) Web-searching existing screeners (Chartink, Trendlyne, etc.) for a candidate pool
2) Ranking candidates using **OHLCV-derived confluence** (so decisions are based on real price/volume)

**Key Design:**
- **Claude agents with WebSearch** do the heavy lifting
- **Run ALL 5 scans in parallel** (not individual selection)
- **Track results over time** to see if picks worked
- **Enrich + rank picks with OHLCV** before adding to watchlist (Yahoo Finance via existing scripts)

---

## How It Works

```
User: "run stock scanner"

Claude: Launching 5 parallel search agents...

┌─────────────────────────────────────────────────────────────┐
│  Agent 1: RSI Oversold     → Search Chartink, Trendlyne    │
│  Agent 2: MACD Crossover   → Search Chartink, TopStock     │
│  Agent 3: Golden Cross     → Search Trendlyne, 5paisa      │
│  Agent 4: Volume Breakout  → Search NSE, Dhan              │
│  Agent 5: 52-Week High     → Search NSE, Groww             │
└─────────────────────────────────────────────────────────────┘

Claude: Scan complete! Found:
  - RSI Oversold: 12 stocks (DCMSRIND, ATMASTCO, ...)
  - MACD Crossover: 8 stocks (YUKENIND, IREDA, ...)
  - Golden Cross: 10 stocks (KESORAMIND, BSOFT, ...)
  - Volume Breakout: 7 stocks (HFCL, MMTC, ...)
  - 52-Week High: 15 stocks (...)

Saved to data/scans/scan_20260101_143000.json

Claude: Validating scan picks with OHLCV...
  uv run python scripts/validate_scan.py latest --enrich-setups --rank
  - Adds pass/fail validation per match
  - Writes per-symbol technical checks to data/scan_technical/
  - Adds confluence setup scores + ranked shortlists
```

---

## Validation (OHLCV-based)

Web search results are noisy; validate signals against real OHLCV before acting.

**Script:** `scripts/validate_scan.py`

```bash
uv run python scripts/validate_scan.py latest --enrich-setups --rank
```

Adds to the scan JSON:
- Per-match `validation` object (pass/reason + key metrics)
- Top-level `validation` summary + `results_by_symbol`

---

## Smart Enrichment (Confluence Setups)

### Goals (KISS)

- Use web search only to build the candidate universe.
- Use OHLCV (cached) to decide what’s actually tradable.
- Rank into two actionable horizons:
  - **`2w_breakout`**: hold ~1–2 weeks
  - **`2m_pullback`**: hold ~1–2 months
- Keep **`support_reversal`** as a manual cross-check bucket (higher risk).

### Required OHLCV Features

Computed from 1y daily OHLCV:
- `sma20`, `sma50`, `sma200`
- `rsi14`
- `volume_ratio` (today vs 20D avg)
- `high_52w`, `low_52w`, `% from high/low`
- `donchian_high_20` (highest high of last 20 trading days, excluding today)
- `days_since_breakout_20` (if close breaks above `donchian_high_20`)
- `support_level` (nearest meaningful swing low over last ~3–6 months) + `% distance`
- Optional (nice-to-have): RSI divergence vs recent swing low, “tight range” compression score

### Setup Definitions (Rules of Thumb)

All setup blocks share this shape:
```json
{
  "pass": true,
  "score": 82,
  "why": ["trend_ok", "near_support", "rsi_reset", "volume_on_bounce"],
  "metrics": {"rsi": 47.2, "volume_ratio": 1.4, "pct_from_sma20": 1.8}
}
```

#### 1) `2m_pullback` (Primary; trend-following)

Intent: buy pullbacks **within uptrends** (not mean reversion).

Hard gates (fail fast):
- Uptrend bias: `close > sma200` AND (`sma50 >= sma200` OR `close > sma50`)
- Not a chase: `close` not too extended above `sma20` (overextension filter)

Score boosters:
- RSI “reset” zone (typically ~40–55) turning up
- Close near `sma20/sma50` or near `support_level`
- Volume expansion on bounce day(s)

#### 2) `2w_breakout` (Secondary; continuation)

Intent: trade fresh breakouts with confirmation, avoid false breaks.

Hard gates:
- Trend bias: `close > sma50` AND `close > sma200` (or at least `close > sma200`)
- Breakout recency: breakout within last ~3 trading days

Score boosters:
- Relative volume: `volume_ratio >= 1.5`
- Close near day high / above breakout level (less “wicky”)
- Prior tight range (compression) before breakout (optional)

#### 3) `support_reversal` (Manual cross-check; higher risk)

Intent: potential turn at major support.

Hard gates:
- Close near `support_level` (within a small % band)
- Bounce confirmation: positive day + volume expansion

Score boosters:
- Bullish RSI divergence near the low (optional)
- “Double bottom” style retest within a tolerance band (optional)
- Reclaim of `sma20` or `sma50` after the bounce

### Ranking Output (in scan JSON)

When `--rank` is enabled, write shortlists into:
- `scan.validation.rankings.2w_breakout`
- `scan.validation.rankings.2m_pullback`
- `scan.validation.rankings.support_reversal`

Each shortlist entry should include `symbol`, `score`, and a one-line `why`.

### CLI Contract (what to implement)

Extend `scripts/validate_scan.py`:
- `--enrich-setups`: compute setup blocks per symbol and store into the scan JSON
- `--rank`: write ranked shortlists into `validation.rankings.*`

No new scripts required; keep it in `validate_scan.py`.

### Schema Additions (scan JSON)

When `--enrich-setups` is enabled, write:
- `scan.validation.engine_version = 2`
- `scan.validation.setups_by_symbol`:
  - Key: `symbol_clean` (no `.NS/.BO`)
  - Value: setup blocks (plus any shared computed levels)
- `scan.validation.rankings` (only when `--rank` is enabled)

Example (trimmed):
```json
{
  "validation": {
    "engine": "scripts/validate_scan.py",
    "engine_version": 2,
    "results_by_symbol": {"DCBBANK": {"yf_symbol": "DCBBANK.NS", "rsi": 65.1, "...": "..."}},
    "setups_by_symbol": {
      "DCBBANK": {
        "2w_breakout": {"pass": true, "score": 78, "why": ["trend_ok", "recent_breakout", "volume_ok"], "metrics": {}},
        "2m_pullback": {"pass": false, "score": 32, "why": ["overextended"], "metrics": {}},
        "support_reversal": {"pass": false, "score": 10, "why": ["not_near_support"], "metrics": {}}
      }
    },
    "rankings": {
      "2w_breakout": [{"symbol": "DCBBANK", "score": 78, "why": "trend_ok + recent_breakout + volume_ok"}],
      "2m_pullback": [],
      "support_reversal": []
    }
  }
}
```

### Implementation Notes (DRY)

- Prefer computing all extra OHLCV features in one place (either:
  - extend `scripts/verify_scan.py:compute_full_analysis()`, or
  - add a small helper in `scripts/validate_scan.py` that works off the cached OHLCV dataframe).
- Keep setup scoring deterministic and fully explainable via `why[]`.

This uses `scripts/verify_scan.py` under the hood, which:
- Fetches 1y OHLCV from Yahoo Finance (cached)
- Computes RSI, MACD (with crossover recency), SMA50/200 (golden cross recency), volume ratio, 52w distance

---

## Scan Types

| Scan | Search Queries | Sources |
|------|---------------|---------|
| `rsi_oversold` | "RSI oversold stocks NSE", "RSI below 30 today" | Chartink, Trendlyne, Groww, Dhan |
| `macd_crossover` | "MACD bullish crossover NSE", "MACD buy signal" | Chartink, TopStockResearch |
| `golden_cross` | "Golden Cross stocks NSE", "SMA 50 crossing 200" | Trendlyne, 5paisa, Dhan |
| `volume_breakout` | "Volume breakout NSE today", "unusual volume" | NSE India, Dhan, TradingView |
| `52week_high` | "52 week high stocks NSE", "new highs today" | NSE India, Groww |

---

## Data Storage

### Scan Results: `data/scans/scan_{timestamp}.json`

```json
{
  "timestamp": "2026-01-01T14:30:00",
  "scans": {
    "rsi_oversold": {
      "count": 12,
      "matches": [
        {"symbol": "DCMSRIND", "note": "RSI 15.1", "source": "trendlyne"},
        {"symbol": "ATMASTCO", "note": "RSI 16.5", "source": "groww"}
      ]
    },
    "macd_crossover": {
      "count": 8,
      "matches": [
        {"symbol": "YUKENIND", "note": "MACD crossed signal", "source": "chartink"}
      ]
    },
    "golden_cross": { ... },
    "volume_breakout": { ... },
    "52week_high": { ... }
  },
  "total_unique_stocks": 35
}
```

### Watchlist: `data/watchlist.json`

```json
{
  "stocks": [
    {
      "symbol": "DCMSRIND",
      "added_date": "2026-01-01",
      "added_from_scan": "rsi_oversold",
      "added_price": 245.50,
      "notes": "RSI 15.1 - extremely oversold"
    }
  ]
}
```

### History: `data/scan_history/{symbol}.json`

Track each stock's performance since discovery:

```json
{
  "symbol": "DCMSRIND",
  "first_seen": "2026-01-01",
  "first_seen_scan": "rsi_oversold",
  "first_price": 245.50,
  "appearances": [
    {"date": "2026-01-01", "scan": "rsi_oversold", "price": 245.50},
    {"date": "2026-01-08", "scan": "macd_crossover", "price": 268.00}
  ],
  "latest_price": 290.00,
  "return_pct": 18.1,
  "days_tracked": 14
}
```

---

## Agent Definition

See `.claude/agents/scanner.md` for the live agent definition.

Key requirements:
- Run **all 5 scans in parallel**
- Save results to `data/scans/scan_YYYYMMDD_HHMMSS.json`
- **Always validate** web-search picks with OHLCV before recommending watchlist adds:
  - Prefer the `scan-validator` agent, or run `uv run python scripts/validate_scan.py latest`

---

## Scripts

### `scripts/save_scan.py`

```python
"""Save aggregated scan results."""
import json
from datetime import datetime
from pathlib import Path

def save_scan_results(results: dict):
    """Save scan results with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output = {
        "timestamp": datetime.now().isoformat(),
        "scans": results,
        "total_unique_stocks": count_unique(results)
    }

    path = Path(f"data/scans/scan_{timestamp}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2))

    print(f"Saved scan results to {path}")
    return path

def count_unique(results: dict) -> int:
    """Count unique symbols across all scans."""
    symbols = set()
    for scan_data in results.values():
        for match in scan_data.get("matches", []):
            symbols.add(match["symbol"])
    return len(symbols)
```

### `scripts/watchlist.py`

```python
"""Watchlist management."""
import json
import sys
from datetime import datetime
from pathlib import Path
import yfinance as yf

WATCHLIST_PATH = Path("data/watchlist.json")

def load_watchlist() -> dict:
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text())
    return {"stocks": []}

def save_watchlist(data: dict):
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(data, indent=2))

def add_stock(symbol: str, scan_type: str, price: float = None, notes: str = ""):
    """Add stock to watchlist."""
    data = load_watchlist()

    # Check if already exists
    for stock in data["stocks"]:
        if stock["symbol"] == symbol:
            print(f"{symbol} already in watchlist")
            return

    # Fetch current price if not provided
    if price is None:
        ticker = yf.Ticker(f"{symbol}.NS")
        price = ticker.info.get("regularMarketPrice", 0)

    data["stocks"].append({
        "symbol": symbol,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "added_from_scan": scan_type,
        "added_price": price,
        "notes": notes
    })

    save_watchlist(data)
    print(f"Added {symbol} to watchlist at Rs {price}")

def remove_stock(symbol: str):
    """Remove stock from watchlist."""
    data = load_watchlist()
    data["stocks"] = [s for s in data["stocks"] if s["symbol"] != symbol]
    save_watchlist(data)
    print(f"Removed {symbol} from watchlist")

def list_watchlist():
    """Show all watchlist stocks with current prices."""
    data = load_watchlist()

    if not data["stocks"]:
        print("Watchlist is empty")
        return

    print(f"\n{'Symbol':<12} {'Added':<12} {'From Scan':<15} {'Added Price':<12} {'Notes'}")
    print("-" * 70)

    for stock in data["stocks"]:
        print(f"{stock['symbol']:<12} {stock['added_date']:<12} {stock['added_from_scan']:<15} Rs {stock['added_price']:<10.2f} {stock.get('notes', '')}")

def update_prices():
    """Update current prices for all watchlist stocks."""
    data = load_watchlist()

    for stock in data["stocks"]:
        symbol = stock["symbol"]
        ticker = yf.Ticker(f"{symbol}.NS")
        current = ticker.info.get("regularMarketPrice", 0)
        added = stock["added_price"]
        pct = ((current - added) / added * 100) if added else 0

        print(f"{symbol}: Rs {added:.2f} → Rs {current:.2f} ({pct:+.1f}%)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "add" and len(sys.argv) >= 4:
        add_stock(sys.argv[2], sys.argv[3],
                  float(sys.argv[4]) if len(sys.argv) > 4 else None)
    elif cmd == "remove" and len(sys.argv) >= 3:
        remove_stock(sys.argv[2])
    elif cmd == "list":
        list_watchlist()
    elif cmd == "update":
        update_prices()
    else:
        print("Usage:")
        print("  watchlist.py list")
        print("  watchlist.py add SYMBOL SCAN_TYPE [PRICE]")
        print("  watchlist.py remove SYMBOL")
        print("  watchlist.py update")
```

### `scripts/track_performance.py`

```python
"""Track watchlist performance over time."""
import json
from datetime import datetime
from pathlib import Path
import yfinance as yf

HISTORY_DIR = Path("data/scan_history")
WATCHLIST_PATH = Path("data/watchlist.json")

def update_history():
    """Update price history for all watchlist stocks."""
    if not WATCHLIST_PATH.exists():
        print("No watchlist found")
        return

    watchlist = json.loads(WATCHLIST_PATH.read_text())
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    print("\nPerformance Report")
    print("=" * 60)

    for stock in watchlist["stocks"]:
        symbol = stock["symbol"]
        history_file = HISTORY_DIR / f"{symbol}.json"

        # Load or create history
        if history_file.exists():
            history = json.loads(history_file.read_text())
        else:
            history = {
                "symbol": symbol,
                "first_seen": stock["added_date"],
                "first_seen_scan": stock["added_from_scan"],
                "first_price": stock["added_price"],
                "appearances": [],
                "price_checkpoints": []
            }

        # Fetch current price
        ticker = yf.Ticker(f"{symbol}.NS")
        current_price = ticker.info.get("regularMarketPrice", 0)

        # Add checkpoint
        today = datetime.now().strftime("%Y-%m-%d")
        history["price_checkpoints"].append({
            "date": today,
            "price": current_price
        })

        # Calculate returns
        first_price = history["first_price"]
        return_pct = ((current_price - first_price) / first_price * 100) if first_price else 0

        first_date = datetime.strptime(history["first_seen"], "%Y-%m-%d")
        days = (datetime.now() - first_date).days

        history["latest_price"] = current_price
        history["return_pct"] = return_pct
        history["days_tracked"] = days

        # Save
        history_file.write_text(json.dumps(history, indent=2))

        # Report
        emoji = "+" if return_pct >= 0 else ""
        print(f"{symbol:<12} {emoji}{return_pct:.1f}% ({days} days since {history['first_seen_scan']})")

    print("=" * 60)

if __name__ == "__main__":
    update_history()
```

---

## Usage Flow

```
# 1. Run scanner (launches 5 parallel agents)
User: "run stock scanner"
Claude: [Launches 5 agents, aggregates results, saves to data/scans/]

# 2. Add interesting stocks to watchlist
User: "add DCMSRIND to watchlist from rsi_oversold scan"
Claude: Added DCMSRIND at Rs 245.50

# 3. Check performance anytime
User: "show watchlist performance"
Claude:
  DCMSRIND: +18.1% (14 days since rsi_oversold)
  YUKENIND: +5.3% (7 days since macd_crossover)

# 4. Remove stocks that didn't work
User: "remove ATMASTCO from watchlist"
Claude: Removed ATMASTCO
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `.claude/agents/scanner.md` | Agent definition |
| `scripts/save_scan.py` | Save aggregated results |
| `scripts/watchlist.py` | Watchlist CRUD |
| `scripts/track_performance.py` | Performance tracking |
| `data/scans/` | Scan results (timestamped) |
| `data/watchlist.json` | Watchlist data |
| `data/scan_history/` | Per-stock history |

---

## Sources Used by Scanner

- [Chartink](https://chartink.com/) - RSI, MACD screens
- [Trendlyne](https://trendlyne.com/) - All technical screens
- [Groww](https://groww.in/) - RSI oversold, 52-week screens
- [Dhan](https://dhan.co/) - Volume, golden cross screens
- [5paisa](https://www.5paisa.com/) - Technical screens
- [NSE India](https://www.nseindia.com/) - Volume gainers, 52-week highs
- [TopStockResearch](https://www.topstockresearch.com/) - MACD signals
