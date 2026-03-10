#!/usr/bin/env python3
"""
Chart Pattern Detection

Usage: uv run python scripts/ta/patterns.py <symbol>

Detects the following patterns over the last 120 bars:

CONTINUATION PATTERNS:
- Bull Flag: Strong up move (pole) → tight consolidation → breakout
- Bear Flag: Strong down move (pole) → tight consolidation → breakdown

REVERSAL PATTERNS (Bottoms — Bullish):
- Double Bottom (W pattern): Two lows at similar price → neckline breakout
- Inverse Head & Shoulders: Left shoulder → head (lower) → right shoulder → breakout

REVERSAL PATTERNS (Tops — Bearish):
- Double Top (M pattern): Two highs at similar price → neckline breakdown
- Head & Shoulders: Left shoulder → head (higher) → right shoulder → breakdown

Methodology:
- Uses swing point detection with configurable window
- Validates geometric relationships (symmetry, neckline, proportionality)
- Provides target price based on pattern height
- Confidence score based on pattern quality
"""

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.ta_config import BULL_FLAG_POLE_MIN, BULL_FLAG_CONSOL_MAX, PATTERN_LOOKBACK
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log


def find_swing_highs(series: pd.Series, window: int = 5) -> list[tuple[int, float]]:
    vals = series.values
    highs = []
    for i in range(window, len(vals) - window):
        segment = vals[i - window:i + window + 1]
        if vals[i] == max(segment):
            highs.append((i, float(vals[i])))
    return highs


def find_swing_lows(series: pd.Series, window: int = 5) -> list[tuple[int, float]]:
    vals = series.values
    lows = []
    for i in range(window, len(vals) - window):
        segment = vals[i - window:i + window + 1]
        if vals[i] == min(segment):
            lows.append((i, float(vals[i])))
    return lows


def check_bull_flag(df: pd.DataFrame, lookback: int = 60) -> Optional[dict]:
    """
    Bull flag: sharp upward pole (>BULL_FLAG_POLE_MIN in ≤10 bars), followed by
    tight channel consolidation (price stays within BULL_FLAG_CONSOL_MAX range for ≥5 bars).
    """
    recent = df.tail(lookback).reset_index(drop=True)
    closes = recent['Close'].values
    n = len(closes)

    # Find pole: look for a strong up move ending within the last 40 bars
    for pole_start in range(0, n - 15):
        for pole_end in range(pole_start + 3, min(pole_start + 12, n - 5)):
            pole_gain = (closes[pole_end] - closes[pole_start]) / closes[pole_start]

            if pole_gain >= BULL_FLAG_POLE_MIN:
                # Check consolidation after pole
                consol_bars = closes[pole_end:]
                if len(consol_bars) < 5:
                    continue

                consol_high = max(consol_bars)
                consol_low = min(consol_bars)
                consol_range = (consol_high - consol_low) / consol_high

                if consol_range <= BULL_FLAG_CONSOL_MAX:
                    # Current price near top of consolidation = potential breakout
                    current = closes[-1]
                    at_breakout = current >= consol_high * 0.98

                    target = consol_high + (closes[pole_end] - closes[pole_start])  # Pole height added to breakout
                    pattern_age = n - pole_end

                    return {
                        "detected": True,
                        "pattern": "bull_flag",
                        "bias": "bullish",
                        "pole_start_price": safe_round(closes[pole_start], 2),
                        "pole_end_price": safe_round(closes[pole_end], 2),
                        "pole_gain_pct": safe_round(pole_gain * 100, 2),
                        "consolidation_high": safe_round(consol_high, 2),
                        "consolidation_low": safe_round(consol_low, 2),
                        "consolidation_range_pct": safe_round(consol_range * 100, 2),
                        "breakout_level": safe_round(consol_high, 2),
                        "target_price": safe_round(target, 2),
                        "at_breakout": at_breakout,
                        "pattern_age_bars": pattern_age,
                        "confidence_pct": min(85, 55 + int(pole_gain * 200) - int(consol_range * 100)),
                        "description": f"Bull flag: +{pole_gain*100:.1f}% pole, {consol_range*100:.1f}% consolidation range",
                        "trade_implication": f"Buy breakout above ${consol_high:.2f}. Target: ${target:.2f}",
                    }

    return None


def check_bear_flag(df: pd.DataFrame, lookback: int = 60) -> Optional[dict]:
    """
    Bear flag: sharp downward pole (>8% in ≤10 bars), followed by
    tight channel consolidation.
    """
    recent = df.tail(lookback).reset_index(drop=True)
    closes = recent['Close'].values
    n = len(closes)

    for pole_start in range(0, n - 15):
        for pole_end in range(pole_start + 3, min(pole_start + 12, n - 5)):
            pole_drop = (closes[pole_start] - closes[pole_end]) / closes[pole_start]

            if pole_drop >= BULL_FLAG_POLE_MIN:
                consol_bars = closes[pole_end:]
                if len(consol_bars) < 5:
                    continue

                consol_high = max(consol_bars)
                consol_low = min(consol_bars)
                consol_range = (consol_high - consol_low) / consol_high

                if consol_range <= BULL_FLAG_CONSOL_MAX:
                    current = closes[-1]
                    at_breakdown = current <= consol_low * 1.02

                    target = consol_low - (closes[pole_start] - closes[pole_end])  # Pole height subtracted
                    pattern_age = n - pole_end

                    return {
                        "detected": True,
                        "pattern": "bear_flag",
                        "bias": "bearish",
                        "pole_start_price": safe_round(closes[pole_start], 2),
                        "pole_end_price": safe_round(closes[pole_end], 2),
                        "pole_drop_pct": safe_round(pole_drop * 100, 2),
                        "consolidation_high": safe_round(consol_high, 2),
                        "consolidation_low": safe_round(consol_low, 2),
                        "consolidation_range_pct": safe_round(consol_range * 100, 2),
                        "breakdown_level": safe_round(consol_low, 2),
                        "target_price": safe_round(target, 2),
                        "at_breakdown": at_breakdown,
                        "pattern_age_bars": pattern_age,
                        "confidence_pct": min(85, 55 + int(pole_drop * 200) - int(consol_range * 100)),
                        "description": f"Bear flag: -{pole_drop*100:.1f}% pole, {consol_range*100:.1f}% consolidation range",
                        "trade_implication": f"Short/avoid below ${consol_low:.2f}. Target: ${target:.2f}",
                    }

    return None


def check_double_bottom(df: pd.DataFrame, lookback: int = 80, tolerance: float = 0.04) -> Optional[dict]:
    """
    Double bottom (W): Two swing lows within tolerance% of each other,
    separated by a swing high (neckline). Bullish on neckline breakout.
    """
    recent = df.tail(lookback).reset_index(drop=True)
    lows = find_swing_lows(recent['Close'], window=5)
    highs = find_swing_highs(recent['Close'], window=5)

    if len(lows) < 2:
        return None

    # Check last few pairs of lows
    for i in range(len(lows) - 1, 0, -1):
        l2_idx, l2_val = lows[i]
        l1_idx, l1_val = lows[i - 1]

        # Must be at least 10 bars apart
        if l2_idx - l1_idx < 10:
            continue

        # Both lows must be within tolerance of each other
        low_diff = abs(l2_val - l1_val) / l1_val
        if low_diff > tolerance:
            continue

        # Find neckline: highest high between the two lows
        between_highs = [h for h in highs if l1_idx < h[0] < l2_idx]
        if not between_highs:
            continue

        neckline_idx, neckline_val = max(between_highs, key=lambda x: x[1])

        # Pattern height (for target)
        pattern_height = neckline_val - min(l1_val, l2_val)
        target = neckline_val + pattern_height

        # Is current price near neckline? (potential breakout)
        current = recent['Close'].iloc[-1]
        at_breakout = current >= neckline_val * 0.98
        already_broke = current > neckline_val * 1.02

        # Symmetry bonus
        left_leg = neckline_idx - l1_idx
        right_leg = l2_idx - neckline_idx
        symmetry = min(left_leg, right_leg) / max(left_leg, right_leg) if max(left_leg, right_leg) > 0 else 0
        confidence = min(88, 55 + int(symmetry * 20) - int(low_diff * 200))

        return {
            "detected": True,
            "pattern": "double_bottom",
            "bias": "bullish",
            "bottom1_price": safe_round(l1_val, 2),
            "bottom2_price": safe_round(l2_val, 2),
            "bottom_diff_pct": safe_round(low_diff * 100, 2),
            "neckline": safe_round(neckline_val, 2),
            "pattern_height": safe_round(pattern_height, 2),
            "target_price": safe_round(target, 2),
            "at_breakout": at_breakout,
            "already_broke_out": already_broke,
            "symmetry_score": safe_round(symmetry, 2),
            "confidence_pct": confidence,
            "description": f"Double bottom at ${l1_val:.2f}/${l2_val:.2f}, neckline ${neckline_val:.2f}",
            "trade_implication": f"Buy breakout above neckline ${neckline_val:.2f}. Target: ${target:.2f}",
        }

    return None


def check_double_top(df: pd.DataFrame, lookback: int = 80, tolerance: float = 0.04) -> Optional[dict]:
    """
    Double top (M): Two swing highs within tolerance% of each other,
    separated by a swing low (neckline). Bearish on neckline breakdown.
    """
    recent = df.tail(lookback).reset_index(drop=True)
    highs = find_swing_highs(recent['Close'], window=5)
    lows = find_swing_lows(recent['Close'], window=5)

    if len(highs) < 2:
        return None

    for i in range(len(highs) - 1, 0, -1):
        h2_idx, h2_val = highs[i]
        h1_idx, h1_val = highs[i - 1]

        if h2_idx - h1_idx < 10:
            continue

        high_diff = abs(h2_val - h1_val) / h1_val
        if high_diff > tolerance:
            continue

        # Neckline: lowest low between the two highs
        between_lows = [l for l in lows if h1_idx < l[0] < h2_idx]
        if not between_lows:
            continue

        neckline_idx, neckline_val = min(between_lows, key=lambda x: x[1])

        pattern_height = max(h1_val, h2_val) - neckline_val
        target = neckline_val - pattern_height

        current = recent['Close'].iloc[-1]
        at_breakdown = current <= neckline_val * 1.02
        already_broke = current < neckline_val * 0.98

        left_leg = neckline_idx - h1_idx
        right_leg = h2_idx - neckline_idx
        symmetry = min(left_leg, right_leg) / max(left_leg, right_leg) if max(left_leg, right_leg) > 0 else 0
        confidence = min(88, 55 + int(symmetry * 20) - int(high_diff * 200))

        return {
            "detected": True,
            "pattern": "double_top",
            "bias": "bearish",
            "top1_price": safe_round(h1_val, 2),
            "top2_price": safe_round(h2_val, 2),
            "top_diff_pct": safe_round(high_diff * 100, 2),
            "neckline": safe_round(neckline_val, 2),
            "pattern_height": safe_round(pattern_height, 2),
            "target_price": safe_round(target, 2),
            "at_breakdown": at_breakdown,
            "already_broke_down": already_broke,
            "symmetry_score": safe_round(symmetry, 2),
            "confidence_pct": confidence,
            "description": f"Double top at ${h1_val:.2f}/${h2_val:.2f}, neckline ${neckline_val:.2f}",
            "trade_implication": f"Short/avoid below neckline ${neckline_val:.2f}. Target: ${target:.2f}",
        }

    return None


def check_head_and_shoulders(df: pd.DataFrame, lookback: int = 100, tolerance: float = 0.05) -> Optional[dict]:
    """
    Head & Shoulders (bearish reversal):
    Left shoulder → Head (higher) → Right shoulder (similar to left) → neckline breakdown
    """
    recent = df.tail(lookback).reset_index(drop=True)
    highs = find_swing_highs(recent['Close'], window=4)
    lows = find_swing_lows(recent['Close'], window=4)

    if len(highs) < 3:
        return None

    # Try triplets of highs
    for i in range(len(highs) - 2):
        ls_idx, ls_val = highs[i]      # Left shoulder
        hd_idx, hd_val = highs[i + 1]  # Head
        rs_idx, rs_val = highs[i + 2]  # Right shoulder

        # Head must be higher than both shoulders
        if hd_val <= ls_val or hd_val <= rs_val:
            continue

        # Shoulders must be roughly symmetrical (within tolerance)
        shoulder_diff = abs(rs_val - ls_val) / ls_val
        if shoulder_diff > tolerance:
            continue

        # Must be reasonably spaced
        if hd_idx - ls_idx < 5 or rs_idx - hd_idx < 5:
            continue

        # Find neckline: lows between LS-HD and HD-RS
        left_trough = [l for l in lows if ls_idx < l[0] < hd_idx]
        right_trough = [l for l in lows if hd_idx < l[0] < rs_idx]

        if not left_trough or not right_trough:
            continue

        lt_val = min(left_trough, key=lambda x: x[1])[1]
        rt_val = min(right_trough, key=lambda x: x[1])[1]
        neckline = (lt_val + rt_val) / 2

        pattern_height = hd_val - neckline
        target = neckline - pattern_height

        current = recent['Close'].iloc[-1]
        at_breakdown = current <= neckline * 1.02
        already_broke = current < neckline * 0.97

        # Confidence based on symmetry and proportions
        symmetry = 1 - shoulder_diff / tolerance
        time_symmetry = min(hd_idx - ls_idx, rs_idx - hd_idx) / max(hd_idx - ls_idx, rs_idx - hd_idx)
        confidence = min(88, 50 + int(symmetry * 20) + int(time_symmetry * 15))

        return {
            "detected": True,
            "pattern": "head_and_shoulders",
            "bias": "bearish",
            "left_shoulder": safe_round(ls_val, 2),
            "head": safe_round(hd_val, 2),
            "right_shoulder": safe_round(rs_val, 2),
            "shoulder_diff_pct": safe_round(shoulder_diff * 100, 2),
            "neckline": safe_round(neckline, 2),
            "pattern_height": safe_round(pattern_height, 2),
            "target_price": safe_round(target, 2),
            "at_breakdown": at_breakdown,
            "already_broke_down": already_broke,
            "time_symmetry_score": safe_round(time_symmetry, 2),
            "confidence_pct": confidence,
            "description": f"H&S: LS={ls_val:.2f}, Head={hd_val:.2f}, RS={rs_val:.2f}, Neckline={neckline:.2f}",
            "trade_implication": f"Bearish. Breakdown below ${neckline:.2f} targets ${target:.2f}",
        }

    return None


def check_inverse_head_and_shoulders(df: pd.DataFrame, lookback: int = 100, tolerance: float = 0.05) -> Optional[dict]:
    """
    Inverse Head & Shoulders (bullish reversal):
    Left shoulder → Head (lower) → Right shoulder (similar to left) → neckline breakout
    """
    recent = df.tail(lookback).reset_index(drop=True)
    lows = find_swing_lows(recent['Close'], window=4)
    highs = find_swing_highs(recent['Close'], window=4)

    if len(lows) < 3:
        return None

    for i in range(len(lows) - 2):
        ls_idx, ls_val = lows[i]
        hd_idx, hd_val = lows[i + 1]
        rs_idx, rs_val = lows[i + 2]

        # Head must be LOWER than both shoulders
        if hd_val >= ls_val or hd_val >= rs_val:
            continue

        shoulder_diff = abs(rs_val - ls_val) / ls_val
        if shoulder_diff > tolerance:
            continue

        if hd_idx - ls_idx < 5 or rs_idx - hd_idx < 5:
            continue

        # Neckline: highs between LS-HD and HD-RS
        left_peak = [h for h in highs if ls_idx < h[0] < hd_idx]
        right_peak = [h for h in highs if hd_idx < h[0] < rs_idx]

        if not left_peak or not right_peak:
            continue

        lp_val = max(left_peak, key=lambda x: x[1])[1]
        rp_val = max(right_peak, key=lambda x: x[1])[1]
        neckline = (lp_val + rp_val) / 2

        pattern_height = neckline - hd_val
        target = neckline + pattern_height

        current = recent['Close'].iloc[-1]
        at_breakout = current >= neckline * 0.98
        already_broke = current > neckline * 1.02

        symmetry = 1 - shoulder_diff / tolerance
        time_symmetry = min(hd_idx - ls_idx, rs_idx - hd_idx) / max(hd_idx - ls_idx, rs_idx - hd_idx)
        confidence = min(88, 50 + int(symmetry * 20) + int(time_symmetry * 15))

        return {
            "detected": True,
            "pattern": "inverse_head_and_shoulders",
            "bias": "bullish",
            "left_shoulder": safe_round(ls_val, 2),
            "head": safe_round(hd_val, 2),
            "right_shoulder": safe_round(rs_val, 2),
            "shoulder_diff_pct": safe_round(shoulder_diff * 100, 2),
            "neckline": safe_round(neckline, 2),
            "pattern_height": safe_round(pattern_height, 2),
            "target_price": safe_round(target, 2),
            "at_breakout": at_breakout,
            "already_broke_out": already_broke,
            "time_symmetry_score": safe_round(time_symmetry, 2),
            "confidence_pct": confidence,
            "description": f"Inv H&S: LS={ls_val:.2f}, Head={hd_val:.2f}, RS={rs_val:.2f}, Neckline={neckline:.2f}",
            "trade_implication": f"Bullish. Breakout above ${neckline:.2f} targets ${target:.2f}",
        }

    return None


def analyze_patterns(df) -> dict:
    """Run all pattern detections and return a consolidated report."""
    current_price = safe_round(df['Close'].iloc[-1], 2)

    results = {
        "current_price": current_price,
        "patterns_detected": [],
        "bullish_patterns": [],
        "bearish_patterns": [],
        "strongest_signal": None,
        "overall_bias": "neutral",
    }

    checkers = [
        ("Bull Flag", check_bull_flag),
        ("Bear Flag", check_bear_flag),
        ("Double Bottom", check_double_bottom),
        ("Double Top", check_double_top),
        ("Head & Shoulders", check_head_and_shoulders),
        ("Inverse H&S", check_inverse_head_and_shoulders),
    ]

    all_found = []
    for name, fn in checkers:
        try:
            result = fn(df)
            if result and result.get("detected"):
                result["name"] = name
                all_found.append(result)
                results["patterns_detected"].append(name)
                if result["bias"] == "bullish":
                    results["bullish_patterns"].append(result)
                else:
                    results["bearish_patterns"].append(result)
        except Exception as e:
            log(f"Warning: {name} check failed: {e}")

    # Determine strongest signal (highest confidence)
    if all_found:
        best = max(all_found, key=lambda x: x.get("confidence_pct", 0))
        results["strongest_signal"] = best

    if len(results["bullish_patterns"]) > len(results["bearish_patterns"]):
        results["overall_bias"] = "bullish"
    elif len(results["bearish_patterns"]) > len(results["bullish_patterns"]):
        results["overall_bias"] = "bearish"
    elif results["bullish_patterns"] or results["bearish_patterns"]:
        results["overall_bias"] = "mixed"

    results["summary"] = (
        f"Found {len(all_found)} pattern(s): "
        f"{len(results['bullish_patterns'])} bullish, {len(results['bearish_patterns'])} bearish. "
        f"Overall bias: {results['overall_bias'].upper()}."
        if all_found else "No significant chart patterns detected in current lookback window."
    )

    return results


def main():
    symbol = get_symbol_from_args()
    log(f"Detecting chart patterns for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_patterns(df)
        output_result(result, symbol, "patterns")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
