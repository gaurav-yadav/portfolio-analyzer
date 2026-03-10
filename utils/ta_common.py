"""Common utilities for technical analysis scripts - DRY principle.

NOTE: load_ohlcv() and output_result() delegate to utils.data internally.
      find_swing_points() delegates to utils.indicators.
      Kept for backward compatibility — new code should import from
      utils.data and utils.indicators directly.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Lazy imports to avoid circular dependency
# (data.py imports NumpyEncoder from ta_common)
_data_module = None
_indicators_module = None


def _get_data():
    global _data_module
    if _data_module is None:
        from utils import data as _dm
        _data_module = _dm
    return _data_module


def _get_indicators():
    global _indicators_module
    if _indicators_module is None:
        from utils import indicators as _im
        _indicators_module = _im
    return _indicators_module


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
    """Load OHLCV data for symbol from parquet cache.

    Delegates to utils.data.load_ohlcv() internally but raises on missing
    data (backward compat — data layer returns None).
    """
    df = _get_data().load_ohlcv(symbol)
    if df is None:
        path = CACHE_DIR / f"{symbol}.parquet"
        raise FileNotFoundError(f"OHLCV data not found: {path}")
    if len(df) < 50:
        raise ValueError(f"Insufficient data: {len(df)} rows, need 50+")
    return df


def output_result(result: dict, symbol: str, indicator: str) -> None:
    """Output result to stdout (JSON) and save to file.

    Delegates file writing to utils.data.save_ta().
    """
    _get_data().save_ta(symbol, indicator, result)
    log(f"Saved to {OUTPUT_DIR / f'{symbol}_{indicator}.json'}")

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
