# Architecture

**Portfolio Analyzer** — deterministic scripts + Claude Code AI agents.

> Scripts do transforms. Agents do thinking.

---

## System Overview

The system is split into three primary jobs:

1. **Stock Scanner + Watchlists** — discover candidates, rank by OHLCV confluence, track with full context
2. **Portfolio Analysis** — import holdings, compute technicals, research, score, archive reports
3. **IPO Scanner** — maintain a versioned IPO database, research, score

All workflows follow the same pattern: agents decide *what/why*, deterministic scripts execute *state writes*.

---

## Repository Layout

```
portfolio-analyzer/
├── .claude/agents/           # AI agent definitions (19 agents)
├── scripts/                  # Deterministic Python scripts
├── utils/                    # Shared config + helpers
├── specs/                    # Canonical schemas and rules
├── docs/                     # Scoring, indicators, data-source docs
├── dashboard/                # Static HTML dashboard (index.html loads CSV)
├── input/                    # Drop broker CSV exports here
├── output/                   # Global analysis CSV (compile_report, no portfolio filter)
├── data/
│   ├── holdings.json         # Active portfolio (global fallback)
│   ├── ipos.json             # IPO database (versioned, single file)
│   ├── portfolios/<id>/
│   │   ├── holdings.json
│   │   ├── report.md         # Latest markdown report (agent-written)
│   │   ├── reports/          # Archived reports: DD-MM-YYYY-slug.md
│   │   └── snapshots/        # Per-run score snapshots
│   ├── watchlists/<id>/
│   │   ├── events.jsonl      # Source of truth (append-only)
│   │   ├── watchlist.json    # Materialized view (rebuilt from events)
│   │   └── snapshots/        # Per-run snapshots
│   ├── scans/                # scan_*.json (scanner output)
│   ├── technical/            # <symbol>.json (portfolio technicals)
│   ├── scan_technical/       # <symbol>.json (scanner technicals)
│   ├── fundamentals/         # <symbol>.json (web research)
│   ├── news/                 # <symbol>.json (news sentiment)
│   ├── legal/                # <symbol>.json (legal/corporate)
│   ├── scores/               # <symbol>.json (final scores)
│   ├── watcher/              # watch_YYYYMMDD_HHMMSS.json (watcher reports)
│   ├── runs/<run_id>/        # decisions.md, research_status.json (per-run audit)
│   └── suggestions/
│       ├── ledger.jsonl      # All logged suggestions (append-only)
│       └── outcomes/         # YYYY-MM.jsonl monthly resolution files
├── cache/ohlcv/              # <symbol>.parquet (18h cache, never committed)
├── main.py                   # Placeholder entry point
└── pyproject.toml            # Python 3.13+ deps: yfinance, pandas, pandas-ta, pyarrow
```

---

## All Agents

Agents live in `.claude/agents/*.md`. They orchestrate workflows and do web research. They never write data directly — they call scripts.

### Portfolio Workflow

| Agent | Description | Key Scripts Called |
|-------|-------------|-------------------|
| `portfolio-analyzer` | End-to-end: import → fetch → technicals → research → score → report → snapshot → archive | `fetch_all.py`, `technical_all.py`, `research_status.py`, `score_all.py`, `compile_report.py`, `portfolio_snapshot.py`, `portfolio_report_archive.py` |
| `portfolio-importer` | Universal CSV import (any format, India/US) | `portfolio_importer.py`, `holdings_validate.py` |
| `csv-parser` | Zerodha/Groww CSV parsing → canonical holdings JSON | `parse_csv.py`, `holdings_validate.py` |
| `portfolio-watcher` | Lightweight monitoring: signals with context (not hard gates) | `fetch_all.py`, `technical_all.py`, `watch_portfolio.py`, `watchlist_snapshot.py` |
| `data-fetcher` | Fetch OHLCV from Yahoo Finance for a symbol | `fetch_ohlcv.py` |
| `technical-analyst` | Compute RSI, MACD, SMA, Bollinger, ADX, Volume | `technical_analysis.py` |

### Research

| Agent | Description | Writes To |
|-------|-------------|-----------|
| `fundamentals-researcher` | P/E, revenue growth, quarterly results via web search | `data/fundamentals/<symbol>.json` |
| `news-sentiment` | Recent news + analyst sentiment via web search | `data/news/<symbol>.json` |
| `legal-corporate` | Legal issues, red flags, corporate actions via web search | `data/legal/<symbol>.json` |
| `scorer` | Aggregate all scores → final recommendation | `scripts/score_stock.py` → `data/scores/<symbol>.json` |

### Scanner

| Agent | Description | Key Scripts |
|-------|-------------|-------------|
| `scanner` | 5-type web search discovery + OHLCV confluence ranking | `validate_scan.py`, `watchlist_events.py` |
| `scan-validator` | Enrich existing scan with OHLCV confluence; annotate + rank | `validate_scan.py` |
| `breakout-crosscheck` | Review `2w_breakout` shortlist from enriched scan (no web search) | reads scan JSON |
| `reversal-crosscheck` | Review `support_reversal` shortlist from enriched scan (no web search) | reads scan JSON |
| `fundamental-scanner` | Small/mid cap growth+quality discovery (fundamental-first, web search) | writes `data/scans/fundamental_scan_*.json` |

### Watchlist

| Agent | Description | Key Scripts |
|-------|-------------|-------------|
| `watchlist-manager` | Event management: add/remove/note/rebuild/validate/snapshot (no web search) | `watchlist_events.py`, `watchlist_snapshot.py`, `watchlist_report.py` |

### IPO

| Agent | Description | Key Files |
|-------|-------------|-----------|
| `ipo-scanner` | Discover upcoming/open IPOs via web search; merge into `data/ipos.json` | `validate_ipos.py`, `render_ipos.py` |
| `ipo-researcher` | Deep-dive research for a single IPO; update `data/ipos.json` | `data/ipos.json` |
| `ipo-scorer` | Score IPOs using rubric (business/financial/valuation/governance); write scores back | `data/ipos.json`, `validate_ipos.py`, `render_ipos.py` |

---

## All Scripts

### Portfolio

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `portfolio_importer.py` | Universal CSV import → canonical holdings JSON | `--portfolio-id`, `--country`, `--platform` |
| `parse_csv.py` | Zerodha/Groww broker CSV → holdings JSON | positional file(s) |
| `holdings_validate.py` | Normalize + validate holdings JSON | `--portfolio-id`, `--country`, `--platform` |
| `portfolio_snapshot.py` | Create timestamped portfolio snapshot from scores | `--portfolio-id`, `--run-id` |
| `portfolio_report_archive.py` | Archive report.md with date-stamp; list previous reports | `--portfolio-id`, `--list`, `--json` |
| `compile_report.py` | Compile scores → CSV analysis report | `--portfolio-id` |
| `research_status.py` | Check research freshness (30-day staleness gate) | `--holdings`, `--days`, `--out` |

### Data + Analysis

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `fetch_ohlcv.py` | Fetch 1yr OHLCV for one symbol; parquet cache | positional symbol |
| `fetch_us_ohlcv.py` | US-specific OHLCV fetch | positional symbol |
| `fetch_all.py` | Batch OHLCV fetch (holdings and/or watchlist) | `--holdings`, `--watchlist-id`, `--symbols` |
| `technical_analysis.py` | Single-symbol technical indicators | positional symbol |
| `compute_technicals.py` | Core indicator computation module | (imported by others) |
| `deep_technical_analysis.py` | Extended/deeper technical analysis | positional symbol |
| `technical_all.py` | Batch technical analysis | `--holdings`, `--watchlist-id` |
| `score_stock.py` | Score one stock from all analysis data | positional symbol, `--broker`, `--profile` |
| `score_all.py` | Batch scoring for all holdings | `--profile` |
| `watch_portfolio.py` | Lightweight portfolio watcher; writes to `data/watcher/` | `--holdings`, `--watchlist-id`, `--symbols` |
| `clean.py` | Clear stale/old data files | various |

### Scanner

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `save_scan.py` | Save aggregated scan results to `data/scans/scan_*.json` | (imported as module) |
| `verify_scan.py` | OHLCV-based technical verification for scan symbols | various |
| `validate_scan.py` | Enrich scan with OHLCV confluence; compute setup scores; rank | `--enrich-setups`, `--rank`, `--top`, `--us`, `--output` |
| `scan_and_log.py` | **Run enrichment → log top picks to suggestions ledger** | `--scan`, `--top`, `--setup`, `--dry-run` |

### Watchlist

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `watchlist_events.py` | Append/rebuild/validate events | `add`, `remove`, `note`, `rebuild`, `validate` subcommands |
| `watchlist_snapshot.py` | Create per-run snapshot of watchlist state | positional `watchlist_id` |
| `watchlist_report.py` | Render history report for a watchlist | positional `watchlist_id` |

### IPO

| Script | Purpose |
|--------|---------|
| `validate_ipos.py` | Schema validation for `data/ipos.json` |
| `render_ipos.py` | Render IPO database to CSV/markdown summary |

### Suggestions (Trade Tracking)

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `suggestions_log.py` | Append one suggestion to `data/suggestions/ledger.jsonl` | `--symbol`, `--action`, `--confidence`, `--score`, `--strategy`, `--entry-low/high`, `--stop-loss`, `--target-1/2`, `--price-now` |
| `suggestions_resolve.py` | Check open suggestions against live prices; write outcomes | `--days` |
| `suggestions_report.py` | Performance report: win rate, P&L by confidence/strategy | `--strategy`, `--confidence`, `--json` |

---

## Data Flows

### A. Full Scanner Flow

```
User: "run stock scanner"
     ↓
scanner agent
  → WebSearch (5 types: RSI oversold, MACD crossover, golden cross, volume breakout, 52w high)
  → Collect symbols + notes into scan JSON
  → Write data/scans/scan_YYYYMMDD_HHMMSS.json
  → uv run python scripts/validate_scan.py <scan_file> --enrich-setups --rank
     ↓
     For each symbol: fetch OHLCV → compute indicators → score 3 setups
       • 2m_pullback  (trend-following, 1-2 month hold)
       • 2w_breakout  (breakout continuation, 1-2 week hold)
       • support_reversal (bounce at support, higher risk)
     → Writes rankings back into scan JSON (in-place)
     ↓
(Optional) breakout-crosscheck / reversal-crosscheck agents review shortlists
(Optional) Add top picks to watchlist via watchlist_events.py add
(Optional) uv run python scripts/scan_and_log.py → log picks to suggestions ledger
```

### B. Scan → Suggestion → Resolution Flow

```
scan_and_log.py
  → Reads latest enriched scan JSON
  → For each top pick (2w_breakout + 2m_pullback rankings):
      • Derives entry_zone, stop_loss, targets from OHLCV metrics
      • Calls suggestions_log.py → appends to data/suggestions/ledger.jsonl
     ↓
(Periodic) suggestions_resolve.py
  → Reads open suggestions from ledger.jsonl
  → Fetches historical prices since suggestion date
  → Checks target/stop hits, elapsed time
  → Appends outcomes to data/suggestions/outcomes/YYYY-MM.jsonl
     ↓
suggestions_report.py
  → Reads ledger.jsonl + outcomes/
  → Prints win rate, avg P&L by confidence/strategy
```

### C. Full Portfolio Analysis Flow

```
User: "analyze my portfolio from input/zerodha.csv"
     ↓
portfolio-analyzer agent
  → portfolio_importer.py (or parse_csv.py + holdings_validate.py)
     → writes data/portfolios/<id>/holdings.json
  → fetch_all.py --holdings
     → fetch_ohlcv.py per symbol → cache/ohlcv/<symbol>.parquet
  → technical_all.py --holdings
     → technical_analysis.py per symbol → data/technical/<symbol>.json
  → research_status.py --holdings --days 30
     → outputs data/runs/<run_id>/research_status.json
     → for each symbol: missing/stale fundamentals/news/legal
  → For missing/stale: run research agents (fundamentals-researcher, news-sentiment, legal-corporate)
     → write data/fundamentals/, data/news/, data/legal/
  → score_all.py --profile portfolio_long_term
     → score_stock.py per symbol → data/scores/<symbol>.json
  → compile_report.py --portfolio-id <id>
     → data/portfolios/<id>/reports/analysis_YYYYMMDD_HHMMSS.csv
  → portfolio_snapshot.py --portfolio-id <id>
     → data/portfolios/<id>/snapshots/<run_id>.json
  → Agent writes data/portfolios/<id>/report.md (narrative, not deterministic)
  → portfolio_report_archive.py --portfolio-id <id>
     → archives report.md, lists previous reports
```

### D. Watchlist Management Flow

```
User: "add RVNL to watchlist swing_trades"
     ↓
watchlist-manager agent
  → watchlist_events.py add swing_trades RVNL.NS \
       --setup 2w_breakout --horizon 2w \
       --entry-zone "240-250" --invalidation "close below 230" \
       --reason "Strong volume near breakout"
     → Appends event to data/watchlists/swing_trades/events.jsonl
  → watchlist_events.py rebuild swing_trades
     → Rebuilds data/watchlists/swing_trades/watchlist.json from events
  → watchlist_events.py validate swing_trades
  → watchlist_snapshot.py swing_trades
     → data/watchlists/swing_trades/snapshots/<run_id>.json
```

### E. IPO Flow

```
User: "scan upcoming IPOs"
     ↓
ipo-scanner agent
  → WebSearch (NSE/BSE/Moneycontrol/Chittorgarh)
  → Merge into data/ipos.json (versioned, never deletes)
  → validate_ipos.py
  → render_ipos.py
     ↓
User: "research <IPO name>"
     ↓
ipo-researcher agent → updates data/ipos.json research section
     ↓
User: "score IPOs"
     ↓
ipo-scorer agent → writes score block into data/ipos.json record
  → validate_ipos.py + render_ipos.py
```

---

## Data Files Reference

### Scans

| File | Format | Write | Read |
|------|--------|-------|------|
| `data/scans/scan_YYYYMMDD_HHMMSS.json` | JSON | scanner agent (via WebSearch) | validate_scan.py, scan_and_log.py |
| `data/scans/fundamental_scan_YYYYMMDD_HHMMSS.json` | JSON | fundamental-scanner agent | watchlist-manager (manual) |

Scan files are enriched **in-place** by `validate_scan.py`. After enrichment, the file gains `validation.rankings`, `validation.setups_by_symbol`, `validation.results_by_symbol`.

### Watchlists (v2)

| File | Format | Write | Notes |
|------|--------|-------|-------|
| `events.jsonl` | JSONL (append-only) | `watchlist_events.py` | Source of truth; never overwrite |
| `watchlist.json` | JSON | `watchlist_events.py rebuild` | Materialized view; always derived |
| `snapshots/<run_id>.json` | JSON | `watchlist_snapshot.py` | Point-in-time state |

Event types: `ADD`, `REMOVE`, `NOTE`. Each event captures: symbol, setup, horizon, entry_zone, invalidation, timing, reentry, reason, tags, source scan.

### Portfolio

| File | Format | Write | Notes |
|------|--------|-------|-------|
| `data/portfolios/<id>/holdings.json` | JSON | importer scripts | Holdings list |
| `data/portfolios/<id>/report.md` | Markdown | portfolio-analyzer agent | Latest narrative report |
| `data/portfolios/<id>/reports/*.md` | Markdown | `portfolio_report_archive.py` | Archived reports; append-only |
| `data/portfolios/<id>/snapshots/<run_id>.json` | JSON | `portfolio_snapshot.py` | Score snapshot per run |
| `data/scores/<symbol>.json` | JSON | `score_stock.py` | Per-symbol final score + recommendation |
| `data/technical/<symbol>.json` | JSON | `technical_analysis.py` | RSI, MACD, SMA, Bollinger, ADX, Volume |
| `data/fundamentals/<symbol>.json` | JSON | `fundamentals-researcher` agent | P/E, growth, results |
| `data/news/<symbol>.json` | JSON | `news-sentiment` agent | News sentiment score |
| `data/legal/<symbol>.json` | JSON | `legal-corporate` agent | Red flags, corporate events |

### Suggestions

| File | Format | Write | Notes |
|------|--------|-------|-------|
| `data/suggestions/ledger.jsonl` | JSONL (append-only) | `suggestions_log.py` | All trade suggestions ever logged |
| `data/suggestions/outcomes/YYYY-MM.jsonl` | JSONL (append) | `suggestions_resolve.py` | Monthly resolution results |

Ledger entry fields: `id`, `ts`, `symbol`, `action` (BUY/SELL), `confidence`, `score`, `strategy`, `entry_zone`, `stop_loss`, `target_1`, `target_2`, `price_at_suggestion`, `scores`.

Outcome fields: `suggestion_id`, `status` (won/lost/expired/open), `pnl_pct`, `hit_target_1`, `hit_target_2`, `hit_stop`, `days_elapsed`.

### Cache + IPO

| File | Format | Notes |
|------|--------|-------|
| `cache/ohlcv/<symbol>.parquet` | Parquet | 18h freshness; never committed to git |
| `data/ipos.json` | JSON (versioned) | Single file; never deletes IPOs; has `file_revision` + `change_log` |

---

## Scoring

All scoring config lives in `utils/config.py`.

### Component Weights (default)

| Component | Default | `portfolio_long_term` | `watchlist_swing` |
|-----------|---------|----------------------|-------------------|
| Technical | 35% | lower | higher |
| Fundamental | 30% | higher | lower |
| News Sentiment | 20% | — | — |
| Legal/Corporate | 15% | — | — |

### Recommendation Thresholds

| Score | Recommendation |
|-------|----------------|
| 8.0+ | STRONG BUY |
| 6.5–7.9 | BUY |
| 4.5–6.4 | HOLD |
| 3.0–4.4 | SELL |
| < 3.0 | STRONG SELL |

### Safety Gates

- Trend score < 5 → cap at HOLD (no buying into downtrends)
- High news + low technicals → BUY → HOLD (no hype-only buys)
- `has_severe_red_flag` in legal data → cap at 5.0, max HOLD
- STRONG BUY requires aligned trend + MACD + ADX

### Scanner Setup Scoring (in `SCAN_SETUP_RULES`)

| Setup | Hard Gates | Min Score to Pass |
|-------|-----------|-------------------|
| `2m_pullback` | close > SMA200, not overextended (< 8% above SMA20) | 60 |
| `2w_breakout` | close > SMA50/200, breakout within 5 days | 65 |
| `support_reversal` | support exists, near support, bounce confirmed | 60 |

---

## Cron Schedule

There is no committed cron configuration in this repo. Scheduled runs are expected to be set up externally (crontab, CI, or via `CronCreate` in Claude Code sessions).

**Recommended schedule (not currently wired):**

| Job | Frequency | Command |
|-----|-----------|---------|
| Weekly scanner + log | Weekly (Sunday) | `uv run python scripts/scan_and_log.py --top 5 --setup both` |
| Suggestion resolution | Weekly | `uv run python scripts/suggestions_resolve.py` |
| Portfolio watch | Daily | `uv run python scripts/fetch_all.py --holdings && uv run python scripts/watch_portfolio.py --holdings` |
| OHLCV cache refresh | Daily | `uv run python scripts/fetch_all.py --holdings` |

---

## How to Add a Stock to a Watchlist

```bash
# 1. Add the event (agent fills in the judgment fields)
uv run python scripts/watchlist_events.py add <watchlist_id> <SYMBOL.NS> \
  --setup 2w_breakout \
  --horizon 2w \
  --entry-zone "240-250" \
  --invalidation "close below 230" \
  --reason "Strong volume, near breakout level" \
  --tags "sector,theme"

# 2. Rebuild + validate the materialized view
uv run python scripts/watchlist_events.py rebuild <watchlist_id>
uv run python scripts/watchlist_events.py validate <watchlist_id>

# 3. Write a per-run snapshot
uv run python scripts/watchlist_snapshot.py <watchlist_id>
```

Or just say "add RVNL to watchlist swing_trades" to the `watchlist-manager` agent.

---

## How to Log a Suggestion Manually

```bash
uv run python scripts/suggestions_log.py \
  --symbol RELIANCE.NS \
  --action BUY \
  --confidence HIGH \
  --score 78.5 \
  --strategy medium \
  --entry-low 2800 \
  --entry-high 2850 \
  --stop-loss 2650 \
  --target-1 3100 \
  --target-2 3400 \
  --price-now 2830 \
  --scores-json '{"tech": 7.5, "fund": 0, "sent": 0, "event_adj": 0}'
```

Or run `scan_and_log.py` to auto-log top picks from the latest enriched scan:

```bash
uv run python scripts/scan_and_log.py --top 5 --setup both
uv run python scripts/scan_and_log.py --dry-run  # preview without writing
```

---

## Known Gaps / TODOs

### Wiring Gaps

- **No cron is configured** in the repo. The scanner + `scan_and_log.py` must be triggered manually or via external scheduler.
- **`main.py` is a placeholder** — it just prints "Hello". No CLI entry point exists for end-users who don't use Claude Code.
- **`scan_and_log.py` entry/stop/target estimates are heuristic** — they use simple % offsets from current price + OHLCV anchors. They are starting points, not precise levels.
- **`fundamental-scanner` output is not validated by `validate_scan.py`** — the fundamental scan JSON uses a different schema (`matches[]` vs `scans.{type}.matches[]`) and won't work with `validate_scan.py latest`.

### Missing Features (from TODO.md)

- Dashboard: load and display snapshots over time
- Dashboard: show watchlist event history
- Sector/industry tags in scans (scan files don't capture sector yet)
- Diversification-aware shortlists (no cross-position concentration check)
- IPO → watchlist integration post-listing (manual today)

### Research Coverage

- Small-cap stocks may have sparse fundamental/news coverage
- `research_status.py` enforces a 30-day freshness window; no auto-refresh for OHLCV (18h cache managed by `fetch_ohlcv.py`)

### Suggestions System

- Outcomes are checked against Yahoo Finance historical data — subject to the same limitations (adjusted prices, gaps for thinly traded stocks)
- No de-duplication guard in the ledger; `scan_and_log.py` will re-log the same symbol if run twice on the same scan
