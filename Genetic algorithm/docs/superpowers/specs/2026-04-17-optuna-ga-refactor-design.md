# Design: Optuna Hyperparameter Tuning + GA Module Refactor

**Date:** 2026-04-17  
**Author:** Kim Verner Soldal  

---

## Overview

Refactor the DSM genetic algorithm from a monolithic Jupyter notebook into a Python module (`dsm_ga.py`) with two thin notebook frontends: one for running the GA with chosen parameters, one for Optuna-based hyperparameter tuning. The original notebook is preserved in an `archive/` folder.

---

## Goals

- Eliminate logic duplication between notebooks
- Enable Optuna hyperparameter tuning with selectable parameter groups
- Keep the main notebook interactive and readable
- Preserve the original notebook exactly as-is for reference

---

## File Structure

```
Genetic algorithm/
├── dsm_ga.py
├── DSM Optimization Genetic Algorithm - local read.ipynb   ← thin wrapper
├── DSM GA - Hyperparameter Tuning.ipynb                    ← Optuna tuning
├── docs/superpowers/specs/
│   └── 2026-04-17-optuna-ga-refactor-design.md
└── archive/
    └── DSM Optimization Genetic Algorithm - local read.ipynb
```

---

## Module: `dsm_ga.py`

### `load_data(freq_csv_path, consol_csv_path)`

Loads and aligns both DSM matrices. Returns `(DSM_freq, DSM_consol, units, header_list)`.  
Logic extracted unchanged from the existing notebook data-loading cells.

### `GAConfig` (dataclass)

Holds all tunable parameters with defaults matching the current notebook:

```python
@dataclass
class GAConfig:
    # Fitness weights
    alpha: float = 0.15       # type 1 error — connections across cluster boundaries
    beta:  float = 0.05       # type 2 error — no connection within cluster
    gamma: float = 0.15       # type 3 error — consolidation potential across clusters
    delta: float = 0.20       # cluster size imbalance penalty
    # Clustering structure
    max_clusters:       int = 10
    target_clusters:    int = 10
    consolidation_mode: str = 'once'   # 'once' | 'directional'
    # GA operators
    population_size: int   = 200
    n_generations:   int   = 400
    cxpb:            float = 0.5
    mutpb:           float = 0.1
    tournsize:       int   = 5
```

### `run_ga(dsm_freq, dsm_consol, config, checkpoint_file=None, verbose=False)`

Runs the full DEAP genetic algorithm. Returns `(best_individual, logbook, final_fitness)`.

- All DEAP setup (creator, toolbox, stats) is contained within this function to avoid global state issues when called multiple times (e.g., from Optuna trials)
- `checkpoint_file=None` disables checkpointing by default (used in tuning trials); pass a path to enable it for full runs
- `verbose=False` suppresses the live plot during Optuna trials; set `True` in the main notebook

---

## Main Notebook: `DSM Optimization Genetic Algorithm - local read.ipynb`

Cells:

1. **Imports** — `from dsm_ga import load_data, GAConfig, run_ga`
2. **Data loading** — `dsm_freq, dsm_consol, units, header_list = load_data(...)`
3. **Config** — instantiate `GAConfig(...)` with desired parameters
4. **Run** — `best, logbook, fitness = run_ga(dsm_freq, dsm_consol, config, checkpoint_file=..., verbose=True)`
5. **Visualization** — existing cluster visualisation and DSM styling cells, unchanged
6. **Export** — existing Excel export cell, unchanged

---

## Tuning Notebook: `DSM GA - Hyperparameter Tuning.ipynb`

### Parameter groups

A single `PARAM_GROUP` cell controls which parameters Optuna tunes in a given run. Params outside the active group are frozen at base config values.

| Group | Parameters tuned |
|---|---|
| `"weights"` | alpha, beta, gamma, delta |
| `"ga_operators"` | population_size, cxpb, mutpb, tournsize |
| `"clustering"` | target_clusters, max_clusters, consolidation_mode |
| `"fitness_and_clustering"` | alpha, beta, gamma, delta, target_clusters, max_clusters, consolidation_mode |
| `"all"` | all parameters above |

### Trial configuration

Two cells control trial speed vs. quality:

```python
TRIAL_GENERATIONS = 100    # reduced from 400 for fast trials
TRIAL_POPULATION  = 100    # reduced from 200 for fast trials
N_TRIALS          = 50     # number of Optuna trials
N_JOBS            = 1      # set to -1 for parallel trials
```

### Objective function

```python
def objective(trial):
    config = build_trial_config(trial, PARAM_GROUP, base_config)
    config.n_generations = TRIAL_GENERATIONS
    config.population_size = TRIAL_POPULATION
    _, _, fitness = run_ga(dsm_freq, dsm_consol, config, verbose=False)
    return fitness
```

### Study and results

- Runs `optuna.create_study(direction="minimize")`
- After the study, prints best params and plots Optuna's built-in visualisations (parameter importances, optimization history)
- Final cell runs one full-length GA with best params and exports to Excel

---

## Archive

The existing `DSM Optimization Genetic Algorithm - local read.ipynb` is copied to `archive/` before any changes are made. It is not modified.

---

## Parameter search spaces (Optuna)

| Parameter | Type | Range / Choices |
|---|---|---|
| alpha | float | 0.0 – 0.5 |
| beta | float | 0.0 – 0.5 |
| gamma | float | 0.0 – 0.5 |
| delta | float | 0.0 – 0.5 |
| target_clusters | int | 3 – 15 |
| max_clusters | int | target_clusters – 20 (suggested after target_clusters so the lower bound is dynamic) |
| consolidation_mode | categorical | 'once', 'directional' |
| population_size | int | 50 – 500 (step 50) |
| cxpb | float | 0.2 – 0.9 |
| mutpb | float | 0.01 – 0.3 |
| tournsize | int | 2 – 10 |

Weight constraint: alpha + beta + gamma + delta ≤ 1.0 (enforced in `build_trial_config`).

---

## Out of scope

- Parallelising individual GA runs (SCOOP/futures)
- Persisting Optuna studies to a database (SQLite could be added later)
- Any changes to the visualisation or Excel export logic
