# TODO — Agent-Friendly Build Plan

This repo is being evolved so that:
- **scripts** do deterministic transforms
- **agents** do branching/selection and write the “thinking” into files

Notes:
- Don’t run agent flows from here; use Claude Code in parallel.
- When a deterministic script changes, verify with `uv run python -m py_compile …` (and later, small smoke runs).

---

## Milestone 0 — Documentation + Contracts

- [ ] Define canonical `run_id` + `as_of` conventions (timestamp + optional label)
- [ ] Document file contracts (inputs/outputs) for:
  - [ ] watchlist flows
  - [ ] scanner flows
  - [ ] portfolio flows
  - [ ] IPO flows
- [x] **Research staleness gate implemented + wired**
  - [x] `scripts/research_status.py` (deterministic freshness checker)
  - [x] Portfolio-analyzer agent uses staleness gate before web research
  - [x] Research agents (fundamentals/news/legal) standardized on `as_of` + `sources`

---

## Milestone 1 — Watchlists v2 (Event Log + Snapshots)

### Data model
- [x] Add `data/watchlists/<watchlist_id>/events.jsonl` (append-only)
- [x] Add `data/watchlists/<watchlist_id>/watchlist.json` (materialized view)
- [x] Add `data/watchlists/<watchlist_id>/snapshots/<run_id>.json` (per-run snapshot)

### Scripts (deterministic)
- [x] `scripts/watchlist_events.py`:
  - [x] append events
  - [x] rebuild materialized state from events
  - [x] validate schema/invariants
- [x] `scripts/watchlist_snapshot.py`:
  - [x] generate snapshot for a watchlist_id + run_id using cached OHLCV + existing technical JSONs
- [x] `scripts/watchlist_report.py`: render snapshots history (CSV/JSON)

### Agent behavior
- [ ] Update `.claude/agents/portfolio-watcher.md` to write snapshots + suggest actions (minimal output)
- [ ] Add a dedicated `watchlist-manager` agent (optional) that only writes events + notes

---

## Milestone 2 — Scanner v2 (Better "Actionability" + Diversification)

### Audit trail (agent-written)
- [x] Scanner writes `data/runs/<run_id>/decisions.md` with:
  - [x] which scan file was used
  - [x] which shortlist was chosen and why
  - [x] which symbols were added/removed (and to which watchlist)

### Ranking improvements (deterministic)
- [ ] Add sector/industry tags into scan JSON (agent supplies tags; script only preserves/uses them)
- [ ] Add diversification-aware shortlist builder:
  - [ ] cap per sector (configurable)
  - [ ] output "final shortlist" per setup type

### Watchlist integration (agent)
- [ ] Agent chooses which symbols to add and writes:
  - [ ] entry zone
  - [ ] invalidation rule
  - [ ] cooldown policy
  - [ ] expected holding horizon

---

## Milestone 3 — Portfolio v2 (Multi-Portfolio + Snapshots)

### Data layout
- [x] Implement portfolio-scoped holdings:
  - [x] `data/portfolios/<portfolio_id>/holdings.json`
  - [x] keep `data/holdings.json` as an alias for “active portfolio”
- [x] Add `data/portfolios/<portfolio_id>/snapshots/<run_id>.json`

### Scripts
- [x] Add `scripts/holdings_validate.py` and standardize on it after any agent-imported holdings JSON
- [x] Keep `scripts/portfolio_importer.py` for deterministic CSV/TSV imports (optional, but convenient)
- [x] Add `scripts/portfolio_snapshot.py` (summary + deltas vs previous run)

### Scoring/weights
- [x] Add scoring “profiles” config:
  - [x] `watchlist_swing`
  - [x] `portfolio_long_term`
  - [ ] optional: `ipo_long_term`, `ipo_listing_gains`

---

## Milestone 4 — IPO System v2 (Validate + Render)

- [x] Add `scripts/validate_ipos.py` (schema + version checks)
- [x] Add `scripts/render_ipos.py` (CSV/MD summary)
- [ ] Optional: connect IPOs → a dedicated watchlist stream post-listing

---

## Milestone 5 — UX / Reporting

- [ ] Dashboard support for:
  - [ ] loading portfolio snapshots over time
  - [ ] loading watchlist snapshots over time
  - [ ] showing “why added / why removed” from events
