"""DSM Genetic Algorithm — core module.

Exports:
    GAConfig      — dataclass of all tunable parameters
    load_data     — load and align DSM matrices from CSV files
    run_ga        — run the DEAP genetic algorithm
"""

import math
import pickle
import random
import threading
from collections.abc import Callable
from dataclasses import dataclass

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
# Exceptions
# ---------------------------------------------------------------------------

class CancelledError(Exception):
    """Raised when a GA run is cancelled via *cancel_event*."""


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
# GA runner
# ---------------------------------------------------------------------------

def run_ga(
    dsm_freq,
    dsm_consol,
    config: GAConfig,
    checkpoint_file: str | None = None,
    verbose: bool = False,
    progress_callback: Callable[[int, float, float, float], None] | None = None,
    cancel_event: threading.Event | None = None,
):
    """Run the DEAP genetic algorithm.

    Parameters
    ----------
    dsm_freq          : pd.DataFrame  — interaction frequency DSM
    dsm_consol        : pd.DataFrame  — consolidation potential DSM
    config            : GAConfig
    checkpoint_file   : str | None    — path for checkpoint pkl; None disables checkpointing
    verbose           : bool          — print progress to stdout
    progress_callback : callable      — called each generation with (gen, avg, min, max)
    cancel_event      : threading.Event — checked each generation; exits early when set

    Returns
    -------
    best          : list[int]   — cluster assignments for each unit
    logbook       : tools.Logbook
    final_fitness : float

    Raises
    ------
    CancelledError  — if cancel_event is set during the run
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
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Run cancelled by user")

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

        avg_val = record["avg"]
        min_val = record["min"]
        max_val = record["max"]

        if verbose and gen % 10 == 0:
            print(
                f"Gen {gen:4d} | "
                f"Avg: {avg_val:.4f} | "
                f"Min: {min_val:.4f} | "
                f"Max: {max_val:.4f}"
            )

        if progress_callback is not None:
            progress_callback(gen, float(avg_val), float(min_val), float(max_val))

        if checkpoint_file and gen % 1000 == 0 and gen > 0:
            cp = dict(population=population, generation=gen, rndstate=random.getstate())
            pickle.dump(cp, open(checkpoint_file, "wb"), 4)

        gen += 1

    best          = hall_of_fame[0]
    final_fitness = eval_fn(best)[0]
    return list(best), logbook, final_fitness
