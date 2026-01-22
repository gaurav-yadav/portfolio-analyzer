# System Architecture

Portfolio Analyzer combines **deterministic Python scripts** for data processing with **Claude Code agents** for judgment and web research.

## Design Principle

**Scripts do transforms. Agents do thinking.**

- Scripts: explicit inputs/outputs, no hidden branching, deterministic
- Agents: workflow selection, web research, writing reports

---

## Directory Layout

```
portfolio-analyzer/
├── scripts/              # Deterministic Python scripts
├── .claude/agents/       # Agent definitions
├── utils/                # Shared config + helpers
├── data/
│   ├── holdings.json     # Active holdings (current portfolio)
│   ├── ipos.json         # IPO database
│   ├── portfolios/<id>/
│   │   ├── holdings.json
│   │   ├── report.md
│   │   ├── reports/      # Archived reports (DD-MM-YYYY-slug.md)
│   │   └── snapshots/
│   ├── watchlists/<id>/
│   │   ├── events.jsonl  # Source of truth
│   │   ├── watchlist.json
│   │   └── snapshots/
│   ├── scans/            # scan_*.json
│   ├── technical/
│   ├── scan_technical/
│   ├── fundamentals/
│   ├── news/
│   ├── legal/
│   └── scores/
├── cache/ohlcv/          # Parquet cache
├── input/                # User CSV files
├── output/               # Global analysis CSVs
└── dashboard/            # Static HTML dashboard
```

---

## Scripts Reference

### Portfolio

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `portfolio_importer.py` | Universal CSV import | `--portfolio-id`, `--country`, `--platform` |
| `parse_csv.py` | Zerodha/Groww CSV parsing | positional file |
| `holdings_validate.py` | Normalize holdings | `--portfolio-id`, `--country`, `--platform` |
| `portfolio_snapshot.py` | Create snapshot | `--portfolio-id`, `--run-id` |
| `portfolio_report_archive.py` | Archive + list reports | `--portfolio-id`, `--list`, `--json` |
| `compile_report.py` | Generate analysis CSV | `--portfolio-id` |
| `research_status.py` | Check research freshness | `--holdings`, `--days`, `--out` |

### Data & Analysis

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `fetch_ohlcv.py` | Fetch single symbol | positional symbol |
| `fetch_all.py` | Batch fetch OHLCV | `--holdings`, `--watchlist-id` |
| `technical_analysis.py` | Single symbol technicals | positional symbol |
| `technical_all.py` | Batch technicals | `--holdings`, `--watchlist-id` |
| `score_stock.py` | Score single stock | positional symbol |
| `score_all.py` | Batch scoring | `--profile` |

### Scanner

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `save_scan.py` | Save scan results | various |
| `validate_scan.py` | Enrich + rank scan | `--enrich-setups`, `--rank`, `--top`, `--us` |
| `verify_scan.py` | OHLCV verification | various |

### Watchlist

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `watchlist_events.py` | Event management | `add`, `remove`, `note`, `rebuild`, `validate` |
| `watchlist_snapshot.py` | Create snapshot | positional watchlist_id |
| `watchlist_report.py` | Generate report | positional watchlist_id |

### IPO

| Script | Purpose |
|--------|---------|
| `validate_ipos.py` | Schema validation |
| `render_ipos.py` | CSV/MD render |

### Utility

| Script | Purpose |
|--------|---------|
| `clean.py` | Clear stale data |
| `watch_portfolio.py` | Lightweight monitoring |

---

## Agent Roster

### Portfolio Workflow
- `portfolio-analyzer` — End-to-end analysis flow
- `portfolio-importer` — Universal CSV import
- `csv-parser` — Broker CSV parsing
- `portfolio-watcher` — Signal monitoring

### Research
- `fundamentals-researcher` — P/E, growth, results
- `news-sentiment` — News sentiment analysis
- `legal-corporate` — Red flags, corporate actions
- `scorer` — Final scoring

### Scanner
- `scanner` — Web discovery + ranking
- `scan-validator` — OHLCV confluence enrichment
- `breakout-crosscheck` — Breakout review
- `reversal-crosscheck` — Reversal review
- `fundamental-scanner` — Fundamental discovery

### Watchlist
- `watchlist-manager` — Event management

### IPO
- `ipo-scanner` — Find IPOs
- `ipo-researcher` — IPO research
- `ipo-scorer` — IPO scoring

### Data
- `data-fetcher` — OHLCV fetching
- `technical-analyst` — Indicator computation

---

## Configuration

All in `utils/config.py`:

- `COMPONENT_WEIGHTS` — Default: technical 35%, fundamental 30%, news 20%, legal 15%
- `SCORING_PROFILES` — `watchlist_swing`, `portfolio_long_term`
- `THRESHOLDS` — STRONG BUY 8.0, BUY 6.5, HOLD 4.5, SELL 3.0
- `GATES` — Safety gate thresholds
- `SCAN_SETUP_RULES` — Confluence scoring params
- `CACHE_FRESHNESS_HOURS` — 18
