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
# SCORING PROFILES (Job-specific weight presets)
# =============================================================================
SCORING_PROFILES = {
    # Backward-compatible default (current pipeline behavior)
    "default": COMPONENT_WEIGHTS,
    # Watchlist/swing-trade oriented (1–8 weeks): technical-heavy, legal as gate
    "watchlist_swing": {
        "technical": 0.60,
        "fundamental": 0.20,
        "news_sentiment": 0.10,
        "legal_corporate": 0.10,
    },
    # Portfolio/long-term oriented: fundamentals + governance matter more
    "portfolio_long_term": {
        "technical": 0.25,
        "fundamental": 0.40,
        "news_sentiment": 0.15,
        "legal_corporate": 0.20,
    },
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


def get_component_weights(profile: str | None = None) -> dict:
    """
    Return component weights for a scoring profile.

    Profiles allow the same pipeline to be reused for different jobs
    (watchlist scanning vs long-term portfolio tracking).
    """
    key = (profile or "default").strip()
    if key in SCORING_PROFILES:
        return SCORING_PROFILES[key]
    valid = ", ".join(sorted(SCORING_PROFILES.keys()))
    raise ValueError(f"Unknown scoring profile: {key}. Choose one of: {valid}")


# =============================================================================
# SCAN SETUP RULES (Confluence scoring for scanner)
# =============================================================================
SCAN_SETUP_RULES = {
    # Lookback windows (trading days)
    "pivot_lookback": 90,           # Days to search for swing lows
    "pivot_window": 2,              # k=2 means 5-bar pivot (i-2 to i+2)
    "breakout_window": 20,          # Donchian channel period
    "tight_range_window": 10,       # Days for compression detection

    # Thresholds
    "near_support_pct": 3.0,        # Within 3% of support = "near support"
    "near_sma_pct": 3.0,            # Within 3% of SMA = "near SMA"
    "max_extension_above_sma20_pct": 8.0,  # Reject if >8% above SMA20
    "max_days_since_breakout": 5,   # Breakout must be within 5 days

    # RSI thresholds
    "rsi_ideal_min": 35,            # Ideal pullback zone lower
    "rsi_ideal_max": 55,            # Ideal pullback zone upper
    "rsi_overbought_max": 70,       # Above this = overbought penalty

    # Volume thresholds
    "min_volume_ratio_bounce": 1.2,      # For volume_on_bounce
    "breakout_min_volume_ratio": 1.5,    # For breakout confirmation
    "breakout_strong_volume_ratio": 2.0, # Strong volume bonus
    "min_bounce_volume_ratio": 1.3,      # For reversal bounce

    # Price change thresholds
    "min_bounce_change_pct": 1.0,   # Minimum 1% up for bounce confirmation

    # Tight range / compression
    "tight_range_max_pct": 8.0,     # Range < 8% of close = tight

    # Close near high (for breakout quality)
    "close_near_high_max_pct": 2.0, # Within 2% of day high

    # Pass thresholds
    "2m_pullback_min_score": 60,
    "2w_breakout_min_score": 65,
    "support_reversal_min_score": 60,
}


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


# =============================================================================
# PORTFOLIO WATCHER (Signal thresholds, not hard gates)
# =============================================================================
WATCHER_THRESHOLDS = {
    # Volatility (ATR as % of price)
    "atr_pct_high": 4.0,
    # Drawdown from recent highs (20 trading days)
    "drawdown_20d_pct": 10.0,
    # Momentum extremes
    "rsi_oversold": 30.0,
    "rsi_overbought": 70.0,
}
