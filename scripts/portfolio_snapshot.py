#!/usr/bin/env python3
"""
Portfolio Snapshot - persist a portfolio run as a JSON snapshot (deterministic).

This script is a lightweight "state recorder" for job #2 (portfolios):
  - Reads current `data/scores/*.json` outputs
  - Computes portfolio-level summary stats
  - Writes a timestamped (or run-id) snapshot under:
      data/portfolios/<portfolio_id>/snapshots/<run_id>.json

It does NOT fetch data, run agents, or compute indicators.

Usage:
  uv run python scripts/portfolio_snapshot.py --portfolio-id gaurav-india-kite
  uv run python scripts/portfolio_snapshot.py --portfolio-id gaurav-india-kite --run-id 20260121_103000
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import save_json  # noqa: E402


BASE_PATH = Path(__file__).parent.parent


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def default_run_id(ts_iso: str | None = None) -> str:
    if ts_iso:
        try:
            dt = datetime.fromisoformat(ts_iso)
            return dt.strftime("%Y%m%d_%H%M%S")
        except Exception:
            pass
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s or s.upper() in {"N/A", "NA", "NONE", "NULL", "-"}:
            return None
        return float(s.replace(",", "").replace("%", ""))
    except Exception:
        return None


@dataclass(frozen=True)
class ScoreRow:
    symbol_yf: str
    broker: str
    name: str
    quantity: float
    avg_price: float
    current_price: float | None
    pnl_pct: float | None
    overall_score: float | None
    recommendation: str
    confidence: str
    coverage: str
    gate_flags: str
    summary: str

    @property
    def invested_value(self) -> float:
        return self.quantity * self.avg_price

    @property
    def market_value(self) -> float | None:
        if self.current_price is None:
            return None
        return self.quantity * self.current_price


def load_score_files(scores_dir: Path) -> list[dict[str, Any]]:
    if not scores_dir.exists():
        return []
    files = sorted(scores_dir.glob("*.json"))
    rows: list[dict[str, Any]] = []
    for fp in files:
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def normalize_score_row(raw: dict[str, Any]) -> ScoreRow | None:
    symbol_yf = str(raw.get("symbol_yf") or "").strip().upper()
    if not symbol_yf:
        # Fallback: for some legacy formats
        symbol_yf = str(raw.get("symbol") or "").strip().upper()
    if not symbol_yf:
        return None

    broker = str(raw.get("broker") or "unknown").strip().lower() or "unknown"
    name = str(raw.get("name") or "").strip() or symbol_yf

    qty = safe_float(raw.get("quantity")) or 0.0
    avg = safe_float(raw.get("avg_price")) or 0.0
    if qty <= 0 or avg <= 0:
        return None

    current_price = safe_float(raw.get("current_price"))
    pnl_pct = safe_float(raw.get("pnl_pct"))
    overall_score = safe_float(raw.get("overall_score"))

    recommendation = str(raw.get("recommendation") or "").strip() or "UNKNOWN"
    confidence = str(raw.get("confidence") or "").strip() or "N/A"
    coverage = str(raw.get("coverage") or "").strip() or ""
    gate_flags = str(raw.get("gate_flags") or "").strip() or ""
    summary = str(raw.get("summary") or "").strip() or ""

    return ScoreRow(
        symbol_yf=symbol_yf,
        broker=broker,
        name=name,
        quantity=float(qty),
        avg_price=float(avg),
        current_price=current_price,
        pnl_pct=pnl_pct,
        overall_score=overall_score,
        recommendation=recommendation,
        confidence=confidence,
        coverage=coverage,
        gate_flags=gate_flags,
        summary=summary,
    )


def find_previous_snapshot(snapshot_dir: Path, current_run_id: str) -> Path | None:
    if not snapshot_dir.exists():
        return None
    snaps = sorted(snapshot_dir.glob("*.json"))
    snaps = [s for s in snaps if s.stem != current_run_id]
    return snaps[-1] if snaps else None


def compute_delta(prev: dict[str, Any] | None, current_rows: list[ScoreRow]) -> dict[str, Any]:
    if not prev:
        return {"has_previous": False}

    prev_rows = prev.get("rows") or []
    prev_map: dict[tuple[str, str], dict[str, Any]] = {}
    if isinstance(prev_rows, list):
        for r in prev_rows:
            if not isinstance(r, dict):
                continue
            key = (str(r.get("symbol_yf") or "").upper(), str(r.get("broker") or "unknown").lower())
            if key[0]:
                prev_map[key] = r

    cur_map = {(r.symbol_yf, r.broker): r for r in current_rows}

    added = [k for k in cur_map.keys() if k not in prev_map]
    removed = [k for k in prev_map.keys() if k not in cur_map]

    rec_changes: list[dict[str, Any]] = []
    score_changes: list[dict[str, Any]] = []

    for key, cur in cur_map.items():
        prev_r = prev_map.get(key)
        if not prev_r:
            continue
        prev_rec = str(prev_r.get("recommendation") or "")
        if prev_rec and prev_rec != cur.recommendation:
            rec_changes.append(
                {
                    "symbol_yf": cur.symbol_yf,
                    "broker": cur.broker,
                    "from": prev_rec,
                    "to": cur.recommendation,
                }
            )

        prev_score = safe_float(prev_r.get("overall_score"))
        if prev_score is not None and cur.overall_score is not None:
            delta = round(cur.overall_score - prev_score, 2)
            if abs(delta) >= 0.5:
                score_changes.append(
                    {
                        "symbol_yf": cur.symbol_yf,
                        "broker": cur.broker,
                        "delta": delta,
                        "from": prev_score,
                        "to": cur.overall_score,
                    }
                )

    score_changes.sort(key=lambda x: abs(float(x.get("delta") or 0)), reverse=True)

    return {
        "has_previous": True,
        "previous_run_id": prev.get("run_id"),
        "added": [{"symbol_yf": s, "broker": b} for (s, b) in added],
        "removed": [{"symbol_yf": s, "broker": b} for (s, b) in removed],
        "recommendation_changes": rec_changes,
        "score_changes": score_changes[:25],
    }


def build_snapshot(portfolio_id: str, run_id: str, as_of: str, rows: list[ScoreRow], prev: dict[str, Any] | None) -> dict[str, Any]:
    invested = sum(r.invested_value for r in rows)
    market_values = [r.market_value for r in rows if r.market_value is not None]
    market = sum(market_values) if market_values else None

    pnl = (market - invested) if (market is not None and invested > 0) else None
    pnl_pct = (pnl / invested * 100) if (pnl is not None and invested > 0) else None

    score_vals = [r.overall_score for r in rows if r.overall_score is not None]
    avg_score = round(sum(score_vals) / len(score_vals), 2) if score_vals else None

    dist: dict[str, int] = {}
    gated = 0
    for r in rows:
        dist[r.recommendation] = dist.get(r.recommendation, 0) + 1
        if r.gate_flags:
            gated += 1

    top = sorted([r for r in rows if r.overall_score is not None], key=lambda r: float(r.overall_score or 0), reverse=True)
    worst = list(reversed(top)) if top else []

    snapshot_rows: list[dict[str, Any]] = []
    for r in rows:
        snapshot_rows.append(
            {
                "symbol_yf": r.symbol_yf,
                "broker": r.broker,
                "name": r.name,
                "quantity": r.quantity,
                "avg_price": r.avg_price,
                "current_price": r.current_price,
                "pnl_pct": r.pnl_pct,
                "overall_score": r.overall_score,
                "recommendation": r.recommendation,
                "confidence": r.confidence,
                "coverage": r.coverage,
                "gate_flags": r.gate_flags,
                "summary": r.summary,
            }
        )

    snapshot_rows.sort(key=lambda x: (str(x.get("broker") or ""), str(x.get("symbol_yf") or "")))

    return {
        "schema_version": 1,
        "portfolio_id": portfolio_id,
        "run_id": run_id,
        "as_of": as_of,
        "summary": {
            "holdings": len(rows),
            "invested_value": round(invested, 2) if invested else 0.0,
            "market_value": round(market, 2) if market is not None else None,
            "pnl_value": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            "avg_score": avg_score,
            "recommendation_distribution": dist,
            "gated_recommendations": gated,
            "top_symbols": [t.symbol_yf for t in top[:5]],
            "worst_symbols": [w.symbol_yf for w in worst[:5]],
        },
        "delta": compute_delta(prev, rows),
        "rows": snapshot_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a portfolio snapshot from current score files.")
    parser.add_argument("--portfolio-id", default="default", help="Portfolio ID (default: default)")
    parser.add_argument("--run-id", default="", help="Run ID (default: derived from as_of)")
    parser.add_argument("--as-of", default="", help="As-of ISO timestamp (default: now)")
    parser.add_argument("--scores-dir", default="data/scores", help="Scores directory (default: data/scores)")
    parser.add_argument("--out", default="", help="Output path (default: data/portfolios/<id>/snapshots/<run_id>.json)")
    args = parser.parse_args()

    portfolio_id = args.portfolio_id.strip() or "default"
    as_of = args.as_of or now_iso()
    run_id = args.run_id or default_run_id(as_of)

    scores_dir = BASE_PATH / args.scores_dir
    raw_scores = load_score_files(scores_dir)
    rows: list[ScoreRow] = []
    for raw in raw_scores:
        r = normalize_score_row(raw)
        if r is not None:
            rows.append(r)

    if not rows:
        print(f"Error: no usable score files found in {scores_dir}", file=sys.stderr)
        raise SystemExit(1)

    snapshot_dir = BASE_PATH / "data" / "portfolios" / portfolio_id / "snapshots"
    prev_path = find_previous_snapshot(snapshot_dir, current_run_id=run_id)
    prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path else None

    snapshot = build_snapshot(portfolio_id=portfolio_id, run_id=run_id, as_of=as_of, rows=rows, prev=prev)

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = BASE_PATH / out_path
    else:
        out_path = snapshot_dir / f"{run_id}.json"

    save_json(out_path, snapshot)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

