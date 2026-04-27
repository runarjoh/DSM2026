"""GA optimize routes — start, stream, cancel."""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace as dc_replace

import pandas as pd
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.models import OptimizeRequest, RunStarted
from api.state import run_manager, sse_generator
from dsm_ga import CancelledError, run_ga
from services.config import AppConfig

log = logging.getLogger("dsm_ga.optimize")
router = APIRouter(prefix="/api", tags=["optimize"])
_pool = ThreadPoolExecutor(max_workers=1)


def _get_config() -> AppConfig:
    from api.main import get_app_config
    return get_app_config()


def _run_optimize(run_id: str, app_config: AppConfig, overrides: OptimizeRequest):
    state = run_manager.get(run_id)
    if state is None:
        return

    try:
        cfg = app_config.ga
        if overrides.ga:
            override_dict = {k: v for k, v in overrides.ga.model_dump().items() if v is not None}
            cfg = dc_replace(cfg, **override_dict)

        freq_csv = overrides.freq_csv or app_config.data.freq_csv
        consol_csv = overrides.consol_csv or app_config.data.consol_csv
        dsm_freq, dsm_consol, units, _ = pd.DataFrame(), pd.DataFrame(), [], []
        from dsm_ga import load_data
        dsm_freq, dsm_consol, units, _ = load_data(freq_csv, consol_csv)

        def on_progress(gen: int, avg: float, min_: float, max_: float):
            state.queue.put({
                "type": "progress",
                "gen": gen,
                "avg": avg,
                "min": min_,
                "max": max_,
            })

        best, logbook, fitness = run_ga(
            dsm_freq, dsm_consol, cfg,
            progress_callback=on_progress,
            cancel_event=state.cancel_event,
        )

        # Export results
        output_dir = app_config.data.output_dir
        from pathlib import Path
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        sorted_indices = sorted(range(len(units)), key=lambda i: best[i])
        sorted_units = [units[i] for i in sorted_indices]
        sorted_groups = [best[i] for i in sorted_indices]

        result_name = f"optimized_{run_id}.xlsx"
        result_path = str(Path(output_dir) / result_name)

        dsm_reordered = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        dsm_reordered.index = dsm_reordered.columns = sorted_units
        consol_reordered = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        consol_reordered.index = consol_reordered.columns = sorted_units

        grouping_df = pd.DataFrame({
            "Unit Name": sorted_units,
            "Cluster": [f"Cluster {g}" for g in sorted_groups],
        })

        from dataclasses import asdict
        config_dict = asdict(cfg)
        metadata_df = pd.DataFrame({
            "parameter": ["fitness"] + list(config_dict.keys()),
            "value": [fitness] + list(config_dict.values()),
        })

        with pd.ExcelWriter(result_path, engine="openpyxl") as writer:
            dsm_reordered.to_excel(writer, sheet_name="dsm_optimized")
            consol_reordered.to_excel(writer, sheet_name="dsm_consolidation")
            grouping_df.to_excel(writer, sheet_name="grouping")
            metadata_df.to_excel(writer, sheet_name="metadata", index=False)

        # Generate figures
        from services.viz import plot_cluster_stats, plot_config_summary, plot_dsm_paper
        from services.stats import compute_cluster_stats

        fig_name = f"optimized_{run_id}.png"
        fig_path = str(Path(output_dir) / fig_name)
        plot_dsm_paper(
            dsm_reordered, consol_reordered,
            sorted_units, sorted_groups,
            title=f"Optimized DSM | Fitness: {fitness:.4f}",
            save_path=fig_path,
        )

        config_fig_name = f"optimized_{run_id}_config.png"
        plot_config_summary(
            config_dict,
            title=f"GA Configuration — {result_name}",
            save_path=str(Path(output_dir) / config_fig_name),
        )

        stats = compute_cluster_stats(
            sorted_groups,
            dsm_reordered.values, consol_reordered.values,
            cfg,
        )
        stats_fig_name = f"optimized_{run_id}_stats.png"
        plot_cluster_stats(
            stats["fitness"], stats["n_clusters"], stats["mdl"],
            stats["components"], stats["rates"],
            title=f"Cluster Statistics — Fitness: {stats['fitness']:.4f}",
            save_path=str(Path(output_dir) / stats_fig_name),
        )

        state.result = {
            "fitness": fitness,
            "result_path": result_name,
            "figure_path": fig_name,
            "config_figure_path": config_fig_name,
            "stats_figure_path": stats_fig_name,
            "best": best,
        }
        state.status = "done"
        state.queue.put({
            "type": "done",
            "fitness": fitness,
            "result_path": result_name,
            "figure_path": fig_name,
            "config_figure_path": config_fig_name,
            "stats_figure_path": stats_fig_name,
            "result_freq": dsm_reordered.values.tolist(),
            "result_consol": consol_reordered.values.tolist(),
            "result_units": sorted_units,
            "result_groups": sorted_groups,
        })

    except CancelledError:
        log.info("Run %s cancelled", run_id)
        state.status = "cancelled"
        state.queue.put({"type": "cancelled"})
    except Exception:
        log.error("Run %s failed:\n%s", run_id, traceback.format_exc())
        state.status = "error"
        state.error = traceback.format_exc()
        state.queue.put({"type": "error", "message": traceback.format_exc()})


@router.post("/optimize", response_model=RunStarted)
def start_optimize(req: OptimizeRequest | None = None):
    try:
        run_id, _ = run_manager.create_run()
    except RuntimeError:
        raise HTTPException(409, "A run is already in progress")

    app_config = _get_config()
    _pool.submit(_run_optimize, run_id, app_config, req or OptimizeRequest())
    return RunStarted(run_id=run_id)


@router.get("/optimize/{run_id}/stream")
async def stream_optimize(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return EventSourceResponse(sse_generator(state))


@router.post("/optimize/{run_id}/cancel")
def cancel_optimize(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    if state.status != "running":
        raise HTTPException(409, f"Run is {state.status}, not running")
    state.cancel_event.set()
    return {"status": "cancelling"}
