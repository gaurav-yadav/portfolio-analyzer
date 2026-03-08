#!/usr/bin/env python3
"""
Scan → validate → log top picks to the suggestions ledger.

Runs the OHLCV-based enrichment on the latest scan file, reads the ranked
shortlists, derives entry/stop/target estimates from OHLCV metrics, and
appends one suggestion per top pick to data/suggestions/ledger.jsonl.

Usage:
    uv run python scripts/scan_and_log.py
    uv run python scripts/scan_and_log.py --scan data/scans/scan_20260308_120000.json
    uv run python scripts/scan_and_log.py --top 5 --setup 2w_breakout
    uv run python scripts/scan_and_log.py --top 3 --setup both --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BASE_PATH = Path(__file__).parent.parent
SCANS_DIR = BASE_PATH / "data" / "scans"
SUGGESTIONS_LOG = BASE_PATH / "scripts" / "suggestions_log.py"


# ---------------------------------------------------------------------------
# Scan file helpers
# ---------------------------------------------------------------------------

def find_latest_scan() -> Path:
    if not SCANS_DIR.exists():
        raise FileNotFoundError("data/scans does not exist — run the scanner first")
    scans = sorted(SCANS_DIR.glob("scan_*.json"), reverse=True)
    if not scans:
        raise FileNotFoundError("No scan_*.json files found in data/scans/")
    return scans[0]


def load_scan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_enriched(scan: dict[str, Any]) -> bool:
    """Check that the scan has been enriched with setup rankings."""
    rankings = scan.get("validation", {}).get("rankings", {})
    return bool(rankings)


def enrich_scan(scan_path: Path) -> None:
    """Run validate_scan.py --enrich-setups --rank in-place."""
    print(f"Enriching scan: {scan_path.name} ...", flush=True)
    result = subprocess.run(
        ["uv", "run", "python", "scripts/validate_scan.py",
         str(scan_path), "--enrich-setups", "--rank"],
        capture_output=True,
        text=True,
        cwd=BASE_PATH,
    )
    if result.returncode != 0:
        print(f"  Warning: validate_scan.py exited {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  {result.stdout.strip()}")


# ---------------------------------------------------------------------------
# Parameter derivation from OHLCV metrics
# ---------------------------------------------------------------------------

def derive_params(
    symbol: str,
    setup_type: str,
    score: float,
    results_by_symbol: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Derive entry_zone, stop_loss, target_1, target_2, confidence from OHLCV.

    Returns None if we cannot determine a valid price (no OHLCV data).
    """
    analysis = results_by_symbol.get(symbol, {})
    price = analysis.get("price") or analysis.get("close")
    if not price or price <= 0:
        return None

    sma20 = analysis.get("sma20")
    sma50 = analysis.get("sma50")
    sma200 = analysis.get("sma200")
    support = analysis.get("support_level")

    # --- Entry zone ---
    if setup_type == "2w_breakout":
        # Buy around current price, within a tight band
        entry_low = round(price * 0.98, 2)
        entry_high = round(price * 1.02, 2)
    elif setup_type == "2m_pullback":
        # Entry near support or SMA20 — buy on the pullback
        anchor = None
        if support and support > 0:
            anchor = support
        elif sma20 and sma20 > 0:
            anchor = sma20
        if anchor:
            entry_low = round(anchor * 0.99, 2)
            entry_high = round(anchor * 1.03, 2)
        else:
            entry_low = round(price * 0.97, 2)
            entry_high = round(price * 1.01, 2)
    else:  # support_reversal
        anchor = support if (support and support > 0) else price
        entry_low = round(anchor * 0.99, 2)
        entry_high = round(anchor * 1.02, 2)

    # --- Stop loss ---
    if setup_type == "2w_breakout":
        # Stop below SMA50 if available, else -6% from entry_low
        if sma50 and sma50 > 0 and sma50 < price:
            stop_loss = round(sma50 * 0.99, 2)
        else:
            stop_loss = round(entry_low * 0.94, 2)
    elif setup_type == "2m_pullback":
        # Stop below support or -5% from entry_low
        if support and support > 0:
            stop_loss = round(support * 0.97, 2)
        elif sma200 and sma200 > 0 and sma200 < price:
            stop_loss = round(sma200 * 0.99, 2)
        else:
            stop_loss = round(entry_low * 0.95, 2)
    else:  # support_reversal
        anchor = support if (support and support > 0) else price
        stop_loss = round(anchor * 0.97, 2)

    # --- Targets ---
    if setup_type == "2w_breakout":
        target_1 = round(price * 1.08, 2)   # +8%
        target_2 = round(price * 1.15, 2)   # +15%
    elif setup_type == "2m_pullback":
        target_1 = round(price * 1.10, 2)   # +10%
        target_2 = round(price * 1.20, 2)   # +20%
    else:  # support_reversal
        target_1 = round(price * 1.07, 2)   # +7%
        target_2 = round(price * 1.14, 2)   # +14%

    # --- Confidence ---
    if score >= 80:
        confidence = "HIGH"
    elif score >= 60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # --- Strategy ---
    strategy_map = {
        "2w_breakout": "swing",
        "2m_pullback": "medium",
        "support_reversal": "swing",
    }
    strategy = strategy_map.get(setup_type, "swing")

    # --- Component scores JSON ---
    tech_score = analysis.get("technical_score", 0) or 0
    scores_json = json.dumps({
        "tech": round(float(tech_score), 1),
        "fund": 0,
        "sent": 0,
        "event_adj": 0,
    })

    return {
        "action": "BUY",
        "confidence": confidence,
        "score": round(float(score), 1),
        "strategy": strategy,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "price_now": round(float(price), 2),
        "scores_json": scores_json,
    }


# ---------------------------------------------------------------------------
# Log to suggestions ledger
# ---------------------------------------------------------------------------

def log_suggestion(symbol: str, params: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Call suggestions_log.py for one symbol. Returns parsed JSON output."""
    cmd = [
        "uv", "run", "python", str(SUGGESTIONS_LOG),
        "--symbol", symbol,
        "--action", params["action"],
        "--confidence", params["confidence"],
        "--score", str(params["score"]),
        "--strategy", params["strategy"],
        "--entry-low", str(params["entry_low"]),
        "--entry-high", str(params["entry_high"]),
        "--stop-loss", str(params["stop_loss"]),
        "--target-1", str(params["target_1"]),
        "--target-2", str(params["target_2"]),
        "--price-now", str(params["price_now"]),
        "--scores-json", params["scores_json"],
    ]

    if dry_run:
        return {"status": "dry_run", "id": f"{symbol}-dry", "cmd": " ".join(cmd[4:])}

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_PATH)
    if result.returncode != 0:
        return {"status": "error", "symbol": symbol, "stderr": result.stderr.strip()}

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"status": "error", "symbol": symbol, "raw": result.stdout.strip()}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan → validate → log top picks to the suggestions ledger"
    )
    parser.add_argument(
        "--scan",
        default=None,
        help="Path to scan file (default: latest data/scans/scan_*.json)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top picks per setup type to log (default: 5)",
    )
    parser.add_argument(
        "--setup",
        choices=["2w_breakout", "2m_pullback", "both"],
        default="both",
        help="Which setup type to log (default: both)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be logged without writing to the ledger",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip re-enrichment even if rankings are missing",
    )
    args = parser.parse_args()

    # Resolve scan file
    scan_path = Path(args.scan) if args.scan else find_latest_scan()
    if not scan_path.exists():
        print(f"Error: scan file not found: {scan_path}", file=sys.stderr)
        return 1

    scan = load_scan(scan_path)

    # Enrich if needed
    if not is_enriched(scan) and not args.skip_enrich:
        enrich_scan(scan_path)
        scan = load_scan(scan_path)  # reload after enrichment

    rankings = scan.get("validation", {}).get("rankings", {})
    results_by_symbol = scan.get("validation", {}).get("results_by_symbol", {})

    if not rankings:
        print("Error: no rankings found in scan. Run validate_scan.py --enrich-setups --rank first.", file=sys.stderr)
        return 1

    # Determine which setup types to process
    if args.setup == "both":
        setup_types = ["2w_breakout", "2m_pullback"]
    else:
        setup_types = [args.setup]

    logged = []
    skipped = []

    for setup_type in setup_types:
        candidates = rankings.get(setup_type, [])[:args.top]
        if not candidates:
            print(f"  No candidates for {setup_type}")
            continue

        print(f"\n{setup_type} — top {len(candidates)} picks:")
        for candidate in candidates:
            symbol = candidate["symbol"]
            score = candidate.get("score", 0)
            why = candidate.get("why", "")

            params = derive_params(symbol, setup_type, score, results_by_symbol)
            if params is None:
                print(f"  SKIP  {symbol:20s} — no OHLCV data")
                skipped.append({"symbol": symbol, "setup": setup_type, "reason": "no_ohlcv"})
                continue

            result = log_suggestion(symbol, params, dry_run=args.dry_run)

            status = result.get("status", "?")
            suggestion_id = result.get("id", "?")

            action_label = "[DRY]" if args.dry_run else "[LOG]"
            print(
                f"  {action_label} {symbol:20s} score={score:5.1f}  "
                f"{params['confidence']:6s}  {params['strategy']:9s}  "
                f"price={params['price_now']:8.2f}  "
                f"T1={params['target_1']:8.2f}  SL={params['stop_loss']:8.2f}  "
                f"id={suggestion_id}  why={why[:40]}"
            )

            if status in ("logged", "dry_run"):
                logged.append({
                    "symbol": symbol,
                    "setup": setup_type,
                    "score": score,
                    "strategy": params["strategy"],
                    "confidence": params["confidence"],
                    "price_now": params["price_now"],
                    "suggestion_id": suggestion_id,
                })
            else:
                skipped.append({
                    "symbol": symbol,
                    "setup": setup_type,
                    "reason": result.get("stderr") or result.get("raw") or status,
                })

    # Summary
    print(f"\n{'DRY RUN ' if args.dry_run else ''}Summary:")
    print(f"  Scan file:  {scan_path.name}")
    print(f"  Logged:     {len(logged)}")
    print(f"  Skipped:    {len(skipped)}")
    if logged:
        print(f"  Ledger:     data/suggestions/ledger.jsonl")
    if skipped:
        print(f"  Skipped:    {[s['symbol'] for s in skipped]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
