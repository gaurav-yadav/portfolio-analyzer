#!/usr/bin/env python3
"""
Batch Scorer - Scores all holdings.

Usage:
    uv run python scripts/score_all.py

Reads holdings from data/holdings.json and scores each holding (per broker).
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

    total = len(holdings)
    print(f"Scoring {total} holdings...")

    success = 0
    failed = []

    for i, holding in enumerate(holdings, 1):
        symbol = holding["symbol_yf"]
        broker = holding.get("broker", "unknown")
        display = f"{holding['symbol']}@{broker}"

        print(f"[{i}/{total}] Scoring {display}...", end=" ", flush=True)

        cmd = ["uv", "run", "python", "scripts/score_stock.py", symbol]
        if broker and broker != "unknown":
            cmd.extend(["--broker", broker])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=base_path
        )
        if result.returncode == 0:
            print("OK")
            success += 1
        else:
            print("FAILED")
            failed.append(display)

    print(f"\nComplete: {success}/{total} succeeded")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
