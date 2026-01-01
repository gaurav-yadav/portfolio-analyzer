"""Save aggregated scan results from Claude agents."""
import json
import sys
from datetime import datetime
from pathlib import Path

SCANS_DIR = Path("data/scans")


def save_scan_results(results: dict) -> Path:
    """Save scan results with timestamp.

    Args:
        results: Dict with scan_type keys and match lists
            {
                "rsi_oversold": {"count": 5, "matches": [...]},
                "macd_crossover": {"count": 3, "matches": [...]},
                ...
            }

    Returns:
        Path to saved file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output = {
        "timestamp": datetime.now().isoformat(),
        "scans": results,
        "total_unique_stocks": count_unique(results)
    }

    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCANS_DIR / f"scan_{timestamp}.json"
    path.write_text(json.dumps(output, indent=2))

    print(f"Saved scan results to {path}")
    return path


def count_unique(results: dict) -> int:
    """Count unique symbols across all scans."""
    symbols = set()
    for scan_data in results.values():
        if isinstance(scan_data, dict):
            for match in scan_data.get("matches", []):
                if isinstance(match, dict):
                    symbols.add(match.get("symbol", ""))
                elif isinstance(match, str):
                    symbols.add(match.split()[0])  # First word is symbol
    return len(symbols)


def list_scans() -> list[Path]:
    """List all saved scan files, newest first."""
    if not SCANS_DIR.exists():
        return []
    return sorted(SCANS_DIR.glob("scan_*.json"), reverse=True)


def load_latest_scan() -> dict | None:
    """Load the most recent scan results."""
    scans = list_scans()
    if not scans:
        return None
    return json.loads(scans[0].read_text())


def print_scan_summary(scan_data: dict):
    """Print a summary of scan results."""
    print(f"\nScan from: {scan_data.get('timestamp', 'unknown')}")
    print(f"Total unique stocks: {scan_data.get('total_unique_stocks', 0)}")
    print("-" * 50)

    for scan_type, data in scan_data.get("scans", {}).items():
        count = data.get("count", len(data.get("matches", [])))
        print(f"  {scan_type}: {count} stocks")

        # Show top 3
        for match in data.get("matches", [])[:3]:
            if isinstance(match, dict):
                symbol = match.get("symbol", "?")
                note = match.get("note", "")
                print(f"    - {symbol}: {note}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        scans = list_scans()
        if scans:
            print(f"Found {len(scans)} scan(s):")
            for s in scans[:10]:
                print(f"  {s.name}")
        else:
            print("No scans found")
    elif len(sys.argv) > 1 and sys.argv[1] == "latest":
        scan = load_latest_scan()
        if scan:
            print_scan_summary(scan)
        else:
            print("No scans found")
    else:
        print("Usage:")
        print("  save_scan.py list    - List all saved scans")
        print("  save_scan.py latest  - Show latest scan summary")
