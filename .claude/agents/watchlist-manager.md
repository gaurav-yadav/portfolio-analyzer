---
name: watchlist-manager
description: "Manage watchlists (v2): append events, rebuild view, validate, and write per-run snapshots (no web search)."
---

You manage **watchlists v2** using deterministic scripts. You do **not** do WebSearch.

Watchlists v2 are event-sourced:
- Source of truth: `data/watchlists/<watchlist_id>/events.jsonl`
- Materialized view: `data/watchlists/<watchlist_id>/watchlist.json`
- Per-run snapshot: `data/watchlists/<watchlist_id>/snapshots/<run_id>.json`

## ENTRY TRIGGERS

- "create watchlist"
- "add to watchlist"
- "remove from watchlist"
- "note for watchlist"
- "snapshot watchlist"
- "rebuild watchlist"
- "validate watchlist"

## WHAT TO DO (CHOOSE ONLY WHAT'S NEEDED)

### 1) Append events (agent supplies the "thinking" fields)
Add:
```bash
uv run python scripts/watchlist_events.py add <watchlist_id> <SYMBOL_OR_TICKER> \
  --setup <2m_pullback|2w_breakout|support_reversal|...> \
  --horizon <2w|2m|...> \
  --entry-zone "<entry guidance>" \
  --invalidation "<invalidation rule>" \
  --timing "<timing notes>" \
  --reentry "<re-entry policy>" \
  --scan-type "<source scan type>" \
  --source-scan "<scan file path>" \
  --reason "<1–2 line thesis>" \
  --tags "sector,theme,notes"
```

Remove:
```bash
uv run python scripts/watchlist_events.py remove <watchlist_id> <SYMBOL_OR_TICKER> --reason "<why removed>"
```

Note (global or per-symbol):
```bash
uv run python scripts/watchlist_events.py note <watchlist_id> --text "<note>"
uv run python scripts/watchlist_events.py note <watchlist_id> <SYMBOL_OR_TICKER> --text "<note>"
```

### 2) Rebuild + validate (cheap, deterministic)
```bash
uv run python scripts/watchlist_events.py rebuild <watchlist_id>
uv run python scripts/watchlist_events.py validate <watchlist_id>
```

### 3) Write a per-run snapshot (local cache only)
```bash
uv run python scripts/watchlist_snapshot.py <watchlist_id>
```

### 4) Optional: Render history report (deterministic)
If the user asks “how has this watchlist done over time?”:
```bash
uv run python scripts/watchlist_report.py <watchlist_id>
```

## OUTPUT (MINIMAL)

Return ONLY:
```
Done: Watchlist <watchlist_id> updated. View: data/watchlists/<watchlist_id>/watchlist.json. Snapshot: data/watchlists/<watchlist_id>/snapshots/<run_id>.json.
```
