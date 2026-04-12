# DSM Optimization Genetic Algorithm

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

## Setup

From the `Genetic algorithm/` directory:

```bash
# Create a virtual environment with Python 3.11
uv venv --python 3.11

# Install all dependencies
uv sync --no-install-project

# Register the Jupyter kernel
uv run python -m ipykernel install --user --name dsm-ga --display-name "DSM Genetic Algorithm (3.11)"
```

## Running the notebook

```bash
uv run jupyter lab
```

This opens Jupyter in your browser. Open `DSM Optimization Genetic Algorithm - local read.ipynb`.

## Selecting the right kernel

1. In the open notebook, click **Kernel** in the top menu bar
2. Select **Change kernel**
3. Choose **DSM Genetic Algorithm (3.11)**

If the kernel does not appear, re-run the full command above and refresh the page:

```bash
uv run python -m ipykernel install --user --name dsm-ga --display-name "DSM Genetic Algorithm (3.11)"
```

## Note on `scoop`

The notebook uses the `scoop` library for parallel computing. This library has known limitations on Windows and may fail when running cells that use `scoop.futures`. This is a platform limitation and does not affect the rest of the notebook.
