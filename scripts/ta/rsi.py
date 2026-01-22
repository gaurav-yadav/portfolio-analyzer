#!/usr/bin/env python3
"""
RSI (Relative Strength Index) Analysis

Usage: uv run python scripts/ta/rsi.py <symbol>

Computes RSI(14) and provides overbought/oversold signals.
- >70: Overbought (don't chase)
- <30: Oversold (watch for reversal)
- 30-70: Neutral zone
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log


def analyze_rsi(df, period: int = 14) -> dict:
    """Compute RSI and generate signals."""
    df = df.copy()
    df['rsi'] = ta.rsi(df['Close'], length=period)

    current = safe_round(df['rsi'].iloc[-1], 2)
    prev = safe_round(df['rsi'].iloc[-2], 2)
    prev_5d = safe_round(df['rsi'].iloc[-5], 2) if len(df) >= 5 else None

    # Determine signal
    if current is None:
        signal = "no_data"
        signal_strength = 0
    elif current < 30:
        signal = "oversold"
        signal_strength = min(10, int((30 - current) / 3))  # 0-10 scale
    elif current > 70:
        signal = "overbought"
        signal_strength = min(10, int((current - 70) / 3))
    elif current < 40:
        signal = "approaching_oversold"
        signal_strength = 3
    elif current > 60:
        signal = "approaching_overbought"
        signal_strength = 3
    else:
        signal = "neutral"
        signal_strength = 0

    # Trend (rising/falling)
    trend = None
    if current and prev:
        if current > prev:
            trend = "rising"
        elif current < prev:
            trend = "falling"
        else:
            trend = "flat"

    # Entry recommendation
    entry_signal = None
    if signal == "oversold":
        entry_signal = "potential_entry_zone"
    elif signal == "overbought":
        entry_signal = "avoid_entry"
    elif signal == "approaching_oversold" and trend == "falling":
        entry_signal = "wait_for_reversal"

    return {
        "rsi": current,
        "rsi_prev": prev,
        "rsi_5d_ago": prev_5d,
        "period": period,
        "signal": signal,
        "signal_strength": signal_strength,
        "trend": trend,
        "entry_signal": entry_signal,
        "thresholds": {"oversold": 30, "overbought": 70},
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing RSI for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_rsi(df)
        output_result(result, symbol, "rsi")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
