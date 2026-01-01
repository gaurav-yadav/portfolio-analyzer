#!/usr/bin/env python3
"""Fetch OHLCV data from Yahoo Finance for Indian stocks."""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import load_json, save_json

# Constants
CACHE_DIR = Path(__file__).parent.parent / "cache" / "ohlcv"
CACHE_METADATA_PATH = Path(__file__).parent.parent / "cache" / "cache_metadata.json"
CACHE_FRESHNESS_HOURS = 18
MAX_RETRIES = 3
LOOKBACK_PERIOD = "1y"


def log(msg: str) -> None:
    """Print message to stderr for logging."""
    print(msg, file=sys.stderr)


def is_cache_fresh(symbol: str, metadata: dict) -> bool:
    """Check if cached data for symbol is fresh (< 18 hours old)."""
    if symbol not in metadata:
        return False

    last_fetched_str = metadata[symbol].get("last_fetched")
    if not last_fetched_str:
        return False

    try:
        last_fetched = datetime.fromisoformat(last_fetched_str)
        age = datetime.now() - last_fetched
        return age < timedelta(hours=CACHE_FRESHNESS_HOURS)
    except (ValueError, TypeError):
        return False


def fetch_with_retry(symbol: str) -> pd.DataFrame | None:
    """Fetch OHLCV data with exponential backoff retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"Attempt {attempt}/{MAX_RETRIES}: Fetching {symbol}...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=LOOKBACK_PERIOD)

            if df is not None and not df.empty:
                log(f"Successfully fetched {len(df)} rows for {symbol}")
                return df

            log(f"No data returned for {symbol}")
            return None

        except Exception as e:
            log(f"Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                delay = 2**attempt  # Exponential backoff: 2, 4, 8 seconds
                log(f"Retrying in {delay} seconds...")
                time.sleep(delay)

    return None


def try_fetch_with_fallback(symbol: str) -> tuple[pd.DataFrame | None, str]:
    """
    Try fetching with the given symbol, fallback to .BO if .NS fails.

    Returns:
        Tuple of (dataframe, actual_symbol_used)
    """
    # First try the original symbol
    df = fetch_with_retry(symbol)
    if df is not None and not df.empty:
        return df, symbol

    # If symbol ends with .NS, try .BO fallback
    if symbol.upper().endswith(".NS"):
        fallback_symbol = symbol[:-3] + ".BO"
        log(f"NSE fetch failed, trying BSE fallback: {fallback_symbol}")
        df = fetch_with_retry(fallback_symbol)
        if df is not None and not df.empty:
            return df, fallback_symbol

    return None, symbol


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        log("Usage: python fetch_ohlcv.py <symbol>")
        log("Example: python fetch_ohlcv.py RELIANCE.NS")
        sys.exit(1)

    symbol = sys.argv[1].strip().upper()

    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Load cache metadata
    metadata = load_json(CACHE_METADATA_PATH) or {}

    # Check if cache is fresh
    cache_path = CACHE_DIR / f"{symbol}.parquet"
    if cache_path.exists() and is_cache_fresh(symbol, metadata):
        log(f"Cache hit: {symbol} data is fresh (< {CACHE_FRESHNESS_HOURS} hours old)")
        cached_meta = metadata[symbol]
        result = {
            "symbol": symbol,
            "status": "cached",
            "cache_hit": True,
            "rows": cached_meta.get("rows", 0),
            "data_start": cached_meta.get("data_start"),
            "data_end": cached_meta.get("data_end"),
            "cache_path": str(cache_path.relative_to(Path(__file__).parent.parent)),
        }
        print(json.dumps(result, indent=2))
        return

    log(f"Cache miss: Fetching fresh data for {symbol}")

    # Fetch data with fallback
    df, actual_symbol = try_fetch_with_fallback(symbol)

    if df is None or df.empty:
        log(f"ERROR: Failed to fetch data for {symbol}")
        result = {
            "symbol": symbol,
            "status": "error",
            "cache_hit": False,
            "error": f"No data available for {symbol}",
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # Update cache path if fallback was used
    if actual_symbol != symbol:
        cache_path = CACHE_DIR / f"{actual_symbol}.parquet"
        log(f"Using fallback symbol: {actual_symbol}")

    # Save to parquet
    df.to_parquet(cache_path)
    log(f"Saved {len(df)} rows to {cache_path}")

    # Update metadata
    data_start = df.index.min().strftime("%Y-%m-%d") if len(df) > 0 else None
    data_end = df.index.max().strftime("%Y-%m-%d") if len(df) > 0 else None

    metadata[actual_symbol] = {
        "last_fetched": datetime.now().isoformat(),
        "data_start": data_start,
        "data_end": data_end,
        "rows": len(df),
    }

    # Also update original symbol if fallback was used
    if actual_symbol != symbol:
        metadata[symbol] = {
            "last_fetched": datetime.now().isoformat(),
            "data_start": data_start,
            "data_end": data_end,
            "rows": len(df),
            "resolved_to": actual_symbol,
        }

    save_json(CACHE_METADATA_PATH, metadata)
    log(f"Updated cache metadata")

    # Output JSON summary
    result = {
        "symbol": actual_symbol,
        "original_symbol": symbol if actual_symbol != symbol else None,
        "status": "fetched",
        "cache_hit": False,
        "rows": len(df),
        "data_start": data_start,
        "data_end": data_end,
        "cache_path": str(cache_path.relative_to(Path(__file__).parent.parent)),
    }
    # Remove None values
    result = {k: v for k, v in result.items() if v is not None}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
