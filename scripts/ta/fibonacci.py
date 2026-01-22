#!/usr/bin/env python3
"""
Fibonacci Retracement Analysis

Usage: uv run python scripts/ta/fibonacci.py <symbol>

Computes Fibonacci retracement levels from swing high/low.
- 61.8% and 50% levels are classical reversal/entry zones
- Also computes extension levels for targets
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import (
    load_ohlcv, output_result, get_symbol_from_args,
    safe_round, log, format_date, find_swing_points
)


def analyze_fibonacci(df, lookback: int = 60) -> dict:
    """Compute Fibonacci retracement levels."""
    recent = df.tail(lookback)
    current_price = safe_round(df['Close'].iloc[-1], 2)

    swing_high = recent['High'].max()
    swing_low = recent['Low'].min()
    swing_high_date = recent['High'].idxmax()
    swing_low_date = recent['Low'].idxmin()

    # Determine trend direction
    is_uptrend = swing_low_date < swing_high_date
    diff = swing_high - swing_low

    # Calculate retracement levels
    if is_uptrend:
        # In uptrend, retracements are measured from high going down
        levels = {
            "0.0_high": safe_round(swing_high, 2),
            "0.236": safe_round(swing_high - diff * 0.236, 2),
            "0.382": safe_round(swing_high - diff * 0.382, 2),
            "0.5": safe_round(swing_high - diff * 0.5, 2),
            "0.618": safe_round(swing_high - diff * 0.618, 2),
            "0.786": safe_round(swing_high - diff * 0.786, 2),
            "1.0_low": safe_round(swing_low, 2),
        }
        extensions = {
            "1.272": safe_round(swing_low + diff * 1.272, 2),
            "1.618": safe_round(swing_low + diff * 1.618, 2),
        }
    else:
        # In downtrend, retracements from low going up
        levels = {
            "0.0_low": safe_round(swing_low, 2),
            "0.236": safe_round(swing_low + diff * 0.236, 2),
            "0.382": safe_round(swing_low + diff * 0.382, 2),
            "0.5": safe_round(swing_low + diff * 0.5, 2),
            "0.618": safe_round(swing_low + diff * 0.618, 2),
            "0.786": safe_round(swing_low + diff * 0.786, 2),
            "1.0_high": safe_round(swing_high, 2),
        }
        extensions = {
            "1.272": safe_round(swing_high - diff * 1.272, 2),
            "1.618": safe_round(swing_high - diff * 1.618, 2),
        }

    # Find entry zones (50% and 61.8% levels)
    entry_zone_50 = levels["0.5"]
    entry_zone_618 = levels["0.618"]

    # Determine current position relative to levels
    position = None
    nearest_level = None
    nearest_distance = float('inf')

    for level_name, level_price in levels.items():
        if level_price:
            dist = abs(current_price - level_price)
            pct_dist = dist / current_price * 100
            if pct_dist < nearest_distance:
                nearest_distance = pct_dist
                nearest_level = level_name

    # Entry signal
    entry_signal = None
    if current_price and entry_zone_618:
        dist_to_618 = abs(current_price - entry_zone_618) / current_price * 100
        dist_to_50 = abs(current_price - entry_zone_50) / current_price * 100

        if dist_to_618 < 2:
            entry_signal = "at_golden_ratio_618"
            position = "entry_zone"
        elif dist_to_50 < 2:
            entry_signal = "at_50_retracement"
            position = "entry_zone"
        elif current_price < entry_zone_618:
            entry_signal = "below_entry_zones"
            position = "deep_pullback"
        elif current_price > entry_zone_50:
            entry_signal = "above_entry_zones"
            position = "wait_for_pullback"

    return {
        "current_price": current_price,
        "swing_high": safe_round(swing_high, 2),
        "swing_low": safe_round(swing_low, 2),
        "swing_high_date": format_date(swing_high_date),
        "swing_low_date": format_date(swing_low_date),
        "trend_direction": "uptrend" if is_uptrend else "downtrend",
        "lookback_days": lookback,
        "retracement_levels": levels,
        "extension_levels": extensions,
        "entry_zones": {
            "golden_ratio_618": entry_zone_618,
            "fifty_percent": entry_zone_50,
        },
        "nearest_level": nearest_level,
        "position": position,
        "entry_signal": entry_signal,
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing Fibonacci levels for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_fibonacci(df)
        output_result(result, symbol, "fibonacci")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
