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
import pandas_ta as ta
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_common import (
    load_ohlcv, get_symbol_from_args, safe_round, log, format_date,
    find_swing_points, BASE_PATH, NumpyEncoder
)


def compute_all_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators in one pass."""
    df = df.copy()

    # RSI
    df['rsi'] = ta.rsi(df['Close'], length=14)

    # MACD
    macd_result = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    if macd_result is not None:
        df['macd'] = macd_result.iloc[:, 0]
        df['macd_signal'] = macd_result.iloc[:, 2]
        df['macd_hist'] = macd_result.iloc[:, 1]

    # SMAs
    df['sma20'] = ta.sma(df['Close'], length=20)
    df['sma50'] = ta.sma(df['Close'], length=50)
    if len(df) >= 200:
        df['sma200'] = ta.sma(df['Close'], length=200)

    # Bollinger Bands
    bbands = ta.bbands(df['Close'], length=20, std=2)
    if bbands is not None:
        df['bb_lower'] = bbands.iloc[:, 0]
        df['bb_upper'] = bbands.iloc[:, 2]
        df['bb_pctb'] = bbands.iloc[:, 4]

    # ADX
    adx_result = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    if adx_result is not None:
        df['adx'] = adx_result.iloc[:, 0]
        df['plus_di'] = adx_result.iloc[:, 1]
        df['minus_di'] = adx_result.iloc[:, 2]

    # Volume
    df['vol_sma20'] = ta.sma(df['Volume'], length=20)
    df['vol_ratio'] = df['Volume'] / df['vol_sma20']

    # ATR for stop loss
    df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    return df


def analyze_entry_points(df: pd.DataFrame) -> dict:
    """Analyze entry points using all indicators."""

    df = compute_all_indicators(df)
    latest = df.iloc[-1]
    price = safe_round(latest['Close'], 2)

    # Extract indicator values
    rsi = safe_round(latest.get('rsi'), 2)
    macd = safe_round(latest.get('macd'), 4)
    macd_signal = safe_round(latest.get('macd_signal'), 4)
    macd_hist = safe_round(latest.get('macd_hist'), 4)
    sma20 = safe_round(latest.get('sma20'), 2)
    sma50 = safe_round(latest.get('sma50'), 2)
    sma200 = safe_round(latest.get('sma200'), 2) if 'sma200' in df.columns else None
    bb_pctb = safe_round(latest.get('bb_pctb'), 4)
    bb_lower = safe_round(latest.get('bb_lower'), 2)
    bb_upper = safe_round(latest.get('bb_upper'), 2)
    adx = safe_round(latest.get('adx'), 2)
    plus_di = safe_round(latest.get('plus_di'), 2)
    minus_di = safe_round(latest.get('minus_di'), 2)
    vol_ratio = safe_round(latest.get('vol_ratio'), 2)
    atr = safe_round(latest.get('atr'), 2)

    # Fibonacci levels (60-day lookback)
    recent = df.tail(60)
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
        if rsi < 30:
            signals.append({"indicator": "RSI", "signal": "oversold", "value": rsi, "bias": "bullish"})
            bullish_count += 2
        elif rsi < 40:
            signals.append({"indicator": "RSI", "signal": "approaching_oversold", "value": rsi, "bias": "bullish"})
            bullish_count += 1
        elif rsi > 70:
            signals.append({"indicator": "RSI", "signal": "overbought", "value": rsi, "bias": "bearish"})
            bearish_count += 2
        elif rsi > 60:
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
        elif bb_pctb < 0.2:
            signals.append({"indicator": "Bollinger", "signal": "near_lower_band", "value": bb_pctb, "bias": "bullish"})
            bullish_count += 1
        elif bb_pctb > 1:
            signals.append({"indicator": "Bollinger", "signal": "above_upper_band", "value": bb_pctb, "bias": "bearish"})
            bearish_count += 1

    # ADX Signal
    if adx and plus_di and minus_di:
        strong_trend = adx > 25
        bullish_di = plus_di > minus_di

        if strong_trend and bullish_di:
            signals.append({"indicator": "ADX", "signal": "strong_uptrend", "value": adx, "bias": "bullish"})
            bullish_count += 2
        elif strong_trend and not bullish_di:
            signals.append({"indicator": "ADX", "signal": "strong_downtrend", "value": adx, "bias": "bearish"})
            bearish_count += 2
        elif adx < 20:
            signals.append({"indicator": "ADX", "signal": "weak_trend", "value": adx, "bias": "neutral"})

    # Volume Signal
    is_up_day = latest['Close'] >= latest['Open']
    if vol_ratio:
        if vol_ratio > 1.5 and is_up_day:
            signals.append({"indicator": "Volume", "signal": "accumulation", "value": vol_ratio, "bias": "bullish"})
            bullish_count += 1
        elif vol_ratio > 1.5 and not is_up_day:
            signals.append({"indicator": "Volume", "signal": "distribution", "value": vol_ratio, "bias": "bearish"})
            bearish_count += 1

    # Fibonacci proximity
    dist_to_fib618 = abs(price - fib_618) / price * 100 if fib_618 else None
    dist_to_fib50 = abs(price - fib_50) / price * 100 if fib_50 else None

    if dist_to_fib618 and dist_to_fib618 < 2:
        signals.append({"indicator": "Fibonacci", "signal": "at_61.8%_level", "value": fib_618, "bias": "bullish"})
        bullish_count += 1
    elif dist_to_fib50 and dist_to_fib50 < 2:
        signals.append({"indicator": "Fibonacci", "signal": "at_50%_level", "value": fib_50, "bias": "bullish"})
        bullish_count += 1

    # Overall verdict
    total_signals = bullish_count + bearish_count
    if total_signals == 0:
        verdict = "NEUTRAL"
        entry_recommendation = "wait_for_signals"
    elif bullish_count >= bearish_count + 3:
        verdict = "BULLISH"
        entry_recommendation = "favorable_entry"
    elif bearish_count >= bullish_count + 3:
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
