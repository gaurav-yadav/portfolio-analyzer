#!/usr/bin/env python3
"""
Watchlist Snapshot (v2) - snapshot a watchlist's state using local cache only.

This script:
  1) Reads watchlist events and materializes the active watchlist
  2) Reads cached OHLCV + existing technical snapshots (no fetching)
  3) Writes a per-run snapshot JSON under:
       data/watchlists/<watchlist_id>/snapshots/<run_id>.json

Usage:
  uv run python scripts/watchlist_snapshot.py swing
  uv run python scripts/watchlist_snapshot.py swing --run-id 20260121_101500
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from utils.helpers import load_json, save_json  # noqa: E402
from utils.config import WATCHER_THRESHOLDS  # noqa: E402

from watchlist_events import events_path_for, materialize_watchlist, read_events  # noqa: E402



BASE_PATH = Path(__file__).parent.parent
CACHE_DIR = BASE_PATH / "cache" / "ohlcv"
TECHNICAL_DIR = BASE_PATH / "data" / "technical"


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _default_run_id(ts_iso: str | None = None) -> str:
    if ts_iso:
        try:
            dt = datetime.fromisoformat(ts_iso)
            return dt.strftime("%Y%m%d_%H%M%S")
        except Exception:
            pass
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_float(x) -> float | None:
    try:
        if x is None:
            return None
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except Exception:
        return None


def load_ohlcv(symbol_yf: str) -> pd.DataFrame | None:
    path = CACHE_DIR / f"{symbol_yf}.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def compute_atr14(df: pd.DataFrame) -> float | None:
    if df is None or df.empty:
        return None
    required = {"High", "Low", "Close"}
    if not required.issubset(df.columns):
        return None
    if len(df) < 15:
        return None

    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(14, min_periods=14).mean()
    return _safe_float(atr.iloc[-1])


def compute_sma(df: pd.DataFrame, window: int) -> float | None:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    if len(df) < window:
        return None
    return _safe_float(df["Close"].astype(float).rolling(window).mean().iloc[-1])


def compute_rolling_high(df: pd.DataFrame, window: int) -> float | None:
    if df is None or df.empty or "High" not in df.columns:
        return None
    if len(df) < window:
        return None
    return _safe_float(df["High"].astype(float).rolling(window).max().iloc[-1])


def trend_label(close: float | None, sma50: float | None, sma200: float | None) -> str:
    if close is None or sma50 is None or sma200 is None:
        return "n/a"
    if close > sma50 > sma200:
        return "uptrend"
    if close < sma50 < sma200:
        return "downtrend"
    return "mixed"


@dataclass(frozen=True)
class SnapshotRow:
    symbol_yf: str
    symbol: str
    close: float | None
    rsi: float | None
    atr_pct: float | None
    sma50: float | None
    sma200: float | None
    drawdown_20d_pct: float | None
    trend: str
    flags: list[str]
    added_price: float | None
    watch_return_pct: float | None
    meta: dict


def build_snapshot(watchlist_id: str, view: dict, as_of: str, run_id: str) -> dict:
    rows: list[dict] = []
    alerts: list[dict] = []

    stocks = view.get("stocks") or []
    if not isinstance(stocks, list):
        stocks = []

    for stock in stocks:
        if not isinstance(stock, dict):
            continue

        symbol_yf = str(stock.get("symbol_yf") or "").strip()
        symbol = str(stock.get("symbol") or "").strip()
        if not symbol_yf:
            continue

        technical = load_json(TECHNICAL_DIR / f"{symbol_yf}.json") or {}
        indicators = (technical.get("indicators") or {}) if isinstance(technical, dict) else {}

        rsi = _safe_float(indicators.get("rsi"))
        sma50 = _safe_float(indicators.get("sma50"))
        sma200 = _safe_float(indicators.get("sma200"))
        close = _safe_float(indicators.get("latest_close"))

        ohlcv = load_ohlcv(symbol_yf)
        if close is None and ohlcv is not None and not ohlcv.empty and "Close" in ohlcv.columns:
            close = _safe_float(ohlcv["Close"].astype(float).iloc[-1])

        atr14 = compute_atr14(ohlcv) if ohlcv is not None else None
        atr_pct = (atr14 / close * 100) if (atr14 is not None and close) else None

        if sma50 is None and ohlcv is not None:
            sma50 = compute_sma(ohlcv, 50)
        if sma200 is None and ohlcv is not None:
            sma200 = compute_sma(ohlcv, 200)

        high20 = compute_rolling_high(ohlcv, 20) if ohlcv is not None else None
        drawdown_20d_pct = (
            (high20 - close) / high20 * 100
            if (high20 is not None and close is not None and high20 > 0)
            else None
        )

        flags: list[str] = []
        if atr_pct is not None and atr_pct >= WATCHER_THRESHOLDS["atr_pct_high"]:
            flags.append("high_volatility")
        if rsi is not None and rsi <= WATCHER_THRESHOLDS["rsi_oversold"]:
            flags.append("rsi_oversold")
        if rsi is not None and rsi >= WATCHER_THRESHOLDS["rsi_overbought"]:
            flags.append("rsi_overbought")
        if drawdown_20d_pct is not None and drawdown_20d_pct >= WATCHER_THRESHOLDS["drawdown_20d_pct"]:
            flags.append("pullback_20d")
        if close is not None and sma200 is not None and close < sma200:
            flags.append("below_sma200")

        tr = trend_label(close, sma50, sma200)
        if tr == "downtrend":
            flags.append("downtrend")

        added_price = _safe_float(stock.get("added_price"))
        watch_return_pct = (
            (close - added_price) / added_price * 100
            if (close is not None and added_price and added_price > 0)
            else None
        )

        meta = {
            "plan": stock.get("plan") if isinstance(stock.get("plan"), dict) else {},
            "tags": stock.get("tags") if isinstance(stock.get("tags"), list) else [],
            "source_scan": stock.get("source_scan") or "",
            "added_date": stock.get("added_date") or "",
            "added_from_scan": stock.get("added_from_scan") or "",
            "last_event_at": stock.get("last_event_at") or "",
        }

        row = SnapshotRow(
            symbol_yf=symbol_yf,
            symbol=symbol,
            close=close,
            rsi=rsi,
            atr_pct=atr_pct,
            sma50=sma50,
            sma200=sma200,
            drawdown_20d_pct=drawdown_20d_pct,
            trend=tr,
            flags=flags,
            added_price=added_price,
            watch_return_pct=watch_return_pct,
            meta=meta,
        )

        rows.append(
            {
                "symbol_yf": row.symbol_yf,
                "symbol": row.symbol,
                "as_of": as_of,
                "close": row.close,
                "rsi": row.rsi,
                "atr_pct": row.atr_pct,
                "sma50": row.sma50,
                "sma200": row.sma200,
                "drawdown_20d_pct": row.drawdown_20d_pct,
                "trend": row.trend,
                "flags": row.flags,
                "added_price": row.added_price,
                "watch_return_pct": row.watch_return_pct,
                "meta": row.meta,
            }
        )

        if flags:
            alerts.append({"symbol_yf": symbol_yf, "flags": flags})

    rows.sort(key=lambda r: str(r.get("symbol_yf") or ""))
    alerts.sort(key=lambda a: len(a.get("flags") or []), reverse=True)

    return {
        "watchlist_id": watchlist_id,
        "run_id": run_id,
        "as_of": as_of,
        "symbols": len(rows),
        "summary": {
            "alerts": len(alerts),
            "needs_attention": [a["symbol_yf"] for a in alerts[:10]],
        },
        "rows": rows,
        "alerts": alerts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a local-cache watchlist snapshot (v2).")
    parser.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    parser.add_argument("--run-id", default="", help="Run identifier (default: derived from as_of or now)")
    parser.add_argument("--as-of", default="", help="As-of timestamp ISO-8601 (default: now)")
    parser.add_argument("--out", default="", help="Output JSON path (default: data/watchlists/<id>/snapshots/<run_id>.json)")
    args = parser.parse_args()

    as_of = args.as_of or _now_iso()
    run_id = args.run_id or _default_run_id(as_of)

    events_path = events_path_for(args.watchlist_id)
    events = read_events(events_path)
    view = materialize_watchlist(args.watchlist_id, events)

    report = build_snapshot(args.watchlist_id, view, as_of=as_of, run_id=run_id)

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = BASE_PATH / "data" / "watchlists" / args.watchlist_id / "snapshots" / f"{run_id}.json"

    save_json(out_path, report)
    # Also keep the materialized view updated for other scripts.
    save_json(BASE_PATH / "data" / "watchlists" / args.watchlist_id / "watchlist.json", view)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
