# Repository Guidelines

## Project Structure & Module Organization
- `scripts/`: CLI entry points for the portfolio pipeline and scanner/watchlist helpers.
- `utils/`: shared helpers and configuration (`utils/config.py` is the single source for thresholds and weights).
- `dashboard/`: static HTML/CSS/JS for the report viewer.
- `config/`: editable CSV weights (`config/technical_weights.csv`).
- `data/`, `cache/ohlcv/`, `output/`, `input/`: runtime artifacts and sample inputs (all gitignored except `input/sample_zerodha.csv`).
- `docs/`, `specs/`: deeper documentation and design notes.
- `.claude/agents/`: agent definitions used by the Claude workflow.

## Build, Test, and Development Commands
- `uv sync`: install dependencies.
- `uv run python scripts/clean.py`: reset `data/` and `output/` before a new run.
- `uv run python scripts/parse_csv.py input/sample_zerodha.csv`: parse holdings into `data/holdings.json`.
- `uv run python scripts/fetch_all.py`: download/cached OHLCV to `cache/ohlcv/`.
- `uv run python scripts/technical_all.py`: compute indicators into `data/technical/`.
- `uv run python scripts/score_all.py`: score holdings into `data/scores/`.
- `uv run python scripts/compile_report.py`: emit `output/analysis_YYYYMMDD_HHMMSS.csv`.
- `uv run python scripts/verify_scan.py SYMBOL1 SYMBOL2`: full technical check for scanner picks.
- Open `dashboard/index.html` and load the CSV for UI validation.

## Coding Style & Naming Conventions
- Python uses 4-space indentation, explicit type hints, and `snake_case` for functions and modules.
- Constants live in `utils/config.py` and follow `UPPER_SNAKE` naming.
- Generated files follow timestamped patterns like `analysis_YYYYMMDD_HHMMSS.csv` and `scan_YYYYMMDD_HHMMSS.json`.

## Testing Guidelines
- No automated test framework or coverage target is configured.
- Manual smoke test: run the parse -> fetch -> technical -> score -> compile pipeline using `input/sample_zerodha.csv` and verify outputs in `data/` and `output/`.
- If you add tests, place them under `tests/` and document the command here.

## Commit & Pull Request Guidelines
- Commit messages are short, imperative, and sentence-case (e.g., "Fix repo URL in README").
- PRs should include a brief summary, rationale, commands run, and screenshots for `dashboard/` changes.
- Do not commit generated artifacts under `data/`, `output/`, or `cache/`.

## Agent Creation Guidelines
- Agent files live in `.claude/agents/` with a `.md` extension.
- Each file must have YAML frontmatter with `name` and `description` fields.
- **Quote descriptions containing colons.** Unquoted colons break YAML parsing:
  ```yaml
  # BAD - parser sees "description: Smart scanner" and chokes on the rest
  description: Smart scanner: web-search discovery + OHLCV ranking

  # GOOD - quoted string handles colons correctly
  description: "Smart scanner: web-search discovery + OHLCV ranking"
  ```
- Filename should match the `name` field (e.g., `scanner.md` with `name: scanner`).
- Restart Claude Code after adding or modifying agents for changes to take effect.

## Security & Configuration Notes
- Report security issues privately (see README).
- Adjust scoring behavior in `utils/config.py` and `config/technical_weights.csv` rather than hardcoding values in scripts.
