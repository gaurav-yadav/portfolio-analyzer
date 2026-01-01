"""Track watchlist performance over time."""
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

HISTORY_DIR = Path("data/scan_history")
WATCHLIST_PATH = Path("data/watchlist.json")


def get_current_price(symbol: str) -> float:
    """Fetch current price from Yahoo Finance."""
    if not HAS_YFINANCE:
        return 0.0

    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        price = ticker.info.get("regularMarketPrice")
        if price is None:
            price = ticker.info.get("currentPrice", 0)
        return float(price) if price else 0.0
    except Exception:
        return 0.0


def load_watchlist() -> dict:
    """Load watchlist from file."""
    if WATCHLIST_PATH.exists():
        return json.loads(WATCHLIST_PATH.read_text())
    return {"stocks": []}


def load_history(symbol: str) -> dict:
    """Load history for a symbol."""
    history_file = HISTORY_DIR / f"{symbol}.json"
    if history_file.exists():
        return json.loads(history_file.read_text())
    return None


def save_history(symbol: str, history: dict):
    """Save history for a symbol."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_file = HISTORY_DIR / f"{symbol}.json"
    history_file.write_text(json.dumps(history, indent=2))


def update_history():
    """Update price history for all watchlist stocks."""
    watchlist = load_watchlist()

    if not watchlist["stocks"]:
        print("No stocks in watchlist to track")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\nPerformance Report ({today})")
    print("=" * 70)
    print(f"{'Symbol':<12} {'Return':<10} {'Days':<8} {'Signal':<18} {'Entry':<10} {'Current':<10}")
    print("-" * 70)

    results = []

    for stock in watchlist["stocks"]:
        symbol = stock["symbol"]

        # Load or create history
        history = load_history(symbol)
        if history is None:
            history = {
                "symbol": symbol,
                "first_seen": stock["added_date"],
                "first_seen_scan": stock["added_from_scan"],
                "first_price": stock["added_price"],
                "appearances": [{
                    "date": stock["added_date"],
                    "scan": stock["added_from_scan"],
                    "price": stock["added_price"]
                }],
                "price_checkpoints": []
            }

        # Fetch current price
        current_price = get_current_price(symbol)

        # Add checkpoint (avoid duplicates for same day)
        if not history["price_checkpoints"] or history["price_checkpoints"][-1]["date"] != today:
            history["price_checkpoints"].append({
                "date": today,
                "price": current_price
            })
        else:
            # Update today's checkpoint
            history["price_checkpoints"][-1]["price"] = current_price

        # Calculate returns
        first_price = history["first_price"]
        if first_price and current_price:
            return_pct = ((current_price - first_price) / first_price * 100)
        else:
            return_pct = 0

        # Calculate days tracked
        try:
            first_date = datetime.strptime(history["first_seen"], "%Y-%m-%d")
            days = (datetime.now() - first_date).days
        except:
            days = 0

        # Update history
        history["latest_price"] = current_price
        history["return_pct"] = return_pct
        history["days_tracked"] = days

        # Save
        save_history(symbol, history)

        # Print row
        return_str = f"{return_pct:+.1f}%"
        scan = history["first_seen_scan"][:16]
        entry = f"Rs {first_price:.0f}" if first_price else "?"
        current = f"Rs {current_price:.0f}" if current_price else "?"

        print(f"{symbol:<12} {return_str:<10} {days:<8} {scan:<18} {entry:<10} {current:<10}")

        results.append({
            "symbol": symbol,
            "return_pct": return_pct,
            "days": days,
            "scan": history["first_seen_scan"]
        })

    print("-" * 70)

    # Summary stats
    if results:
        avg_return = sum(r["return_pct"] for r in results) / len(results)
        winners = sum(1 for r in results if r["return_pct"] > 0)
        losers = sum(1 for r in results if r["return_pct"] < 0)

        print(f"\nSummary: {len(results)} stocks | Avg return: {avg_return:+.1f}% | Winners: {winners} | Losers: {losers}")

    print("=" * 70)


def show_stock_history(symbol: str):
    """Show detailed history for a single stock."""
    symbol = symbol.upper().replace(".NS", "")
    history = load_history(symbol)

    if not history:
        print(f"No history found for {symbol}")
        return

    print(f"\nHistory for {symbol}")
    print("=" * 50)
    print(f"First seen: {history['first_seen']} via {history['first_seen_scan']}")
    print(f"Entry price: Rs {history['first_price']:.2f}")
    print(f"Current price: Rs {history.get('latest_price', 0):.2f}")
    print(f"Return: {history.get('return_pct', 0):+.1f}%")
    print(f"Days tracked: {history.get('days_tracked', 0)}")

    if history.get("appearances"):
        print(f"\nAppearances in scans:")
        for app in history["appearances"]:
            print(f"  {app['date']}: {app['scan']} at Rs {app['price']:.2f}")

    if history.get("price_checkpoints"):
        print(f"\nPrice history (last 10):")
        for cp in history["price_checkpoints"][-10:]:
            print(f"  {cp['date']}: Rs {cp['price']:.2f}")


def record_scan_appearance(symbol: str, scan_type: str, price: float = None):
    """Record that a stock appeared in a scan."""
    symbol = symbol.upper().replace(".NS", "")

    if price is None:
        price = get_current_price(symbol)

    history = load_history(symbol)
    if history is None:
        history = {
            "symbol": symbol,
            "first_seen": datetime.now().strftime("%Y-%m-%d"),
            "first_seen_scan": scan_type,
            "first_price": price,
            "appearances": [],
            "price_checkpoints": []
        }

    # Add appearance
    today = datetime.now().strftime("%Y-%m-%d")
    history["appearances"].append({
        "date": today,
        "scan": scan_type,
        "price": price
    })

    save_history(symbol, history)
    print(f"Recorded {symbol} appearance in {scan_type} at Rs {price:.2f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        update_history()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "update":
        update_history()

    elif cmd == "show" and len(sys.argv) >= 3:
        show_stock_history(sys.argv[2])

    elif cmd == "record" and len(sys.argv) >= 4:
        symbol = sys.argv[2]
        scan_type = sys.argv[3]
        price = float(sys.argv[4]) if len(sys.argv) > 4 else None
        record_scan_appearance(symbol, scan_type, price)

    else:
        print("Usage:")
        print("  track_performance.py              - Update all watchlist performance")
        print("  track_performance.py update       - Same as above")
        print("  track_performance.py show SYMBOL  - Show history for one stock")
        print("  track_performance.py record SYMBOL SCAN [PRICE] - Record scan appearance")
