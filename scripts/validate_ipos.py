#!/usr/bin/env python3
"""
Validate IPO database file: data/ipos.json

This script does not fetch anything. It enforces basic schema invariants so
agents can safely update the file without breaking downstream consumers.

Usage:
  uv run python scripts/validate_ipos.py
  uv run python scripts/validate_ipos.py --path data/ipos.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_STATUS = {"UPCOMING", "OPEN", "CLOSED", "LISTED", "WITHDRAWN", "CANCELLED"}


def fail(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def is_iso_date(s: Any) -> bool:
    if s is None:
        return True
    if not isinstance(s, str):
        return False
    # Very light check: YYYY-MM-DD
    parts = s.split("-")
    if len(parts) != 3:
        return False
    return all(p.isdigit() for p in parts) and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2


def validate_root(doc: dict[str, Any]) -> None:
    if not isinstance(doc.get("schema_version"), int):
        fail("schema_version must be int")
    if doc["schema_version"] != 1:
        fail(f"Unsupported schema_version: {doc['schema_version']} (expected 1)")

    if not isinstance(doc.get("file_revision"), int) or doc["file_revision"] < 0:
        fail("file_revision must be int >= 0")

    if "updated_at" in doc and doc["updated_at"] is not None and not isinstance(doc["updated_at"], str):
        fail("updated_at must be string or null")

    ipos = doc.get("ipos")
    if ipos is None:
        fail("ipos missing")
    if not isinstance(ipos, list):
        fail("ipos must be a list")

    if "change_log" in doc and doc["change_log"] is not None and not isinstance(doc["change_log"], list):
        fail("change_log must be a list if present")


def validate_ipo(ipo: dict[str, Any], idx: int, file_revision: int) -> None:
    prefix = f"ipos[{idx}]"
    for k in ["ipo_id", "company_name", "segment", "status", "dates", "exchange"]:
        if k not in ipo:
            fail(f"{prefix}: missing required field: {k}")

    if not isinstance(ipo["ipo_id"], str) or not ipo["ipo_id"].strip():
        fail(f"{prefix}.ipo_id must be non-empty string")
    if not isinstance(ipo["company_name"], str) or not ipo["company_name"].strip():
        fail(f"{prefix}.company_name must be non-empty string")
    if not isinstance(ipo["segment"], str) or not ipo["segment"].strip():
        fail(f"{prefix}.segment must be non-empty string")

    status = ipo["status"]
    if not isinstance(status, str) or status not in ALLOWED_STATUS:
        fail(f"{prefix}.status must be one of: {sorted(ALLOWED_STATUS)}")

    exch = ipo["exchange"]
    if not isinstance(exch, list) or not all(isinstance(x, str) and x.strip() for x in exch):
        fail(f"{prefix}.exchange must be a list of strings")

    dates = ipo["dates"]
    if not isinstance(dates, dict):
        fail(f"{prefix}.dates must be an object")
    for dk in ["open", "close", "allotment", "listing"]:
        if dk in dates and not is_iso_date(dates.get(dk)):
            fail(f"{prefix}.dates.{dk} must be YYYY-MM-DD or null")

    # Optional: price_band
    if "price_band" in ipo and ipo["price_band"] is not None:
        pb = ipo["price_band"]
        if not isinstance(pb, dict):
            fail(f"{prefix}.price_band must be object or null")
        for pk in ["low", "high"]:
            if pk in pb and pb[pk] is not None and not isinstance(pb[pk], (int, float)):
                fail(f"{prefix}.price_band.{pk} must be number or null")
        if "currency" in pb and pb["currency"] is not None and not isinstance(pb["currency"], str):
            fail(f"{prefix}.price_band.currency must be string or null")

    # Versioning fields (recommended; keep flexible but consistent)
    if "record_revision" in ipo:
        if not isinstance(ipo["record_revision"], int) or ipo["record_revision"] < 0:
            fail(f"{prefix}.record_revision must be int >= 0")
    if "change_log" in ipo and ipo["change_log"] is not None:
        if not isinstance(ipo["change_log"], list):
            fail(f"{prefix}.change_log must be a list")
        # Ensure IPO-level change_log file_revision doesn't exceed file_revision.
        for j, cl in enumerate(ipo["change_log"]):
            if not isinstance(cl, dict):
                fail(f"{prefix}.change_log[{j}] must be object")
            fr = cl.get("file_revision")
            if fr is not None and (not isinstance(fr, int) or fr > file_revision):
                fail(f"{prefix}.change_log[{j}].file_revision must be int <= root.file_revision")


def validate_unique_ids(ipos: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for ipo in ipos:
        ipo_id = str(ipo.get("ipo_id") or "").strip()
        if not ipo_id:
            continue
        if ipo_id in seen:
            fail(f"Duplicate ipo_id: {ipo_id}")
        seen.add(ipo_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate data/ipos.json schema.")
    parser.add_argument("--path", default="data/ipos.json", help="Path to IPO db (default: data/ipos.json)")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        fail(f"File not found: {path}")

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"Invalid JSON: {e}")

    if not isinstance(doc, dict):
        fail("Root must be an object")

    validate_root(doc)
    file_revision = int(doc["file_revision"])

    ipos = doc.get("ipos") or []
    for idx, ipo in enumerate(ipos):
        if not isinstance(ipo, dict):
            fail(f"ipos[{idx}] must be an object")
        validate_ipo(ipo, idx, file_revision=file_revision)

    validate_unique_ids(ipos)
    print(f"OK: {path} (ipos: {len(ipos)}, file_revision: {file_revision})")


if __name__ == "__main__":
    main()

