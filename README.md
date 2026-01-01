# Portfolio Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI-powered stock portfolio analyzer **and scanner** for Indian markets. Analyze your existing holdings (Zerodha/Groww) with technical indicators, fundamental research, news sentiment, and legal signals—or discover new opportunities with the built-in stock scanner.
<img width="1113" height="603" alt="Screenshot 2026-01-01 at 8 57 11 PM" src="https://github.com/user-attachments/assets/78b377b9-4848-4321-8e69-3af09bd39c68" />
<img width="423" height="524" alt="Screenshot 2026-01-01 at 8 56 56 PM" src="https://github.com/user-attachments/assets/05fd1a5a-fa04-4f04-84b1-4e47e4fc9de8" />


## Features

### Portfolio Analysis
- **CSV Import** - Drop your Zerodha or Groww holdings CSV
- **Technical Analysis** - RSI, MACD, SMA, Bollinger Bands, ADX
- **Fundamental Research** - Quarterly results, P/E ratios, growth metrics
- **News Sentiment** - Recent news, analyst ratings, target prices
- **Legal Signals** - SEBI issues, lawsuits, major contracts
- **Hardened Scoring** - Conservative recommendations with safety gates

### Stock Scanner
- **Multi-Signal Scanning** - RSI oversold, MACD crossover, Golden Cross, volume breakouts, 52-week highs
- **Watchlist Tracking** - Add promising stocks, track entry prices
- **Performance Reports** - Monitor returns on your picks over time
- **Technical Verification** - Full analysis before committing to watchlist

---

## Scoring Philosophy at a Glance

```
                    PORTFOLIO ANALYZER SCORING SYSTEM
    ================================================================

    STRATEGY: Medium-Term Trend-Following (1-3 months)
    INTENT:   Conservative BUY signals, avoid falling knives

    ┌─────────────────────────────────────────────────────────────┐
    │                    SIGNAL FLOW                              │
    │                                                             │
    │   RAW SCORES          GATES              FINAL OUTPUT       │
    │   ──────────         ──────              ────────────       │
    │                                                             │
    │   Technical ─35%─┐                                          │
    │                  │    ┌──────────────┐                      │
    │   Fundamental 30%├───>│ SAFETY GATES │───> Recommendation   │
    │                  │    │              │     + Confidence     │
    │   News ─────20%──┤    │ - Trend < 5? │                      │
    │                  │    │ - ADX weak?  │                      │
    │   Legal ────15%──┘    │ - Hype only? │                      │
    │                       └──────────────┘                      │
    └─────────────────────────────────────────────────────────────┘

    INDICATOR ROLES:
    ┌────────────────────────────────────────────────────────────┐
    │  Trend (SMA)  ████████████  PRIMARY GATE - Must confirm    │
    │  ADX          ████████░░░░  Strength qualifier             │
    │  MACD         ████████░░░░  Momentum confirmation          │
    │  RSI          ████░░░░░░░░  Entry timing only              │
    │  Bollinger    ████░░░░░░░░  Pullback context only          │
    │  Volume       ████░░░░░░░░  Breakout confirmation          │
    └────────────────────────────────────────────────────────────┘

    HARD GATES (Non-Negotiable):
    ┌────────────────────────────────────────────────────────────┐
    │  Trend < 5         →  Max recommendation: HOLD             │
    │  ADX weak + low vol →  Max recommendation: HOLD            │
    │  High news, low tech → Downgrade BUY to HOLD               │
    │  STRONG BUY needs   →  Trend >= 7, MACD >= 6, ADX >= 6     │
    └────────────────────────────────────────────────────────────┘

    CONFIDENCE LEVELS:
    ┌────────────────────────────────────────────────────────────┐
    │  ●●● HIGH    All signals aligned                           │
    │  ●●○ MEDIUM  Partial alignment                             │
    │  ●○○ LOW     Conflicting signals or weak trend             │
    └────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Setup

```bash
cd portfolio-analyzer
uv sync
```

### 2. Add Your Portfolio

Export your holdings CSV from your broker and place it in the `input/` folder:

- **Zerodha:** Console → Portfolio → Holdings → Download CSV
- **Groww:** Stocks → Holdings → Export

### 3. Run Analysis

Start Claude Code:

```bash
claude
```

Then say:

```
analyze my portfolio from input/your_holdings.csv
```

### 4. View Results

Results are saved to `output/analysis_YYYYMMDD_HHMMSS.csv`

**Interactive Dashboard:**
1. Open `dashboard/index.html` in your browser
2. Click "Select CSV File" and load your analysis CSV
3. View charts, sort by score, and click rows for details

## What Happens

```
1. Parse your CSV → extract holdings
2. Fetch OHLCV data from Yahoo Finance (sequential with throttling)
3. For each stock, run 4 analyses in parallel:
   - Technical indicators (RSI, MACD, SMA, Bollinger, ADX)
   - Fundamental research (quarterly results, P/E, growth)
   - News sentiment (recent news, analyst ratings)
   - Legal/corporate signals (SEBI, lawsuits, contracts)
4. Score each stock
5. Generate final report with recommendations
```

---

## Stock Scanner

Discover new investment opportunities by scanning for technical signals across NSE stocks.

### Run a Scan

```
> run stock scanner

Launching 5 parallel scan agents...
  - RSI Oversold: Found 12 stocks
  - MACD Crossover: Found 8 stocks
  - Golden Cross: Found 10 stocks
  - Volume Breakout: Found 7 stocks
  - 52-Week High: Found 15 stocks

Top picks by category:
  RSI Oversold: DCMSRIND (RSI 15), ATMASTCO (RSI 17)
  MACD Crossover: YUKENIND, IREDA
  Golden Cross: KESORAMIND, BSOFT
```

### Verify Before Adding

Run full technical analysis on promising stocks:

```bash
uv run python scripts/verify_scan.py VPRPL IREDA RVNL COALINDIA
```

Output:
```
================================================================================
Symbol       Score   Rec          RSI      MACD     Trend        52W
================================================================================
RVNL         8.0     STRONG BUY   38.0     Bullish  STRONG UP    5.2% off
IREDA        7.0     BUY          45.0     Bullish  STRONG UP    8.1% off
VPRPL        6.5     BUY          21.0     Bullish  UP           15.3% off
COALINDIA    5.5     HOLD         52.0     Bearish  UP           12.0% off
================================================================================
```

### Manage Watchlist

```bash
# Add stocks
uv run python scripts/watchlist.py add RVNL rsi_oversold 245.50

# View watchlist with prices
uv run python scripts/watchlist.py list -p

# Track performance
uv run python scripts/track_performance.py
```

Performance output:
```
Symbol       Return     Days     Signal             Entry      Current
----------------------------------------------------------------------
DCMSRIND     +18.1%     14       rsi_oversold       Rs 245     Rs 290
YUKENIND     +5.3%      7        macd_crossover     Rs 1030    Rs 1085
```

---

## Scoring System

### Weights

| Component | Weight |
|-----------|--------|
| Technical Analysis | 35% |
| Fundamentals | 30% |
| News Sentiment | 20% |
| Legal/Corporate | 15% |

### Recommendations

| Score | Recommendation |
|-------|----------------|
| 8.0+ | STRONG BUY |
| 6.5 - 7.9 | BUY |
| 4.5 - 6.4 | HOLD |
| 3.0 - 4.4 | SELL |
| < 3.0 | STRONG SELL |

## Technical Indicators

| Indicator | Period | What it measures |
|-----------|--------|------------------|
| RSI | 14 days | Overbought/oversold momentum |
| MACD | 12/26/9 | Trend momentum and crossovers |
| SMA | 50 & 200 | Short and long-term trend |
| Bollinger | 20, 2σ | Volatility and price position |
| ADX | 14 days | Trend strength |
| Volume | 20-day avg | Buying/selling pressure |

### How Technical Scores Work

Each indicator is scored 1-10 (higher = more bullish). **Tuned for trend-following, NOT mean-reversion.**

**RSI (Relative Strength Index)** - *Entry Timing*
| RSI Value | Score | Interpretation |
|-----------|-------|----------------|
| < 25 | 4 | Extreme oversold - potential falling knife |
| 25-35 | 7 | Pullback zone - ideal entry in uptrend |
| 35-55 | 6 | Healthy momentum |
| 55-70 | 5 | Neutral-to-strong |
| 70-80 | 4 | Overbought - not ideal entry |
| > 80 | 3 | Extreme overbought |

**MACD (Moving Average Convergence Divergence)** - *Momentum Confirmation*
| Condition | Score | Interpretation |
|-----------|-------|----------------|
| Above signal + rising + above zero | 9 | Full bullish |
| Above signal + rising | 7 | Recovering |
| Above signal (not rising) | 5 | Momentum fading |
| Below signal but above zero | 4 | Pullback in uptrend |
| Below signal + below zero | 2 | Full bearish |

**Trend (SMA 50/200)** - *PRIMARY GATE*
| Condition | Score | Interpretation |
|-----------|-------|----------------|
| Price > SMA50 > SMA200 | 9 | Strong uptrend - green light |
| Price > SMA200 > SMA50 | 7 | Golden cross forming |
| Price > SMA50, SMA50 < SMA200 | 5 | Bear market rally - caution |
| SMA50 > SMA200, Price < SMA50 | 5 | Pullback in uptrend - watch |
| Price < SMA50 < SMA200 | 2 | Strong downtrend - avoid |

**Bollinger Bands (%B)** - *Pullback Context (Not Mean-Reversion)*
| %B Value | Score | Interpretation |
|----------|-------|----------------|
| < 0 | 3 | Breaking down below bands |
| 0 - 0.2 | 5 | Near lower band (neutral) |
| 0.2 - 0.8 | 6 | Healthy range |
| 0.8 - 1.0 | 5 | Approaching upper band |
| > 1.0 | 4 | Extended breakout |

**ADX (Average Directional Index)** - *Trend Strength Qualifier*
| ADX + Direction | Score | Interpretation |
|-----------------|-------|----------------|
| > 30 + uptrend | 9 | Strong uptrend - high confidence |
| 25-30 + uptrend | 7 | Moderate uptrend |
| 20-25 | 5 | Developing trend |
| < 20 | 4 | Weak/no trend - dampen signals |
| > 25 + downtrend | 2 | Strong downtrend - avoid |

**Volume Ratio** - *Breakout Confirmation*
| Condition | Score | Interpretation |
|-----------|-------|----------------|
| > 2.0x avg + up day | 9 | Breakout volume |
| 1.5-2.0x avg + up day | 7 | Accumulation |
| 1.0-1.5x avg | 5 | Normal volume |
| 1.5-2.0x avg + down day | 4 | Distribution |
| > 2.0x avg + down day | 2 | Panic selling |

The **technical_score** is the weighted average of all 6 indicator scores.

## Output Columns

| Column | Description |
|--------|-------------|
| symbol | Stock symbol |
| broker | Source broker (zerodha/groww) |
| name | Company name |
| quantity | Shares held |
| avg_price | Average purchase price |
| current_price | Latest price |
| pnl_pct | Profit/Loss % |
| rsi | RSI value (14-day) |
| rsi_score | RSI score (1-10) |
| macd_score | MACD score (1-10) |
| trend_score | Trend score (1-10) |
| bollinger_score | Bollinger score (1-10) |
| adx_score | ADX score (1-10) |
| volume_score | Volume score (1-10) |
| technical_score | Technical composite (1-10) |
| fundamental_score | Financials (1-10) |
| news_sentiment_score | News/analyst sentiment (1-10) |
| legal_corporate_score | Legal signals (1-10) |
| overall_score | Weighted final score |
| recommendation | STRONG BUY / BUY / HOLD / SELL / STRONG SELL |
| confidence | HIGH / MEDIUM / LOW - signal alignment |
| coverage | Data sources present (e.g., TFNL) |
| coverage_pct | % of analysis complete |
| gate_flags | Safety gates triggered |
| summary | Brief analysis summary |
| red_flags | Any severe concerns |

**Note:** The CSV includes a portfolio summary footer after the data rows. Use `pandas.read_csv(..., skipfooter=N)` or filter rows where `symbol` is empty to get clean tabular data.

## Sample Output

```
> analyze my portfolio from input/sample_zerodha.csv

● csv-parser - Done (5 stocks found)
● Running 5 data-fetcher agents in parallel...
● Batch 1: Analyzing RELIANCE, TCS, TATAPOWER (12 agents)
● Batch 2: Analyzing IRCTC, HAPPSTMNDS (8 agents)
● Running 5 scorer agents...
● Analysis complete!

| Symbol     | Score | Recommendation | Confidence |
|------------|-------|----------------|------------|
| RELIANCE   | 7.2   | BUY            | ●●● HIGH   |
| TCS        | 6.8   | BUY            | ●●○ MEDIUM |
| TATAPOWER  | 5.5   | HOLD           | ●●○ MEDIUM |
| IRCTC      | 6.1   | HOLD           | ●○○ LOW    | (gated: weak_trend)
| HAPPSTMNDS | 4.8   | HOLD           | ●○○ LOW    |

Report saved to: output/analysis_20260101_120000.csv
```

## Project Structure

```
portfolio-analyzer/
├── input/              # Put your CSV files here
├── output/             # Analysis reports generated here
├── .claude/agents/     # AI agent definitions
├── scripts/            # Python analysis scripts
├── data/
│   ├── holdings.json   # Parsed portfolio
│   ├── technical/      # Portfolio technical analysis
│   ├── scan_technical/ # Scanner verification results
│   ├── fundamentals/   # Fundamental research
│   ├── news/           # News sentiment
│   ├── legal/          # Legal/corporate signals
│   ├── scores/         # Final scores
│   ├── scans/          # Scanner results (timestamped)
│   ├── scan_history/   # Per-stock tracking history
│   └── watchlist.json  # Your tracked stocks
├── cache/ohlcv/        # Cached OHLCV data (18hr freshness)
└── dashboard/          # Interactive HTML dashboard
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

## Disclaimer

This tool is for informational purposes only. It does not constitute financial advice. Always do your own research and consult a qualified financial advisor before making investment decisions.
