#!/usr/bin/env python3
"""Report on suggestion history: win rates, P&L, breakdowns by confidence/strategy."""

import argparse
import json
import os
import sys
from collections import defaultdict

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "suggestions")
LEDGER_PATH = os.path.join(BASE_DIR, "ledger.jsonl")
OUTCOMES_DIR = os.path.join(BASE_DIR, "outcomes")


def read_ledger() -> list[dict]:
    if not os.path.exists(LEDGER_PATH):
        return []
    entries = []
    with open(LEDGER_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def read_all_outcomes() -> dict[str, dict]:
    """Read all outcomes, keyed by suggestion_id. Latest outcome wins."""
    outcomes = {}
    if not os.path.exists(OUTCOMES_DIR):
        return outcomes
    for fname in sorted(os.listdir(OUTCOMES_DIR)):
        if fname.endswith(".jsonl"):
            with open(os.path.join(OUTCOMES_DIR, fname)) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        o = json.loads(line)
                        outcomes[o["suggestion_id"]] = o
    return outcomes


def compute_stats(outcomes: list[dict]) -> dict:
    """Compute win rate, avg P&L, etc. from a list of outcomes."""
    if not outcomes:
        return {"count": 0}

    won = [o for o in outcomes if o["status"] == "won"]
    lost = [o for o in outcomes if o["status"] == "lost"]
    expired = [o for o in outcomes if o["status"] == "expired"]
    still_open = [o for o in outcomes if o["status"] == "open"]

    resolved = won + lost + expired
    pnls = [o["pnl_pct"] for o in resolved if o.get("pnl_pct") is not None]

    win_rate = len(won) / len(resolved) * 100 if resolved else 0
    avg_pnl = sum(pnls) / len(pnls) if pnls else 0
    avg_win = sum(o["pnl_pct"] for o in won) / len(won) if won else 0
    avg_loss = sum(o["pnl_pct"] for o in lost) / len(lost) if lost else 0

    return {
        "count": len(outcomes),
        "won": len(won),
        "lost": len(lost),
        "expired": len(expired),
        "open": len(still_open),
        "win_rate": round(win_rate, 1),
        "avg_pnl": round(avg_pnl, 2),
        "avg_win_pnl": round(avg_win, 2),
        "avg_loss_pnl": round(avg_loss, 2),
        "total_pnl": round(sum(pnls), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Suggestions performance report")
    parser.add_argument("--strategy", help="Filter by strategy (swing/medium/long_term)")
    parser.add_argument("--confidence", help="Filter by confidence (HIGH/MEDIUM/LOW)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    ledger = read_ledger()
    all_outcomes = read_all_outcomes()

    if not ledger:
        print("No suggestions logged yet.")
        return

    # Build combined view
    combined = []
    for entry in ledger:
        sid = entry["id"]
        outcome = all_outcomes.get(sid, {"status": "open", "pnl_pct": None})
        combined.append({**entry, **outcome})

    # Apply filters
    if args.strategy:
        combined = [c for c in combined if c.get("strategy") == args.strategy]
    if args.confidence:
        combined = [c for c in combined if c.get("confidence") == args.confidence]

    overall = compute_stats(combined)

    # Breakdowns
    by_confidence = defaultdict(list)
    by_strategy = defaultdict(list)
    for c in combined:
        by_confidence[c.get("confidence", "?")].append(c)
        by_strategy[c.get("strategy", "?")].append(c)

    confidence_stats = {k: compute_stats(v) for k, v in sorted(by_confidence.items())}
    strategy_stats = {k: compute_stats(v) for k, v in sorted(by_strategy.items())}

    if args.json:
        print(json.dumps({
            "overall": overall,
            "by_confidence": confidence_stats,
            "by_strategy": strategy_stats,
        }, indent=2))
        return

    # Pretty print
    print("=" * 55)
    print("📊 SUGGESTIONS PERFORMANCE REPORT")
    print("=" * 55)
    print()
    print(f"Total suggestions: {overall['count']}")
    print(f"Resolved: {overall.get('won', 0) + overall.get('lost', 0) + overall.get('expired', 0)} | Open: {overall.get('open', 0)}")
    print(f"Won: {overall.get('won', 0)} | Lost: {overall.get('lost', 0)} | Expired: {overall.get('expired', 0)}")
    print(f"Win Rate: {overall.get('win_rate', 0):.1f}%")
    print(f"Avg P&L: {overall.get('avg_pnl', 0):+.2f}%")
    print(f"Avg Win: {overall.get('avg_win_pnl', 0):+.2f}% | Avg Loss: {overall.get('avg_loss_pnl', 0):+.2f}%")
    print(f"Total P&L: {overall.get('total_pnl', 0):+.2f}%")

    print()
    print("BY CONFIDENCE")
    print("-" * 55)
    for tier, stats in confidence_stats.items():
        resolved = stats.get("won", 0) + stats.get("lost", 0) + stats.get("expired", 0)
        print(f"  {tier:8s} | {stats['count']:3d} total | {resolved:3d} resolved | WR {stats.get('win_rate', 0):5.1f}% | P&L {stats.get('avg_pnl', 0):+6.2f}%")

    print()
    print("BY STRATEGY")
    print("-" * 55)
    for strat, stats in strategy_stats.items():
        resolved = stats.get("won", 0) + stats.get("lost", 0) + stats.get("expired", 0)
        print(f"  {strat:10s} | {stats['count']:3d} total | {resolved:3d} resolved | WR {stats.get('win_rate', 0):5.1f}% | P&L {stats.get('avg_pnl', 0):+6.2f}%")

    # Recent suggestions (last 10)
    print()
    print("RECENT SUGGESTIONS (last 10)")
    print("-" * 55)
    for c in combined[-10:]:
        status = c.get("status", "open")
        emoji = {"won": "✅", "lost": "❌", "expired": "⏰", "open": "⏳"}.get(status, "?")
        pnl = c.get("pnl_pct")
        pnl_str = f"{pnl:+.1f}%" if pnl is not None else "  n/a"
        date = c.get("ts", "")[:10]
        print(f"  {emoji} {date} {c.get('symbol', '?'):15s} {c.get('action', '?'):4s} {c.get('confidence', '?'):6s} {c.get('score', 0):5.1f} {pnl_str}")

    print()


if __name__ == "__main__":
    main()
