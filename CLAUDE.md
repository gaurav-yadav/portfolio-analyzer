# Portfolio Analyzer - Claude Code Entry Point (vNext)

This repo is designed so that:
- **Agents do the thinking and branching** (what to run next, what to add/remove, when to refresh research).
- **Scripts do deterministic work** (parsing, calculations, ranking, normalization, snapshots).

Keep responses minimal; write all details to files.

---

## Non‑Negotiables

- Prefer **deterministic scripts** for transforms and state writes.
- **All agents run `claude-sonnet-4-6`** (set in `.claude/settings.json` + each agent's frontmatter `model:` field).
- Watchlists are flat JSON files: `data/watchlists/<name>.json` (NOT subdirectories).
- Treat WebSearch/WebFetch outputs as **candidate discovery only**; confirm tradability via OHLCV-based validation (`scripts/validate_scan.py`).
- When data is missing/stale, **refresh only what's needed** (don't rerun everything blindly).
- `technical_all.py` runs BOTH the core scoring script AND the modular `scripts/ta/` scripts (stoch_rsi, divergence, patterns, entry_points) — saves to `data/ta/<symbol>_<name>.json`.
- `validate_scan.py` runs the same `scripts/ta/` suite post-validation — saves to `data/scan_technical/`.

---

## Primary Jobs (3)

1) **Watchlists + Scanner**
   - Create/manage watchlists; store *what/why/entry/invalidation/timing/re-entry* in events.
   - Scan stocks and add best candidates to watchlists.
   - Track outcomes via per-run snapshots.

2) **Portfolios**
   - Import holdings, compute technicals, add research context, score, generate report.
   - Track runs over time via portfolio snapshots.

3) **IPO Scanner**
   - Maintain `data/ipos.json`, research IPOs, score/rank them.

---

## Intents → Agent → Deterministic Steps

### Watchlist management (v2)
Trigger: "create watchlist", "add to watchlist", "remove from watchlist", "snapshot watchlist"
- Agent: `watchlist-manager` (`.claude/agents/watchlist-manager.md`)
- Scripts:
  - `uv run python scripts/watchlist_events.py add|remove|note <watchlist_id> ...`
  - `uv run python scripts/watchlist_events.py rebuild <watchlist_id>`
  - `uv run python scripts/watchlist_events.py validate <watchlist_id>`
  - `uv run python scripts/watchlist_snapshot.py <watchlist_id>`
  - Optional: `uv run python scripts/watchlist_report.py <watchlist_id>`

### Stock scanner → validated shortlists
Trigger: "run stock scanner", "scan for stocks"
- Agent: `scanner` → `scan-validator` → optional `breakout-crosscheck` / `reversal-crosscheck`
- Deterministic validation: `uv run python scripts/validate_scan.py latest --enrich-setups --rank`
- Optional add-to-watchlist: use `watchlist-manager` (or directly append events via `watchlist_events.py`).

### Portfolio monitoring (holdings + watchlist signals)
Trigger: "watch my portfolio", "monitor my holdings"
- Agent: `portfolio-watcher` (`.claude/agents/portfolio-watcher.md`)
- Scripts:
  - `uv run python scripts/fetch_all.py --holdings --watchlist-id <watchlist_id>`
  - `uv run python scripts/technical_all.py --holdings --watchlist-id <watchlist_id>`
  - `uv run python scripts/watch_portfolio.py --holdings --watchlist-id <watchlist_id>`
  - `uv run python scripts/watchlist_snapshot.py <watchlist_id>`

### Full portfolio analysis (end-to-end)
Trigger: "analyze my portfolio from …", "run full portfolio analysis"
- Agent: `portfolio-analyzer` (`.claude/agents/portfolio-analyzer.md`)
- Import options:
  - Agent-extracted holdings JSON → normalize: `uv run python scripts/holdings_validate.py ...`
  - CSV/TSV import: `uv run python scripts/portfolio_importer.py ...`
  - Zerodha/Groww CSV: `uv run python scripts/parse_csv.py ...` then `holdings_validate.py`
- Then:
  - `uv run python scripts/fetch_all.py --holdings`
  - `uv run python scripts/technical_all.py --holdings`
  - Run staleness gate: `uv run python scripts/research_status.py --holdings --days 30 --out data/runs/<run_id>/research_status.json`
    - The 30-day policy is enforced by the script output, not agent judgment
    - Agents branch based on `missing`/`stale` status per symbol
  - Web research agents as-needed (missing/stale fundamentals/news/legal)
  - `uv run python scripts/score_all.py --profile portfolio_long_term`
  - `uv run python scripts/compile_report.py --portfolio-id <portfolio_id>` → `data/portfolios/<portfolio_id>/reports/analysis_*.csv`
  - `uv run python scripts/portfolio_snapshot.py --portfolio-id <portfolio_id>`
  - Write markdown report to `data/portfolios/<portfolio_id>/report.md` (agent-written)
  - Archive + list reports: `uv run python scripts/portfolio_report_archive.py --portfolio-id <portfolio_id> --json`
- User can ask: "compare to last time" or "compare to <report>" for delta summary

### IPO system
Trigger: "scan upcoming IPOs", "update IPO list", "score IPOs"
- Agents: `ipo-scanner`, `ipo-researcher`, `ipo-scorer`
- Deterministic checks/render:
  - `uv run python scripts/validate_ipos.py`
  - `uv run python scripts/render_ipos.py`

### Suggestions (trade call tracking)
Trigger: "log this as a suggestion", "resolve suggestions", "how accurate are my calls?"
- Log a call: `uv run python scripts/suggestions_log.py <SYMBOL> BUY --confidence HIGH --score 7.5 --strategy swing --entry-low 240 --entry-high 250 --stop-loss 225 --target-1 280 --target-2 310`
- Log from scanner: `uv run python scripts/scan_and_log.py --top 5 --setup both`
- Resolve weekly: `uv run python scripts/suggestions_resolve.py`
- Report: `uv run python scripts/suggestions_report.py`
- Ledger: `data/suggestions/ledger.jsonl` (append-only)
- Outcomes: `data/suggestions/outcomes/`

### Dashboard
- Local (live API): `cd dashboard && npx tsx src/server.ts` → http://localhost:3323
- Static bake for GitHub Pages: `uv run python scripts/bake_dashboard.py --push`
- Bakes: `data/technical/`, `data/ta/`, `data/watchlists/`, `data/suggestions/` → `dashboard/public/data.js`
- GitHub Actions auto-deploys on push to main (`.github/workflows/deploy.yml`)

---

## Agent Roster (Expected to Exist)

Watchlists / portfolio:
- `watchlist-manager`
- `portfolio-analyzer`
- `portfolio-watcher`
- `portfolio-importer`
- `csv-parser`

Scanner:
- `scanner`
- `scan-validator`
- `breakout-crosscheck`
- `reversal-crosscheck`
- `technical-analyst`

Research + scoring:
- `fundamentals-researcher`
- `news-sentiment`
- `legal-corporate`
- `scorer`

IPOs:
- `ipo-scanner`
- `ipo-researcher`
- `ipo-scorer`

---

## Key File Contracts

### Watchlists
- Shared watchlist: `data/watchlists/shared.json` (flat file, not subdirectory)
- Events log: `data/watchlist_events.jsonl` (append-only)

### Suggestions
- Ledger: `data/suggestions/ledger.jsonl` (append-only trade calls)
- Outcomes: `data/suggestions/outcomes/*.jsonl` (weekly resolution results)

### TA Indicators
- Portfolio/watchlist: `data/ta/<symbol>_<indicator>.json`
- Scanner: `data/scan_technical/<symbol>_<indicator>.json`

### Portfolio snapshots
- `data/portfolios/<portfolio_id>/snapshots/<run_id>.json` (written from `data/scores/*.json`)

### Scans
- `data/scans/scan_*.json` (written by `scanner`)
- Enrichment + rankings stored in-place under `scan.validation.*` (`scripts/validate_scan.py`)

### IPO DB
- `data/ipos.json` (single canonical DB with revision logs)
