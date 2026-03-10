#!/usr/bin/env python3
"""
Watch dashboard-relevant data dirs and auto-bake + push on changes.

Only triggers on:
  data/watchlists/   — watchlist changes
  data/technical/    — technical scores
  data/ta/           — modular TA indicators
  data/suggestions/  — suggestions ledger + outcomes

Strictly ignores:
  data/portfolios/, data/holdings.json, data/fundamentals/,
  data/news/, data/legal/, data/scores/, data/scans/, data/runs/, etc.

Uses 60s debounce — bursts of changes → single bake+push.

Usage:
    uv run python scripts/watch_and_deploy.py            # foreground
    nohup uv run python scripts/watch_and_deploy.py      # background
    uv run python scripts/watch_and_deploy.py --dry-run  # no push, just print
"""

import argparse
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

BASE  = Path(__file__).parent.parent
DATA  = BASE / "data"
CACHE = BASE / "cache"
LOG   = BASE / "data" / "watch_deploy.log"

# ── Watched paths and their allowed subdirs ─────────────────────────────────
# Format: { root_dir: set_of_allowed_subdirs | None (= watch all) }
WATCH_ROOTS: dict[Path, set[str] | None] = {
    DATA: {
        "watchlists",   # watchlist changes
        "technical",    # technical scores
        "ta",           # modular TA indicators
        "suggestions",  # trade call ledger + outcomes
    },
    CACHE: {
        "ohlcv",        # OHLCV parquet files → candlestick charts
    },
}

DEBOUNCE_SECS = 60  # wait this long after last change before deploying


def setup_logging():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG, encoding="utf-8"),
        ],
    )


class DeployHandler(FileSystemEventHandler):
    def __init__(self, dry_run: bool, debounce: int = DEBOUNCE_SECS):
        super().__init__()
        self.dry_run = dry_run
        self.debounce = debounce
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _is_relevant(self, path: str) -> bool:
        """Return True only if the changed file is inside a watched root+subdir."""
        p = Path(path)
        for root, allowed_subdirs in WATCH_ROOTS.items():
            try:
                rel = p.relative_to(root)
                if allowed_subdirs is None:
                    return True
                return bool(rel.parts) and rel.parts[0] in allowed_subdirs
            except ValueError:
                continue
        return False

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if not self._is_relevant(event.src_path):
            return

        # Get the shortest relative path for logging
        p = Path(event.src_path)
        display = next(
            (str(p.relative_to(root)) for root in WATCH_ROOTS if p.is_relative_to(root)),
            str(p)
        )
        logging.info(f"Change detected: {display} ({event.event_type}) — debouncing {self.debounce}s")
        self._schedule_deploy()

    def _schedule_deploy(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self._deploy)
            self._timer.daemon = True
            self._timer.start()

    def _deploy(self):
        logging.info("Debounce elapsed — starting bake + push")
        # NOTE: deliberately no --refresh here — adding it would cause an infinite
        # loop because technical_all.py writes to data/technical/ and data/ta/,
        # which would re-trigger the watcher. Full refresh is handled by the
        # daily cron: bake_dashboard.py --refresh --push
        cmd = [
            "uv", "run", "python", "scripts/bake_dashboard.py",
        ]
        if not self.dry_run:
            cmd.append("--push")
        else:
            logging.info("[DRY RUN] would run: " + " ".join(cmd + ["--push"]))

        try:
            result = subprocess.run(
                cmd,
                cwd=BASE,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logging.info("Deploy OK:\n" + result.stdout.strip())
            else:
                logging.error("Deploy FAILED:\n" + result.stderr.strip())
        except subprocess.TimeoutExpired:
            logging.error("Deploy timed out after 120s")
        except Exception as e:
            logging.error(f"Deploy error: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="detect changes but don't push")
    parser.add_argument("--debounce", type=int, default=DEBOUNCE_SECS, help=f"debounce seconds (default: {DEBOUNCE_SECS})")
    args = parser.parse_args()

    setup_logging()

    if not DATA.exists():
        logging.error(f"data/ dir not found at {DATA}")
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    logging.info(f"=== watch_and_deploy starting [{mode}] ===")
    for root, subdirs in WATCH_ROOTS.items():
        tag = ", ".join(sorted(subdirs)) if subdirs else "*"
        logging.info(f"  {root.name}/  [{tag}]")
    logging.info(f"  Ignoring: portfolios, holdings, fundamentals, news, legal, scores, scans, ...")
    logging.info(f"  Debounce: {args.debounce}s")

    handler = DeployHandler(dry_run=args.dry_run, debounce=args.debounce)
    observer = Observer()
    for root in WATCH_ROOTS:
        if root.exists():
            observer.schedule(handler, str(root), recursive=True)
        else:
            logging.warning(f"  Watch root not found (skipping): {root}")
    observer.start()

    logging.info("Watching for changes... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopping watcher...")
        observer.stop()
    observer.join()
    logging.info("Stopped.")


if __name__ == "__main__":
    main()
