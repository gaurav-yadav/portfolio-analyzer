#!/usr/bin/env python3
"""Fetch OHLCV data from Yahoo Finance for US stocks."""

import sys
import json
from pathlib import Path
from datetime import datetime

import yfinance as yf

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "ohlcv"


def fetch_ohlcv(symbol: str, period: str = "6mo") -> dict:
    """
    Fetch OHLCV data for a US stock symbol.

    Args:
        symbol: Stock ticker (e.g., 'GOOG', 'NVDA')
        period: Data period (default '6mo' for 6 months)

    Returns:
        Dictionary with OHLCV data and metadata
    """
    print(f"Fetching {symbol}...", file=sys.stderr)

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)

        if df is None or df.empty:
            return {
                "symbol": symbol,
                "status": "error",
                "error": f"No data available for {symbol}"
            }

        # Convert to list of OHLCV records
        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 4),
                "high": round(row["High"], 4),
                "low": round(row["Low"], 4),
                "close": round(row["Close"], 4),
                "volume": int(row["Volume"])
            })

        result = {
            "symbol": symbol,
            "status": "success",
            "fetched_at": datetime.now().isoformat(),
            "period": period,
            "rows": len(records),
            "data_start": records[0]["date"] if records else None,
            "data_end": records[-1]["date"] if records else None,
            "data": records
        }

        return result

    except Exception as e:
        return {
            "symbol": symbol,
            "status": "error",
            "error": str(e)
        }


def main():
    """Main entry point."""
    # US stock symbols to fetch
    symbols = [
        "AMD", "ANET", "CRCL", "CSIQ", "GOOG",
        "INOD", "INTC", "MU", "MVIS", "NVDA",
        "PSTG", "RKLB", "TER"
    ]

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for symbol in symbols:
        data = fetch_ohlcv(symbol, period="6mo")

        # Save to JSON file
        output_path = OUTPUT_DIR / f"{symbol}.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        # Summary for reporting
        summary = {
            "symbol": symbol,
            "status": data["status"],
            "rows": data.get("rows", 0),
            "data_start": data.get("data_start"),
            "data_end": data.get("data_end"),
            "output_path": str(output_path)
        }

        if data["status"] == "error":
            summary["error"] = data.get("error")

        results.append(summary)

        print(f"  {symbol}: {data['status']} - {data.get('rows', 0)} rows", file=sys.stderr)

    # Print summary as JSON
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
