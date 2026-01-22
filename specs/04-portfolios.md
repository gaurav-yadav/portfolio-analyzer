# Portfolios

Multi-portfolio support with snapshots and report archiving.

## Storage

```
data/portfolios/<portfolio_id>/
├── holdings.json     # Canonical holdings
├── report.md         # Latest narrative report
├── reports/          # Archived reports (DD-MM-YYYY-slug.md)
└── snapshots/        # Per-run JSON snapshots
```

---

## CLI: portfolio_importer.py

```bash
uv run python scripts/portfolio_importer.py <file> [options]

options:
  --portfolio-id ID     Portfolio identifier
  --country COUNTRY     india or us
  --platform PLATFORM   kite, groww, vested, etc
```

---

## CLI: compile_report.py

```bash
uv run python scripts/compile_report.py [options]

options:
  --portfolio-id ID     Filter scores by portfolio holdings
```

Output:
- With `--portfolio-id`: `data/portfolios/<id>/reports/analysis_*.csv`
- Without: `output/analysis_*.csv`

---

## CLI: portfolio_snapshot.py

```bash
uv run python scripts/portfolio_snapshot.py --portfolio-id <id> [--run-id <run_id>]
```

Output: `data/portfolios/<id>/snapshots/<run_id>.json`

---

## CLI: portfolio_report_archive.py

```bash
# Archive current report + list all
uv run python scripts/portfolio_report_archive.py --portfolio-id <id>

# List only
uv run python scripts/portfolio_report_archive.py --portfolio-id <id> --list

# JSON output
uv run python scripts/portfolio_report_archive.py --portfolio-id <id> --json
```

Output: `data/portfolios/<id>/reports/DD-MM-YYYY-<slug>.md`

Handles duplicates with `-2`, `-3` suffixes.

---

## CLI: research_status.py

```bash
uv run python scripts/research_status.py --holdings --days 30 [--out <path>]
```

Checks freshness of fundamentals/news/legal research. Returns `missing`/`stale`/`fresh` status per symbol.

---

## Workflow

1. Import: `portfolio_importer.py` or `csv-parser` agent
2. Fetch: `fetch_all.py --holdings`
3. Technicals: `technical_all.py --holdings`
4. Freshness: `research_status.py --holdings --days 30`
5. Research: agents refresh stale/missing
6. Score: `score_all.py --profile portfolio_long_term`
7. Report: `compile_report.py --portfolio-id <id>`
8. Narrative: agent writes `report.md`
9. Snapshot: `portfolio_snapshot.py --portfolio-id <id>`
10. Archive: `portfolio_report_archive.py --portfolio-id <id>`

---

## Agents

| Agent | Role |
|-------|------|
| `portfolio-analyzer` | End-to-end workflow |
| `portfolio-importer` | Universal CSV import |
| `csv-parser` | Broker CSV parsing |
| `portfolio-watcher` | Signal monitoring |
