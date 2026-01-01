#!/usr/bin/env python3
"""
Verify scan results by running full technical analysis.

Usage:
    uv run python scripts/verify_scan.py SYMBOL1 SYMBOL2 SYMBOL3
    uv run python scripts/verify_scan.py VPRPL IREDA RVNL COALINDIA

Features:
    - Runs FULL technical analysis (RSI, MACD, SMA, Bollinger, ADX, Volume)
    - Uses cached OHLCV when fresh (<18 hours)
    - Batches requests (5 at a time, 2s delay)
    - Exponential backoff on failures (2s, 4s, 8s)
    - Shows comprehensive results for informed decisions
"""

import sys
import json
import time
import math
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from utils.helpers import load_json, save_json
from utils.config import THRESHOLDS

# Rate limiting config
BATCH_SIZE = 5              # Fetch 5 stocks at a time
DELAY_BETWEEN_BATCH = 2     # 2 seconds between batches
MAX_RETRIES = 3             # Retry failed fetches
BASE_WAIT_SECONDS = 2       # Base wait for exponential backoff: 2s, 4s, 8s
CACHE_FRESHNESS_HOURS = 18

# Paths
CACHE_DIR = Path(__file__).parent.parent / "cache" / "ohlcv"
CACHE_METADATA_PATH = Path(__file__).parent.parent / "cache" / "cache_metadata.json"
# Use separate directory to avoid schema clash with portfolio technical analysis
SCAN_TECHNICAL_DIR = Path(__file__).parent.parent / "data" / "scan_technical"


def log(msg: str):
    """Print to stderr for logging."""
    print(msg, file=sys.stderr)


def safe_float(x, default=None):
    """Convert to float, returning default if NaN or invalid."""
    try:
        val = float(x)
        return default if math.isnan(val) else val
    except (TypeError, ValueError):
        return default


def normalize_symbol(s: str) -> str:
    """Normalize symbol, preserving .NS/.BO suffix if provided."""
    s = s.upper().strip()
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    return f"{s}.NS"


def display_symbol(yf_symbol: str) -> str:
    """Get display symbol without exchange suffix."""
    return yf_symbol.replace(".NS", "").replace(".BO", "")


def is_cache_fresh(symbol: str, metadata: dict) -> bool:
    """Check if cached data is fresh."""
    if symbol not in metadata:
        return False

    last_fetched_str = metadata.get(symbol, {}).get("last_fetched")
    if not last_fetched_str:
        return False

    try:
        last_fetched = datetime.fromisoformat(last_fetched_str)
        age = datetime.now() - last_fetched
        return age < timedelta(hours=CACHE_FRESHNESS_HOURS)
    except:
        return False


def load_cached_ohlcv(yf_symbol: str) -> pd.DataFrame | None:
    """Load OHLCV from cache.

    Args:
        yf_symbol: Full symbol with exchange suffix (e.g., RELIANCE.NS)
    """
    cache_path = CACHE_DIR / f"{yf_symbol}.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    # Fallback: try without suffix for backwards compatibility
    base_symbol = display_symbol(yf_symbol)
    cache_path = CACHE_DIR / f"{base_symbol}.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    return None


def fetch_with_backoff(yf_symbol: str, metadata: dict, retries: int = 0) -> pd.DataFrame | None:
    """Fetch OHLCV with exponential backoff on failure.

    Args:
        yf_symbol: Full symbol with exchange suffix (e.g., RELIANCE.NS)
        metadata: Cache metadata dict (will be updated in-place on success)
        retries: Current retry count (internal use)

    Returns:
        DataFrame with OHLCV data, or None on failure
    """
    if not HAS_YFINANCE:
        log("yfinance not installed")
        return None

    try:
        log(f"  Fetching {yf_symbol}...")
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1y")

        if df is not None and not df.empty:
            # Cache it (atomic write via temp file)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path = CACHE_DIR / f"{yf_symbol}.parquet"
            temp_path = cache_path.with_suffix(".parquet.tmp")
            df.to_parquet(temp_path)
            temp_path.replace(cache_path)

            # Update metadata in memory and on disk
            metadata[yf_symbol] = {
                "last_fetched": datetime.now().isoformat(),
                "rows": len(df)
            }
            save_json(CACHE_METADATA_PATH, metadata)

            return df

        log(f"  No data for {yf_symbol}")
        return None

    except Exception as e:
        if retries < MAX_RETRIES:
            # Exponential backoff: 2s, 4s, 8s
            wait = BASE_WAIT_SECONDS * (2 ** retries)
            log(f"  Retry {yf_symbol} in {wait}s... ({e})")
            time.sleep(wait)
            return fetch_with_backoff(yf_symbol, metadata, retries + 1)
        else:
            log(f"  Failed to fetch {yf_symbol} after {MAX_RETRIES} retries")
            return None


def compute_full_analysis(df: pd.DataFrame) -> dict:
    """Compute all technical indicators.

    Uses safe_float() to handle NaN values gracefully.
    """
    result = {}

    # Current price
    result["price"] = safe_float(df['Close'].iloc[-1], 0)
    if len(df) > 1 and result["price"] > 0:
        prev_close = safe_float(df['Close'].iloc[-2], result["price"])
        result["price_change_1d"] = ((result["price"] / prev_close) - 1) * 100 if prev_close > 0 else 0
    else:
        result["price_change_1d"] = 0

    # RSI
    if HAS_PANDAS_TA:
        rsi = ta.rsi(df['Close'], length=14)
        result["rsi"] = safe_float(rsi.iloc[-1] if rsi is not None else None, 50.0)
    else:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        result["rsi"] = safe_float(rsi.iloc[-1], 50.0)

    # RSI interpretation
    if result["rsi"] < 30:
        result["rsi_signal"] = "OVERSOLD"
    elif result["rsi"] < 40:
        result["rsi_signal"] = "Pullback"
    elif result["rsi"] > 70:
        result["rsi_signal"] = "OVERBOUGHT"
    else:
        result["rsi_signal"] = "Neutral"

    # MACD
    if HAS_PANDAS_TA:
        macd_df = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd_df is not None:
            # Use column name filter for robustness
            macd_cols = macd_df.filter(like="MACD_12_26_9").columns
            signal_cols = macd_df.filter(like="MACDs_12_26_9").columns
            result["macd"] = safe_float(macd_df[macd_cols[0]].iloc[-1] if len(macd_cols) > 0 else None, 0)
            result["macd_signal"] = safe_float(macd_df[signal_cols[0]].iloc[-1] if len(signal_cols) > 0 else None, 0)
        else:
            result["macd"] = 0
            result["macd_signal"] = 0
    else:
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        result["macd"] = safe_float(macd.iloc[-1], 0)
        result["macd_signal"] = safe_float(signal.iloc[-1], 0)

    result["macd_bullish"] = result["macd"] > result["macd_signal"]

    # SMAs
    result["sma50"] = safe_float(df['Close'].rolling(50).mean().iloc[-1]) if len(df) >= 50 else None
    result["sma200"] = safe_float(df['Close'].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

    # Trend - use explicit None checks (NaN is truthy!)
    if result["sma50"] is not None and result["sma200"] is not None:
        if result["price"] > result["sma50"] > result["sma200"]:
            result["trend"] = "STRONG UP"
        elif result["price"] > result["sma200"]:
            result["trend"] = "UP"
        elif result["price"] < result["sma50"] < result["sma200"]:
            result["trend"] = "STRONG DOWN"
        else:
            result["trend"] = "DOWN"

        result["golden_cross"] = result["sma50"] > result["sma200"]
    elif result["sma50"] is not None:
        # Have SMA50 but not SMA200
        result["trend"] = "UP" if result["price"] > result["sma50"] else "DOWN"
        result["golden_cross"] = None
    else:
        result["trend"] = "N/A (insufficient data)"
        result["golden_cross"] = None

    # ADX
    if HAS_PANDAS_TA:
        adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx_df is not None:
            # Use column name filter for robustness
            adx_cols = adx_df.filter(like="ADX_14").columns
            result["adx"] = safe_float(adx_df[adx_cols[0]].iloc[-1] if len(adx_cols) > 0 else None)
        else:
            result["adx"] = None
    else:
        # ADX requires complex calculation; set to None if pandas_ta not available
        result["adx"] = None

    # ADX interpretation (only if available)
    if result["adx"] is not None:
        if result["adx"] > 25:
            result["adx_signal"] = "Strong trend"
        elif result["adx"] > 20:
            result["adx_signal"] = "Trending"
        else:
            result["adx_signal"] = "Weak/No trend"
    else:
        result["adx_signal"] = "N/A"

    # Volume
    vol_avg = safe_float(df['Volume'].rolling(20).mean().iloc[-1])
    vol_today = safe_float(df['Volume'].iloc[-1])
    if vol_avg and vol_avg > 0 and vol_today is not None:
        result["volume_ratio"] = vol_today / vol_avg
    else:
        result["volume_ratio"] = 1.0
    result["volume_signal"] = "HIGH" if result["volume_ratio"] > 1.5 else "Normal"

    # 52-week high/low
    result["high_52w"] = safe_float(df['High'].max(), result["price"])
    result["low_52w"] = safe_float(df['Low'].min(), result["price"])
    if result["high_52w"] and result["high_52w"] > 0:
        result["pct_from_high"] = (result["high_52w"] - result["price"]) / result["high_52w"] * 100
    else:
        result["pct_from_high"] = 0
    if result["low_52w"] and result["low_52w"] > 0:
        result["pct_from_low"] = (result["price"] - result["low_52w"]) / result["low_52w"] * 100
    else:
        result["pct_from_low"] = 0

    # Bollinger Bands
    if HAS_PANDAS_TA:
        bb = ta.bbands(df['Close'], length=20, std=2)
        if bb is not None:
            # Use column name filter for robustness (BBU = upper, BBL = lower)
            upper_cols = bb.filter(like="BBU_").columns
            lower_cols = bb.filter(like="BBL_").columns
            result["bb_upper"] = safe_float(
                bb[upper_cols[0]].iloc[-1] if len(upper_cols) > 0 else None,
                result["price"]
            )
            result["bb_lower"] = safe_float(
                bb[lower_cols[0]].iloc[-1] if len(lower_cols) > 0 else None,
                result["price"]
            )
        else:
            result["bb_upper"] = result["price"]
            result["bb_lower"] = result["price"]
    else:
        sma20 = df['Close'].rolling(20).mean()
        std20 = df['Close'].rolling(20).std()
        result["bb_upper"] = safe_float((sma20 + 2 * std20).iloc[-1], result["price"])
        result["bb_lower"] = safe_float((sma20 - 2 * std20).iloc[-1], result["price"])

    if result["price"] <= result["bb_lower"]:
        result["bb_signal"] = "At lower band"
    elif result["price"] >= result["bb_upper"]:
        result["bb_signal"] = "At upper band"
    else:
        result["bb_signal"] = "Mid-band"

    # Overall technical score (simplified)
    score = 5.0  # Base score

    # RSI contribution (always available with fallback)
    if 30 < result["rsi"] < 45:
        score += 1.0  # Pullback zone
    elif result["rsi"] < 30:
        score += 0.5  # Oversold (risky)
    elif result["rsi"] > 70:
        score -= 0.5  # Overbought

    # MACD contribution
    if result["macd_bullish"]:
        score += 1.0

    # Trend contribution
    if result["trend"] == "STRONG UP":
        score += 2.0
    elif result["trend"] == "UP":
        score += 1.0
    elif result["trend"] == "DOWN":
        score -= 1.0
    elif result["trend"] == "STRONG DOWN":
        score -= 2.0

    # ADX contribution (only if available)
    if result["adx"] is not None and result["adx"] > 25:
        score += 0.5

    # Volume contribution
    if result["volume_ratio"] > 1.5:
        score += 0.5

    result["technical_score"] = max(1, min(10, score))

    # Recommendation using centralized thresholds
    if result["technical_score"] >= THRESHOLDS["strong_buy"]:
        result["recommendation"] = "STRONG BUY"
    elif result["technical_score"] >= THRESHOLDS["buy"]:
        result["recommendation"] = "BUY"
    elif result["technical_score"] >= THRESHOLDS["hold"]:
        result["recommendation"] = "HOLD"
    elif result["technical_score"] >= THRESHOLDS["sell"]:
        result["recommendation"] = "SELL"
    else:
        result["recommendation"] = "STRONG SELL"

    return result


def analyze_batch(symbols: list[str]) -> list[dict]:
    """Analyze stocks in batches with rate limiting.

    Args:
        symbols: List of stock symbols (with or without .NS/.BO suffix)

    Returns:
        List of analysis results
    """
    if not HAS_YFINANCE:
        print("Error: yfinance not installed")
        return []

    metadata = load_json(CACHE_METADATA_PATH) or {}
    results = []

    # Normalize all symbols upfront (preserves .BO if provided)
    normalized = [normalize_symbol(s) for s in symbols]
    total = len(normalized)
    print(f"\nAnalyzing {total} stocks...\n")

    for i in range(0, len(normalized), BATCH_SIZE):
        batch = normalized[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(normalized) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"Batch {batch_num}/{total_batches}: {', '.join(display_symbol(s) for s in batch)}")

        for yf_symbol in batch:
            disp_symbol = display_symbol(yf_symbol)

            # Check cache first
            if is_cache_fresh(yf_symbol, metadata):
                log(f"  {disp_symbol}: Using cached data")
                ohlcv = load_cached_ohlcv(yf_symbol)
            else:
                ohlcv = fetch_with_backoff(yf_symbol, metadata)

            if ohlcv is None or ohlcv.empty:
                print(f"  {disp_symbol}: ERROR - Could not fetch data")
                continue

            # Run full analysis
            analysis = compute_full_analysis(ohlcv)
            analysis["symbol"] = disp_symbol
            analysis["yf_symbol"] = yf_symbol

            # Save to scan_technical folder (separate from portfolio analysis)
            SCAN_TECHNICAL_DIR.mkdir(parents=True, exist_ok=True)
            save_json(SCAN_TECHNICAL_DIR / f"{yf_symbol}.json", analysis)

            results.append(analysis)

            # Print summary
            rec = analysis["recommendation"]
            score = analysis["technical_score"]
            rsi = analysis["rsi"]
            trend = analysis["trend"]
            macd = "↑" if analysis["macd_bullish"] else "↓"

            print(f"  {disp_symbol}: Score {score:.1f} | {rec} | RSI {rsi:.0f} | MACD {macd} | {trend}")

        # Delay between batches
        if i + BATCH_SIZE < len(normalized):
            print(f"\n  Waiting {DELAY_BETWEEN_BATCH}s before next batch...\n")
            time.sleep(DELAY_BETWEEN_BATCH)

    # Summary table
    print(f"\n{'='*80}")
    print(f"{'Symbol':<12} {'Score':<7} {'Rec':<12} {'RSI':<8} {'MACD':<8} {'Trend':<12} {'52W':<10}")
    print(f"{'='*80}")

    for r in sorted(results, key=lambda x: x["technical_score"], reverse=True):
        symbol = r["symbol"]
        score = r["technical_score"]
        rec = r["recommendation"]
        rsi = r["rsi"]
        macd = "Bullish" if r["macd_bullish"] else "Bearish"
        trend = r["trend"]
        pct_high = f"{r['pct_from_high']:.1f}% off"

        print(f"{symbol:<12} {score:<7.1f} {rec:<12} {rsi:<8.1f} {macd:<8} {trend:<12} {pct_high:<10}")

    print(f"{'='*80}\n")

    # Group by recommendation
    strong_buys = [r for r in results if r["recommendation"] == "STRONG BUY"]
    buys = [r for r in results if r["recommendation"] == "BUY"]
    holds = [r for r in results if r["recommendation"] == "HOLD"]

    if strong_buys:
        print(f"STRONG BUY: {', '.join(r['symbol'] for r in strong_buys)}")
    if buys:
        print(f"BUY: {', '.join(r['symbol'] for r in buys)}")
    if holds:
        print(f"HOLD: {', '.join(r['symbol'] for r in holds)}")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: verify_scan.py SYMBOL1 SYMBOL2 SYMBOL3 ...")
        print("")
        print("Runs FULL technical analysis on each stock:")
        print("  - RSI, MACD, SMA50/200, Bollinger, ADX, Volume")
        print("  - Computes technical score (1-10)")
        print("  - Gives recommendation (STRONG BUY/BUY/HOLD/SELL)")
        print("")
        print("Examples:")
        print("  verify_scan.py VPRPL IREDA RVNL")
        print("  verify_scan.py RELIANCE TCS INFY HDFCBANK")
        print("  verify_scan.py RELIANCE.BO  # BSE stock")
        sys.exit(1)

    # Parse symbols - pass as-is, analyze_batch handles normalization
    symbols = sys.argv[1:]

    if not symbols:
        print("Error: No symbols provided")
        sys.exit(1)

    # Run analysis
    results = analyze_batch(symbols)

    # Return strong buys for easy copy
    strong_buys = [r["symbol"] for r in results if r["recommendation"] in ("STRONG BUY", "BUY")]
    if strong_buys:
        print(f"\nReady for watchlist: {' '.join(strong_buys)}")


if __name__ == "__main__":
    main()
