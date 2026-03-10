#!/usr/bin/env python3
"""
Entry Points Analysis - Combines all TA signals for entry recommendations.

Usage: uv run python scripts/ta/entry_points.py <symbol>

Aggregates signals from:
- RSI (overbought/oversold)
- MACD (momentum confirmation)
- Fibonacci (key entry zones)
- SMA Stack (trend direction)
- Bollinger Bands (mean reversion)
- ADX (trend strength)
- Volume (confirmation)

Outputs specific entry price targets and risk/reward.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.indicators import compute_all, extract_latest
from utils.ta_config import (
    RSI_OVERSOLD, RSI_APPROACHING_OVERSOLD, RSI_OVERBOUGHT, RSI_ELEVATED,
    ADX_WEAK, ADX_STRONG,
    BB_LOWER_THRESHOLD,
    VOLUME_HIGH,
    FIB_LOOKBACK, FIB_PROXIMITY_PCT,
    SIGNAL_BULLISH_THRESHOLD,
)
from utils.ta_common import (
    load_ohlcv, get_symbol_from_args, safe_round, log, format_date,
    find_swing_points, BASE_PATH, NumpyEncoder
)


def analyze_entry_points(df: pd.DataFrame) -> dict:
    """Analyze entry points using all indicators."""

    ind = compute_all(df)
    df = ind['df']
    vals = extract_latest(df)
    price = vals['price']

    # Extract indicator values from extract_latest
    rsi = vals['rsi']
    macd = vals['macd']
    macd_signal = vals['macd_signal']
    macd_hist = vals['macd_hist']
    sma20 = vals['sma20']
    sma50 = vals['sma50']
    sma200 = vals['sma200']
    bb_pctb = vals['bb_pctb']
    bb_lower = vals['bb_lower']
    bb_upper = vals['bb_upper']
    adx = vals['adx']
    plus_di = vals['plus_di']
    minus_di = vals['minus_di']
    vol_ratio = vals['vol_ratio']
    atr = vals['atr']

    # Fibonacci levels
    recent = df.tail(FIB_LOOKBACK)
    swing_high = recent['High'].max()
    swing_low = recent['Low'].min()
    fib_diff = swing_high - swing_low

    fib_618 = safe_round(swing_high - fib_diff * 0.618, 2)
    fib_50 = safe_round(swing_high - fib_diff * 0.5, 2)
    fib_382 = safe_round(swing_high - fib_diff * 0.382, 2)

    # Build signals
    signals = []
    bullish_count = 0
    bearish_count = 0

    # RSI Signal
    if rsi:
        if rsi < RSI_OVERSOLD:
            signals.append({"indicator": "RSI", "signal": "oversold", "value": rsi, "bias": "bullish"})
            bullish_count += 2
        elif rsi < RSI_APPROACHING_OVERSOLD:
            signals.append({"indicator": "RSI", "signal": "approaching_oversold", "value": rsi, "bias": "bullish"})
            bullish_count += 1
        elif rsi > RSI_OVERBOUGHT:
            signals.append({"indicator": "RSI", "signal": "overbought", "value": rsi, "bias": "bearish"})
            bearish_count += 2
        elif rsi > RSI_ELEVATED:
            signals.append({"indicator": "RSI", "signal": "elevated", "value": rsi, "bias": "neutral"})

    # MACD Signal
    if macd is not None and macd_signal is not None:
        macd_bullish = macd > macd_signal
        macd_above_zero = macd > 0
        hist_positive = macd_hist and macd_hist > 0

        if macd_bullish and macd_above_zero and hist_positive:
            signals.append({"indicator": "MACD", "signal": "strong_bullish", "value": macd, "bias": "bullish"})
            bullish_count += 2
        elif macd_bullish:
            signals.append({"indicator": "MACD", "signal": "bullish_crossover", "value": macd, "bias": "bullish"})
            bullish_count += 1
        elif not macd_bullish and not macd_above_zero:
            signals.append({"indicator": "MACD", "signal": "bearish", "value": macd, "bias": "bearish"})
            bearish_count += 2

    # SMA Stack Signal
    if sma20 and sma50:
        if sma200:
            if price > sma20 > sma50 > sma200:
                signals.append({"indicator": "SMA_Stack", "signal": "perfect_bullish", "bias": "bullish"})
                bullish_count += 3
            elif price < sma20 < sma50 < sma200:
                signals.append({"indicator": "SMA_Stack", "signal": "perfect_bearish", "bias": "bearish"})
                bearish_count += 3
            elif sma50 > sma200 and price < sma50:
                signals.append({"indicator": "SMA_Stack", "signal": "pullback_in_uptrend", "bias": "bullish"})
                bullish_count += 1

    # Bollinger Signal
    if bb_pctb is not None:
        if bb_pctb < 0:
            signals.append({"indicator": "Bollinger", "signal": "below_lower_band", "value": bb_pctb, "bias": "bullish"})
            bullish_count += 1
        elif bb_pctb < BB_LOWER_THRESHOLD:
            signals.append({"indicator": "Bollinger", "signal": "near_lower_band", "value": bb_pctb, "bias": "bullish"})
            bullish_count += 1
        elif bb_pctb > 1:
            signals.append({"indicator": "Bollinger", "signal": "above_upper_band", "value": bb_pctb, "bias": "bearish"})
            bearish_count += 1

    # ADX Signal
    if adx and plus_di and minus_di:
        strong_trend = adx > ADX_STRONG
        bullish_di = plus_di > minus_di

        if strong_trend and bullish_di:
            signals.append({"indicator": "ADX", "signal": "strong_uptrend", "value": adx, "bias": "bullish"})
            bullish_count += 2
        elif strong_trend and not bullish_di:
            signals.append({"indicator": "ADX", "signal": "strong_downtrend", "value": adx, "bias": "bearish"})
            bearish_count += 2
        elif adx < ADX_WEAK:
            signals.append({"indicator": "ADX", "signal": "weak_trend", "value": adx, "bias": "neutral"})

    # Volume Signal
    is_up_day = vals['is_up_day']
    if vol_ratio:
        if vol_ratio > VOLUME_HIGH and is_up_day:
            signals.append({"indicator": "Volume", "signal": "accumulation", "value": vol_ratio, "bias": "bullish"})
            bullish_count += 1
        elif vol_ratio > VOLUME_HIGH and not is_up_day:
            signals.append({"indicator": "Volume", "signal": "distribution", "value": vol_ratio, "bias": "bearish"})
            bearish_count += 1

    # Fibonacci proximity
    dist_to_fib618 = abs(price - fib_618) / price * 100 if fib_618 else None
    dist_to_fib50 = abs(price - fib_50) / price * 100 if fib_50 else None

    if dist_to_fib618 and dist_to_fib618 < FIB_PROXIMITY_PCT:
        signals.append({"indicator": "Fibonacci", "signal": "at_61.8%_level", "value": fib_618, "bias": "bullish"})
        bullish_count += 1
    elif dist_to_fib50 and dist_to_fib50 < FIB_PROXIMITY_PCT:
        signals.append({"indicator": "Fibonacci", "signal": "at_50%_level", "value": fib_50, "bias": "bullish"})
        bullish_count += 1

    # Overall verdict
    total_signals = bullish_count + bearish_count
    if total_signals == 0:
        verdict = "NEUTRAL"
        entry_recommendation = "wait_for_signals"
    elif bullish_count >= bearish_count + SIGNAL_BULLISH_THRESHOLD:
        verdict = "BULLISH"
        entry_recommendation = "favorable_entry"
    elif bearish_count >= bullish_count + SIGNAL_BULLISH_THRESHOLD:
        verdict = "BEARISH"
        entry_recommendation = "avoid_entry"
    elif bullish_count > bearish_count:
        verdict = "SLIGHTLY_BULLISH"
        entry_recommendation = "consider_small_position"
    elif bearish_count > bullish_count:
        verdict = "SLIGHTLY_BEARISH"
        entry_recommendation = "wait_for_improvement"
    else:
        verdict = "MIXED"
        entry_recommendation = "wait_for_clarity"

    # Calculate entry levels
    entry_levels = {}

    # Conservative: at Fib 61.8% or near support
    if fib_618 and fib_618 < price:
        entry_levels["conservative"] = {
            "price": fib_618,
            "type": "fib_61.8%",
            "distance_pct": safe_round((price - fib_618) / price * 100, 2),
        }

    # Moderate: at Fib 50% or SMA50
    if fib_50 and fib_50 < price:
        entry_levels["moderate"] = {
            "price": fib_50,
            "type": "fib_50%",
            "distance_pct": safe_round((price - fib_50) / price * 100, 2),
        }
    elif sma50 and sma50 < price:
        entry_levels["moderate"] = {
            "price": sma50,
            "type": "sma50",
            "distance_pct": safe_round((price - sma50) / price * 100, 2),
        }

    # Aggressive: current level if signals are bullish
    if verdict in ["BULLISH", "SLIGHTLY_BULLISH"]:
        entry_levels["aggressive"] = {
            "price": price,
            "type": "current",
            "distance_pct": 0,
        }

    # Stop loss levels
    stop_losses = {}
    if atr:
        stop_losses["atr_2x"] = {
            "price": safe_round(price - 2 * atr, 2),
            "risk_pct": safe_round(2 * atr / price * 100, 2),
        }

    if fib_618 and fib_618 < price:
        stop_losses["below_fib_618"] = {
            "price": safe_round(fib_618 * 0.97, 2),
            "risk_pct": safe_round((price - fib_618 * 0.97) / price * 100, 2),
        }

    # Target levels
    targets = {}
    if fib_382 and fib_382 > price:
        targets["T1"] = {
            "price": fib_382,
            "type": "fib_38.2%",
            "gain_pct": safe_round((fib_382 - price) / price * 100, 2),
        }

    targets["T2"] = {
        "price": safe_round(swing_high, 2),
        "type": "swing_high",
        "gain_pct": safe_round((swing_high - price) / price * 100, 2),
    }

    # Risk/Reward calculation
    risk_reward = {}
    if stop_losses.get("atr_2x") and targets:
        risk = price - stop_losses["atr_2x"]["price"]
        for target_name, target_info in targets.items():
            reward = target_info["price"] - price
            if risk > 0:
                risk_reward[target_name] = {
                    "ratio": safe_round(reward / risk, 2),
                    "favorable": reward / risk >= 2.0,
                }

    return {
        "current_price": price,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "indicators": {
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "bb_pctb": bb_pctb,
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "vol_ratio": vol_ratio,
            "atr": atr,
        },
        "fibonacci_levels": {
            "swing_high": safe_round(swing_high, 2),
            "swing_low": safe_round(swing_low, 2),
            "fib_38.2%": fib_382,
            "fib_50%": fib_50,
            "fib_61.8%": fib_618,
        },
        "signals": signals,
        "signal_counts": {
            "bullish": bullish_count,
            "bearish": bearish_count,
        },
        "verdict": verdict,
        "entry_recommendation": entry_recommendation,
        "entry_levels": entry_levels,
        "stop_losses": stop_losses,
        "targets": targets,
        "risk_reward": risk_reward,
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Computing Entry Points Analysis for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_entry_points(df)

        # Add symbol and save
        result["symbol"] = symbol
        result["indicator"] = "entry_points"

        # Save to file
        output_dir = BASE_PATH / "data" / "ta"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{symbol}_entry_points.json"

        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, cls=NumpyEncoder)

        log(f"Saved to {output_path}")

        # Print to stdout
        print(json.dumps(result, indent=2, cls=NumpyEncoder))

    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
