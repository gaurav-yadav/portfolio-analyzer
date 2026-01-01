"""Watchlist management for tracked stocks."""
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

WATCHLIST_PATH = Path("data/watchlist.json")


def load_watchlist() -> dict:
    """Load watchlist from file."""
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text())
    return {"stocks": []}


def save_watchlist(data: dict):
    """Save watchlist to file."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(data, indent=2))


def get_current_price(symbol: str) -> float:
    """Fetch current price from Yahoo Finance."""
    if not HAS_YFINANCE:
        print("Warning: yfinance not installed, cannot fetch price")
        return 0.0

    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        price = ticker.info.get("regularMarketPrice")
        if price is None:
            price = ticker.info.get("currentPrice", 0)
        return float(price) if price else 0.0
    except Exception as e:
        print(f"Warning: Could not fetch price for {symbol}: {e}")
        return 0.0


def add_stock(symbol: str, scan_type: str, price: float = None, notes: str = ""):
    """Add stock to watchlist.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE")
        scan_type: Which scan found it (e.g., "rsi_oversold")
        price: Entry price (fetched if not provided)
        notes: Optional notes
    """
    data = load_watchlist()
    symbol = symbol.upper().replace(".NS", "")

    # Check if already exists
    for stock in data["stocks"]:
        if stock["symbol"] == symbol:
            print(f"{symbol} already in watchlist (added {stock['added_date']})")
            return

    # Fetch current price if not provided
    if price is None:
        price = get_current_price(symbol)

    data["stocks"].append({
        "symbol": symbol,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "added_from_scan": scan_type,
        "added_price": price,
        "notes": notes
    })

    save_watchlist(data)
    print(f"Added {symbol} to watchlist at Rs {price:.2f}")


def remove_stock(symbol: str):
    """Remove stock from watchlist."""
    data = load_watchlist()
    symbol = symbol.upper().replace(".NS", "")

    original_count = len(data["stocks"])
    data["stocks"] = [s for s in data["stocks"] if s["symbol"] != symbol]

    if len(data["stocks"]) < original_count:
        save_watchlist(data)
        print(f"Removed {symbol} from watchlist")
    else:
        print(f"{symbol} not found in watchlist")


def list_watchlist(show_prices: bool = False):
    """Show all watchlist stocks."""
    data = load_watchlist()

    if not data["stocks"]:
        print("Watchlist is empty")
        return

    print(f"\nWatchlist ({len(data['stocks'])} stocks)")
    print("=" * 80)
    print(f"{'Symbol':<12} {'Added':<12} {'Scan Type':<18} {'Price':<10} {'Current':<10} {'P&L':<10}")
    print("-" * 80)

    for stock in data["stocks"]:
        symbol = stock["symbol"]
        added = stock["added_date"]
        scan = stock["added_from_scan"]
        added_price = stock["added_price"]

        if show_prices and HAS_YFINANCE:
            current = get_current_price(symbol)
            pnl = ((current - added_price) / added_price * 100) if added_price else 0
            pnl_str = f"{pnl:+.1f}%"
            current_str = f"Rs {current:.0f}"
        else:
            current_str = "-"
            pnl_str = "-"

        print(f"{symbol:<12} {added:<12} {scan:<18} Rs {added_price:<8.0f} {current_str:<10} {pnl_str:<10}")

    print("=" * 80)


def update_prices():
    """Update and show current prices for all watchlist stocks."""
    data = load_watchlist()

    if not data["stocks"]:
        print("Watchlist is empty")
        return

    print(f"\nPrice Update ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("=" * 60)

    for stock in data["stocks"]:
        symbol = stock["symbol"]
        added_price = stock["added_price"]
        current = get_current_price(symbol)

        if added_price and current:
            pnl = ((current - added_price) / added_price * 100)
            emoji = "+" if pnl >= 0 else ""
            print(f"{symbol:<12} Rs {added_price:.0f} → Rs {current:.0f} ({emoji}{pnl:.1f}%)")
        else:
            print(f"{symbol:<12} Rs {added_price:.0f} → ? (could not fetch)")

    print("=" * 60)


def get_watchlist_symbols() -> list[str]:
    """Get list of all watchlist symbols."""
    data = load_watchlist()
    return [s["symbol"] for s in data["stocks"]]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        list_watchlist()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "list":
        show_prices = "--prices" in sys.argv or "-p" in sys.argv
        list_watchlist(show_prices)

    elif cmd == "add":
        if len(sys.argv) < 4:
            print("Usage: watchlist.py add SYMBOL SCAN_TYPE [PRICE] [NOTES]")
            print("Example: watchlist.py add RELIANCE rsi_oversold 2450.50 'RSI at 28'")
            sys.exit(1)

        symbol = sys.argv[2]
        scan_type = sys.argv[3]
        price = float(sys.argv[4]) if len(sys.argv) > 4 else None
        notes = sys.argv[5] if len(sys.argv) > 5 else ""
        add_stock(symbol, scan_type, price, notes)

    elif cmd == "remove" or cmd == "rm":
        if len(sys.argv) < 3:
            print("Usage: watchlist.py remove SYMBOL")
            sys.exit(1)
        remove_stock(sys.argv[2])

    elif cmd == "update" or cmd == "prices":
        update_prices()

    elif cmd == "symbols":
        symbols = get_watchlist_symbols()
        print(" ".join(symbols) if symbols else "No stocks in watchlist")

    else:
        print("Usage:")
        print("  watchlist.py                    - List watchlist")
        print("  watchlist.py list [-p]          - List watchlist (with prices)")
        print("  watchlist.py add SYMBOL SCAN    - Add stock to watchlist")
        print("  watchlist.py remove SYMBOL      - Remove stock from watchlist")
        print("  watchlist.py update             - Update and show current prices")
        print("  watchlist.py symbols            - Print symbols only")
