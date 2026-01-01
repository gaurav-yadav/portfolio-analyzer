#!/usr/bin/env python3
"""
Batch Technical Analysis - Runs technical analysis for all holdings.

Usage:
    uv run python scripts/technical_all.py

Reads holdings from data/holdings.json and computes technical indicators for each unique symbol.
"""

import json
import subprocess
import sys
from pathlib import Path

def main():
    base_path = Path(__file__).parent.parent
    holdings_file = base_path / "data" / "holdings.json"

    if not holdings_file.exists():
        print("Error: data/holdings.json not found. Run parse_csv.py first.", file=sys.stderr)
        sys.exit(1)

    with open(holdings_file) as f:
        holdings = json.load(f)

    # Get unique symbols (technical analysis is same regardless of broker)
    unique_symbols = list(set(h["symbol_yf"] for h in holdings))
    total = len(unique_symbols)

    print(f"Running technical analysis for {total} unique symbols...")

    success = 0
    failed = []

    for i, symbol in enumerate(unique_symbols, 1):
        print(f"[{i}/{total}] Analyzing {symbol}...", end=" ", flush=True)
        result = subprocess.run(
            ["uv", "run", "python", "scripts/technical_analysis.py", symbol],
            capture_output=True,
            text=True,
            cwd=base_path
        )
        if result.returncode == 0:
            print("OK")
            success += 1
        else:
            print("FAILED")
            failed.append(symbol)

    print(f"\nComplete: {success}/{total} succeeded")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
