# Portfolio Analyzer — Claude Code Entry Point

## Non-Negotiables

- Do **not** fall back to `general-purpose` for scanning/flows.
- If a requested agent type is missing, **stop** and ask the user to restart Claude Code / verify `.claude/agents/`.
- Scripts are run via `uv run python …` (or directly via `.venv/bin/python …` if `uv` is blocked).

## Intents → Agent → Sequence

### Stock Scanner (technical discovery)

Trigger: “run stock scanner”, “scan for stocks”, “scan midcaps in <sector>”

1) Run `scanner` (WebSearch discovery → writes `data/scans/scan_*.json`)
2) Run `scan-validator` (OHLCV confluence → enriches the same scan JSON)
3) Optional: `breakout-crosscheck` / `reversal-crosscheck`
4) Optional: add to watchlist via `scripts/watchlist.py`

### Stock Scanner (fundamental discovery)

Trigger: “run fundamental scanner”, “scan small caps”, “find midcap compounders”

1) Run `fundamental-scanner` (WebSearch discovery → writes `data/scans/fundamental_scan_*.json`)
2) Optional: add candidates to watchlist for tracking

### Portfolio Watcher (monitoring)

Trigger: “watch my portfolio”, “run portfolio watcher”

1) Run `portfolio-watcher` (updates cache + technicals, then writes `data/watcher/watch_*.json`)
2) Optional: `scripts/track_performance.py` for watchlist returns

### Portfolio Analyzer (deep analysis + report)

Trigger: “analyze my portfolio from `<csv_path>`”

1) Import holdings: `csv-parser` (Zerodha/Groww) or `portfolio-importer` (any CSV)
2) Fetch OHLCV: `scripts/fetch_all.py`
3) Technicals: `scripts/technical_all.py`
4) Web research agents (batched): `fundamentals-researcher`, `news-sentiment`, `legal-corporate`
5) Score: `scripts/score_all.py`
6) Report: `scripts/compile_report.py` → `output/analysis_YYYYMMDD_HHMMSS.csv`

## Agent Roster (must exist as Task subagents)

- `scanner` (`.claude/agents/scanner.md`)
- `scan-validator` (`.claude/agents/scan-validator.md`)
- `breakout-crosscheck` (`.claude/agents/breakout-crosscheck.md`)
- `reversal-crosscheck` (`.claude/agents/reversal-crosscheck.md`)
- `fundamental-scanner` (`.claude/agents/fundamental-scanner.md`)
- `portfolio-watcher` (`.claude/agents/portfolio-watcher.md`)
- `csv-parser` (`.claude/agents/csv-parser.md`)
- `portfolio-importer` (`.claude/agents/portfolio-importer.md`)
- `data-fetcher` (`.claude/agents/data-fetcher.md`)
- `technical-analyst` (`.claude/agents/technical-analyst.md`)
- `fundamentals-researcher` (`.claude/agents/fundamentals-researcher.md`)
- `news-sentiment` (`.claude/agents/news-sentiment.md`)
- `legal-corporate` (`.claude/agents/legal-corporate.md`)
- `scorer` (`.claude/agents/scorer.md`)
- IPO helpers: `ipo-scanner`, `ipo-researcher`, `ipo-scorer`

## File Naming (actual scripts)

- OHLCV cache: `cache/ohlcv/<symbol_yf>.parquet`
- Portfolio technicals: `data/technical/<symbol_yf>.json`
- Portfolio research: `data/fundamentals/<symbol_yf>.json`, `data/news/<symbol_yf>.json`, `data/legal/<symbol_yf>.json`
- Scanner technical breakdowns: `data/scan_technical/<symbol_clean>.json` (from `scripts/verify_scan.py`)
- Scanner scan files: `data/scans/scan_*.json` (technical), `data/scans/fundamental_scan_*.json` (fundamental)

## Quick Commands (manual)

```bash
# Portfolio watcher (holdings + watchlist)
uv run python scripts/fetch_all.py --holdings --watchlist
uv run python scripts/technical_all.py --holdings --watchlist
uv run python scripts/watch_portfolio.py --holdings --watchlist

# Validate a specific scan
uv run python scripts/validate_scan.py data/scans/scan_YYYYMMDD_HHMMSS.json --enrich-setups --rank
```
