# Portfolio Analyzer - Build Specification

## Project Overview

Build a **Claude Code agent-orchestrated portfolio analyzer** that takes exported CSV files from Indian brokers (Zerodha/Groww), analyzes each stock using technical indicators and web search (for fundamentals, news, legal info), and outputs a comprehensive CSV with scores and actionable recommendations.

**Architecture:** Claude Code agents orchestrate the pipeline. Deterministic work (data fetching, calculations) runs via Python scripts. Research work (fundamentals, news, legal) uses Claude's WebSearch tool.

**Core Principles:**
- KISS (Keep It Simple, Stupid)
- DRY (Don't Repeat Yourself)
- Fail gracefully, never crash
- Cache data to disk for reuse across runs
- JSON files for inter-agent communication

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE AGENTS ORCHESTRATION                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User: "Analyze my portfolio" + CSV path                                 │
│                        │                                                 │
│                        ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              portfolio-manager (orchestrator agent)               │   │
│  │  - Spawns sub-agents via Task tool                               │   │
│  │  - Coordinates pipeline                                           │   │
│  │  - Aggregates results into final CSV                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                        │                                                 │
│         ┌──────────────┼──────────────┐                                 │
│         ▼              ▼              ▼                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                       │
│  │ csv-parser  │ │data-fetcher │ │ technical-  │   Python Scripts      │
│  │   (Python)  │ │  (Python)   │ │  analyst    │   via Bash tool       │
│  └─────────────┘ └─────────────┘ └─────────────┘                       │
│                                                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                       │
│  │fundamentals-│ │news-        │ │legal-       │   WebSearch tool      │
│  │ researcher  │ │ sentiment   │ │ corporate   │   (Claude searches)   │
│  └─────────────┘ └─────────────┘ └─────────────┘                       │
│                        │                                                 │
│                        ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    scorer (Python script)                         │   │
│  │  - Aggregates all scores                                          │   │
│  │  - Generates recommendations                                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                        │                                                 │
│                        ▼                                                 │
│                  OUTPUT CSV (output/analysis_YYYYMMDD.csv)              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
portfolio-analyzer/
├── .claude/
│   └── agents/
│       ├── portfolio-manager.md      # Orchestrator agent
│       ├── csv-parser.md             # Parses broker CSVs
│       ├── data-fetcher.md           # Fetches OHLCV data
│       ├── technical-analyst.md      # Computes indicators
│       ├── fundamentals-researcher.md # Web search fundamentals
│       ├── news-sentiment.md         # Web search news
│       ├── legal-corporate.md        # Web search red flags
│       └── scorer.md                 # Aggregates scores
├── scripts/
│   ├── parse_csv.py                  # CSV parsing script
│   ├── fetch_ohlcv.py                # yfinance data fetcher
│   ├── technical_analysis.py         # Technical indicators
│   └── score_stock.py                # Scoring calculations
├── utils/
│   ├── __init__.py
│   ├── cache.py                      # Cache management
│   └── helpers.py                    # Common utilities
├── cache/
│   ├── ohlcv/                        # Parquet files
│   └── cache_metadata.json
├── data/                             # Inter-agent JSON files
│   ├── holdings.json                 # Parsed holdings
│   ├── technical/                    # Technical analysis per stock
│   ├── fundamentals/                 # Fundamentals per stock
│   ├── news/                         # News sentiment per stock
│   └── legal/                        # Legal/corporate per stock
├── input/                            # Place input CSVs here
├── output/                           # Generated analysis CSVs
├── pyproject.toml                    # uv project config
└── uv.lock                           # uv lockfile
```

---

## Agent Specifications

### Agent: portfolio-manager (Orchestrator)

**File:** `.claude/agents/portfolio-manager.md`

**Purpose:** Main orchestrator that runs the full analysis pipeline by spawning sub-agents.

**Workflow:**
1. Receive CSV path from user
2. Spawn `csv-parser` agent → get holdings list
3. For each stock:
   - Spawn `data-fetcher` → ensure OHLCV cached
   - Spawn `technical-analyst` → get technical scores
   - Spawn `fundamentals-researcher` → get fundamentals (WebSearch)
   - Spawn `news-sentiment` → get news (WebSearch)
   - Spawn `legal-corporate` → get red flags (WebSearch)
   - Spawn `scorer` → aggregate into recommendation
4. Compile all results into final CSV
5. Report summary to user

**Spawns agents via:** Task tool with appropriate sub-agent type

---

### Agent: csv-parser

**File:** `.claude/agents/csv-parser.md`

**Purpose:** Parse Zerodha/Groww CSV and extract holdings.

**How it works:** Runs `uv run python scripts/parse_csv.py <input_csv>` via Bash tool.

**Input:** CSV file path (provided as argument)

**Output:** Writes `data/holdings.json`

```json
[
    {
        "symbol": "RELIANCE",
        "symbol_yf": "RELIANCE.NS",
        "name": "Reliance Industries",
        "quantity": 10,
        "avg_price": 2450.50,
        "broker": "zerodha"
    }
]
```

**Broker Detection:**
- Zerodha: Header contains "Instrument"
- Groww: Header contains "Symbol" + "Company Name"

---

### Agent: data-fetcher

**File:** `.claude/agents/data-fetcher.md`

**Purpose:** Fetch OHLCV data from yfinance with caching.

**How it works:** Runs `uv run python scripts/fetch_ohlcv.py <symbol>` via Bash tool.

**Input:** Symbol (e.g., "RELIANCE.NS")

**Output:**
- Caches to `cache/ohlcv/<symbol>.parquet`
- Updates `cache/cache_metadata.json`
- Prints status to stdout

**Caching Logic:**
- Skip if data exists and is fresh (< 18 hours old)
- Fetch 1 year of data by default
- Fallback to BSE (.BO) if NSE fails
- Retry with exponential backoff

---

### Agent: technical-analyst

**File:** `.claude/agents/technical-analyst.md`

**Purpose:** Compute technical indicators from OHLCV data.

**How it works:** Runs `uv run python scripts/technical_analysis.py <symbol>` via Bash tool.

**Input:** Symbol (reads from cached parquet)

**Output:** Writes `data/technical/<symbol>.json`

```json
{
    "symbol": "RELIANCE.NS",
    "rsi": 42.5,
    "rsi_score": 6,
    "macd": 12.3,
    "macd_signal": 10.1,
    "macd_histogram": 2.2,
    "macd_score": 7,
    "sma_50": 2800,
    "sma_200": 2650,
    "price_vs_sma50": 3.2,
    "price_vs_sma200": 9.1,
    "trend_score": 8,
    "bollinger_upper": 2950,
    "bollinger_lower": 2750,
    "bollinger_pct_b": 0.65,
    "bollinger_score": 5,
    "adx": 28.5,
    "adx_score": 7,
    "volume_ratio": 1.3,
    "volume_score": 6,
    "technical_score": 6.5,
    "current_price": 2890.00
}
```

**Indicator Scoring:**

| Indicator | Parameters | Score Logic |
|-----------|------------|-------------|
| RSI | period=14 | <30: 9, 30-40: 7, 40-60: 5, 60-70: 4, >70: 2 |
| MACD | fast=12, slow=26, signal=9 | MACD > Signal & rising: 8-10, MACD < Signal: 2-4 |
| SMA | 50 and 200 | Price > 50 > 200: 9, Price > 50 < 200: 6, Price < both: 2 |
| Bollinger | period=20, std=2 | %B < 0.2: 8, %B 0.2-0.8: 5, %B > 0.8: 3 |
| ADX | period=14 | >25 + uptrend: 8, >25 + downtrend: 3, <20: 5 |
| Volume | 20-day avg | >1.5x + up day: 8, >1.5x + down day: 3, normal: 5 |

---

### Agent: fundamentals-researcher

**File:** `.claude/agents/fundamentals-researcher.md`

**Purpose:** Research fundamental data via web search.

**How it works:** Uses WebSearch tool directly (no Python script).

**Input:** Company name and symbol

**Search Queries:**
```
"{company_name} quarterly results Q3 Q4 2024 revenue profit"
"{company_name} PE ratio valuation financial ratios"
"{company_name} annual report 2024 YoY growth"
```

**Output:** Writes `data/fundamentals/<symbol>.json`

```json
{
    "symbol": "RELIANCE.NS",
    "pe_ratio": 25.5,
    "pe_vs_sector": "below",
    "revenue_growth_yoy": 12.5,
    "profit_growth_yoy": 8.2,
    "last_4q_trend": "improving",
    "debt_to_equity": 0.45,
    "roe": 18.5,
    "fundamental_score": 7,
    "fundamental_summary": "Q3 results beat estimates with 12% revenue growth. Margins stable. Low debt."
}
```

**Scoring Logic:**
- Strong growth + low PE + improving trend: 8-10
- Stable metrics, inline with sector: 5-7
- Declining growth, high debt: 2-4

---

### Agent: news-sentiment

**File:** `.claude/agents/news-sentiment.md`

**Purpose:** Analyze recent news and market sentiment via web search.

**How it works:** Uses WebSearch tool directly.

**Input:** Company name and symbol

**Search Queries:**
```
"{company_name} stock news last 30 days"
"{company_name} analyst rating target price 2024"
"{company_name} sector outlook"
```

**Output:** Writes `data/news/<symbol>.json`

```json
{
    "symbol": "RELIANCE.NS",
    "news_sentiment": "positive",
    "analyst_consensus": "buy",
    "target_price_avg": 3100,
    "target_vs_current": 7.3,
    "sector_outlook": "positive",
    "news_sentiment_score": 7,
    "news_summary": "Positive analyst coverage after Q3 results. Target prices raised. Sector tailwinds."
}
```

---

### Agent: legal-corporate

**File:** `.claude/agents/legal-corporate.md`

**Purpose:** Surface red flags and material corporate events via web search.

**How it works:** Uses WebSearch tool directly.

**Input:** Company name and symbol

**Search Queries:**
```
"{company_name} SEBI order penalty investigation"
"{company_name} lawsuit legal case court"
"{company_name} major order contract win deal"
"{company_name} merger acquisition stake sale"
"{company_name} management change CEO CFO resignation"
"{company_name} insider trading bulk deal promoter"
```

**Red Flags to Detect:**
- SEBI investigations/penalties
- Major lawsuits
- Auditor resignations
- Promoter pledge increases
- Management exodus

**Positive Signals:**
- Major order wins
- Strategic partnerships
- Institutional buying
- Promoter buying

**Output:** Writes `data/legal/<symbol>.json`

```json
{
    "symbol": "RELIANCE.NS",
    "red_flags": [],
    "positive_signals": ["Won $500M defense contract"],
    "corporate_actions": ["Bonus 1:1 announced"],
    "legal_corporate_score": 8,
    "has_severe_red_flag": false,
    "legal_summary": "No legal concerns. Major defense order win. Bonus announced."
}
```

**Severe Red Flags (cap score at 5):**
- "sebi penalty"
- "fraud"
- "default"
- "auditor resignation"

---

### Agent: scorer

**File:** `.claude/agents/scorer.md`

**Purpose:** Aggregate all scores and generate final recommendation.

**How it works:** Runs `uv run python scripts/score_stock.py <symbol>` via Bash tool.

**Input:** Symbol (reads from all data/*.json files)

**Output:** Returns JSON with final scores

```json
{
    "symbol": "RELIANCE",
    "name": "Reliance Industries",
    "quantity": 10,
    "avg_price": 2450.50,
    "current_price": 2890.00,
    "pnl_pct": 17.9,
    "technical_score": 6.5,
    "fundamental_score": 7,
    "news_sentiment_score": 7,
    "legal_corporate_score": 8,
    "overall_score": 7.1,
    "recommendation": "BUY",
    "red_flags": "",
    "summary": "Technical: Healthy uptrend with RSI at 42. Q3 results beat estimates with 12% revenue growth. Positive analyst coverage. No legal concerns."
}
```

**Scoring Weights:**
```python
WEIGHTS = {
    "technical": 0.35,
    "fundamental": 0.30,
    "news_sentiment": 0.20,
    "legal_corporate": 0.15
}
```

**Recommendation Mapping:**
- >= 8.0: STRONG BUY
- >= 6.5: BUY
- >= 4.5: HOLD
- >= 3.0: SELL
- < 3.0: STRONG SELL

---

## Output CSV Format

**Columns:**
```
symbol,name,quantity,avg_price,current_price,pnl_pct,rsi,rsi_score,macd_score,trend_score,bollinger_score,adx_score,volume_score,technical_score,fundamental_score,news_sentiment_score,legal_corporate_score,overall_score,recommendation,red_flags,summary
```

**Example Row:**
```csv
RELIANCE,Reliance Industries,10,2450.50,2890.00,17.9,42,6,7,8,5,7,6,6.5,7,7,8,7.1,BUY,,"Technical: Healthy uptrend with RSI at 42. Q3 results beat estimates. Positive analyst coverage. No legal concerns."
```

---

## Configuration

**Stored in scripts or agent prompts:**

```python
# Scoring weights
WEIGHTS = {
    "technical": 0.35,
    "fundamental": 0.30,
    "news_sentiment": 0.20,
    "legal_corporate": 0.15
}

# Recommendation thresholds
THRESHOLDS = {
    "strong_buy": 8.0,
    "buy": 6.5,
    "hold": 4.5,
    "sell": 3.0
}

# Red flags that cap score at 5
SEVERE_RED_FLAGS = [
    "sebi penalty",
    "fraud",
    "default",
    "auditor resignation"
]

# Technical indicator parameters
INDICATOR_PARAMS = {
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "sma_short": 50,
    "sma_long": 200,
    "bollinger_period": 20,
    "bollinger_std": 2,
    "adx_period": 14,
    "volume_avg_period": 20
}

# Cache settings
CACHE_STALE_HOURS = 18
```

---

## Dependencies (uv)

Using `uv` for fast, modern Python package management.

```bash
# Initialize project
uv init

# Add dependencies
uv add yfinance pandas pandas-ta pyarrow
```

**pyproject.toml:**
```toml
[project]
name = "portfolio-analyzer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "yfinance>=0.2.36",
    "pandas>=2.0.0",
    "pandas-ta>=0.3.14b",
    "pyarrow>=14.0.0",
]
```

**Running scripts:**
```bash
# Run any script with uv
uv run python scripts/parse_csv.py input/portfolio.csv
uv run python scripts/fetch_ohlcv.py RELIANCE.NS
uv run python scripts/technical_analysis.py RELIANCE.NS
```

---

## Build Order

1. **Phase 1**: Setup + csv-parser + data-fetcher + technical-analyst agents
2. **Phase 2**: fundamentals-researcher agent (WebSearch)
3. **Phase 3**: news-sentiment agent (WebSearch)
4. **Phase 4**: legal-corporate agent (WebSearch)
5. **Phase 5**: scorer agent + portfolio-manager orchestrator
6. **Phase 6**: Testing + polish

---

## Usage

```bash
# User invokes the portfolio-manager agent
# Either via Claude Code CLI or by asking Claude to run it

# Example conversation:
User: "Analyze my portfolio from input/zerodha_holdings.csv"

# Claude (portfolio-manager) will:
# 1. Parse the CSV
# 2. Fetch data for each stock
# 3. Run technical analysis
# 4. Search for fundamentals, news, legal info
# 5. Score and summarize
# 6. Output to output/analysis_YYYYMMDD_HHMMSS.csv
```

---

## Error Handling

- **Missing data:** Use neutral score (5), note in summary
- **yfinance failure:** Try .BO suffix, log error, continue
- **WebSearch failure:** Use neutral score, note "Unable to fetch"
- **Never skip a stock:** Always include in output with available data

---

## Notes for Claude Code Agents

- Python scripts handle deterministic work (parsing, calculations)
- WebSearch handles research work (fundamentals, news, legal)
- All inter-agent data passes through JSON files in `data/`
- Each agent should be self-contained and focused
- Manager agent orchestrates via Task tool
- Agents should fail gracefully and report errors clearly
