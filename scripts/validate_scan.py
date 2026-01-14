#!/usr/bin/env python3
"""
Validate stock scan results using Yahoo Finance OHLCV + technical checks.

This script reads a saved scan file from `data/scans/`, runs `verify_scan.py`
style technical analysis on all unique symbols, then annotates the scan JSON
with validation results per match.

Usage:
  uv run python scripts/validate_scan.py latest
  uv run python scripts/validate_scan.py data/scans/scan_YYYYMMDD_HHMMSS.json
  uv run python scripts/validate_scan.py latest --output data/scans/scan_validated.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import normalize_symbol
from utils.config import SCAN_SETUP_RULES


SCANS_DIR = Path("data/scans")


# =============================================================================
# SETUP SCORING FUNCTIONS
# =============================================================================

def score_2m_pullback(analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Score for 2-month trend-following pullback entry.

    Hard gates:
    - sma200 available AND close > sma200
    - Not overextended: pct_from_sma20 <= max_extension

    Returns setup block with pass, score, why[], metrics.
    """
    rules = SCAN_SETUP_RULES
    result = {
        "pass": False,
        "score": 0,
        "why": [],
        "metrics": {},
    }

    # Extract needed values
    price = analysis.get("price", 0)
    sma20 = analysis.get("sma20")
    sma50 = analysis.get("sma50")
    sma200 = analysis.get("sma200")
    pct_from_sma20 = analysis.get("pct_from_sma20")
    pct_from_sma50 = analysis.get("pct_from_sma50")
    rsi = analysis.get("rsi", 50)
    macd_bullish = analysis.get("macd_bullish", False)
    volume_ratio = analysis.get("volume_ratio", 1.0)
    price_change_1d = analysis.get("price_change_1d", 0)
    support_level = analysis.get("support_level")
    pct_above_support = analysis.get("pct_above_support")

    # Populate metrics
    result["metrics"] = {
        "close": price,
        "rsi": rsi,
        "volume_ratio": volume_ratio,
        "pct_from_sma20": pct_from_sma20,
        "pct_above_support": pct_above_support,
        "days_since_breakout_20": analysis.get("days_since_breakout_20"),
    }

    # Hard gate 1: sma200 must exist and price > sma200
    if sma200 is None or price <= sma200:
        result["why"].append("gate_fail_below_sma200")
        return result

    # Hard gate 2: Not overextended above SMA20
    if pct_from_sma20 is not None and pct_from_sma20 > rules["max_extension_above_sma20_pct"]:
        result["why"].append("gate_fail_overextended")
        return result

    score = 0

    # +25 trend_ok: close > sma200 AND (sma50 >= sma200 OR close > sma50)
    trend_ok = False
    if sma50 is not None and sma200 is not None:
        if sma50 >= sma200 or price > sma50:
            trend_ok = True
    elif sma50 is not None and price > sma50:
        trend_ok = True
    elif price > sma200:
        trend_ok = True

    if trend_ok:
        score += 25
        result["why"].append("trend_ok")

    # +20 near_support: pct_above_support <= near_support_pct
    if pct_above_support is not None and pct_above_support <= rules["near_support_pct"]:
        score += 20
        result["why"].append("near_support")

    # +15 near_sma: abs(pct_from_sma20) <= near_sma_pct OR abs(pct_from_sma50) <= near_sma_pct
    near_sma = False
    if pct_from_sma20 is not None and abs(pct_from_sma20) <= rules["near_sma_pct"]:
        near_sma = True
    if pct_from_sma50 is not None and abs(pct_from_sma50) <= rules["near_sma_pct"]:
        near_sma = True
    if near_sma:
        score += 15
        result["why"].append("near_sma")

    # +20 rsi_reset: rsi in ideal range
    if rules["rsi_ideal_min"] <= rsi <= rules["rsi_ideal_max"]:
        score += 20
        result["why"].append("rsi_reset")

    # +10 macd_bullish
    if macd_bullish:
        score += 10
        result["why"].append("macd_bullish")

    # +10 volume_on_bounce: price_change_1d > 0 AND volume_ratio >= min
    if price_change_1d > 0 and volume_ratio >= rules["min_volume_ratio_bounce"]:
        score += 10
        result["why"].append("volume_on_bounce")

    # -15 overbought: rsi >= rsi_overbought_max
    if rsi >= rules["rsi_overbought_max"]:
        score -= 15
        result["why"].append("overbought")

    result["score"] = max(0, min(100, score))
    result["pass"] = score >= rules["2m_pullback_min_score"]

    return result


def score_2w_breakout(analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Score for 2-week breakout continuation.

    Hard gates:
    - close > sma50 (if available) AND close > sma200 (if available)
    - days_since_breakout_20 is not None AND <= max_days_since_breakout

    Returns setup block with pass, score, why[], metrics.
    """
    rules = SCAN_SETUP_RULES
    result = {
        "pass": False,
        "score": 0,
        "why": [],
        "metrics": {},
    }

    # Extract needed values
    price = analysis.get("price", 0)
    sma50 = analysis.get("sma50")
    sma200 = analysis.get("sma200")
    pct_from_sma20 = analysis.get("pct_from_sma20")
    rsi = analysis.get("rsi", 50)
    volume_ratio = analysis.get("volume_ratio", 1.0)
    days_since_breakout = analysis.get("days_since_breakout_20")
    tight_range = analysis.get("tight_range", False)
    close_near_high = analysis.get("close_near_high", False)

    # Populate metrics
    result["metrics"] = {
        "close": price,
        "rsi": rsi,
        "volume_ratio": volume_ratio,
        "pct_from_sma20": pct_from_sma20,
        "days_since_breakout_20": days_since_breakout,
        "tight_range": tight_range,
        "close_near_high": close_near_high,
    }

    # Hard gate 1: price above SMAs
    if sma200 is not None and price <= sma200:
        result["why"].append("gate_fail_below_sma200")
        return result
    if sma50 is not None and price <= sma50:
        # If sma200 not available, require sma50
        if sma200 is None:
            result["why"].append("gate_fail_below_sma50")
            return result

    # Hard gate 2: recent breakout
    if days_since_breakout is None or days_since_breakout > rules["max_days_since_breakout"]:
        result["why"].append("gate_fail_no_recent_breakout")
        return result

    score = 0

    # +25 trend_ok
    trend_ok = False
    if sma50 is not None and sma200 is not None:
        if price > sma50 and sma50 >= sma200:
            trend_ok = True
    elif sma50 is not None and price > sma50:
        trend_ok = True
    elif sma200 is not None and price > sma200:
        trend_ok = True

    if trend_ok:
        score += 25
        result["why"].append("trend_ok")

    # +25 recent_breakout (0-3 days is best)
    if days_since_breakout <= 3:
        score += 25
        result["why"].append("recent_breakout")
    elif days_since_breakout <= rules["max_days_since_breakout"]:
        score += 15
        result["why"].append("breakout_ok")

    # +20 volume_ok
    if volume_ratio >= rules["breakout_min_volume_ratio"]:
        score += 20
        result["why"].append("volume_ok")

    # +10 strong_volume
    if volume_ratio >= rules["breakout_strong_volume_ratio"]:
        score += 10
        result["why"].append("strong_volume")

    # +10 close_near_high
    if close_near_high:
        score += 10
        result["why"].append("close_near_high")

    # +10 tight_range
    if tight_range:
        score += 10
        result["why"].append("tight_range")

    # -15 overextended
    if pct_from_sma20 is not None and pct_from_sma20 > rules["max_extension_above_sma20_pct"]:
        score -= 15
        result["why"].append("overextended")

    # -10 too_overbought
    if rsi > rules["rsi_overbought_max"]:
        score -= 10
        result["why"].append("too_overbought")

    result["score"] = max(0, min(100, score))
    result["pass"] = score >= rules["2w_breakout_min_score"]

    return result


def score_support_reversal(analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Score for support reversal (higher risk, manual cross-check).

    Hard gates:
    - support_level exists
    - pct_above_support <= near_support_pct
    - Bounce confirmation: price_change_1d >= min AND volume_ratio >= min

    Returns setup block with pass, score, why[], metrics.
    """
    rules = SCAN_SETUP_RULES
    result = {
        "pass": False,
        "score": 0,
        "why": [],
        "metrics": {},
    }

    # Extract needed values
    price = analysis.get("price", 0)
    sma20 = analysis.get("sma20")
    sma50 = analysis.get("sma50")
    sma200 = analysis.get("sma200")
    rsi = analysis.get("rsi", 50)
    volume_ratio = analysis.get("volume_ratio", 1.0)
    price_change_1d = analysis.get("price_change_1d", 0)
    support_level = analysis.get("support_level")
    pct_above_support = analysis.get("pct_above_support")

    # Populate metrics
    result["metrics"] = {
        "close": price,
        "rsi": rsi,
        "volume_ratio": volume_ratio,
        "price_change_1d": price_change_1d,
        "support_level": support_level,
        "pct_above_support": pct_above_support,
    }

    # Hard gate 1: support_level exists
    if support_level is None:
        result["why"].append("gate_fail_no_support")
        return result

    # Hard gate 2: near support
    if pct_above_support is None or pct_above_support > rules["near_support_pct"]:
        result["why"].append("gate_fail_not_near_support")
        return result

    # Hard gate 3: bounce confirmation
    bounce_confirmed = (
        price_change_1d >= rules["min_bounce_change_pct"] and
        volume_ratio >= rules["min_bounce_volume_ratio"]
    )
    if not bounce_confirmed:
        result["why"].append("gate_fail_no_bounce")
        return result

    score = 0

    # +30 near_support (already passed gate)
    score += 30
    result["why"].append("near_support")

    # +25 bounce_confirmed (already passed gate)
    score += 25
    result["why"].append("bounce_confirmed")

    # +15 reclaim_sma20
    if sma20 is not None and price > sma20:
        score += 15
        result["why"].append("reclaim_sma20")

    # +10 reclaim_sma50
    if sma50 is not None and price > sma50:
        score += 10
        result["why"].append("reclaim_sma50")

    # -20 downtrend_risk: close < sma200 AND sma50 < sma200
    if sma200 is not None and sma50 is not None:
        if price < sma200 and sma50 < sma200:
            score -= 20
            result["why"].append("downtrend_risk")

    result["score"] = max(0, min(100, score))
    result["pass"] = score >= rules["support_reversal_min_score"]

    return result


def compute_setups_for_symbol(analysis: dict[str, Any]) -> dict[str, Any]:
    """Compute all three setup scores for a symbol."""
    return {
        "2m_pullback": score_2m_pullback(analysis),
        "2w_breakout": score_2w_breakout(analysis),
        "support_reversal": score_support_reversal(analysis),
    }


def compute_rankings(
    setups_by_symbol: dict[str, dict[str, Any]],
    results_by_symbol: dict[str, dict[str, Any]],
    scan_hits_by_symbol: dict[str, list[str]],
    top_n: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    """
    Compute ranked shortlists for each setup type.

    Ranking rules:
    - Only include symbols where setup block has pass: true
    - Sort by score desc, then volume_ratio desc, then pct_from_sma20 asc, then symbol asc
    - Keep top N
    """
    rankings = {
        "2w_breakout": [],
        "2m_pullback": [],
        "support_reversal": [],
    }

    for setup_type in rankings.keys():
        candidates = []

        for symbol, setups in setups_by_symbol.items():
            setup = setups.get(setup_type, {})
            if not setup.get("pass"):
                continue

            analysis = results_by_symbol.get(symbol, {})
            volume_ratio = analysis.get("volume_ratio", 1.0)
            pct_from_sma20 = analysis.get("pct_from_sma20", 0) or 0

            # Compile why string
            why_list = setup.get("why", [])
            why_str = " + ".join(why_list[:4]) if why_list else ""

            candidates.append({
                "symbol": symbol,
                "score": setup.get("score", 0),
                "why": why_str,
                "scan_hits": scan_hits_by_symbol.get(symbol, []),
                # For sorting
                "_volume_ratio": volume_ratio,
                "_pct_from_sma20": pct_from_sma20,
            })

        # Sort: score desc, volume_ratio desc, pct_from_sma20 asc (less chase), symbol asc
        candidates.sort(
            key=lambda x: (-x["score"], -x["_volume_ratio"], x["_pct_from_sma20"], x["symbol"])
        )

        # Keep top N and remove sort keys
        for c in candidates[:top_n]:
            del c["_volume_ratio"]
            del c["_pct_from_sma20"]
            rankings[setup_type].append(c)

    return rankings


@dataclass(frozen=True)
class ValidationRuleSet:
    """Validation thresholds for scan types."""

    rsi_oversold_max: float = 30.0
    rsi_recovery_max: float = 40.0
    macd_crossover_max_days: int = 5
    golden_cross_max_days: int = 30
    volume_breakout_min_ratio: float = 1.5
    week52_high_max_pct_off: float = 5.0


def find_latest_scan_file() -> Path:
    if not SCANS_DIR.exists():
        raise FileNotFoundError("data/scans does not exist (no scan files found)")
    scans = sorted(SCANS_DIR.glob("scan_*.json"), reverse=True)
    if not scans:
        raise FileNotFoundError("No scan files found in data/scans/")
    return scans[0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_serializer(obj):
    """Handle numpy types and other non-serializable objects."""
    import numpy as np
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_json_serializer), encoding="utf-8")


def load_verify_scan_module():
    """Import scripts/verify_scan.py as a module without turning scripts/ into a package."""
    verify_path = Path(__file__).parent / "verify_scan.py"
    spec = importlib.util.spec_from_file_location("verify_scan", verify_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load verify_scan module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_match(match: Any) -> dict[str, Any]:
    """
    Normalize a match entry into a dict with at least `symbol`.

    Supports:
    - {"symbol": "...", "note": "...", "source": "..."}
    - "SYMBOL - note - source"
    - "SYMBOL ..."
    """
    if isinstance(match, dict):
        symbol = str(match.get("symbol", "")).strip()
        out = dict(match)
        out["symbol"] = symbol
        return out

    if isinstance(match, str):
        raw = match.strip()
        if " - " in raw:
            parts = [p.strip() for p in raw.split(" - ") if p.strip()]
            symbol = parts[0] if parts else ""
            note = parts[1] if len(parts) >= 2 else ""
            source = parts[2] if len(parts) >= 3 else ""
            return {"symbol": symbol, "note": note, "source": source, "raw": raw}

        first = raw.split()[0] if raw else ""
        return {"symbol": first, "raw": raw}

    return {"symbol": "", "raw": str(match)}


def extract_symbols(scan_data: dict[str, Any], max_per_scan: int | None = None) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    scans = scan_data.get("scans", {}) or {}
    normalized_scans: dict[str, list[dict[str, Any]]] = {}
    symbols: list[str] = []
    seen: set[str] = set()

    for scan_type, scan_block in scans.items():
        matches = []
        if isinstance(scan_block, dict):
            matches = scan_block.get("matches", []) or []
        elif isinstance(scan_block, list):
            matches = scan_block

        normalized_matches = [normalize_match(m) for m in matches]
        if max_per_scan is not None:
            normalized_matches = normalized_matches[: max_per_scan]
        normalized_scans[str(scan_type)] = normalized_matches

        for m in normalized_matches:
            sym = normalize_symbol(str(m.get("symbol", "")).strip())
            if not sym:
                continue
            if sym not in seen:
                seen.add(sym)
                symbols.append(sym)

    return symbols, normalized_scans


def validate_for_scan_type(scan_type: str, analysis: dict[str, Any] | None, rules: ValidationRuleSet) -> dict[str, Any]:
    """Return a compact validation result for a given scan type."""
    if analysis is None:
        return {"pass": False, "reason": "no_ohlcv_data"}

    rsi = analysis.get("rsi")
    macd_bullish = bool(analysis.get("macd_bullish"))
    macd_crossover_days_ago = analysis.get("macd_crossover_days_ago")
    trend = analysis.get("trend")
    golden_cross = analysis.get("golden_cross")
    golden_cross_days_ago = analysis.get("golden_cross_days_ago")
    volume_ratio = analysis.get("volume_ratio")
    price_change_1d = analysis.get("price_change_1d")
    pct_from_high = analysis.get("pct_from_high")

    metrics = {
        "yf_symbol": analysis.get("yf_symbol"),
        "technical_score": analysis.get("technical_score"),
        "recommendation": analysis.get("recommendation"),
        "rsi": rsi,
        "macd_bullish": macd_bullish,
        "macd_crossover_days_ago": macd_crossover_days_ago,
        "trend": trend,
        "golden_cross": golden_cross,
        "golden_cross_days_ago": golden_cross_days_ago,
        "volume_ratio": volume_ratio,
        "price_change_1d": price_change_1d,
        "pct_from_high": pct_from_high,
    }

    scan_type_norm = scan_type.lower().strip()
    if scan_type_norm in {"rsi_oversold", "rsi"}:
        # Best practice: oversold OR recovering within an uptrend with bullish momentum
        if isinstance(rsi, (int, float)) and rsi <= rules.rsi_oversold_max:
            return {"pass": True, "reason": f"rsi<= {rules.rsi_oversold_max}", "metrics": metrics}
        if (
            isinstance(rsi, (int, float))
            and rsi <= rules.rsi_recovery_max
            and trend in {"UP", "STRONG UP"}
            and macd_bullish
        ):
            return {"pass": True, "reason": "oversold_recovery_in_uptrend", "metrics": metrics}
        return {"pass": False, "reason": "rsi_not_oversold", "metrics": metrics}

    if scan_type_norm in {"macd_crossover", "macd"}:
        # Screeners typically mean a *recent* crossover, not just MACD>signal.
        if not macd_bullish:
            return {"pass": False, "reason": "macd_not_bullish", "metrics": metrics}
        if isinstance(macd_crossover_days_ago, int) and macd_crossover_days_ago <= rules.macd_crossover_max_days:
            return {"pass": True, "reason": "recent_macd_crossover", "metrics": metrics}
        if macd_crossover_days_ago is None:
            # If crossover recency can't be computed, fall back to bullish MACD.
            return {"pass": True, "reason": "macd_bullish_no_recency", "metrics": metrics}
        return {"pass": False, "reason": "macd_crossover_not_recent", "metrics": metrics}

    if scan_type_norm in {"golden_cross"}:
        if not golden_cross:
            return {"pass": False, "reason": "no_golden_cross", "metrics": metrics}
        if isinstance(golden_cross_days_ago, int) and golden_cross_days_ago <= rules.golden_cross_max_days:
            return {"pass": True, "reason": "recent_golden_cross", "metrics": metrics}
        if golden_cross_days_ago is None:
            return {"pass": True, "reason": "golden_cross_no_recency", "metrics": metrics}
        return {"pass": True, "reason": "golden_cross_older", "metrics": metrics}

    if scan_type_norm in {"volume_breakout", "volume"}:
        vol_ok = isinstance(volume_ratio, (int, float)) and volume_ratio >= rules.volume_breakout_min_ratio
        price_ok = isinstance(price_change_1d, (int, float)) and price_change_1d > 0
        passed = bool(vol_ok and price_ok)
        reason = "volume_and_price_breakout" if passed else "no_volume_breakout"
        return {"pass": passed, "reason": reason, "metrics": metrics}

    if scan_type_norm in {"52week_high", "52_week_high", "week52_high"}:
        near_high = isinstance(pct_from_high, (int, float)) and pct_from_high <= rules.week52_high_max_pct_off
        passed = bool(near_high and trend in {"UP", "STRONG UP"})
        reason = "near_52w_high" if passed else "not_near_52w_high"
        return {"pass": passed, "reason": reason, "metrics": metrics}

    # Unknown scan type: just attach metrics
    return {"pass": False, "reason": "unknown_scan_type", "metrics": metrics}


def build_scan_hits_by_symbol(normalized_scans: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    """Build a mapping of symbol -> list of scan types it appeared in."""
    scan_hits: dict[str, list[str]] = {}
    for scan_type, matches in normalized_scans.items():
        for m in matches:
            sym = normalize_symbol(str(m.get("symbol", "")).strip())
            if sym:
                if sym not in scan_hits:
                    scan_hits[sym] = []
                if scan_type not in scan_hits[sym]:
                    scan_hits[sym].append(scan_type)
    return scan_hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate scan results with OHLCV-based technical checks.")
    parser.add_argument(
        "scan",
        nargs="?",
        default="latest",
        help="Scan file path, or 'latest' to use most recent data/scans/scan_*.json",
    )
    parser.add_argument("--max-per-scan", type=int, default=None, help="Limit matches validated per scan type")
    parser.add_argument("--max-symbols", type=int, default=None, help="Limit total unique symbols validated")
    parser.add_argument("--output", type=str, default=None, help="Write annotated scan JSON to this path (default: in-place)")
    parser.add_argument("--enrich-setups", action="store_true", help="Compute and attach setup blocks (2m_pullback, 2w_breakout, support_reversal)")
    parser.add_argument("--rank", action="store_true", help="Write ranked shortlists into validation.rankings (requires --enrich-setups)")
    parser.add_argument("--top", type=int, default=10, help="Shortlist length per ranking bucket (default: 10)")
    parser.add_argument("--us", action="store_true", help="Treat symbols as US stocks (no .NS suffix)")
    args = parser.parse_args()

    scan_path = Path(args.scan) if args.scan != "latest" else find_latest_scan_file()
    if not scan_path.exists():
        print(f"Error: Scan file not found: {scan_path}", file=sys.stderr)
        return 1

    scan_data = load_json(scan_path)
    symbols, normalized_scans = extract_symbols(scan_data, max_per_scan=args.max_per_scan)
    if args.max_symbols is not None:
        symbols = symbols[: args.max_symbols]

    if not symbols:
        print("No symbols found in scan file (nothing to validate)", file=sys.stderr)
        return 1

    # Run OHLCV-based verification (reuses existing verify_scan implementation)
    verify_scan = load_verify_scan_module()
    results = verify_scan.analyze_batch(symbols, us_market=args.us, verbose=False)
    results_by_symbol: dict[str, dict[str, Any]] = {r.get("symbol"): r for r in results if isinstance(r, dict)}

    rules = ValidationRuleSet()

    # Annotate each match with validation result
    per_scan_summary: dict[str, Any] = {}
    for scan_type, matches in normalized_scans.items():
        validated = 0
        missing = 0
        for m in matches:
            sym = normalize_symbol(str(m.get("symbol", "")).strip())
            analysis = results_by_symbol.get(sym)
            v = validate_for_scan_type(scan_type, analysis, rules)
            m["validation"] = v
            if v.get("pass"):
                validated += 1
            if v.get("reason") == "no_ohlcv_data":
                missing += 1

        per_scan_summary[scan_type] = {
            "matches": len(matches),
            "validated": validated,
            "missing_ohlcv": missing,
        }

    # Determine engine version
    engine_version = 2 if args.enrich_setups else 1

    scan_data["validated_at"] = datetime.now().isoformat()
    scan_data["validation"] = {
        "engine": "scripts/validate_scan.py",
        "engine_version": engine_version,
        "rules": {
            "rsi_oversold_max": rules.rsi_oversold_max,
            "rsi_recovery_max": rules.rsi_recovery_max,
            "macd_crossover_max_days": rules.macd_crossover_max_days,
            "golden_cross_max_days": rules.golden_cross_max_days,
            "volume_breakout_min_ratio": rules.volume_breakout_min_ratio,
            "week52_high_max_pct_off": rules.week52_high_max_pct_off,
        },
        "symbols_requested": symbols,
        "symbols_validated": sorted(results_by_symbol.keys()),
        "per_scan_summary": per_scan_summary,
        "results_by_symbol": results_by_symbol,
    }

    # Enrich with setup scores if requested
    if args.enrich_setups:
        setups_by_symbol: dict[str, dict[str, Any]] = {}
        for symbol, analysis in results_by_symbol.items():
            setups_by_symbol[symbol] = compute_setups_for_symbol(analysis)

        scan_data["validation"]["setups_by_symbol"] = setups_by_symbol

        # Compute rankings if requested
        if args.rank:
            scan_hits_by_symbol = build_scan_hits_by_symbol(normalized_scans)
            rankings = compute_rankings(
                setups_by_symbol,
                results_by_symbol,
                scan_hits_by_symbol,
                top_n=args.top,
            )
            scan_data["validation"]["rankings"] = rankings

    # Write normalized scans back into scan_data
    if isinstance(scan_data.get("scans"), dict):
        for scan_type, matches in normalized_scans.items():
            block = scan_data["scans"].get(scan_type)
            if isinstance(block, dict):
                block["matches"] = matches
                block["count"] = block.get("count", len(matches))
            else:
                scan_data["scans"][scan_type] = {"count": len(matches), "matches": matches}

    out_path = Path(args.output) if args.output else scan_path
    save_json(out_path, scan_data)

    active_validated = sum(
        s.get("validated", 0) for s in per_scan_summary.values() if isinstance(s, dict)
    )

    # Build output message
    msg = f"Done: Validated scan at {out_path} (validated matches: {active_validated}, symbols: {len(results_by_symbol)})"

    if args.enrich_setups and args.rank:
        rankings = scan_data["validation"].get("rankings", {})
        top_breakout = [r["symbol"] for r in rankings.get("2w_breakout", [])[:5]]
        top_pullback = [r["symbol"] for r in rankings.get("2m_pullback", [])[:5]]
        if top_breakout:
            msg += f"\nTop 2w_breakout: {', '.join(top_breakout)}"
        if top_pullback:
            msg += f"\nTop 2m_pullback: {', '.join(top_pullback)}"

    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
