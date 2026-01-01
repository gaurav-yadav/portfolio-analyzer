# Scoring System

This document explains the Portfolio Analyzer's scoring methodology in detail.

## Strategy Overview

**Medium-Term Trend-Following with Pullback Entries (1-3 months)**

- **Bias:** Trend-following, NOT mean-reversion
- **Entry style:** Buy pullbacks within established uptrends
- **Risk stance:** Avoid falling knives; prefer fewer high-confidence signals
- **Philosophy:** Technicals must confirm before fundamentals/news can recommend action

## Signal Flow

```
                    PORTFOLIO ANALYZER SCORING SYSTEM
    ================================================================

    STRATEGY: Medium-Term Trend-Following (1-3 months)
    INTENT:   Conservative BUY signals, avoid falling knives

    ┌─────────────────────────────────────────────────────────────┐
    │                    SIGNAL FLOW                              │
    │                                                             │
    │   RAW SCORES          GATES              FINAL OUTPUT       │
    │   ──────────         ──────              ────────────       │
    │                                                             │
    │   Technical ─35%─┐                                          │
    │                  │    ┌──────────────┐                      │
    │   Fundamental 30%├───>│ SAFETY GATES │───> Recommendation   │
    │                  │    │              │     + Confidence     │
    │   News ─────20%──┤    │ - Trend < 5? │                      │
    │                  │    │ - ADX weak?  │                      │
    │   Legal ────15%──┘    │ - Hype only? │                      │
    │                       └──────────────┘                      │
    └─────────────────────────────────────────────────────────────┘
```

## Component Weights

| Component | Weight | Role |
|-----------|--------|------|
| Technical Analysis | 35% | Price action, momentum, trend strength |
| Fundamentals | 30% | Quarterly results, P/E, growth metrics |
| News Sentiment | 20% | Recent news, analyst ratings |
| Legal/Corporate | 15% | SEBI issues, lawsuits, contracts |

Weights are defined in `utils/config.py` and can be adjusted.

## Indicator Roles

```
    ┌────────────────────────────────────────────────────────────┐
    │  Trend (SMA)  ████████████  PRIMARY GATE - Must confirm    │
    │  ADX          ████████░░░░  Strength qualifier             │
    │  MACD         ████████░░░░  Momentum confirmation          │
    │  RSI          ████░░░░░░░░  Entry timing only              │
    │  Bollinger    ████░░░░░░░░  Pullback context only          │
    │  Volume       ████░░░░░░░░  Breakout confirmation          │
    └────────────────────────────────────────────────────────────┘
```

| Indicator | Role | Can Boost? | Can Veto BUY? |
|-----------|------|------------|---------------|
| Trend (SMA) | Primary direction gate | Yes | **Yes** |
| ADX | Trend strength qualifier | Yes | Indirect |
| MACD | Momentum confirmation | Yes | Yes |
| RSI | Entry timing | Limited | No |
| Bollinger %B | Pullback context | Limited | No |
| Volume | Breakout confirmation | Yes | Indirect |

**Key principle:** RSI and Bollinger should never independently cause a BUY. They are timing tools, not direction tools.

## Safety Gates (Hard Rules)

These gates prevent bad recommendations regardless of raw scores:

```
    ┌────────────────────────────────────────────────────────────┐
    │  Trend < 5         →  Max recommendation: HOLD             │
    │  ADX weak + low vol →  Max recommendation: HOLD            │
    │  High news, low tech → Downgrade BUY to HOLD               │
    │  STRONG BUY needs   →  Trend >= 7, MACD >= 6, ADX >= 6     │
    └────────────────────────────────────────────────────────────┘
```

| Gate | Condition | Effect |
|------|-----------|--------|
| Trend Gate | `trend_score < 5` | Caps recommendation at HOLD |
| Weak Trend + Volume | `ADX <= 4 AND volume < 6` | Caps recommendation at HOLD |
| News Override | `news >= 8 AND technical < 5` | Downgrades BUY to HOLD |
| STRONG BUY Alignment | Missing trend/MACD/ADX alignment | Downgrades to BUY |
| Red Flag | Severe legal/regulatory issue | Caps score at 5.0 |

### Gate Thresholds (from `utils/config.py`)

```python
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
```

## Recommendation Thresholds

| Score Range | Recommendation | Meaning |
|-------------|----------------|---------|
| >= 8.0 | STRONG BUY | Trend-confirmed, high-confidence entry. All signals aligned. |
| 6.5 - 7.9 | BUY | Trend-aligned, acceptable entry risk. Consider scaling in. |
| 4.5 - 6.4 | HOLD | Mixed signals OR strong fundamentals without technical confirmation. |
| 3.0 - 4.4 | SELL | Technical + fundamental deterioration. Reduce on rallies. |
| < 3.0 | STRONG SELL | Multiple negative signals. Exit on any bounce. |

## Confidence Levels

Each recommendation includes a confidence level based on signal alignment:

| Confidence | Meaning |
|------------|---------|
| HIGH | All key signals (trend, MACD, ADX) are aligned |
| MEDIUM | Partial alignment, some mixed signals |
| LOW | Conflicting signals, or momentum without trend confirmation |

**Confidence drops when:**
- MACD strong but trend weak (momentum without direction)
- ADX < 20 (no clear trend to follow)
- Signals conflict (some bullish, some bearish)

## Coverage Tracking

Each analysis tracks which data sources were available:

| Code | Component |
|------|-----------|
| T | Technical analysis |
| F | Fundamental research |
| N | News sentiment |
| L | Legal/corporate |

Example: `TFNL` = all 4 components present, `TF--` = only technical and fundamental.

**Weight Renormalization:** When components are missing, their weights are redistributed proportionally among available components. This prevents "default 5" inflation.

## Portfolio Health

The overall portfolio receives a health assessment based on the weighted average score:

| Average Score | Health Label |
|---------------|--------------|
| >= 7.5 | Excellent |
| >= 6.5 | Good |
| >= 5.5 | Fair |
| >= 4.5 | Needs Attention |
| < 4.5 | At Risk |
