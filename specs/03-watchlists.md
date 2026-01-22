# Watchlists (v2)

Event-sourced watchlists with full audit trail.

## Storage

```
data/watchlists/<watchlist_id>/
├── events.jsonl      # Source of truth (append-only)
├── watchlist.json    # Materialized view
└── snapshots/        # Per-run snapshots
```

---

## CLI: watchlist_events.py

### Add symbol

```bash
uv run python scripts/watchlist_events.py add <watchlist_id> <symbol> [options]

options:
  --setup SETUP           Setup type (2m_pullback, 2w_breakout, support_reversal)
  --horizon HORIZON       Holding horizon (2w, 2m, etc)
  --entry-zone ZONE       Entry guidance
  --invalidation RULE     When thesis breaks
  --timing NOTES          Timing guidance
  --reentry POLICY        Re-entry rules
  --reason TEXT           Short thesis
  --tags TAGS             Comma-separated tags
  --scan-type TYPE        Origin scan type
  --source-scan PATH      Source scan file
  --added-price PRICE     Reference price
  --default-suffix SUF    Symbol suffix (default: .NS)
```

### Remove symbol

```bash
uv run python scripts/watchlist_events.py remove <watchlist_id> <symbol> --reason "..."
```

### Add note

```bash
# Global note
uv run python scripts/watchlist_events.py note <watchlist_id> --text "..."

# Per-symbol note
uv run python scripts/watchlist_events.py note <watchlist_id> <symbol> --text "..."
```

### Rebuild view

```bash
uv run python scripts/watchlist_events.py rebuild <watchlist_id>
```

### Validate

```bash
uv run python scripts/watchlist_events.py validate <watchlist_id>
```

---

## CLI: watchlist_snapshot.py

```bash
uv run python scripts/watchlist_snapshot.py <watchlist_id>
```

---

## CLI: watchlist_report.py

```bash
uv run python scripts/watchlist_report.py <watchlist_id>
```

---

## Event Schema

```json
{
  "event_type": "ADD",
  "timestamp": "2026-01-20T14:30:00+05:30",
  "run_id": "20260120_143000",
  "symbol_yf": "RVNL.NS",
  "setup": "2w_breakout",
  "horizon": "2w",
  "entry_zone": "240-250",
  "invalidation": "close below 230",
  "reason": "Strong volume near breakout",
  "tags": ["infra", "midcap"]
}
```

---

## Agent

`watchlist-manager` — manages events, rebuild, snapshot (no web search)
