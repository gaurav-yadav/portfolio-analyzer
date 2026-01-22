# Features

## Portfolio Analysis

Import holdings → fetch OHLCV → compute technicals → web research → score → report → snapshot.

- Supports Zerodha, Groww, Vested, custom CSV
- 30-day research staleness policy
- Scoring profiles: `portfolio_long_term`, `watchlist_swing`
- Report archiving with comparison

## Stock Scanner

Web discovery → OHLCV confluence validation → ranked shortlists.

- 5 scan types: RSI oversold, MACD crossover, golden cross, volume breakout, 52w high
- 3 setup scores: `2m_pullback`, `2w_breakout`, `support_reversal`
- Configurable pass thresholds

## Watchlists (v2)

Event-sourced with full audit trail.

- Events: ADD, REMOVE, NOTE
- Captures: setup, horizon, entry zone, invalidation, timing, re-entry
- Per-run snapshots

## IPO Scanner

Maintain IPO database, research, score.

- Versioned `data/ipos.json`
- Validation + rendering scripts

## Scoring

| Component | Default Weight |
|-----------|----------------|
| Technical | 35% |
| Fundamental | 30% |
| News | 20% |
| Legal | 15% |

Safety gates prevent bad recommendations (trend < 5 → max HOLD).

## Technical Indicators

RSI (14), MACD (12/26/9), SMA (50/200), Bollinger (20, 2σ), ADX (14), Volume (20d avg).

## Data Sources

- OHLCV: Yahoo Finance (18h cache)
- Research: Web search (30-day staleness)
- Scanner: Chartink, Trendlyne, Groww, etc.
