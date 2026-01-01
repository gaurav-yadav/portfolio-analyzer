#!/usr/bin/env python3
"""
Stock Scorer Script - Aggregates all analysis scores and generates recommendation.

Usage:
    uv run python scripts/score_stock.py <symbol>

Output:
    Prints final scored JSON to stdout
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import load_json

# Scoring weights
WEIGHTS = {
    "technical": 0.35,
    "fundamental": 0.30,
    "news_sentiment": 0.20,
    "legal_corporate": 0.15,
}

# Recommendation thresholds
THRESHOLDS = {
    "strong_buy": 8.0,
    "buy": 6.5,
    "hold": 4.5,
    "sell": 3.0,
}


def get_recommendation(score: float) -> str:
    """Map score to recommendation."""
    if score >= THRESHOLDS["strong_buy"]:
        return "STRONG BUY"
    elif score >= THRESHOLDS["buy"]:
        return "BUY"
    elif score >= THRESHOLDS["hold"]:
        return "HOLD"
    elif score >= THRESHOLDS["sell"]:
        return "SELL"
    else:
        return "STRONG SELL"


def score_stock(symbol: str) -> dict:
    """
    Aggregate all analysis data and compute final score.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE.NS")

    Returns:
        Dictionary with final scores and recommendation
    """
    base_path = Path(__file__).parent.parent

    # Normalize symbol for file lookup
    symbol_clean = symbol.replace(".NS", "").replace(".BO", "")
    symbol_yf = symbol if "." in symbol else f"{symbol}.NS"

    # Load holdings data
    holdings = load_json(base_path / "data" / "holdings.json") or []
    holding = next((h for h in holdings if h["symbol"] == symbol_clean), None)

    # Load analysis data
    technical = load_json(base_path / "data" / "technical" / f"{symbol_yf}.json") or {}
    fundamentals = load_json(base_path / "data" / "fundamentals" / f"{symbol_yf}.json") or {}
    news = load_json(base_path / "data" / "news" / f"{symbol_yf}.json") or {}
    legal = load_json(base_path / "data" / "legal" / f"{symbol_yf}.json") or {}

    # Extract scores (default to 5 if missing)
    technical_score = technical.get("technical_score", 5)
    fundamental_score = fundamentals.get("fundamental_score", 5)
    news_score = news.get("news_sentiment_score", 5)
    legal_score = legal.get("legal_corporate_score", 5)

    # Calculate weighted score
    overall_score = (
        technical_score * WEIGHTS["technical"] +
        fundamental_score * WEIGHTS["fundamental"] +
        news_score * WEIGHTS["news_sentiment"] +
        legal_score * WEIGHTS["legal_corporate"]
    )

    # Check for severe red flags
    has_red_flag = legal.get("has_severe_red_flag", False)
    red_flags = legal.get("red_flags", [])

    if has_red_flag:
        overall_score = min(overall_score, 5.0)

    overall_score = round(overall_score, 1)
    recommendation = get_recommendation(overall_score)

    # Build summary
    summaries = []
    if technical.get("technical_summary"):
        summaries.append(technical["technical_summary"])
    elif technical:
        rsi = technical.get("rsi", "N/A")
        trend = "uptrend" if technical.get("trend_score", 5) >= 6 else "downtrend"
        summaries.append(f"Technical: {trend}, RSI at {rsi}")

    if fundamentals.get("fundamental_summary"):
        summaries.append(fundamentals["fundamental_summary"])

    if news.get("news_summary"):
        summaries.append(news["news_summary"])

    if legal.get("legal_summary"):
        summaries.append(legal["legal_summary"])

    summary = " ".join(summaries) if summaries else "Analysis data incomplete."

    # Get current price and calculate P&L
    current_price = technical.get("current_price", 0)
    avg_price = holding["avg_price"] if holding else 0
    quantity = holding["quantity"] if holding else 0
    name = holding["name"] if holding else symbol_clean

    pnl_pct = 0
    if avg_price and current_price:
        pnl_pct = round((current_price - avg_price) / avg_price * 100, 1)

    result = {
        "symbol": symbol_clean,
        "symbol_yf": symbol_yf,
        "name": name,
        "quantity": quantity,
        "avg_price": avg_price,
        "current_price": current_price,
        "pnl_pct": pnl_pct,
        "rsi": technical.get("rsi"),
        "rsi_score": technical.get("rsi_score"),
        "macd_score": technical.get("macd_score"),
        "trend_score": technical.get("trend_score"),
        "bollinger_score": technical.get("bollinger_score"),
        "adx_score": technical.get("adx_score"),
        "volume_score": technical.get("volume_score"),
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "news_sentiment_score": news_score,
        "legal_corporate_score": legal_score,
        "overall_score": overall_score,
        "recommendation": recommendation,
        "red_flags": ", ".join(red_flags) if red_flags else "",
        "summary": summary,
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/score_stock.py <symbol>", file=sys.stderr)
        sys.exit(1)

    symbol = sys.argv[1]

    try:
        result = score_stock(symbol)

        # Save to data/scores/<symbol>.json
        base_path = Path(__file__).parent.parent
        scores_dir = base_path / "data" / "scores"
        scores_dir.mkdir(parents=True, exist_ok=True)

        symbol_yf = result["symbol_yf"]
        output_file = scores_dir / f"{symbol_yf}.json"

        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        print(f"Saved: {output_file}")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error scoring {symbol}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
