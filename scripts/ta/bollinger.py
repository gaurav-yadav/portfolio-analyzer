#!/usr/bin/env python3
"""
Bollinger Bands Analysis

Usage: uv run python scripts/ta/bollinger.py <symbol>

Computes Bollinger Bands (20,2) for mean reversion signals.
- %B > 1: Overextended above upper band
- %B < 0: Oversold below lower band
- %B 0.4-0.6: Middle of bands (neutral)
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log


def analyze_bollinger(df, length: int = 20, std: float = 2.0) -> dict:
    """Compute Bollinger Bands and generate signals."""
    df = df.copy()

    bbands = ta.bbands(df['Close'], length=length, std=std)
    if bbands is None:
        return {"error": "Could not compute Bollinger Bands"}

    df['bb_lower'] = bbands.iloc[:, 0]
    df['bb_middle'] = bbands.iloc[:, 1]
    df['bb_upper'] = bbands.iloc[:, 2]
    df['bb_bandwidth'] = bbands.iloc[:, 3]
    df['bb_pctb'] = bbands.iloc[:, 4]

    latest = df.iloc[-1]
    price = safe_round(latest['Close'], 2)
    upper = safe_round(latest['bb_upper'], 2)
    middle = safe_round(latest['bb_middle'], 2)
    lower = safe_round(latest['bb_lower'], 2)
    pctb = safe_round(latest['bb_pctb'], 4)
    bandwidth = safe_round(latest['bb_bandwidth'], 4)

    # Determine position and signal
    if pctb is None:
        signal = "no_data"
        position = "unknown"
    elif pctb > 1:
        signal = "overextended"
        position = "above_upper_band"
    elif pctb < 0:
        signal = "oversold"
        position = "below_lower_band"
    elif pctb > 0.8:
        signal = "approaching_upper"
        position = "upper_zone"
    elif pctb < 0.2:
        signal = "approaching_lower"
        position = "lower_zone"
    else:
        signal = "neutral"
        position = "middle_zone"

    # Bandwidth analysis (volatility)
    avg_bandwidth = df['bb_bandwidth'].tail(20).mean()
    bandwidth_expanding = bandwidth > avg_bandwidth * 1.1 if bandwidth and avg_bandwidth else None
    bandwidth_contracting = bandwidth < avg_bandwidth * 0.9 if bandwidth and avg_bandwidth else None

    volatility_state = "normal"
    if bandwidth_expanding:
        volatility_state = "expanding"
    elif bandwidth_contracting:
        volatility_state = "contracting"

    # Entry signal
    entry_signal = None
    if signal == "oversold":
        entry_signal = "potential_mean_reversion_entry"
    elif signal == "approaching_lower" and volatility_state == "contracting":
        entry_signal = "watch_for_breakout"
    elif signal == "overextended":
        entry_signal = "avoid_chasing"
    elif signal == "neutral" and volatility_state == "contracting":
        entry_signal = "consolidation_watch"

    return {
        "price": price,
        "upper_band": upper,
        "middle_band": middle,
        "lower_band": lower,
        "percent_b": pctb,
        "bandwidth": bandwidth,
        "params": {"length": length, "std": std},
        "position": position,
        "signal": signal,
        "volatility_state": volatility_state,
        "entry_signal": entry_signal,
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing Bollinger Bands for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_bollinger(df)
        output_result(result, symbol, "bollinger")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
