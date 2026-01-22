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
from utils.config import (
    THRESHOLDS,
    GATES,
    get_component_weights,
    get_recommendation,
)


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
    trend_score: float | None,
    macd_score: float | None,
    adx_score: float | None,
    volume_score: float | None,
    technical_score: float | None,
    news_score: float | None,
) -> tuple[str, list[str]]:
    """
    Apply hard gating rules to recommendation.

    Returns: (adjusted_recommendation, list_of_gate_flags)

    Note: None values are treated as neutral (5) for gating purposes.
    """
    flags = []

    # Use neutral defaults for None values in gate comparisons
    trend = trend_score if trend_score is not None else 5
    macd = macd_score if macd_score is not None else 5
    adx = adx_score if adx_score is not None else 5
    volume = volume_score if volume_score is not None else 5
    tech = technical_score if technical_score is not None else 5
    news = news_score if news_score is not None else 5

    # Gate 1: Trend gate - no BUY without trend confirmation
    if trend < GATES["trend_min_for_buy"] and recommendation in ["BUY", "STRONG BUY"]:
        recommendation = "HOLD"
        flags.append("weak_trend_gate")

    # Gate 2: Weak trend + volume gate
    if (adx <= GATES["adx_weak_threshold"] and
        volume < GATES["volume_min_for_weak_trend"] and
        recommendation in ["BUY", "STRONG BUY"]):
        recommendation = "HOLD"
        flags.append("trendless_no_volume_gate")

    # Gate 3: News override prevention
    if (news >= GATES["news_hype_threshold"] and
        tech < GATES["tech_min_for_news_buy"] and
        recommendation == "BUY"):
        recommendation = "HOLD"
        flags.append("sentiment_without_confirmation")

    # Gate 4: STRONG BUY alignment - requires trend + momentum + strength
    if recommendation == "STRONG BUY":
        if not (trend >= GATES["strong_buy_trend_min"] and
                macd >= GATES["strong_buy_macd_min"] and
                adx >= GATES["strong_buy_adx_min"]):
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


def score_stock(symbol: str, broker: str | None = None, profile: str | None = None) -> dict:
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

    def normalize_score(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    # Extract scores - treat None/non-numeric as missing data
    technical_score = normalize_score(technical.get("technical_score"))
    fundamental_score = normalize_score(fundamentals.get("fundamental_score"))
    news_score = normalize_score(news.get("news_sentiment_score"))
    legal_score = normalize_score(legal.get("legal_corporate_score"))

    # Track coverage - which components have real data
    coverage = {
        "technical": technical_score is not None,
        "fundamental": fundamental_score is not None,
        "news": news_score is not None,
        "legal": legal_score is not None,
    }
    coverage_count = sum(coverage.values())
    coverage_pct = round(coverage_count / 4 * 100)

    # Normalize missing scores to None for consistency
    technical_score = technical_score if coverage["technical"] else None
    fundamental_score = fundamental_score if coverage["fundamental"] else None
    news_score = news_score if coverage["news"] else None
    legal_score = legal_score if coverage["legal"] else None

    # Select scoring profile (weights only; gates remain global for now)
    weights = get_component_weights(profile)

    # Build weights dict for present components only (renormalization)
    active_weights = {}
    active_scores = {}

    if technical_score is not None:
        active_weights["technical"] = weights["technical"]
        active_scores["technical"] = technical_score
    if fundamental_score is not None:
        active_weights["fundamental"] = weights["fundamental"]
        active_scores["fundamental"] = fundamental_score
    if news_score is not None:
        active_weights["news_sentiment"] = weights["news_sentiment"]
        active_scores["news_sentiment"] = news_score
    if legal_score is not None:
        active_weights["legal_corporate"] = weights["legal_corporate"]
        active_scores["legal_corporate"] = legal_score

    # Renormalize weights to sum to 1.0
    total_weight = sum(active_weights.values())
    if total_weight > 0:
        normalized_weights = {k: v / total_weight for k, v in active_weights.items()}
    else:
        # No data at all - default to neutral
        normalized_weights = {}

    # Extract individual technical indicator scores
    tech_scores = technical.get("scores", {})
    trend_score = tech_scores.get("trend", 5)
    macd_score = tech_scores.get("macd", 5)
    adx_score = tech_scores.get("adx", 5)
    volume_score = tech_scores.get("volume", 5)

    # For display/output, use None (shown as "NA") for missing scores
    technical_score_display = technical_score
    fundamental_score_display = fundamental_score
    news_score_display = news_score
    legal_score_display = legal_score

    # Apply influence caps when technicals are weak (only on present components)
    if technical_score is not None and fundamental_score is not None:
        capped_fundamental, _, _ = apply_influence_caps(
            technical_score, fundamental_score, news_score or 5, legal_score or 5
        )
        active_scores["fundamental"] = capped_fundamental
    if technical_score is not None and news_score is not None:
        _, capped_news, _ = apply_influence_caps(
            technical_score, fundamental_score or 5, news_score, legal_score or 5
        )
        active_scores["news_sentiment"] = capped_news

    # Calculate weighted score using only present components with renormalized weights
    if normalized_weights:
        overall_score = sum(
            active_scores[k] * normalized_weights[k]
            for k in normalized_weights
        )
    else:
        # No components available - assign neutral score
        overall_score = 5.0

    # Check for severe red flags
    has_red_flag = legal.get("has_severe_red_flag", False)
    red_flags = legal.get("red_flags", [])

    if has_red_flag:
        overall_score = min(overall_score, 5.0)

    overall_score = round(overall_score, 1)

    # Skip recommendations when data is incomplete
    if coverage_count < 4:
        recommendation = "INSUFFICIENT DATA"
        gate_flags = ["missing_data"]
        confidence = "N/A"
    else:
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

    # Build coverage string for visibility
    coverage_parts = []
    if coverage["technical"]:
        coverage_parts.append("T")
    if coverage["fundamental"]:
        coverage_parts.append("F")
    if coverage["news"]:
        coverage_parts.append("N")
    if coverage["legal"]:
        coverage_parts.append("L")
    coverage_str = "".join(coverage_parts) if coverage_parts else "none"

    result = {
        "symbol": symbol_clean,
        "symbol_yf": symbol_yf,
        "broker": holding_broker or "unknown",
        "scoring_profile": (profile or "default"),
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
        "technical_score": technical_score_display,
        "fundamental_score": fundamental_score_display,
        "news_sentiment_score": news_score_display,
        "legal_corporate_score": legal_score_display,
        "overall_score": overall_score,
        "recommendation": recommendation,
        "confidence": confidence,
        "coverage": coverage_str,
        "coverage_pct": coverage_pct,
        "gate_flags": ", ".join(gate_flags) if gate_flags else "",
        "red_flags": ", ".join(red_flags) if red_flags else "",
        "summary": summary,
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/score_stock.py <symbol> [--broker <broker>] [--profile <profile>]", file=sys.stderr)
        sys.exit(1)

    symbol = sys.argv[1]
    broker = None
    profile = None

    # Parse --broker argument
    if "--broker" in sys.argv:
        idx = sys.argv.index("--broker")
        if idx + 1 < len(sys.argv):
            broker = sys.argv[idx + 1]

    try:
        if "--profile" in sys.argv:
            idx = sys.argv.index("--profile")
            if idx + 1 < len(sys.argv):
                profile = sys.argv[idx + 1]

        result = score_stock(symbol, broker, profile)

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
