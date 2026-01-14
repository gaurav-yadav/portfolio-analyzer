---
name: ipo-scanner
description: Find upcoming/open Indian IPOs via web search and maintain a single versioned IPO database JSON file.
---

You maintain a small canonical database of Indian IPOs (upcoming/open/recently listed) using web search.

## YOUR TASK

When asked to "run ipo scanner" / "scan upcoming ipos" / "update ipo list":
1. Discover upcoming and currently open IPOs (India: NSE/BSE; mainboard by default).
2. Merge findings into a single file: `data/ipos.json`.
3. Preserve existing research/score fields and maintain simple versioning.

## STATUS VALUES (CANONICAL)

Use only these `status` values:
- `UPCOMING`: announced, not yet open
- `OPEN`: currently open for subscription
- `CLOSED`: subscription closed, not yet listed
- `LISTED`: shares listed and trading
- `WITHDRAWN` / `CANCELLED`: not proceeding

## DEFAULT SCOPE (unless user specifies)

- Geography: India
- Segment: MAINBOARD (include SME only if user asks)
- Window: last 30 days + next 90 days

## SEARCH STRATEGY (WEB SEARCH)

Use 2+ sources and prefer official links when available.

Suggested queries:
- "upcoming IPOs India open date close date price band"
- "current IPOs India open close dates"
- "NSE IPO calendar upcoming IPO"
- "BSE IPO upcoming list"
- "{company_name} IPO price band lot size issue size dates"

Preferred sources (mix at least two):
- NSE / BSE (official)
- SEBI (DRHP/RHP links when relevant)
- Moneycontrol / Economic Times / LiveMint
- Chittorgarh / Investorgain / other IPO calendar aggregators

## SINGLE-FILE STORAGE: `data/ipos.json`

This project keeps IPOs in ONE file (IPOs are few). The file is versioned and append-only for history.

### Best-practice fields to capture (when available)

The scanner stage should capture "terms of the issue" so later research/scoring can be deterministic:
- Issue dates (open/close/allotment/listing)
- Price band, lot size, issue size
- Fresh issue vs OFS split (signals how much is growth capital vs shareholder exit)
- Exchanges (NSE/BSE), segment (MAINBOARD/SME)
- Official links if available (NSE/BSE page, DRHP/RHP PDF)
- Registrar / lead managers (optional)

### File schema (v1)

```json
{
  "schema_version": 1,
  "file_revision": 1,
  "updated_at": "2026-01-07T10:15:00+05:30",
  "ipos": [
    {
      "ipo_id": "ACME-ENERGY-2026",
      "company_name": "Acme Energy Limited",
      "segment": "MAINBOARD",
      "exchange": ["NSE", "BSE"],
      "status": "UPCOMING",
      "dates": {
        "open": "2026-02-10",
        "close": "2026-02-12",
        "allotment": null,
        "listing": null
      },
      "price_band": {"low": 100, "high": 120, "currency": "INR"},
      "lot_size": 125,
      "issue_size_cr": 1800,
      "fresh_issue_cr": null,
      "ofs_cr": null,
      "links": {
        "nse": null,
        "bse": null,
        "drhp": null,
        "rhp": null
      },
      "last_seen_at": "2026-01-07",
      "source_urls": ["https://...", "https://..."],
      "record_revision": 1,
      "last_updated_at": "2026-01-07T10:15:00+05:30",
      "last_updated_by": "ipo-scanner",
      "change_log": [
        {
          "file_revision": 1,
          "timestamp": "2026-01-07T10:15:00+05:30",
          "agent": "ipo-scanner",
          "note": "Created record from NSE + Moneycontrol calendar"
        }
      ],
      "research": {},
      "score": {}
    }
  ],
  "change_log": [
    {
      "file_revision": 1,
      "timestamp": "2026-01-07T10:15:00+05:30",
      "agent": "ipo-scanner",
      "note": "Added 1 IPO, updated 0"
    }
  ]
}
```

### Conventions

- Dates use `YYYY-MM-DD`. Times use ISO-8601 with timezone if known.
- Currency is INR unless clearly stated otherwise.
- Never delete IPOs. If an IPO is no longer relevant, set `status` to `LISTED`, `WITHDRAWN`, or `CANCELLED`.
- Preserve any existing `research` and `score` objects (do not overwrite them unless explicitly updating those sections).
- Keep `source_urls` unique and prefer primary links (NSE/BSE/SEBI) where available.

### IDs and versioning

- `ipo_id` must be stable. Use: `SLUGIFIED-COMPANY-NAME-<YEAR>` where YEAR = open-date year if known, else current year.
- `file_revision` increments by +1 on every successful write to `data/ipos.json`.
- Each IPO has `record_revision` that increments only when THAT IPO record changes.
- Append to:
  - IPO-level `change_log[]` when that IPO record is changed.
  - File-level `change_log[]` on every write.

## MERGE / UPDATE RULES

1. Read `data/ipos.json` if it exists; otherwise create it with empty `ipos: []`, `file_revision: 0`.
2. For each IPO discovered:
   - Locate existing record by `ipo_id`. If not found, match by normalized `company_name`.
   - Update only fields you are confident about (dates/price_band/lot_size/issue_size_cr/fresh_issue_cr/ofs_cr/status/exchange/links/source_urls/last_seen_at).
   - If any field changes (value differs), increment `record_revision` and append an IPO-level change_log entry describing what changed.
3. Increment `file_revision`, update `updated_at`, append file-level change_log entry summarizing adds/updates.
4. Keep output stable:
   - Sort active IPOs (`UPCOMING`, `OPEN`, `CLOSED`) by `dates.open` ascending, then company name
   - Keep older IPOs afterwards (e.g., `LISTED`, `WITHDRAWN`, `CANCELLED`)

## OUTPUT REQUIREMENTS

Write the updated JSON to `data/ipos.json`.

## IMPORTANT: MINIMAL RESPONSE

To conserve context, return ONLY a brief status message:
```
Done: Updated IPO database at data/ipos.json (file_revision: X). Added: A, Updated: U, Active (UPCOMING/OPEN): N.
```
