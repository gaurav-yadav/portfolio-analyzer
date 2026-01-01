#!/usr/bin/env python3
"""
Stock Scorer Script - Aggregates all analysis scores and generates recommendation.

Usage:
    uv run python scripts/score_stock.py <symbol> [--broker <broker>]

Examples:
    uv run python scripts/score_stock.py RELIANCE.NS
    uv run python scripts/score_stock.py RELIANCE.NS --broker zerodha

Output:
    Saves score to data/scores/<symbol>@<broker>.json (or <symbol>.json if no broker specified)
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

# Gating thresholds for hardened recommendations
GATES = {
    "trend_min_for_buy": 5,        # Trend score must be >= 5 for BUY
    "adx_weak_threshold": 4,       # ADX <= 4 is weak trend
    "volume_min_for_weak_trend": 6,  # Volume must be >= 6 if ADX is weak
    "news_hype_threshold": 8,      # News >= 8 is potential hype
    "tech_min_for_news_buy": 5,    # Tech must be >= 5 to trust high news
    "strong_buy_trend_min": 7,     # STRONG BUY requires trend >= 7
    "strong_buy_macd_min": 6,      # STRONG BUY requires MACD >= 6
    "strong_buy_adx_min": 6,       # STRONG BUY requires ADX >= 6
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


def compute_confidence(scores: dict) -> str:
    """
    Compute confidence level based on signal agreement.

    Returns: "HIGH", "MEDIUM", or "LOW"

    Confidence drops when:
    - Key signals conflict (some bullish, some bearish)
    - MACD is strong but trend is weak (momentum without direction)
    - ADX shows no trend (< threshold)
    """
    trend = scores.get("trend", 5)
    macd = scores.get("macd", 5)
    adx = scores.get("adx", 5)

    # Count aligned signals (all bullish or all bearish)
    bullish = sum(1 for s in [trend, macd, adx] if s >= 6)
    bearish = sum(1 for s in [trend, macd, adx] if s <= 4)

    # Conflict detection: both bullish and bearish signals present
    has_conflict = (bullish > 0 and bearish > 0)

    if has_conflict:
        return "LOW"

    # MACD strong but trend weak = momentum without direction
    if macd >= 7 and trend < 5:
        return "LOW"

    # ADX shows no trend
    if adx < GATES["adx_weak_threshold"]:
        return "LOW"

    # High alignment: all three agree
    if bullish >= 3 or bearish >= 3:
        return "HIGH"

    return "MEDIUM"


def apply_influence_caps(
    technical_score: float,
    fundamental_score: float,
    news_score: float,
    legal_score: float,
) -> tuple[float, float, float]:
    """
    Cap non-technical influence when technicals are weak.

    Prevents fundamentals/news from pushing weak-technical stocks to BUY.
    Returns: (capped_fundamental, capped_news, capped_legal)
    """
    if technical_score < GATES["tech_min_for_news_buy"]:
        # Cap news at 6.0 to prevent hype-driven BUY
        news_score = min(news_score, 6.0)
        # Cap fundamentals at 7.0 to prevent value-trap BUY
        fundamental_score = min(fundamental_score, 7.0)

    return fundamental_score, news_score, legal_score


def apply_gates(
    recommendation: str,
    trend_score: float,
    macd_score: float,
    adx_score: float,
    volume_score: float,
    technical_score: float,
    news_score: float,
) -> tuple[str, list[str]]:
    """
    Apply hard gating rules to recommendation.

    Returns: (adjusted_recommendation, list_of_gate_flags)
    """
    flags = []

    # Gate 1: Trend gate - no BUY without trend confirmation
    if trend_score < GATES["trend_min_for_buy"] and recommendation in ["BUY", "STRONG BUY"]:
        recommendation = "HOLD"
        flags.append("weak_trend_gate")

    # Gate 2: Weak trend + volume gate
    if (adx_score <= GATES["adx_weak_threshold"] and
        volume_score < GATES["volume_min_for_weak_trend"] and
        recommendation in ["BUY", "STRONG BUY"]):
        recommendation = "HOLD"
        flags.append("trendless_no_volume_gate")

    # Gate 3: News override prevention
    if (news_score >= GATES["news_hype_threshold"] and
        technical_score < GATES["tech_min_for_news_buy"] and
        recommendation == "BUY"):
        recommendation = "HOLD"
        flags.append("sentiment_without_confirmation")

    # Gate 4: STRONG BUY alignment - requires trend + momentum + strength
    if recommendation == "STRONG BUY":
        if not (trend_score >= GATES["strong_buy_trend_min"] and
                macd_score >= GATES["strong_buy_macd_min"] and
                adx_score >= GATES["strong_buy_adx_min"]):
            recommendation = "BUY"
            flags.append("strong_buy_alignment_failed")

    return recommendation, flags


def get_rsi_description(rsi: float | None) -> str:
    """Get human-readable RSI description."""
    if rsi is None:
        return "RSI N/A"
    rsi = round(rsi, 1)
    if rsi >= 70:
        return f"RSI {rsi} (overbought)"
    elif rsi >= 60:
        return f"RSI {rsi} (bullish)"
    elif rsi >= 40:
        return f"RSI {rsi} (neutral)"
    elif rsi >= 30:
        return f"RSI {rsi} (bearish)"
    else:
        return f"RSI {rsi} (oversold)"


def get_trend_description(technical: dict) -> str:
    """Get trend direction from technical data."""
    indicators = technical.get("indicators", {})
    scores = technical.get("scores", {})

    trend_score = scores.get("trend", technical.get("trend_score", 5))
    sma50 = indicators.get("sma50")
    sma200 = indicators.get("sma200")
    latest_close = indicators.get("latest_close")

    # Determine trend based on score and SMA positions
    if trend_score >= 8:
        trend = "strong uptrend"
    elif trend_score >= 6:
        trend = "uptrend"
    elif trend_score >= 4:
        trend = "sideways"
    elif trend_score >= 2:
        trend = "downtrend"
    else:
        trend = "strong downtrend"

    # Add SMA context if available
    if sma50 and sma200 and latest_close:
        if sma50 > sma200 and latest_close > sma50:
            trend += ", above SMAs"
        elif sma50 < sma200 and latest_close < sma50:
            trend += ", below SMAs"

    return trend


def get_macd_description(technical: dict) -> str:
    """Get MACD signal description."""
    indicators = technical.get("indicators", {})
    macd_histogram = indicators.get("macd_histogram")

    if macd_histogram is None:
        return ""

    if macd_histogram > 0:
        return "MACD bullish"
    else:
        return "MACD bearish"


def get_fundamental_highlight(fundamentals: dict) -> str:
    """Extract key fundamental highlight."""
    if not fundamentals:
        return "fundamentals N/A"

    parts = []

    # PE ratio context
    pe = fundamentals.get("pe_ratio")
    pe_vs_sector = fundamentals.get("pe_vs_sector", "")
    if pe:
        parts.append(f"P/E {pe:.1f}" if pe_vs_sector != "above" else f"P/E {pe:.1f} (premium)")

    # Growth metrics
    profit_growth = fundamentals.get("profit_growth_yoy")
    revenue_growth = fundamentals.get("revenue_growth_yoy")
    if profit_growth is not None:
        if profit_growth >= 20:
            parts.append(f"profit +{profit_growth:.0f}% YoY (strong)")
        elif profit_growth >= 10:
            parts.append(f"profit +{profit_growth:.0f}% YoY")
        elif profit_growth >= 0:
            parts.append(f"profit +{profit_growth:.0f}% YoY (modest)")
        else:
            parts.append(f"profit {profit_growth:.0f}% YoY (declining)")

    # ROE
    roe = fundamentals.get("roe")
    if roe and roe >= 15:
        parts.append(f"ROE {roe:.1f}% (strong)")
    elif roe:
        parts.append(f"ROE {roe:.1f}%")

    # Debt
    de = fundamentals.get("debt_to_equity")
    if de is not None:
        if de < 0.1:
            parts.append("debt-free")
        elif de < 0.5:
            parts.append("low debt")
        elif de > 1.0:
            parts.append("high debt")

    return ", ".join(parts[:3]) if parts else "fundamentals N/A"


def get_news_sentiment_label(news: dict) -> str:
    """Get news sentiment label."""
    if not news:
        return "news N/A"

    sentiment = news.get("news_sentiment", "").lower()
    analyst_consensus = news.get("analyst_consensus", "").lower()
    target_vs_current = news.get("target_vs_current")

    parts = []

    # Overall sentiment
    if sentiment == "positive":
        parts.append("positive sentiment")
    elif sentiment == "negative":
        parts.append("negative sentiment")
    elif sentiment == "neutral":
        parts.append("neutral sentiment")
    else:
        parts.append("mixed sentiment")

    # Analyst consensus
    if analyst_consensus in ["strong_buy", "buy"]:
        parts.append("analysts bullish")
    elif analyst_consensus in ["strong_sell", "sell"]:
        parts.append("analysts bearish")

    # Target price upside
    if target_vs_current is not None:
        if target_vs_current >= 15:
            parts.append(f"+{target_vs_current:.0f}% target upside")
        elif target_vs_current >= 5:
            parts.append(f"+{target_vs_current:.0f}% upside")
        elif target_vs_current <= -10:
            parts.append(f"{target_vs_current:.0f}% downside")

    return ", ".join(parts[:2]) if parts else "news N/A"


def build_comprehensive_summary(technical: dict, fundamentals: dict, news: dict, legal: dict) -> str:
    """
    Build a comprehensive summary string with key metrics from all components.

    Format: "Technical: [trend/RSI]. Fundamentals: [key point]. News: [sentiment]. [Red flags if any]"
    """
    parts = []

    # Technical summary
    rsi = technical.get("indicators", {}).get("rsi") if technical.get("indicators") else technical.get("rsi")
    rsi_desc = get_rsi_description(rsi)
    trend_desc = get_trend_description(technical) if technical else "trend N/A"
    macd_desc = get_macd_description(technical) if technical else ""

    tech_parts = [trend_desc, rsi_desc]
    if macd_desc:
        tech_parts.append(macd_desc)
    parts.append(f"Technical: {', '.join(tech_parts)}.")

    # Fundamentals summary
    fund_highlight = get_fundamental_highlight(fundamentals)
    parts.append(f"Fundamentals: {fund_highlight}.")

    # News summary
    news_label = get_news_sentiment_label(news)
    parts.append(f"News: {news_label}.")

    # Red flags (if any)
    red_flags = legal.get("red_flags", []) if legal else []
    has_severe = legal.get("has_severe_red_flag", False) if legal else False

    if has_severe:
        parts.append("ALERT: Severe red flags detected.")
    elif red_flags:
        parts.append(f"Caution: {len(red_flags)} regulatory/legal issue(s) noted.")

    return " ".join(parts)


def score_stock(symbol: str, broker: str | None = None) -> dict:
    """
    Aggregate all analysis data and compute final score.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE.NS")
        broker: Optional broker name to filter holdings (e.g., "zerodha", "groww")

    Returns:
        Dictionary with final scores and recommendation
    """
    base_path = Path(__file__).parent.parent

    # Normalize symbol for file lookup
    symbol_clean = symbol.replace(".NS", "").replace(".BO", "")
    symbol_yf = symbol if "." in symbol else f"{symbol}.NS"

    # Load holdings data
    holdings = load_json(base_path / "data" / "holdings.json") or []

    # Find matching holding (optionally filter by broker)
    if broker:
        holding = next((h for h in holdings if h["symbol"] == symbol_clean and h.get("broker") == broker), None)
    else:
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

    # Extract individual technical indicator scores
    tech_scores = technical.get("scores", {})
    trend_score = tech_scores.get("trend", 5)
    macd_score = tech_scores.get("macd", 5)
    adx_score = tech_scores.get("adx", 5)
    volume_score = tech_scores.get("volume", 5)

    # Apply influence caps when technicals are weak
    capped_fundamental, capped_news, capped_legal = apply_influence_caps(
        technical_score, fundamental_score, news_score, legal_score
    )

    # Calculate weighted score with capped values
    overall_score = (
        technical_score * WEIGHTS["technical"] +
        capped_fundamental * WEIGHTS["fundamental"] +
        capped_news * WEIGHTS["news_sentiment"] +
        capped_legal * WEIGHTS["legal_corporate"]
    )

    # Check for severe red flags
    has_red_flag = legal.get("has_severe_red_flag", False)
    red_flags = legal.get("red_flags", [])

    if has_red_flag:
        overall_score = min(overall_score, 5.0)

    overall_score = round(overall_score, 1)
    recommendation = get_recommendation(overall_score)

    # Apply hard gating rules
    recommendation, gate_flags = apply_gates(
        recommendation,
        trend_score,
        macd_score,
        adx_score,
        volume_score,
        technical_score,
        news_score,
    )

    # Compute confidence level
    confidence = compute_confidence(tech_scores)

    # Build comprehensive summary using new format
    summary = build_comprehensive_summary(technical, fundamentals, news, legal)

    # Get current price and calculate P&L
    indicators = technical.get("indicators", {})
    current_price = indicators.get("latest_close") or technical.get("current_price", 0)
    avg_price = holding["avg_price"] if holding else 0
    quantity = holding["quantity"] if holding else 0
    name = holding["name"] if holding else symbol_clean

    pnl_pct = 0
    if avg_price and current_price:
        pnl_pct = round((current_price - avg_price) / avg_price * 100, 1)

    # Get broker from holding or parameter
    holding_broker = holding.get("broker") if holding else broker

    result = {
        "symbol": symbol_clean,
        "symbol_yf": symbol_yf,
        "broker": holding_broker or "unknown",
        "name": name,
        "quantity": quantity,
        "avg_price": avg_price,
        "current_price": current_price,
        "pnl_pct": pnl_pct,
        "rsi": indicators.get("rsi"),
        "rsi_score": tech_scores.get("rsi"),
        "macd_score": tech_scores.get("macd"),
        "trend_score": tech_scores.get("trend"),
        "bollinger_score": tech_scores.get("bollinger"),
        "adx_score": tech_scores.get("adx"),
        "volume_score": tech_scores.get("volume"),
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "news_sentiment_score": news_score,
        "legal_corporate_score": legal_score,
        "overall_score": overall_score,
        "recommendation": recommendation,
        "confidence": confidence,
        "gate_flags": ", ".join(gate_flags) if gate_flags else "",
        "red_flags": ", ".join(red_flags) if red_flags else "",
        "summary": summary,
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/score_stock.py <symbol> [--broker <broker>]", file=sys.stderr)
        sys.exit(1)

    symbol = sys.argv[1]
    broker = None

    # Parse --broker argument
    if "--broker" in sys.argv:
        idx = sys.argv.index("--broker")
        if idx + 1 < len(sys.argv):
            broker = sys.argv[idx + 1]

    try:
        result = score_stock(symbol, broker)

        # Save to data/scores/<symbol>@<broker>.json or <symbol>.json
        base_path = Path(__file__).parent.parent
        scores_dir = base_path / "data" / "scores"
        scores_dir.mkdir(parents=True, exist_ok=True)

        # Use broker in filename if available
        result_broker = result.get("broker", "unknown")
        if result_broker and result_broker != "unknown":
            output_file = scores_dir / f"{result['symbol']}@{result_broker}.json"
        else:
            output_file = scores_dir / f"{result['symbol_yf']}.json"

        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        print(f"Saved: {output_file}")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error scoring {symbol}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
