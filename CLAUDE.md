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

### Step 5: Compile Results
Read all `data/scores/*.json` files and compile final CSV to `output/analysis_YYYYMMDD_HHMMSS.csv`

Report summary table with recommendations.

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

## Directory Structure

```
portfolio-analyzer/
├── .claude/agents/     # Agent definitions
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
