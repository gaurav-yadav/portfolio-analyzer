# SPEC: OHLCV Confluence Enrichment for Stock Scanner

This spec defines the **code changes** needed to make scan results “smart” by enriching web-search candidates with **OHLCV-derived confluence setups** and producing ranked shortlists for:
- **`2w_breakout`** (hold ~1–2 weeks)
- **`2m_pullback`** (hold ~1–2 months)
- **`support_reversal`** (manual cross-check; higher risk)

It is written to be **KISS + DRY**:
- WebSearch is only for discovery (candidate pool).
- OHLCV (cached) is the decision engine.
- Compute OHLCV features once per symbol; reuse everywhere.
- Keep scoring deterministic + explainable via `why[]`.

## Non-goals

- No new backtesting framework.
- No new data sources besides existing Yahoo Finance OHLCV cache.
- No subjective pattern recognition beyond simple, deterministic heuristics.

---

## Where the logic lives (DRY)

You have two options; pick **one** to avoid duplication:

### Option A (recommended): extend `scripts/verify_scan.py`

- Add missing OHLCV-derived features to `compute_full_analysis(df)`.
- `scripts/validate_scan.py` continues to call `verify_scan.analyze_batch(...)` and scores setups from `results_by_symbol`.

Pros: one OHLCV compute path; caching already handled; other scripts can reuse.
Cons: `verify_scan.py` grows.

### Option B: implement setup enrichment in `scripts/validate_scan.py`

- Load cached parquet per symbol (same as verify_scan does) and compute features inside validate_scan.
- Keep `verify_scan.py` unchanged.

Pros: isolated to validation pipeline.
Cons: duplicate OHLCV load/fallback logic unless you refactor shared helper(s).

---

## CLI changes (validate/enrich)

Extend `scripts/validate_scan.py` CLI:

- `--enrich-setups` (bool): compute and attach setup blocks per symbol into scan JSON.
- `--rank` (bool): write ranked shortlists into `validation.rankings.*`.
- `--top N` (int, default 10): shortlist length per ranking bucket.
- `--us` (bool, default false): pass through to `verify_scan.analyze_batch(..., us_market=True)`.

Existing args remain supported:
- `--max-per-scan`, `--max-symbols`, `--output`

Behavior:
- Without `--enrich-setups`, current behavior stays (per-match validation only).
- With `--enrich-setups`, update `validation.engine_version` to `2`.
- With `--rank`, rankings are computed from `validation.setups_by_symbol` (requires `--enrich-setups`).

---

## Config (single source of truth)

Add a single constant in `utils/config.py`:
- `SCAN_SETUP_RULES` (dict) containing:
  - lookbacks (swing, pivot, breakout window)
  - thresholds (near support %, volume ratio min, overextension %, breakout recency, etc.)

All setup scoring uses these values; do not hardcode in scripts.

---

## Data flow

Input: `data/scans/scan_*.json`
- `scan.scans.<scan_type>.matches[]` entries have at least `symbol` (+ optional `note`, `source`, `source_url`, `as_of`).

Processing:
1. Normalize scan matches to dicts (already done in validate_scan).
2. Deduplicate into `symbols[]` (clean symbols).
3. Compute OHLCV metrics once per symbol (via verify_scan or local load).
4. Produce:
   - per-match scan-type validation (existing)
   - per-symbol setup scoring blocks (new)
   - rankings (new)

Output: same scan file updated in-place (or to `--output`).

---

## Required OHLCV features

Minimum features needed for setup scoring (daily, 1y):

### Moving averages
- `sma20`, `sma50`, `sma200` (None if insufficient rows)
- `pct_from_sma20 = (close/sma20 - 1) * 100` (if sma20 available)
- `pct_from_sma50`, `pct_from_sma200` similarly

### RSI + volume
- `rsi14`
- `volume_ratio = volume_today / volume_avg_20`
- `price_change_1d` (%)

### Breakout window (Donchian-style)
- `donchian_high_20 = high.shift(1).rolling(20).max().iloc[-1]`
- `breakout_today = close > donchian_high_20`
- `days_since_breakout_20`: trading days since last `close > donchian_high_20` event (within last ~30d)

### Support level (deterministic swing support)

Goal: a “nearest meaningful support below price” from recent swing lows.

KISS pivot-low detection (no scipy):
- Use a small window `k=2` (5-bar pivot):
  - pivot low at index `i` if `Low[i]` is the minimum of `Low[i-k : i+k+1]`.
- Collect pivot lows over `pivot_lookback` days (e.g., 90).
- Consider only pivot lows `< close`.
- Support level = the **highest** pivot low below current close (closest support).
- If none exist, fallback to `rolling_min_low` over last `pivot_lookback` days.

Derived:
- `support_level`
- `pct_above_support = (close/support_level - 1) * 100` (if support_level)

### Optional (nice-to-have, still KISS)

#### Tight range / compression
- Over last `n=10` days:
  - `range_pct = (max(high_n) - min(low_n)) / close * 100`
  - `tight_range = range_pct <= tight_range_max_pct`

#### “Close near high” (for breakout quality)
- `close_to_high_pct = (high_today - close_today) / high_today * 100`
- “close near high” if `close_to_high_pct <= close_near_high_max_pct`

#### Bullish RSI divergence (for reversal bucket)
- Find last two pivot lows (using pivot-low detection above).
- Bullish divergence if:
  - price pivot low2 < low1 (lower low)
  - RSI at pivot low2 > RSI at pivot low1 (higher low)

---

## Setup scoring outputs (per symbol)

Add a new structure at:
- `scan.validation.setups_by_symbol[symbol_clean]`

Each symbol has three setup blocks:
- `2m_pullback`
- `2w_breakout`
- `support_reversal`

Each block format:
```json
{
  "pass": true,
  "score": 82,
  "why": ["trend_ok", "near_support", "rsi_reset", "volume_on_bounce"],
  "metrics": {
    "close": 180.4,
    "rsi": 47.2,
    "volume_ratio": 1.4,
    "pct_from_sma20": 1.8,
    "pct_above_support": 1.2,
    "days_since_breakout_20": null
  }
}
```

`why[]` must contain stable string keys (no free-form sentences). Human “why” is assembled later.

---

## Setup definitions (rules + scoring)

Scoring is **0–100**, deterministic:
- Start with `score = 0`.
- Add/subtract points per rule.
- Set `pass` based on hard gates + minimum score threshold.

### A) `2m_pullback` (primary)

Intent: trend-following pullback entry.

Hard gates (fail fast):
- `sma200` available AND `close > sma200`
- Not overextended: `pct_from_sma20 <= max_extension_above_sma20_pct` (if sma20 exists; else skip this gate)

Point rubric (suggested):
- +25 `trend_ok`: `close > sma200` AND `sma50 >= sma200` (or `close > sma50` if sma50 exists)
- +20 `near_support`: `pct_above_support <= near_support_pct`
- +15 `near_sma`: `abs(pct_from_sma20) <= near_sma_pct` OR `abs(pct_from_sma50) <= near_sma_pct`
- +20 `rsi_reset`: `rsi_ideal_min <= rsi <= rsi_ideal_max`
- +10 `macd_bullish` (if you already compute MACD; optional)
- +10 `volume_on_bounce`: (`price_change_1d > 0` AND `volume_ratio >= min_volume_ratio_bounce`)
- -15 `overbought`: `rsi >= rsi_overbought_max`

Pass condition:
- gates pass AND `score >= 60`

### B) `2w_breakout` (secondary)

Intent: breakout continuation; avoid false breakouts.

Hard gates:
- `close > sma50` (if available) AND `close > sma200` (if available; if not available, require `close > sma50`)
- `days_since_breakout_20` is not None AND `days_since_breakout_20 <= max_days_since_breakout`

Point rubric (suggested):
- +25 `trend_ok` (as above)
- +25 `recent_breakout` (0–3 days)
- +20 `volume_ok`: `volume_ratio >= breakout_min_volume_ratio`
- +10 `strong_volume` if `volume_ratio >= breakout_strong_volume_ratio`
- +10 `close_near_high` if `close_to_high_pct <= close_near_high_max_pct`
- +10 `tight_range` if `tight_range == true`
- -15 `overextended` if `pct_from_sma20 > max_extension_above_sma20_pct`
- -10 `too_overbought` if `rsi > rsi_overbought_max`

Pass condition:
- gates pass AND `score >= 65`

### C) `support_reversal` (manual cross-check)

Intent: potential turn at support; higher risk.

Hard gates:
- `support_level` exists
- `pct_above_support <= near_support_pct`
- Bounce confirmation: `price_change_1d >= min_bounce_change_pct` AND `volume_ratio >= min_bounce_volume_ratio`

Point rubric (suggested):
- +30 `near_support`
- +25 `bounce_confirmed`
- +15 `rsi_bull_divergence` (if computed)
- +15 `reclaim_sma20` if `close > sma20` (optional)
- +10 `reclaim_sma50` if `close > sma50` (optional)
- -20 `downtrend_risk` if `close < sma200` AND `sma50 < sma200` (if both exist)

Pass condition:
- gates pass AND `score >= 60`

---

## Rankings

When `--rank` is enabled, write:
- `scan.validation.rankings.2w_breakout`
- `scan.validation.rankings.2m_pullback`
- `scan.validation.rankings.support_reversal`

Each entry:
```json
{"symbol":"DCBBANK","score":78,"why":"trend_ok + recent_breakout + volume_ok","scan_hits":["macd_crossover","rsi_oversold"]}
```

Ranking rules:
- Only include symbols where that setup block has `pass: true`.
- Sort by `score` desc, then tie-break by:
  - higher `volume_ratio`, then
  - lower `pct_from_sma20` (less chase), then
  - `symbol` asc
- Keep top `--top N` (default 10).

`scan_hits` is derived from which scan types the symbol appeared in (from `scan.scans.*.matches`).

---

## Engine versioning + compatibility

In `scan.validation`:
- Keep existing fields (`rules`, `results_by_symbol`, etc.).
- Set `engine_version`:
  - `1` = legacy validation only
  - `2` = includes `setups_by_symbol` and `rankings`

Do not change the shape of existing per-match `validation.metrics` fields; only add new keys if needed.

---

## Minimal output (agent expectations)

The enrichment writes all details to files; agent responses stay small:
- Scanner agent: print scan file path + top 5 `2w_breakout` + top 5 `2m_pullback`.
- Cross-check agents: read the scan JSON and print top 10 for their bucket.

---

## Smoke test checklist (manual)

1. Ensure you have at least one scan file in `data/scans/`.
2. Run:
   - `uv run python scripts/validate_scan.py latest --enrich-setups --rank`
3. Open the scan JSON and confirm:
   - `validation.engine_version == 2`
   - `validation.setups_by_symbol` exists and has 3 blocks per symbol
   - `validation.rankings.*` lists exist and are sorted
4. Sanity check 2–3 symbols manually against charts for reasonableness.

