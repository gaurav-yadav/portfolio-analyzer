#!/usr/bin/env python3
"""
Clean Script - Clears all analysis data for fresh run.

Usage:
    uv run python scripts/clean.py [--clear-cache]

Options:
    --clear-cache  Also clear OHLCV cache (rarely needed, historical data doesn't change)
"""

import shutil
import sys
from pathlib import Path


def main():
    base_path = Path(__file__).parent.parent
    clear_cache = "--clear-cache" in sys.argv

    # Directories to clean
    data_dirs = [
        base_path / "data" / "technical",
        base_path / "data" / "technical_deep",
        # Legacy path used by older deep technical analysis script
        base_path / "data" / "technicals",
        base_path / "data" / "fundamentals",
        base_path / "data" / "news",
        base_path / "data" / "legal",
        base_path / "data" / "scores",
    ]

    # Files to remove
    data_files = [
        base_path / "data" / "holdings.json",
    ]

    # Cache (optional)
    cache_dir = base_path / "cache" / "ohlcv"

    cleaned = 0

    # Clean data directories
    for dir_path in data_dirs:
        if dir_path.exists():
            count = len(list(dir_path.glob("*.json")))
            shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"Cleaned: {dir_path.relative_to(base_path)} ({count} files)")
            cleaned += count

    # Clean data files
    for file_path in data_files:
        if file_path.exists():
            file_path.unlink()
            print(f"Removed: {file_path.relative_to(base_path)}")
            cleaned += 1

    # Clean cache only if explicitly requested
    if clear_cache and cache_dir.exists():
        count = len(list(cache_dir.glob("*.parquet")))
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Cleaned: {cache_dir.relative_to(base_path)} ({count} files)")
        cleaned += count
    else:
        cache_count = len(list(cache_dir.glob("*.parquet"))) if cache_dir.exists() else 0
        print(f"Kept: cache/ohlcv ({cache_count} files)")

    print(f"\nTotal cleaned: {cleaned} files")
    print("Ready for fresh portfolio analysis!")


if __name__ == "__main__":
    main()
