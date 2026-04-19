"""Tune-then-optimize sequential route."""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace as dc_replace
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.models import RunStarted, TuneOptimizeRequest
from api.state import run_manager, sse_generator
from dsm_ga import CancelledError, load_data, run_ga
from services.config import AppConfig
from services.optuna_runner import run_optuna

router = APIRouter(prefix="/api", tags=["tune-optimize"])
_pool = ThreadPoolExecutor(max_workers=1)


def _get_config() -> AppConfig:
    from api.main import get_app_config
    return get_app_config()


def _apply_overrides(app_config: AppConfig, req: TuneOptimizeRequest) -> AppConfig:
    cfg = app_config
    if req.ga:
        ga_overrides = {k: v for k, v in req.ga.model_dump().items() if v is not None}
        cfg = dc_replace(cfg, ga=dc_replace(cfg.ga, **ga_overrides))
    if req.optuna:
        opt_overrides = {k: v for k, v in req.optuna.model_dump().items() if v is not None}
        cfg = dc_replace(cfg, optuna=dc_replace(cfg.optuna, **opt_overrides))
    if req.freq_csv:
        cfg = dc_replace(cfg, data=dc_replace(cfg.data, freq_csv=req.freq_csv))
    if req.consol_csv:
        cfg = dc_replace(cfg, data=dc_replace(cfg.data, consol_csv=req.consol_csv))
    return cfg


def _run_tune_optimize(run_id: str, app_config: AppConfig):
    state = run_manager.get(run_id)
    if state is None:
        return

    try:
        dsm_freq, dsm_consol, units, _ = load_data(
            app_config.data.freq_csv, app_config.data.consol_csv
        )

        # --- Phase 1: Tune ---
        state.queue.put({"type": "phase", "phase": "tune"})

        def on_trial(trial_num: int, value: float, best_so_far: float):
            state.queue.put({
                "type": "trial",
                "trial": trial_num,
                "value": value,
                "best": best_so_far,
            })

        best_params, study = run_optuna(
            dsm_freq, dsm_consol, app_config,
            trial_callback=on_trial,
            cancel_event=state.cancel_event,
        )

        # --- Phase 2: Optimize with best params ---
        state.queue.put({"type": "phase", "phase": "optimize"})

        # Merge best Optuna params into GA config
        ga_cfg = app_config.ga
        param_map = {
            "raw_w0": "alpha", "raw_w1": "beta", "raw_w2": "gamma", "raw_w3": "delta",
        }
        ga_overrides = {}
        for k, v in best_params.items():
            target_key = param_map.get(k, k)
            if hasattr(ga_cfg, target_key):
                ga_overrides[target_key] = v
        if ga_overrides:
            ga_cfg = dc_replace(ga_cfg, **ga_overrides)

        def on_progress(gen: int, avg: float, min_: float, max_: float):
            state.queue.put({
                "type": "progress",
                "gen": gen,
                "avg": avg,
                "min": min_,
                "max": max_,
            })

        best, logbook, fitness = run_ga(
            dsm_freq, dsm_consol, ga_cfg,
            progress_callback=on_progress,
            cancel_event=state.cancel_event,
        )

        # Export results
        output_dir = app_config.data.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        sorted_indices = sorted(range(len(units)), key=lambda i: best[i])
        sorted_units = [units[i] for i in sorted_indices]
        sorted_groups = [best[i] for i in sorted_indices]

        result_name = f"tune_optimized_{run_id}.xlsx"
        result_path = str(Path(output_dir) / result_name)

        dsm_reordered = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        dsm_reordered.index = dsm_reordered.columns = sorted_units
        consol_reordered = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        consol_reordered.index = consol_reordered.columns = sorted_units

        grouping_df = pd.DataFrame({
            "Unit Name": sorted_units,
            "Cluster": [f"Cluster {g}" for g in sorted_groups],
        })

        with pd.ExcelWriter(result_path, engine="openpyxl") as writer:
            dsm_reordered.to_excel(writer, sheet_name="dsm_optimized")
            consol_reordered.to_excel(writer, sheet_name="dsm_consolidation")
            grouping_df.to_excel(writer, sheet_name="grouping")

        from services.viz import plot_dsm_paper
        fig_name = f"tune_optimized_{run_id}.png"
        fig_path = str(Path(output_dir) / fig_name)
        plot_dsm_paper(
            dsm_reordered, consol_reordered,
            sorted_units, sorted_groups,
            title=f"Tune+Optimize DSM | Fitness: {fitness:.4f}",
            save_path=fig_path,
        )

        state.result = {
            "fitness": fitness,
            "best_params": best_params,
            "result_path": result_name,
            "figure_path": fig_name,
        }
        state.status = "done"
        state.queue.put({
            "type": "done",
            "fitness": fitness,
            "best_params": best_params,
            "result_path": result_name,
            "figure_path": fig_name,
        })

    except CancelledError:
        state.status = "cancelled"
        state.queue.put({"type": "cancelled"})
    except Exception as exc:
        if "Cancelled" in str(exc):
            state.status = "cancelled"
            state.queue.put({"type": "cancelled"})
        else:
            state.status = "error"
            state.error = traceback.format_exc()
            state.queue.put({"type": "error", "message": traceback.format_exc()})


@router.post("/tune-optimize", response_model=RunStarted)
def start_tune_optimize(req: TuneOptimizeRequest | None = None):
    try:
        run_id, _ = run_manager.create_run()
    except RuntimeError:
        raise HTTPException(409, "A run is already in progress")

    app_config = _get_config()
    if req:
        app_config = _apply_overrides(app_config, req)
    _pool.submit(_run_tune_optimize, run_id, app_config)
    return RunStarted(run_id=run_id)


@router.get("/tune-optimize/{run_id}/stream")
async def stream_tune_optimize(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return EventSourceResponse(sse_generator(state))


@router.post("/tune-optimize/{run_id}/cancel")
def cancel_tune_optimize(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    if state.status != "running":
        raise HTTPException(409, f"Run is {state.status}, not running")
    state.cancel_event.set()
    return {"status": "cancelling"}
