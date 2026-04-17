# Optuna GA Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the monolithic DSM GA notebook into a `dsm_ga.py` module with a thin main notebook and a new Optuna hyperparameter tuning notebook.

**Architecture:** All GA logic (data loading, fitness function, GA runner) moves into `dsm_ga.py`. The main notebook becomes a 6-cell wrapper. A new tuning notebook imports the same module and runs Optuna with 5 selectable parameter groups. The original notebook is archived untouched.

**Tech Stack:** Python, DEAP, Optuna, pandas, numpy, matplotlib, pytest, Jupyter

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `archive/DSM Optimization Genetic Algorithm - local read.ipynb` | Original notebook, untouched |
| Create | `dsm_ga.py` | `load_data`, `GAConfig`, `_make_eval_fn`, `run_ga` |
| Create | `tests/test_dsm_ga.py` | pytest tests for the module |
| Modify | `DSM Optimization Genetic Algorithm - local read.ipynb` | Thin wrapper — imports, config, run, viz, export |
| Create | `DSM GA - Hyperparameter Tuning.ipynb` | Optuna study with `build_trial_config` + 5 param groups |

---

## Task 1: Archive the original notebook

**Files:**
- Create: `archive/DSM Optimization Genetic Algorithm - local read.ipynb`

- [ ] **Step 1: Create archive directory and copy notebook**

```bash
mkdir -p "archive"
cp "DSM Optimization Genetic Algorithm - local read.ipynb" \
   "archive/DSM Optimization Genetic Algorithm - local read.ipynb"
```

- [ ] **Step 2: Verify copy exists**

```bash
ls archive/
```
Expected: `DSM Optimization Genetic Algorithm - local read.ipynb`

- [ ] **Step 3: Commit**

```bash
git add "archive/DSM Optimization Genetic Algorithm - local read.ipynb"
git commit -m "archive: preserve original monolithic GA notebook"
```

---

## Task 2: Create `dsm_ga.py` — `load_data` and `GAConfig`

**Files:**
- Create: `dsm_ga.py`
- Create: `tests/test_dsm_ga.py`

- [ ] **Step 1: Create tests directory and write failing tests**

Create `tests/__init__.py` (empty) and `tests/test_dsm_ga.py`:

```python
import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from dsm_ga import load_data, GAConfig


FREQ_CSV = "consolidation_potential_DSM_scenario1_interaction_frequency.csv"
CONSOL_CSV = "consolidation_potential_DSM_scenario1_SA4_FTE2_2026-08-04-12h27.csv"


def test_load_data_returns_aligned_matrices():
    dsm_freq, dsm_consol, units, header_list = load_data(FREQ_CSV, CONSOL_CSV)
    assert list(dsm_freq.index) == sorted(units)
    assert list(dsm_freq.columns) == sorted(units)
    assert list(dsm_consol.index) == sorted(units)
    assert list(dsm_consol.columns) == sorted(units)
    assert dsm_freq.shape == dsm_consol.shape
    assert len(header_list) == len(units)


def test_load_data_returns_30_units():
    dsm_freq, dsm_consol, units, header_list = load_data(FREQ_CSV, CONSOL_CSV)
    assert len(units) == 30


def test_gaconfig_defaults():
    cfg = GAConfig()
    assert cfg.alpha == 0.15
    assert cfg.beta == 0.05
    assert cfg.gamma == 0.15
    assert cfg.delta == 0.20
    assert cfg.max_clusters == 10
    assert cfg.target_clusters == 10
    assert cfg.consolidation_mode == "once"
    assert cfg.population_size == 200
    assert cfg.n_generations == 400
    assert cfg.cxpb == 0.5
    assert cfg.mutpb == 0.1
    assert cfg.tournsize == 5


def test_gaconfig_override():
    cfg = GAConfig(alpha=0.3, population_size=50)
    assert cfg.alpha == 0.3
    assert cfg.population_size == 50
    assert cfg.beta == 0.05  # default unchanged
```

- [ ] **Step 2: Run tests to confirm they fail**

Run from the `Genetic algorithm/` directory:
```bash
cd "C:/git/DSM2026/Genetic algorithm"
python -m pytest tests/test_dsm_ga.py -v 2>&1 | head -30
```
Expected: `ERROR` or `ModuleNotFoundError: No module named 'dsm_ga'`

- [ ] **Step 3: Create `dsm_ga.py` with `load_data` and `GAConfig`**

Create `dsm_ga.py`:

```python
"""DSM Genetic Algorithm — core module.

Exports:
    GAConfig      — dataclass of all tunable parameters
    load_data     — load and align DSM matrices from CSV files
    run_ga        — run the DEAP genetic algorithm
"""

import math
import pickle
import random
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from deap import algorithms, base, creator, tools


# ---------------------------------------------------------------------------
# DEAP creator types — initialised once at module level (idempotent guards)
# ---------------------------------------------------------------------------
if not hasattr(creator, "FitnessMin"):
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMin)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class GAConfig:
    """All tunable parameters for the DSM genetic algorithm."""
    # Fitness weights
    alpha: float = 0.15   # type 1 error — connections across cluster boundaries
    beta:  float = 0.05   # type 2 error — no connection within cluster
    gamma: float = 0.15   # type 3 error — consolidation potential across clusters
    delta: float = 0.20   # cluster size imbalance penalty
    # Clustering structure
    max_clusters:       int   = 10
    target_clusters:    int   = 10
    consolidation_mode: str   = "once"  # "once" | "directional"
    # GA operators
    population_size: int   = 200
    n_generations:   int   = 400
    cxpb:            float = 0.5
    mutpb:           float = 0.1
    tournsize:       int   = 5


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(freq_csv_path: str, consol_csv_path: str):
    """Load and align interaction-frequency and consolidation-potential DSMs.

    Returns
    -------
    dsm_freq      : pd.DataFrame  — interaction frequency matrix (sorted units)
    dsm_consol    : pd.DataFrame  — consolidation potential matrix (sorted units)
    units         : list[str]     — sorted unit names
    header_list   : list[str]     — same as units (column order)
    """
    dsm_freq = pd.read_csv(freq_csv_path, index_col=0)

    consol_raw = pd.read_csv(consol_csv_path, header=None)
    col_names = consol_raw.iloc[1, 2:].tolist()
    row_names = consol_raw.iloc[2:, 1].tolist()
    dsm_consol = pd.DataFrame(
        consol_raw.iloc[2:, 2:].values,
        index=row_names,
        columns=col_names,
        dtype=float,
    )

    units = sorted(dsm_freq.index.tolist())
    dsm_freq   = dsm_freq.loc[units, units]
    dsm_consol = dsm_consol.loc[units, units]

    return dsm_freq, dsm_consol, units, dsm_freq.columns.tolist()
```

- [ ] **Step 4: Run tests — expect load_data and GAConfig tests to pass**

```bash
python -m pytest tests/test_dsm_ga.py -v 2>&1 | head -30
```
Expected: `test_load_data_returns_aligned_matrices PASSED`, `test_load_data_returns_30_units PASSED`, `test_gaconfig_defaults PASSED`, `test_gaconfig_override PASSED`

- [ ] **Step 5: Commit**

```bash
git add dsm_ga.py tests/__init__.py tests/test_dsm_ga.py
git commit -m "feat: add dsm_ga module with load_data and GAConfig"
```

---

## Task 3: Add `_make_eval_fn` and `run_ga` to `dsm_ga.py`

**Files:**
- Modify: `dsm_ga.py`
- Modify: `tests/test_dsm_ga.py`

- [ ] **Step 1: Add failing tests for `run_ga`**

Append to `tests/test_dsm_ga.py`:

```python
from dsm_ga import run_ga
import numpy as np


def _make_synthetic_dsm(n=6):
    """Return a tiny symmetric interaction-frequency DSM and a zero consolidation matrix."""
    data = np.zeros((n, n))
    # Add some interactions: units 0-2 interact with each other, 3-5 interact with each other
    for i in range(3):
        for j in range(3):
            if i != j:
                data[i][j] = 1
    for i in range(3, 6):
        for j in range(3, 6):
            if i != j:
                data[i][j] = 1
    units = [f"Unit{i}" for i in range(n)]
    dsm_freq   = pd.DataFrame(data, index=units, columns=units)
    dsm_consol = pd.DataFrame(np.zeros((n, n)), index=units, columns=units)
    return dsm_freq, dsm_consol


def test_run_ga_returns_correct_types():
    dsm_freq, dsm_consol = _make_synthetic_dsm()
    cfg = GAConfig(
        max_clusters=3,
        target_clusters=2,
        population_size=20,
        n_generations=10,
    )
    best, logbook, fitness = run_ga(dsm_freq, dsm_consol, cfg, verbose=False)
    assert isinstance(best, list)
    assert len(best) == 6
    assert all(0 <= x < cfg.max_clusters for x in best)
    assert isinstance(fitness, float)
    assert fitness > 0


def test_run_ga_logbook_has_generations():
    dsm_freq, dsm_consol = _make_synthetic_dsm()
    cfg = GAConfig(
        max_clusters=3,
        target_clusters=2,
        population_size=20,
        n_generations=5,
    )
    _, logbook, _ = run_ga(dsm_freq, dsm_consol, cfg, verbose=False)
    assert len(logbook) == 5


def test_run_ga_fitness_is_finite():
    dsm_freq, dsm_consol = _make_synthetic_dsm()
    cfg = GAConfig(
        max_clusters=3,
        target_clusters=2,
        population_size=20,
        n_generations=10,
    )
    _, _, fitness = run_ga(dsm_freq, dsm_consol, cfg, verbose=False)
    assert math.isfinite(fitness)
```

- [ ] **Step 2: Run tests to confirm new tests fail**

```bash
python -m pytest tests/test_dsm_ga.py::test_run_ga_returns_correct_types -v
```
Expected: `ImportError` or `AttributeError: module 'dsm_ga' has no attribute 'run_ga'`

- [ ] **Step 3: Add `_make_eval_fn`, `_update_plot`, and `run_ga` to `dsm_ga.py`**

Append to `dsm_ga.py` (after `load_data`):

```python
# ---------------------------------------------------------------------------
# Fitness function factory
# ---------------------------------------------------------------------------

def _make_eval_fn(dsm_matrix, consolidation_matrix, config: GAConfig):
    """Return a DEAP-compatible fitness function closed over the DSM data and config."""
    n = len(dsm_matrix)

    # Binarise interaction frequency once
    binary = [
        [1 if dsm_matrix[r][c] > 0 else 0 for c in range(n)]
        for r in range(n)
    ]

    def evaluate(individual):
        CLi = [0] * config.max_clusters
        for elem in range(n):
            CLi[individual[elem]] += 1

        Nc = sum(1 for c in CLi if c > 0)
        S1 = S2 = S3 = 0

        for col in range(n):
            for row in range(n):
                if col == row:
                    continue
                same = individual[col] == individual[row]
                if binary[col][row] != 0 and not same:
                    S1 += 1
                if binary[col][row] == 0 and same:
                    S2 += 1
                if not same:
                    if config.consolidation_mode == "once":
                        if col < row and (
                            consolidation_matrix[col][row] == 1
                            or consolidation_matrix[row][col] == 1
                        ):
                            S3 += 1
                    elif config.consolidation_mode == "directional":
                        S3 += consolidation_matrix[col][row]

        ideal_size = n / config.target_clusters
        size_imbalance = (
            sum(
                (CLi[c] - ideal_size) ** 2
                for c in range(config.max_clusters)
                if CLi[c] > 0
            )
            / config.target_clusters
        )

        mdl_weight = 1.0 - config.alpha - config.beta - config.gamma - config.delta
        MDL = Nc * math.log(n, 2) + math.log(n, 2) * sum(CLi)
        log_factor = 2 * math.log(n + 1, 2)
        fitness = (
            mdl_weight * MDL
            + config.alpha * S1 * log_factor
            + config.beta  * S2 * log_factor
            + config.gamma * S3 * log_factor
            + config.delta * size_imbalance
        )
        return (fitness,)

    return evaluate


# ---------------------------------------------------------------------------
# Live progress plot (used only when verbose=True inside a Jupyter kernel)
# ---------------------------------------------------------------------------

def _update_plot(logbook):
    from IPython.display import clear_output  # only imported when needed

    gens = logbook.select("gen")
    avgs = logbook.select("avg")
    mins = logbook.select("min")
    maxs = logbook.select("max")

    clear_output(wait=True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(gens, avgs, color="black", linewidth=1.5, label="Average")
    ax.plot(gens, mins, color="red",   linewidth=1.5, label="Minimum")
    ax.plot(gens, maxs, color="green", linewidth=1.5, label="Maximum")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Fitness")
    ax.legend(loc="upper right")
    ax.set_title(f"Evolution progress — generation {gens[-1]}")
    plt.tight_layout()
    plt.show()
    print(
        f"Gen {gens[-1]:4d} | "
        f"Avg: {avgs[-1]:.4f} | "
        f"Min: {mins[-1]:.4f} | "
        f"Max: {maxs[-1]:.4f}"
    )


# ---------------------------------------------------------------------------
# GA runner
# ---------------------------------------------------------------------------

def run_ga(dsm_freq, dsm_consol, config: GAConfig, checkpoint_file=None, verbose=False):
    """Run the DEAP genetic algorithm.

    Parameters
    ----------
    dsm_freq        : pd.DataFrame  — interaction frequency DSM
    dsm_consol      : pd.DataFrame  — consolidation potential DSM
    config          : GAConfig
    checkpoint_file : str | None    — path for checkpoint pkl; None disables checkpointing
    verbose         : bool          — show live progress plot (requires Jupyter kernel)

    Returns
    -------
    best          : list[int]   — cluster assignments for each unit
    logbook       : tools.Logbook
    final_fitness : float
    """
    n = len(dsm_freq.columns)
    dsm_matrix    = dsm_freq.values.tolist()
    consol_matrix = dsm_consol.values.tolist()

    eval_fn = _make_eval_fn(dsm_matrix, consol_matrix, config)

    toolbox = base.Toolbox()
    toolbox.register("attribute", random.randint, 0, config.max_clusters - 1)
    toolbox.register(
        "individual", tools.initRepeat, creator.Individual, toolbox.attribute, n=n
    )
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", eval_fn)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register(
        "mutate", tools.mutUniformInt, indpb=0.05, low=0, up=config.max_clusters - 1
    )
    toolbox.register("select", tools.selTournament, tournsize=config.tournsize)

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("min", np.min)
    stats.register("max", np.max)
    logbook = tools.Logbook()

    hall_of_fame = tools.HallOfFame(2)
    population   = toolbox.population(n=config.population_size)

    gen = 0
    while gen < config.n_generations:
        if gen == 0 and checkpoint_file:
            try:
                cp = pickle.load(open(checkpoint_file, "rb"))
                population = cp["population"]
                gen        = cp["generation"]
                random.setstate(cp["rndstate"])
                if verbose:
                    print(f"Checkpoint found, resuming from generation {gen}")
            except IOError:
                if verbose:
                    print("No checkpoint found, starting from scratch")

        population = toolbox.select(population, k=len(population))
        population = [toolbox.clone(ind) for ind in population]
        population = algorithms.varAnd(population, toolbox, cxpb=config.cxpb, mutpb=config.mutpb)

        offspring = [ind for ind in population if not ind.fitness.valid]
        for ind, fit in zip(offspring, map(toolbox.evaluate, offspring)):
            ind.fitness.values = fit

        record = stats.compile(population)
        logbook.record(gen=gen, evals=len(offspring), **record)
        hall_of_fame.update(offspring)

        if verbose and gen % 10 == 0:
            _update_plot(logbook)

        if checkpoint_file and gen % 1000 == 0 and gen > 0:
            cp = dict(population=population, generation=gen, rndstate=random.getstate())
            pickle.dump(cp, open(checkpoint_file, "wb"), 4)

        gen += 1

    best          = hall_of_fame[0]
    final_fitness = eval_fn(best)[0]
    return list(best), logbook, final_fitness
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_dsm_ga.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add dsm_ga.py tests/test_dsm_ga.py
git commit -m "feat: add _make_eval_fn and run_ga to dsm_ga module"
```

---

## Task 4: Refactor the main notebook into a thin wrapper

**Files:**
- Modify: `DSM Optimization Genetic Algorithm - local read.ipynb`

The new notebook keeps the existing **visualization cells** (styles, cluster colouring, Excel export) completely unchanged. Only the data-loading, parameter, fitness-function, and GA-runner cells are replaced.

- [ ] **Step 1: Overwrite the notebook with the thin-wrapper version**

Replace the entire notebook file with the following content. The visualization cells (style_freq, style_consol, cluster colouring, export) are copied verbatim from the original.

Write `DSM Optimization Genetic Algorithm - local read.ipynb`:

```json
{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "%matplotlib inline\n",
    "import matplotlib.pyplot as plt\n",
    "import matplotlib.patches as mpatches\n",
    "import matplotlib.colors as mcolors\n",
    "import numpy as np\n",
    "import pandas as pd\n",
    "from dsm_ga import load_data, GAConfig, run_ga"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## Loading DSM from CSV files"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "freq_csv_path   = \"consolidation_potential_DSM_scenario1_interaction_frequency.csv\"\n",
    "consol_csv_path = \"consolidation_potential_DSM_scenario1_SA4_FTE2_2026-08-04-12h27.csv\"\n",
    "\n",
    "DSM_freq, DSM_consol, units, DSM_header_list = load_data(freq_csv_path, consol_csv_path)\n",
    "DSM = DSM_freq   # primary matrix used in visualisation cells below\n",
    "NUMBER_OF_DSM_ELEMENTS = len(units)\n",
    "csv_file = consol_csv_path.replace(\".csv\", \"\")\n",
    "print(f\"Loaded {NUMBER_OF_DSM_ELEMENTS} units\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def style_freq(df):\n",
    "    vals = df.values.astype(float).copy()\n",
    "    np.fill_diagonal(vals, np.nan)\n",
    "    vmax = np.nanmax(vals)\n",
    "    cmap = plt.cm.YlOrRd\n",
    "    styled = pd.DataFrame('', index=df.index, columns=df.columns)\n",
    "    for i in range(len(df)):\n",
    "        for j in range(len(df.columns)):\n",
    "            if i == j:\n",
    "                styled.iloc[i, j] = 'background-color: #f0f0f0'\n",
    "            elif df.iloc[i, j] > 0:\n",
    "                intensity = df.iloc[i, j] / vmax\n",
    "                colour = mcolors.rgb2hex(cmap(intensity))\n",
    "                styled.iloc[i, j] = f'background-color: {colour}'\n",
    "    return styled\n",
    "\n",
    "DSM_freq.style.apply(style_freq, axis=None)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def style_consol(df):\n",
    "    styled = pd.DataFrame('', index=df.index, columns=df.columns)\n",
    "    for i in range(len(df)):\n",
    "        for j in range(len(df.columns)):\n",
    "            if i == j:\n",
    "                styled.iloc[i, j] = 'background-color: #f0f0f0'\n",
    "            elif df.iloc[i, j] == 1:\n",
    "                styled.iloc[i, j] = 'background-color: #6fa8dc'\n",
    "    return styled\n",
    "\n",
    "DSM_consol.style.apply(style_consol, axis=None)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Optimization Algorithm\n",
    "### Parameters"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "config = GAConfig(\n",
    "    alpha=0.15,\n",
    "    beta=0.05,\n",
    "    gamma=0.15,\n",
    "    delta=0.20,\n",
    "    max_clusters=10,\n",
    "    target_clusters=10,\n",
    "    consolidation_mode='once',\n",
    "    population_size=200,\n",
    "    n_generations=400,\n",
    "    cxpb=0.5,\n",
    "    mutpb=0.1,\n",
    "    tournsize=5,\n",
    ")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["### Optimization loop"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "checkpoint_file = csv_file + \"_checkpoint.pkl\"\n",
    "try:\n",
    "    os.remove(checkpoint_file)\n",
    "    print(\"Deleted existing checkpoint\")\n",
    "except FileNotFoundError:\n",
    "    print(\"No checkpoint found\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "best, logbook, final_fitness = run_ga(\n",
    "    DSM_freq, DSM_consol, config,\n",
    "    checkpoint_file=checkpoint_file,\n",
    "    verbose=True,\n",
    ")\n",
    "print(f\"Best solution: {best}\")\n",
    "print(f\"Final fitness: {final_fitness:.4f}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["# Export optimized model to Excel"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "group_assignments = list(best)\n",
    "sorted_indices = sorted(range(NUMBER_OF_DSM_ELEMENTS), key=lambda i: group_assignments[i])\n",
    "sorted_units  = [DSM_header_list[i] for i in sorted_indices]\n",
    "sorted_groups = [group_assignments[i] for i in sorted_indices]\n",
    "\n",
    "DSM_reordered = DSM.iloc[sorted_indices].iloc[:, sorted_indices].copy()\n",
    "DSM_reordered.index   = sorted_units\n",
    "DSM_reordered.columns = sorted_units\n",
    "\n",
    "DSM_consol_reordered = DSM_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()\n",
    "DSM_consol_reordered.index   = sorted_units\n",
    "DSM_consol_reordered.columns = sorted_units\n",
    "\n",
    "unique_clusters = sorted(set(sorted_groups))\n",
    "palette = plt.cm.Set2(np.linspace(0, 0.8, len(unique_clusters)))\n",
    "cluster_color_map = {c: mcolors.rgb2hex(palette[i]) for i, c in enumerate(unique_clusters)}\n",
    "\n",
    "cluster_starts = {}\n",
    "cluster_ends   = {}\n",
    "for idx, group in enumerate(sorted_groups):\n",
    "    if group not in cluster_starts:\n",
    "        cluster_starts[group] = idx\n",
    "    cluster_ends[group] = idx\n",
    "\n",
    "COLOUR_ACHIEVED = '#93c47d'\n",
    "COLOUR_MISSED   = '#e06666'\n",
    "\n",
    "def _cell_style(i, j, has_consol):\n",
    "    parts = []\n",
    "    same_cluster = sorted_groups[i] == sorted_groups[j]\n",
    "    if has_consol and same_cluster:\n",
    "        parts.append(f'background-color: {COLOUR_ACHIEVED}')\n",
    "    elif has_consol and not same_cluster:\n",
    "        parts.append(f'background-color: {COLOUR_MISSED}')\n",
    "    if same_cluster:\n",
    "        c     = sorted_groups[i]\n",
    "        color = cluster_color_map[c]\n",
    "        if i == cluster_starts[c]: parts.append(f'border-top: 2px solid {color}')\n",
    "        if i == cluster_ends[c]:   parts.append(f'border-bottom: 2px solid {color}')\n",
    "        if j == cluster_starts[c]: parts.append(f'border-left: 2px solid {color}')\n",
    "        if j == cluster_ends[c]:   parts.append(f'border-right: 2px solid {color}')\n",
    "    return '; '.join(parts)\n",
    "\n",
    "def style_func(df):\n",
    "    styled = pd.DataFrame('', index=df.index, columns=df.columns)\n",
    "    for i in range(len(df)):\n",
    "        for j in range(len(df.columns)):\n",
    "            styled.iloc[i, j] = _cell_style(i, j, DSM_consol_reordered.iloc[i, j] == 1)\n",
    "    return styled\n",
    "\n",
    "def style_func_consol(df):\n",
    "    styled = pd.DataFrame('', index=df.index, columns=df.columns)\n",
    "    for i in range(len(df)):\n",
    "        for j in range(len(df.columns)):\n",
    "            styled.iloc[i, j] = _cell_style(i, j, df.iloc[i, j] == 1)\n",
    "    return styled\n",
    "\n",
    "DSM_styled = DSM_reordered.style.apply(style_func, axis=None)\n",
    "DSM_styled"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "df_optimized_grouping = pd.DataFrame({\n",
    "    'Unit Name': sorted_units,\n",
    "    'Cluster':   [f'Cluster {g}' for g in sorted_groups],\n",
    "})\n",
    "df_optimized_grouping"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "DSM_consol_styled = DSM_consol_reordered.style.apply(style_func_consol, axis=None)\n",
    "\n",
    "optimized_path = csv_file + '_optimized.xlsx'\n",
    "with pd.ExcelWriter(optimized_path, engine='openpyxl') as writer:\n",
    "    DSM_styled.to_excel(writer, sheet_name='dsm_optimized')\n",
    "    DSM_consol_styled.to_excel(writer, sheet_name='dsm_consolidation')\n",
    "    df_optimized_grouping.to_excel(writer, sheet_name='grouping')\n",
    "    DSM_freq.to_excel(writer, sheet_name='interaction_frequency')\n",
    "    DSM_consol.to_excel(writer, sheet_name='consolidation_potential')\n",
    "\n",
    "print(f'Exported to {optimized_path}')"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.9.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Verify the notebook is valid JSON**

```bash
python -c "import json; json.load(open('DSM Optimization Genetic Algorithm - local read.ipynb')); print('Valid JSON')"
```
Expected: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
git add "DSM Optimization Genetic Algorithm - local read.ipynb"
git commit -m "refactor: replace main notebook with thin wrapper over dsm_ga module"
```

---

## Task 5: Create the hyperparameter tuning notebook

**Files:**
- Create: `DSM GA - Hyperparameter Tuning.ipynb`

- [ ] **Step 1: Create the tuning notebook**

Write `DSM GA - Hyperparameter Tuning.ipynb`:

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# DSM GA — Hyperparameter Tuning with Optuna\n",
    "\n",
    "Uses Optuna to find optimal parameters for the DSM genetic algorithm.\n",
    "\n",
    "## How to use\n",
    "1. Set `PARAM_GROUP` in the cell below to one of: `\"weights\"`, `\"ga_operators\"`, `\"clustering\"`, `\"fitness_and_clustering\"`, `\"all\"`\n",
    "2. Adjust `TRIAL_GENERATIONS`, `TRIAL_POPULATION`, `N_TRIALS` for speed vs. quality\n",
    "3. Run all cells\n",
    "4. The final cell runs a full GA with the best found parameters and exports to Excel"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "%matplotlib inline\n",
    "import matplotlib.pyplot as plt\n",
    "import matplotlib.colors as mcolors\n",
    "import numpy as np\n",
    "import pandas as pd\n",
    "import optuna\n",
    "from dataclasses import replace as dc_replace\n",
    "from dsm_ga import load_data, GAConfig, run_ga\n",
    "\n",
    "optuna.logging.set_verbosity(optuna.logging.WARNING)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## Data"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "freq_csv_path   = \"consolidation_potential_DSM_scenario1_interaction_frequency.csv\"\n",
    "consol_csv_path = \"consolidation_potential_DSM_scenario1_SA4_FTE2_2026-08-04-12h27.csv\"\n",
    "\n",
    "DSM_freq, DSM_consol, units, DSM_header_list = load_data(freq_csv_path, consol_csv_path)\n",
    "print(f\"Loaded {len(units)} units\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## Tuning configuration"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ── Parameter group ─────────────────────────────────────────────────────────\n",
    "# Choose ONE of:\n",
    "#   'weights'               — alpha, beta, gamma, delta\n",
    "#   'ga_operators'          — population_size, cxpb, mutpb, tournsize\n",
    "#   'clustering'            — target_clusters, max_clusters, consolidation_mode\n",
    "#   'fitness_and_clustering'— weights + clustering\n",
    "#   'all'                   — every parameter\n",
    "PARAM_GROUP = \"weights\"\n",
    "\n",
    "# ── Trial budget ─────────────────────────────────────────────────────────────\n",
    "TRIAL_GENERATIONS = 100   # reduced GA run per trial (full run uses config.n_generations)\n",
    "TRIAL_POPULATION  = 100   # reduced population per trial\n",
    "N_TRIALS          = 50    # number of Optuna trials\n",
    "N_JOBS            = 1     # set to -1 for parallel trials\n",
    "\n",
    "# ── Base config (frozen params stay at these values) ─────────────────────────\n",
    "base_config = GAConfig()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## Objective function"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "VALID_GROUPS = {\"weights\", \"ga_operators\", \"clustering\", \"fitness_and_clustering\", \"all\"}\n",
    "assert PARAM_GROUP in VALID_GROUPS, f\"PARAM_GROUP must be one of {VALID_GROUPS}\"\n",
    "\n",
    "\n",
    "def _suggest_weights(trial):\n",
    "    \"\"\"Sample 4 weights that sum to ≤ 1.0.\"\"\"\n",
    "    raw = [trial.suggest_float(f\"raw_w{i}\", 0.0, 1.0) for i in range(4)]\n",
    "    total = sum(raw)\n",
    "    if total > 1.0:\n",
    "        raw = [w / total * 0.95 for w in raw]\n",
    "    return raw[0], raw[1], raw[2], raw[3]\n",
    "\n",
    "\n",
    "def build_trial_config(trial, param_group: str, base: GAConfig) -> GAConfig:\n",
    "    \"\"\"Return a GAConfig with trial-suggested values merged over base.\"\"\"\n",
    "    kwargs = {}\n",
    "\n",
    "    if param_group in (\"weights\", \"fitness_and_clustering\", \"all\"):\n",
    "        a, b, g, d = _suggest_weights(trial)\n",
    "        kwargs[\"alpha\"] = a\n",
    "        kwargs[\"beta\"]  = b\n",
    "        kwargs[\"gamma\"] = g\n",
    "        kwargs[\"delta\"] = d\n",
    "\n",
    "    if param_group in (\"clustering\", \"fitness_and_clustering\", \"all\"):\n",
    "        target = trial.suggest_int(\"target_clusters\", 3, 15)\n",
    "        kwargs[\"target_clusters\"]    = target\n",
    "        kwargs[\"max_clusters\"]       = trial.suggest_int(\"max_clusters\", target, 20)\n",
    "        kwargs[\"consolidation_mode\"] = trial.suggest_categorical(\n",
    "            \"consolidation_mode\", [\"once\", \"directional\"]\n",
    "        )\n",
    "\n",
    "    if param_group in (\"ga_operators\", \"all\"):\n",
    "        kwargs[\"population_size\"] = trial.suggest_int(\"population_size\", 50, 500, step=50)\n",
    "        kwargs[\"cxpb\"]            = trial.suggest_float(\"cxpb\", 0.2, 0.9)\n",
    "        kwargs[\"mutpb\"]           = trial.suggest_float(\"mutpb\", 0.01, 0.3)\n",
    "        kwargs[\"tournsize\"]        = trial.suggest_int(\"tournsize\", 2, 10)\n",
    "\n",
    "    return dc_replace(base, **kwargs)\n",
    "\n",
    "\n",
    "def objective(trial):\n",
    "    cfg = build_trial_config(trial, PARAM_GROUP, base_config)\n",
    "    cfg = dc_replace(cfg, n_generations=TRIAL_GENERATIONS, population_size=TRIAL_POPULATION)\n",
    "    _, _, fitness = run_ga(DSM_freq, DSM_consol, cfg, verbose=False)\n",
    "    return fitness"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## Run study"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "study = optuna.create_study(direction=\"minimize\")\n",
    "study.optimize(objective, n_trials=N_TRIALS, n_jobs=N_JOBS, show_progress_bar=True)\n",
    "\n",
    "print(f\"\\nBest trial: #{study.best_trial.number}\")\n",
    "print(f\"Best fitness: {study.best_value:.4f}\")\n",
    "print(\"\\nBest parameters:\")\n",
    "for k, v in study.best_params.items():\n",
    "    print(f\"  {k}: {v}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## Results visualisation"]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from optuna.visualization.matplotlib import (\n",
    "    plot_optimization_history,\n",
    "    plot_param_importances,\n",
    ")\n",
    "\n",
    "fig, axes = plt.subplots(1, 2, figsize=(14, 5))\n",
    "plt.sca(axes[0])\n",
    "plot_optimization_history(study)\n",
    "axes[0].set_title(\"Optimization history\")\n",
    "plt.sca(axes[1])\n",
    "plot_param_importances(study)\n",
    "axes[1].set_title(\"Parameter importances\")\n",
    "plt.tight_layout()\n",
    "plt.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Full run with best parameters\n",
    "\n",
    "Applies the best Optuna parameters on top of `base_config` and runs a full-length GA, then exports to Excel."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "best_config = build_trial_config(\n",
    "    study.best_trial, PARAM_GROUP, base_config\n",
    ")\n",
    "print(\"Running full GA with best config:\")\n",
    "print(best_config)\n",
    "\n",
    "best, logbook, final_fitness = run_ga(\n",
    "    DSM_freq, DSM_consol, best_config, verbose=True\n",
    ")\n",
    "print(f\"\\nFinal fitness: {final_fitness:.4f}\")\n",
    "print(f\"Best solution: {best}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "NUMBER_OF_DSM_ELEMENTS = len(units)\n",
    "group_assignments = list(best)\n",
    "sorted_indices = sorted(range(NUMBER_OF_DSM_ELEMENTS), key=lambda i: group_assignments[i])\n",
    "sorted_units  = [DSM_header_list[i] for i in sorted_indices]\n",
    "sorted_groups = [group_assignments[i] for i in sorted_indices]\n",
    "\n",
    "df_optimized_grouping = pd.DataFrame({\n",
    "    'Unit Name': sorted_units,\n",
    "    'Cluster':   [f'Cluster {g}' for g in sorted_groups],\n",
    "})\n",
    "display(df_optimized_grouping)\n",
    "\n",
    "csv_file = consol_csv_path.replace('.csv', '')\n",
    "output_path = csv_file + f'_tuned_{PARAM_GROUP}_optimized.xlsx'\n",
    "\n",
    "DSM_reordered = DSM_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()\n",
    "DSM_reordered.index = DSM_reordered.columns = sorted_units\n",
    "DSM_consol_reordered = DSM_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()\n",
    "DSM_consol_reordered.index = DSM_consol_reordered.columns = sorted_units\n",
    "\n",
    "with pd.ExcelWriter(output_path, engine='openpyxl') as writer:\n",
    "    DSM_reordered.to_excel(writer, sheet_name='dsm_optimized')\n",
    "    DSM_consol_reordered.to_excel(writer, sheet_name='dsm_consolidation')\n",
    "    df_optimized_grouping.to_excel(writer, sheet_name='grouping')\n",
    "    DSM_freq.to_excel(writer, sheet_name='interaction_frequency')\n",
    "    DSM_consol.to_excel(writer, sheet_name='consolidation_potential')\n",
    "\n",
    "print(f'Exported to {output_path}')"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.9.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Verify the notebook is valid JSON**

```bash
python -c "import json; json.load(open('DSM GA - Hyperparameter Tuning.ipynb')); print('Valid JSON')"
```
Expected: `Valid JSON`

- [ ] **Step 3: Run all tests one final time to confirm nothing broke**

```bash
python -m pytest tests/test_dsm_ga.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add "DSM GA - Hyperparameter Tuning.ipynb"
git commit -m "feat: add Optuna hyperparameter tuning notebook with 5 param groups"
```

---

## Self-Review Notes

- **Spec coverage:** All five sections covered — archive ✓, `dsm_ga.py` with `load_data`/`GAConfig`/`run_ga` ✓, main notebook refactored ✓, tuning notebook with all 5 groups ✓, parameter search spaces ✓
- **DEAP creator singleton:** Guarded with `hasattr` at module level — safe across multiple `run_ga` calls
- **Weight constraint:** Enforced in `_suggest_weights` via normalization
- **`build_trial_config` type consistency:** Same function used in both the objective and the final full-run cell
- **Variable name continuity:** Main notebook exposes `best`, `DSM_header_list`, `NUMBER_OF_DSM_ELEMENTS`, `DSM`, `DSM_consol` — all names used by the unchanged visualization cells
