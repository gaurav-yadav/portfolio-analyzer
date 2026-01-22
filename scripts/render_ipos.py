#!/usr/bin/env python3
"""
Render IPO database (data/ipos.json) into a human-readable report.

Usage:
  uv run python scripts/render_ipos.py
  uv run python scripts/render_ipos.py --out output/ipos.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_date(d: Any) -> str:
    if not isinstance(d, str) or not d:
        return ""
    return d


def render_md(doc: dict[str, Any]) -> str:
    ipos = doc.get("ipos") or []
    if not isinstance(ipos, list):
        ipos = []

    active = [i for i in ipos if isinstance(i, dict) and str(i.get("status") or "") in {"UPCOMING", "OPEN", "CLOSED"}]
    inactive = [i for i in ipos if isinstance(i, dict) and i not in active]

    def sort_key(i: dict[str, Any]) -> tuple:
        dates = i.get("dates") or {}
        open_d = parse_date(dates.get("open")) if isinstance(dates, dict) else ""
        return (open_d or "9999-99-99", str(i.get("company_name") or ""))

    active.sort(key=sort_key)
    inactive.sort(key=sort_key)

    lines: list[str] = []
    lines.append("# IPO Report")
    lines.append("")
    lines.append(f"- Updated at: {doc.get('updated_at') or ''}")
    lines.append(f"- File revision: {doc.get('file_revision')}")
    lines.append("")

    def fmt_price_band(pb: Any) -> str:
        if not isinstance(pb, dict):
            return ""
        lo = pb.get("low")
        hi = pb.get("high")
        cur = pb.get("currency") or "INR"
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            return f"{cur} {lo:.0f}-{hi:.0f}"
        if isinstance(hi, (int, float)):
            return f"{cur} up to {hi:.0f}"
        return ""

    def fmt_issue_size(i: dict[str, Any]) -> str:
        v = i.get("issue_size_cr")
        if isinstance(v, (int, float)):
            return f"{v:.0f} cr"
        return ""

    def fmt_score(i: dict[str, Any]) -> str:
        score = i.get("score") or {}
        if not isinstance(score, dict):
            return ""
        overall = score.get("overall")
        verdict = score.get("verdict")
        conf = score.get("confidence")
        parts: list[str] = []
        if isinstance(overall, (int, float)):
            parts.append(f"{overall:.1f}/10")
        if isinstance(verdict, str) and verdict:
            parts.append(verdict)
        if isinstance(conf, str) and conf:
            parts.append(conf)
        return " · ".join(parts)

    def render_table(title: str, items: list[dict[str, Any]]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("_None_")
            lines.append("")
            return

        lines.append("| Company | Status | Open | Close | Price band | Lot | Issue size | Score |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---|")
        for i in items:
            company = str(i.get("company_name") or "")
            status = str(i.get("status") or "")
            dates = i.get("dates") or {}
            open_d = parse_date(dates.get("open")) if isinstance(dates, dict) else ""
            close_d = parse_date(dates.get("close")) if isinstance(dates, dict) else ""
            pb = fmt_price_band(i.get("price_band"))
            lot = i.get("lot_size")
            lot_s = f"{int(lot)}" if isinstance(lot, int) else ""
            issue = fmt_issue_size(i)
            score = fmt_score(i)
            lines.append(f"| {company} | {status} | {open_d} | {close_d} | {pb} | {lot_s} | {issue} | {score} |")
        lines.append("")

    render_table("Active IPOs (UPCOMING/OPEN/CLOSED)", active)
    render_table("Inactive IPOs (LISTED/WITHDRAWN/CANCELLED)", inactive)

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render data/ipos.json to a markdown report.")
    parser.add_argument("--path", default="data/ipos.json", help="Path to IPO db (default: data/ipos.json)")
    parser.add_argument("--out", default="", help="Output markdown file (default: output/ipos_<timestamp>.md)")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"Error: File not found: {path}")

    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("Error: root must be an object")

    md = render_md(doc)
    if args.out:
        out = Path(args.out)
    else:
        out = Path("output") / f"ipos_{now_stamp()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()

