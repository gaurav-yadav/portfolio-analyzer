#!/usr/bin/env python3
"""
Batch Technical Analysis - Runs technical analysis for all holdings.

Usage:
    uv run python scripts/technical_all.py
    uv run python scripts/technical_all.py --watchlist-id swing
    uv run python scripts/technical_all.py --symbols RELIANCE.NS TCS.NS
    uv run python scripts/technical_all.py --holdings --watchlist-id swing

Reads holdings from data/holdings.json and computes technical indicators for each unique symbol.
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data import load_watchlist, watchlist_symbols, list_watchlists, all_watchlist_symbols  # noqa: E402


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


def main():
    base_path = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Run technical analysis for holdings/watchlist/symbols.")
    parser.add_argument(
        "--holdings",
        action="store_true",
        help="Include symbols from data/holdings.json (default if no other input is provided).",
    )
    parser.add_argument(
        "--watchlist-id",
        default="",
        help="Include symbols from data/watchlists/<watchlist_id>.json.",
    )
    parser.add_argument(
        "--all-watchlists",
        action="store_true",
        help="Include symbols from all watchlists.",
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

    use_holdings = args.holdings
    use_watchlist = bool(args.watchlist_id)
    use_all_watchlists = args.all_watchlists
    explicit_symbols = [s for s in (args.symbols or []) if s.strip()]

    # Backward-compatible default: if user passes no selectors, use holdings.
    if not use_holdings and not use_watchlist and not use_all_watchlists and not explicit_symbols:
        use_holdings = True

    symbols: list[str] = []
    if use_holdings:
        if not holdings_file.exists():
            print("Error: data/holdings.json not found. Import/parse holdings first, or pass --symbols/--watchlist-id.", file=sys.stderr)
            sys.exit(1)
        symbols.extend(load_holdings_symbols(holdings_file))
    if use_watchlist:
        wl_syms = watchlist_symbols(args.watchlist_id)
        if not wl_syms:
            print(f"Error: watchlist '{args.watchlist_id}' not found or empty.", file=sys.stderr)
            sys.exit(1)
        symbols.extend(wl_syms)  # Already YF-formatted by data layer
    if use_all_watchlists:
        symbols.extend(all_watchlist_symbols().keys())  # Already YF-formatted
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
        print("No symbols to analyze. Provide --holdings, --watchlist-id, or --symbols.", file=sys.stderr)
        sys.exit(1)

    print(f"Running technical analysis for {total} unique symbols...")

    # New modular TA scripts — output saved to data/ta/<symbol>_<name>.json
    TA_SCRIPTS = [
        ("stoch_rsi",  "scripts/ta/stoch_rsi.py"),
        ("divergence", "scripts/ta/divergence.py"),
        ("patterns",   "scripts/ta/patterns.py"),
        ("entry_points","scripts/ta/entry_points.py"),
    ]
    ta_dir = base_path / "data" / "ta"
    ta_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = []

    for i, symbol in enumerate(unique_symbols, 1):
        print(f"[{i}/{total}] Analyzing {symbol}...", end=" ", flush=True)

        # Core scoring script (RSI, MACD, SMA, Bollinger, ADX, Volume → weighted score)
        result = subprocess.run(
            ["uv", "run", "python", "scripts/technical_analysis.py", symbol],
            capture_output=True, text=True, cwd=base_path
        )
        if result.returncode != 0:
            print("FAILED (core)")
            failed.append(symbol)
            continue

        # Modular TA scripts (StochRSI, divergence, patterns, entry points)
        ta_ok = True
        for name, script in TA_SCRIPTS:
            ta_result = subprocess.run(
                ["uv", "run", "python", script, symbol],
                capture_output=True, text=True, cwd=base_path
            )
            if ta_result.returncode == 0 and ta_result.stdout.strip():
                out_path = ta_dir / f"{symbol}_{name}.json"
                out_path.write_text(ta_result.stdout.strip(), encoding="utf-8")
            else:
                ta_ok = False  # Non-fatal — core analysis still counts

        print("OK" if ta_ok else "OK (some ta scripts skipped)")
        success += 1

    print(f"\nComplete: {success}/{total} succeeded")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
