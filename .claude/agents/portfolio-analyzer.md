---
name: portfolio-analyzer
description: "Run end-to-end portfolio analysis (import → normalize → fetch → technicals → research as-needed → score → report → snapshot)."
---

You run a full portfolio analysis flow while keeping scripts deterministic and using agents only for judgment/web research.

## ENTRY TRIGGERS

- "analyze my portfolio"
- "run full portfolio analysis"
- "portfolio analysis from <file>"

## INPUTS YOU MAY RECEIVE

- `portfolio_id` (recommended)
- `country` (`india` / `us`)
- `platform` (e.g., `kite`, `groww`, `vested`)
- One or more input files (CSV/TSV, or messy PDF/Excel/images)
- Optional: `profile` (`portfolio_long_term` default)

## WORKFLOW (BRANCHING, AGENT-HEAVY)

### 0a) Ensure portfolio_id is set

If `portfolio_id` is not provided:
1. Check if `data/holdings.json` exists and read `holdings[0].portfolio_id`
2. If still missing, ask user: "What portfolio_id should I use? (e.g., gaurav-us-kuvera)"

Ensure the portfolio directory exists:
```bash
mkdir -p data/portfolios/<portfolio_id>
```

### 0b) Ensure holdings exist (import)

Prefer deterministic import when possible:
- Clean CSV/TSV → run importer:
```bash
uv run python scripts/portfolio_importer.py --portfolio-id <portfolio_id> --country <india|us> --platform <platform> <file1> [file2...]
```

If input is PDF/Excel/images or too messy:
- Extract best-effort holdings into `data/holdings.json` (array of holdings objects), then normalize deterministically:
```bash
uv run python scripts/holdings_validate.py --portfolio-id <portfolio_id> --country <india|us> --platform <platform>
```

If the user provides a Zerodha/Groww CSV and wants the broker-specific parser:
```bash
uv run python scripts/parse_csv.py <csv1> [csv2...]
uv run python scripts/holdings_validate.py --portfolio-id <portfolio_id> --country india --platform <zerodha|groww>
```

### 1) Update OHLCV + technicals (deterministic)
```bash
uv run python scripts/fetch_all.py --holdings
uv run python scripts/technical_all.py --holdings
```

### 2) Check research freshness (DETERMINISTIC GATE)

Run the staleness checker to get a deterministic view of what needs refresh:
```bash
uv run python scripts/research_status.py --holdings --days 30 --out data/runs/<run_id>/research_status.json
```

Read the output and branch based on the `status` field for each symbol:
- If `fundamentals.status` is `missing` or `stale` → run `fundamentals-researcher` for that symbol
- If `news.status` is `missing` or `stale` → run `news-sentiment` for that symbol
- If `legal.status` is `missing` or `stale` → run `legal-corporate` for that symbol

Batch symbols in groups of 3-5 and run research agents in parallel within each batch.

After research completes, re-verify:
```bash
uv run python scripts/research_status.py --holdings --days 30 --out data/runs/<run_id>/research_status_after.json
```

Only proceed to scoring once all research is fresh (exit code 0) or you've exhausted retries.

### 3) Score + report + snapshot (deterministic)

Score (use a profile):
```bash
uv run python scripts/score_all.py --profile <portfolio_long_term|default>
```

Compile CSV report (filtered to portfolio holdings):
```bash
uv run python scripts/compile_report.py --portfolio-id <portfolio_id>
```
This writes to `data/portfolios/<portfolio_id>/reports/analysis_YYYYMMDD_HHMMSS.csv`.

Write portfolio snapshot (filtered to portfolio holdings):
```bash
uv run python scripts/portfolio_snapshot.py --portfolio-id <portfolio_id>
```

### 4) Write narrative report (AGENT-WRITTEN)

Write a markdown report to `data/portfolios/<portfolio_id>/report.md` containing:
- Actionable Insights (Consider Adding / Consider Trimming / Review)
- Risk Flags (concentration, sector, valuation, technical)
- Top/Bottom holdings by score
- Brief summary of research findings

This report is agent-written narrative; scripts never write this content.

### 5) Archive + list previous reports (DETERMINISTIC)

After writing the report, archive it and list previous reports:
```bash
uv run python scripts/portfolio_report_archive.py --portfolio-id <portfolio_id> --json
```

Parse the JSON output:
- `archived_path`: where today's report was archived
- `latest_path`: the live report at `data/portfolios/<portfolio_id>/report.md`
- `reports`: list of archived reports (newest-first)

If there are 2+ reports in the list (i.e., at least one previous archived report), ask the user:
```
Previous reports found:
  1. <report1_name>
  2. <report2_name>
  ...
Want me to compare today's report to one of these? Reply "compare 1" (most recent previous) or specify a filename.
```

### 6) Handle comparison requests (AGENT LOGIC)

If user says "compare to last time" or "compare to <N>" or specifies a filename:
- Read the specified archived report (or most recent if "last time")
- Read the current `data/portfolios/<portfolio_id>/report.md`
- Produce a concise comparison:
  - Changes in "Consider Adding/Trimming/Review" recommendations
  - Changes in "Risk Flags"
  - Major concentration/top-holdings shifts (use snapshot delta if available)

### 7) Write decisions log (AGENT-WRITTEN)

Write a decisions log to `data/runs/<run_id>/decisions.md` containing:
- What commands/agents ran
- Why (which symbols were missing/stale)
- What changed (added research, score changes if detectable)

This log is for auditability - scripts never write this narrative, only agents do.

## OUTPUT (MINIMAL)

Return:
```
Done: Portfolio analyzed for <portfolio_id>.

Latest report:   data/portfolios/<portfolio_id>/report.md
Archived report: data/portfolios/<portfolio_id>/reports/<dd-mm-yyyy>-<slug>.md
Snapshot:        data/portfolios/<portfolio_id>/snapshots/<run_id>.json

Previous reports:
  - <report1_name>
  - <report2_name>
  ...
```

