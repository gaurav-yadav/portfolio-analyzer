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

---

## Scoring Philosophy

**Strategy: Medium-Term Trend-Following with Pullback Entries (1-3 months)**

- Bias toward trend-following, NOT mean-reversion
- Entry style: Buy pullbacks within established uptrends
- Risk stance: Avoid falling knives; prefer fewer high-confidence signals
- Philosophy: Technicals must confirm before fundamentals/news can recommend action

---

## Scoring Weights

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
├── dashboard/          # HTML dashboard
│   ├── index.html
│   ├── style.css
│   └── app.js
├── input/              # CSV files go here
├── output/             # Final analysis reports
├── data/               # Intermediate JSON (written by agents)
│   ├── holdings.json
│   ├── technical/
│   ├── fundamentals/
│   ├── news/
│   ├── legal/
│   └── scores/
└── cache/ohlcv/        # Cached OHLCV parquet files
```
