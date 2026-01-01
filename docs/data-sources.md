# Data Sources

This document explains where Portfolio Analyzer gets its data and any limitations.

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Yahoo Finance  │────>│  Technical Data  │────>│  Technical      │
│  (yfinance)     │     │  (OHLCV)         │     │  Analysis       │
└─────────────────┘     └──────────────────┘     └─────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Web Search     │────>│  Multiple Sites  │────>│  Fundamentals   │
│  (Claude)       │     │  (see below)     │     │  News/Legal     │
└─────────────────┘     └──────────────────┘     └─────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Broker CSV     │────>│  Holdings Parse  │────>│  Portfolio      │
│  (Zerodha/Groww)│     │  (scripts/)      │     │  Data           │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Technical Data: Yahoo Finance

**Source:** [Yahoo Finance](https://finance.yahoo.com/) via the [yfinance](https://github.com/ranaroussi/yfinance) Python library.

### What We Fetch
- **OHLCV:** Open, High, Low, Close, Volume
- **Period:** 1 year of daily data
- **Symbols:** NSE suffix (e.g., `RELIANCE.NS`, `TCS.NS`)

### Caching
- **Location:** `cache/ohlcv/<SYMBOL>.parquet`
- **Freshness:** 18 hours (configurable in `utils/config.py`)
- **Format:** Apache Parquet (efficient columnar storage)

### Rate Limiting
- Fetches are sequential with throttling
- Exponential backoff on failures (2s → 4s → 8s)
- Batch scripts use 2-second delays between stocks

### Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Delayed data | Quotes may be 15-20 minutes delayed | Use end-of-day analysis, not intraday |
| Corporate actions | Splits/bonuses may cause price gaps | Yahoo adjusts historical data |
| Thin liquidity stocks | May have missing or stale data | Flag stocks with < 1000 avg volume |
| API rate limits | Too many requests = temporary block | Sequential fetching + cache |
| Symbol mismatches | Some NSE symbols differ | Use `.NS` suffix consistently |

---

## Fundamental & Sentiment Data: Web Search

Fundamental, news, and legal data are gathered via Claude's WebSearch tool, searching financial news sites and databases.

### Sources Searched

| Category | Primary Sources |
|----------|-----------------|
| Fundamentals | Screener.in, Moneycontrol, Economic Times |
| News/Sentiment | Moneycontrol, Economic Times, LiveMint, Reuters |
| Legal/Corporate | SEBI website, BSE filings, news archives |
| Analyst Ratings | Trendlyne, ICICI Direct, Motilal Oswal |

### What Each Agent Searches

**Fundamentals Researcher:**
- Quarterly results (revenue, profit, margins)
- P/E ratio, P/B ratio
- Revenue/profit growth (YoY, QoQ)
- Debt-to-equity ratio
- Promoter holding changes

**News Sentiment:**
- Recent company news (last 30 days)
- Analyst recommendations and target prices
- Sector outlook and peer comparisons
- Earnings surprises

**Legal/Corporate:**
- SEBI actions or warnings
- Ongoing lawsuits or disputes
- Major contract wins/losses
- Management changes
- Related party transactions

### Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Stale search results | Old news may surface | Agents prioritize recent results |
| Conflicting information | Different sources disagree | Agents note source and date |
| Small-cap coverage | Limited analyst coverage | May result in lower confidence |
| Pay-walled content | Some premium data inaccessible | Use free sources only |

---

## Scanner Data: Screener Sites

The stock scanner uses web search to find stocks from existing screener sites.

### Sources by Scan Type

| Scan | Primary Sources |
|------|-----------------|
| RSI Oversold | Chartink, Trendlyne, Groww, Dhan |
| MACD Crossover | Chartink, TopStockResearch |
| Golden Cross | Trendlyne, 5paisa, Dhan |
| Volume Breakout | NSE India, Dhan |
| 52-Week High | NSE India, Groww |

### Site Details

- **[Chartink](https://chartink.com/)** - Technical screeners (RSI, MACD, volume)
- **[Trendlyne](https://trendlyne.com/)** - Comprehensive screens + fundamentals
- **[Groww](https://groww.in/)** - Retail-focused screens
- **[Dhan](https://dhan.co/)** - Technical screens, option data
- **[5paisa](https://www.5paisa.com/)** - Technical screens
- **[NSE India](https://www.nseindia.com/)** - Official exchange data
- **[TopStockResearch](https://www.topstockresearch.com/)** - MACD signals

### Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Site changes | Screeners may change format | Agents adapt search queries |
| Delayed updates | Lists may not be real-time | Verify with technical analysis |
| Duplicate listings | Same stock on multiple sites | Deduplication in save_scan.py |

---

## Portfolio Data: Broker CSVs

### Supported Formats

**Zerodha (Kite):**
- Export: Console → Portfolio → Holdings → Download CSV
- Columns: Instrument, Qty, Avg. cost, LTP, Cur. val, P&L, Day chg, Net chg

**Groww:**
- Export: Stocks → Holdings → Export
- Columns: Company Name, Symbol, Quantity, Avg Price, Current Price, Invested, Current Value

### Currency Handling
The CSV parser automatically strips currency prefixes:
- `₹`, `Rs.`, `Rs`, `INR` → removed
- Commas in numbers → removed
- Negative values → preserved

### Duplicate Handling
When the same symbol+broker appears multiple times:
- Quantities are summed
- Average price is recalculated (weighted average)

---

## Data Freshness Summary

| Data Type | Source | Cache Duration | Refresh Trigger |
|-----------|--------|----------------|-----------------|
| OHLCV | Yahoo Finance | 18 hours | Automatic |
| Technical | Computed | Per-run | Manual |
| Fundamentals | Web Search | Per-run | Manual |
| News | Web Search | Per-run | Manual |
| Legal | Web Search | Per-run | Manual |
| Scan Results | Web Search | Timestamped | Manual |

---

## Troubleshooting

### "No data found for symbol"
- Check symbol suffix (should be `.NS` for NSE)
- Verify symbol exists on Yahoo Finance
- Some recently listed stocks may not have history

### "Stale cache"
- Delete specific cache file: `rm cache/ohlcv/SYMBOL.parquet`
- Or clear all: `uv run python scripts/clean.py` (keeps cache by default)
- Force refresh: delete cache and re-run fetch

### "Rate limit exceeded"
- Wait 5-10 minutes before retrying
- Reduce batch size in fetch scripts
- Use cached data when possible

### "Agent returned empty results"
- Web search may have failed
- Check internet connectivity
- Retry the specific agent
