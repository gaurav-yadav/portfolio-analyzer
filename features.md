# Portfolio Analyzer — Features & Agent-Friendly Roadmap

This document captures the **target product shape** and **agent-friendly architecture** for this repo.

The system needs to reliably do 3 jobs:
1. **Watchlists + Scanner**: create/manage watchlists, scan for candidates, and track outcomes over time.
2. **Portfolios**: import holdings, score them, and track portfolio health/deltas over time.
3. **IPO Scanner**: maintain a small canonical IPO database, research IPOs, and score/rank them.

---

## Design Principle: Scripts Are Deterministic, Agents Do The Thinking

**Scripts should be “pure transforms”**:
- Inputs/outputs are explicit (`--input`, `--output`, `--as-of`, `--run-id`).
- No hidden branching (“if X then also fetch Y”)—agents decide what to run next.
- Deterministic + explainable outputs (given same inputs, produce same outputs).
- Offline where possible (especially validation/ranking steps that rely on cached OHLCV).

**Agents should own branching + judgment**:
- Which pipeline(s) to run (scanner vs portfolio refresh vs IPO update).
- When to refresh web-research (fundamentals/news/legal) based on freshness + confidence.
- Which candidates to add/remove, and why (with explicit invalidation and timing rules).
- How to batch work (avoid rate limits; enforce “minimal output, write to files”).

This separation makes sessions safer, cheaper, and easier to iterate.

---

## Job 1: Watchlists + Scanner (Most Critical)

### Goal
Turn a noisy universe into a **small, diversified shortlist** with:
- clear setup type + horizon (e.g., `2w_breakout`, `2m_pullback`)
- entry zone + invalidation rule
- “why” in 1–2 lines
- sector/industry context (avoid over-concentration)
- tracking over time (did it work?)

### Proposed Data Model (Event Log + Snapshots)

**Source of truth: event-sourced watchlists**
- `data/watchlists/<watchlist_id>/events.jsonl`
  - Append-only events: `ADD`, `REMOVE`, `NOTE`, `INVALIDATE`, `REENTER`, `ENTRY_FILLED`, `EXIT`, etc.
  - Each event includes: `timestamp`, `run_id`, `symbol_yf`, `reason`, `setup`, `horizon`, `entry_zone`, `invalidation`, `source_scan`, `tags`.

**Materialized current state**
- `data/watchlists/<watchlist_id>/watchlist.json`
  - Derived from events; safe for UI/CLI reads.

**Per-run snapshots**
- `data/watchlists/<watchlist_id>/snapshots/<run_id>.json`
  - Captures “as-of” facts per symbol: price, key indicators, setup validity, flags, and “still actionable?”.

This enables “store that information on every run: what/why/timing/re-entry” cleanly.

### Scanner Pipeline (Smart but Deterministic)

**Discovery (agent)**
- Web-search builds the candidate universe (5 scans: RSI/MACD/golden/volume/52w).
- Agent writes a scan file: `data/scans/scan_<timestamp>[_focus].json`.

**Enrich + validate + rank (script)**
- `scripts/validate_scan.py --enrich-setups --rank`
  - Uses cached OHLCV + deterministic setup scoring (`SCAN_SETUP_RULES`).
  - Writes:
    - `validation.results_by_symbol` (raw metrics)
    - `validation.setups_by_symbol` (pass/score/why/metrics for each setup)
    - `validation.rankings.*` (ranked shortlists)

**Action selection (agent)**
- Reads rankings and decides:
  - what to add to watchlist(s)
  - diversification caps (e.g., max 2 per sector)
  - entry/invalidation phrasing
  - re-entry policy (cooldowns; “don’t chase” rules)

### Critical Improvements to Explore
- **Diversification-aware ranking** (script):
  - take top N by score, but cap by `sector`/`industry` tags.
- **Quality gates for “don’t chase”**:
  - explicit “overextended” penalties and max % above SMA20 already exist—extend with “gap risk” / “wickiness” if useful.
- **Entry timing helpers**:
  - store entry zone as ranges (e.g., “within 0–2% above SMA20” or “retest breakout level ±1%”).
- **Re-entry logic**:
  - event type `REENTER_REQUESTED` → agent decides if setup is still valid and cooldown satisfied.

---

## Job 2: Portfolios (Import → Score → Track Over Time)

### Goal
Maintain one or more portfolios, and on each run produce:
- updated holdings snapshot
- scoring snapshot + recommendation
- deltas vs last run (what changed, and why)

### Proposed Multi-Portfolio Layout
- Canonical per-portfolio holdings:
  - `data/portfolios/<portfolio_id>/holdings.json`
- Compatibility alias (current pipeline expectation):
  - `data/holdings.json` (generated from the selected portfolio)
- Per-run portfolio snapshots:
  - `data/portfolios/<portfolio_id>/snapshots/<run_id>.json`
  - Includes: scores, coverage/freshness, and deltas vs last snapshot.

### Import philosophy (agent-friendly)
Two supported paths:
1. **Agent-extracted holdings → validate/normalize (recommended for messy inputs)**:
   - Agent reads PDF/Excel/images and writes a holdings JSON array to `data/holdings.json`.
   - Then run deterministic normalization:
     - `uv run python scripts/holdings_validate.py`
2. **CSV/TSV exports → deterministic importer (recommended for repeatability)**:
   - `uv run python scripts/portfolio_importer.py --portfolio-id ... --country ... --platform ... <file.csv>`

### Data Freshness (DETERMINISTIC GATE)

Research freshness is now enforced by a **deterministic script**, not agent judgment.

**Freshness gate script:** `scripts/research_status.py`

```bash
# Check freshness for holdings (30-day threshold)
uv run python scripts/research_status.py --holdings --days 30

# Output to a run-specific file
uv run python scripts/research_status.py --holdings --days 30 --out data/runs/<run_id>/research_status.json
```

**Contract:**
| Input | Description |
|-------|-------------|
| `--holdings` | Use symbols from `data/holdings.json` |
| `--symbols X Y Z` | Additional symbols to check |
| `--days N` | Staleness threshold (default: 30) |
| `--out <path>` | Write JSON to file (default: stdout) |
| `--format json\|md` | Output format (default: json) |

**Output JSON:**
```json
{
  "run_id": "20260121_123045",
  "generated_at": "2026-01-21T12:30:45Z",
  "threshold_days": 30,
  "symbols": {
    "AMD": {
      "fundamentals": { "status": "fresh", "as_of": "...", "age_days": 15, "path": "..." },
      "news": { "status": "stale", "as_of": "...", "age_days": 45, "path": "..." },
      "legal": { "status": "missing", "as_of": null, "age_days": null, "path": "..." }
    }
  },
  "summary": { "total_symbols": 1, "missing": 1, "stale": 1, "fresh": 1 }
}
```

**Exit codes:**
- `0` = all research is fresh
- `2` = some research is missing or stale

**As-of extraction priority:**
1. JSON field `as_of` (preferred)
2. JSON field `timestamp` (backward compat)
3. File mtime (fallback)

**Agent workflow:**
1. Run `research_status.py` before web research
2. Branch based on `status` per symbol: `missing` or `stale` → refresh
3. Re-run `research_status.py` after research to verify

---

## Job 3: IPO Scanner (Database → Research → Score)

### Goal
Maintain a single canonical IPO DB:
- upcoming/open/closed/listed
- key issue terms + dates
- research + score with versioning

### Current Direction (Good)
- `data/ipos.json` as the single file DB with:
  - `schema_version`, `file_revision`, IPO `record_revision`, `change_log`.

### Improvements to Explore
- Deterministic validators/renderers:
  - `scripts/validate_ipos.py` (schema + invariants + versioning sanity)
  - `scripts/render_ipos.py` (CSV/MD summary output)
- Optional: “IPO watchlist” integration:
  - add IPOs to a dedicated watchlist stream to track post-listing setups.

---

## Scoring Weights: Profiles, Not One Global Setting

The right weights depend on the job/horizon.

### Proposal: scoring profiles
Add a config file (or `utils/config.py` map) like:
- `portfolio_long_term`
- `watchlist_swing`
- `ipo_long_term`
- `ipo_listing_gains`

Each profile defines:
- weights (component-level)
- gating rules (hard excludes / caps)
- freshness decay rules (downweight stale components)
- confidence rules (based on agreement + data completeness)

### Practical defaults (starting point)
- **Watchlist swing (1–8 weeks)**: technical-heavy; fundamentals lighter; legal as a hard gate.
- **Portfolio long-term**: fundamentals + legal heavier; technical still matters but less dominant.
- **IPO**: governance is the largest gate; demand signals are time-sensitive and should be explicitly timestamped.

---

## Claude Code Subagent Best Practices (Pairing/Chaining)

Practical subagent patterns for Claude Code:
- Keep subagents **single-purpose** (one responsibility) and make the prompt **operational** (exact inputs/outputs, file paths, and “minimal response” rules).
- **Chain intentionally**: have an orchestrator agent explicitly call “agent A → produce file X → agent B consumes X → produces Y”.
- Use **good `description` text** so the router picks the right agent (include triggers like “run ipo scanner”, “cross-check breakouts”, etc.).
- Minimize tool surface area via Claude Code **settings/permissions** so agents can’t do unintended work.

References:
- Subagents (definition + usage): https://docs.anthropic.com/en/docs/claude-code/subagents
- Settings/permissions: https://docs.anthropic.com/en/docs/claude-code/settings
- Tutorials: https://docs.anthropic.com/en/docs/claude-code/tutorials
- Sandboxing/security: https://docs.anthropic.com/en/docs/claude-code/security
- Engineering write-up: https://www.anthropic.com/engineering/claude-code-best-practices

---

## Suggested Next Step

Start by making the system “run-id first” and event-sourced for watchlists:
- it unlocks reliable tracking (“what/why/timing/re-entry”) without adding complexity to scoring.

See `TODO.md` for a build order.
