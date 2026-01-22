#!/usr/bin/env python3
"""
Holdings Validator/Normalizer (deterministic).

Purpose:
  - Accept holdings JSON produced by *anything* (agent parsing, CSV scripts, manual edits)
  - Validate the canonical schema requirements for the rest of the pipeline
  - Normalize symbols (symbol vs symbol_yf), numeric fields, and deduplicate

This is intentionally "dumb" and deterministic. Agents do the judgment/workflow.

Usage:
  # Validate/normalize the main pipeline file in-place
  uv run python scripts/holdings_validate.py

  # Validate a specific file and write output elsewhere
  uv run python scripts/holdings_validate.py --in data/holdings_raw.json --out data/holdings.json

  # Fill missing metadata (useful when an agent extracted a bare table)
  uv run python scripts/holdings_validate.py --portfolio-id gaurav-india-kite --country india --platform kite
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import normalize_symbol as normalize_symbol_clean  # noqa: E402
from utils.helpers import save_json  # noqa: E402


BASE_PATH = Path(__file__).parent.parent


def normalize_us_symbol(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    # Yahoo uses BRK-B style for class shares; accept BRK.B and normalize.
    if "." in t:
        t = t.replace(".", "-")
    return t


def normalize_yf_symbol(country: str, symbol_yf: str, default_suffix: str) -> str:
    s = (symbol_yf or "").strip().upper()
    if not s:
        return ""

    if country == "us":
        return normalize_us_symbol(s)

    # India default: allow .NS/.BO; add suffix if missing
    if "." in s:
        return s
    return f"{s}{default_suffix}" if default_suffix else s


def infer_country_from_symbol_yf(symbol_yf: str) -> str | None:
    s = (symbol_yf or "").upper()
    if s.endswith(".NS") or s.endswith(".BO"):
        return "india"
    # Heuristic: US tickers generally have no .NS/.BO suffix
    if s and "." not in s:
        return "us"
    return None


def safe_float(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s or s.upper() in {"N/A", "NA", "NONE", "NULL", "-"}:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
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


@dataclass(frozen=True)
class NormalizedHolding:
    portfolio_id: str | None
    country: str
    platform: str | None
    broker: str
    symbol: str
    symbol_yf: str
    name: str
    quantity: float
    avg_price: float
    currency: str | None
    current_price: float | None
    market_value: float | None
    invested: float | None


def normalize_holding(
    raw: dict[str, Any],
    *,
    default_country: str | None,
    default_portfolio_id: str | None,
    default_platform: str | None,
    default_broker: str | None,
    default_suffix: str,
) -> NormalizedHolding:
    # Basic symbol fields
    raw_symbol_yf = str(raw.get("symbol_yf") or "").strip()
    raw_symbol = str(raw.get("symbol") or "").strip()

    # Infer country, prefer explicit raw field, then defaults, then suffix heuristic.
    country = str(raw.get("country") or "").strip().lower() or (default_country or "")
    if not country:
        country = infer_country_from_symbol_yf(raw_symbol_yf) or "india"
    if country not in {"india", "us"}:
        raise ValueError(f"Unsupported country: {country}")

    symbol_yf = raw_symbol_yf or raw_symbol
    symbol_yf = normalize_yf_symbol(country, symbol_yf, default_suffix=default_suffix)
    if not symbol_yf:
        raise ValueError("Missing symbol/symbol_yf")

    symbol = normalize_symbol_clean(symbol_yf) if country == "india" else normalize_us_symbol(symbol_yf)

    # Required numeric fields
    quantity = safe_float(raw.get("quantity"))
    avg_price = safe_float(raw.get("avg_price"))
    if quantity is None or avg_price is None:
        raise ValueError(f"Missing quantity/avg_price for {symbol_yf}")
    if quantity <= 0 or avg_price <= 0:
        raise ValueError(f"Invalid quantity/avg_price for {symbol_yf}: qty={quantity}, avg={avg_price}")

    # Optional fields
    name = str(raw.get("name") or "").strip() or symbol
    broker = str(raw.get("broker") or "").strip() or (default_broker or default_platform or "unknown")
    platform = str(raw.get("platform") or "").strip() or (default_platform or None)
    portfolio_id = str(raw.get("portfolio_id") or "").strip() or (default_portfolio_id or None)
    currency = str(raw.get("currency") or "").strip() or ("INR" if country == "india" else "USD")

    current_price = safe_float(raw.get("current_price"))
    market_value = safe_float(raw.get("market_value"))
    invested = safe_float(raw.get("invested") or raw.get("cost_basis"))

    return NormalizedHolding(
        portfolio_id=portfolio_id,
        country=country,
        platform=platform,
        broker=broker,
        symbol=symbol,
        symbol_yf=symbol_yf,
        name=name,
        quantity=float(quantity),
        avg_price=float(avg_price),
        currency=currency,
        current_price=current_price,
        market_value=market_value,
        invested=invested,
    )


def dedupe_holdings(holdings: list[NormalizedHolding]) -> list[NormalizedHolding]:
    agg: dict[tuple[str, str], NormalizedHolding] = {}
    qty_cost: dict[tuple[str, str], tuple[float, float]] = {}

    for h in holdings:
        key = (h.symbol_yf, h.broker)
        if key not in agg:
            agg[key] = h
            qty_cost[key] = (h.quantity, h.quantity * h.avg_price)
            continue

        prev = agg[key]
        prev_qty, prev_cost = qty_cost[key]
        new_qty = prev_qty + h.quantity
        new_cost = prev_cost + h.quantity * h.avg_price
        new_avg = (new_cost / new_qty) if new_qty > 0 else prev.avg_price

        # Merge optional fields conservatively
        merged = NormalizedHolding(
            portfolio_id=prev.portfolio_id or h.portfolio_id,
            country=prev.country,
            platform=prev.platform or h.platform,
            broker=prev.broker,
            symbol=prev.symbol,
            symbol_yf=prev.symbol_yf,
            name=prev.name or h.name,
            quantity=new_qty,
            avg_price=new_avg,
            currency=prev.currency or h.currency,
            current_price=prev.current_price if prev.current_price is not None else h.current_price,
            market_value=prev.market_value if prev.market_value is not None else h.market_value,
            invested=prev.invested if prev.invested is not None else h.invested,
        )

        agg[key] = merged
        qty_cost[key] = (new_qty, new_cost)

    # Stable ordering: broker then symbol_yf
    out = list(agg.values())
    out.sort(key=lambda x: (x.broker, x.symbol_yf))
    return out


def to_json(h: NormalizedHolding) -> dict[str, Any]:
    d: dict[str, Any] = {
        "portfolio_id": h.portfolio_id,
        "country": h.country,
        "platform": h.platform,
        "broker": h.broker,
        "symbol": h.symbol,
        "symbol_yf": h.symbol_yf,
        "name": h.name,
        "quantity": h.quantity,
        "avg_price": h.avg_price,
        "currency": h.currency,
    }
    if h.current_price is not None:
        d["current_price"] = h.current_price
    if h.market_value is not None:
        d["market_value"] = h.market_value
    if h.invested is not None:
        d["invested"] = h.invested
    return {k: v for k, v in d.items() if v is not None and v != ""}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/normalize holdings JSON deterministically.")
    parser.add_argument("--in", dest="in_path", default="data/holdings.json", help="Input holdings JSON (default: data/holdings.json)")
    parser.add_argument("--out", dest="out_path", default="data/holdings.json", help="Output holdings JSON (default: data/holdings.json)")
    parser.add_argument("--portfolio-id", default="", help="Fill missing portfolio_id")
    parser.add_argument("--country", default="", choices=["", "india", "us"], help="Fill missing country (optional)")
    parser.add_argument("--platform", default="", help="Fill missing platform")
    parser.add_argument("--broker", default="", help="Fill missing broker")
    parser.add_argument("--default-suffix", default=".NS", help="Default suffix for India tickers without suffix (default: .NS)")
    args = parser.parse_args()

    in_path = BASE_PATH / args.in_path
    if not in_path.exists():
        raise SystemExit(f"Error: input file not found: {in_path}")

    data = json.loads(in_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Error: holdings JSON must be an array")

    normalized: list[NormalizedHolding] = []
    errors: list[str] = []

    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            errors.append(f"Row {idx}: not an object")
            continue
        try:
            normalized.append(
                normalize_holding(
                    row,
                    default_country=(args.country or None),
                    default_portfolio_id=(args.portfolio_id or None),
                    default_platform=(args.platform or None),
                    default_broker=(args.broker or None),
                    default_suffix=args.default_suffix,
                )
            )
        except Exception as e:
            errors.append(f"Row {idx}: {e}")

    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors[:25]:
            print(f"- {e}", file=sys.stderr)
        if len(errors) > 25:
            print(f"- ... and {len(errors) - 25} more", file=sys.stderr)
        raise SystemExit(1)

    deduped = dedupe_holdings(normalized)
    out_rows = [to_json(h) for h in deduped]

    out_path = BASE_PATH / args.out_path
    save_json(out_path, out_rows)

    print(f"Wrote: {out_path}")
    print(f"Holdings: {len(out_rows)} (deduped from {len(normalized)})")


if __name__ == "__main__":
    main()

