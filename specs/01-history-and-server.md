# SPEC: History Tracking + FastAPI Server

## Overview

Add persistent history tracking and a local API server to enable:
- Score trends over time per stock
- Portfolio value tracking across runs
- Dashboard auto-refresh via API
- Upload holdings directly from browser

## Current Architecture

```
CSV → parse_csv.py → holdings.json
                   → fetch_all.py → cache/ohlcv/*.parquet
                   → technical_all.py → data/technical/*.json
                   → [agents] → data/fundamentals|news|legal/*.json
                   → score_all.py → data/scores/*.json
                   → compile_report.py → output/analysis_YYYYMMDD.csv
                   → Dashboard loads CSV manually
```

## Proposed Architecture

```
Dashboard → FastAPI Server → Triggers analysis pipeline
                          → Stores to history.parquet
                          → Returns results
                          → Dashboard auto-refreshes

data/history/
├── analysis_history.parquet  # All runs, timestamped
└── portfolio_snapshots.parquet  # Portfolio value over time
```

---

## Part A: Parquet History Storage

### New file: `scripts/history.py`

**Schema: analysis_history.parquet**
| Column | Type | Description |
|--------|------|-------------|
| run_id | string | UUID for each analysis run |
| timestamp | datetime | When analysis was run |
| symbol | string | e.g., "RELIANCE" |
| symbol_yf | string | e.g., "RELIANCE.NS" |
| broker | string | e.g., "zerodha" |
| quantity | float | Shares held |
| avg_price | float | Average buy price |
| current_price | float | Price at analysis time |
| pnl_pct | float | Profit/loss percentage |
| technical_score | float | 1-10 |
| fundamental_score | float | 1-10 |
| news_sentiment_score | float | 1-10 |
| legal_corporate_score | float | 1-10 |
| overall_score | float | Weighted score |
| recommendation | string | STRONG BUY/BUY/HOLD/SELL/STRONG SELL |
| confidence | string | HIGH/MEDIUM/LOW |
| gate_flags | string | Safety gates triggered |

**Schema: portfolio_snapshots.parquet**
| Column | Type | Description |
|--------|------|-------------|
| run_id | string | UUID |
| timestamp | datetime | When run |
| total_stocks | int | Number of holdings |
| total_value | float | Portfolio value in INR |
| avg_score | float | Average overall score |
| health_rating | string | Excellent/Good/Fair/etc |

**Functions:**
```python
def append_analysis_run(scores: list[dict]) -> str:
    """Add new analysis run to history. Returns run_id."""

def get_symbol_history(symbol: str, days: int = 30) -> pd.DataFrame:
    """Get score trend for a symbol over N days."""

def get_portfolio_history(days: int = 90) -> pd.DataFrame:
    """Get portfolio value and health over time."""

def get_recommendation_accuracy(symbol: str, days: int = 30) -> dict:
    """Compare past recommendations vs actual price movement."""
```

**Modification to compile_report.py:**
- After generating CSV, call `history.append_analysis_run(scores)`
- Generate run_id at start of pipeline, pass through

---

## Part B: FastAPI Server

### New file: `server.py`

```python
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import uvicorn
from pathlib import Path

app = FastAPI(title="Portfolio Analyzer API")

# Serve dashboard
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/upload")
async def upload_csv(file: UploadFile, background_tasks: BackgroundTasks):
    """Upload holdings CSV and trigger analysis."""
    content = await file.read()
    input_path = Path("input/uploaded.csv")
    input_path.write_bytes(content)

    job_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(run_analysis, job_id)
    return {"job_id": job_id, "status": "started"}

@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    """Check analysis progress."""
    status_file = Path(f"data/jobs/{job_id}.json")
    if not status_file.exists():
        return {"status": "unknown"}
    return json.loads(status_file.read_text())

@app.get("/api/results/latest")
def get_latest_results():
    """Get most recent analysis as JSON."""
    output_dir = Path("output")
    csvs = sorted(output_dir.glob("analysis_*.csv"), reverse=True)
    if not csvs:
        return {"error": "No analysis found"}
    # Parse and return

@app.get("/api/history/{symbol}")
def get_symbol_history(symbol: str, days: int = 30):
    """Get score history for a symbol."""
    from scripts.history import get_symbol_history
    df = get_symbol_history(symbol, days)
    return df.to_dict(orient="records")

@app.get("/api/portfolio/history")
def get_portfolio_history(days: int = 90):
    """Get portfolio value history."""
    from scripts.history import get_portfolio_history
    df = get_portfolio_history(days)
    return df.to_dict(orient="records")

def run_analysis(job_id: str):
    """Run analysis pipeline in background."""
    status_file = Path(f"data/jobs/{job_id}.json")
    status_file.parent.mkdir(exist_ok=True)

    status_file.write_text(json.dumps({"status": "running", "step": "parsing"}))
    subprocess.run(["uv", "run", "python", "scripts/run_pipeline.py", job_id])
    status_file.write_text(json.dumps({"status": "complete"}))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### New file: `scripts/run_pipeline.py`

```python
"""Run full analysis pipeline for server."""
import sys
import subprocess
from pathlib import Path
import json

def main(job_id: str):
    status_file = Path(f"data/jobs/{job_id}.json")

    steps = [
        ("cleaning", ["python", "scripts/clean.py"]),
        ("parsing", ["python", "scripts/parse_csv.py", "input/uploaded.csv"]),
        ("fetching", ["python", "scripts/fetch_all.py"]),
        ("technical", ["python", "scripts/technical_all.py"]),
        # Note: Web research agents run separately via Claude
        ("scoring", ["python", "scripts/score_all.py"]),
        ("compiling", ["python", "scripts/compile_report.py"]),
    ]

    for step_name, cmd in steps:
        update_status(status_file, "running", step_name)
        result = subprocess.run(["uv"] + cmd, capture_output=True)
        if result.returncode != 0:
            update_status(status_file, "error", step_name, result.stderr.decode())
            return

    update_status(status_file, "complete")

def update_status(path, status, step=None, error=None):
    data = {"status": status}
    if step:
        data["step"] = step
    if error:
        data["error"] = error
    path.write_text(json.dumps(data))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "manual")
```

---

## Part C: Dashboard Enhancements

### Modifications to `dashboard/app.js`

```javascript
// Add at top
const API_BASE = 'http://localhost:8000';
let serverMode = false;

// Server mode toggle
function toggleServerMode() {
    serverMode = !serverMode;
    document.getElementById('serverModeBtn').textContent =
        serverMode ? 'Server Mode: ON' : 'Server Mode: OFF';
    document.getElementById('serverStatus').style.display =
        serverMode ? 'block' : 'none';
}

// Upload to server
async function uploadToServer(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        pollStatus(data.job_id);
    } catch (e) {
        showError('Server not running. Start with: uv run python server.py');
    }
}

// Poll status
async function pollStatus(jobId) {
    const statusEl = document.getElementById('jobStatus');

    const poll = async () => {
        const resp = await fetch(`${API_BASE}/api/status/${jobId}`);
        const data = await resp.json();

        statusEl.textContent = `Status: ${data.status} ${data.step || ''}`;

        if (data.status === 'complete') {
            fetchLatestResults();
        } else if (data.status === 'error') {
            showError(data.error);
        } else {
            setTimeout(poll, 2000);
        }
    };

    poll();
}

// Fetch results
async function fetchLatestResults() {
    const resp = await fetch(`${API_BASE}/api/results/latest`);
    const data = await resp.json();
    processServerData(data);
}
```

### Modifications to `dashboard/index.html`

Add server mode toggle and status display:
```html
<div class="server-controls">
    <button id="serverModeBtn" onclick="toggleServerMode()">Server Mode: OFF</button>
    <div id="serverStatus" style="display:none">
        <span id="jobStatus">Ready</span>
    </div>
</div>
```

Add history tab:
```html
<div class="tabs">
    <button class="tab active" data-tab="analysis">Analysis</button>
    <button class="tab" data-tab="history">History</button>
</div>

<div id="historyTab" style="display:none">
    <canvas id="scoreHistoryChart"></canvas>
    <canvas id="portfolioValueChart"></canvas>
</div>
```

---

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `scripts/history.py` | CREATE | Parquet history functions |
| `scripts/run_pipeline.py` | CREATE | Pipeline runner for server |
| `server.py` | CREATE | FastAPI server |
| `scripts/compile_report.py` | MODIFY | Add history.append_analysis_run() |
| `dashboard/app.js` | MODIFY | Add server mode, polling, history |
| `dashboard/index.html` | MODIFY | Add server toggle, history tab |
| `pyproject.toml` | MODIFY | Add fastapi, uvicorn deps |

---

## Dependencies

```toml
# Add to pyproject.toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-multipart>=0.0.6",
]
```

---

## Usage

```bash
# Start server
uv run python server.py

# Open browser
open http://localhost:8000

# Upload CSV via dashboard → auto-triggers analysis
# Results appear when complete
```
