#!/usr/bin/env python3
"""
Deep Technical Analysis Script - Comprehensive technical analysis with trading levels.

Usage:
    uv run python scripts/deep_technical_analysis.py <symbol>

Features:
    - RSI (14) with overbought/oversold levels
    - MACD (12,26,9) with signal line crossovers
    - SMA 20, 50, 200 and golden/death cross detection
    - Bollinger Bands (20,2) with position analysis
    - ADX (14) for trend strength
    - Volume analysis with spike detection
    - Support/Resistance levels from price action
    - Fibonacci retracement levels
    - Specific entry, stop-loss, and target prices
    - Risk/Reward ratio calculations
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


def find_swing_points(df: pd.DataFrame, window: int = 10) -> tuple[list, list]:
    """Find swing highs and swing lows in price data."""
    highs = []
    lows = []

    for i in range(window, len(df) - window):
        # Check for swing high
        if df['High'].iloc[i] == df['High'].iloc[i-window:i+window+1].max():
            highs.append((df.index[i], df['High'].iloc[i]))

        # Check for swing low
        if df['Low'].iloc[i] == df['Low'].iloc[i-window:i+window+1].min():
            lows.append((df.index[i], df['Low'].iloc[i]))

    return highs, lows


def find_support_resistance(df: pd.DataFrame, num_levels: int = 5) -> dict:
    """
    Find support and resistance levels using multiple methods:
    1. Recent swing highs/lows
    2. Volume-weighted price levels
    3. Round number levels
    """
    highs, lows = find_swing_points(df, window=5)

    # Get recent swing points (last 60 days)
    recent_highs = [h[1] for h in highs[-20:]] if highs else []
    recent_lows = [l[1] for l in lows[-20:]] if lows else []

    current_price = df['Close'].iloc[-1]

    # Cluster nearby levels
    def cluster_levels(levels, threshold_pct=0.02):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for level in levels[1:]:
            if (level - clusters[-1][0]) / clusters[-1][0] < threshold_pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        return [np.mean(c) for c in clusters]

    # Find resistance levels (above current price)
    resistance_candidates = [h for h in recent_highs if h > current_price * 1.01]
    resistance_levels = cluster_levels(resistance_candidates)[:num_levels]

    # Find support levels (below current price)
    support_candidates = [l for l in recent_lows if l < current_price * 0.99]
    support_levels = sorted(cluster_levels(support_candidates), reverse=True)[:num_levels]

    # Add SMA levels as dynamic support/resistance
    sma50 = df['Close'].rolling(50).mean().iloc[-1]
    sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else None

    return {
        "resistance": [round(r, 2) for r in resistance_levels],
        "support": [round(s, 2) for s in support_levels],
        "sma50_level": round(sma50, 2),
        "sma200_level": round(sma200, 2) if sma200 else None,
    }


def calculate_fibonacci_levels(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Calculate Fibonacci retracement levels from recent swing high/low.
    """
    recent_df = df.tail(lookback)
    swing_high = recent_df['High'].max()
    swing_low = recent_df['Low'].min()

    swing_high_date = recent_df['High'].idxmax()
    swing_low_date = recent_df['Low'].idxmin()

    # Determine trend direction (is high before or after low?)
    is_uptrend = swing_low_date < swing_high_date

    diff = swing_high - swing_low

    fib_levels = {
        "0.0": round(swing_low if is_uptrend else swing_high, 2),
        "0.236": round(swing_low + diff * 0.236, 2) if is_uptrend else round(swing_high - diff * 0.236, 2),
        "0.382": round(swing_low + diff * 0.382, 2) if is_uptrend else round(swing_high - diff * 0.382, 2),
        "0.5": round(swing_low + diff * 0.5, 2) if is_uptrend else round(swing_high - diff * 0.5, 2),
        "0.618": round(swing_low + diff * 0.618, 2) if is_uptrend else round(swing_high - diff * 0.618, 2),
        "0.786": round(swing_low + diff * 0.786, 2) if is_uptrend else round(swing_high - diff * 0.786, 2),
        "1.0": round(swing_high if is_uptrend else swing_low, 2),
    }

    # Extension levels
    extensions = {
        "1.272": round(swing_low + diff * 1.272, 2) if is_uptrend else round(swing_high - diff * 1.272, 2),
        "1.618": round(swing_low + diff * 1.618, 2) if is_uptrend else round(swing_high - diff * 1.618, 2),
    }

    return {
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "swing_high_date": str(swing_high_date.date()) if hasattr(swing_high_date, 'date') else str(swing_high_date),
        "swing_low_date": str(swing_low_date.date()) if hasattr(swing_low_date, 'date') else str(swing_low_date),
        "trend_direction": "uptrend" if is_uptrend else "downtrend",
        "retracement_levels": fib_levels,
        "extension_levels": extensions,
    }


def analyze_volume(df: pd.DataFrame) -> dict:
    """Comprehensive volume analysis."""
    df = df.copy()
    df['volume_sma20'] = df['Volume'].rolling(20).mean()
    df['volume_sma50'] = df['Volume'].rolling(50).mean()
    df['volume_ratio'] = df['Volume'] / df['volume_sma20']

    latest = df.iloc[-1]

    # Find volume spikes (> 2x average)
    recent_df = df.tail(20)
    volume_spikes = []
    for idx, row in recent_df.iterrows():
        if row['volume_ratio'] > 2.0:
            volume_spikes.append({
                "date": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                "volume_ratio": round(row['volume_ratio'], 2),
                "price_change_pct": round((row['Close'] - row['Open']) / row['Open'] * 100, 2),
            })

    # Volume trend (is volume increasing or decreasing?)
    vol_5d = df['Volume'].tail(5).mean()
    vol_20d = df['Volume'].tail(20).mean()
    volume_trend = "increasing" if vol_5d > vol_20d * 1.1 else "decreasing" if vol_5d < vol_20d * 0.9 else "stable"

    return {
        "current_volume": int(latest['Volume']),
        "avg_volume_20d": int(df['volume_sma20'].iloc[-1]),
        "avg_volume_50d": int(df['volume_sma50'].iloc[-1]) if not pd.isna(df['volume_sma50'].iloc[-1]) else None,
        "volume_ratio": round(latest['volume_ratio'], 2),
        "volume_trend": volume_trend,
        "recent_spikes": volume_spikes[-5:],  # Last 5 spikes
    }


def detect_crossovers(df: pd.DataFrame) -> dict:
    """Detect golden cross, death cross, and MACD crossovers."""
    df = df.copy()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean() if len(df) >= 200 else None

    macd_result = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    if macd_result is not None:
        df['macd'] = macd_result.iloc[:, 0]
        df['macd_signal'] = macd_result.iloc[:, 2]

    crossovers = {
        "golden_cross": None,
        "death_cross": None,
        "macd_bullish_cross": None,
        "macd_bearish_cross": None,
    }

    # Check for SMA crossovers in last 60 days
    if df['sma200'] is not None and len(df) >= 200:
        recent = df.tail(60)
        for i in range(1, len(recent)):
            curr = recent.iloc[i]
            prev = recent.iloc[i-1]

            # Golden cross: SMA50 crosses above SMA200
            if prev['sma50'] <= prev['sma200'] and curr['sma50'] > curr['sma200']:
                crossovers["golden_cross"] = str(recent.index[i].date())

            # Death cross: SMA50 crosses below SMA200
            if prev['sma50'] >= prev['sma200'] and curr['sma50'] < curr['sma200']:
                crossovers["death_cross"] = str(recent.index[i].date())

    # Check for MACD crossovers in last 20 days
    if 'macd' in df.columns:
        recent = df.tail(20)
        for i in range(1, len(recent)):
            curr = recent.iloc[i]
            prev = recent.iloc[i-1]

            if pd.notna(curr['macd']) and pd.notna(prev['macd']):
                # MACD bullish crossover
                if prev['macd'] <= prev['macd_signal'] and curr['macd'] > curr['macd_signal']:
                    crossovers["macd_bullish_cross"] = str(recent.index[i].date())

                # MACD bearish crossover
                if prev['macd'] >= prev['macd_signal'] and curr['macd'] < curr['macd_signal']:
                    crossovers["macd_bearish_cross"] = str(recent.index[i].date())

    return crossovers


def generate_trading_levels(df: pd.DataFrame, indicators: dict, support_resistance: dict, fib_levels: dict) -> dict:
    """
    Generate specific entry, stop-loss, and target prices based on technical analysis.
    """
    current_price = df['Close'].iloc[-1]
    atr = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]

    # Determine trend
    sma50 = indicators.get('sma50')
    sma200 = indicators.get('sma200')
    rsi = indicators.get('rsi')
    adx = indicators.get('adx')

    is_uptrend = current_price > sma50 if sma50 else False
    is_strong_uptrend = is_uptrend and (sma50 > sma200 if sma200 else True)

    # Get support/resistance levels
    supports = support_resistance.get('support', [])
    resistances = support_resistance.get('resistance', [])

    # Determine entry strategy based on conditions
    entry_rationale = []
    stop_loss_rationale = []

    if is_strong_uptrend and rsi and 35 <= rsi <= 55:
        entry_strategy = "pullback_buy"
        entry_rationale.append("Strong uptrend with RSI in healthy zone (35-55)")
    elif is_strong_uptrend and adx and adx > 25:
        entry_strategy = "trend_continuation"
        entry_rationale.append(f"Strong trend (ADX={adx:.1f}), consider breakout entry")
    elif not is_uptrend and rsi and rsi < 30:
        entry_strategy = "oversold_bounce"
        entry_rationale.append(f"Oversold RSI ({rsi:.1f}), but wait for trend confirmation")
    else:
        entry_strategy = "wait_for_setup"
        entry_rationale.append("No clear entry setup, wait for better conditions")

    # Calculate entry levels
    entries = {}

    # Conservative entry: at nearest support
    if supports:
        entries["conservative"] = {
            "price": round(supports[0], 2),
            "rationale": f"Buy at first support level (${supports[0]:.2f})"
        }

    # Moderate entry: slightly below current if in pullback
    if is_uptrend:
        pullback_entry = current_price * 0.98  # 2% below current
        entries["moderate"] = {
            "price": round(pullback_entry, 2),
            "rationale": f"Buy on 2% pullback from current (${pullback_entry:.2f})"
        }

    # Aggressive entry: breakout above resistance
    if resistances:
        entries["aggressive"] = {
            "price": round(resistances[0] * 1.01, 2),
            "rationale": f"Buy on breakout above ${resistances[0]:.2f} resistance"
        }

    # Calculate stop-loss levels
    stop_losses = {}

    # ATR-based stop (2 ATR below entry)
    atr_stop = current_price - (2 * atr)
    stop_losses["atr_based"] = {
        "price": round(atr_stop, 2),
        "rationale": f"2x ATR (${atr:.2f}) below current price",
        "risk_pct": round((current_price - atr_stop) / current_price * 100, 2)
    }

    # Support-based stop
    if len(supports) >= 2:
        support_stop = supports[1] * 0.98  # Below second support
        stop_losses["support_based"] = {
            "price": round(support_stop, 2),
            "rationale": f"2% below second support level (${supports[1]:.2f})",
            "risk_pct": round((current_price - support_stop) / current_price * 100, 2)
        }
    elif supports:
        support_stop = supports[0] * 0.97  # 3% below first support
        stop_losses["support_based"] = {
            "price": round(support_stop, 2),
            "rationale": f"3% below support level (${supports[0]:.2f})",
            "risk_pct": round((current_price - support_stop) / current_price * 100, 2)
        }

    # Calculate target prices
    targets = {}

    # T1: First resistance or 10% gain
    if resistances:
        targets["T1"] = {
            "price": round(resistances[0], 2),
            "gain_pct": round((resistances[0] - current_price) / current_price * 100, 2),
            "rationale": f"First resistance level"
        }
    else:
        t1_price = current_price * 1.10
        targets["T1"] = {
            "price": round(t1_price, 2),
            "gain_pct": 10.0,
            "rationale": "10% gain target"
        }

    # T2: Second resistance or Fib extension 1.272
    if len(resistances) >= 2:
        targets["T2"] = {
            "price": round(resistances[1], 2),
            "gain_pct": round((resistances[1] - current_price) / current_price * 100, 2),
            "rationale": "Second resistance level"
        }
    else:
        fib_ext = fib_levels.get('extension_levels', {}).get('1.272')
        if fib_ext and fib_ext > current_price:
            targets["T2"] = {
                "price": fib_ext,
                "gain_pct": round((fib_ext - current_price) / current_price * 100, 2),
                "rationale": "Fibonacci 1.272 extension"
            }
        else:
            t2_price = current_price * 1.20
            targets["T2"] = {
                "price": round(t2_price, 2),
                "gain_pct": 20.0,
                "rationale": "20% gain target"
            }

    # T3: Fib extension 1.618 or 30% gain
    fib_ext_1618 = fib_levels.get('extension_levels', {}).get('1.618')
    if fib_ext_1618 and fib_ext_1618 > current_price:
        targets["T3"] = {
            "price": fib_ext_1618,
            "gain_pct": round((fib_ext_1618 - current_price) / current_price * 100, 2),
            "rationale": "Fibonacci 1.618 extension"
        }
    else:
        t3_price = current_price * 1.30
        targets["T3"] = {
            "price": round(t3_price, 2),
            "gain_pct": 30.0,
            "rationale": "30% gain target"
        }

    # Calculate Risk/Reward ratios
    risk_reward = {}
    best_stop = stop_losses.get('atr_based', stop_losses.get('support_based', {}))
    if best_stop:
        stop_price = best_stop['price']
        risk = current_price - stop_price

        for target_name, target_info in targets.items():
            reward = target_info['price'] - current_price
            if risk > 0:
                rr_ratio = reward / risk
                risk_reward[target_name] = {
                    "ratio": round(rr_ratio, 2),
                    "risk_amount": round(risk, 2),
                    "reward_amount": round(reward, 2),
                    "favorable": rr_ratio >= 2.0
                }

    return {
        "current_price": round(current_price, 2),
        "atr_14": round(atr, 2),
        "entry_strategy": entry_strategy,
        "entry_rationale": entry_rationale,
        "entry_levels": entries,
        "stop_loss_levels": stop_losses,
        "target_prices": targets,
        "risk_reward": risk_reward,
    }


def assess_trend(indicators: dict, crossovers: dict) -> dict:
    """Provide comprehensive trend assessment."""
    rsi = indicators.get('rsi')
    macd = indicators.get('macd')
    macd_signal = indicators.get('macd_signal')
    adx = indicators.get('adx')
    plus_di = indicators.get('plus_di')
    minus_di = indicators.get('minus_di')
    close = indicators.get('latest_close')
    sma50 = indicators.get('sma50')
    sma200 = indicators.get('sma200')
    bb_pctb = indicators.get('bollinger_pctb')

    assessments = []
    signals = []

    # Price vs SMAs
    if sma50 and sma200:
        if close > sma50 > sma200:
            assessments.append("Strong uptrend: Price > SMA50 > SMA200")
            signals.append(("bullish", "Price above both moving averages in bullish alignment"))
        elif close < sma50 < sma200:
            assessments.append("Strong downtrend: Price < SMA50 < SMA200")
            signals.append(("bearish", "Price below both moving averages in bearish alignment"))
        elif sma50 > sma200 and close < sma50:
            assessments.append("Pullback in uptrend: SMA50 > SMA200 but price below SMA50")
            signals.append(("neutral", "Pullback in overall uptrend - potential buying opportunity"))
        else:
            assessments.append("Mixed trend signals")
            signals.append(("neutral", "No clear trend direction"))
    elif sma50:
        if close > sma50:
            assessments.append("Short-term uptrend: Price > SMA50")
            signals.append(("bullish", "Price above 50-day moving average"))
        else:
            assessments.append("Short-term downtrend: Price < SMA50")
            signals.append(("bearish", "Price below 50-day moving average"))

    # RSI assessment
    if rsi:
        if rsi < 30:
            assessments.append(f"RSI oversold at {rsi:.1f}")
            signals.append(("oversold", f"RSI at {rsi:.1f} indicates oversold conditions"))
        elif rsi > 70:
            assessments.append(f"RSI overbought at {rsi:.1f}")
            signals.append(("overbought", f"RSI at {rsi:.1f} indicates overbought conditions"))
        elif 40 <= rsi <= 60:
            assessments.append(f"RSI neutral at {rsi:.1f}")
        elif rsi < 40:
            assessments.append(f"RSI weakening at {rsi:.1f}")
        else:
            assessments.append(f"RSI strong at {rsi:.1f}")

    # MACD assessment
    if macd is not None and macd_signal is not None:
        if macd > macd_signal and macd > 0:
            assessments.append("MACD bullish: Above signal and zero line")
            signals.append(("bullish", "MACD showing strong bullish momentum"))
        elif macd > macd_signal:
            assessments.append("MACD turning bullish: Above signal, below zero")
            signals.append(("neutral", "MACD improving but still below zero line"))
        elif macd < macd_signal and macd < 0:
            assessments.append("MACD bearish: Below signal and zero line")
            signals.append(("bearish", "MACD showing bearish momentum"))
        else:
            assessments.append("MACD turning bearish: Below signal, above zero")

    # ADX assessment
    if adx and plus_di and minus_di:
        if adx > 25 and plus_di > minus_di:
            assessments.append(f"Strong uptrend (ADX={adx:.1f}, +DI > -DI)")
            signals.append(("bullish", f"ADX at {adx:.1f} confirms strong uptrend"))
        elif adx > 25 and minus_di > plus_di:
            assessments.append(f"Strong downtrend (ADX={adx:.1f}, -DI > +DI)")
            signals.append(("bearish", f"ADX at {adx:.1f} confirms strong downtrend"))
        elif adx < 20:
            assessments.append(f"Weak/No trend (ADX={adx:.1f})")
            signals.append(("neutral", f"ADX at {adx:.1f} indicates no clear trend"))

    # Bollinger Band assessment
    if bb_pctb is not None:
        if bb_pctb < 0:
            assessments.append("Breaking below Bollinger Bands")
            signals.append(("bearish", "Price breaking below lower Bollinger Band"))
        elif bb_pctb > 1:
            assessments.append("Breaking above Bollinger Bands")
            signals.append(("bullish", "Price breaking above upper Bollinger Band - momentum breakout"))
        elif bb_pctb < 0.2:
            assessments.append("Near lower Bollinger Band")
        elif bb_pctb > 0.8:
            assessments.append("Near upper Bollinger Band")

    # Recent crossovers
    if crossovers.get('golden_cross'):
        signals.append(("bullish", f"Recent Golden Cross on {crossovers['golden_cross']}"))
    if crossovers.get('death_cross'):
        signals.append(("bearish", f"Recent Death Cross on {crossovers['death_cross']}"))
    if crossovers.get('macd_bullish_cross'):
        signals.append(("bullish", f"MACD bullish crossover on {crossovers['macd_bullish_cross']}"))
    if crossovers.get('macd_bearish_cross'):
        signals.append(("bearish", f"MACD bearish crossover on {crossovers['macd_bearish_cross']}"))

    # Overall trend score
    bullish_signals = len([s for s in signals if s[0] == 'bullish'])
    bearish_signals = len([s for s in signals if s[0] == 'bearish'])

    if bullish_signals > bearish_signals + 1:
        overall_trend = "BULLISH"
    elif bearish_signals > bullish_signals + 1:
        overall_trend = "BEARISH"
    else:
        overall_trend = "NEUTRAL"

    return {
        "overall_trend": overall_trend,
        "assessments": assessments,
        "signals": [{"type": s[0], "description": s[1]} for s in signals],
        "bullish_count": bullish_signals,
        "bearish_count": bearish_signals,
    }


def compute_deep_analysis(df: pd.DataFrame) -> dict:
    """Compute comprehensive technical analysis."""

    # Ensure enough data
    if len(df) < 50:
        raise ValueError(f"Not enough data: {len(df)} rows, need at least 50")

    df = df.copy()

    # Compute all technical indicators
    df['rsi'] = ta.rsi(df['Close'], length=14)

    # SMA 20, 50, 200
    df['sma20'] = ta.sma(df['Close'], length=20)
    df['sma50'] = ta.sma(df['Close'], length=50)
    if len(df) >= 200:
        df['sma200'] = ta.sma(df['Close'], length=200)

    # MACD
    macd_result = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    if macd_result is not None:
        df['macd'] = macd_result.iloc[:, 0]
        df['macd_histogram'] = macd_result.iloc[:, 1]
        df['macd_signal'] = macd_result.iloc[:, 2]

    # Bollinger Bands
    bbands = ta.bbands(df['Close'], length=20, std=2)
    if bbands is not None:
        df['bb_lower'] = bbands.iloc[:, 0]
        df['bb_middle'] = bbands.iloc[:, 1]
        df['bb_upper'] = bbands.iloc[:, 2]
        df['bb_pctb'] = bbands.iloc[:, 4]

    # ADX
    adx_result = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    if adx_result is not None:
        df['adx'] = adx_result.iloc[:, 0]
        df['plus_di'] = adx_result.iloc[:, 1]
        df['minus_di'] = adx_result.iloc[:, 2]

    # Get latest values
    latest = df.iloc[-1]

    def safe_float(val, decimals=4):
        if pd.isna(val):
            return None
        return round(float(val), decimals)

    indicators = {
        "latest_close": safe_float(latest['Close'], 2),
        "latest_high": safe_float(latest['High'], 2),
        "latest_low": safe_float(latest['Low'], 2),
        "latest_volume": int(latest['Volume']),
        "rsi": safe_float(latest.get('rsi')),
        "macd": safe_float(latest.get('macd')),
        "macd_signal": safe_float(latest.get('macd_signal')),
        "macd_histogram": safe_float(latest.get('macd_histogram')),
        "sma20": safe_float(latest.get('sma20'), 2),
        "sma50": safe_float(latest.get('sma50'), 2),
        "sma200": safe_float(latest.get('sma200'), 2) if 'sma200' in df.columns else None,
        "bollinger_upper": safe_float(latest.get('bb_upper'), 2),
        "bollinger_middle": safe_float(latest.get('bb_middle'), 2),
        "bollinger_lower": safe_float(latest.get('bb_lower'), 2),
        "bollinger_pctb": safe_float(latest.get('bb_pctb')),
        "adx": safe_float(latest.get('adx')),
        "plus_di": safe_float(latest.get('plus_di')),
        "minus_di": safe_float(latest.get('minus_di')),
    }

    # Additional analyses
    support_resistance = find_support_resistance(df)
    fib_levels = calculate_fibonacci_levels(df)
    volume_analysis = analyze_volume(df)
    crossovers = detect_crossovers(df)
    trend_assessment = assess_trend(indicators, crossovers)
    trading_levels = generate_trading_levels(df, indicators, support_resistance, fib_levels)

    return {
        "indicators": indicators,
        "support_resistance": support_resistance,
        "fibonacci": fib_levels,
        "volume_analysis": volume_analysis,
        "crossovers": crossovers,
        "trend_assessment": trend_assessment,
        "trading_levels": trading_levels,
        "data_points": len(df),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/deep_technical_analysis.py <symbol>", file=sys.stderr)
        sys.exit(1)

    symbol = sys.argv[1]
    print(f"Computing deep technical analysis for {symbol}...", file=sys.stderr)

    # Read OHLCV data
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

    # Compute analysis
    try:
        result = compute_deep_analysis(df)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build output
    output = {
        "symbol": symbol,
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_range": {
            "start": str(df.index.min().date()) if hasattr(df.index.min(), 'date') else str(df.index.min()),
            "end": str(df.index.max().date()) if hasattr(df.index.max(), 'date') else str(df.index.max()),
            "trading_days": len(df),
        },
        **result,
    }

    # Save to data/technical_deep/<symbol>.json (kept separate from scoring pipeline outputs)
    output_dir = base_path / "data" / "technical_deep"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{symbol}.json"

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, cls=NumpyEncoder)
    print(f"Saved analysis to {output_path}", file=sys.stderr)

    # Print JSON to stdout
    print(json.dumps(output, indent=2, cls=NumpyEncoder))


if __name__ == "__main__":
    main()
