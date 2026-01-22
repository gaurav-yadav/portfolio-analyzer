#!/usr/bin/env python3
"""
Volume Analysis

Usage: uv run python scripts/ta/volume.py <symbol>

Analyzes volume patterns for accumulation/distribution signals.
- Volume spike + price up = accumulation (bullish)
- Volume spike + price down = distribution (bearish)
- Volume trend analysis
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log, format_date


def analyze_volume(df) -> dict:
    """Analyze volume patterns."""
    df = df.copy()

    df['vol_sma20'] = ta.sma(df['Volume'], length=20)
    df['vol_sma50'] = ta.sma(df['Volume'], length=50)
    df['vol_ratio'] = df['Volume'] / df['vol_sma20']
    df['price_change'] = df['Close'].pct_change()

    latest = df.iloc[-1]

    volume = int(latest['Volume'])
    vol_sma20 = int(latest['vol_sma20']) if latest['vol_sma20'] else None
    vol_sma50 = int(latest['vol_sma50']) if latest['vol_sma50'] else None
    vol_ratio = safe_round(latest['vol_ratio'], 2)

    is_up_day = latest['Close'] >= latest['Open']
    price_change_pct = safe_round(latest['price_change'] * 100, 2)

    # Volume signal
    if vol_ratio and vol_ratio > 2.0:
        if is_up_day:
            signal = "strong_accumulation"
        else:
            signal = "strong_distribution"
    elif vol_ratio and vol_ratio > 1.5:
        if is_up_day:
            signal = "accumulation"
        else:
            signal = "distribution"
    elif vol_ratio and vol_ratio < 0.5:
        signal = "very_low_volume"
    else:
        signal = "normal"

    # Volume trend (5-day vs 20-day)
    vol_5d = df['Volume'].tail(5).mean()
    vol_trend = None
    if vol_5d and vol_sma20:
        if vol_5d > vol_sma20 * 1.2:
            vol_trend = "increasing"
        elif vol_5d < vol_sma20 * 0.8:
            vol_trend = "decreasing"
        else:
            vol_trend = "stable"

    # Find recent volume spikes
    recent_spikes = []
    recent = df.tail(20)
    for idx, row in recent.iterrows():
        if row['vol_ratio'] > 2.0:
            recent_spikes.append({
                "date": format_date(idx),
                "volume_ratio": safe_round(row['vol_ratio'], 2),
                "price_change_pct": safe_round(row['price_change'] * 100, 2) if row['price_change'] else None,
                "type": "accumulation" if row['Close'] >= row['Open'] else "distribution",
            })

    # Entry signal based on volume
    entry_signal = None
    if signal == "strong_accumulation":
        entry_signal = "volume_confirms_buying"
    elif signal == "accumulation":
        entry_signal = "positive_volume"
    elif signal == "strong_distribution":
        entry_signal = "avoid_entry_selling_pressure"
    elif signal == "very_low_volume":
        entry_signal = "wait_for_volume_confirmation"

    return {
        "volume": volume,
        "avg_volume_20d": vol_sma20,
        "avg_volume_50d": vol_sma50,
        "volume_ratio": vol_ratio,
        "is_up_day": is_up_day,
        "price_change_pct": price_change_pct,
        "signal": signal,
        "volume_trend": vol_trend,
        "recent_spikes": recent_spikes[-5:],  # Last 5 spikes
        "entry_signal": entry_signal,
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing Volume Analysis for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_volume(df)
        output_result(result, symbol, "volume")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
