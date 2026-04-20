"""CLI entry-point — thin wrappers around the service layer."""

from __future__ import annotations

from pathlib import Path

import click


@click.group()
def cli():
    """DSM Genetic Algorithm — optimization and tuning toolkit."""


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8080, type=int, help="Port number")
def serve(host: str, port: int):
    """Start the web server."""
    import uvicorn

    from api.main import _config_path, get_app_config  # noqa: F401 — ensure config loads

    click.echo(f"Starting DSM GA server on http://{host}:{port}")
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


@cli.command(name="run")
@click.argument("config_path", type=click.Path(exists=True))
def run_cmd(config_path: str):
    """Run GA optimisation, printing progress to stdout."""
    from dsm_ga import load_data, run_ga
    from services.config import load_config

    cfg = load_config(config_path)
    dsm_freq, dsm_consol, units, _ = load_data(cfg.data.freq_csv, cfg.data.consol_csv)

    click.echo(f"Running GA: {cfg.ga.n_generations} generations, pop {cfg.ga.population_size}")
    best, logbook, fitness = run_ga(dsm_freq, dsm_consol, cfg.ga, verbose=True)

    click.echo(f"\nFinal fitness: {fitness:.4f}")
    click.echo(f"Cluster assignments: {best}")

    # Export
    output_dir = Path(cfg.data.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "optimized.xlsx"

    import pandas as pd

    sorted_indices = sorted(range(len(units)), key=lambda i: best[i])
    sorted_units = [units[i] for i in sorted_indices]
    sorted_groups = [best[i] for i in sorted_indices]

    dsm_reordered = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
    dsm_reordered.index = dsm_reordered.columns = sorted_units
    consol_reordered = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()
    consol_reordered.index = consol_reordered.columns = sorted_units

    grouping_df = pd.DataFrame({
        "Unit Name": sorted_units,
        "Cluster": [f"Cluster {g}" for g in sorted_groups],
    })

    with pd.ExcelWriter(str(result_path), engine="openpyxl") as writer:
        dsm_reordered.to_excel(writer, sheet_name="dsm_optimized")
        consol_reordered.to_excel(writer, sheet_name="dsm_consolidation")
        grouping_df.to_excel(writer, sheet_name="grouping")

    click.echo(f"Exported to {result_path}")


@cli.command()
@click.argument("config_path", type=click.Path(exists=True))
def tune(config_path: str):
    """Run Optuna hyperparameter tuning, print best params."""
    from dsm_ga import load_data
    from services.config import load_config
    from services.optuna_runner import run_optuna

    cfg = load_config(config_path)
    dsm_freq, dsm_consol, _, _ = load_data(cfg.data.freq_csv, cfg.data.consol_csv)

    click.echo(f"Running Optuna: {cfg.optuna.n_trials} trials, group={cfg.optuna.param_group}")

    def on_trial(num: int, value: float, best: float):
        click.echo(f"  Trial {num:3d} | fitness {value:.4f} | best {best:.4f}")

    best_params, study = run_optuna(dsm_freq, dsm_consol, cfg, trial_callback=on_trial)

    click.echo(f"\nBest fitness: {study.best_value:.4f}")
    click.echo("Best parameters:")
    for k, v in best_params.items():
        click.echo(f"  {k}: {v}")


@cli.command(name="tune-optimize")
@click.argument("config_path", type=click.Path(exists=True))
def tune_optimize(config_path: str):
    """Run Optuna tuning, then full GA with best params."""
    from dataclasses import replace as dc_replace

    from dsm_ga import load_data, run_ga
    from services.config import load_config
    from services.optuna_runner import run_optuna

    cfg = load_config(config_path)
    dsm_freq, dsm_consol, units, _ = load_data(cfg.data.freq_csv, cfg.data.consol_csv)

    click.echo("Phase 1: Tuning")
    click.echo(f"  {cfg.optuna.n_trials} trials, group={cfg.optuna.param_group}")

    def on_trial(num: int, value: float, best: float):
        click.echo(f"  Trial {num:3d} | fitness {value:.4f} | best {best:.4f}")

    best_params, study = run_optuna(dsm_freq, dsm_consol, cfg, trial_callback=on_trial)
    click.echo(f"  Best fitness: {study.best_value:.4f}")

    click.echo("\nPhase 2: Full GA with best params")
    ga_cfg = cfg.ga
    param_map = {"raw_w0": "alpha", "raw_w1": "beta", "raw_w2": "gamma", "raw_w3": "delta"}
    ga_overrides = {}
    for k, v in best_params.items():
        target_key = param_map.get(k, k)
        if hasattr(ga_cfg, target_key):
            ga_overrides[target_key] = v
    if ga_overrides:
        ga_cfg = dc_replace(ga_cfg, **ga_overrides)

    best, logbook, fitness = run_ga(dsm_freq, dsm_consol, ga_cfg, verbose=True)
    click.echo(f"\nFinal fitness: {fitness:.4f}")

    # Export
    import pandas as pd

    output_dir = Path(cfg.data.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "tune_optimized.xlsx"

    sorted_indices = sorted(range(len(units)), key=lambda i: best[i])
    sorted_units = [units[i] for i in sorted_indices]
    sorted_groups = [best[i] for i in sorted_indices]

    dsm_reordered = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
    dsm_reordered.index = dsm_reordered.columns = sorted_units
    consol_reordered = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()
    consol_reordered.index = consol_reordered.columns = sorted_units

    grouping_df = pd.DataFrame({
        "Unit Name": sorted_units,
        "Cluster": [f"Cluster {g}" for g in sorted_groups],
    })

    with pd.ExcelWriter(str(result_path), engine="openpyxl") as writer:
        dsm_reordered.to_excel(writer, sheet_name="dsm_optimized")
        consol_reordered.to_excel(writer, sheet_name="dsm_consolidation")
        grouping_df.to_excel(writer, sheet_name="grouping")

    click.echo(f"Exported to {result_path}")


@cli.command(name="visualize")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--result-xlsx", default=None, help="Path to result Excel for cluster groupings")
@click.option("--title", default=None, help="Figure title")
@click.option("--output", default=None, help="Output PNG path (default: results/dsm_figure.png)")
def visualize_cmd(config_path: str, result_xlsx: str | None, title: str | None, output: str | None):
    """Generate a publication-quality DSM figure."""
    import pandas as pd

    from dsm_ga import load_data
    from services.config import load_config
    from services.viz import plot_dsm_paper

    cfg = load_config(config_path)
    dsm_freq, dsm_consol, units, _ = load_data(cfg.data.freq_csv, cfg.data.consol_csv)

    groups = list(range(len(units)))
    if result_xlsx:
        grouping_df = pd.read_excel(result_xlsx, sheet_name="grouping")
        unit_to_cluster = {}
        for _, row in grouping_df.iterrows():
            cluster_num = int(str(row["Cluster"]).replace("Cluster ", ""))
            unit_to_cluster[row["Unit Name"]] = cluster_num
        groups = [unit_to_cluster.get(u, 0) for u in units]

        sorted_indices = sorted(range(len(units)), key=lambda i: groups[i])
        units = [units[i] for i in sorted_indices]
        groups = [groups[i] for i in sorted_indices]
        dsm_freq = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        dsm_freq.index = dsm_freq.columns = units
        dsm_consol = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        dsm_consol.index = dsm_consol.columns = units

    output_dir = Path(cfg.data.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_path = output or str(output_dir / "dsm_figure.png")

    plot_dsm_paper(dsm_freq, dsm_consol, units, groups, title=title, save_path=save_path)
    click.echo(f"Saved figure to {save_path}")


@cli.command(name="init-config")
@click.argument("output_path", default="config.yaml")
def init_config_cmd(output_path: str):
    """Scaffold an annotated starter config.yaml."""
    from services.config import init_config

    p = init_config(output_path)
    click.echo(f"Created {p}")


if __name__ == "__main__":
    cli()
