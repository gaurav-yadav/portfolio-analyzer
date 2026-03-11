#!/usr/bin/env python3
"""
Bake dashboard data into a static JS file for GitHub Pages deployment.

Reads local data/ files and embeds them as window.BAKED_DATA in
dashboard/public/data.js. The dashboard detects this and uses it
instead of API calls (for static hosting).

Usage:
    uv run python scripts/bake_dashboard.py                    # bake only (uses existing technical data)
    uv run python scripts/bake_dashboard.py --refresh          # fetch OHLCV + recompute technicals, then bake
    uv run python scripts/bake_dashboard.py --refresh --push   # refresh + bake + push to GitHub Pages

Excludes: holdings, portfolios, input CSVs (privacy)
Includes: watchlists, suggestions, technical scores, TA indicators

--refresh pipeline:
  1. fetch_ohlcv.py for all watchlist symbols (18h freshness cache — safe to always run)
  2. technical_all.py --symbols ... (recomputes RSI/MACD/SMA/BB/ADX/StochRSI/patterns)
  3. bake_dashboard.py (reads updated data/ files → dashboard/public/data.js)
"""

import json
import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
CACHE = BASE / "cache" / "ohlcv"
OUT  = BASE / "dashboard" / "public" / "data.js"
LIB_SRC = BASE / "dashboard" / "node_modules" / "lightweight-charts" / "dist" / "lightweight-charts.standalone.production.js"
LIB_DST = BASE / "dashboard" / "public" / "lib"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def load_technical() -> list:
    d = DATA / "technical"
    if not d.exists():
        return []
    results = []
    for f in d.glob("*.json"):
        data = read_json(f)
        if data:
            results.append({"symbol": f.stem, **data})
    return results


def load_ta_indicators() -> dict:
    """Returns {symbol: {indicator_name: data}}"""
    d = DATA / "ta"
    if not d.exists():
        return {}
    by_symbol: dict = {}
    for f in sorted(d.glob("*.json")):
        # filename: SYMBOL_indicatorname.json
        parts = f.stem.split("_", 1)
        if len(parts) != 2:
            continue
        sym, name = parts[0], parts[1]
        if sym not in by_symbol:
            by_symbol[sym] = {}
        by_symbol[sym][name] = read_json(f)
    return by_symbol


def load_ohlcv(symbols: list) -> dict:
    """Read parquet files for given symbols → {symbol: [{time,open,high,low,close,volume}]}"""
    if not CACHE.exists():
        return {}
    result = {}
    for sym in symbols:
        pq = CACHE / f"{sym}.parquet"
        if not pq.exists():
            continue
        try:
            df = pd.read_parquet(pq)
            records = []
            for idx, row in df.iterrows():
                records.append({
                    "time": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })
            result[sym] = records
        except Exception as e:
            print(f"  ⚠️  OHLCV read failed for {sym}: {e}", file=sys.stderr)
    return result


def copy_lib():
    """Copy lightweight-charts standalone JS to public/lib/ for static serving."""
    if not LIB_SRC.exists():
        print(f"  ⚠️  lightweight-charts not found at {LIB_SRC}", file=sys.stderr)
        print("     Run: cd dashboard && npm install lightweight-charts", file=sys.stderr)
        return
    LIB_DST.mkdir(parents=True, exist_ok=True)
    dst = LIB_DST / LIB_SRC.name
    shutil.copy2(LIB_SRC, dst)
    size_kb = dst.stat().st_size / 1024
    print(f"  Copied lightweight-charts ({size_kb:.0f} KB) → public/lib/")


def load_watchlists() -> list:
    d = DATA / "watchlists"
    if not d.exists():
        return []

    results = []
    # Flat files: data/watchlists/<name>.json (primary format)
    for f in sorted(d.glob("*.json")):
        data = read_json(f)
        if not data:
            continue
        wl_id = f.stem
        if "id" not in data:
            data["id"] = wl_id
        if "name" not in data:
            data["name"] = wl_id.replace("_", " ").replace("-", " ").title()
        # Normalize entries for frontend
        for s in (data.get("watchlist") or []):
            if "ticker" not in s and "symbol" in s:
                s["ticker"] = s["symbol"]
            if "market" not in s:
                ticker = str(s.get("ticker") or "")
                s["market"] = "IN" if ticker.endswith(".NS") or ticker.endswith(".BO") else "US"
        results.append({"id": wl_id, "data": data})
    return results


def load_suggestions():
    ledger = read_jsonl(DATA / "suggestions" / "ledger.jsonl")
    outcomes_dir = DATA / "suggestions" / "outcomes"
    outcomes = []
    if outcomes_dir.exists():
        for f in outcomes_dir.glob("*.jsonl"):
            outcomes.extend(read_jsonl(f))
    return ledger, outcomes


def compute_suggestion_stats(ledger, outcomes):
    outcome_map = {o["suggestion_id"]: o for o in outcomes if "suggestion_id" in o}
    total = len(ledger)
    resolved = [o for o in outcome_map.values() if o.get("status") in ("won", "lost", "expired")]
    won  = sum(1 for o in resolved if o["status"] == "won")
    lost = sum(1 for o in resolved if o["status"] == "lost")
    expired = sum(1 for o in resolved if o["status"] == "expired")
    open_ = total - len(resolved)
    win_rate = round(won / len(resolved) * 100, 1) if resolved else 0
    avg_pnl = round(sum(o.get("pnl_pct", 0) for o in resolved) / len(resolved), 2) if resolved else 0

    by_conf: dict = {}
    for entry in ledger:
        conf = entry.get("confidence", "?")
        if conf not in by_conf:
            by_conf[conf] = {"total": 0, "won": 0, "lost": 0, "expired": 0, "open": 0, "pnls": []}
        by_conf[conf]["total"] += 1
        o = outcome_map.get(entry.get("id"))
        if o:
            s = o.get("status")
            if s in by_conf[conf]:
                by_conf[conf][s] += 1
            by_conf[conf]["pnls"].append(o.get("pnl_pct", 0))
        else:
            by_conf[conf]["open"] += 1

    for k, v in by_conf.items():
        r = v["won"] + v["lost"] + v["expired"]
        v["winRate"] = round(v["won"] / r * 100, 1) if r else 0
        v["avgPnl"] = round(sum(v["pnls"]) / len(v["pnls"]), 2) if v["pnls"] else 0
        del v["pnls"]

    return {
        "total": total, "won": won, "lost": lost, "expired": expired,
        "open": open_, "winRate": win_rate, "avgPnl": avg_pnl,
        "byConfidence": by_conf,
    }


def fetch_prices(symbols: list) -> dict:
    """Fetch current prices for a list of symbols using yfinance."""
    if not symbols:
        return {}
    try:
        import yfinance as yf
        result = {}
        data = yf.download(symbols, period="5d", auto_adjust=True, progress=False, group_by="ticker")
        for sym in symbols:
            try:
                df = data[sym] if len(symbols) > 1 else data
                if df.empty:
                    continue
                # Drop NaN closes (market not settled yet) and use last valid
                closes = df["Close"].dropna()
                if closes.empty:
                    continue
                price = float(closes.iloc[-1])
                prev  = float(closes.iloc[-2]) if len(closes) > 1 else price
                if not (price == price):  # NaN check
                    continue
                change_pct = round((price - prev) / prev * 100, 2)
                result[sym] = {"price": round(price, 2), "change_pct": change_pct}
            except Exception:
                pass
        return result
    except Exception as e:
        print(f"  ⚠️  Price fetch failed: {e}", file=sys.stderr)
        return {}


def get_watchlist_symbols() -> tuple[list[str], list[str]]:
    """Extract all active watchlist tickers split by market (IN vs US).
    Returns (in_symbols, us_symbols) as yfinance-style tickers."""
    d = DATA / "watchlists"
    in_syms, us_syms = [], []
    seen = set()

    def collect(stocks):
        for s in stocks:
            if s.get("status") == "REMOVED":
                continue
            ticker = (s.get("ticker") or s.get("symbol") or "").strip().upper()
            if not ticker:
                continue
            market = (s.get("market") or "US").upper()
            if market == "IN":
                yf_sym = ticker if "." in ticker else f"{ticker}.NS"
                if yf_sym in seen:
                    continue
                seen.add(yf_sym)
                in_syms.append(yf_sym)
            else:
                if ticker in seen:
                    continue
                seen.add(ticker)
                us_syms.append(ticker)

    # flat files: data/watchlists/<name>.json (primary format)
    for f in d.glob("*.json"):
        data = read_json(f)
        if data:
            collect(data.get("watchlist") or data.get("stocks") or [])

    return in_syms, us_syms


def refresh_technicals(in_symbols: list[str], us_symbols: list[str]) -> None:
    """Fetch fresh OHLCV and recompute technical indicators for all watchlist stocks."""
    all_symbols = in_symbols + us_symbols
    if not all_symbols:
        print("  No symbols to refresh.")
        return

    print(f"\n{'='*55}")
    print(f"  Refreshing technicals for {len(all_symbols)} symbols")
    print(f"  IN: {len(in_symbols)}  |  US: {len(us_symbols)}")
    print(f"{'='*55}")

    # Step 1: Fetch OHLCV (uses 18h freshness cache — safe to call every bake)
    print("\n[1/2] Fetching OHLCV data...")
    fetch_script = BASE / "scripts" / "fetch_ohlcv.py"
    if in_symbols:
        r = subprocess.run(
            ["uv", "run", "python", str(fetch_script)] + in_symbols,
            cwd=BASE, capture_output=True, text=True
        )
        ok_count = r.stdout.count("✓") + r.stdout.count("OK") + r.stdout.count("cached")
        print(f"  IN stocks: {ok_count}/{len(in_symbols)} fetched/cached"
              + (f" (errors: {r.returncode})" if r.returncode != 0 else ""))
        if r.returncode != 0 and r.stderr:
            print(f"  stderr: {r.stderr[:300]}", file=sys.stderr)

    if us_symbols:
        # US OHLCV: fetch_ohlcv.py also handles US tickers via yfinance
        r = subprocess.run(
            ["uv", "run", "python", str(fetch_script)] + us_symbols,
            cwd=BASE, capture_output=True, text=True
        )
        ok_count = r.stdout.count("✓") + r.stdout.count("OK") + r.stdout.count("cached")
        print(f"  US stocks: {ok_count}/{len(us_symbols)} fetched/cached"
              + (f" (errors: {r.returncode})" if r.returncode != 0 else ""))

    # Step 2: Recompute technical indicators for all symbols
    print(f"\n[2/2] Computing technical indicators...")
    ta_script = BASE / "scripts" / "technical_all.py"
    r = subprocess.run(
        ["uv", "run", "python", str(ta_script), "--symbols"] + all_symbols,
        cwd=BASE, capture_output=True, text=True
    )
    # technical_all.py prints progress per symbol to stdout
    for line in r.stdout.splitlines():
        if line.strip():
            print(f"  {line}")
    if r.returncode != 0 and r.stderr:
        print(f"  Warnings: {r.stderr[:300]}", file=sys.stderr)
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="git add/commit/push after baking")
    parser.add_argument("--no-prices", action="store_true", help="skip live price fetch")
    parser.add_argument("--no-ohlcv", action="store_true", help="skip OHLCV baking")
    parser.add_argument("--refresh", action="store_true",
                        help="Fetch fresh OHLCV + recompute technicals for all watchlist stocks before baking")
    args = parser.parse_args()

    # Refresh technicals BEFORE loading any data
    if args.refresh:
        in_syms, us_syms = get_watchlist_symbols()
        refresh_technicals(in_syms, us_syms)

    print("Baking dashboard data...")

    technical    = load_technical()
    ta           = load_ta_indicators()
    watchlists   = load_watchlists()
    ledger, outcomes = load_suggestions()
    stats        = compute_suggestion_stats(ledger, outcomes)

    # Collect all symbols that have technical data
    all_symbols = [t["symbol"] for t in technical]

    # OHLCV
    ohlcv = {}
    if not args.no_ohlcv and all_symbols:
        print(f"  Baking OHLCV for {len(all_symbols)} symbols...", end=" ", flush=True)
        ohlcv = load_ohlcv(all_symbols)
        print(f"got {len(ohlcv)}")

    # Copy lightweight-charts lib for static serving
    copy_lib()

    # Fetch prices for all watchlist tickers
    prices = {}
    if not args.no_prices:
        all_tickers = []
        for wl in watchlists:
            stocks = wl.get("data", {}).get("watchlist", [])
            for s in stocks:
                if s.get("status") == "REMOVED":
                    continue
                ticker = s.get("ticker", "")
                market = s.get("market", "")
                yf_sym = ticker + ".NS" if market == "IN" and "." not in ticker else ticker
                if yf_sym:
                    all_tickers.append(yf_sym)
        all_tickers = list(dict.fromkeys(all_tickers))
        if all_tickers:
            print(f"  Fetching prices for {len(all_tickers)} tickers...", end=" ", flush=True)
            prices = fetch_prices(all_tickers)
            print(f"got {len(prices)}")

    baked = {
        "bakedAt": datetime.now(timezone.utc).isoformat(),
        "technical": technical,
        "ta": ta,
        "ohlcv": ohlcv,
        "watchlists": watchlists,
        "suggestions": ledger,
        "suggestionOutcomes": outcomes,
        "suggestionStats": stats,
        "prices": prices,
    }

    js = f"// Auto-generated by bake_dashboard.py — do not edit manually\n"
    js += f"window.BAKED_DATA = {json.dumps(baked, indent=2, ensure_ascii=False)};\n"

    OUT.write_text(js, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"✅ Wrote {OUT} ({size_kb:.1f} KB)")
    print(f"   Stocks: {len(technical)} | TA: {len(ta)} | OHLCV: {len(ohlcv)} | Watchlists: {len(watchlists)} | Suggestions: {len(ledger)}")

    if args.push:
        print("\nPushing to GitHub...")
        cmds = [
            ["git", "add", "dashboard/public/data.js", "dashboard/public/index.html", "dashboard/public/app.js", "dashboard/public/app.css", "dashboard/public/lib/"],
            ["git", "commit", "-m", f"chore: bake dashboard data {datetime.now().strftime('%Y-%m-%d %H:%M')}" + (" [+technicals]" if args.refresh else "")],
            ["git", "push"],
        ]
        for cmd in cmds:
            r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
            print(f"  {' '.join(cmd[:2])}: {'OK' if r.returncode == 0 else 'FAILED'}")
            if r.returncode != 0 and "nothing to commit" not in r.stderr:
                print(f"  {r.stderr.strip()}")
                break
        print("Done. GitHub Pages will update in ~1 min.")


if __name__ == "__main__":
    main()
