#!/usr/bin/env python3
"""
Technical Analysis Script - Computes technical indicators for a stock.

Usage:
    uv run python scripts/technical_analysis.py <symbol>

Example:
    uv run python scripts/technical_analysis.py RELIANCE.NS

Output:
    Writes analysis to data/technical/<symbol>.json
    Prints JSON to stdout
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pandas_ta as ta

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import save_json
from utils.config import DEFAULT_TECHNICAL_WEIGHTS as DEFAULT_WEIGHTS


def load_technical_weights(config_path: Path) -> dict:
    """
    Load technical indicator weights from CSV config file.

    Returns dict mapping indicator name to weight.
    Falls back to equal weights if config file is missing or invalid.
    """
    if not config_path.exists():
        print(f"Config file not found at {config_path}, using equal weights", file=sys.stderr)
        return DEFAULT_WEIGHTS.copy()

    try:
        weights = {}
        with open(config_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                indicator = row["indicator"].strip().lower()
                weight = float(row["weight"])
                weights[indicator] = weight

        # Validate that all required indicators are present
        required_indicators = {"rsi", "macd", "trend", "bollinger", "adx", "volume"}
        missing = required_indicators - set(weights.keys())
        if missing:
            print(f"Warning: Missing indicators in config: {missing}, using equal weights", file=sys.stderr)
            return DEFAULT_WEIGHTS.copy()

        # Validate weights sum to approximately 1.0
        total_weight = sum(weights[ind] for ind in required_indicators)
        if abs(total_weight - 1.0) > 0.01:
            print(f"Warning: Weights sum to {total_weight:.4f}, not 1.0. Normalizing.", file=sys.stderr)
            for ind in required_indicators:
                weights[ind] = weights[ind] / total_weight

        print(f"Loaded technical weights from {config_path}", file=sys.stderr)
        return weights

    except Exception as e:
        print(f"Error reading config file: {e}, using equal weights", file=sys.stderr)
        return DEFAULT_WEIGHTS.copy()


def score_rsi(rsi: float) -> int:
    """
    Score RSI on 1-10 scale (trend-aligned, not mean-reversion).

    Tuned for trend-following with pullback entries:
    - Extreme oversold may be falling knife, not automatic buy
    - Pullback zone (25-35) is ideal entry in confirmed uptrend
    - Overbought is caution for new entries, not bearish
    """
    if pd.isna(rsi):
        return 5
    if rsi < 25:
        return 4   # Extreme oversold - potential falling knife
    elif rsi < 35:
        return 7   # Pullback zone - ideal entry in uptrend
    elif rsi < 55:
        return 6   # Healthy momentum
    elif rsi < 70:
        return 5   # Neutral-to-strong
    elif rsi < 80:
        return 4   # Overbought - not ideal entry
    else:
        return 3   # Extreme overbought


def score_macd(macd: float, signal: float, prev_macd: float, prev_signal: float) -> int:
    """
    Score MACD on 1-10 scale (zero-line aware).

    Considers:
    - MACD vs Signal line (momentum direction)
    - Rising vs falling (momentum strength)
    - Above vs below zero (trend context)
    """
    if pd.isna(macd) or pd.isna(signal):
        return 5

    macd_above_signal = macd > signal
    rising = macd > prev_macd if not pd.isna(prev_macd) else True
    above_zero = macd > 0

    if macd_above_signal and rising and above_zero:
        return 9   # Full bullish - above zero, rising, above signal
    elif macd_above_signal and rising:
        return 7   # Recovering - rising but below zero
    elif macd_above_signal:
        return 5   # Momentum fading - above signal but not rising
    elif above_zero:
        return 4   # Pullback in uptrend - below signal but above zero
    else:
        return 2   # Full bearish - below zero and below signal


def score_trend(close: float, sma50: float, sma200: float) -> int:
    """
    Score trend based on price vs SMAs on 1-10 scale.

    This is the PRIMARY TREND GATE - most important indicator.
    Distinguishes between:
    - Strong uptrend (price > SMA50 > SMA200)
    - Pullback in uptrend (SMA50 > SMA200, price < SMA50)
    - Bear market rally (price > SMA50, SMA50 < SMA200)
    - Strong downtrend (price < SMA50 < SMA200)
    """
    if pd.isna(sma50):
        return 5  # Not enough data

    # If SMA200 is not available, just use SMA50
    if pd.isna(sma200):
        if close > sma50:
            return 7
        else:
            return 3

    if close > sma50 > sma200:
        return 9   # Strong uptrend - green light
    elif close > sma200 > sma50:
        return 7   # Golden cross forming / recovery
    elif close > sma50 and sma50 < sma200:
        return 5   # Bear market rally - caution
    elif sma50 > sma200 and close < sma50:
        return 5   # Pullback in uptrend - watch
    elif close < sma50 < sma200:
        return 2   # Strong downtrend - avoid
    else:
        return 4   # Sideways / no clear trend


def score_bollinger(pctb: float) -> int:
    """
    Score Bollinger %B on 1-10 scale (trend-neutral, not mean-reversion).

    For trend-following:
    - Near lower band is NOT automatically bullish (may be breakdown)
    - Near upper band is NOT automatically bearish (may be breakout)
    - Scores are neutral; requires trend confirmation for interpretation
    """
    if pd.isna(pctb):
        return 5
    if pctb < 0:
        return 3   # Breaking down below bands
    elif pctb < 0.2:
        return 5   # Near lower band (neutral until trend confirms)
    elif pctb < 0.5:
        return 6   # Pullback zone - healthy in uptrend
    elif pctb < 0.8:
        return 6   # Middle-upper range
    elif pctb <= 1.0:
        return 5   # Approaching upper band
    else:
        return 4   # Extended breakout - may be stretched


def score_adx(adx: float, plus_di: float, minus_di: float) -> int:
    """
    Score ADX on 1-10 scale (trend strength qualifier).

    ADX measures trend STRENGTH, not direction.
    Direction comes from +DI vs -DI.

    Key insight: Low ADX (< 20) means NO TREND - dampens all signals.
    Used as a qualifier for other indicators.
    """
    if pd.isna(adx):
        return 5

    uptrend = plus_di > minus_di if not (pd.isna(plus_di) or pd.isna(minus_di)) else True

    if adx > 30 and uptrend:
        return 9   # Strong uptrend - high confidence
    elif adx > 25 and uptrend:
        return 7   # Moderate uptrend
    elif adx > 25 and not uptrend:
        return 2   # Strong downtrend - avoid
    elif adx >= 20:
        return 5   # Developing trend
    else:
        return 4   # Weak/no trend - dampen all signals


def score_volume(volume_ratio: float, is_up_day: bool) -> int:
    """
    Score volume on 1-10 scale.

    Volume confirms price moves:
    - High volume on up day = accumulation (bullish)
    - High volume on down day = distribution (bearish)
    - Normal volume = neutral (no confirmation)
    """
    if pd.isna(volume_ratio):
        return 5

    if volume_ratio > 2.0:
        if is_up_day:
            return 9   # Breakout volume - strong accumulation
        else:
            return 2   # Panic selling - distribution
    elif volume_ratio > 1.5:
        if is_up_day:
            return 7   # Accumulation
        else:
            return 4   # Distribution
    elif volume_ratio > 1.0:
        return 5   # Normal volume
    else:
        return 5   # Below average - no signal


def compute_technical_indicators(df: pd.DataFrame, weights: dict = None) -> dict:
    """
    Compute all technical indicators for the given OHLCV data.

    Args:
        df: DataFrame with OHLCV columns
        weights: Dict mapping indicator names to weights. If None, uses equal weights.

    Returns:
        Dict with indicators, scores, and weighted technical_score.
    """
    # Use equal weights if not provided
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    # Ensure we have enough data
    if len(df) < 50:
        raise ValueError(f"Not enough data: {len(df)} rows, need at least 50")

    # Make a copy to avoid modifying original
    df = df.copy()

    # Compute indicators using pandas-ta
    # RSI(14)
    df["rsi"] = ta.rsi(df["Close"], length=14)

    # MACD(12, 26, 9)
    macd_result = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    if macd_result is not None:
        df["macd"] = macd_result.iloc[:, 0]  # MACD line
        df["macd_histogram"] = macd_result.iloc[:, 1]  # Histogram
        df["macd_signal"] = macd_result.iloc[:, 2]  # Signal line

    # SMA(50) and SMA(200)
    df["sma50"] = ta.sma(df["Close"], length=50)
    df["sma200"] = ta.sma(df["Close"], length=200) if len(df) >= 200 else pd.Series([float("nan")] * len(df))

    # Bollinger Bands(20, 2)
    bbands = ta.bbands(df["Close"], length=20, std=2)
    if bbands is not None:
        df["bb_lower"] = bbands.iloc[:, 0]
        df["bb_middle"] = bbands.iloc[:, 1]
        df["bb_upper"] = bbands.iloc[:, 2]
        df["bb_bandwidth"] = bbands.iloc[:, 3]
        df["bb_pctb"] = bbands.iloc[:, 4]

    # ADX(14)
    adx_result = ta.adx(df["High"], df["Low"], df["Close"], length=14)
    if adx_result is not None:
        df["adx"] = adx_result.iloc[:, 0]
        df["plus_di"] = adx_result.iloc[:, 1]
        df["minus_di"] = adx_result.iloc[:, 2]

    # Volume ratio vs 20-day average
    df["volume_sma20"] = ta.sma(df["Volume"], length=20)
    df["volume_ratio"] = df["Volume"] / df["volume_sma20"]

    # Get latest values
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    # Determine if up day
    is_up_day = latest["Close"] >= latest["Open"]

    # Build indicators dict with safe value extraction
    def safe_float(val):
        if pd.isna(val):
            return None
        return round(float(val), 4)

    indicators = {
        "rsi": safe_float(latest.get("rsi")),
        "macd": safe_float(latest.get("macd")),
        "macd_signal": safe_float(latest.get("macd_signal")),
        "macd_histogram": safe_float(latest.get("macd_histogram")),
        "sma50": safe_float(latest.get("sma50")),
        "sma200": safe_float(latest.get("sma200")),
        "bollinger_upper": safe_float(latest.get("bb_upper")),
        "bollinger_middle": safe_float(latest.get("bb_middle")),
        "bollinger_lower": safe_float(latest.get("bb_lower")),
        "bollinger_pctb": safe_float(latest.get("bb_pctb")),
        "adx": safe_float(latest.get("adx")),
        "plus_di": safe_float(latest.get("plus_di")),
        "minus_di": safe_float(latest.get("minus_di")),
        "volume_ratio": safe_float(latest.get("volume_ratio")),
        "latest_close": safe_float(latest["Close"]),
    }

    # Compute scores
    scores = {
        "rsi": score_rsi(latest.get("rsi")),
        "macd": score_macd(
            latest.get("macd"),
            latest.get("macd_signal"),
            prev.get("macd"),
            prev.get("macd_signal"),
        ),
        "trend": score_trend(
            latest["Close"],
            latest.get("sma50"),
            latest.get("sma200"),
        ),
        "bollinger": score_bollinger(latest.get("bb_pctb")),
        "adx": score_adx(
            latest.get("adx"),
            latest.get("plus_di"),
            latest.get("minus_di"),
        ),
        "volume": score_volume(latest.get("volume_ratio"), is_up_day),
    }

    # Calculate overall technical score using weighted average
    technical_score = sum(scores[ind] * weights[ind] for ind in scores.keys())
    technical_score = round(technical_score, 1)

    return {
        "indicators": indicators,
        "scores": scores,
        "weights": {ind: round(weights[ind], 4) for ind in scores.keys()},
        "technical_score": technical_score,
        "data_points": len(df),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/technical_analysis.py <symbol>", file=sys.stderr)
        sys.exit(1)

    symbol = sys.argv[1]
    print(f"Computing technical indicators for {symbol}...", file=sys.stderr)

    # Read OHLCV data from parquet
    base_path = Path(__file__).parent.parent
    ohlcv_path = base_path / "cache" / "ohlcv" / f"{symbol}.parquet"

    if not ohlcv_path.exists():
        print(f"Error: OHLCV data not found at {ohlcv_path}", file=sys.stderr)
        sys.exit(1)

    try:
        df = pd.read_parquet(ohlcv_path)
        print(f"Loaded {len(df)} data points from {ohlcv_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading parquet file: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure required columns exist
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns: {missing_cols}", file=sys.stderr)
        sys.exit(1)

    # Load technical weights from config
    config_path = base_path / "config" / "technical_weights.csv"
    weights = load_technical_weights(config_path)

    # Compute indicators
    try:
        result = compute_technical_indicators(df, weights)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build output
    output = {
        "symbol": symbol,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "data_points": result["data_points"],
        "indicators": result["indicators"],
        "scores": result["scores"],
        "weights": result["weights"],
        "technical_score": result["technical_score"],
    }

    # Save to data/technical/<symbol>.json
    output_path = base_path / "data" / "technical" / f"{symbol}.json"
    save_json(output_path, output)
    print(f"Saved analysis to {output_path}", file=sys.stderr)

    # Print JSON to stdout
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
