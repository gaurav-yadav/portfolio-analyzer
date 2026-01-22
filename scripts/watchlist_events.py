#!/usr/bin/env python3
"""
Watchlist Events (v2) - event-sourced watchlists.

Goal:
  - Agents decide *what/why* (setup, entry zone, invalidation, timing, tags).
  - Scripts do deterministic state updates (append event, rebuild view).

Storage:
  - Source of truth: data/watchlists/<watchlist_id>/events.jsonl
  - Materialized view: data/watchlists/<watchlist_id>/watchlist.json

Usage:
  # Add a symbol
  uv run python scripts/watchlist_events.py add swing RECLTD --setup 2m_pullback --horizon 2m --entry-zone "near SMA20" --invalidation "close < support" --tags infra,midcap

  # Remove a symbol
  uv run python scripts/watchlist_events.py remove swing RECLTD --reason "setup invalidated"

  # Add a note (portfolio-level or per-symbol)
  uv run python scripts/watchlist_events.py note swing --text "Avoid results week"
  uv run python scripts/watchlist_events.py note swing RECLTD --text "Wait for retest"

  # Rebuild materialized view
  uv run python scripts/watchlist_events.py rebuild swing
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import normalize_symbol  # noqa: E402


BASE_PATH = Path(__file__).parent.parent
WATCHLISTS_DIR = BASE_PATH / "data" / "watchlists"
SUPPORTED_EVENT_TYPES = {"ADD", "REMOVE", "NOTE"}


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _today_str(ts_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_iso)
        return dt.date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


def _default_run_id(ts_iso: str | None) -> str:
    if ts_iso:
        try:
            dt = datetime.fromisoformat(ts_iso)
            return dt.strftime("%Y%m%d_%H%M%S")
        except Exception:
            pass
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def normalize_yf_symbol(symbol: str, default_suffix: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        return ""
    if "." in s:
        return s
    return f"{s}{default_suffix}" if default_suffix else s


def events_path_for(watchlist_id: str) -> Path:
    return WATCHLISTS_DIR / watchlist_id / "events.jsonl"


def view_path_for(watchlist_id: str) -> Path:
    return WATCHLISTS_DIR / watchlist_id / "watchlist.json"


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_no} in {path}: {e}") from e
            if not isinstance(obj, dict):
                raise ValueError(f"Invalid event (not an object) on line {line_no} in {path}")
            events.append(obj)
    return events


def materialize_watchlist(watchlist_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Deterministically build a materialized watchlist view from events.

    Output is designed to be compatible with existing scripts that read:
      watchlist.get("stocks") -> list of { "symbol": "RELIANCE", ... }
    """
    stocks_by_yf: dict[str, dict[str, Any]] = {}
    notes: list[dict[str, Any]] = []

    last_event_ts: str | None = None

    for ev in events:
        ev_type = str(ev.get("type") or "").upper().strip()
        ts = str(ev.get("timestamp") or "")
        if ts:
            last_event_ts = ts

        symbol_yf = str(ev.get("symbol_yf") or "").strip().upper()
        symbol = str(ev.get("symbol") or "").strip().upper()
        if symbol and not symbol_yf:
            symbol_yf = symbol
        if symbol_yf:
            symbol_yf = symbol_yf.strip().upper()
            symbol_clean = normalize_symbol(symbol_yf)
        else:
            symbol_clean = ""

        if ev_type == "NOTE" and not symbol_yf:
            notes.append(
                {
                    "timestamp": ts or "",
                    "run_id": ev.get("run_id") or "",
                    "text": ev.get("text") or "",
                }
            )
            continue

        if not symbol_yf:
            # Ignore unknown event without a symbol (except global NOTE handled above).
            continue

        rec = stocks_by_yf.get(symbol_yf)
        if rec is None:
            rec = {
                "symbol": symbol_clean or normalize_symbol(symbol_yf),
                "symbol_yf": symbol_yf,
                "status": "ACTIVE",
                "added_date": "",
                "added_from_scan": "",
                "added_price": None,
                "notes": [],
                "plan": {},
                "tags": [],
                "source_scan": "",
                "last_event_at": "",
            }
            stocks_by_yf[symbol_yf] = rec

        rec["last_event_at"] = ts or rec.get("last_event_at") or ""

        if ev_type == "ADD":
            rec["status"] = "ACTIVE"
            rec["added_date"] = ev.get("added_date") or _today_str(ts or _now_iso())
            rec["added_from_scan"] = ev.get("scan_type") or ev.get("added_from_scan") or rec.get("added_from_scan") or ""
            rec["added_price"] = ev.get("added_price") if ev.get("added_price") is not None else rec.get("added_price")
            rec["source_scan"] = ev.get("source_scan") or rec.get("source_scan") or ""
            # Merge plan/tags if present
            plan = ev.get("plan")
            if isinstance(plan, dict):
                merged = dict(rec.get("plan") or {})
                merged.update(plan)
                rec["plan"] = merged
            tags = ev.get("tags")
            if isinstance(tags, list):
                existing = {str(t).strip() for t in (rec.get("tags") or []) if str(t).strip()}
                for t in tags:
                    s = str(t).strip()
                    if s:
                        existing.add(s)
                rec["tags"] = sorted(existing)
            continue

        if ev_type == "REMOVE":
            rec["status"] = "REMOVED"
            rec["removed_at"] = ts or rec.get("removed_at") or ""
            rec["removed_reason"] = ev.get("reason") or rec.get("removed_reason") or ""
            continue

        if ev_type == "NOTE":
            note_text = str(ev.get("text") or "").strip()
            if note_text:
                rec_notes = rec.get("notes") or []
                if not isinstance(rec_notes, list):
                    rec_notes = []
                rec_notes.append(
                    {
                        "timestamp": ts or "",
                        "run_id": ev.get("run_id") or "",
                        "text": note_text,
                    }
                )
                rec["notes"] = rec_notes
            continue

    active = [r for r in stocks_by_yf.values() if r.get("status") == "ACTIVE"]
    removed = [r for r in stocks_by_yf.values() if r.get("status") == "REMOVED"]

    # Stable ordering
    active.sort(key=lambda r: str(r.get("symbol_yf") or r.get("symbol") or ""))
    removed.sort(key=lambda r: str(r.get("symbol_yf") or r.get("symbol") or ""))

    return {
        "watchlist_id": watchlist_id,
        "updated_at": last_event_ts or "",
        "events_count": len(events),
        "notes": notes,
        "stocks": active,
        "removed": removed,
    }


def cmd_add(args: argparse.Namespace) -> int:
    ts = args.timestamp or _now_iso()
    run_id = args.run_id or _default_run_id(ts)

    symbol_yf = args.symbol_yf or normalize_yf_symbol(args.symbol, args.default_suffix)
    if not symbol_yf:
        print("Error: empty symbol", file=sys.stderr)
        return 2

    symbol_clean = normalize_symbol(symbol_yf)
    tags = [t.strip() for t in (args.tags.split(",") if args.tags else []) if t.strip()]

    plan: dict[str, Any] = {}
    if args.setup:
        plan["setup"] = args.setup
    if args.horizon:
        plan["horizon"] = args.horizon
    if args.entry_zone:
        plan["entry_zone"] = args.entry_zone
    if args.invalidation:
        plan["invalidation"] = args.invalidation
    if args.timing:
        plan["timing"] = args.timing
    if args.reentry:
        plan["reentry"] = args.reentry

    ev: dict[str, Any] = {
        "type": "ADD",
        "timestamp": ts,
        "as_of": args.as_of or ts,
        "run_id": run_id,
        "watchlist_id": args.watchlist_id,
        "symbol": symbol_clean,
        "symbol_yf": symbol_yf,
        "scan_type": args.scan_type or "",
        "source_scan": args.source_scan or "",
        "added_date": _today_str(ts),
        "added_price": args.added_price,
        "reason": args.reason or "",
        "plan": plan,
        "tags": tags,
    }
    # Remove noisy empty fields
    ev = {k: v for k, v in ev.items() if v not in ("", None, {}, [])}

    path = events_path_for(args.watchlist_id)
    append_event(path, ev)
    print(f"Appended: {path}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    ts = args.timestamp or _now_iso()
    run_id = args.run_id or _default_run_id(ts)

    symbol_yf = args.symbol_yf or normalize_yf_symbol(args.symbol, args.default_suffix)
    if not symbol_yf:
        print("Error: empty symbol", file=sys.stderr)
        return 2

    symbol_clean = normalize_symbol(symbol_yf)
    ev: dict[str, Any] = {
        "type": "REMOVE",
        "timestamp": ts,
        "as_of": args.as_of or ts,
        "run_id": run_id,
        "watchlist_id": args.watchlist_id,
        "symbol": symbol_clean,
        "symbol_yf": symbol_yf,
        "reason": args.reason or "",
    }
    ev = {k: v for k, v in ev.items() if v not in ("", None)}

    path = events_path_for(args.watchlist_id)
    append_event(path, ev)
    print(f"Appended: {path}")
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    ts = args.timestamp or _now_iso()
    run_id = args.run_id or _default_run_id(ts)
    text = (args.text or "").strip()
    if not text:
        print("Error: empty note text", file=sys.stderr)
        return 2

    symbol_yf = ""
    symbol_clean = ""
    if args.symbol or args.symbol_yf:
        symbol_yf = args.symbol_yf or normalize_yf_symbol(args.symbol, args.default_suffix)
        symbol_clean = normalize_symbol(symbol_yf)

    ev: dict[str, Any] = {
        "type": "NOTE",
        "timestamp": ts,
        "as_of": args.as_of or ts,
        "run_id": run_id,
        "watchlist_id": args.watchlist_id,
        "symbol": symbol_clean,
        "symbol_yf": symbol_yf,
        "text": text,
    }
    ev = {k: v for k, v in ev.items() if v not in ("", None)}

    path = events_path_for(args.watchlist_id)
    append_event(path, ev)
    print(f"Appended: {path}")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    events_path = events_path_for(args.watchlist_id)
    events = read_events(events_path)
    view = materialize_watchlist(args.watchlist_id, events)

    out_path = Path(args.out) if args.out else view_path_for(args.watchlist_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(view, indent=2, ensure_ascii=False))
    print(f"Wrote: {out_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """
    Validate events.jsonl for a watchlist.

    This enforces a minimal contract:
    - Each line is a JSON object with `type` and `timestamp`
    - `type` is one of SUPPORTED_EVENT_TYPES (or allowed via --allow-unknown)
    - For symbol events, `symbol_yf` must be present and non-empty
    - `watchlist_id` (if present) must match
    """
    path = events_path_for(args.watchlist_id)
    events = read_events(path)
    if not events:
        print(f"OK: {path} (0 events)")
        return 0

    errors: list[str] = []
    for i, ev in enumerate(events):
        prefix = f"line {i+1}"

        ev_type = str(ev.get("type") or "").upper().strip()
        if not ev_type:
            errors.append(f"{prefix}: missing type")
            continue

        if not args.allow_unknown and ev_type not in SUPPORTED_EVENT_TYPES:
            errors.append(f"{prefix}: unsupported type '{ev_type}'")

        ts = ev.get("timestamp")
        if not isinstance(ts, str) or not ts.strip():
            errors.append(f"{prefix}: missing timestamp")
        else:
            try:
                datetime.fromisoformat(ts)
            except Exception:
                errors.append(f"{prefix}: invalid timestamp '{ts}' (expected ISO-8601)")

        wl = ev.get("watchlist_id")
        if wl is not None and str(wl) != args.watchlist_id:
            errors.append(f"{prefix}: watchlist_id '{wl}' does not match '{args.watchlist_id}'")

        if ev_type in {"ADD", "REMOVE"}:
            sym_yf = str(ev.get("symbol_yf") or "").strip()
            if not sym_yf:
                errors.append(f"{prefix}: {ev_type} missing symbol_yf")

        if ev_type == "NOTE":
            # symbol_yf optional (global note); if present, must be non-empty string
            if "symbol_yf" in ev and not str(ev.get("symbol_yf") or "").strip():
                errors.append(f"{prefix}: NOTE has empty symbol_yf (omit it for global notes)")

    if errors:
        print(f"Invalid: {path}", file=sys.stderr)
        for e in errors[:25]:
            print(f"- {e}", file=sys.stderr)
        if len(errors) > 25:
            print(f"- ... and {len(errors) - 25} more", file=sys.stderr)
        return 1

    print(f"OK: {path} ({len(events)} events)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Event-sourced watchlist manager (v2).")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common_flags(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--default-suffix", default=".NS", help="Suffix for symbols without exchange suffix (default: .NS)")
        sp.add_argument("--symbol-yf", default="", help="Explicit Yahoo Finance ticker (overrides positional symbol)")
        sp.add_argument("--run-id", default="", help="Run identifier (default: derived from timestamp)")
        sp.add_argument("--timestamp", default="", help="Event timestamp ISO-8601 (default: now)")
        sp.add_argument("--as-of", default="", help="As-of timestamp ISO-8601 (default: same as timestamp)")

    sp_add = sub.add_parser("add", help="Append an ADD event.")
    sp_add.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    sp_add.add_argument("symbol", help="Symbol or ticker (e.g., RELIANCE or RELIANCE.NS)")
    add_common_flags(sp_add)
    sp_add.add_argument("--scan-type", default="", help="Origin scan type (e.g., rsi_oversold, 2m_pullback)")
    sp_add.add_argument("--source-scan", default="", help="Path to scan file that produced this candidate")
    sp_add.add_argument("--reason", default="", help="Short reason/thesis (1-2 lines)")
    sp_add.add_argument("--setup", default="", help="Setup name (e.g., 2m_pullback, 2w_breakout)")
    sp_add.add_argument("--horizon", default="", help="Expected holding horizon (e.g., 2w, 2m)")
    sp_add.add_argument("--entry-zone", default="", help="Entry zone description (string)")
    sp_add.add_argument("--invalidation", default="", help="Invalidation rule (string)")
    sp_add.add_argument("--timing", default="", help="Timing guidance (string)")
    sp_add.add_argument("--reentry", default="", help="Re-entry rule/cooldown guidance (string)")
    sp_add.add_argument("--added-price", type=float, default=None, help="Entry/reference price to track returns")
    sp_add.add_argument("--tags", default="", help="Comma-separated tags (sector/theme/etc)")
    sp_add.set_defaults(fn=cmd_add)

    sp_rm = sub.add_parser("remove", help="Append a REMOVE event.")
    sp_rm.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    sp_rm.add_argument("symbol", help="Symbol or ticker (e.g., RELIANCE or RELIANCE.NS)")
    add_common_flags(sp_rm)
    sp_rm.add_argument("--reason", default="", help="Removal reason")
    sp_rm.set_defaults(fn=cmd_remove)

    sp_note = sub.add_parser("note", help="Append a NOTE event (global or per-symbol).")
    sp_note.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    sp_note.add_argument("symbol", nargs="?", default="", help="Optional symbol/ticker for a per-symbol note")
    add_common_flags(sp_note)
    sp_note.add_argument("--text", required=True, help="Note text")
    sp_note.set_defaults(fn=cmd_note)

    sp_rebuild = sub.add_parser("rebuild", help="Rebuild materialized watchlist.json from events.jsonl.")
    sp_rebuild.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    sp_rebuild.add_argument("--out", default="", help="Output path (default: data/watchlists/<id>/watchlist.json)")
    sp_rebuild.set_defaults(fn=cmd_rebuild)

    sp_validate = sub.add_parser("validate", help="Validate events.jsonl schema (minimal contract).")
    sp_validate.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    sp_validate.add_argument("--allow-unknown", action="store_true", help="Allow unknown event types (skip strict type checking)")
    sp_validate.set_defaults(fn=cmd_validate)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Normalize timestamp/as_of flags
    if getattr(args, "timestamp", "") == "":
        args.timestamp = ""
    if getattr(args, "as_of", "") == "":
        args.as_of = ""
    if getattr(args, "run_id", "") == "":
        args.run_id = ""
    if getattr(args, "symbol_yf", "") == "":
        args.symbol_yf = ""

    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
