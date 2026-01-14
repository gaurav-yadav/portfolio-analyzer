#!/usr/bin/env python3
"""
Portfolio Watcher - lightweight monitoring for holdings + watchlist.

Usage:
  uv run python scripts/watch_portfolio.py
  uv run python scripts/watch_portfolio.py --holdings --watchlist
  uv run python scripts/watch_portfolio.py --symbols RELIANCE.NS TCS.NS

What it does:
  - Loads holdings from data/holdings.json (optional)
  - Loads watchlist from data/watchlist.json (optional)
  - Uses cached OHLCV under cache/ohlcv/<symbol_yf>.parquet (no fetch)
  - Uses technical snapshots under data/technical/<symbol_yf>.json when present
  - Computes a few practical "signals with context" (ATR%, drawdown, trend)
  - Writes a timestamped JSON report under data/watcher/
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

from utils.config import WATCHER_THRESHOLDS  # noqa: E402
from utils.helpers import load_json, save_json  # noqa: E402


BASE_PATH = Path(__file__).parent.parent
CACHE_DIR = BASE_PATH / "cache" / "ohlcv"
TECHNICAL_DIR = BASE_PATH / "data" / "technical"
HOLDINGS_PATH = BASE_PATH / "data" / "holdings.json"
WATCHLIST_PATH = BASE_PATH / "data" / "watchlist.json"
WATCHER_DIR = BASE_PATH / "data" / "watcher"


def normalize_yf_symbol(symbol: str, default_suffix: str) -> str:
    s = symbol.strip().upper()
    if not s:
        return ""
    if "." in s:
        return s
    return f"{s}{default_suffix}" if default_suffix else s


@dataclass(frozen=True)
class HoldingAgg:
    symbol_yf: str
    quantity: float
    avg_price: float
    name: str | None = None


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


def load_holdings_aggregated() -> dict[str, HoldingAgg]:
    if not HOLDINGS_PATH.exists():
        return {}

    holdings = json.loads(HOLDINGS_PATH.read_text())
    agg: dict[str, dict[str, float | str | None]] = {}

    for row in holdings:
        symbol_yf = (row.get("symbol_yf") or "").strip()
        if not symbol_yf:
            continue

        quantity = _safe_float(row.get("quantity")) or 0.0
        avg_price = _safe_float(row.get("avg_price")) or 0.0
        name = row.get("name")

        if quantity <= 0 or avg_price <= 0:
            continue

        if symbol_yf not in agg:
            agg[symbol_yf] = {"qty": 0.0, "cost": 0.0, "name": name}

        agg[symbol_yf]["qty"] = float(agg[symbol_yf]["qty"]) + quantity
        agg[symbol_yf]["cost"] = float(agg[symbol_yf]["cost"]) + quantity * avg_price
        if not agg[symbol_yf].get("name") and name:
            agg[symbol_yf]["name"] = name

    result: dict[str, HoldingAgg] = {}
    for symbol_yf, a in agg.items():
        qty = float(a["qty"])
        cost = float(a["cost"])
        if qty <= 0:
            continue
        result[symbol_yf] = HoldingAgg(
            symbol_yf=symbol_yf,
            quantity=qty,
            avg_price=cost / qty,
            name=a.get("name") if isinstance(a.get("name"), str) else None,
        )
    return result


def load_watchlist_entries(default_suffix: str) -> dict[str, dict]:
    if not WATCHLIST_PATH.exists():
        return {}

    watchlist = json.loads(WATCHLIST_PATH.read_text())
    entries: dict[str, dict] = {}
    for stock in (watchlist.get("stocks") or []):
        raw = (stock.get("symbol") or "").strip()
        if not raw:
            continue
        symbol_yf = normalize_yf_symbol(raw, default_suffix)
        entries[symbol_yf] = stock
    return entries


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


def compute_rolling_high_low(df: pd.DataFrame, window: int) -> tuple[float | None, float | None]:
    if df is None or df.empty:
        return None, None
    if "High" not in df.columns or "Low" not in df.columns:
        return None, None
    if len(df) < window:
        return None, None
    high_n = _safe_float(df["High"].astype(float).rolling(window).max().iloc[-1])
    low_n = _safe_float(df["Low"].astype(float).rolling(window).min().iloc[-1])
    return high_n, low_n


def trend_label(close: float | None, sma50: float | None, sma200: float | None) -> str:
    if close is None or sma50 is None or sma200 is None:
        return "n/a"
    if close > sma50 > sma200:
        return "uptrend"
    if close < sma50 < sma200:
        return "downtrend"
    return "mixed"


def build_report(
    symbols: list[str],
    holdings: dict[str, HoldingAgg],
    watchlist: dict[str, dict],
) -> dict:
    rows: list[dict] = []
    alerts: list[dict] = []

    for symbol_yf in symbols:
        holding = holdings.get(symbol_yf)
        watch = watchlist.get(symbol_yf)

        sources: list[str] = []
        if holding is not None:
            sources.append("holdings")
        if watch is not None:
            sources.append("watchlist")

        technical = load_json(TECHNICAL_DIR / f"{symbol_yf}.json") or {}
        indicators = (technical.get("indicators") or {}) if isinstance(technical, dict) else {}

        rsi = _safe_float(indicators.get("rsi"))
        sma50 = _safe_float(indicators.get("sma50"))
        sma200 = _safe_float(indicators.get("sma200"))
        close = _safe_float(indicators.get("latest_close"))
        technical_score = _safe_float(technical.get("technical_score")) if isinstance(technical, dict) else None

        ohlcv = load_ohlcv(symbol_yf)
        if close is None and ohlcv is not None and not ohlcv.empty and "Close" in ohlcv.columns:
            close = _safe_float(ohlcv["Close"].astype(float).iloc[-1])

        atr14 = compute_atr14(ohlcv) if ohlcv is not None else None
        atr_pct = (atr14 / close * 100) if (atr14 is not None and close) else None

        if sma50 is None and ohlcv is not None:
            sma50 = compute_sma(ohlcv, 50)
        if sma200 is None and ohlcv is not None:
            sma200 = compute_sma(ohlcv, 200)

        high20, low20 = compute_rolling_high_low(ohlcv, 20) if ohlcv is not None else (None, None)
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

        tr_label = trend_label(close, sma50, sma200)
        if tr_label == "downtrend":
            flags.append("downtrend")

        pnl_pct: float | None = None
        if holding is not None and close is not None and holding.avg_price > 0:
            pnl_pct = (close - holding.avg_price) / holding.avg_price * 100

        watch_return_pct: float | None = None
        if watch is not None and close is not None:
            added_price = _safe_float(watch.get("added_price"))
            if added_price and added_price > 0:
                watch_return_pct = (close - added_price) / added_price * 100

        row = {
            "symbol_yf": symbol_yf,
            "sources": sources,
            "close": close,
            "rsi": rsi,
            "sma50": sma50,
            "sma200": sma200,
            "trend": tr_label,
            "technical_score": technical_score,
            "atr14": atr14,
            "atr_pct": atr_pct,
            "high20": high20,
            "low20": low20,
            "drawdown_20d_pct": drawdown_20d_pct,
            "pnl_pct": pnl_pct,
            "watch_return_pct": watch_return_pct,
            "flags": flags,
            "data": {
                "has_ohlcv_cache": bool(ohlcv is not None and not ohlcv.empty),
                "has_technical_snapshot": bool(technical),
            },
        }

        if holding is not None:
            row["position"] = {
                "quantity": holding.quantity,
                "avg_price": holding.avg_price,
                "name": holding.name,
            }
        if watch is not None:
            row["watch"] = {
                "added_date": watch.get("added_date"),
                "added_from_scan": watch.get("added_from_scan"),
                "added_price": _safe_float(watch.get("added_price")),
                "notes": watch.get("notes", ""),
            }

        rows.append(row)

        if flags:
            alerts.append(
                {
                    "symbol_yf": symbol_yf,
                    "flags": flags,
                    "headline": f"{symbol_yf}: {', '.join(flags)}",
                }
            )

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "symbols": len(symbols),
            "alerts": len(alerts),
        },
        "rows": rows,
        "alerts": alerts,
        "thresholds": WATCHER_THRESHOLDS,
    }


def print_table(report: dict) -> None:
    rows = report.get("rows") or []
    if not rows:
        print("No symbols to watch.")
        return

    print(f"\nPortfolio Watch ({report.get('timestamp')})")
    print("=" * 110)
    print(f"{'Symbol':<14} {'Src':<10} {'Close':>10} {'PnL%':>8} {'RSI':>7} {'ATR%':>7} {'Trend':<9} {'Flags'}")
    print("-" * 110)

    for r in rows:
        symbol = r.get("symbol_yf", "")
        src = ",".join(r.get("sources") or [])
        close = r.get("close")
        pnl = r.get("pnl_pct")
        rsi = r.get("rsi")
        atr_pct = r.get("atr_pct")
        tr = r.get("trend", "n/a")
        flags = ",".join(r.get("flags") or [])

        close_s = f"{close:,.2f}" if isinstance(close, (int, float)) else "?"
        pnl_s = f"{pnl:+.1f}" if isinstance(pnl, (int, float)) else "-"
        rsi_s = f"{rsi:.0f}" if isinstance(rsi, (int, float)) else "-"
        atr_s = f"{atr_pct:.1f}" if isinstance(atr_pct, (int, float)) else "-"

        print(f"{symbol:<14} {src:<10} {close_s:>10} {pnl_s:>8} {rsi_s:>7} {atr_s:>7} {tr:<9} {flags}")

    print("=" * 110)
    print(f"Alerts: {report.get('summary', {}).get('alerts', 0)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch holdings + watchlist using local cache and snapshots.")
    parser.add_argument("--holdings", action="store_true", help="Include data/holdings.json")
    parser.add_argument("--watchlist", action="store_true", help="Include data/watchlist.json")
    parser.add_argument("--default-suffix", default=".NS", help="Suffix for watchlist symbols without exchange suffix (default: .NS)")
    parser.add_argument("--symbols", nargs="*", default=[], help="Explicit Yahoo Finance tickers to include")
    parser.add_argument("--out", default="", help="Output JSON path (default: data/watcher/watch_YYYYMMDD_HHMMSS.json)")
    args = parser.parse_args()

    use_holdings = args.holdings
    use_watchlist = args.watchlist
    explicit_symbols = [s for s in (args.symbols or []) if s.strip()]

    # Default behavior for this watcher: include both, if available.
    if not use_holdings and not use_watchlist and not explicit_symbols:
        use_holdings = True
        use_watchlist = True

    holdings = load_holdings_aggregated() if use_holdings else {}
    watchlist = load_watchlist_entries(args.default_suffix) if use_watchlist else {}

    symbols: list[str] = []
    symbols.extend(list(holdings.keys()))
    symbols.extend(list(watchlist.keys()))
    symbols.extend([normalize_yf_symbol(s, default_suffix="") for s in explicit_symbols])

    # Deduplicate while preserving order
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        if not s or s in seen:
            continue
        unique_symbols.append(s)
        seen.add(s)

    if not unique_symbols:
        print("No symbols found. Add holdings/watchlist or pass --symbols.")
        return

    report = build_report(unique_symbols, holdings, watchlist)
    print_table(report)

    WATCHER_DIR.mkdir(parents=True, exist_ok=True)
    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = WATCHER_DIR / f"watch_{ts}.json"
    save_json(out_path, report)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
