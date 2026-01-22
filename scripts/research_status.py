#!/usr/bin/env python3
"""Deterministic research freshness checker.

Reports whether research files (fundamentals, news, legal) exist and are stale.
Used as a gate by orchestrator agents to decide what research to refresh.

Usage:
    uv run python scripts/research_status.py --holdings --days 30
    uv run python scripts/research_status.py --symbols AMD NVDA GOOG --days 14
    uv run python scripts/research_status.py --holdings --out data/runs/run_123/research_status.json

Exit codes:
    0: All research is fresh (or no symbols to check)
    2: Some research is missing or stale
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Research categories and their paths
RESEARCH_TYPES = {
    "fundamentals": "data/fundamentals",
    "news": "data/news",
    "legal": "data/legal",
}


def parse_iso8601(s: str) -> datetime | None:
    """Parse ISO8601 timestamp string to datetime (UTC)."""
    if not s:
        return None
    try:
        # Handle various ISO8601 formats
        s = s.strip()
        # Replace Z with +00:00 for fromisoformat
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        # Convert to UTC if timezone-aware
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            # Assume UTC if no timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def get_as_of(file_path: Path) -> datetime | None:
    """Extract as_of timestamp from a research JSON file.

    Priority:
    1. JSON field 'as_of' (preferred)
    2. JSON field 'timestamp' (backward compat)
    3. File mtime (fallback)
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        # Try as_of first
        if "as_of" in data and data["as_of"]:
            dt = parse_iso8601(data["as_of"])
            if dt:
                return dt

        # Fallback to timestamp
        if "timestamp" in data and data["timestamp"]:
            dt = parse_iso8601(data["timestamp"])
            if dt:
                return dt
    except (json.JSONDecodeError, IOError):
        pass

    # Final fallback: file mtime
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except OSError:
        return None


def check_symbol_research(symbol_yf: str, threshold_days: int, now: datetime) -> dict:
    """Check research status for a single symbol.

    Returns dict with status for each research type.
    """
    result = {}

    for rtype, rpath in RESEARCH_TYPES.items():
        file_path = Path(rpath) / f"{symbol_yf}.json"

        if not file_path.exists():
            result[rtype] = {
                "status": "missing",
                "as_of": None,
                "age_days": None,
                "path": str(file_path),
            }
            continue

        as_of = get_as_of(file_path)
        if as_of is None:
            # File exists but can't determine age - treat as stale
            result[rtype] = {
                "status": "stale",
                "as_of": None,
                "age_days": None,
                "path": str(file_path),
            }
            continue

        age = now - as_of
        age_days = age.days

        status = "stale" if age_days > threshold_days else "fresh"

        result[rtype] = {
            "status": status,
            "as_of": as_of.isoformat(),
            "age_days": age_days,
            "path": str(file_path),
        }

    return result


def load_holdings_symbols() -> list[str]:
    """Load symbol_yf values from data/holdings.json."""
    holdings_path = Path("data/holdings.json")
    if not holdings_path.exists():
        return []

    try:
        with open(holdings_path, "r") as f:
            holdings = json.load(f)

        symbols = []
        for h in holdings:
            sym = h.get("symbol_yf") or h.get("symbol")
            if sym:
                symbols.append(sym)
        return list(dict.fromkeys(symbols))  # Dedupe preserving order
    except (json.JSONDecodeError, IOError):
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Check freshness of research files (fundamentals, news, legal)."
    )
    parser.add_argument(
        "--holdings",
        action="store_true",
        help="Use symbols from data/holdings.json",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=[],
        help="Additional symbols to check (e.g., AMD NVDA GOOG)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Staleness threshold in days (default: 30)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path for JSON (default: print to stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "md"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    # Collect symbols
    symbols = []
    if args.holdings:
        symbols.extend(load_holdings_symbols())
    if args.symbols:
        symbols.extend(args.symbols)

    # Dedupe
    symbols = list(dict.fromkeys(symbols))

    if not symbols:
        print("No symbols to check. Use --holdings or --symbols.", file=sys.stderr)
        sys.exit(0)

    # Check research
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%d_%H%M%S")

    symbols_status = {}
    summary = {"total_symbols": len(symbols), "missing": 0, "stale": 0, "fresh": 0}

    for sym in symbols:
        status = check_symbol_research(sym, args.days, now)
        symbols_status[sym] = status

        # Aggregate summary
        for rtype, rinfo in status.items():
            if rinfo["status"] == "missing":
                summary["missing"] += 1
            elif rinfo["status"] == "stale":
                summary["stale"] += 1
            else:
                summary["fresh"] += 1

    result = {
        "run_id": run_id,
        "generated_at": now.isoformat(),
        "threshold_days": args.days,
        "symbols": symbols_status,
        "summary": summary,
    }

    # Output
    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        # Markdown format
        lines = [
            f"# Research Status Report",
            f"",
            f"- **Run ID**: {run_id}",
            f"- **Generated**: {now.isoformat()}",
            f"- **Threshold**: {args.days} days",
            f"",
            f"## Summary",
            f"- Total symbols: {summary['total_symbols']}",
            f"- Fresh: {summary['fresh']}",
            f"- Stale: {summary['stale']}",
            f"- Missing: {summary['missing']}",
            f"",
            f"## By Symbol",
            f"",
        ]
        for sym, status in symbols_status.items():
            lines.append(f"### {sym}")
            for rtype, rinfo in status.items():
                age_str = f"{rinfo['age_days']}d" if rinfo['age_days'] is not None else "n/a"
                lines.append(f"- {rtype}: **{rinfo['status']}** (age: {age_str})")
            lines.append("")
        output = "\n".join(lines)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write(output)
        print(f"Wrote research status to {args.out}", file=sys.stderr)
    else:
        print(output)

    # Exit code
    if summary["missing"] > 0 or summary["stale"] > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
