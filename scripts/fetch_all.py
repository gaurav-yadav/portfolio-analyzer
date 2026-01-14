#!/usr/bin/env python3
"""
Batch OHLCV Fetcher - Fetches data for all holdings with throttling.

Usage:
    uv run python scripts/fetch_all.py
    uv run python scripts/fetch_all.py --watchlist
    uv run python scripts/fetch_all.py --symbols RELIANCE.NS TCS.NS
    uv run python scripts/fetch_all.py --holdings --watchlist --default-suffix .NS

Reads holdings from data/holdings.json and fetches OHLCV for each unique symbol.
Includes rate limiting and retry logic to avoid overwhelming Yahoo Finance.
"""

import json
import argparse
import subprocess
import sys
import time
from pathlib import Path

# Throttling settings
DELAY_BETWEEN_REQUESTS = 0.5  # seconds between API calls
RETRY_DELAY = 3  # seconds before retrying failed symbols
MAX_RETRY_ROUNDS = 2  # retry failed symbols up to N times


def normalize_yf_symbol(symbol: str, default_suffix: str) -> str:
    """
    Normalize a symbol into a Yahoo Finance-compatible ticker.

    - If symbol already contains an exchange suffix (e.g., RELIANCE.NS), keep it.
    - If it looks like a US ticker (no suffix) and default_suffix is "", keep it.
    - Otherwise, append default_suffix (commonly ".NS" for India).
    """
    s = symbol.strip().upper()
    if not s:
        return ""
    if "." in s:
        return s
    return f"{s}{default_suffix}" if default_suffix else s


def fetch_symbol(symbol: str, base_path: Path) -> bool:
    """Fetch a single symbol. Returns True on success."""
    result = subprocess.run(
        ["uv", "run", "python", "scripts/fetch_ohlcv.py", symbol],
        capture_output=True,
        text=True,
        cwd=base_path
    )
    return result.returncode == 0


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
    symbols = []
    for stock in stocks:
        raw = (stock.get("symbol") or "").strip()
        if not raw:
            continue
        symbols.append(normalize_yf_symbol(raw, default_suffix))
    return symbols


def main():
    base_path = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Fetch OHLCV for holdings/watchlist/symbols with caching and throttling.")
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
        help="Explicit Yahoo Finance tickers to fetch (e.g., RELIANCE.NS MSFT).",
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
        print("No symbols to fetch. Provide --holdings, --watchlist, or --symbols.", file=sys.stderr)
        sys.exit(1)

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
