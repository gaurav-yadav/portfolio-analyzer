#!/usr/bin/env python3
"""Append a trade suggestion to the suggestions ledger (JSONL)."""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
LEDGER_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "suggestions", "ledger.jsonl")


def make_id(symbol: str, strategy: str, ts: datetime) -> str:
    """Generate stable suggestion ID: SYMBOL-YYYYMMDD-STRATEGY."""
    # Strip exchange suffix for shorter ID
    short = re.sub(r"\.(NS|BO|NYSE|NASDAQ)$", "", symbol, flags=re.IGNORECASE)
    # Truncate to first 6 chars
    short = short[:6].upper()
    date_str = ts.strftime("%Y%m%d")
    strat = strategy.upper()[:5]
    return f"{short}-{date_str}-{strat}"


def main():
    parser = argparse.ArgumentParser(description="Log a trade suggestion")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. RELIANCE.NS)")
    parser.add_argument("--action", required=True, choices=["BUY", "SELL"], help="Trade action")
    parser.add_argument("--confidence", required=True, choices=["HIGH", "MEDIUM", "LOW"])
    parser.add_argument("--score", required=True, type=float, help="Composite score (0-100)")
    parser.add_argument("--strategy", required=True, choices=["swing", "medium", "long_term"])
    parser.add_argument("--entry-low", required=True, type=float)
    parser.add_argument("--entry-high", required=True, type=float)
    parser.add_argument("--stop-loss", required=True, type=float)
    parser.add_argument("--target-1", required=True, type=float)
    parser.add_argument("--target-2", required=True, type=float)
    parser.add_argument("--price-now", required=True, type=float)
    parser.add_argument("--scores-json", default="{}", help='JSON string: {"tech":X,"fund":X,"sent":X,"event_adj":X}')
    args = parser.parse_args()

    now = datetime.now(IST)
    suggestion_id = make_id(args.symbol, args.strategy, now)

    # Parse component scores
    try:
        scores = json.loads(args.scores_json)
    except json.JSONDecodeError:
        scores = {}

    entry = {
        "id": suggestion_id,
        "ts": now.isoformat(),
        "symbol": args.symbol,
        "action": args.action,
        "confidence": args.confidence,
        "score": args.score,
        "strategy": args.strategy,
        "entry_zone": {"low": args.entry_low, "high": args.entry_high},
        "stop_loss": args.stop_loss,
        "target_1": args.target_1,
        "target_2": args.target_2,
        "scores": scores,
        "price_at_suggestion": args.price_now,
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)

    # Append to ledger
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(json.dumps({"status": "logged", "id": suggestion_id, "path": LEDGER_PATH}))


if __name__ == "__main__":
    main()
