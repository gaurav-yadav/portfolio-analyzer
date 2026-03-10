"""Tests for utils/data.py — data access layer."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from utils import data


def test_paths_are_absolute():
    assert data.BASE.is_absolute()
    assert data.CACHE_DIR.is_absolute()
    assert data.WL_DIR.is_absolute()
    assert data.TA_DIR.is_absolute()


def test_list_watchlists():
    wls = data.list_watchlists()
    assert isinstance(wls, list)
    # We should at least have default and shared after migration
    assert "default" in wls or "shared" in wls


def test_load_watchlist_returns_v2_fields():
    wls = data.list_watchlists()
    if not wls:
        pytest.skip("No watchlists found")

    wl = data.load_watchlist(wls[0])
    assert wl is not None
    assert "id" in wl
    assert "watchlist" in wl
    assert isinstance(wl["watchlist"], list)


def test_load_watchlist_missing():
    result = data.load_watchlist("nonexistent_watchlist_xyz")
    assert result is None


def test_watchlist_symbols():
    syms = data.watchlist_symbols("default")
    if syms:
        # All should be non-empty strings
        assert all(isinstance(s, str) and len(s) > 0 for s in syms)


def test_all_watchlist_symbols():
    result = data.all_watchlist_symbols()
    assert isinstance(result, dict)
    # Values should be lists of watchlist IDs
    for sym, wl_ids in result.items():
        assert isinstance(wl_ids, list)
        assert all(isinstance(wid, str) for wid in wl_ids)


def test_ticker_to_yf_us():
    entry = {"ticker": "AVGO", "market": "US"}
    assert data._ticker_to_yf(entry) == "AVGO"


def test_ticker_to_yf_india():
    entry = {"ticker": "RELIANCE", "market": "IN"}
    assert data._ticker_to_yf(entry) == "RELIANCE.NS"


def test_ticker_to_yf_already_suffixed():
    entry = {"ticker": "RELIANCE.NS", "market": "IN"}
    assert data._ticker_to_yf(entry) == "RELIANCE.NS"


def test_ticker_to_yf_no_market_defaults_ns():
    entry = {"ticker": "TCS"}
    assert data._ticker_to_yf(entry) == "TCS.NS"


def test_create_watchlist(tmp_path):
    """Test watchlist creation in a temp directory."""
    with patch.object(data, "WL_DIR", tmp_path):
        wl = data.create_watchlist("test_wl", "Test Watchlist", description="For testing")
        assert wl["id"] == "test_wl"
        assert wl["name"] == "Test Watchlist"
        assert wl["schema_version"] == 2
        assert wl["watchlist"] == []

        # Verify file was written
        path = tmp_path / "test_wl.json"
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["id"] == "test_wl"


def test_load_ohlcv_missing():
    result = data.load_ohlcv("NONEXISTENT_SYMBOL_XYZ")
    assert result is None


def test_load_ta_missing():
    result = data.load_ta("NONEXISTENT_SYMBOL_XYZ", "rsi")
    assert result is None


def test_load_score_missing():
    result = data.load_score("NONEXISTENT_SYMBOL_XYZ")
    assert result is None


def test_load_latest_scan():
    scan = data.load_latest_scan()
    # May or may not exist, but shouldn't crash
    assert scan is None or isinstance(scan, dict)


def test_load_ledger():
    entries = data.load_ledger()
    assert isinstance(entries, list)


def test_load_outcomes():
    outcomes = data.load_outcomes()
    assert isinstance(outcomes, list)
