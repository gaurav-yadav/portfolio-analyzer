"""Data access layer — single source of truth for all file paths and I/O.

Every data path lives here. Scripts import from here, never construct paths
themselves. Returns None on missing data, never crashes.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from utils.helpers import load_json, save_json
from utils.ta_common import NumpyEncoder

# =============================================================================
# PATHS (single source of truth)
# =============================================================================

BASE = Path(__file__).parent.parent
CACHE_DIR = BASE / "cache" / "ohlcv"
CACHE_META = BASE / "cache" / "cache_metadata.json"
DATA = BASE / "data"
WL_DIR = DATA / "watchlists"
TA_DIR = DATA / "ta"
TECH_DIR = DATA / "technical"
SCAN_DIR = DATA / "scans"
SCAN_TA = DATA / "scan_technical"
SCORES_DIR = DATA / "scores"
SUGGEST = DATA / "suggestions"
FUND_DIR = DATA / "fundamentals"
NEWS_DIR = DATA / "news"
LEGAL_DIR = DATA / "legal"
WATCHER_DIR = DATA / "watcher"

# =============================================================================
# OHLCV
# =============================================================================


def load_ohlcv(symbol: str) -> pd.DataFrame | None:
    """Load OHLCV data from parquet cache. Returns None if not found."""
    path = CACHE_DIR / f"{symbol}.parquet"

    # Try with .NS suffix for Indian stocks
    if not path.exists() and not any(symbol.endswith(s) for s in [".NS", ".BO"]):
        path = CACHE_DIR / f"{symbol}.NS.parquet"

    if not path.exists():
        return None

    df = pd.read_parquet(path)
    return df if len(df) >= 20 else None


def save_ohlcv(symbol: str, df: pd.DataFrame) -> Path:
    """Save OHLCV DataFrame to parquet cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{symbol}.parquet"
    df.to_parquet(path)
    return path


def is_ohlcv_fresh(symbol: str, max_hours: int = 18) -> bool:
    """Check if OHLCV cache is fresh enough."""
    meta = get_cache_meta(symbol)
    if not meta or "last_fetched" not in meta:
        return False
    try:
        fetched = datetime.fromisoformat(meta["last_fetched"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - fetched).total_seconds() < max_hours * 3600
    except (ValueError, TypeError):
        return False


def get_latest_price(symbol: str) -> float | None:
    """Get latest closing price from OHLCV cache."""
    df = load_ohlcv(symbol)
    if df is None or df.empty:
        return None
    return float(df["Close"].iloc[-1])


# =============================================================================
# CACHE METADATA
# =============================================================================


def get_cache_meta(symbol: str) -> dict | None:
    """Get cache metadata for a symbol."""
    data = load_json(CACHE_META)
    if not data or symbol not in data:
        return None
    return data[symbol]


def set_cache_meta(symbol: str, meta: dict) -> None:
    """Set cache metadata for a symbol."""
    data = load_json(CACHE_META) or {}
    data[symbol] = meta
    save_json(CACHE_META, data)


# =============================================================================
# WATCHLISTS
# =============================================================================


def list_watchlists() -> list[str]:
    """List all watchlist IDs (from *.json files in watchlist dir)."""
    if not WL_DIR.exists():
        return []
    return sorted(p.stem for p in WL_DIR.glob("*.json"))


def load_watchlist(wl_id: str) -> dict | None:
    """Load a watchlist by ID. Handles both v1 and v2 schemas transparently."""
    path = WL_DIR / f"{wl_id}.json"
    if not path.exists():
        return None
    data = load_json(path)
    if data is None:
        return None

    # Ensure v2 fields exist (infer from filename if missing)
    if "id" not in data:
        data["id"] = wl_id
    if "name" not in data:
        data["name"] = wl_id.replace("_", " ").title() + " Watchlist"
    if "schema_version" not in data:
        data["schema_version"] = 1

    return data


def save_watchlist(wl_id: str, data: dict) -> None:
    """Save watchlist, bumping file_revision and updated_at."""
    WL_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().astimezone().isoformat()
    data["file_revision"] = data.get("file_revision", 0) + 1
    path = WL_DIR / f"{wl_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)


def create_watchlist(wl_id: str, name: str, **kw) -> dict:
    """Create a new watchlist with v2 schema."""
    now = datetime.now().astimezone().isoformat()
    data = {
        "schema_version": 2,
        "id": wl_id,
        "name": name,
        "description": kw.get("description", ""),
        "created_at": now,
        "updated_at": now,
        "file_revision": 1,
        "watchlist": [],
    }
    save_watchlist(wl_id, data)
    return data


def all_watchlist_symbols() -> dict[str, list[str]]:
    """Get all YF symbols across all watchlists, deduped. Returns {yf_symbol: [wl_ids]}."""
    result: dict[str, list[str]] = {}
    for wl_id in list_watchlists():
        wl = load_watchlist(wl_id)
        if not wl:
            continue
        for entry in wl.get("watchlist", []):
            yf_sym = _ticker_to_yf(entry)
            if yf_sym:
                result.setdefault(yf_sym, []).append(wl_id)
    return result


def _ticker_to_yf(entry: dict) -> str:
    """Convert a watchlist entry's ticker to Yahoo Finance format.

    Uses market field to determine suffix: IN→.NS, US→no suffix.
    """
    ticker = (entry.get("ticker") or "").strip()
    if not ticker:
        return ""
    # Already has exchange suffix
    if "." in ticker:
        return ticker
    market = (entry.get("market") or "").upper()
    if market == "US":
        return ticker
    # Default to .NS for Indian stocks
    return f"{ticker}.NS"


def watchlist_symbols(wl_id: str) -> list[str]:
    """Get list of Yahoo Finance symbols from a specific watchlist."""
    wl = load_watchlist(wl_id)
    if not wl:
        return []
    return [_ticker_to_yf(e) for e in wl.get("watchlist", []) if e.get("ticker")]


# =============================================================================
# TECHNICAL (aggregated scores)
# =============================================================================


def load_technical(symbol: str) -> dict | None:
    """Load aggregated technical analysis for a symbol."""
    return load_json(TECH_DIR / f"{symbol}.json")


def save_technical(symbol: str, data: dict) -> None:
    """Save aggregated technical analysis."""
    TECH_DIR.mkdir(parents=True, exist_ok=True)
    save_json(TECH_DIR / f"{symbol}.json", data)


# =============================================================================
# TA INDICATORS (per-indicator files)
# =============================================================================


def load_ta(symbol: str, indicator: str) -> dict | None:
    """Load a specific TA indicator result."""
    return load_json(TA_DIR / f"{symbol}_{indicator}.json")


def save_ta(symbol: str, indicator: str, data: dict) -> None:
    """Save a TA indicator result."""
    TA_DIR.mkdir(parents=True, exist_ok=True)
    data["symbol"] = symbol
    data["indicator"] = indicator
    data["timestamp"] = datetime.now().isoformat()
    path = TA_DIR / f"{symbol}_{indicator}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)


# =============================================================================
# SCAN TA (separate namespace for scanner)
# =============================================================================


def load_scan_ta(symbol: str, indicator: str) -> dict | None:
    """Load scan-specific TA indicator."""
    return load_json(SCAN_TA / f"{symbol}_{indicator}.json")


def save_scan_ta(symbol: str, indicator: str, data: dict) -> None:
    """Save scan-specific TA indicator."""
    SCAN_TA.mkdir(parents=True, exist_ok=True)
    data["symbol"] = symbol
    data["indicator"] = indicator
    data["timestamp"] = datetime.now().isoformat()
    path = SCAN_TA / f"{symbol}_{indicator}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)


# =============================================================================
# SCANS
# =============================================================================


def load_latest_scan() -> dict | None:
    """Load the most recent scan file by filename sort."""
    if not SCAN_DIR.exists():
        return None
    files = sorted(SCAN_DIR.glob("scan_*.json"))
    if not files:
        return None
    return load_json(files[-1])


def save_scan(data: dict) -> Path:
    """Save scan with timestamped filename."""
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCAN_DIR / f"scan_{ts}.json"
    save_json(path, data)
    return path


# =============================================================================
# SUGGESTIONS
# =============================================================================


def append_suggestion(entry: dict) -> None:
    """Append an entry to the suggestions ledger."""
    SUGGEST.mkdir(parents=True, exist_ok=True)
    ledger = SUGGEST / "ledger.jsonl"
    with open(ledger, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def load_ledger() -> list[dict]:
    """Read all suggestion entries from the ledger."""
    ledger = SUGGEST / "ledger.jsonl"
    if not ledger.exists():
        return []
    entries = []
    for line in ledger.read_text().strip().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def load_outcomes() -> list[dict]:
    """Load all outcome entries from outcomes directory."""
    outcomes_dir = SUGGEST / "outcomes"
    if not outcomes_dir.exists():
        return []
    entries = []
    for f in sorted(outcomes_dir.glob("*.jsonl")):
        for line in f.read_text().strip().splitlines():
            if line.strip():
                entries.append(json.loads(line))
    return entries


# =============================================================================
# SCORES
# =============================================================================


def load_score(symbol: str) -> dict | None:
    """Load final score for a symbol."""
    return load_json(SCORES_DIR / f"{symbol}.json")


def save_score(symbol: str, data: dict) -> None:
    """Save final score for a symbol."""
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    save_json(SCORES_DIR / f"{symbol}.json", data)
