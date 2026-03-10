"""Tests for utils/ta_config.py — verify all constants are accessible and sane."""

from utils.ta_config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STD, ADX_PERIOD,
    SMA_FAST, SMA_MID, SMA_SLOW,
    STOCH_RSI_LENGTH, STOCH_RSI_K, STOCH_RSI_D,
    ATR_PERIOD, VOLUME_SMA_PERIOD,
    RSI_OVERSOLD, RSI_OVERBOUGHT,
    ADX_WEAK, ADX_STRONG,
    VOLUME_SPIKE, VOLUME_HIGH,
    FIB_PROXIMITY_PCT, FIB_LOOKBACK, FIB_RATIOS,
    BULL_FLAG_POLE_MIN, BULL_FLAG_CONSOL_MAX,
    PATTERN_LOOKBACK, DIV_LOOKBACK, DIV_SWING_WINDOW,
    SIGNAL_BULLISH_THRESHOLD, CONFLUENCE_BOOST,
)


def test_indicator_periods_positive():
    for name, val in [
        ("RSI_PERIOD", RSI_PERIOD),
        ("MACD_FAST", MACD_FAST),
        ("MACD_SLOW", MACD_SLOW),
        ("MACD_SIGNAL", MACD_SIGNAL),
        ("BB_PERIOD", BB_PERIOD),
        ("ADX_PERIOD", ADX_PERIOD),
        ("SMA_FAST", SMA_FAST),
        ("SMA_MID", SMA_MID),
        ("SMA_SLOW", SMA_SLOW),
        ("ATR_PERIOD", ATR_PERIOD),
        ("VOLUME_SMA_PERIOD", VOLUME_SMA_PERIOD),
    ]:
        assert val > 0, f"{name} should be positive, got {val}"


def test_sma_ordering():
    assert SMA_FAST < SMA_MID < SMA_SLOW


def test_macd_ordering():
    assert MACD_FAST < MACD_SLOW


def test_rsi_thresholds():
    assert 0 < RSI_OVERSOLD < RSI_OVERBOUGHT < 100


def test_adx_thresholds():
    assert 0 < ADX_WEAK < ADX_STRONG


def test_volume_thresholds():
    assert VOLUME_HIGH < VOLUME_SPIKE


def test_fib_ratios():
    assert FIB_RATIOS[0] == 0.0
    assert FIB_RATIOS[-1] == 1.0
    assert len(FIB_RATIOS) == 7
    # Should be sorted ascending
    assert FIB_RATIOS == sorted(FIB_RATIOS)


def test_pattern_thresholds():
    assert BULL_FLAG_POLE_MIN > 0
    assert BULL_FLAG_CONSOL_MAX > 0
    assert PATTERN_LOOKBACK > 0
    assert DIV_LOOKBACK > 0
