# Portfolio Analyzer

A practical, opinionated toolkit for stock investors: run a quick check on your Zerodha/Groww/Vested holdings, scan the market for setups worth watching, and track everything over time. It's built to answer the everyday question: *"What should I look at first, and what should I ignore?"*

**MIT License · Python 3.13+**

> This is a personal hobby project. It's not production software, and it's not financial advice. Treat it as a second opinion, then do your own homework.

## Who It's For

- You already have a **Zerodha, Groww, or Vested portfolio** (India or US) and want a disciplined, repeatable "sanity check" instead of gut-feel.
- You like **technical signals** (RSI, MACD, trend) but don't want to manually pull charts for 20–50 stocks.
- You **scan for candidates**—oversold bounces, crossovers, breakouts—and want a pipeline to shortlist, track, and compare outcomes over time.
- You want to **track how your analysis changes** between runs—what got added, removed, or flagged differently.
- You're the **"tinker and extend" type** and want a working end-to-end setup you can fork and customize with your own rules.

## What You Get

- A **ranked view of your holdings** with simple recommendations (BUY / HOLD / SELL) plus a confidence level, so you know what deserves attention.
- **Technical analysis** across the core indicators (RSI, MACD, SMA trend, Bollinger context, ADX strength, volume confirmation).
- **Lightweight fundamental and narrative context** pulled via AI web research (results, valuation, growth) so the output isn't just numbers.
- **News + legal/corporate signals** rolled up into a "anything weird going on?" layer.
- A **stock scanner** with OHLCV-validated confluence ranking (2-week breakout, 2-month pullback, support reversal setups).
- **Event-sourced watchlists**: record *what/why/entry/invalidation/timing/re-entry* for each pick, track outcomes with snapshots.
- **Portfolio snapshots**: compare analysis runs over time—see what changed, what improved, what got worse.
- **Report archiving**: automatically archive each analysis report with a date-stamped filename; compare to previous runs on demand.

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
git clone https://github.com/gaurav-yadav/portfolio-analyzer.git
cd portfolio-analyzer
uv sync
```

### Run Portfolio Analysis

1. Export your holdings CSV from your broker:
   - **Zerodha:** Console → Portfolio → Holdings → Download CSV
   - **Groww:** Stocks → Holdings → Export
   - **Vested (US):** Portfolio → Export

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

## Three Primary Jobs

### A) Analyze Your Holdings

Best for: checking portfolio health, getting sell/hold/buy signals on stocks you own.

```
analyze my portfolio from input/zerodha.csv
```

**What happens:**
1. Parse CSV → extract holdings (supports Zerodha, Groww, Vested, or any clean CSV)
2. Fetch 1 year of price data (Yahoo Finance)
3. Run 4 parallel analyses per stock:
   - Technical indicators
   - Fundamental research (web search)
   - News sentiment (web search)
   - Legal/corporate signals (web search)
4. Check research freshness (30-day staleness policy)—only refresh what's needed
5. Score each stock (1-10) with safety gates
6. Generate reports:
   - `output/analysis_YYYYMMDD_HHMMSS.csv`
   - `data/portfolios/<portfolio_id>/report.md`
   - `data/portfolios/<portfolio_id>/snapshots/<run_id>.json`
7. Archive the report and offer comparison to previous runs

**Compare to previous analysis:**
```
compare to last time
```

### B) Scan → Validate → Track

Best for: discovering new opportunities, building a watchlist with full context.

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

**Step 2: Validate** — Run OHLCV-based confluence ranking

The scanner automatically enriches picks with:
- **2-week breakout score**: Is the stock setting up for a near-term breakout?
- **2-month pullback score**: Is this a quality stock in a healthy pullback?
- **Support reversal score**: Is the stock bouncing off a key level?

Output includes ranked shortlists for each setup type.

**Step 3: Add to Watchlist** — Track your picks with full context

```
add RVNL to watchlist swing_trades
```

Each watchlist entry captures:
- **Setup type**: 2w_breakout, 2m_pullback, support_reversal
- **Horizon**: 2w, 2m
- **Entry zone**: price range to consider buying
- **Invalidation**: when the thesis is broken
- **Timing**: when to act
- **Re-entry policy**: what to do if stopped out

**Step 4: Monitor** — Track performance over time

```
watch my portfolio
```

### C) Monitor IPOs

Best for: tracking upcoming IPOs and scoring them.

```
scan upcoming IPOs
```

Maintains a single versioned IPO database (`data/ipos.json`) with research, scores, and rankings.

---

## Event-Sourced Watchlists (v2)

Watchlists are now event-sourced for full auditability:

```
data/watchlists/<watchlist_id>/
├── events.jsonl      # Source of truth (append-only)
├── watchlist.json    # Materialized view (rebuilt from events)
└── snapshots/        # Per-run snapshots for tracking
    └── <run_id>.json
```

Each ADD event captures the agent's judgment:
- Setup type, horizon, entry zone
- Invalidation rule, timing notes, re-entry policy
- Source scan file, reason, tags

Commands:
```bash
# Add to watchlist
uv run python scripts/watchlist_events.py add swing_trades RVNL \
  --setup 2w_breakout --horizon 2w \
  --entry-zone "240-250" --invalidation "close below 230" \
  --reason "Strong volume, near breakout level"

# Remove from watchlist
uv run python scripts/watchlist_events.py remove swing_trades RVNL --reason "Hit target"

# Rebuild view from events
uv run python scripts/watchlist_events.py rebuild swing_trades

# Write snapshot
uv run python scripts/watchlist_snapshot.py swing_trades

# Generate report
uv run python scripts/watchlist_report.py swing_trades
```

---

## Portfolio Snapshots & Report Archiving

Every portfolio analysis creates:

1. **Snapshot**: `data/portfolios/<portfolio_id>/snapshots/<run_id>.json`
   - Full portfolio state at that point in time
   - Score distribution, top/bottom holdings
   - Delta vs previous snapshot (what changed)

2. **Archived report**: `data/portfolios/<portfolio_id>/reports/<DD-MM-YYYY>-<slug>.md`
   - Human-readable markdown report
   - Actionable insights, risk flags, recommendations

Compare runs over time:
```
compare to last time
```
or
```
compare to 15-01-2026-gaurav-us.md
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
├── input/                    # Put your CSV files here
├── output/                   # Analysis reports (CSV)
├── dashboard/                # HTML dashboard (index.html)
├── scripts/                  # Python analysis scripts
├── utils/                    # Shared config and helpers
├── data/
│   ├── holdings.json         # Parsed portfolio
│   ├── technical/            # Technical analysis (portfolio)
│   ├── scan_technical/       # Technical analysis (scanner)
│   ├── fundamentals/         # Fundamental research
│   ├── news/                 # News sentiment
│   ├── legal/                # Legal signals
│   ├── scores/               # Final scores
│   ├── scans/                # Scanner results
│   ├── watchlists/           # Event-sourced watchlists (v2)
│   │   └── <watchlist_id>/
│   │       ├── events.jsonl
│   │       ├── watchlist.json
│   │       └── snapshots/
│   ├── portfolios/           # Portfolio snapshots & reports
│   │   └── <portfolio_id>/
│   │       ├── holdings.json
│   │       ├── report.md
│   │       ├── reports/      # Archived reports
│   │       └── snapshots/
│   ├── runs/                 # Per-run decision logs
│   └── ipos.json             # IPO database
├── cache/ohlcv/              # Cached price data (parquet)
├── .claude/agents/           # AI agent definitions
└── docs/                     # Detailed documentation
```

---

## Agent Roster

The system uses specialized AI agents for different workflows:

**Portfolio Analysis Agents:**
- `portfolio-analyzer` — End-to-end analysis: import → fetch → technicals → research → score → report → snapshot
- `portfolio-importer` — Universal importer for any holdings CSV format (India/US)
- `csv-parser` — Parse Zerodha/Groww CSV exports into canonical holdings JSON
- `portfolio-watcher` — Lightweight monitoring: surface signals with context (not hard gates)
- `data-fetcher` — Fetch OHLCV data from Yahoo Finance
- `technical-analyst` — Compute technical indicators (RSI, MACD, SMA, Bollinger, ADX, Volume)
- `fundamentals-researcher` — Research fundamental data (P/E, revenue growth, quarterly results) via web search
- `news-sentiment` — Analyze recent news and market sentiment via web search
- `legal-corporate` — Search for legal issues, red flags, and corporate actions via web search
- `scorer` — Aggregate all analysis scores and generate final stock recommendations

**Watchlist Agents:**
- `watchlist-manager` — Manage event-sourced watchlists: add/remove/note events, rebuild view, validate, snapshot

**Stock Scanner Agents:**
- `scanner` — Smart scanner: web-search discovery + OHLCV confluence ranking (2w breakout + 2m pullback + reversal)
- `scan-validator` — Enrich scan picks with OHLCV confluence and annotate + rank the scan JSON
- `breakout-crosscheck` — Manual cross-check to shortlist 1-2 week breakout setups (no web search)
- `reversal-crosscheck` — Manual cross-check to shortlist support-reversal setups (no web search)
- `fundamental-scanner` — Small/Mid cap growth + quality discovery (fundamental-first)

**IPO Agents:**
- `ipo-scanner` — Find upcoming/open Indian IPOs via web search, maintain versioned IPO database
- `ipo-researcher` — Deep-dive research for a single IPO via web search
- `ipo-scorer` — Score IPOs using a simple rubric

---

## Contributing

### Dev Setup

```bash
git clone https://github.com/gaurav-yadav/portfolio-analyzer.git
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
- Workflow steps

See [CLAUDE.md](CLAUDE.md) for workflow orchestration.

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
