"""Tests for utils/indicators.py — shared computation layer."""

import os

import pandas as pd
import pytest

from utils.indicators import compute_all, find_swing_points, extract_latest
from utils.data import load_ohlcv, CACHE_DIR


def _get_test_symbol() -> str | None:
    """Find a cached symbol to test with."""
    if not CACHE_DIR.exists():
        return None
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".parquet")]
    return files[0].replace(".parquet", "") if files else None


@pytest.fixture
def sample_df():
    """Load a real OHLCV DataFrame for testing."""
    symbol = _get_test_symbol()
    if symbol is None:
        pytest.skip("No cached OHLCV data available for testing")
    df = load_ohlcv(symbol)
    if df is None:
        pytest.skip(f"Could not load OHLCV for {symbol}")
    return df


def test_compute_all_returns_df(sample_df):
    result = compute_all(sample_df)
    assert "df" in result
    df = result["df"]
    assert isinstance(df, pd.DataFrame)


def test_compute_all_adds_rsi(sample_df):
    df = compute_all(sample_df)["df"]
    assert "rsi" in df.columns
    assert df["rsi"].notna().any()


def test_compute_all_adds_macd(sample_df):
    df = compute_all(sample_df)["df"]
    assert "macd" in df.columns
    assert "macd_hist" in df.columns
    assert "macd_signal" in df.columns


def test_compute_all_adds_smas(sample_df):
    df = compute_all(sample_df)["df"]
    assert "sma20" in df.columns
    assert "sma50" in df.columns


def test_compute_all_adds_bbands(sample_df):
    df = compute_all(sample_df)["df"]
    assert "bb_lower" in df.columns
    assert "bb_upper" in df.columns
    assert "bb_pctb" in df.columns


def test_compute_all_adds_adx(sample_df):
    df = compute_all(sample_df)["df"]
    assert "adx" in df.columns
    assert "plus_di" in df.columns
    assert "minus_di" in df.columns


def test_compute_all_adds_stoch_rsi(sample_df):
    df = compute_all(sample_df)["df"]
    assert "stoch_rsi_k" in df.columns
    assert "stoch_rsi_d" in df.columns


def test_compute_all_adds_atr(sample_df):
    df = compute_all(sample_df)["df"]
    assert "atr" in df.columns


def test_compute_all_adds_volume(sample_df):
    df = compute_all(sample_df)["df"]
    assert "vol_sma20" in df.columns
    assert "vol_ratio" in df.columns


def test_extract_latest(sample_df):
    ind = compute_all(sample_df)
    latest = extract_latest(ind["df"])

    assert isinstance(latest, dict)
    assert "price" in latest
    assert "rsi" in latest
    assert "macd" in latest
    assert "sma20" in latest
    assert "adx" in latest
    assert "vol_ratio" in latest
    assert "is_up_day" in latest

    # Values should be numbers or None
    for key in ["price", "rsi", "macd", "sma20", "adx"]:
        val = latest[key]
        assert val is None or isinstance(val, (int, float)), f"{key} = {val}"


def test_find_swing_points(sample_df):
    highs, lows = find_swing_points(sample_df["Close"], window=5)
    assert isinstance(highs, list)
    assert isinstance(lows, list)
    # Should find at least some swing points in real data
    assert len(highs) > 0 or len(lows) > 0


def test_find_swing_points_structure(sample_df):
    highs, lows = find_swing_points(sample_df["Close"], window=5)
    if highs:
        idx, val = highs[0]
        assert isinstance(idx, int)
        assert isinstance(val, float)
