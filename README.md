# Portfolio Analyzer

AI-powered stock portfolio analyzer for Indian brokers (Zerodha/Groww). Uses Claude Code agents to analyze your holdings with technical indicators, fundamental research, news sentiment, and legal/corporate signals.

## Features

- **CSV Import** - Drop your Zerodha or Groww holdings CSV
- **Technical Analysis** - RSI, MACD, SMA, Bollinger Bands, ADX
- **Fundamental Research** - Quarterly results, P/E ratios, growth metrics
- **News Sentiment** - Recent news, analyst ratings, target prices
- **Legal Signals** - SEBI issues, lawsuits, major contracts
- **Scoring System** - Weighted scores with BUY/HOLD/SELL recommendations

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

## What Happens

```
1. Parse your CSV → extract holdings
2. Fetch OHLCV data from Yahoo Finance (5 stocks in parallel)
3. For each stock, run 4 analyses in parallel:
   - Technical indicators (RSI, MACD, SMA, Bollinger, ADX)
   - Fundamental research (quarterly results, P/E, growth)
   - News sentiment (recent news, analyst ratings)
   - Legal/corporate signals (SEBI, lawsuits, contracts)
4. Score each stock
5. Generate final report with recommendations
```

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

Each indicator is scored 1-10 (higher = more bullish):

**RSI (Relative Strength Index)**
| RSI Value | Score | Interpretation |
|-----------|-------|----------------|
| < 30 | 9 | Oversold - potential buying opportunity |
| 30-40 | 7 | Approaching oversold |
| 40-60 | 5 | Neutral |
| 60-70 | 4 | Approaching overbought |
| > 70 | 2 | Overbought - potential selling signal |

**MACD (Moving Average Convergence Divergence)**
| Condition | Score | Interpretation |
|-----------|-------|----------------|
| MACD > Signal & rising | 8 | Strong bullish momentum |
| MACD > Signal | 6 | Bullish |
| MACD < Signal | 4 | Bearish |
| MACD < Signal & falling | 2 | Strong bearish momentum |

**Trend (SMA 50/200)**
| Condition | Score | Interpretation |
|-----------|-------|----------------|
| Price > SMA50 > SMA200 | 9 | Strong uptrend (Golden setup) |
| Price > SMA50 | 6 | Short-term uptrend |
| Price < SMA50 < SMA200 | 2 | Strong downtrend |

**Bollinger Bands (%B)**
| %B Value | Score | Interpretation |
|----------|-------|----------------|
| < 0.2 | 8 | Near lower band - potential bounce |
| 0.2 - 0.8 | 5 | Normal range |
| > 0.8 | 3 | Near upper band - potential pullback |

**ADX (Average Directional Index)**
| ADX + Direction | Score | Interpretation |
|-----------------|-------|----------------|
| > 25 + uptrend | 8 | Strong bullish trend |
| > 25 + downtrend | 3 | Strong bearish trend |
| < 20 | 5 | Weak/no trend |

**Volume Ratio**
| Condition | Score | Interpretation |
|-----------|-------|----------------|
| > 1.5x avg + up day | 8 | High volume buying |
| > 1.5x avg + down day | 3 | High volume selling |
| Normal volume | 5 | No significant signal |

The **technical_score** is the average of all 6 indicator scores.

## Output Columns

| Column | Description |
|--------|-------------|
| symbol | Stock symbol |
| name | Company name |
| quantity | Shares held |
| current_price | Latest price |
| pnl_pct | Profit/Loss % |
| technical_score | Technical indicators (1-10) |
| fundamental_score | Financials (1-10) |
| news_sentiment_score | News/analyst sentiment (1-10) |
| legal_corporate_score | Legal signals (1-10) |
| overall_score | Weighted final score |
| recommendation | STRONG BUY / BUY / HOLD / SELL / STRONG SELL |
| red_flags | Any severe concerns |
| summary | Brief analysis summary |

## Sample Output

```
> analyze my portfolio from input/sample_zerodha.csv

● csv-parser - Done (5 stocks found)
● Running 5 data-fetcher agents in parallel...
● Batch 1: Analyzing RELIANCE, TCS, TATAPOWER (12 agents)
● Batch 2: Analyzing IRCTC, HAPPSTMNDS (8 agents)
● Running 5 scorer agents...
● Analysis complete!

| Symbol | Score | Recommendation |
|--------|-------|----------------|
| RELIANCE | 7.2 | BUY |
| TCS | 6.8 | BUY |
| TATAPOWER | 5.5 | HOLD |
| IRCTC | 6.1 | HOLD |
| HAPPSTMNDS | 4.8 | HOLD |

Report saved to: output/analysis_20260101_120000.csv
```

## Project Structure

```
portfolio-analyzer/
├── input/              # Put your CSV files here
├── output/             # Analysis reports generated here
├── .claude/agents/     # AI agent definitions (7 agents)
├── scripts/            # Python analysis scripts
├── data/               # Intermediate analysis data
└── cache/              # Cached market data (18hr freshness)
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

## Disclaimer

This tool is for informational purposes only. It does not constitute financial advice. Always do your own research and consult a qualified financial advisor before making investment decisions.
