# Stock Scanner

Web-search discovery + OHLCV confluence validation.

## CLI: validate_scan.py

```
uv run python scripts/validate_scan.py [scan] [options]

positional:
  scan                  Path or 'latest' (default: latest)

options:
  --enrich-setups       Add setup blocks (2m_pullback, 2w_breakout, support_reversal)
  --rank                Write ranked shortlists (requires --enrich-setups)
  --top N               Shortlist size (default: 10)
  --us                  US stocks (no .NS suffix)
  --max-per-scan N      Limit matches per scan type
  --max-symbols N       Limit total symbols
  --output PATH         Output path (default: in-place)
```

### Examples

```bash
# Enrich and rank latest scan
uv run python scripts/validate_scan.py latest --enrich-setups --rank

# Specific scan, top 5
uv run python scripts/validate_scan.py data/scans/scan_20260120.json --enrich-setups --rank --top 5

# US market
uv run python scripts/validate_scan.py latest --enrich-setups --rank --us
```

---

## Scan Types

| Type | What it finds |
|------|---------------|
| `rsi_oversold` | RSI < 30 or recovering |
| `macd_crossover` | MACD line crossed signal |
| `golden_cross` | SMA50 > SMA200 |
| `volume_breakout` | Unusual volume + price move |
| `52w_high` | Near 52-week high |

---

## Setup Scoring

Three setup types with different intents:

### 2m_pullback (Primary)
- **Intent:** Trend-following pullback entry (1-2 month hold)
- **Hard gates:** close > SMA200, not overextended (< 8% above SMA20)
- **Signals:** near support, RSI 35-55, near SMA, volume on bounce

### 2w_breakout (Secondary)
- **Intent:** Breakout continuation (1-2 week hold)
- **Hard gates:** close > SMA50/200, recent breakout (within 5 days)
- **Signals:** volume confirmation, close near high, tight range

### support_reversal (Manual)
- **Intent:** Bounce at support (higher risk, cross-check)
- **Hard gates:** support exists, near support, bounce confirmed
- **Signals:** RSI divergence, reclaiming SMAs

---

## Output Schema

After `--enrich-setups --rank`:

```json
{
  "validation": {
    "engine_version": 2,
    "validated_at": "...",
    "results_by_symbol": {
      "RVNL": { "pass": true, "reason": "...", "metrics": {...} }
    },
    "setups_by_symbol": {
      "RVNL": {
        "2m_pullback": { "pass": true, "score": 75, "why": [...], "metrics": {...} },
        "2w_breakout": { "pass": false, "score": 40, "why": [...], "metrics": {...} },
        "support_reversal": { "pass": false, "score": 30, "why": [...], "metrics": {...} }
      }
    },
    "rankings": {
      "2m_pullback": [{ "symbol": "RVNL", "score": 75, "why": "...", "scan_hits": [...] }],
      "2w_breakout": [...],
      "support_reversal": [...]
    }
  }
}
```

---

## Configuration

`utils/config.py` → `SCAN_SETUP_RULES`:

```python
{
    "pivot_lookback": 90,
    "breakout_window": 20,
    "near_support_pct": 3.0,
    "max_extension_above_sma20_pct": 8.0,
    "max_days_since_breakout": 5,
    "rsi_ideal_min": 35,
    "rsi_ideal_max": 55,
    "rsi_overbought_max": 70,
    "min_volume_ratio_bounce": 1.2,
    "breakout_min_volume_ratio": 1.5,
    "2m_pullback_min_score": 60,
    "2w_breakout_min_score": 65,
    "support_reversal_min_score": 60,
}
```

---

## Agents

| Agent | Role |
|-------|------|
| `scanner` | Run web searches, save scan, call validate_scan |
| `scan-validator` | Run validate_scan on existing scan |
| `breakout-crosscheck` | Review 2w_breakout shortlist |
| `reversal-crosscheck` | Review support_reversal shortlist |
