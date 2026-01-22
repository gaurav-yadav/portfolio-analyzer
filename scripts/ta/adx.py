#!/usr/bin/env python3
"""
ADX (Average Directional Index) Analysis

Usage: uv run python scripts/ta/adx.py <symbol>

Computes ADX(14) for trend strength.
- ADX > 25: Strong trend
- ADX < 20: Weak/no trend (ranging)
- +DI > -DI: Bullish direction
- -DI > +DI: Bearish direction
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log


def analyze_adx(df, length: int = 14) -> dict:
    """Compute ADX and directional indicators."""
    df = df.copy()

    adx_result = ta.adx(df['High'], df['Low'], df['Close'], length=length)
    if adx_result is None:
        return {"error": "Could not compute ADX"}

    df['adx'] = adx_result.iloc[:, 0]
    df['plus_di'] = adx_result.iloc[:, 1]
    df['minus_di'] = adx_result.iloc[:, 2]

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    adx = safe_round(latest['adx'], 2)
    plus_di = safe_round(latest['plus_di'], 2)
    minus_di = safe_round(latest['minus_di'], 2)

    prev_adx = safe_round(prev['adx'], 2)

    # Trend strength
    if adx is None:
        trend_strength = "unknown"
    elif adx > 40:
        trend_strength = "very_strong"
    elif adx > 25:
        trend_strength = "strong"
    elif adx > 20:
        trend_strength = "developing"
    else:
        trend_strength = "weak_or_ranging"

    # Direction
    if plus_di and minus_di:
        if plus_di > minus_di:
            direction = "bullish"
            di_spread = safe_round(plus_di - minus_di, 2)
        else:
            direction = "bearish"
            di_spread = safe_round(minus_di - plus_di, 2)
    else:
        direction = "unknown"
        di_spread = None

    # ADX trend (rising = strengthening trend)
    adx_rising = adx > prev_adx if adx and prev_adx else None

    # Combined signal
    if trend_strength in ["strong", "very_strong"] and direction == "bullish":
        signal = "strong_uptrend"
    elif trend_strength in ["strong", "very_strong"] and direction == "bearish":
        signal = "strong_downtrend"
    elif trend_strength == "weak_or_ranging":
        signal = "no_clear_trend"
    elif trend_strength == "developing" and direction == "bullish" and adx_rising:
        signal = "uptrend_developing"
    else:
        signal = "mixed"

    # Entry signal
    entry_signal = None
    if signal == "strong_uptrend":
        entry_signal = "trend_confirmed"
    elif signal == "uptrend_developing":
        entry_signal = "early_trend_entry"
    elif signal == "no_clear_trend":
        entry_signal = "wait_for_trend"
    elif signal == "strong_downtrend":
        entry_signal = "avoid_long_entry"

    return {
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "di_spread": di_spread,
        "period": length,
        "trend_strength": trend_strength,
        "direction": direction,
        "adx_rising": adx_rising,
        "signal": signal,
        "entry_signal": entry_signal,
        "thresholds": {"strong": 25, "very_strong": 40, "weak": 20},
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing ADX for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_adx(df)
        output_result(result, symbol, "adx")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
