#!/usr/bin/env python3
"""
Watchlist Report - summarize watchlist snapshots over time (deterministic).

Inputs:
  - data/watchlists/<watchlist_id>/snapshots/*.json (written by watchlist_snapshot.py)

Outputs:
  - data/watchlists/<watchlist_id>/reports/history_<timestamp>.csv
  - data/watchlists/<watchlist_id>/reports/summary_<timestamp>.json

Usage:
  uv run python scripts/watchlist_report.py <watchlist_id>
  uv run python scripts/watchlist_report.py <watchlist_id> --out-csv output/watchlist_<id>.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_PATH = Path(__file__).parent.parent


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace("%", "").replace(",", "")
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def load_snapshots(snapshot_dir: Path) -> list[dict[str, Any]]:
    if not snapshot_dir.exists():
        return []
    snaps: list[dict[str, Any]] = []
    for fp in sorted(snapshot_dir.glob("*.json")):
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict):
            snaps.append(obj)
    return snaps


def build_history_rows(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        run_id = str(snap.get("run_id") or "")
        as_of = str(snap.get("as_of") or "")
        for r in (snap.get("rows") or []):
            if not isinstance(r, dict):
                continue
            rows.append(
                {
                    "run_id": run_id,
                    "as_of": as_of,
                    "symbol_yf": str(r.get("symbol_yf") or ""),
                    "close": safe_float(r.get("close")),
                    "watch_return_pct": safe_float(r.get("watch_return_pct")),
                    "trend": str(r.get("trend") or ""),
                    "flags": ",".join(r.get("flags") or []) if isinstance(r.get("flags"), list) else "",
                }
            )
    # Stable ordering
    rows.sort(key=lambda x: (x.get("as_of") or "", x.get("symbol_yf") or ""))
    return rows


def build_summary(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {"snapshots": 0}

    first = snapshots[0]
    last = snapshots[-1]

    last_rows = last.get("rows") or []
    if not isinstance(last_rows, list):
        last_rows = []

    perf: list[dict[str, Any]] = []
    flags_rank: list[dict[str, Any]] = []

    for r in last_rows:
        if not isinstance(r, dict):
            continue
        symbol_yf = str(r.get("symbol_yf") or "")
        ret = safe_float(r.get("watch_return_pct"))
        flags = r.get("flags") if isinstance(r.get("flags"), list) else []
        perf.append({"symbol_yf": symbol_yf, "watch_return_pct": ret})
        flags_rank.append({"symbol_yf": symbol_yf, "flags": flags, "flags_count": len(flags)})

    perf_valid = [p for p in perf if isinstance(p.get("watch_return_pct"), (int, float))]
    perf_valid.sort(key=lambda x: float(x.get("watch_return_pct") or 0), reverse=True)

    flags_rank.sort(key=lambda x: int(x.get("flags_count") or 0), reverse=True)

    return {
        "schema_version": 1,
        "snapshots": len(snapshots),
        "first_as_of": first.get("as_of"),
        "last_as_of": last.get("as_of"),
        "last_run_id": last.get("run_id"),
        "symbols_last_snapshot": len(last_rows),
        "top_returns": perf_valid[:10],
        "worst_returns": list(reversed(perf_valid[-10:])) if perf_valid else [],
        "most_flagged": flags_rank[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render watchlist snapshots into a simple history report.")
    parser.add_argument("watchlist_id", help="Watchlist identifier (folder name)")
    parser.add_argument("--out-csv", default="", help="Output CSV path (default: data/watchlists/<id>/reports/history_<ts>.csv)")
    parser.add_argument("--out-json", default="", help="Output JSON path (default: data/watchlists/<id>/reports/summary_<ts>.json)")
    args = parser.parse_args()

    snapshot_dir = BASE_PATH / "data" / "watchlists" / args.watchlist_id / "snapshots"
    snapshots = load_snapshots(snapshot_dir)
    if not snapshots:
        raise SystemExit(f"Error: no snapshots found in {snapshot_dir}. Run scripts/watchlist_snapshot.py first.")

    stamp = now_stamp()
    reports_dir = BASE_PATH / "data" / "watchlists" / args.watchlist_id / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_csv = Path(args.out_csv) if args.out_csv else (reports_dir / f"history_{stamp}.csv")
    out_json = Path(args.out_json) if args.out_json else (reports_dir / f"summary_{stamp}.json")
    if not out_csv.is_absolute():
        out_csv = BASE_PATH / out_csv
    if not out_json.is_absolute():
        out_json = BASE_PATH / out_json

    history_rows = build_history_rows(snapshots)
    summary = build_summary(snapshots)

    # Write CSV
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["run_id", "as_of", "symbol_yf", "close", "watch_return_pct", "trend", "flags"],
        )
        writer.writeheader()
        writer.writerows(history_rows)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_json}")


if __name__ == "__main__":
    main()

