"""Common utility functions for Portfolio Analyzer."""

import re
import json
from pathlib import Path


def normalize_symbol(symbol: str) -> str:
    """
    Normalize stock symbol by removing exchange suffixes.

    Args:
        symbol: Raw symbol (e.g., "RELIANCE.NS", "INFY.BO", "TCS")

    Returns:
        Normalized symbol without suffix (e.g., "RELIANCE", "INFY", "TCS")
    """
    if not symbol:
        return ""

    symbol = symbol.strip().upper()
    suffixes = [".NS", ".BSE", ".BO", ".NSE"]

    for suffix in suffixes:
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
            break

    return symbol


def create_yf_symbol(symbol: str) -> str:
    """
    Create Yahoo Finance compatible symbol.

    Args:
        symbol: Normalized symbol (e.g., "RELIANCE")

    Returns:
        Yahoo Finance symbol (e.g., "RELIANCE.NS")
    """
    normalized = normalize_symbol(symbol)
    return f"{normalized}.NS" if normalized else ""


def clean_numeric(value: str) -> float | None:
    """
    Clean and parse numeric value from string.

    Handles formats like:
    - "2,450.50"
    - "2450.50"
    - "-5.2%"
    - "N/A"
    - "₹2,450.50" (Unicode rupee)
    - "Rs. 2,450" or "Rs 2450"
    - "INR 2,450.50"

    Args:
        value: String representation of number

    Returns:
        Float value or None if parsing fails
    """
    if not value or str(value).strip().upper() in ("N/A", "-", "", "NAN", "NONE"):
        return None

    try:
        value_str = str(value)
        # Remove currency symbols and prefixes
        # ₹ (Unicode rupee), Rs., Rs, INR
        cleaned = re.sub(r"[₹]", "", value_str)
        cleaned = re.sub(r"\bRs\.?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bINR\s*", "", cleaned, flags=re.IGNORECASE)
        # Remove commas, percentage signs, whitespace
        cleaned = re.sub(r"[,%\s]", "", cleaned)
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def ensure_data_dirs():
    """Ensure all data directories exist."""
    base = Path(__file__).parent.parent
    dirs = [
        base / "data",
        base / "data" / "technical",
        base / "data" / "scan_technical",  # Separate from portfolio analysis
        base / "data" / "fundamentals",
        base / "data" / "news",
        base / "data" / "legal",
        base / "data" / "scores",
        base / "data" / "scans",
        base / "data" / "scan_history",
        base / "cache" / "ohlcv",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict | list | None:
    """Load JSON file, return None if not found."""
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_json(path: Path, data: dict | list) -> None:
    """Save data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
