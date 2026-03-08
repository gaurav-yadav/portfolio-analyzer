#!/usr/bin/env python3
"""Resolve open suggestions by checking current prices and historical highs/lows."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import yfinance as yf
import pandas as pd

IST = timezone(timedelta(hours=5, minutes=30))
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "suggestions")
LEDGER_PATH = os.path.join(BASE_DIR, "ledger.jsonl")
OUTCOMES_DIR = os.path.join(BASE_DIR, "outcomes")

# Strategy → max holding days
HORIZONS = {
    "swing": 15,
    "medium": 60,
    "long_term": 180,
}


def read_ledger() -> list[dict]:
    """Read all suggestions from ledger."""
    if not os.path.exists(LEDGER_PATH):
        return []
    entries = []
    with open(LEDGER_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def read_resolved_ids() -> set[str]:
    """Read all resolved suggestion IDs from outcome files."""
    resolved = set()
    if not os.path.exists(OUTCOMES_DIR):
        return resolved
    for fname in os.listdir(OUTCOMES_DIR):
        if fname.endswith(".jsonl"):
            with open(os.path.join(OUTCOMES_DIR, fname)) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        outcome = json.loads(line)
                        if outcome.get("status") in ("won", "lost", "expired"):
                            resolved.add(outcome["suggestion_id"])
    return resolved


def resolve_suggestion(entry: dict, current_price: float, hist: pd.DataFrame) -> dict:
    """Check if a suggestion hit target, stop, or expired."""
    now = datetime.now(IST)
    entry_ts = datetime.fromisoformat(entry["ts"])
    days_elapsed = (now - entry_ts).days
    horizon = HORIZONS.get(entry["strategy"], 30)

    # Get price extremes since suggestion
    if not hist.empty:
        max_favorable = float(hist["High"].max().iloc[0]) if entry["action"] == "BUY" else float(hist["Low"].min().iloc[0])
        max_adverse = float(hist["Low"].min().iloc[0]) if entry["action"] == "BUY" else float(hist["High"].max().iloc[0])
    else:
        max_favorable = current_price
        max_adverse = current_price

    # Determine outcome
    is_buy = entry["action"] == "BUY"
    stop = entry["stop_loss"]
    t1 = entry["target_1"]
    t2 = entry["target_2"]
    ref_price = entry["price_at_suggestion"]

    hit_stop = (max_adverse <= stop) if is_buy else (max_adverse >= stop)
    hit_t1 = (max_favorable >= t1) if is_buy else (max_favorable <= t1)
    hit_t2 = (max_favorable >= t2) if is_buy else (max_favorable <= t2)

    if is_buy:
        pnl_pct = round((current_price - ref_price) / ref_price * 100, 2)
    else:
        pnl_pct = round((ref_price - current_price) / ref_price * 100, 2)

    # Status logic: stop hit = lost, target hit = won, expired = expired, else open
    if hit_stop and not hit_t1:
        status = "lost"
    elif hit_t1:
        status = "won"
    elif days_elapsed >= horizon:
        status = "expired"
    else:
        status = "open"

    return {
        "suggestion_id": entry["id"],
        "symbol": entry["symbol"],
        "action": entry["action"],
        "strategy": entry["strategy"],
        "confidence": entry["confidence"],
        "check_ts": now.isoformat(),
        "days_elapsed": days_elapsed,
        "price_at_suggestion": ref_price,
        "price_now": current_price,
        "hit_target_1": hit_t1,
        "hit_target_2": hit_t2,
        "hit_stop": hit_stop,
        "max_favorable": round(max_favorable, 2),
        "max_adverse": round(max_adverse, 2),
        "pnl_pct": pnl_pct,
        "status": status,
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve open suggestions")
    parser.add_argument("--days", type=int, default=180, help="Max age of suggestions to check")
    args = parser.parse_args()

    entries = read_ledger()
    resolved_ids = read_resolved_ids()

    # Filter to unresolved, not too old
    now = datetime.now(IST)
    cutoff = now - timedelta(days=args.days)
    open_entries = [
        e for e in entries
        if e["id"] not in resolved_ids
        and datetime.fromisoformat(e["ts"]) >= cutoff
    ]

    if not open_entries:
        print(json.dumps({"status": "no_open_suggestions", "total_in_ledger": len(entries), "resolved": len(resolved_ids)}))
        return

    # Batch fetch current prices
    symbols = list({e["symbol"] for e in open_entries})
    print(f"Checking {len(open_entries)} open suggestions across {len(symbols)} symbols...", file=sys.stderr)

    outcomes = []
    for entry in open_entries:
        sym = entry["symbol"]
        entry_date = datetime.fromisoformat(entry["ts"]).strftime("%Y-%m-%d")
        try:
            hist = yf.download(sym, start=entry_date, progress=False, auto_adjust=True)
            if hist.empty:
                print(f"  Warning: no data for {sym}", file=sys.stderr)
                continue
            current_price = float(hist["Close"].iloc[-1].iloc[0]) if hasattr(hist["Close"].iloc[-1], 'iloc') else float(hist["Close"].iloc[-1])
            outcome = resolve_suggestion(entry, current_price, hist)
            outcomes.append(outcome)
        except Exception as ex:
            print(f"  Error resolving {sym}: {ex}", file=sys.stderr)
            continue

    # Write outcomes
    os.makedirs(OUTCOMES_DIR, exist_ok=True)
    month_file = os.path.join(OUTCOMES_DIR, now.strftime("%Y-%m") + ".jsonl")
    newly_resolved = 0
    with open(month_file, "a") as f:
        for o in outcomes:
            f.write(json.dumps(o) + "\n")
            if o["status"] in ("won", "lost", "expired"):
                newly_resolved += 1

    summary = {
        "status": "resolved",
        "checked": len(outcomes),
        "newly_resolved": newly_resolved,
        "still_open": len(outcomes) - newly_resolved,
        "outcomes_file": month_file,
    }
    print(json.dumps(summary, indent=2))

    # Print details
    for o in outcomes:
        if o["status"] != "open":
            emoji = "✅" if o["status"] == "won" else "❌" if o["status"] == "lost" else "⏰"
            print(f"  {emoji} {o['suggestion_id']}: {o['status']} | {o['pnl_pct']:+.1f}% | {o['days_elapsed']}d", file=sys.stderr)


if __name__ == "__main__":
    main()
