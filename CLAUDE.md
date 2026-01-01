# Portfolio Analyzer - Claude Code Instructions

## Quick Start

When user says **"analyze my portfolio from `<csv_path>`"**, follow the orchestration steps below.

## Orchestration Steps

### Step 1: Parse CSV
Launch the `csv-parser` agent with the CSV path.

Wait for completion. Then read `data/holdings.json` to get the stock list.

### Step 2: Fetch OHLCV Data
Launch `data-fetcher` for ALL stocks IN PARALLEL.

Wait for all to complete before Step 3.

### Step 3: Analyze (Parallel per Stock)

For EACH stock, launch these **4 agents IN PARALLEL**:

1. **technical-analyst** - Computes RSI, MACD, SMA, Bollinger, ADX from OHLCV
2. **fundamentals-researcher** - WebSearch for quarterly results, P/E ratio, revenue growth
3. **news-sentiment** - WebSearch for recent news, analyst ratings, target prices
4. **legal-corporate** - WebSearch for SEBI issues, lawsuits, major contracts

**Batch stocks:** Process 2-3 stocks at a time to avoid overwhelming.

### Step 4: Score (Parallel)
After all Step 3 agents complete, launch the `scorer` agent for each stock IN PARALLEL.

### Step 5: Compile Report
Run the compile script to generate final report with portfolio health summary:

```bash
uv run python scripts/compile_report.py
```

This creates:
- `output/analysis_YYYYMMDD_HHMMSS.csv` - Full report with portfolio health footer

Report summary table with recommendations.

### Step 6: View Dashboard (Optional)
Tell user they can open `dashboard/index.html` in browser and load the CSV for visual dashboard.

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

## Scoring Weights

| Component | Weight |
|-----------|--------|
| Technical | 35% |
| Fundamental | 30% |
| News Sentiment | 20% |
| Legal/Corporate | 15% |

## Recommendations

| Score | Recommendation |
|-------|----------------|
| >= 8.0 | STRONG BUY |
| >= 6.5 | BUY |
| >= 4.5 | HOLD |
| >= 3.0 | SELL |
| < 3.0 | STRONG SELL |

## Configurable Weights

Technical indicator weights can be customized in `config/technical_weights.csv`:
```
indicator,weight,description
rsi,0.20,Relative Strength Index
macd,0.20,Moving Average Convergence Divergence
trend,0.25,Price trend based on SMA50/200
bollinger,0.10,Bollinger Bands
adx,0.15,Average Directional Index
volume,0.10,Volume analysis
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
