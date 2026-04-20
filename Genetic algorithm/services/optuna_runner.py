"""Optuna hyperparameter tuning — extracted from notebook."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace as dc_replace

import optuna

from dsm_ga import GAConfig, run_ga
from services.config import AppConfig

optuna.logging.set_verbosity(optuna.logging.WARNING)

VALID_GROUPS = {"weights", "ga_operators", "clustering", "fitness_and_clustering", "all"}


# ---------------------------------------------------------------------------
# Trial config builder (from notebook cell-objective)
# ---------------------------------------------------------------------------

def _suggest_weights(trial: optuna.Trial):
    """Sample 4 weights that sum to <= 1.0."""
    raw = [trial.suggest_float(f"raw_w{i}", 0.0, 1.0) for i in range(4)]
    total = sum(raw)
    if total > 1.0:
        raw = [w / total * 0.95 for w in raw]
    return raw[0], raw[1], raw[2], raw[3]


def build_trial_config(trial: optuna.Trial, param_group: str, base: GAConfig) -> GAConfig:
    """Return a GAConfig with trial-suggested values merged over *base*."""
    kwargs: dict = {}

    if param_group in ("weights", "fitness_and_clustering", "all"):
        a, b, g, d = _suggest_weights(trial)
        kwargs["alpha"] = a
        kwargs["beta"] = b
        kwargs["gamma"] = g
        kwargs["delta"] = d

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
) -> tuple[dict, optuna.Study]:
    """Run an Optuna study and return (best_params, study).

    Parameters
    ----------
    trial_callback : called after each trial with (trial_number, value, best_so_far)
    cancel_event   : checked between trials; raises OptunaError when set
    """
    cfg = app_config.optuna
    base_ga = app_config.ga
    param_group = cfg.param_group

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
        _, _, fitness = run_ga(dsm_freq, dsm_consol, trial_cfg, verbose=False)

        if trial_callback is not None:
            best_so_far = min(
                (t.value for t in trial.study.trials if t.value is not None),
                default=fitness,
            )
            trial_callback(trial.number, fitness, best_so_far)

        return fitness

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=cfg.n_trials, n_jobs=cfg.n_jobs)

    return study.best_params, study
