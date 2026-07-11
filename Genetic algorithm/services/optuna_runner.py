"""Optuna hyperparameter tuning — extracted from notebook."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace as dc_replace

import optuna

from dsm_ga import GAConfig, MODE_WEIGHTS, run_ga
from services.config import AppConfig

optuna.logging.set_verbosity(optuna.logging.WARNING)

VALID_GROUPS = {"weights", "ga_operators", "clustering", "fitness_and_clustering", "all"}


# ---------------------------------------------------------------------------
# Trial config builder (from notebook cell-objective)
# ---------------------------------------------------------------------------

def _suggest_weights(trial: optuna.Trial, fitness_mode: str = "classic"):
    """Sample weights using pair-balanced parameterization.

    Dimensions come in opposing pairs:
      Pair A: S1 (cross-boundary interactions) vs S2 (missing within-cluster)
      Pair B: S3 (consolidation across boundaries) vs S4 / size-imbalance

    The pair_balance parameter (clamped 0.2–0.8) prevents either pair from
    being starved, and within-pair fractions (clamped 0.15–0.85) keep both
    sides of each pair meaningful.

    For 'full' and 'anti_singleton' modes, additional weights (epsilon, zeta)
    are suggested independently.
    """
    # Reserve budget for extra weights so total stays <= 0.95
    active = MODE_WEIGHTS.get(fitness_mode, MODE_WEIGHTS["classic"])
    extra_budget = 0.0
    extra_weights: dict[str, float] = {}

    if "epsilon" in active:
        extra_weights["epsilon"] = trial.suggest_float("epsilon", 0.02, 0.3)
        extra_budget += extra_weights["epsilon"]
    if "zeta" in active:
        extra_weights["zeta"] = trial.suggest_float("zeta", 0.02, 0.3)
        extra_budget += extra_weights["zeta"]

    max_pair_budget = max(0.2, 0.95 - extra_budget)
    total_weight = trial.suggest_float("total_error_weight", 0.2, max_pair_budget)
    pair_balance = trial.suggest_float("pair_balance", 0.2, 0.8)

    pair_a = total_weight * pair_balance
    pair_b = total_weight * (1.0 - pair_balance)

    s1_frac = trial.suggest_float("s1_fraction", 0.15, 0.85)
    s3_frac = trial.suggest_float("s3_fraction", 0.15, 0.85)

    alpha = pair_a * s1_frac
    beta  = pair_a * (1.0 - s1_frac)
    gamma = pair_b * s3_frac
    delta = pair_b * (1.0 - s3_frac)

    result = {"alpha": alpha, "beta": beta, "gamma": gamma, "delta": delta}
    result.update(extra_weights)
    return result


def resolve_best_params(best_params: dict) -> dict:
    """Convert Optuna best_params to config-level parameter names.

    Translates the pair-balanced weight params (total_error_weight,
    pair_balance, s1_fraction, s3_fraction) into alpha/beta/gamma/delta.
    Passes through epsilon, zeta, and other params unchanged.
    """
    resolved: dict = {}
    weight_keys = {"total_error_weight", "pair_balance", "s1_fraction", "s3_fraction"}

    if "total_error_weight" in best_params:
        total = best_params["total_error_weight"]
        pb = best_params["pair_balance"]
        s1f = best_params["s1_fraction"]
        s3f = best_params["s3_fraction"]

        pair_a = total * pb
        pair_b = total * (1.0 - pb)

        resolved["alpha"] = pair_a * s1f
        resolved["beta"]  = pair_a * (1.0 - s1f)
        resolved["gamma"] = pair_b * s3f
        resolved["delta"] = pair_b * (1.0 - s3f)

    for k, v in best_params.items():
        if k not in weight_keys:
            resolved[k] = v

    return resolved


def build_trial_config(trial: optuna.Trial, param_group: str, base: GAConfig) -> GAConfig:
    """Return a GAConfig with trial-suggested values merged over *base*."""
    kwargs: dict = {}

    if param_group in ("weights", "fitness_and_clustering", "all"):
        weights = _suggest_weights(trial, base.fitness_mode)
        kwargs.update(weights)

    if param_group in ("clustering", "fitness_and_clustering", "all"):
        target = trial.suggest_int("target_clusters", 3, 15)
        kwargs["target_clusters"] = target
        kwargs["max_clusters"] = trial.suggest_int("max_clusters", target, 20)
        kwargs["consolidation_mode"] = trial.suggest_categorical(
            "consolidation_mode", ["once", "directional"]
        )

    if param_group in ("ga_operators", "all"):
        kwargs["population_size"] = trial.suggest_int("population_size", 50, 500, step=50)
        kwargs["cxpb"] = trial.suggest_float("cxpb", 0.2, 0.9)
        kwargs["mutpb"] = trial.suggest_float("mutpb", 0.01, 0.3)
        kwargs["tournsize"] = trial.suggest_int("tournsize", 2, 10)

    return dc_replace(base, **kwargs)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_optuna(
    dsm_freq,
    dsm_consol,
    app_config: AppConfig,
    trial_callback: Callable[[int, float, float], None] | None = None,
    cancel_event: threading.Event | None = None,
    seed: int | None = None,
) -> tuple[dict, optuna.Study]:
    """Run an Optuna study and return (best_params, study).

    Parameters
    ----------
    trial_callback : called after each trial with (trial_number, value, best_so_far)
    cancel_event   : checked between trials; raises OptunaError when set
    seed           : if set, seeds the TPE sampler so the study is reproducible.
                     Leave ``None`` for tuning (exploratory); pass a fixed value
                     for the importance analysis so fANOVA scores are stable.
    """
    cfg = app_config.optuna
    base_ga = app_config.ga
    param_group = cfg.param_group

    # Fall back to the app-level seed so tuning is reproducible whenever a global
    # seed is set, without the caller having to pass it explicitly.
    if seed is None:
        seed = base_ga.seed

    if param_group not in VALID_GROUPS:
        raise ValueError(f"param_group must be one of {VALID_GROUPS}, got {param_group!r}")

    def objective(trial: optuna.Trial) -> float:
        if cancel_event is not None and cancel_event.is_set():
            raise optuna.exceptions.OptunaError("Cancelled by user")

        trial_cfg = build_trial_config(trial, param_group, base_ga)
        trial_cfg = dc_replace(
            trial_cfg,
            n_generations=cfg.trial_generations,
            population_size=cfg.trial_population,
        )
        # When the study is seeded, seed each trial's GA deterministically too, so
        # the whole importance pipeline (sampling + evaluation) is reproducible.
        ga_seed = None if seed is None else seed * 100_003 + trial.number
        _, _, fitness = run_ga(dsm_freq, dsm_consol, trial_cfg, verbose=False, seed=ga_seed)

        if trial_callback is not None:
            best_so_far = min(
                (t.value for t in trial.study.trials if t.value is not None),
                default=fitness,
            )
            trial_callback(trial.number, fitness, best_so_far)

        return fitness

    sampler = optuna.samplers.TPESampler(seed=seed) if seed is not None else None
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(objective, n_trials=cfg.n_trials, n_jobs=cfg.n_jobs)

    return study.best_params, study
