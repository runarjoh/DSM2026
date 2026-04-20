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

from dsm_ga import CancelledError, GAConfig, run_ga
from services.config import AppConfig
from services.optuna_runner import build_trial_config, run_optuna


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _save_importance_chart(importances: dict[str, float], path: Path) -> None:
    """Save a horizontal bar chart of parameter importances."""
    sorted_items = sorted(importances.items(), key=lambda x: x[1])
    names = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.5)))
    ax.barh(names, values, color="#3b82f6")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Importance (fANOVA)")
    ax.set_title("Parameter Importance")
    for i, v in enumerate(values):
        ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=8)
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
    """Save a 2x2 grid of weight sweep line charts."""
    weight_names = [w for w in ("alpha", "beta", "gamma", "delta") if w in sweeps]
    n = len(weight_names)
    cols = min(n, 2)
    rows = (n + 1) // 2

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
) -> tuple[dict[str, float], str, optuna.Study]:
    """Compute fANOVA parameter importances.

    If *existing_study* already has >= *n_trials* completed trials the
    importances are derived directly from it (``source="reused"``).
    Otherwise a fresh Optuna study is executed.

    Parameters
    ----------
    callback : called after each trial with ``(trial_num, value, best_so_far)``
    log_dir  : if set, write ``config.json`` and ``summary.json`` there

    Returns
    -------
    (importances, source, study)
        *importances* maps parameter names to fANOVA scores,
        *source* is ``"reused"`` or ``"new_study"``.
    """
    # Decide whether to reuse --------------------------------------------------
    reuse = (
        existing_study is not None
        and len([t for t in existing_study.trials
                 if t.state == optuna.trial.TrialState.COMPLETE]) >= n_trials
    )

    if reuse:
        study = existing_study
        source = "reused"
    else:
        # Build a temporary AppConfig with the requested trial count / group
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

    importances: dict[str, float] = optuna.importance.get_param_importances(study)

    # Logging ------------------------------------------------------------------
    if log_dir is not None:
        p = Path(log_dir)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "config.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "n_trials": n_trials,
                    "param_group": param_group,
                    "source": source,
                    "ga": asdict(app_config.ga),
                },
                f,
                indent=2,
            )
        with open(p / "summary.json", "w", encoding="utf-8") as f:
            json.dump({"importances": importances, "source": source}, f, indent=2)
        _save_importance_chart(importances, p / "importance.png")

    return importances, source, study


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

    for i in range(n_repeats):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Robustness analysis cancelled by user")

        best, logbook, fitness = run_ga(
            dsm_freq, dsm_consol, ga_config, verbose=False, cancel_event=cancel_event,
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

    For each weight (*alpha*, *beta*, *gamma*, *delta*) the value is swept
    from ``current / range_multiplier`` to ``current * range_multiplier``
    (clamped to ``[0.001, 1.0]``), generating *n_steps* evenly spaced values.

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
    weight_names = ("alpha", "beta", "gamma", "delta")
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
