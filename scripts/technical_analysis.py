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

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pandas_ta as ta

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import save_json


def score_rsi(rsi: float) -> int:
    """Score RSI on 1-10 scale."""
    if pd.isna(rsi):
        return 5
    if rsi < 30:
        return 9  # Oversold - bullish
    elif rsi < 40:
        return 7
    elif rsi < 60:
        return 5  # Neutral
    elif rsi < 70:
        return 4
    else:
        return 2  # Overbought - bearish


def score_macd(macd: float, signal: float, prev_macd: float, prev_signal: float) -> int:
    """Score MACD on 1-10 scale."""
    if pd.isna(macd) or pd.isna(signal):
        return 5

    macd_above = macd > signal
    prev_macd_above = prev_macd > prev_signal if not (pd.isna(prev_macd) or pd.isna(prev_signal)) else macd_above
    rising = macd > prev_macd if not pd.isna(prev_macd) else True

    if macd_above and rising:
        return 8  # Bullish and strengthening
    elif macd_above:
        return 6  # Bullish
    elif not macd_above and not rising:
        return 2  # Bearish and weakening
    else:
        return 4  # Bearish


def score_trend(close: float, sma50: float, sma200: float) -> int:
    """Score trend based on price vs SMAs on 1-10 scale."""
    if pd.isna(sma50):
        return 5  # Not enough data

    # If SMA200 is not available, just use SMA50
    if pd.isna(sma200):
        if close > sma50:
            return 7
        else:
            return 3

    if close > sma50 > sma200:
        return 9  # Strong uptrend
    elif close > sma50:
        return 6  # Above short-term
    elif close < sma50 < sma200:
        return 2  # Strong downtrend
    else:
        return 4  # Mixed


def score_bollinger(pctb: float) -> int:
    """Score Bollinger %B on 1-10 scale."""
    if pd.isna(pctb):
        return 5
    if pctb < 0.2:
        return 8  # Near lower band - potential bounce
    elif pctb < 0.8:
        return 5  # Middle range
    else:
        return 3  # Near upper band - potential resistance


def score_adx(adx: float, plus_di: float, minus_di: float) -> int:
    """Score ADX on 1-10 scale."""
    if pd.isna(adx):
        return 5

    uptrend = plus_di > minus_di if not (pd.isna(plus_di) or pd.isna(minus_di)) else True

    if adx > 25 and uptrend:
        return 8  # Strong uptrend
    elif adx > 25 and not uptrend:
        return 3  # Strong downtrend
    elif adx < 20:
        return 5  # Weak trend
    else:
        return 5  # Moderate trend


def score_volume(volume_ratio: float, is_up_day: bool) -> int:
    """Score volume on 1-10 scale."""
    if pd.isna(volume_ratio):
        return 5

    if volume_ratio > 1.5:
        if is_up_day:
            return 8  # High volume on up day - bullish
        else:
            return 3  # High volume on down day - bearish
    else:
        return 5  # Normal volume


def compute_technical_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators for the given OHLCV data."""
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

    # Calculate overall technical score
    technical_score = round(sum(scores.values()) / len(scores), 1)

    return {
        "indicators": indicators,
        "scores": scores,
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

    # Compute indicators
    try:
        result = compute_technical_indicators(df)
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
