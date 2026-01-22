#!/usr/bin/env python3
"""
Compute comprehensive technical indicators for stocks.

Usage: uv run python scripts/compute_technicals.py <symbol1> [symbol2] ...

Computes: RSI, MACD, SMA (20/50/200), Bollinger Bands, ADX, Volume analysis
Saves results to data/technicals/<symbol>.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta


BASE_PATH = Path(__file__).parent.parent
CACHE_DIR = BASE_PATH / "cache" / "ohlcv"
OUTPUT_DIR = BASE_PATH / "data" / "technicals"


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if pd.isna(obj):
            return None
        return super().default(obj)


def log(msg: str) -> None:
    """Print to stderr for logging."""
    print(msg, file=sys.stderr)


def safe_round(val, decimals: int = 4):
    """Safely round a value, handling NaN/None."""
    if val is None or pd.isna(val):
        return None
    return round(float(val), decimals)


def load_ohlcv(symbol: str) -> pd.DataFrame:
    """Load OHLCV data from parquet cache."""
    path = CACHE_DIR / f"{symbol}.parquet"

    if not path.exists() and not any(symbol.endswith(s) for s in ['.NS', '.BO']):
        path = CACHE_DIR / f"{symbol}.NS.parquet"

    if not path.exists():
        raise FileNotFoundError(f"OHLCV data not found: {path}")

    df = pd.read_parquet(path)

    if len(df) < 50:
        raise ValueError(f"Insufficient data: {len(df)} rows, need 50+")

    return df


def compute_rsi(df: pd.DataFrame, period: int = 14) -> dict:
    """Compute RSI indicator."""
    df = df.copy()
    df['rsi'] = ta.rsi(df['Close'], length=period)

    current = safe_round(df['rsi'].iloc[-1], 2)

    if current is None:
        signal = "no_data"
    elif current < 30:
        signal = "oversold"
    elif current > 70:
        signal = "overbought"
    elif current < 40:
        signal = "approaching_oversold"
    elif current > 60:
        signal = "approaching_overbought"
    else:
        signal = "neutral"

    return {
        "value": current,
        "period": period,
        "signal": signal,
        "thresholds": {"oversold": 30, "overbought": 70},
    }


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """Compute MACD indicator."""
    df = df.copy()

    macd_result = ta.macd(df['Close'], fast=fast, slow=slow, signal=signal)
    if macd_result is None:
        return {"error": "Could not compute MACD"}

    df['macd'] = macd_result.iloc[:, 0]
    df['macd_hist'] = macd_result.iloc[:, 1]
    df['macd_signal'] = macd_result.iloc[:, 2]

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    macd_val = safe_round(latest['macd'], 4)
    signal_val = safe_round(latest['macd_signal'], 4)
    histogram = safe_round(latest['macd_hist'], 4)

    above_signal = macd_val > signal_val if macd_val and signal_val else None
    above_zero = macd_val > 0 if macd_val else None
    hist_rising = histogram > safe_round(prev['macd_hist'], 4) if histogram else None

    # Check for recent crossover
    crossover = None
    recent = df.tail(10)
    for i in range(1, len(recent)):
        curr_row = recent.iloc[i]
        prev_row = recent.iloc[i-1]
        if prev_row['macd'] <= prev_row['macd_signal'] and curr_row['macd'] > curr_row['macd_signal']:
            crossover = "bullish"
        if prev_row['macd'] >= prev_row['macd_signal'] and curr_row['macd'] < curr_row['macd_signal']:
            crossover = "bearish"

    if above_signal and above_zero and hist_rising:
        signal_type = "strong_bullish"
    elif above_signal and hist_rising:
        signal_type = "bullish"
    elif above_signal:
        signal_type = "weak_bullish"
    elif not above_signal and not above_zero:
        signal_type = "bearish"
    else:
        signal_type = "neutral"

    return {
        "macd": macd_val,
        "signal_line": signal_val,
        "histogram": histogram,
        "params": {"fast": fast, "slow": slow, "signal": signal},
        "above_signal_line": above_signal,
        "above_zero_line": above_zero,
        "histogram_rising": hist_rising,
        "recent_crossover": crossover,
        "signal": signal_type,
    }


def compute_sma_stack(df: pd.DataFrame) -> dict:
    """Compute SMA 20/50/200 stack."""
    df = df.copy()

    df['sma20'] = ta.sma(df['Close'], length=20)
    df['sma50'] = ta.sma(df['Close'], length=50)
    if len(df) >= 200:
        df['sma200'] = ta.sma(df['Close'], length=200)

    latest = df.iloc[-1]
    price = safe_round(latest['Close'], 2)
    sma20 = safe_round(latest['sma20'], 2)
    sma50 = safe_round(latest['sma50'], 2)
    sma200 = safe_round(latest.get('sma200'), 2) if 'sma200' in df.columns else None

    # Stack alignment
    stack_type = "mixed"
    if sma20 and sma50:
        if sma200:
            if price > sma20 > sma50 > sma200:
                stack_type = "perfect_bullish"
            elif price < sma20 < sma50 < sma200:
                stack_type = "perfect_bearish"
            elif sma50 > sma200 and price > sma50:
                stack_type = "bullish"
            elif sma50 < sma200 and price < sma50:
                stack_type = "bearish"
            elif sma50 > sma200 and price < sma50:
                stack_type = "pullback_in_uptrend"
            elif sma50 < sma200 and price > sma50:
                stack_type = "rally_in_downtrend"
        else:
            if price > sma20 > sma50:
                stack_type = "bullish"
            elif price < sma20 < sma50:
                stack_type = "bearish"

    # Distance from MAs
    dist_sma20 = safe_round((price - sma20) / sma20 * 100, 2) if sma20 else None
    dist_sma50 = safe_round((price - sma50) / sma50 * 100, 2) if sma50 else None
    dist_sma200 = safe_round((price - sma200) / sma200 * 100, 2) if sma200 else None

    return {
        "price": price,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "stack_type": stack_type,
        "distance_from_sma20_pct": dist_sma20,
        "distance_from_sma50_pct": dist_sma50,
        "distance_from_sma200_pct": dist_sma200,
    }


def compute_bollinger(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> dict:
    """Compute Bollinger Bands."""
    df = df.copy()

    bbands = ta.bbands(df['Close'], length=length, std=std)
    if bbands is None:
        return {"error": "Could not compute Bollinger Bands"}

    df['bb_lower'] = bbands.iloc[:, 0]
    df['bb_middle'] = bbands.iloc[:, 1]
    df['bb_upper'] = bbands.iloc[:, 2]
    df['bb_bandwidth'] = bbands.iloc[:, 3]
    df['bb_pctb'] = bbands.iloc[:, 4]

    latest = df.iloc[-1]
    price = safe_round(latest['Close'], 2)
    upper = safe_round(latest['bb_upper'], 2)
    middle = safe_round(latest['bb_middle'], 2)
    lower = safe_round(latest['bb_lower'], 2)
    pctb = safe_round(latest['bb_pctb'], 4)
    bandwidth = safe_round(latest['bb_bandwidth'], 4)

    if pctb is None:
        signal = "no_data"
        position = "unknown"
    elif pctb > 1:
        signal = "overextended"
        position = "above_upper_band"
    elif pctb < 0:
        signal = "oversold"
        position = "below_lower_band"
    elif pctb > 0.8:
        signal = "approaching_upper"
        position = "upper_zone"
    elif pctb < 0.2:
        signal = "approaching_lower"
        position = "lower_zone"
    else:
        signal = "neutral"
        position = "middle_zone"

    # Bandwidth analysis
    avg_bandwidth = df['bb_bandwidth'].tail(20).mean()
    if bandwidth and avg_bandwidth:
        if bandwidth > avg_bandwidth * 1.1:
            volatility_state = "expanding"
        elif bandwidth < avg_bandwidth * 0.9:
            volatility_state = "contracting"
        else:
            volatility_state = "normal"
    else:
        volatility_state = "unknown"

    return {
        "price": price,
        "upper_band": upper,
        "middle_band": middle,
        "lower_band": lower,
        "percent_b": pctb,
        "bandwidth": bandwidth,
        "params": {"length": length, "std": std},
        "position": position,
        "volatility_state": volatility_state,
        "signal": signal,
    }


def compute_adx(df: pd.DataFrame, length: int = 14) -> dict:
    """Compute ADX indicator."""
    df = df.copy()

    adx_result = ta.adx(df['High'], df['Low'], df['Close'], length=length)
    if adx_result is None:
        return {"error": "Could not compute ADX"}

    df['adx'] = adx_result.iloc[:, 0]
    df['plus_di'] = adx_result.iloc[:, 1]
    df['minus_di'] = adx_result.iloc[:, 2]

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    adx = safe_round(latest['adx'], 2)
    plus_di = safe_round(latest['plus_di'], 2)
    minus_di = safe_round(latest['minus_di'], 2)
    prev_adx = safe_round(prev['adx'], 2)

    # Trend strength
    if adx is None:
        trend_strength = "unknown"
    elif adx > 40:
        trend_strength = "very_strong"
    elif adx > 25:
        trend_strength = "strong"
    elif adx > 20:
        trend_strength = "developing"
    else:
        trend_strength = "weak_or_ranging"

    # Direction
    if plus_di and minus_di:
        if plus_di > minus_di:
            direction = "bullish"
            di_spread = safe_round(plus_di - minus_di, 2)
        else:
            direction = "bearish"
            di_spread = safe_round(minus_di - plus_di, 2)
    else:
        direction = "unknown"
        di_spread = None

    adx_rising = adx > prev_adx if adx and prev_adx else None

    if trend_strength in ["strong", "very_strong"] and direction == "bullish":
        signal = "strong_uptrend"
    elif trend_strength in ["strong", "very_strong"] and direction == "bearish":
        signal = "strong_downtrend"
    elif trend_strength == "weak_or_ranging":
        signal = "no_clear_trend"
    elif trend_strength == "developing" and direction == "bullish" and adx_rising:
        signal = "uptrend_developing"
    else:
        signal = "mixed"

    return {
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "di_spread": di_spread,
        "period": length,
        "trend_strength": trend_strength,
        "direction": direction,
        "adx_rising": adx_rising,
        "signal": signal,
        "thresholds": {"strong": 25, "very_strong": 40, "weak": 20},
    }


def compute_volume(df: pd.DataFrame) -> dict:
    """Compute volume analysis."""
    df = df.copy()

    df['vol_sma20'] = ta.sma(df['Volume'], length=20)
    df['vol_sma50'] = ta.sma(df['Volume'], length=50)
    df['vol_ratio'] = df['Volume'] / df['vol_sma20']
    df['price_change'] = df['Close'].pct_change()

    latest = df.iloc[-1]

    volume = int(latest['Volume'])
    vol_sma20 = int(latest['vol_sma20']) if latest['vol_sma20'] else None
    vol_sma50 = int(latest['vol_sma50']) if latest['vol_sma50'] else None
    vol_ratio = safe_round(latest['vol_ratio'], 2)

    is_up_day = latest['Close'] >= latest['Open']
    price_change_pct = safe_round(latest['price_change'] * 100, 2)

    if vol_ratio and vol_ratio > 2.0:
        if is_up_day:
            signal = "strong_accumulation"
        else:
            signal = "strong_distribution"
    elif vol_ratio and vol_ratio > 1.5:
        if is_up_day:
            signal = "accumulation"
        else:
            signal = "distribution"
    elif vol_ratio and vol_ratio < 0.5:
        signal = "very_low_volume"
    else:
        signal = "normal"

    # Volume trend
    vol_5d = df['Volume'].tail(5).mean()
    if vol_5d and vol_sma20:
        if vol_5d > vol_sma20 * 1.2:
            vol_trend = "increasing"
        elif vol_5d < vol_sma20 * 0.8:
            vol_trend = "decreasing"
        else:
            vol_trend = "stable"
    else:
        vol_trend = "unknown"

    return {
        "volume": volume,
        "avg_volume_20d": vol_sma20,
        "avg_volume_50d": vol_sma50,
        "volume_ratio": vol_ratio,
        "is_up_day": is_up_day,
        "price_change_pct": price_change_pct,
        "volume_trend": vol_trend,
        "signal": signal,
    }


def determine_overall_signal(rsi: dict, macd: dict, sma: dict, bollinger: dict, adx: dict, volume: dict) -> str:
    """
    Determine overall technical signal based on all indicators.

    Returns: 'bullish', 'bearish', or 'neutral'
    """
    bullish_score = 0
    bearish_score = 0

    # RSI scoring
    rsi_signal = rsi.get("signal", "")
    if rsi_signal in ["oversold", "approaching_oversold"]:
        bullish_score += 1
    elif rsi_signal in ["overbought", "approaching_overbought"]:
        bearish_score += 1

    # MACD scoring
    macd_signal = macd.get("signal", "")
    if macd_signal in ["strong_bullish", "bullish"]:
        bullish_score += 2
    elif macd_signal == "weak_bullish":
        bullish_score += 1
    elif macd_signal == "bearish":
        bearish_score += 2

    # SMA stack scoring
    sma_stack = sma.get("stack_type", "")
    if sma_stack in ["perfect_bullish", "bullish"]:
        bullish_score += 2
    elif sma_stack == "pullback_in_uptrend":
        bullish_score += 1
    elif sma_stack in ["perfect_bearish", "bearish"]:
        bearish_score += 2
    elif sma_stack == "rally_in_downtrend":
        bearish_score += 1

    # Bollinger scoring
    bb_signal = bollinger.get("signal", "")
    if bb_signal in ["oversold", "approaching_lower"]:
        bullish_score += 1
    elif bb_signal in ["overextended", "approaching_upper"]:
        bearish_score += 1

    # ADX scoring
    adx_signal = adx.get("signal", "")
    if adx_signal in ["strong_uptrend", "uptrend_developing"]:
        bullish_score += 2
    elif adx_signal == "strong_downtrend":
        bearish_score += 2

    # Volume scoring
    vol_signal = volume.get("signal", "")
    if vol_signal in ["strong_accumulation", "accumulation"]:
        bullish_score += 1
    elif vol_signal in ["strong_distribution", "distribution"]:
        bearish_score += 1

    # Determine final signal
    if bullish_score >= bearish_score + 3:
        return "bullish"
    elif bearish_score >= bullish_score + 3:
        return "bearish"
    else:
        return "neutral"


def compute_all_indicators(symbol: str) -> dict:
    """Compute all technical indicators for a symbol."""
    log(f"Computing technicals for {symbol}...")

    df = load_ohlcv(symbol)

    rsi = compute_rsi(df)
    macd = compute_macd(df)
    sma = compute_sma_stack(df)
    bollinger = compute_bollinger(df)
    adx = compute_adx(df)
    volume = compute_volume(df)

    overall_signal = determine_overall_signal(rsi, macd, sma, bollinger, adx, volume)

    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "price": sma.get("price"),
        "technical_signal": overall_signal,
        "rsi": rsi,
        "macd": macd,
        "sma": sma,
        "bollinger": bollinger,
        "adx": adx,
        "volume": volume,
    }


def save_result(result: dict, symbol: str) -> Path:
    """Save result to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{symbol}.json"

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/compute_technicals.py <symbol1> [symbol2] ...", file=sys.stderr)
        sys.exit(1)

    symbols = [s.strip().upper() for s in sys.argv[1:]]

    results = []
    for symbol in symbols:
        try:
            result = compute_all_indicators(symbol)
            output_path = save_result(result, symbol)
            log(f"Saved {symbol} -> {output_path}")
            results.append(result)
        except (FileNotFoundError, ValueError) as e:
            log(f"Error processing {symbol}: {e}")
            continue

    # Print summary
    print(json.dumps({
        "processed": len(results),
        "symbols": [r["symbol"] for r in results],
        "output_dir": str(OUTPUT_DIR),
    }, indent=2))


if __name__ == "__main__":
    main()
