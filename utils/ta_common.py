"""Common utilities for technical analysis scripts - DRY principle."""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


BASE_PATH = Path(__file__).parent.parent
CACHE_DIR = BASE_PATH / "cache" / "ohlcv"
OUTPUT_DIR = BASE_PATH / "data" / "ta"


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if pd.isna(obj):
            return None
        return super().default(obj)


def log(msg: str) -> None:
    """Print to stderr for logging."""
    print(msg, file=sys.stderr)


def safe_round(val, decimals: int = 4):
    """Safely round a value, handling NaN/None."""
    if val is None or pd.isna(val):
        return None
    return round(float(val), decimals)


def load_ohlcv(symbol: str) -> pd.DataFrame:
    """
    Load OHLCV data for symbol from parquet cache.

    Args:
        symbol: Stock symbol (e.g., AAPL, RELIANCE.NS)

    Returns:
        DataFrame with OHLCV columns

    Raises:
        FileNotFoundError: If cache file doesn't exist
        ValueError: If data is insufficient
    """
    # Try exact symbol first
    path = CACHE_DIR / f"{symbol}.parquet"

    # If not found, try with .NS suffix for Indian stocks
    if not path.exists() and not any(symbol.endswith(s) for s in ['.NS', '.BO']):
        path = CACHE_DIR / f"{symbol}.NS.parquet"

    if not path.exists():
        raise FileNotFoundError(f"OHLCV data not found: {path}")

    df = pd.read_parquet(path)

    if len(df) < 50:
        raise ValueError(f"Insufficient data: {len(df)} rows, need 50+")

    return df


def output_result(result: dict, symbol: str, indicator: str) -> None:
    """
    Output result to stdout (JSON) and save to file.

    Args:
        result: Analysis result dict
        symbol: Stock symbol
        indicator: Indicator name (for filename)
    """
    # Add metadata
    result["symbol"] = symbol
    result["indicator"] = indicator
    result["timestamp"] = datetime.now().isoformat()

    # Save to file
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{symbol}_{indicator}.json"

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)

    log(f"Saved to {output_path}")

    # Print to stdout
    print(json.dumps(result, indent=2, cls=NumpyEncoder))


def get_symbol_from_args() -> str:
    """Get symbol from command line args."""
    if len(sys.argv) < 2:
        print(f"Usage: uv run python {sys.argv[0]} <symbol>", file=sys.stderr)
        sys.exit(1)
    return sys.argv[1].strip().upper()


def find_swing_points(df: pd.DataFrame, window: int = 10) -> tuple[list, list]:
    """
    Find swing highs and lows in price data.

    Returns:
        Tuple of (highs, lows) where each is list of (date, price)
    """
    highs, lows = [], []

    for i in range(window, len(df) - window):
        high_window = df['High'].iloc[i-window:i+window+1]
        low_window = df['Low'].iloc[i-window:i+window+1]

        if df['High'].iloc[i] == high_window.max():
            highs.append((df.index[i], df['High'].iloc[i]))

        if df['Low'].iloc[i] == low_window.min():
            lows.append((df.index[i], df['Low'].iloc[i]))

    return highs, lows


def format_date(dt) -> str:
    """Format datetime/date to string."""
    if hasattr(dt, 'date'):
        return str(dt.date())
    return str(dt)
