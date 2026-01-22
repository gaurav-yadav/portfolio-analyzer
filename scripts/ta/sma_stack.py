#!/usr/bin/env python3
"""
SMA Stack (Moving Average Stack) Analysis

Usage: uv run python scripts/ta/sma_stack.py <symbol>

Analyzes SMA 20/50/200 alignment for trend direction.
- Price > SMA20 > SMA50 > SMA200 = strong uptrend
- Golden cross / death cross detection
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log, format_date


def analyze_sma_stack(df) -> dict:
    """Analyze SMA stack alignment and crossovers."""
    df = df.copy()

    df['sma20'] = ta.sma(df['Close'], length=20)
    df['sma50'] = ta.sma(df['Close'], length=50)
    if len(df) >= 200:
        df['sma200'] = ta.sma(df['Close'], length=200)

    latest = df.iloc[-1]
    price = safe_round(latest['Close'], 2)
    sma20 = safe_round(latest['sma20'], 2)
    sma50 = safe_round(latest['sma50'], 2)
    sma200 = safe_round(latest.get('sma200'), 2) if 'sma200' in df.columns else None

    # Stack alignment check
    stack_bullish = False
    stack_bearish = False
    stack_type = "mixed"

    if sma20 and sma50:
        if sma200:
            if price > sma20 > sma50 > sma200:
                stack_bullish = True
                stack_type = "perfect_bullish"
            elif price < sma20 < sma50 < sma200:
                stack_bearish = True
                stack_type = "perfect_bearish"
            elif sma50 > sma200 and price > sma50:
                stack_type = "bullish"
            elif sma50 < sma200 and price < sma50:
                stack_type = "bearish"
            elif sma50 > sma200 and price < sma50:
                stack_type = "pullback_in_uptrend"
            elif sma50 < sma200 and price > sma50:
                stack_type = "rally_in_downtrend"
        else:
            if price > sma20 > sma50:
                stack_type = "bullish"
            elif price < sma20 < sma50:
                stack_type = "bearish"

    # Distance from MAs (for pullback identification)
    dist_sma20 = safe_round((price - sma20) / sma20 * 100, 2) if sma20 else None
    dist_sma50 = safe_round((price - sma50) / sma50 * 100, 2) if sma50 else None
    dist_sma200 = safe_round((price - sma200) / sma200 * 100, 2) if sma200 else None

    # Golden/Death cross detection (last 60 days)
    golden_cross = None
    death_cross = None

    if 'sma200' in df.columns:
        recent = df.tail(60)
        for i in range(1, len(recent)):
            curr = recent.iloc[i]
            prev = recent.iloc[i-1]

            if prev['sma50'] <= prev['sma200'] and curr['sma50'] > curr['sma200']:
                golden_cross = format_date(recent.index[i])

            if prev['sma50'] >= prev['sma200'] and curr['sma50'] < curr['sma200']:
                death_cross = format_date(recent.index[i])

    # Entry signal based on stack
    entry_signal = None
    if stack_type == "perfect_bullish":
        entry_signal = "strong_trend_continuation"
    elif stack_type == "pullback_in_uptrend":
        entry_signal = "potential_entry_on_pullback"
    elif stack_type == "bullish" and dist_sma20 and dist_sma20 < 2:
        entry_signal = "near_sma20_support"
    elif stack_type in ["bearish", "perfect_bearish"]:
        entry_signal = "avoid_long_entry"
    elif stack_type == "rally_in_downtrend":
        entry_signal = "caution_bear_rally"

    return {
        "price": price,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "stack_type": stack_type,
        "stack_bullish": stack_bullish,
        "stack_bearish": stack_bearish,
        "distance_from_sma20_pct": dist_sma20,
        "distance_from_sma50_pct": dist_sma50,
        "distance_from_sma200_pct": dist_sma200,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "entry_signal": entry_signal,
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing SMA Stack for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_sma_stack(df)
        output_result(result, symbol, "sma_stack")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
