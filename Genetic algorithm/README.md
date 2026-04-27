# DSM Optimization Genetic Algorithm

A web application and CLI for running Design Structure Matrix (DSM) optimization using a genetic algorithm (DEAP), with Optuna hyperparameter tuning and publication-quality visualization.

## TLDR: Quick Start (Development)

```bash
uv venv --python 3.11 && uv sync   # one-time setup
uv run dsm-ga dev                   # starts API (:8099) + Vite (:5173) together
```

Open http://localhost:5173 — hot-reload frontend, API proxied automatically.

---

## Prerequisites

### Install uv

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv | sh
```

After installing, restart your terminal so the `uv` command is available.

### Install Node.js (for frontend development only)

Node.js 18+ is required if you want to modify the frontend. The pre-built frontend is included in `frontend/dist/` and does not require Node.js to run.

## Setup

From the `Genetic algorithm/` directory:

```bash
# Create a virtual environment with Python 3.11
uv venv --python 3.11

# Install all dependencies (including the dsm-ga CLI)
uv sync
```

## Serving the pre-built frontend

If you don't need to modify the frontend, you can serve the pre-built bundle directly:

```bash
uv run dsm-ga serve
```

This starts the server at http://127.0.0.1:8080 serving the frontend from `frontend/dist/`.

Options:
```bash
uv run dsm-ga serve --host 0.0.0.0 --port 8080
```

To rebuild the frontend bundle:
```bash
cd frontend && npm install && npm run build
```

## Frontend development

For active frontend work, use the dev command which starts both the backend API and Vite dev server with hot reload:

```bash
uv run dsm-ga dev
```

This starts:
- Backend API on http://127.0.0.1:8099 (with auto-reload)
- Vite dev server on http://localhost:5173 (proxies `/api` to the backend)

Open http://localhost:5173 in your browser.

The web UI provides four actions:
- **Optimize** — run the GA with configurable parameters and watch live fitness progress
- **Tune** — run Optuna hyperparameter tuning with live trial-by-trial results
- **Tune & Optimize** — run tuning first, then a full GA with the best parameters
- **Visualize** — generate a publication-quality DSM figure

## CLI usage

All commands use a `config.yaml` file for settings. To create a starter config:

```bash
uv run dsm-ga init-config
```

Then run any command:

```bash
# Run GA optimization
uv run dsm-ga run config.yaml

# Run Optuna hyperparameter tuning
uv run dsm-ga tune config.yaml

# Run tuning then full GA with best params
uv run dsm-ga tune-optimize config.yaml

# Generate a DSM figure
uv run dsm-ga visualize config.yaml
uv run dsm-ga visualize config.yaml --result-xlsx results/optimized.xlsx --title "My DSM"
```

## Configuration

All settings are in `config.yaml`:

```yaml
data:
  freq_csv: "interaction_frequency.csv"
  consol_csv: "consolidation_potential.csv"
  output_dir: "./results"

ga:
  alpha: 0.15          # type 1 error weight
  beta: 0.05           # type 2 error weight
  gamma: 0.15          # type 3 error weight
  delta: 0.20          # cluster imbalance weight
  max_clusters: 10
  target_clusters: 10
  consolidation_mode: "once"   # "once" or "directional"
  population_size: 200
  n_generations: 400
  cxpb: 0.5
  mutpb: 0.1
  tournsize: 5

optuna:
  param_group: "weights"   # "weights", "ga_operators", "clustering", "fitness_and_clustering", "all"
  n_trials: 50
  n_jobs: 1
  trial_generations: 100
  trial_population: 100
```

The web UI loads these values as defaults and lets you override them per-run.

## Running tests

```bash
uv run pytest tests/ -v
```

> **Tip:** All `uv run` commands work without manually activating the virtual environment. If you prefer, you can activate it once with `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux) and then omit the `uv run` prefix.
