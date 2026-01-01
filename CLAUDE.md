# Portfolio Analyzer - Claude Code Instructions

## Quick Start

When user says **"analyze my portfolio from `<csv_path>`"** (or multiple CSVs), follow the orchestration steps below.

## Orchestration Steps (Optimized for Large Portfolios)

### Step 0: Clean Previous Data (Important!)
```bash
uv run python scripts/clean.py
```
Clears old analysis data before new portfolio. Cache is always kept (historical OHLCV doesn't change).

### Step 1: Parse CSV(s)
```bash
uv run python scripts/parse_csv.py input/kite.csv input/groww.csv
```

### Step 2: Fetch OHLCV (Batch Script)
```bash
uv run python scripts/fetch_all.py
```
Fetches Yahoo Finance data for all unique symbols. Cached for 18 hours.

### Step 3: Technical Analysis (Batch Script)
```bash
uv run python scripts/technical_all.py
```
Computes RSI, MACD, SMA, Bollinger, ADX for all stocks. Deterministic, no agents needed.

### Step 4: Web Research (Agents - Batched)
For each unique symbol_yf, launch these **3 agents**:
- **fundamentals-researcher** - P/E, revenue growth, quarterly results
- **news-sentiment** - Recent news, analyst ratings
- **legal-corporate** - Red flags, corporate actions

**Batching:** Process 3-5 stocks at a time to conserve context:
```
Batch 1: RELIANCE, TCS, INFY → 9 agents
Wait for completion
Batch 2: HDFC, ICICI, SBIN → 9 agents
Continue...
```

**Important:** Agents return minimal status only (not full JSON).

### Step 5: Score All Holdings (Batch Script)
```bash
uv run python scripts/score_all.py
```
Scores each holding (per broker) using the analysis data.

### Step 6: Compile Report
```bash
uv run python scripts/compile_report.py
```
Creates `output/analysis_YYYYMMDD_HHMMSS.csv` with portfolio health summary.

### Step 7: View Dashboard (Optional)
Open `dashboard/index.html` in browser and load the CSV.

---

## Quick Commands

```bash
# Full pipeline (after agents complete Step 4)
uv run python scripts/clean.py  # Clear old analysis data first!
uv run python scripts/parse_csv.py input/portfolio.csv
uv run python scripts/fetch_all.py
uv run python scripts/technical_all.py
# ... run research agents for each stock ...
uv run python scripts/score_all.py
uv run python scripts/compile_report.py
```

---

## Agent Details

### csv-parser
- Input: CSV file path
- Output: `data/holdings.json`
- Runs: `scripts/parse_csv.py`
- Supports: Zerodha (Kite), Groww CSV formats
- Currency handling: `₹`, `Rs.`, `Rs`, `INR` prefixes auto-stripped
- Duplicate handling: Same symbol+broker aggregated (weighted avg price, summed qty)

### data-fetcher
- Input: Stock symbol (e.g., RELIANCE.NS)
- Output: `cache/ohlcv/<symbol>.parquet`
- Runs: `scripts/fetch_ohlcv.py`
- Fetches 1 year of daily OHLCV from Yahoo Finance
- 18-hour cache freshness

### technical-analyst
- Input: Stock symbol
- Output: `data/technical/<symbol>.json`
- Runs: `scripts/technical_analysis.py`
- **Requires data-fetcher to run first** (reads from cache)
- Computes:
  - RSI (14-day) - Momentum oscillator
  - MACD (12/26/9) - Trend momentum
  - SMA 50 & 200 - Trend direction
  - Bollinger Bands (20,2) - Volatility
  - ADX (14-day) - Trend strength
  - Volume ratio - Buying pressure
- Scores each indicator 1-10, outputs weighted technical_score

### fundamentals-researcher
- Input: Company name and symbol
- Output: `data/fundamentals/<symbol>.json`
- Uses: WebSearch tool
- Searches for: quarterly results, P/E ratio, revenue/profit growth, debt ratios

### news-sentiment
- Input: Company name and symbol
- Output: `data/news/<symbol>.json`
- Uses: WebSearch tool
- Searches for: recent news, analyst ratings, target prices, sector outlook

### legal-corporate
- Input: Company name and symbol
- Output: `data/legal/<symbol>.json`
- Uses: WebSearch tool
- Searches for: SEBI penalties, lawsuits, major contracts, management changes

### scorer
- Input: Stock symbol
- Output: `data/scores/<symbol>.json`
- Runs: `scripts/score_stock.py`
- Reads all data files and computes weighted score
- **Requires all other agents to complete first**
- Coverage tracking: Tracks which components have data (T=technical, F=fundamental, N=news, L=legal)
- Weight renormalization: Missing components excluded, weights redistributed (no default 5 inflation)

---

## Scoring Philosophy

**Strategy: Medium-Term Trend-Following with Pullback Entries (1-3 months)**

- Bias toward trend-following, NOT mean-reversion
- Entry style: Buy pullbacks within established uptrends
- Risk stance: Avoid falling knives; prefer fewer high-confidence signals
- Philosophy: Technicals must confirm before fundamentals/news can recommend action

---

## Scoring Weights

**Note:** All weights and thresholds are defined in `utils/config.py` (single source of truth).

| Component | Weight |
|-----------|--------|
| Technical | 35% |
| Fundamental | 30% |
| News Sentiment | 20% |
| Legal/Corporate | 15% |

## Recommendations

| Score | Recommendation | Meaning |
|-------|----------------|---------|
| >= 8.0 | STRONG BUY | Trend-confirmed, high-confidence entry. All signals aligned. |
| >= 6.5 | BUY | Trend-aligned, acceptable entry risk. Consider scaling in. |
| >= 4.5 | HOLD | Mixed signals OR strong fundamentals without technical confirmation. |
| >= 3.0 | SELL | Technical + fundamental deterioration. Reduce on rallies. |
| < 3.0 | STRONG SELL | Multiple negative signals. Exit on any bounce. |

## Hard Gating Rules (Safety Constraints)

These gates prevent bad recommendations:

| Gate | Rule | Effect |
|------|------|--------|
| Trend Gate | `trend_score < 5` | Caps recommendation at HOLD |
| Weak Trend + Volume | `ADX <= 4 AND volume < 6` | Caps recommendation at HOLD |
| News Override | `news >= 8 AND technical < 5` | Downgrades BUY to HOLD |
| STRONG BUY Alignment | Missing trend/MACD/ADX alignment | Downgrades to BUY |
| Red Flag | Severe legal/regulatory issue | Caps score at 5.0 |

## Confidence Levels

Each recommendation includes a confidence level:

| Confidence | Meaning |
|------------|---------|
| HIGH | All key signals (trend, MACD, ADX) are aligned |
| MEDIUM | Partial alignment, some mixed signals |
| LOW | Conflicting signals, or momentum without trend confirmation |

Confidence drops when:
- MACD strong but trend weak (momentum without direction)
- ADX < 20 (no clear trend to follow)
- Signals conflict (some bullish, some bearish)

## Technical Indicator Roles

| Indicator | Role | Can Boost? | Can Veto BUY? |
|-----------|------|------------|---------------|
| Trend (SMA) | Primary direction gate | Yes | **Yes** |
| ADX | Trend strength qualifier | Yes | Indirect |
| MACD | Momentum confirmation | Yes | Yes |
| RSI | Entry timing | Limited | No |
| Bollinger %B | Pullback context | Limited | No |
| Volume | Breakout confirmation | Yes | Indirect |

**Key principle:** RSI and Bollinger should never independently cause a BUY. They are timing tools, not direction tools.

## Configurable Weights

Technical indicator weights can be customized in `config/technical_weights.csv`:
```
indicator,weight,description
rsi,0.20,Relative Strength Index - entry timing in confirmed trends
macd,0.20,Moving Average Convergence Divergence - momentum confirmation
trend,0.25,Price trend based on SMA50/200 - PRIMARY GATE
bollinger,0.10,Bollinger Bands - pullback context (not mean-reversion)
adx,0.15,Average Directional Index - trend strength qualifier
volume,0.10,Volume analysis - breakout/distribution confirmation
```

## Directory Structure

```
portfolio-analyzer/
├── .claude/agents/     # Agent definitions
├── config/             # Configuration files
│   └── technical_weights.csv
├── utils/              # Shared utilities
│   ├── helpers.py      # Common functions
│   └── config.py       # Centralized thresholds/weights (single source of truth)
├── dashboard/          # HTML dashboard
│   ├── index.html
│   ├── style.css
│   └── app.js
├── input/              # CSV files go here
├── output/             # Final analysis reports
├── data/               # Intermediate JSON (written by agents)
│   ├── holdings.json
│   ├── technical/      # Portfolio technical analysis (nested schema)
│   ├── scan_technical/ # Scanner verification (flat schema, separate to avoid clash)
│   ├── fundamentals/
│   ├── news/
│   ├── legal/
│   ├── scores/
│   ├── scans/          # Scanner results (timestamped)
│   ├── scan_history/   # Per-stock tracking history
│   └── watchlist.json  # User's tracked stocks
└── cache/ohlcv/        # Cached OHLCV parquet files
```

---

## Stock Scanner

The scanner discovers **new investment opportunities** by searching existing screener sites via parallel web search agents.

### Running a Scan

When user says **"run stock scanner"** or **"scan for stocks"**:

1. Launch **5 parallel Task agents** with WebSearch:

```
Agent 1: RSI Oversold
  - Search: "RSI oversold stocks NSE India", "chartink RSI below 30"

Agent 2: MACD Crossover
  - Search: "MACD bullish crossover NSE", "MACD buy signal India"

Agent 3: Golden Cross
  - Search: "Golden Cross stocks NSE", "SMA 50 crossing 200"

Agent 4: Volume Breakout
  - Search: "volume breakout NSE today", "unusual volume stocks"

Agent 5: 52-Week High
  - Search: "52 week high stocks NSE", "new highs India today"
```

2. Each agent returns: `SYMBOL - note - source`

3. Aggregate results and save:
```bash
uv run python scripts/save_scan.py
# Saves to data/scans/scan_YYYYMMDD_HHMMSS.json
```

4. Report summary to user

### Watchlist Management

When user wants to track a stock from scan results:

**Add to watchlist:**
```bash
uv run python scripts/watchlist.py add SYMBOL SCAN_TYPE [PRICE]
# Example: uv run python scripts/watchlist.py add DCMSRIND rsi_oversold 245.50
```

**Remove from watchlist:**
```bash
uv run python scripts/watchlist.py remove SYMBOL
```

**List watchlist:**
```bash
uv run python scripts/watchlist.py list
uv run python scripts/watchlist.py list -p  # With current prices
```

**Update prices:**
```bash
uv run python scripts/watchlist.py update
```

### Performance Tracking

Track how scan picks perform over time:

```bash
uv run python scripts/track_performance.py
```

Output:
```
Performance Report (2026-01-01)
======================================================================
Symbol       Return     Days     Signal             Entry      Current
----------------------------------------------------------------------
DCMSRIND     +18.1%     14       rsi_oversold       Rs 245     Rs 290
YUKENIND     +5.3%      7        macd_crossover     Rs 1030    Rs 1085
======================================================================
Summary: 2 stocks | Avg return: +11.7% | Winners: 2 | Losers: 0
```

**Show single stock history:**
```bash
uv run python scripts/track_performance.py show DCMSRIND
```

### Scanner Workflow Example

```
User: "run stock scanner"

Claude: Launching 5 parallel scan agents...
  - RSI Oversold: Found 12 stocks
  - MACD Crossover: Found 8 stocks
  - Golden Cross: Found 10 stocks
  - Volume Breakout: Found 7 stocks
  - 52-Week High: Found 15 stocks

Saved to data/scans/scan_20260101_143000.json

Top picks by category:
  RSI Oversold: DCMSRIND (RSI 15), ATMASTCO (RSI 17)
  MACD Crossover: YUKENIND, IREDA
  Golden Cross: KESORAMIND, BSOFT

User: "add DCMSRIND and YUKENIND to watchlist"

Claude:
  Added DCMSRIND to watchlist at Rs 245.50 (from rsi_oversold)
  Added YUKENIND to watchlist at Rs 1030.00 (from macd_crossover)

User: "show watchlist performance"

Claude: [Runs track_performance.py and shows returns]
```

### Scan Data Files

**Scan results:** `data/scans/scan_{YYYYMMDD_HHMMSS}.json`
```json
{
  "timestamp": "2026-01-01T14:30:00",
  "scans": {
    "rsi_oversold": {
      "count": 12,
      "matches": [{"symbol": "DCMSRIND", "note": "RSI 15.1", "source": "trendlyne"}]
    }
  },
  "total_unique_stocks": 35
}
```

**Watchlist:** `data/watchlist.json`
```json
{
  "stocks": [
    {
      "symbol": "DCMSRIND",
      "added_date": "2026-01-01",
      "added_from_scan": "rsi_oversold",
      "added_price": 245.50,
      "notes": "RSI 15.1"
    }
  ]
}
```

**Per-stock history:** `data/scan_history/{SYMBOL}.json`
```json
{
  "symbol": "DCMSRIND",
  "first_seen": "2026-01-01",
  "first_seen_scan": "rsi_oversold",
  "first_price": 245.50,
  "latest_price": 290.00,
  "return_pct": 18.1,
  "days_tracked": 14
}
```

### Full Technical Analysis (Verification)

After web search, run full technical analysis on picked stocks before adding to watchlist.

**Note:** Results save to `data/scan_technical/` (not `data/technical/`) to avoid schema conflicts with portfolio analysis.

**Analyze stocks:**
```bash
uv run python scripts/verify_scan.py VPRPL IREDA RVNL COALINDIA
```

**Output:**
```
Analyzing 4 stocks...

Batch 1/1: VPRPL, IREDA, RVNL, COALINDIA
  VPRPL: Score 6.5 | BUY | RSI 21 | MACD ↑ | UP
  IREDA: Score 7.0 | BUY | RSI 45 | MACD ↑ | STRONG UP
  RVNL: Score 8.0 | STRONG BUY | RSI 38 | MACD ↑ | STRONG UP
  COALINDIA: Score 5.5 | HOLD | RSI 52 | MACD ↓ | UP

================================================================================
Symbol       Score   Rec          RSI      MACD     Trend        52W
================================================================================
RVNL         8.0     STRONG BUY   38.0     Bullish  STRONG UP    5.2% off
IREDA        7.0     BUY          45.0     Bullish  STRONG UP    8.1% off
VPRPL        6.5     BUY          21.0     Bullish  UP           15.3% off
COALINDIA    5.5     HOLD         52.0     Bearish  UP           12.0% off
================================================================================

STRONG BUY: RVNL
BUY: IREDA, VPRPL
HOLD: COALINDIA

Ready for watchlist: RVNL IREDA VPRPL
```

**What it computes:**
- RSI (14-day) + signal interpretation
- MACD + Signal line + bullish/bearish
- SMA50 & SMA200 + trend direction
- ADX (trend strength)
- Volume ratio vs 20-day avg
- 52-week high/low distance
- Bollinger Bands position
- Technical score (1-10)
- Recommendation (STRONG BUY/BUY/HOLD/SELL)

**Rate limiting:**
- Batches of 5 stocks with 2-second delay
- Exponential backoff on failures (2s → 4s → 8s)
- Uses cached OHLCV when fresh (< 18 hours)
- Saves results to `data/scan_technical/`

### Analysis Workflow

```
Step 1: Run scan (web search)
  User: "run stock scanner"
  Claude: [Shows scan results from web search]

Step 2: User picks stocks to analyze
  User: "analyze VPRPL IREDA RVNL COALINDIA"
  Claude: [Runs verify_scan.py with full technical analysis]

Step 3: Add recommended stocks to watchlist
  User: "add RVNL and IREDA to watchlist"
  Claude: [Runs watchlist.py add]
```
