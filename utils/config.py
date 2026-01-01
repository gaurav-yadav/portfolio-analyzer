"""Centralized configuration for Portfolio Analyzer.

This module contains all thresholds, weights, and constants used across
the codebase. Import from here to avoid config drift.
"""

# =============================================================================
# SCORING WEIGHTS (Component-level)
# =============================================================================
COMPONENT_WEIGHTS = {
    "technical": 0.35,
    "fundamental": 0.30,
    "news_sentiment": 0.20,
    "legal_corporate": 0.15,
}

# =============================================================================
# RECOMMENDATION THRESHOLDS
# =============================================================================
THRESHOLDS = {
    "strong_buy": 8.0,
    "buy": 6.5,
    "hold": 4.5,
    "sell": 3.0,
}

# =============================================================================
# GATING THRESHOLDS (Safety constraints)
# =============================================================================
GATES = {
    "trend_min_for_buy": 5,           # Trend score must be >= 5 for BUY
    "adx_weak_threshold": 4,          # ADX <= 4 is weak trend
    "volume_min_for_weak_trend": 6,   # Volume must be >= 6 if ADX is weak
    "news_hype_threshold": 8,         # News >= 8 is potential hype
    "tech_min_for_news_buy": 5,       # Tech must be >= 5 to trust high news
    "strong_buy_trend_min": 7,        # STRONG BUY requires trend >= 7
    "strong_buy_macd_min": 6,         # STRONG BUY requires MACD >= 6
    "strong_buy_adx_min": 6,          # STRONG BUY requires ADX >= 6
}

# =============================================================================
# TECHNICAL INDICATOR DEFAULTS
# =============================================================================
DEFAULT_TECHNICAL_WEIGHTS = {
    "rsi": 1/6,
    "macd": 1/6,
    "trend": 1/6,
    "bollinger": 1/6,
    "adx": 1/6,
    "volume": 1/6,
}

# =============================================================================
# CACHE SETTINGS
# =============================================================================
CACHE_FRESHNESS_HOURS = 18


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_recommendation(score: float, thresholds: dict = None) -> str:
    """Map score to recommendation using provided or default thresholds."""
    if thresholds is None:
        thresholds = THRESHOLDS

    if score >= thresholds["strong_buy"]:
        return "STRONG BUY"
    elif score >= thresholds["buy"]:
        return "BUY"
    elif score >= thresholds["hold"]:
        return "HOLD"
    elif score >= thresholds["sell"]:
        return "SELL"
    else:
        return "STRONG SELL"


def get_portfolio_health_label(avg_score: float) -> str:
    """Get overall portfolio health assessment."""
    if avg_score >= 7.5:
        return "Excellent"
    elif avg_score >= 6.5:
        return "Good"
    elif avg_score >= 5.5:
        return "Fair"
    elif avg_score >= 4.5:
        return "Needs Attention"
    else:
        return "At Risk"
