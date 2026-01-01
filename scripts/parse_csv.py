#!/usr/bin/env python3
"""
CSV Parser Script - Parses Zerodha/Groww portfolio CSVs.

Usage:
    uv run python scripts/parse_csv.py <csv1> [csv2] [csv3] ...

Examples:
    uv run python scripts/parse_csv.py input/kite.csv
    uv run python scripts/parse_csv.py input/kite.csv input/groww.csv

Output:
    Writes parsed holdings to data/holdings.json
    Holdings from different brokers are kept separate (not merged).
"""

import csv
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import normalize_symbol, create_yf_symbol, clean_numeric, save_json


def detect_broker(headers: list[str]) -> str | None:
    """Detect broker based on CSV header row."""
    headers_lower = [h.lower().strip() for h in headers]

    # Zerodha: Has "Instrument" column
    if "instrument" in headers_lower:
        return "zerodha"

    # Groww: Has both "Symbol" and "Company Name" columns
    if "symbol" in headers_lower and any("company" in h for h in headers_lower):
        return "groww"

    # Check for variations
    if any("instrument" in h for h in headers_lower):
        return "zerodha"

    return None


def find_column(row: dict, *patterns: str) -> str | None:
    """Find value in row by matching column name patterns."""
    for key in row:
        key_lower = key.lower()
        if all(p in key_lower for p in patterns):
            return row[key]
    return None


def parse_zerodha_row(row: dict) -> dict | None:
    """Parse a Zerodha CSV row (supports old and new Kite formats)."""
    symbol = find_column(row, "instrument")
    if not symbol:
        return None

    # Skip empty rows or header-like rows
    if symbol.lower() in ["instrument", ""]:
        return None

    quantity = clean_numeric(find_column(row, "qty"))

    # New Kite format: "Avg. cost", Old format: "Avg. cost" or similar
    avg_price = clean_numeric(find_column(row, "avg"))

    # Get LTP (Last Traded Price) if available
    ltp = clean_numeric(find_column(row, "ltp"))

    # Get P&L percentage if available
    pnl = clean_numeric(find_column(row, "p&l"))
    net_chg = clean_numeric(find_column(row, "net", "chg"))

    # Get invested and current value
    invested = clean_numeric(find_column(row, "invested"))
    cur_val = clean_numeric(find_column(row, "cur", "val"))

    if quantity is None or avg_price is None:
        return None

    normalized = normalize_symbol(symbol)

    result = {
        "symbol": normalized,
        "symbol_yf": create_yf_symbol(normalized),
        "name": normalized,  # Zerodha doesn't provide company name
        "quantity": quantity,
        "avg_price": avg_price,
        "broker": "zerodha",
    }

    # Add optional fields if available
    if ltp is not None:
        result["ltp"] = ltp
    if invested is not None:
        result["invested"] = invested
    if cur_val is not None:
        result["current_value"] = cur_val
    if pnl is not None:
        result["pnl"] = pnl
    if net_chg is not None:
        result["net_change_pct"] = net_chg

    return result


def parse_groww_row(row: dict) -> dict | None:
    """Parse a Groww CSV row."""
    symbol = find_column(row, "symbol")
    if not symbol:
        # Try to get it from first column if header is just "symbol"
        for key in row:
            if key.lower().strip() == "symbol":
                symbol = row[key]
                break

    if not symbol:
        return None

    # Find company name
    name = find_column(row, "company") or symbol

    quantity = clean_numeric(find_column(row, "quantity") or find_column(row, "qty"))
    avg_price = clean_numeric(find_column(row, "avg", "price"))

    if quantity is None or avg_price is None:
        return None

    normalized = normalize_symbol(symbol)

    return {
        "symbol": normalized,
        "symbol_yf": create_yf_symbol(normalized),
        "name": name.strip() if name else normalized,
        "quantity": quantity,
        "avg_price": avg_price,
        "broker": "groww",
    }


def parse_portfolio_csv(file_path: str) -> list[dict]:
    """
    Parse a portfolio CSV file from Zerodha or Groww.

    Args:
        file_path: Path to the CSV file

    Returns:
        List of holding dictionaries
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    holdings = []

    # Try different encodings
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    content = None

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError("Could not decode file with any known encoding")

    # Parse CSV
    lines = content.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("CSV file is empty or has no data rows")

    reader = csv.DictReader(lines)
    headers = reader.fieldnames or []

    if not headers:
        raise ValueError("No headers found in CSV")

    # Detect broker
    broker = detect_broker(headers)

    if broker is None:
        raise ValueError(
            f"Unknown CSV format. Headers: {headers}. "
            "Expected Zerodha (Instrument column) or Groww (Symbol + Company Name columns)"
        )

    print(f"Detected broker: {broker}", file=sys.stderr)

    # Parse each row
    parse_func = parse_zerodha_row if broker == "zerodha" else parse_groww_row

    for row in reader:
        if not any(row.values()):
            continue

        holding = parse_func(row)
        if holding:
            holdings.append(holding)

    print(f"Parsed {len(holdings)} holdings", file=sys.stderr)

    return holdings


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/parse_csv.py <csv1> [csv2] [csv3] ...", file=sys.stderr)
        sys.exit(1)

    csv_files = sys.argv[1:]
    all_holdings = []

    for csv_file in csv_files:
        try:
            print(f"\nParsing: {csv_file}", file=sys.stderr)
            holdings = parse_portfolio_csv(csv_file)
            all_holdings.extend(holdings)
        except Exception as e:
            print(f"Error parsing {csv_file}: {e}", file=sys.stderr)
            sys.exit(1)

    # Aggregate duplicates: same symbol + same broker = weighted average price
    aggregated = {}
    for h in all_holdings:
        key = (h["symbol"], h["broker"])
        if key not in aggregated:
            aggregated[key] = h.copy()
        else:
            # Aggregate: combine quantities and compute weighted average price
            existing = aggregated[key]
            old_qty = existing["quantity"]
            old_price = existing["avg_price"]
            new_qty = h["quantity"]
            new_price = h["avg_price"]

            total_qty = old_qty + new_qty
            # Weighted average price
            if total_qty > 0:
                weighted_avg = (old_qty * old_price + new_qty * new_price) / total_qty
            else:
                weighted_avg = old_price

            existing["quantity"] = total_qty
            existing["avg_price"] = round(weighted_avg, 2)

            # Sum invested/current_value if present in either row
            if "invested" in h:
                existing["invested"] = existing.get("invested", 0) + h["invested"]
            if "current_value" in h:
                existing["current_value"] = existing.get("current_value", 0) + h["current_value"]

            print(f"Aggregated duplicate: {h['symbol']} from {h['broker']} (total qty: {total_qty})", file=sys.stderr)

    unique_holdings = list(aggregated.values())

    # Save to data/holdings.json
    output_path = Path(__file__).parent.parent / "data" / "holdings.json"
    save_json(output_path, unique_holdings)

    # Summary
    broker_counts = {}
    for h in unique_holdings:
        broker_counts[h["broker"]] = broker_counts.get(h["broker"], 0) + 1

    print(f"\nTotal: {len(unique_holdings)} holdings from {len(csv_files)} file(s)", file=sys.stderr)
    for broker, count in broker_counts.items():
        print(f"  {broker}: {count} stocks", file=sys.stderr)
    print(f"Saved to: {output_path}", file=sys.stderr)

    # Also print to stdout for agent to capture
    print(json.dumps(unique_holdings, indent=2))


if __name__ == "__main__":
    main()
