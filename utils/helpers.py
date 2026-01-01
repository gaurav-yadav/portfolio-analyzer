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

    Args:
        value: String representation of number

    Returns:
        Float value or None if parsing fails
    """
    if not value or str(value).strip().upper() in ("N/A", "-", "", "NAN", "NONE"):
        return None

    try:
        cleaned = re.sub(r"[,%\s]", "", str(value))
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def ensure_data_dirs():
    """Ensure all data directories exist."""
    base = Path(__file__).parent.parent
    dirs = [
        base / "data",
        base / "data" / "technical",
        base / "data" / "fundamentals",
        base / "data" / "news",
        base / "data" / "legal",
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
