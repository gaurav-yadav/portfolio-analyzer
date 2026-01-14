#!/usr/bin/env python3
"""
Batch Technical Analysis - Runs technical analysis for all holdings.

Usage:
    uv run python scripts/technical_all.py
    uv run python scripts/technical_all.py --watchlist
    uv run python scripts/technical_all.py --symbols RELIANCE.NS TCS.NS
    uv run python scripts/technical_all.py --holdings --watchlist --default-suffix .NS

Reads holdings from data/holdings.json and computes technical indicators for each unique symbol.
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path

def normalize_yf_symbol(symbol: str, default_suffix: str) -> str:
    s = symbol.strip().upper()
    if not s:
        return ""
    if "." in s:
        return s
    return f"{s}{default_suffix}" if default_suffix else s


def load_holdings_symbols(holdings_path: Path) -> list[str]:
    if not holdings_path.exists():
        return []
    with open(holdings_path) as f:
        holdings = json.load(f)
    return [h["symbol_yf"] for h in holdings if h.get("symbol_yf")]


def load_watchlist_symbols(watchlist_path: Path, default_suffix: str) -> list[str]:
    if not watchlist_path.exists():
        return []
    with open(watchlist_path) as f:
        watchlist = json.load(f)
    stocks = watchlist.get("stocks") or []
    symbols: list[str] = []
    for stock in stocks:
        raw = (stock.get("symbol") or "").strip()
        if not raw:
            continue
        symbols.append(normalize_yf_symbol(raw, default_suffix))
    return symbols


def main():
    base_path = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Run technical analysis for holdings/watchlist/symbols.")
    parser.add_argument(
        "--holdings",
        action="store_true",
        help="Include symbols from data/holdings.json (default if no other input is provided).",
    )
    parser.add_argument(
        "--watchlist",
        action="store_true",
        help="Include symbols from data/watchlist.json (symbols without suffix will use --default-suffix).",
    )
    parser.add_argument(
        "--default-suffix",
        default=".NS",
        help="Suffix to append for watchlist symbols without an exchange suffix (default: .NS). Use '' for none.",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=[],
        help="Explicit Yahoo Finance tickers to analyze (e.g., RELIANCE.NS MSFT).",
    )
    args = parser.parse_args()

    holdings_file = base_path / "data" / "holdings.json"
    watchlist_file = base_path / "data" / "watchlist.json"

    use_holdings = args.holdings
    use_watchlist = args.watchlist
    explicit_symbols = [s for s in (args.symbols or []) if s.strip()]

    # Backward-compatible default: if user passes no selectors, use holdings.
    if not use_holdings and not use_watchlist and not explicit_symbols:
        use_holdings = True

    symbols: list[str] = []
    if use_holdings:
        if not holdings_file.exists():
            print("Error: data/holdings.json not found. Import/parse holdings first, or pass --symbols/--watchlist.", file=sys.stderr)
            sys.exit(1)
        symbols.extend(load_holdings_symbols(holdings_file))
    if use_watchlist:
        symbols.extend(load_watchlist_symbols(watchlist_file, args.default_suffix))
    symbols.extend([normalize_yf_symbol(s, default_suffix="") for s in explicit_symbols])

    # Deduplicate while preserving order
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        if not s or s in seen:
            continue
        unique_symbols.append(s)
        seen.add(s)

    total = len(unique_symbols)
    if total == 0:
        print("No symbols to analyze. Provide --holdings, --watchlist, or --symbols.", file=sys.stderr)
        sys.exit(1)

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
