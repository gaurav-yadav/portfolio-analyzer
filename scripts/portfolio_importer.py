#!/usr/bin/env python3
"""
Universal Portfolio Importer - normalize arbitrary holdings exports into canonical holdings JSON.

Why:
  - Common CSV/TSV exports are cheap to import deterministically (repeatable + auditable).
  - For messy inputs (PDF/Excel/images), let an agent extract holdings into JSON,
    then run a deterministic validator/normalizer (`scripts/holdings_validate.py`).
  - This importer writes both portfolio-scoped holdings and the legacy compatibility copy.

Outputs:
  1) data/portfolios/<portfolio_id>/holdings.json
  2) data/holdings.json (compatibility copy for existing pipeline)
  3) data/portfolios/<portfolio_id>/import_notes.md (audit trail)

Usage:
  uv run python scripts/portfolio_importer.py --portfolio-id gaurav-india-kite --country india --platform kite input/zerodha.csv
  uv run python scripts/portfolio_importer.py --portfolio-id gaurav-us-vested --country us --platform vested input/vested.csv
"""

from __future__ import annotations

import argparse
import csv
import re
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


def normalize_header(h: str) -> str:
    h = (h or "").strip().lower()
    h = re.sub(r"[^a-z0-9]+", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def clean_numeric_any(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() in {"N/A", "NA", "NONE", "NULL", "-"}:
        return None
    # Handle parentheses negatives: (123.45)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    # Strip currency + separators
    s = s.replace("₹", "").replace("$", "")
    s = re.sub(r"\bINR\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bUSD\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bRs\.?\b", "", s, flags=re.IGNORECASE)
    s = s.replace(",", "").replace("%", "").strip()
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return None


def infer_country_from_portfolio_id(portfolio_id: str) -> str | None:
    pid = (portfolio_id or "").lower()
    if "-india-" in pid or pid.endswith("-india") or pid.startswith("india-"):
        return "india"
    if "-us-" in pid or pid.endswith("-us") or pid.startswith("us-"):
        return "us"
    return None


def normalize_us_symbol(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    # Yahoo uses BRK-B style for class shares
    if "." in t:
        t = t.replace(".", "-")
    return t


def normalize_symbol(country: str, symbol_raw: str, default_suffix: str) -> tuple[str, str]:
    """
    Returns (symbol, symbol_yf).
    - symbol: exchange-less stable ticker
    - symbol_yf: Yahoo Finance compatible ticker
    """
    raw = (symbol_raw or "").strip().upper()
    if not raw:
        return "", ""

    if country == "us":
        yf = normalize_us_symbol(raw)
        return yf, yf

    # India default
    if "." in raw:
        yf = raw
        sym = raw.split(".", 1)[0]
        return sym, yf

    sym = raw
    yf = f"{raw}{default_suffix}" if default_suffix else raw
    return sym, yf


@dataclass(frozen=True)
class ColumnMap:
    symbol: str
    name: str | None
    quantity: str
    avg_price: str
    current_price: str | None
    market_value: str | None
    invested: str | None


def pick_column(headers: list[str], candidates: list[str]) -> str | None:
    """
    Pick the first header that matches any candidate token.
    candidates are normalized header strings (partial match).
    """
    norm_map = {h: normalize_header(h) for h in headers}
    for cand in candidates:
        cand_n = normalize_header(cand)
        for orig, norm in norm_map.items():
            if cand_n and cand_n in norm:
                return orig
    return None


def detect_columns(headers: list[str]) -> ColumnMap:
    """
    Heuristic column mapping across common exports.

    Required: symbol, quantity, avg_price.
    """
    symbol = pick_column(headers, ["symbol", "ticker", "instrument", "trading symbol", "tradingsymbol", "security", "scrip"])
    quantity = pick_column(headers, ["quantity", "qty", "shares", "units"])
    avg_price = pick_column(headers, ["avg cost", "avg. cost", "average cost", "avg price", "average price", "buy price", "cost price"])

    name = pick_column(headers, ["company name", "security name", "name", "company", "description"])
    current_price = pick_column(headers, ["ltp", "current price", "market price", "price"])
    market_value = pick_column(headers, ["market value", "current value", "value"])
    invested = pick_column(headers, ["invested", "cost basis", "investment", "cost value"])

    if not symbol or not quantity or not avg_price:
        raise ValueError(
            "Could not detect required columns. "
            f"Detected: symbol={symbol}, quantity={quantity}, avg_price={avg_price}. "
            f"Headers: {headers}"
        )

    return ColumnMap(
        symbol=symbol,
        name=name,
        quantity=quantity,
        avg_price=avg_price,
        current_price=current_price,
        market_value=market_value,
        invested=invested,
    )


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    content = None
    used_encoding = None
    for enc in encodings:
        try:
            content = path.read_text(encoding=enc)
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError(f"Could not decode {path} with known encodings")

    # Detect delimiter
    sample = content[:8192]
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=[",", "\t", ";", "|"])
    except Exception:
        dialect = csv.get_dialect("excel")

    rows: list[dict[str, str]] = []
    reader = csv.DictReader(content.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError(f"No headers found in {path}")

    for r in reader:
        if not r or not any((v or "").strip() for v in r.values()):
            continue
        rows.append({k: (v or "").strip() for k, v in r.items()})

    if not rows:
        raise ValueError(f"No data rows found in {path}")

    return rows, (used_encoding or "unknown")


def build_import_notes(
    *,
    portfolio_id: str,
    country: str,
    platform: str,
    files: list[Path],
    mappings: dict[str, ColumnMap],
    delimiter_notes: dict[str, str],
    stats: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# Import Notes — {portfolio_id}")
    lines.append("")
    lines.append(f"- Imported at: {now_iso()}")
    lines.append(f"- Country: `{country}`")
    lines.append(f"- Platform/broker: `{platform}`")
    lines.append("")
    lines.append("## Source Files")
    for f in files:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## Parsing Notes")
    for f in files:
        enc = delimiter_notes.get(str(f), "unknown")
        lines.append(f"- `{f}`: encoding `{enc}` (delimiter autodetected)")
    lines.append("")
    lines.append("## Column Mappings")
    for f in files:
        m = mappings.get(str(f))
        if not m:
            continue
        lines.append(f"### `{f.name}`")
        lines.append(f"- symbol: `{m.symbol}`")
        lines.append(f"- quantity: `{m.quantity}`")
        lines.append(f"- avg_price: `{m.avg_price}`")
        if m.name:
            lines.append(f"- name: `{m.name}`")
        if m.current_price:
            lines.append(f"- current_price: `{m.current_price}`")
        if m.market_value:
            lines.append(f"- market_value: `{m.market_value}`")
        if m.invested:
            lines.append(f"- invested/cost_basis: `{m.invested}`")
        lines.append("")
    lines.append("## Stats")
    for k, v in stats.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Universal portfolio holdings importer (deterministic).")
    parser.add_argument("--portfolio-id", required=True, help="Portfolio ID (e.g., gaurav-india-kite)")
    parser.add_argument("--country", default="", choices=["", "india", "us"], help="india/us (inferred from portfolio_id if omitted)")
    parser.add_argument("--platform", required=True, help="Platform/broker label (e.g., kite, groww, vested)")
    parser.add_argument("--default-suffix", default=".NS", help="Default suffix for India tickers without suffix (default: .NS)")
    parser.add_argument("files", nargs="+", help="One or more holdings export files (CSV/TSV)")
    args = parser.parse_args()

    portfolio_id = args.portfolio_id.strip()
    if not portfolio_id:
        raise SystemExit("Error: --portfolio-id is required")

    country = (args.country or "").strip()
    if not country:
        inferred = infer_country_from_portfolio_id(portfolio_id)
        if not inferred:
            raise SystemExit("Error: --country missing and could not infer from --portfolio-id")
        country = inferred

    platform = args.platform.strip()
    if not platform:
        raise SystemExit("Error: --platform is required")

    file_paths = [Path(f) for f in args.files]

    mappings: dict[str, ColumnMap] = {}
    delimiter_notes: dict[str, str] = {}

    holdings_raw: list[dict[str, Any]] = []
    scanned_rows = 0

    for fp in file_paths:
        rows, enc = read_csv_rows(fp)
        delimiter_notes[str(fp)] = enc
        scanned_rows += len(rows)

        headers = list(rows[0].keys())
        cmap = detect_columns(headers)
        mappings[str(fp)] = cmap

        for r in rows:
            sym_raw = r.get(cmap.symbol, "")
            qty = clean_numeric_any(r.get(cmap.quantity))
            avg = clean_numeric_any(r.get(cmap.avg_price))
            if qty is None or avg is None:
                continue
            if qty <= 0 or avg <= 0:
                continue

            sym, sym_yf = normalize_symbol(country, sym_raw, args.default_suffix)
            if not sym_yf:
                continue

            name = (r.get(cmap.name, "") if cmap.name else "").strip() or sym
            current_price = clean_numeric_any(r.get(cmap.current_price)) if cmap.current_price else None
            market_value = clean_numeric_any(r.get(cmap.market_value)) if cmap.market_value else None
            invested = clean_numeric_any(r.get(cmap.invested)) if cmap.invested else None

            holding: dict[str, Any] = {
                "portfolio_id": portfolio_id,
                "country": country,
                "platform": platform,
                "broker": platform,
                "symbol": sym,
                "symbol_yf": sym_yf,
                "name": name,
                "quantity": float(qty),
                "avg_price": float(avg),
            }

            if country == "india":
                holding["currency"] = "INR"
            elif country == "us":
                holding["currency"] = "USD"

            if current_price is not None:
                holding["current_price"] = float(current_price)
            if market_value is not None:
                holding["market_value"] = float(market_value)
            if invested is not None:
                holding["invested"] = float(invested)

            holdings_raw.append(holding)

    if not holdings_raw:
        raise SystemExit("Error: no holdings parsed (check CSV format and required columns)")

    # Deduplicate: (symbol_yf, broker) -> aggregate qty and weighted avg_price
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    for h in holdings_raw:
        key = (h["symbol_yf"], h.get("broker") or platform)
        if key not in agg:
            agg[key] = dict(h)
            continue
        existing = agg[key]
        old_qty = float(existing.get("quantity") or 0)
        old_avg = float(existing.get("avg_price") or 0)
        new_qty = float(h.get("quantity") or 0)
        new_avg = float(h.get("avg_price") or 0)
        total_qty = old_qty + new_qty
        if total_qty > 0 and old_avg > 0 and new_avg > 0:
            existing["avg_price"] = round((old_qty * old_avg + new_qty * new_avg) / total_qty, 6)
        existing["quantity"] = total_qty

        # Prefer name if missing
        if not existing.get("name") and h.get("name"):
            existing["name"] = h["name"]

    holdings = list(agg.values())
    holdings.sort(key=lambda x: (str(x.get("broker") or ""), str(x.get("symbol_yf") or "")))

    # Validation
    for h in holdings:
        if not h.get("symbol_yf") or (h.get("quantity") or 0) <= 0 or (h.get("avg_price") or 0) <= 0:
            raise SystemExit(f"Error: invalid holding record: {h}")

    portfolio_dir = BASE_PATH / "data" / "portfolios" / portfolio_id
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    out_portfolio_holdings = portfolio_dir / "holdings.json"
    out_compat_holdings = BASE_PATH / "data" / "holdings.json"
    out_notes = portfolio_dir / "import_notes.md"

    save_json(out_portfolio_holdings, holdings)
    save_json(out_compat_holdings, holdings)

    stats = {
        "files": len(file_paths),
        "rows_scanned": scanned_rows,
        "holdings_parsed": len(holdings_raw),
        "holdings_deduped": len(holdings),
    }
    out_notes.write_text(
        build_import_notes(
            portfolio_id=portfolio_id,
            country=country,
            platform=platform,
            files=file_paths,
            mappings=mappings,
            delimiter_notes=delimiter_notes,
            stats=stats,
        ),
        encoding="utf-8",
    )

    print(f"Wrote: {out_portfolio_holdings}")
    print(f"Wrote: {out_compat_holdings}")
    print(f"Wrote: {out_notes}")
    print(f"Holdings: {len(holdings)}")


if __name__ == "__main__":
    main()
