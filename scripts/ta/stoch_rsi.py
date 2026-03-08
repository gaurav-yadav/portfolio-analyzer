#!/usr/bin/env python3
"""
Stochastic RSI Analysis

Usage: uv run python scripts/ta/stoch_rsi.py <symbol>

Computes StochRSI(14,14,3,3):
- K line: fast stochastic applied to RSI values
- D line: 3-period SMA of K (signal line)

Signals:
- K < 20: Oversold zone — watch for bullish crossover
- K > 80: Overbought zone — watch for bearish crossover
- K crosses above D while in oversold: Strong buy signal
- K crosses below D while in overbought: Strong sell signal
"""

import sys
from pathlib import Path

import pandas_ta as ta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log


def analyze_stoch_rsi(df, rsi_length: int = 14, stoch_length: int = 14, k: int = 3, d: int = 3) -> dict:
    """Compute Stochastic RSI and generate signals."""
    df = df.copy()

    stochrsi = ta.stochrsi(df['Close'], length=rsi_length, rsi_length=rsi_length, k=k, d=d)

    if stochrsi is None or stochrsi.empty:
        return {"error": "insufficient_data", "signal": "no_data"}

    k_col = stochrsi.columns[0]  # STOCHRSIk
    d_col = stochrsi.columns[1]  # STOCHRSId

    k_val = safe_round(stochrsi[k_col].iloc[-1], 2)
    d_val = safe_round(stochrsi[d_col].iloc[-1], 2)

    # Previous values for crossover detection
    k_prev = safe_round(stochrsi[k_col].iloc[-2], 2) if len(stochrsi) >= 2 else None
    d_prev = safe_round(stochrsi[d_col].iloc[-2], 2) if len(stochrsi) >= 2 else None

    # Zone classification
    if k_val is None:
        zone = "unknown"
    elif k_val < 20:
        zone = "oversold"
    elif k_val > 80:
        zone = "overbought"
    else:
        zone = "neutral"

    # Crossover detection
    crossover = None
    if k_val is not None and d_val is not None and k_prev is not None and d_prev is not None:
        k_crossed_above_d = k_prev < d_prev and k_val > d_val
        k_crossed_below_d = k_prev > d_prev and k_val < d_val

        if k_crossed_above_d and zone == "oversold":
            crossover = "bullish_from_oversold"   # strongest buy signal
        elif k_crossed_above_d:
            crossover = "bullish"
        elif k_crossed_below_d and zone == "overbought":
            crossover = "bearish_from_overbought"  # strongest sell signal
        elif k_crossed_below_d:
            crossover = "bearish"
        elif k_val > d_val:
            crossover = "k_above_d"  # bullish alignment
        else:
            crossover = "k_below_d"  # bearish alignment

    # Momentum direction
    momentum = None
    if k_val is not None and k_prev is not None:
        if k_val > k_prev:
            momentum = "rising"
        elif k_val < k_prev:
            momentum = "falling"
        else:
            momentum = "flat"

    # Overall signal
    if crossover in ("bullish_from_oversold",):
        signal = "strong_buy"
        signal_strength = 9
    elif crossover in ("bullish",) and zone != "overbought":
        signal = "buy"
        signal_strength = 6
    elif zone == "oversold" and momentum == "rising":
        signal = "potential_reversal"
        signal_strength = 5
    elif crossover in ("bearish_from_overbought",):
        signal = "strong_sell"
        signal_strength = 9
    elif crossover in ("bearish",) and zone != "oversold":
        signal = "sell"
        signal_strength = 6
    elif zone == "overbought" and momentum == "falling":
        signal = "potential_top"
        signal_strength = 5
    elif zone == "oversold":
        signal = "oversold_watch"
        signal_strength = 3
    elif zone == "overbought":
        signal = "overbought_watch"
        signal_strength = 3
    else:
        signal = "neutral"
        signal_strength = 0

    return {
        "stoch_rsi_k": k_val,
        "stoch_rsi_d": d_val,
        "stoch_rsi_k_prev": k_prev,
        "stoch_rsi_d_prev": d_prev,
        "zone": zone,
        "crossover": crossover,
        "momentum": momentum,
        "signal": signal,
        "signal_strength": signal_strength,
        "params": {"rsi_length": rsi_length, "stoch_length": stoch_length, "k": k, "d": d},
        "thresholds": {"oversold": 20, "overbought": 80},
        "interpretation": {
            "strong_buy": "K crossed above D from oversold zone — highest conviction entry signal",
            "buy": "K crossed above D — bullish momentum building",
            "potential_reversal": "In oversold with K rising — watch for crossover confirmation",
            "strong_sell": "K crossed below D from overbought zone — exit/short signal",
            "sell": "K crossed below D — bearish momentum",
            "potential_top": "In overbought with K falling — watch for crossover confirmation",
            "oversold_watch": "Deeply oversold — no crossover yet but approaching buy territory",
            "overbought_watch": "Deeply overbought — no crossover yet but watch for reversal",
            "neutral": "Mid-range, no clear signal",
        }.get(signal, ""),
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing Stochastic RSI for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_stoch_rsi(df)
        output_result(result, symbol, "stoch_rsi")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
