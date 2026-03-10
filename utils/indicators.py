"""Shared TA computation layer — compute once, use everywhere.

All indicator computation lives here. Individual TA scripts import
pre-computed indicators instead of recomputing them independently.
"""

import pandas as pd
import pandas_ta as ta

from utils.ta_config import (
    RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STD,
    ADX_PERIOD,
    SMA_FAST, SMA_MID, SMA_SLOW,
    STOCH_RSI_LENGTH, STOCH_RSI_K, STOCH_RSI_D,
    ATR_PERIOD,
    VOLUME_SMA_PERIOD,
)
from utils.ta_common import safe_round


def compute_all(df: pd.DataFrame) -> dict:
    """Compute all core indicators from OHLCV. Single source of truth.

    Returns a dict with all indicator Series/DataFrames plus the enriched df.
    Individual TA scripts read from this instead of recomputing.
    """
    df = df.copy()

    # RSI
    df["rsi"] = ta.rsi(df["Close"], length=RSI_PERIOD)

    # MACD
    macd_result = ta.macd(df["Close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    if macd_result is not None:
        df["macd"] = macd_result.iloc[:, 0]
        df["macd_hist"] = macd_result.iloc[:, 1]
        df["macd_signal"] = macd_result.iloc[:, 2]

    # SMAs
    df["sma20"] = ta.sma(df["Close"], length=SMA_FAST)
    df["sma50"] = ta.sma(df["Close"], length=SMA_MID)
    if len(df) >= SMA_SLOW:
        df["sma200"] = ta.sma(df["Close"], length=SMA_SLOW)

    # Bollinger Bands
    bbands = ta.bbands(df["Close"], length=BB_PERIOD, std=BB_STD)
    if bbands is not None:
        df["bb_lower"] = bbands.iloc[:, 0]
        df["bb_middle"] = bbands.iloc[:, 1]
        df["bb_upper"] = bbands.iloc[:, 2]
        df["bb_bandwidth"] = bbands.iloc[:, 3]
        df["bb_pctb"] = bbands.iloc[:, 4]

    # ADX
    adx_result = ta.adx(df["High"], df["Low"], df["Close"], length=ADX_PERIOD)
    if adx_result is not None:
        df["adx"] = adx_result.iloc[:, 0]
        df["plus_di"] = adx_result.iloc[:, 1]
        df["minus_di"] = adx_result.iloc[:, 2]

    # Stochastic RSI
    stochrsi = ta.stochrsi(
        df["Close"], length=STOCH_RSI_LENGTH,
        rsi_length=RSI_PERIOD, k=STOCH_RSI_K, d=STOCH_RSI_D,
    )
    if stochrsi is not None and not stochrsi.empty:
        df["stoch_rsi_k"] = stochrsi.iloc[:, 0]
        df["stoch_rsi_d"] = stochrsi.iloc[:, 1]

    # ATR
    df["atr"] = ta.atr(df["High"], df["Low"], df["Close"], length=ATR_PERIOD)

    # Volume
    df["vol_sma20"] = ta.sma(df["Volume"], length=VOLUME_SMA_PERIOD)
    df["vol_ratio"] = df["Volume"] / df["vol_sma20"]

    return {"df": df}


def find_swing_points(series: pd.Series, window: int = 5) -> tuple[list, list]:
    """ONE implementation of swing detection. Used everywhere.

    Returns:
        Tuple of (highs, lows) where each is list of (index, value).
        Index is integer position within the series.
    """
    vals = series.values
    highs = []
    lows = []

    for i in range(window, len(vals) - window):
        segment = vals[i - window:i + window + 1]
        if vals[i] == max(segment):
            highs.append((i, float(vals[i])))
        if vals[i] == min(segment):
            lows.append((i, float(vals[i])))

    return highs, lows


def extract_latest(df: pd.DataFrame) -> dict:
    """Extract latest values from enriched DataFrame with safe handling.

    Returns a flat dict of the most recent indicator values, ready for
    signal interpretation by individual TA scripts.
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    def sf(val, decimals=4):
        return safe_round(val, decimals)

    result = {
        "price": sf(latest["Close"], 2),
        "open": sf(latest["Open"], 2),
        "high": sf(latest["High"], 2),
        "low": sf(latest["Low"], 2),
        "volume": int(latest["Volume"]) if pd.notna(latest["Volume"]) else None,

        # RSI
        "rsi": sf(latest.get("rsi"), 2),
        "rsi_prev": sf(prev.get("rsi"), 2),

        # MACD
        "macd": sf(latest.get("macd")),
        "macd_signal": sf(latest.get("macd_signal")),
        "macd_hist": sf(latest.get("macd_hist")),
        "macd_prev": sf(prev.get("macd")),
        "macd_signal_prev": sf(prev.get("macd_signal")),
        "macd_hist_prev": sf(prev.get("macd_hist")),

        # SMAs
        "sma20": sf(latest.get("sma20"), 2),
        "sma50": sf(latest.get("sma50"), 2),
        "sma200": sf(latest.get("sma200"), 2) if "sma200" in df.columns else None,

        # Bollinger
        "bb_lower": sf(latest.get("bb_lower"), 2),
        "bb_middle": sf(latest.get("bb_middle"), 2),
        "bb_upper": sf(latest.get("bb_upper"), 2),
        "bb_pctb": sf(latest.get("bb_pctb")),
        "bb_bandwidth": sf(latest.get("bb_bandwidth")),

        # ADX
        "adx": sf(latest.get("adx"), 2),
        "plus_di": sf(latest.get("plus_di"), 2),
        "minus_di": sf(latest.get("minus_di"), 2),
        "adx_prev": sf(prev.get("adx"), 2),

        # Stoch RSI
        "stoch_rsi_k": sf(latest.get("stoch_rsi_k"), 2),
        "stoch_rsi_d": sf(latest.get("stoch_rsi_d"), 2),
        "stoch_rsi_k_prev": sf(prev.get("stoch_rsi_k"), 2),
        "stoch_rsi_d_prev": sf(prev.get("stoch_rsi_d"), 2),

        # ATR
        "atr": sf(latest.get("atr"), 2),

        # Volume
        "vol_sma20": int(latest["vol_sma20"]) if pd.notna(latest.get("vol_sma20")) else None,
        "vol_ratio": sf(latest.get("vol_ratio"), 2),
        "is_up_day": bool(latest["Close"] >= latest["Open"]),
    }

    return result
