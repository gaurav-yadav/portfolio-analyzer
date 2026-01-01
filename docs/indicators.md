# Technical Indicators

This document details how each technical indicator is calculated and scored.

## Indicator Summary

| Indicator | Period | What it measures |
|-----------|--------|------------------|
| RSI | 14 days | Overbought/oversold momentum |
| MACD | 12/26/9 | Trend momentum and crossovers |
| SMA | 50 & 200 | Short and long-term trend |
| Bollinger | 20, 2σ | Volatility and price position |
| ADX | 14 days | Trend strength |
| Volume | 20-day avg | Buying/selling pressure |

## Scoring Overview

Each indicator is scored 1-10 (higher = more bullish). The scoring is **tuned for trend-following, NOT mean-reversion**.

The **technical_score** is the weighted average of all 6 indicator scores.

---

## RSI (Relative Strength Index)

**Role:** Entry Timing

RSI measures momentum on a 0-100 scale. In a trend-following strategy, we don't blindly buy oversold or sell overbought—we look for pullback entries in established trends.

| RSI Value | Score | Interpretation |
|-----------|-------|----------------|
| < 25 | 4 | Extreme oversold - potential falling knife |
| 25-35 | 7 | Pullback zone - ideal entry in uptrend |
| 35-55 | 6 | Healthy momentum |
| 55-70 | 5 | Neutral-to-strong |
| 70-80 | 4 | Overbought - not ideal entry |
| > 80 | 3 | Extreme overbought |

**Why extreme oversold scores low:**
In trend-following, extreme RSI < 25 often indicates a falling knife rather than a buying opportunity. We prefer RSI 25-35 (pullback in uptrend) over RSI < 25 (capitulation).

---

## MACD (Moving Average Convergence Divergence)

**Role:** Momentum Confirmation

MACD uses 12/26/9 periods (fast EMA, slow EMA, signal line). It confirms whether momentum supports the trend.

| Condition | Score | Interpretation |
|-----------|-------|----------------|
| Above signal + rising + above zero | 9 | Full bullish |
| Above signal + rising | 7 | Recovering |
| Above signal (not rising) | 5 | Momentum fading |
| Below signal but above zero | 4 | Pullback in uptrend |
| Below signal + below zero | 2 | Full bearish |

**Scoring logic:**
- Above zero line = uptrend context
- Above signal line = bullish crossover
- Rising histogram = accelerating momentum

---

## Trend (SMA 50/200)

**Role:** PRIMARY GATE

The trend indicator uses Simple Moving Averages (50-day and 200-day) to determine the primary market direction. This is the most important indicator—it can veto BUY recommendations.

| Condition | Score | Interpretation |
|-----------|-------|----------------|
| Price > SMA50 > SMA200 | 9 | Strong uptrend - green light |
| Price > SMA200 > SMA50 | 7 | Golden cross forming |
| Price > SMA50, SMA50 < SMA200 | 5 | Bear market rally - caution |
| SMA50 > SMA200, Price < SMA50 | 5 | Pullback in uptrend - watch |
| Price < SMA50 < SMA200 | 2 | Strong downtrend - avoid |

**Gate behavior:**
If `trend_score < 5`, the system caps the final recommendation at HOLD, regardless of other signals.

---

## Bollinger Bands

**Role:** Pullback Context (Not Mean-Reversion)

Bollinger Bands (20-period, 2 standard deviations) measure volatility and price position. We use %B (percentage position within bands).

| %B Value | Score | Interpretation |
|----------|-------|----------------|
| < 0 | 3 | Breaking down below bands |
| 0 - 0.2 | 5 | Near lower band (neutral) |
| 0.2 - 0.8 | 6 | Healthy range |
| 0.8 - 1.0 | 5 | Approaching upper band |
| > 1.0 | 4 | Extended breakout |

**Why we don't use mean-reversion:**
Traditional Bollinger strategies buy at lower band and sell at upper band. In trend-following, we recognize that prices can "walk the band" in strong trends. Being at the lower band is neutral, not bullish.

---

## ADX (Average Directional Index)

**Role:** Trend Strength Qualifier

ADX (14-period) measures trend strength (not direction). We combine it with +DI/-DI to determine direction.

| ADX + Direction | Score | Interpretation |
|-----------------|-------|----------------|
| > 30 + uptrend | 9 | Strong uptrend - high confidence |
| 25-30 + uptrend | 7 | Moderate uptrend |
| 20-25 | 5 | Developing trend |
| < 20 | 4 | Weak/no trend - dampen signals |
| > 25 + downtrend | 2 | Strong downtrend - avoid |

**Gate behavior:**
When `ADX <= 4 AND volume < 6`, the system caps recommendation at HOLD. Weak trends require volume confirmation.

---

## Volume

**Role:** Breakout Confirmation

Volume ratio compares current volume to 20-day average. We also consider whether the day closed up or down.

| Condition | Score | Interpretation |
|-----------|-------|----------------|
| > 2.0x avg + up day | 9 | Breakout volume |
| 1.5-2.0x avg + up day | 7 | Accumulation |
| 1.0-1.5x avg | 5 | Normal volume |
| 1.5-2.0x avg + down day | 4 | Distribution |
| > 2.0x avg + down day | 2 | Panic selling |

**Interpretation:**
- High volume on up days = accumulation (bullish)
- High volume on down days = distribution (bearish)
- Low volume = lack of conviction either way

---

## Configurable Weights

Technical indicator weights can be customized in `config/technical_weights.csv`:

```csv
indicator,weight,description
rsi,0.167,Relative Strength Index - entry timing in confirmed trends
macd,0.167,Moving Average Convergence Divergence - momentum confirmation
trend,0.167,Price trend based on SMA50/200 - PRIMARY GATE
bollinger,0.167,Bollinger Bands - pullback context (not mean-reversion)
adx,0.167,Average Directional Index - trend strength qualifier
volume,0.167,Volume analysis - breakout/distribution confirmation
```

Default weights are equal (1/6 each). Adjust based on your strategy preferences.

---

## Data Requirements

- **Minimum history:** 200 trading days (for SMA200)
- **Data source:** Yahoo Finance (via yfinance)
- **Refresh rate:** 18-hour cache freshness
- **Market hours:** Uses daily close prices
