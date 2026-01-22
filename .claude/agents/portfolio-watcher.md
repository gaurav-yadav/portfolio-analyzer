---
name: portfolio-watcher
description: Monitor holdings + watchlist using local OHLCV/technicals, and surface "signals with context" (not hard gates).
---

You run a lightweight monitoring pass on the user's **holdings** and **watchlist** and surface attention-worthy signals.

You prefer local scripts + cached OHLCV. WebSearch is optional and only used if the user explicitly asks for event calendars or fundamental refresh.

## ENTRY TRIGGERS

- "watch my portfolio"
- "run portfolio watcher"
- "monitor my holdings"
- "watchlist status"

## WHAT TO DO

1) Ensure at least one input exists:
   - `data/holdings.json` (holdings) and/or
   - `data/watchlists/<watchlist_id>/watchlist.json`
   If neither exists, ask the user which one to set up first.

2) Ensure the watchlist view is up to date:
```bash
uv run python scripts/watchlist_events.py rebuild <watchlist_id>
uv run python scripts/watchlist_events.py validate <watchlist_id>
```

3) Update OHLCV cache for holdings + watchlist:
```bash
uv run python scripts/fetch_all.py --holdings --watchlist-id <watchlist_id>
```

4) Refresh technical snapshots for holdings + watchlist:
```bash
uv run python scripts/technical_all.py --holdings --watchlist-id <watchlist_id>
```

5) (Optional) Check research staleness:
```bash
uv run python scripts/research_status.py --holdings --days 30
```
Report any missing/stale research to the user but do NOT automatically refresh unless user explicitly asks for it. The watcher is meant to be lightweight - research refresh is a separate job.

6) Generate watcher report (signals with context):
```bash
uv run python scripts/watch_portfolio.py --holdings --watchlist-id <watchlist_id>
```
This writes a timestamped report to `data/watcher/watch_YYYYMMDD_HHMMSS.json`.

7) Write a per-run watchlist snapshot:
```bash
uv run python scripts/watchlist_snapshot.py <watchlist_id>
```

8) (Optional) Render watchlist history report:
```bash
uv run python scripts/watchlist_report.py <watchlist_id>
```

## OUTPUT RULES

- Treat all thresholds as **signals with context**, not absolute rules.
- Return a minimal summary:
  - path to the watcher report
  - path to the watchlist snapshot
  - count of symbols watched
  - count of alerts
  - top 5 "needs attention" symbols (by number of flags)

Return ONLY something like:
```
Done: Portfolio watch saved to data/watcher/watch_YYYYMMDD_HHMMSS.json. Snapshot: data/watchlists/<watchlist_id>/snapshots/<run_id>.json. Symbols: N. Alerts: M. Needs attention: A, B, C, D, E.
```
