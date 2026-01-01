# Portfolio Analyzer

A practical, opinionated toolkit for Indian stock investors: run a quick check on your Zerodha/Groww holdings, or scan the market for setups worth putting on a watchlist. It's built to answer the everyday question: *"What should I look at first, and what should I ignore?"*

**MIT License · Python 3.13+**

> This is a personal hobby project. It's not production software, and it's not financial advice. Treat it as a second opinion, then do your own homework.

## Who It's For

- You already have a **Zerodha or Groww portfolio** and want a disciplined, repeatable "sanity check" instead of gut-feel.
- You like **technical signals** (RSI, MACD, trend) but don't want to manually pull charts for 20–50 stocks.
- You **scan for candidates**—oversold bounces, crossovers, breakouts—and want a simple pipeline to shortlist and track them.
- You're the **"tinker and extend" type** and want a working end-to-end setup you can fork and customize with your own rules.

## What You Get

- A **ranked view of your holdings** with simple recommendations (BUY / HOLD / SELL) plus a confidence level, so you know what deserves attention.
- **Technical analysis** across the core indicators (RSI, MACD, SMA trend, Bollinger context, ADX strength, volume confirmation).
- **Lightweight fundamental and narrative context** pulled via AI web research (results, valuation, growth) so the output isn't just numbers.
- **News + legal/corporate signals** rolled up into a "anything weird going on?" layer.
- A **stock scanner** for common setups (RSI oversold, MACD crossover, golden cross, volume breakouts, 52-week strength).
- A **watchlist flow**: add a pick, record an entry price + reason, and track performance over time.

## Demo

<img width="1113" alt="Dashboard showing portfolio analysis with scores and recommendations" src="https://github.com/user-attachments/assets/78b377b9-4848-4321-8e69-3af09bd39c68" />

<details>
<summary>More screenshots</summary>

<img width="423" alt="Stock detail view showing technical indicators" src="https://github.com/user-attachments/assets/05fd1a5a-fa04-4f04-84b1-4e47e4fc9de8" />

</details>

---

## Quickstart (60 seconds)

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) — required (orchestrates the AI agents)
- [uv](https://github.com/astral-sh/uv) — Python package manager
- Python 3.13+

### Setup

```bash
git clone https://github.com/yourusername/portfolio-analyzer.git
cd portfolio-analyzer
uv sync
```

### Run Portfolio Analysis

1. Export your holdings CSV from your broker:
   - **Zerodha:** Console → Portfolio → Holdings → Download CSV
   - **Groww:** Stocks → Holdings → Export

2. Place the CSV in `input/` and start Claude Code:

```bash
claude
```

3. Tell Claude to analyze:

```
analyze my portfolio from input/your_holdings.csv
```

### Run Stock Scanner

```
run stock scanner
```

### Open Dashboard

Open `dashboard/index.html` in your browser, then load your analysis CSV.

---

## Two Ways to Use

### A) Analyze Your Holdings

Best for: checking portfolio health, getting sell/hold/buy signals on stocks you own.

```
analyze my portfolio from input/zerodha.csv
```

**What happens:**
1. Parse CSV → extract holdings
2. Fetch 1 year of price data (Yahoo Finance)
3. Run 4 parallel analyses per stock:
   - Technical indicators
   - Fundamental research (web search)
   - News sentiment (web search)
   - Legal/corporate signals (web search)
4. Score each stock (1-10) with safety gates
5. Generate `output/analysis_YYYYMMDD_HHMMSS.csv`

### B) Scan → Verify → Track

Best for: discovering new opportunities, building a watchlist.

**Step 1: Scan** — Find candidates via web search of screener sites

```
run stock scanner
```

Searches Chartink, Trendlyne, Groww, etc. for:
- RSI Oversold (< 30)
- MACD Crossover
- Golden Cross (SMA50 > SMA200)
- Volume Breakout
- 52-Week High

**Step 2: Verify** — Run full technical analysis on picks

```bash
uv run python scripts/verify_scan.py SYMBOL1 SYMBOL2 SYMBOL3
```

Output:
```
Symbol       Score   Rec          RSI      MACD     Trend        52W
RVNL         8.0     STRONG BUY   38.0     Bullish  STRONG UP    5.2% off
IREDA        7.0     BUY          45.0     Bullish  STRONG UP    8.1% off
```

**Step 3: Watchlist** — Track your picks

```bash
# Add to watchlist
uv run python scripts/watchlist.py add RVNL rsi_oversold 245.50

# View watchlist
uv run python scripts/watchlist.py list -p

# Track performance
uv run python scripts/track_performance.py
```

---

## Output

### CSV Location

Reports are saved to `output/analysis_YYYYMMDD_HHMMSS.csv`.

### Key Columns

| Column | Description |
|--------|-------------|
| `symbol` | Stock symbol |
| `overall_score` | Weighted final score (1-10) |
| `recommendation` | STRONG BUY / BUY / HOLD / SELL / STRONG SELL |
| `confidence` | HIGH / MEDIUM / LOW |
| `rsi`, `rsi_score` | RSI value and score |
| `macd_score`, `trend_score` | Individual indicator scores |
| `technical_score` | Technical composite |
| `fundamental_score` | Financials (1-10) |
| `news_sentiment_score` | News/analyst sentiment |
| `coverage` | Data sources present (T=technical, F=fundamental, N=news, L=legal) |

> **Note:** The CSV includes a portfolio summary footer after data rows. When using pandas: `pd.read_csv(..., skipfooter=N)` or filter rows where `symbol` is not empty.

### Dashboard

Open `dashboard/index.html` in any browser. Click "Select CSV File" to load your analysis. Features:
- Sort by score, recommendation, or any column
- Click a row for detailed breakdown
- Visual charts for score distribution

---

## Scoring Overview

| Component | Weight |
|-----------|--------|
| Technical | 35% |
| Fundamental | 30% |
| News Sentiment | 20% |
| Legal/Corporate | 15% |

| Score | Recommendation |
|-------|----------------|
| 8.0+ | STRONG BUY |
| 6.5 - 7.9 | BUY |
| 4.5 - 6.4 | HOLD |
| 3.0 - 4.4 | SELL |
| < 3.0 | STRONG SELL |

**Safety gates** prevent bad recommendations:
- Trend < 5 → caps at HOLD (no buying into downtrends)
- High news + low technicals → downgrades BUY to HOLD (no hype-only buys)
- STRONG BUY requires aligned trend, MACD, and ADX

See [docs/scoring.md](docs/scoring.md) for complete methodology.

---

## Configuration

All thresholds are in `utils/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CACHE_FRESHNESS_HOURS` | 18 | How long to cache OHLCV data |
| `COMPONENT_WEIGHTS` | See file | Technical/fundamental/news/legal weights |
| `THRESHOLDS` | See file | Score cutoffs for recommendations |
| `GATES` | See file | Safety gate thresholds |

### Planned Configuration

These should be configurable but currently require code changes:

| Setting | Current | Location |
|---------|---------|----------|
| Fetch delay between stocks | 2s | `scripts/fetch_all.py` |
| Batch size for agents | 3-5 | `CLAUDE.md` orchestration |
| Technical indicator weights | Equal (1/6) | `utils/config.py` |

---

## Limitations & Data Accuracy

**Yahoo Finance caveats:**
- Data may be 15-20 minutes delayed
- Some thinly traded stocks have gaps or stale quotes
- Corporate actions (splits, bonuses) may cause temporary anomalies

**Throttling:**
- Fetches are sequential with delays to avoid rate limits
- Large portfolios (20+ stocks) take several minutes
- Web search agents run in batches of 3-5

**Coverage:**
- Small-cap stocks may have limited fundamental/news coverage
- Some analysis components may return empty (reflected in `coverage` column)

See [docs/data-sources.md](docs/data-sources.md) for complete data flow.

---

## Project Structure

```
portfolio-analyzer/
├── input/              # Put your CSV files here
├── output/             # Analysis reports
├── dashboard/          # HTML dashboard (index.html)
├── scripts/            # Python analysis scripts
├── utils/              # Shared config and helpers
├── data/
│   ├── holdings.json   # Parsed portfolio
│   ├── technical/      # Technical analysis (portfolio)
│   ├── scan_technical/ # Technical analysis (scanner)
│   ├── fundamentals/   # Fundamental research
│   ├── news/           # News sentiment
│   ├── legal/          # Legal signals
│   ├── scores/         # Final scores
│   ├── scans/          # Scanner results
│   └── watchlist.json  # Tracked stocks
├── cache/ohlcv/        # Cached price data (parquet)
├── .claude/agents/     # AI agent definitions
└── docs/               # Detailed documentation
```

---

## Roadmap

- [ ] Support for BSE stocks (`.BO` suffix)
- [ ] Email/Slack alerts for watchlist price targets
- [ ] Historical score tracking (see how recommendations changed)
- [ ] Export to Google Sheets
- [ ] Custom screener queries
- [ ] Options chain analysis
- [ ] Mutual fund holdings overlap detection
- [ ] Docker container for isolated execution
- [ ] API mode (JSON output)
- [ ] Backtest recommendations against historical returns

---

## Contributing

### Dev Setup

```bash
git clone https://github.com/yourusername/portfolio-analyzer.git
cd portfolio-analyzer
uv sync
```

### Adding New Scanners

1. Add search queries to `.claude/agents/scanner.md`
2. Add scan type to `scripts/save_scan.py`

### Adding New Indicators

1. Add calculation to `scripts/technical_analysis.py`
2. Add scoring logic to `scripts/score_stock.py`
3. Update weights in `utils/config.py`

### Agent Definitions

Agent behavior is defined in `.claude/agents/*.md`. Each file specifies:
- Input/output format
- Data sources
- Scoring logic

---

## Security

If you discover a security vulnerability, please email the maintainer directly rather than opening a public issue.

---

## Disclaimer

This tool is for **informational purposes only**. It does not constitute financial advice. The recommendations are based on technical and fundamental signals, not personalized investment advice.

- Past performance does not guarantee future results
- Always do your own research (DYOR)
- Consult a qualified financial advisor before making investment decisions
- The authors are not responsible for any financial losses

---

## License

[MIT](LICENSE)
