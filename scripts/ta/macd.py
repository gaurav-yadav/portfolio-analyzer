#!/usr/bin/env python3
"""
MACD (Moving Average Convergence Divergence) Analysis

Usage: uv run python scripts/ta/macd.py <symbol>

Computes MACD(12,26,9) and provides momentum signals.
- Bullish crossover + positive histogram = momentum confirmation for entry
- MACD above zero line = bullish bias
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log, format_date


def analyze_macd(df, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """Compute MACD and generate signals."""
    df = df.copy()

    macd_result = ta.macd(df['Close'], fast=fast, slow=slow, signal=signal)
    if macd_result is None:
        return {"error": "Could not compute MACD"}

    df['macd'] = macd_result.iloc[:, 0]
    df['macd_hist'] = macd_result.iloc[:, 1]
    df['macd_signal'] = macd_result.iloc[:, 2]

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    macd_val = safe_round(latest['macd'], 4)
    signal_val = safe_round(latest['macd_signal'], 4)
    histogram = safe_round(latest['macd_hist'], 4)

    prev_macd = safe_round(prev['macd'], 4)
    prev_signal = safe_round(prev['macd_signal'], 4)

    # Determine crossover
    crossover = None
    crossover_date = None

    # Check last 10 days for recent crossover
    recent = df.tail(10)
    for i in range(1, len(recent)):
        curr_row = recent.iloc[i]
        prev_row = recent.iloc[i-1]

        if prev_row['macd'] <= prev_row['macd_signal'] and curr_row['macd'] > curr_row['macd_signal']:
            crossover = "bullish"
            crossover_date = format_date(recent.index[i])

        if prev_row['macd'] >= prev_row['macd_signal'] and curr_row['macd'] < curr_row['macd_signal']:
            crossover = "bearish"
            crossover_date = format_date(recent.index[i])

    # Current state
    above_signal = macd_val > signal_val if macd_val and signal_val else None
    above_zero = macd_val > 0 if macd_val else None
    hist_rising = histogram > safe_round(prev['macd_hist'], 4) if histogram else None

    # Signal determination
    if above_signal and above_zero and hist_rising:
        signal_type = "strong_bullish"
        entry_signal = "momentum_confirmed"
    elif above_signal and hist_rising:
        signal_type = "bullish"
        entry_signal = "momentum_building"
    elif above_signal:
        signal_type = "weak_bullish"
        entry_signal = "wait_for_histogram"
    elif not above_signal and not above_zero:
        signal_type = "bearish"
        entry_signal = "avoid_entry"
    else:
        signal_type = "neutral"
        entry_signal = "wait"

    return {
        "macd": macd_val,
        "signal_line": signal_val,
        "histogram": histogram,
        "params": {"fast": fast, "slow": slow, "signal": signal},
        "above_signal_line": above_signal,
        "above_zero_line": above_zero,
        "histogram_rising": hist_rising,
        "signal": signal_type,
        "recent_crossover": crossover,
        "crossover_date": crossover_date,
        "entry_signal": entry_signal,
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing MACD for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_macd(df)
        output_result(result, symbol, "macd")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
