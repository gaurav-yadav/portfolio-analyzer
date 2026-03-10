#!/usr/bin/env python3
"""
Bullish & Bearish Divergence Detection

Usage: uv run python scripts/ta/divergence.py <symbol>

Detects divergence between Price and RSI/MACD over the last 60 bars.

BULLISH DIVERGENCE (buy signal):
- Regular: Price makes lower low, RSI/MACD makes higher low → reversal likely
- Hidden:  Price makes higher low, RSI/MACD makes lower low → trend continuation

BEARISH DIVERGENCE (sell signal):
- Regular: Price makes higher high, RSI/MACD makes lower high → reversal likely
- Hidden:  Price makes lower high, RSI/MACD makes higher high → trend continuation (down)

Methodology:
- Finds swing highs/lows in price using local extrema (5-bar window)
- Compares direction of last 2 significant swings in price vs indicator
- Confirms only when divergence spans at least 5 bars
"""

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.indicators import compute_all
from utils.ta_config import DIV_LOOKBACK, DIV_SWING_WINDOW, CONFLUENCE_BOOST
from utils.ta_common import load_ohlcv, output_result, get_symbol_from_args, safe_round, log


def find_local_extrema(series: pd.Series, window: int = 5) -> tuple[list, list]:
    """Find local swing highs and lows using a rolling window."""
    highs = []
    lows = []
    vals = series.values

    for i in range(window, len(vals) - window):
        left = vals[i - window:i]
        right = vals[i + 1:i + window + 1]
        curr = vals[i]

        if curr == max(left) and curr == max(right) and curr >= max(vals[i - window:i + window + 1]):
            highs.append((i, curr))
        if curr == min(left) and curr == min(right) and curr <= min(vals[i - window:i + window + 1]):
            lows.append((i, curr))

    return highs, lows


def detect_divergence(
    price: pd.Series,
    indicator: pd.Series,
    lookback: int = DIV_LOOKBACK,
    min_bar_gap: int = 5,
    window: int = DIV_SWING_WINDOW,
) -> dict:
    """
    Detect regular and hidden bullish/bearish divergence.
    Returns divergence type and confidence.
    """
    price = price.tail(lookback).reset_index(drop=True)
    indicator = indicator.tail(lookback).dropna().reset_index(drop=True)

    # Align lengths
    min_len = min(len(price), len(indicator))
    price = price.tail(min_len).reset_index(drop=True)
    indicator = indicator.tail(min_len).reset_index(drop=True)

    if len(price) < window * 3:
        return {"detected": False, "reason": "insufficient_data"}

    price_highs, price_lows = find_local_extrema(price, window)
    ind_highs, ind_lows = find_local_extrema(indicator, window)

    divergences = []

    # --- BULLISH DIVERGENCE (check last 2 price lows) ---
    if len(price_lows) >= 2:
        # Get last 2 price swing lows
        pl1_idx, pl1_val = price_lows[-2]
        pl2_idx, pl2_val = price_lows[-1]

        # Must be at least min_bar_gap apart
        if pl2_idx - pl1_idx >= min_bar_gap:
            # Find corresponding indicator lows near those price lows
            il_near_pl1 = [il for il in ind_lows if abs(il[0] - pl1_idx) <= window + 2]
            il_near_pl2 = [il for il in ind_lows if abs(il[0] - pl2_idx) <= window + 2]

            if il_near_pl1 and il_near_pl2:
                il1_val = min(il_near_pl1, key=lambda x: x[1])[1]
                il2_val = min(il_near_pl2, key=lambda x: x[1])[1]

                price_lower_low = pl2_val < pl1_val
                ind_higher_low = il2_val > il1_val
                price_higher_low = pl2_val > pl1_val
                ind_lower_low = il2_val < il1_val

                # Regular bullish divergence
                if price_lower_low and ind_higher_low:
                    pct_diff = abs(pl2_val - pl1_val) / pl1_val * 100
                    ind_diff = abs(il2_val - il1_val)
                    confidence = min(90, 50 + int(pct_diff * 5) + int(ind_diff))
                    divergences.append({
                        "type": "regular_bullish",
                        "bias": "bullish",
                        "strength": "strong",
                        "description": f"Price: lower low ({pl1_val:.2f}→{pl2_val:.2f}), Indicator: higher low ({il1_val:.2f}→{il2_val:.2f})",
                        "price_swing": [safe_round(pl1_val, 2), safe_round(pl2_val, 2)],
                        "ind_swing": [safe_round(il1_val, 2), safe_round(il2_val, 2)],
                        "bar_gap": pl2_idx - pl1_idx,
                        "confidence_pct": confidence,
                        "trade_implication": "Potential reversal to upside. Watch for price confirmation above recent swing high.",
                    })

                # Hidden bullish divergence
                elif price_higher_low and ind_lower_low:
                    divergences.append({
                        "type": "hidden_bullish",
                        "bias": "bullish",
                        "strength": "moderate",
                        "description": f"Price: higher low ({pl1_val:.2f}→{pl2_val:.2f}), Indicator: lower low ({il1_val:.2f}→{il2_val:.2f})",
                        "price_swing": [safe_round(pl1_val, 2), safe_round(pl2_val, 2)],
                        "ind_swing": [safe_round(il1_val, 2), safe_round(il2_val, 2)],
                        "bar_gap": pl2_idx - pl1_idx,
                        "confidence_pct": 55,
                        "trade_implication": "Uptrend likely to continue. Good re-entry in pullback.",
                    })

    # --- BEARISH DIVERGENCE (check last 2 price highs) ---
    if len(price_highs) >= 2:
        ph1_idx, ph1_val = price_highs[-2]
        ph2_idx, ph2_val = price_highs[-1]

        if ph2_idx - ph1_idx >= min_bar_gap:
            ih_near_ph1 = [ih for ih in ind_highs if abs(ih[0] - ph1_idx) <= window + 2]
            ih_near_ph2 = [ih for ih in ind_highs if abs(ih[0] - ph2_idx) <= window + 2]

            if ih_near_ph1 and ih_near_ph2:
                ih1_val = max(ih_near_ph1, key=lambda x: x[1])[1]
                ih2_val = max(ih_near_ph2, key=lambda x: x[1])[1]

                price_higher_high = ph2_val > ph1_val
                ind_lower_high = ih2_val < ih1_val
                price_lower_high = ph2_val < ph1_val
                ind_higher_high = ih2_val > ih1_val

                # Regular bearish divergence
                if price_higher_high and ind_lower_high:
                    pct_diff = abs(ph2_val - ph1_val) / ph1_val * 100
                    ind_diff = abs(ih2_val - ih1_val)
                    confidence = min(90, 50 + int(pct_diff * 5) + int(ind_diff))
                    divergences.append({
                        "type": "regular_bearish",
                        "bias": "bearish",
                        "strength": "strong",
                        "description": f"Price: higher high ({ph1_val:.2f}→{ph2_val:.2f}), Indicator: lower high ({ih1_val:.2f}→{ih2_val:.2f})",
                        "price_swing": [safe_round(ph1_val, 2), safe_round(ph2_val, 2)],
                        "ind_swing": [safe_round(ih1_val, 2), safe_round(ih2_val, 2)],
                        "bar_gap": ph2_idx - ph1_idx,
                        "confidence_pct": confidence,
                        "trade_implication": "Potential reversal to downside. Watch for price breakdown below recent swing low.",
                    })

                # Hidden bearish divergence
                elif price_lower_high and ind_higher_high:
                    divergences.append({
                        "type": "hidden_bearish",
                        "bias": "bearish",
                        "strength": "moderate",
                        "description": f"Price: lower high ({ph1_val:.2f}→{ph2_val:.2f}), Indicator: higher high ({ih1_val:.2f}→{ih2_val:.2f})",
                        "price_swing": [safe_round(ph1_val, 2), safe_round(ph2_val, 2)],
                        "ind_swing": [safe_round(ih1_val, 2), safe_round(ih2_val, 2)],
                        "bar_gap": ph2_idx - ph1_idx,
                        "confidence_pct": 55,
                        "trade_implication": "Downtrend likely to continue. Avoid longs.",
                    })

    return {
        "detected": len(divergences) > 0,
        "count": len(divergences),
        "divergences": divergences,
    }


def analyze_divergence(df, lookback: int = DIV_LOOKBACK) -> dict:
    """Run divergence detection on RSI and MACD vs price."""
    ind = compute_all(df)
    df = ind['df']

    price = df['Close']
    current_price = safe_round(price.iloc[-1], 2)

    # RSI divergence
    rsi_div = {"detected": False}
    if 'rsi' in df.columns:
        rsi_div = detect_divergence(price, df['rsi'], lookback=lookback)
        for d in rsi_div.get("divergences", []):
            d["indicator"] = "RSI"

    # MACD divergence (use histogram for cleaner signals)
    macd_div = {"detected": False}
    if 'macd_hist' in df.columns:
        macd_div = detect_divergence(price, df['macd_hist'], lookback=lookback)
        for d in macd_div.get("divergences", []):
            d["indicator"] = "MACD_Histogram"

    # Combine all divergences
    all_divergences = rsi_div.get("divergences", []) + macd_div.get("divergences", [])

    # Confluence: same divergence type on both RSI and MACD = higher confidence
    bullish_count = sum(1 for d in all_divergences if d["bias"] == "bullish")
    bearish_count = sum(1 for d in all_divergences if d["bias"] == "bearish")

    # Determine overall bias
    if bullish_count > 0 and bullish_count >= bearish_count:
        overall_signal = "bullish_divergence"
        overall_bias = "bullish"
        confluence = bullish_count >= 2  # Both RSI and MACD confirming
    elif bearish_count > 0 and bearish_count > bullish_count:
        overall_signal = "bearish_divergence"
        overall_bias = "bearish"
        confluence = bearish_count >= 2
    else:
        overall_signal = "no_divergence"
        overall_bias = "neutral"
        confluence = False

    max_confidence = max((d["confidence_pct"] for d in all_divergences), default=0)
    if confluence:
        max_confidence = min(95, max_confidence + CONFLUENCE_BOOST)  # Boost for multi-indicator confirmation

    return {
        "current_price": current_price,
        "lookback_bars": lookback,
        "overall_signal": overall_signal,
        "overall_bias": overall_bias,
        "confluence": confluence,
        "confidence_pct": max_confidence,
        "bullish_divergences": bullish_count,
        "bearish_divergences": bearish_count,
        "rsi_divergence": rsi_div,
        "macd_divergence": macd_div,
        "all_divergences": all_divergences,
        "trade_note": (
            f"{'⚠️ HIGH CONFIDENCE — ' if confluence else ''}{'Bullish' if overall_bias == 'bullish' else 'Bearish' if overall_bias == 'bearish' else 'No'} divergence detected. "
            f"{'Both RSI and MACD confirming.' if confluence else ''}"
        ),
    }


def main():
    symbol = get_symbol_from_args()
    log(f"Detecting divergence for {symbol}...")

    try:
        df = load_ohlcv(symbol)
        result = analyze_divergence(df)
        output_result(result, symbol, "divergence")
    except (FileNotFoundError, ValueError) as e:
        log(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
