"""Sensitivity analysis helpers — importance, robustness, and weight sweeps."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import asdict, replace as dc_replace
from pathlib import Path

import numpy as np
import optuna
from sklearn.metrics import adjusted_rand_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dsm_ga import CancelledError, GAConfig, MODE_WEIGHTS, run_ga
from services.config import AppConfig
from services.optuna_runner import build_trial_config, run_optuna


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _save_importance_chart(
    importances: dict[str, float],
    path: Path,
    std: dict[str, float] | None = None,
    subtitle: str | None = None,
) -> None:
    """Save a horizontal bar chart of parameter importances.

    If *std* is provided (from averaging over repeated studies), horizontal
    error bars are drawn to show the run-to-run spread.
    """
    sorted_items = sorted(importances.items(), key=lambda x: x[1])
    names = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    errors = [std.get(k, 0.0) for k, _ in sorted_items] if std else None

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.5)))
    ax.barh(names, values, color="#3b82f6",
            xerr=errors, error_kw={"ecolor": "#1e3a8a", "capsize": 4} if errors else {})
    ax.set_xlim(0, 1)
    ax.set_xlabel("Importance (fANOVA)")
    title = "Parameter Importance"
    if subtitle:
        ax.set_title(f"{title}\n{subtitle}", fontsize=11)
    else:
        ax.set_title(title)
    for i, v in enumerate(values):
        label = f"{v:.3f} ± {errors[i]:.3f}" if errors else f"{v:.3f}"
        ax.text(v + (errors[i] if errors else 0) + 0.01, i, label, va="center", fontsize=8)
    plt.tight_layout()
    fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _save_robustness_chart(runs: list[dict], stats: dict, path: Path) -> None:
    """Save a bar chart of per-run fitness with mean/std annotation."""
    run_nums = list(range(1, len(runs) + 1))
    fitnesses = [r["fitness"] for r in runs]

    fig, ax = plt.subplots(figsize=(max(6, len(runs) * 0.8), 4))
    bars = ax.bar(run_nums, fitnesses, color="#6366f1", width=0.6)
    ax.axhline(stats["mean_fitness"], color="#ef4444", linestyle="--", linewidth=1.5, label=f"Mean: {stats['mean_fitness']:.2f}")
    ax.fill_between(
        [0.5, len(runs) + 0.5],
        stats["mean_fitness"] - stats["std_fitness"],
        stats["mean_fitness"] + stats["std_fitness"],
        alpha=0.15, color="#ef4444", label=f"Std: {stats['std_fitness']:.2f}",
    )
    ax.set_xlabel("Run")
    ax.set_ylabel("Fitness")
    ax.set_title(f"Robustness Analysis — {len(runs)} runs  |  ARI mean: {stats['ari_mean']:.4f}")
    ax.set_xticks(run_nums)
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _save_sweep_chart(sweeps: dict[str, list[dict]], path: Path) -> None:
    """Save a grid of weight sweep line charts."""
    weight_names = [w for w in sweeps]
    n = len(weight_names)
    cols = min(n, 3)
    rows = (n + cols - 1) // cols

    # Compute global fitness range across all sweeps for consistent y-axis
    all_fit = [d["fitness"] for entries in sweeps.values() for d in entries]
    if all_fit:
        global_min = np.floor(min(all_fit) / 50) * 50  # round down to nearest 50
        global_max = np.ceil(max(all_fit) / 50) * 50    # round up to nearest 50
        # Ensure at least some range
        if global_max - global_min < 10:
            global_min -= 25
            global_max += 25
    else:
        global_min, global_max = 0, 1

    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows), squeeze=False)
    for idx, wname in enumerate(weight_names):
        ax = axes[idx // cols][idx % cols]
        data = sweeps[wname]
        values = [d["value"] for d in data]
        fitnesses = [d["fitness"] for d in data]
        clusters = [d["n_clusters"] for d in data]

        ax.plot(values, fitnesses, "o-", color="#3b82f6", linewidth=1.5, markersize=4, label="Fitness")
        ax.set_xlabel(wname)
        ax.set_ylabel("Fitness", color="#3b82f6")
        ax.set_ylim(global_min, global_max)
        ax.tick_params(axis="y", labelcolor="#3b82f6")

        ax2 = ax.twinx()
        ax2.plot(values, clusters, "s--", color="#f97316", linewidth=1, markersize=3, label="Clusters")
        ax2.set_ylabel("Clusters", color="#f97316")
        ax2.tick_params(axis="y", labelcolor="#f97316")

        ax.set_title(f"Sweep: {wname}")

    # Hide unused subplots
    for idx in range(n, rows * cols):
        axes[idx // cols][idx % cols].set_visible(False)

    plt.tight_layout()
    fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 1. Parameter importance (fANOVA via Optuna)
# ---------------------------------------------------------------------------

# Map internal Optuna weight params to user-facing names
_PARAM_NAMES = {
    "total_error_weight": "total_error_weight",
    "pair_balance": "pair_balance (S1S2 vs S3S4)",
    "s1_fraction": "s1_fraction (S1 vs S2)",
    "s3_fraction": "s3_fraction (S3 vs S4)",
}


def _study_importances(study: optuna.Study, evaluator_seed: int | None = None) -> dict[str, float]:
    """fANOVA importances for one study, with user-facing param names.

    The default fANOVA evaluator fits a random forest with its own RNG, so its
    output varies run-to-run even for an identical study. Passing
    *evaluator_seed* fixes that forest so the importances are reproducible.
    """
    evaluator = (
        optuna.importance.FanovaImportanceEvaluator(seed=evaluator_seed)
        if evaluator_seed is not None
        else None
    )
    raw = optuna.importance.get_param_importances(study, evaluator=evaluator)
    return {_PARAM_NAMES.get(k, k): v for k, v in raw.items()}


def run_importance(
    dsm_freq,
    dsm_consol,
    app_config: AppConfig,
    n_trials: int = 50,
    param_group: str = "weights",
    existing_study: optuna.Study | None = None,
    callback: Callable[[int, float, float], None] | None = None,
    cancel_event: threading.Event | None = None,
    log_dir: str | None = None,
    n_repeats: int = 1,
    seed: int | None = None,
) -> tuple[dict[str, float], str, optuna.Study, dict[str, float]]:
    """Compute fANOVA parameter importances.

    fANOVA importances computed from a single Optuna study are *not* stable:
    the sampler is stochastic, so two runs of the same configuration can rank
    the parameters differently. To get a reproducible, publishable result,
    pass ``seed`` (fixes the sampler) and/or ``n_repeats > 1`` (runs that many
    independent seeded studies and averages the importances, reporting the
    run-to-run standard deviation).

    Behaviour:
      * ``n_repeats > 1`` or ``seed is not None`` → run fresh **seeded** studies
        (``existing_study`` is ignored) and average. ``source`` reports the
        number of repeats and the base seed.
      * otherwise → legacy behaviour: reuse *existing_study* if it has enough
        completed trials, else run one fresh (unseeded) study.

    Parameters
    ----------
    callback : called after each trial with ``(trial_num, value, best_so_far)``
    log_dir  : if set, write ``config.json`` and ``summary.json`` there

    Returns
    -------
    (importances, source, study, std)
        *importances* maps parameter names to mean fANOVA scores,
        *std* maps the same names to the run-to-run standard deviation
        (all zeros when a single study is used).
    """
    # Fall back to the app-level seed so importance honours the global seed.
    if seed is None:
        seed = app_config.ga.seed
    reproducible = n_repeats > 1 or seed is not None

    per_repeat: list[dict[str, float]] = []
    study: optuna.Study | None = None

    if reproducible:
        cfg = dc_replace(app_config.optuna, n_trials=n_trials, param_group=param_group)
        tmp_app = AppConfig(data=app_config.data, ga=app_config.ga, optuna=cfg)
        base_seed = seed if seed is not None else 0
        for i in range(max(1, n_repeats)):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Importance analysis cancelled by user")
            _, study = run_optuna(
                dsm_freq,
                dsm_consol,
                tmp_app,
                trial_callback=callback,
                cancel_event=cancel_event,
                seed=base_seed + i,
            )
            per_repeat.append(_study_importances(study, evaluator_seed=base_seed + i))
        source = f"averaged over {max(1, n_repeats)} seeded studies (base seed {base_seed})"
    else:
        # Legacy single-study path (may reuse a prior tuning study) ------------
        reuse = (
            existing_study is not None
            and len([t for t in existing_study.trials
                     if t.state == optuna.trial.TrialState.COMPLETE]) >= n_trials
        )
        if reuse:
            study = existing_study
            source = "reused"
        else:
            cfg = dc_replace(app_config.optuna, n_trials=n_trials, param_group=param_group)
            tmp_app = AppConfig(data=app_config.data, ga=app_config.ga, optuna=cfg)
            _, study = run_optuna(
                dsm_freq,
                dsm_consol,
                tmp_app,
                trial_callback=callback,
                cancel_event=cancel_event,
            )
            source = "new_study"
        per_repeat.append(_study_importances(study))

    # Aggregate mean / std across repeats (union of all param names) -----------
    all_keys = sorted({k for rep in per_repeat for k in rep})
    importances = {k: float(np.mean([rep.get(k, 0.0) for rep in per_repeat])) for k in all_keys}
    std = {k: float(np.std([rep.get(k, 0.0) for rep in per_repeat])) for k in all_keys}

    # Logging ------------------------------------------------------------------
    if log_dir is not None:
        p = Path(log_dir)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "config.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "n_trials": n_trials,
                    "param_group": param_group,
                    "n_repeats": n_repeats,
                    "seed": seed,
                    "source": source,
                    "ga": asdict(app_config.ga),
                },
                f,
                indent=2,
            )
        with open(p / "summary.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "importances": importances,
                    "std": std,
                    "source": source,
                    "n_repeats": n_repeats,
                    "seed": seed,
                    "per_repeat": per_repeat,
                },
                f,
                indent=2,
            )
        subtitle = source if reproducible else None
        _save_importance_chart(importances, p / "importance.png",
                               std=std if reproducible else None, subtitle=subtitle)

    return importances, source, study, std


# ---------------------------------------------------------------------------
# 2. Robustness analysis (repeated runs + ARI matrix)
# ---------------------------------------------------------------------------

def run_robustness(
    dsm_freq,
    dsm_consol,
    ga_config: GAConfig,
    n_repeats: int = 10,
    callback: Callable[[int, int, float], None] | None = None,
    cancel_event: threading.Event | None = None,
    log_dir: str | None = None,
) -> dict:
    """Run the GA *n_repeats* times and measure result stability.

    Parameters
    ----------
    callback : called after each run with ``(run_num, n_repeats, fitness)``
    log_dir  : if set, write per-run and summary JSON files

    Returns
    -------
    dict with keys: ``runs``, ``mean_fitness``, ``std_fitness``,
    ``min_fitness``, ``max_fitness``, ``ari_matrix``, ``ari_mean``.
    """
    runs: list[dict] = []
    # When a global seed is set, give each repeat a distinct child seed so the
    # analysis is reproducible yet still measures genuine run-to-run spread. With
    # no seed, every run is independently random (the original behaviour).
    base_seed = ga_config.seed

    for i in range(n_repeats):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Robustness analysis cancelled by user")

        run_seed = None if base_seed is None else base_seed + i
        best, logbook, fitness = run_ga(
            dsm_freq, dsm_consol, ga_config, verbose=False, cancel_event=cancel_event,
            seed=run_seed,
        )

        logbook_records = [
            {"gen": rec["gen"], "avg": float(rec["avg"]),
             "min": float(rec["min"]), "max": float(rec["max"])}
            for rec in logbook
        ]

        runs.append({
            "fitness": fitness,
            "clusters": best,
            "logbook": logbook_records,
        })

        if callback is not None:
            callback(i + 1, n_repeats, fitness)

    # Pairwise Adjusted Rand Index ---------------------------------------------
    n = len(runs)
    ari_matrix = [[0.0] * n for _ in range(n)]
    ari_values: list[float] = []

    for i in range(n):
        for j in range(n):
            score = adjusted_rand_score(runs[i]["clusters"], runs[j]["clusters"])
            ari_matrix[i][j] = score
            if i < j:
                ari_values.append(score)

    ari_mean = float(np.mean(ari_values)) if ari_values else 1.0

    fitnesses = [r["fitness"] for r in runs]
    result = {
        "runs": runs,
        "mean_fitness": float(np.mean(fitnesses)),
        "std_fitness": float(np.std(fitnesses)),
        "min_fitness": float(np.min(fitnesses)),
        "max_fitness": float(np.max(fitnesses)),
        "ari_matrix": ari_matrix,
        "ari_mean": ari_mean,
    }

    # Logging ------------------------------------------------------------------
    if log_dir is not None:
        p = Path(log_dir)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "config.json", "w", encoding="utf-8") as f:
            json.dump(
                {"n_repeats": n_repeats, "ga": asdict(ga_config)},
                f,
                indent=2,
            )
        for idx, run in enumerate(runs):
            with open(p / f"run_{idx + 1:03d}.json", "w", encoding="utf-8") as f:
                json.dump(run, f, indent=2)
        summary = {k: v for k, v in result.items() if k != "runs"}
        with open(p / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        _save_robustness_chart(runs, result, p / "robustness.png")

    return result


# ---------------------------------------------------------------------------
# 3. Weight sweep (one-at-a-time sensitivity)
# ---------------------------------------------------------------------------

def run_weight_sweep(
    dsm_freq,
    dsm_consol,
    ga_config: GAConfig,
    n_steps: int = 10,
    range_multiplier: float = 3.0,
    callback: Callable[[str, int, int, float, float, int], None] | None = None,
    cancel_event: threading.Event | None = None,
    log_dir: str | None = None,
) -> dict:
    """Sweep each fitness weight independently and record fitness & cluster count.

    For each fitness weight the value is swept from
    ``current / range_multiplier`` to ``current * range_multiplier``
    (clamped to ``[0.001, 1.0]``), generating *n_steps* evenly spaced values.
    The set of weights swept depends on the active fitness mode.

    Parameters
    ----------
    callback : called after each GA run with
               ``(weight_name, step_num, total_steps, value, fitness, n_clusters)``
    log_dir  : if set, write per-weight and summary JSON files

    Returns
    -------
    dict with key ``sweeps`` mapping each weight name to a list of
    ``{"value": v, "fitness": f, "n_clusters": c}`` dicts.
    """
    weight_names = MODE_WEIGHTS.get(ga_config.fitness_mode, MODE_WEIGHTS["classic"])
    sweeps: dict[str, list[dict]] = {}
    total_steps = n_steps * len(weight_names)
    step_counter = 0

    for wname in weight_names:
        current_value = getattr(ga_config, wname)
        lo = max(current_value / range_multiplier, 0.001)
        hi = min(current_value * range_multiplier, 1.0)
        values = np.linspace(lo, hi, n_steps).tolist()

        entries: list[dict] = []
        for si, val in enumerate(values):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Weight sweep cancelled by user")

            trial_cfg = dc_replace(ga_config, **{wname: val})
            best, _, fitness = run_ga(
                dsm_freq, dsm_consol, trial_cfg, verbose=False,
                cancel_event=cancel_event,
            )
            n_clusters = len(set(best))

            entries.append({
                "value": val,
                "fitness": fitness,
                "n_clusters": n_clusters,
            })

            step_counter += 1
            if callback is not None:
                callback(wname, step_counter, total_steps, val, fitness, n_clusters)

        sweeps[wname] = entries

    result = {"sweeps": sweeps}

    # Logging ------------------------------------------------------------------
    if log_dir is not None:
        p = Path(log_dir)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "config.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "n_steps": n_steps,
                    "range_multiplier": range_multiplier,
                    "ga": asdict(ga_config),
                },
                f,
                indent=2,
            )
        for wname, entries in sweeps.items():
            with open(p / f"{wname}.json", "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        with open(p / "summary.json", "w", encoding="utf-8") as f:
            json.dump(
                {wname: {"n_entries": len(entries)} for wname, entries in sweeps.items()},
                f,
                indent=2,
            )
        _save_sweep_chart(sweeps, p / "sweep.png")

    return result
