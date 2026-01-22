#!/usr/bin/env python3
"""
Portfolio Report Archive - archive and list portfolio markdown reports (deterministic).

This script handles report archiving for job #2 (portfolios):
  - Copies (not moves) a markdown report to a dated archive directory
  - Lists existing archived reports sorted newest-first
  - Uses human-friendly filenames: DD-MM-YYYY-<portfolio-slug>.md

It does NOT fetch data, parse report content, or run agents.

Usage:
  # Archive current report + list all
  uv run python scripts/portfolio_report_archive.py --portfolio-id gaurav-us-kuvera

  # List only (no archiving)
  uv run python scripts/portfolio_report_archive.py --portfolio-id gaurav-us-kuvera --list

  # JSON output
  uv run python scripts/portfolio_report_archive.py --portfolio-id gaurav-us-kuvera --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def portfolio_slug(portfolio_id: str) -> str:
    """Convert portfolio_id to filename-safe slug."""
    return portfolio_id.replace("_", "-").replace(" ", "")


def archive_filename(portfolio_id: str, as_of: datetime) -> str:
    """Generate archive filename: DD-MM-YYYY-<slug>.md"""
    slug = portfolio_slug(portfolio_id)
    date_str = as_of.strftime("%d-%m-%Y")
    return f"{date_str}-{slug}.md"


def find_unique_path(out_dir: Path, base_name: str) -> Path:
    """Find unique path, appending -2, -3, etc. if needed."""
    stem = base_name.rsplit(".", 1)[0]
    ext = ".md"
    candidate = out_dir / base_name
    counter = 2
    while candidate.exists():
        candidate = out_dir / f"{stem}-{counter}{ext}"
        counter += 1
    return candidate


def list_reports(reports_dir: Path) -> list[dict[str, str]]:
    """List archived reports sorted newest-first by mtime."""
    if not reports_dir.exists():
        return []
    files = list(reports_dir.glob("*.md"))
    report_list: list[dict[str, str]] = []
    for fp in files:
        try:
            mtime = fp.stat().st_mtime
            mtime_iso = datetime.fromtimestamp(mtime).astimezone().replace(microsecond=0).isoformat()
        except Exception:
            mtime = 0.0
            mtime_iso = ""
        report_list.append({
            "name": fp.name,
            "path": str(fp),
            "mtime_iso": mtime_iso,
            "_mtime": mtime,
        })
    report_list.sort(key=lambda x: x.get("_mtime", 0), reverse=True)
    for r in report_list:
        r.pop("_mtime", None)
    return report_list


def archive_report(
    portfolio_id: str,
    src_path: Path,
    out_dir: Path,
    as_of: datetime,
    run_id: str | None = None,
) -> dict[str, str | list]:
    """Archive report and return result dict."""
    if not src_path.exists():
        return {"error": f"Source report not found: {src_path}"}

    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = archive_filename(portfolio_id, as_of)
    dest_path = find_unique_path(out_dir, base_name)

    shutil.copy2(src_path, dest_path)

    reports = list_reports(out_dir)

    result: dict[str, str | list] = {
        "archived_path": str(dest_path),
        "latest_path": str(src_path),
        "reports": reports,
    }
    if run_id:
        result["run_id"] = run_id

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive and list portfolio markdown reports.")
    parser.add_argument("--portfolio-id", required=True, help="Portfolio ID")
    parser.add_argument("--src", default="", help="Source report path (default: data/portfolios/<id>/report.md)")
    parser.add_argument("--out-dir", default="", help="Output directory (default: data/portfolios/<id>/reports)")
    parser.add_argument("--as-of", default="", help="As-of ISO timestamp for naming (default: now)")
    parser.add_argument("--run-id", default="", help="Optional run ID for metadata")
    parser.add_argument("--list", dest="list_only", action="store_true", help="Only list reports, don't archive")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    portfolio_id = args.portfolio_id.strip()
    if not portfolio_id:
        print("Error: --portfolio-id is required", file=sys.stderr)
        raise SystemExit(1)

    portfolio_dir = BASE_PATH / "data" / "portfolios" / portfolio_id

    if args.src:
        src_path = Path(args.src)
        if not src_path.is_absolute():
            src_path = BASE_PATH / src_path
    else:
        src_path = portfolio_dir / "report.md"

    if args.out_dir:
        out_dir = Path(args.out_dir)
        if not out_dir.is_absolute():
            out_dir = BASE_PATH / out_dir
    else:
        out_dir = portfolio_dir / "reports"

    if args.as_of:
        try:
            as_of = datetime.fromisoformat(args.as_of)
        except ValueError:
            print(f"Error: invalid --as-of timestamp: {args.as_of}", file=sys.stderr)
            raise SystemExit(1)
    else:
        as_of = datetime.now().astimezone()

    run_id = args.run_id.strip() or None

    if args.list_only:
        reports = list_reports(out_dir)
        result = {"reports": reports}
    else:
        result = archive_report(
            portfolio_id=portfolio_id,
            src_path=src_path,
            out_dir=out_dir,
            as_of=as_of,
            run_id=run_id,
        )

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            raise SystemExit(1)

        if not args.list_only:
            print(f"Archived: {result.get('archived_path')}")
            print(f"Latest:   {result.get('latest_path')}")
            print()

        reports = result.get("reports", [])
        if reports:
            print(f"Archived reports ({len(reports)}):")
            for r in reports:
                print(f"  - {r['name']}  ({r['mtime_iso']})")
        else:
            print("No archived reports found.")


if __name__ == "__main__":
    main()
