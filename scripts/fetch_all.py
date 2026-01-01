#!/usr/bin/env python3
"""
Batch OHLCV Fetcher - Fetches data for all holdings with throttling.

Usage:
    uv run python scripts/fetch_all.py

Reads holdings from data/holdings.json and fetches OHLCV for each unique symbol.
Includes rate limiting and retry logic to avoid overwhelming Yahoo Finance.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# Throttling settings
DELAY_BETWEEN_REQUESTS = 0.5  # seconds between API calls
RETRY_DELAY = 3  # seconds before retrying failed symbols
MAX_RETRY_ROUNDS = 2  # retry failed symbols up to N times


def fetch_symbol(symbol: str, base_path: Path) -> bool:
    """Fetch a single symbol. Returns True on success."""
    result = subprocess.run(
        ["uv", "run", "python", "scripts/fetch_ohlcv.py", symbol],
        capture_output=True,
        text=True,
        cwd=base_path
    )
    return result.returncode == 0


def main():
    base_path = Path(__file__).parent.parent
    holdings_file = base_path / "data" / "holdings.json"

    if not holdings_file.exists():
        print("Error: data/holdings.json not found. Run parse_csv.py first.", file=sys.stderr)
        sys.exit(1)

    with open(holdings_file) as f:
        holdings = json.load(f)

    # Get unique symbols (avoid fetching same stock twice for multi-broker)
    unique_symbols = list(set(h["symbol_yf"] for h in holdings))
    total = len(unique_symbols)

    print(f"Fetching OHLCV for {total} unique symbols (with {DELAY_BETWEEN_REQUESTS}s throttle)...")

    success = 0
    failed = []

    # First pass
    for i, symbol in enumerate(unique_symbols, 1):
        # Throttle: delay between requests (except first)
        if i > 1:
            time.sleep(DELAY_BETWEEN_REQUESTS)

        print(f"[{i}/{total}] Fetching {symbol}...", end=" ", flush=True)

        if fetch_symbol(symbol, base_path):
            print("OK")
            success += 1
        else:
            print("FAILED")
            failed.append(symbol)

    # Retry failed symbols
    retry_round = 0
    while failed and retry_round < MAX_RETRY_ROUNDS:
        retry_round += 1
        print(f"\n--- Retry round {retry_round}/{MAX_RETRY_ROUNDS} for {len(failed)} failed symbols ---")
        time.sleep(RETRY_DELAY)

        still_failed = []
        for i, symbol in enumerate(failed, 1):
            if i > 1:
                time.sleep(DELAY_BETWEEN_REQUESTS)

            print(f"[Retry {i}/{len(failed)}] {symbol}...", end=" ", flush=True)

            if fetch_symbol(symbol, base_path):
                print("OK")
                success += 1
            else:
                print("FAILED")
                still_failed.append(symbol)

        failed = still_failed

    # Summary
    print(f"\n{'='*40}")
    print(f"Complete: {success}/{total} succeeded")
    if failed:
        print(f"Failed after {MAX_RETRY_ROUNDS} retries: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All symbols fetched successfully!")


if __name__ == "__main__":
    main()
