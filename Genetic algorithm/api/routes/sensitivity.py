"""Sensitivity analysis routes — importance, robustness, weight-sweep."""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.models import ImportanceRequest, RobustnessRequest, RunStarted, SweepRequest
from api.state import run_manager, sse_generator
from dsm_ga import CancelledError, load_data
from services.config import AppConfig
from services.sensitivity import run_importance, run_robustness, run_weight_sweep

router = APIRouter(tags=["sensitivity"])
_pool = ThreadPoolExecutor(max_workers=1)

# Reusable Optuna study for importance analysis
_last_study = None


def _get_config() -> AppConfig:
    from api.main import get_app_config
    return get_app_config()


# ---------------------------------------------------------------------------
# Importance
# ---------------------------------------------------------------------------

def _run_importance(run_id: str, app_config: AppConfig, req: ImportanceRequest):
    global _last_study
    state = run_manager.get(run_id)
    if state is None:
        return

    try:
        freq_path = req.freq_csv or app_config.data.freq_csv
        consol_path = req.consol_csv or app_config.data.consol_csv
        dsm_freq, dsm_consol, units, _ = load_data(freq_path, consol_path)

        # Apply GA overrides
        cfg = app_config.ga
        if req.ga:
            overrides = {k: v for k, v in req.ga.model_dump().items() if v is not None}
            cfg = dc_replace(cfg, **overrides)
        app_cfg = dc_replace(app_config, ga=cfg)

        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        log_dir = str(Path("sensitivity_runs") / f"{ts}_importance")

        def on_trial(trial_num: int, value: float, best_so_far: float):
            state.queue.put({
                "type": "trial",
                "trial": trial_num,
                "value": value,
                "best": best_so_far,
            })

        importances, source, study = run_importance(
            dsm_freq,
            dsm_consol,
            app_cfg,
            n_trials=req.n_trials,
            param_group=req.param_group,
            existing_study=_last_study,
            callback=on_trial,
            cancel_event=state.cancel_event,
            log_dir=log_dir,
        )
        _last_study = study

        state.result = {
            "importances": importances,
            "source": source,
            "log_path": log_dir,
        }
        state.status = "done"
        state.queue.put({
            "type": "done",
            "importances": importances,
            "source": source,
            "log_path": log_dir,
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


@router.post("/api/sensitivity/importance", response_model=RunStarted)
def start_importance(req: ImportanceRequest | None = None):
    try:
        run_id, _ = run_manager.create_run()
    except RuntimeError:
        raise HTTPException(409, "A run is already in progress")

    app_config = _get_config()
    _pool.submit(_run_importance, run_id, app_config, req or ImportanceRequest())
    return RunStarted(run_id=run_id)


@router.get("/api/sensitivity/importance/{run_id}/stream")
async def stream_importance(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return EventSourceResponse(sse_generator(state))


@router.post("/api/sensitivity/importance/{run_id}/cancel")
def cancel_importance(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    if state.status != "running":
        raise HTTPException(409, f"Run is {state.status}, not running")
    state.cancel_event.set()
    return {"status": "cancelling"}


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

def _run_robustness(run_id: str, app_config: AppConfig, req: RobustnessRequest):
    state = run_manager.get(run_id)
    if state is None:
        return

    try:
        freq_path = req.freq_csv or app_config.data.freq_csv
        consol_path = req.consol_csv or app_config.data.consol_csv
        dsm_freq, dsm_consol, units, _ = load_data(freq_path, consol_path)

        cfg = app_config.ga
        if req.ga:
            overrides = {k: v for k, v in req.ga.model_dump().items() if v is not None}
            cfg = dc_replace(cfg, **overrides)

        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        log_dir = str(Path("sensitivity_runs") / f"{ts}_robustness")

        def on_run(run_num: int, total: int, fitness: float):
            state.queue.put({
                "type": "run_progress",
                "run": run_num,
                "total": total,
                "fitness": fitness,
            })

        result = run_robustness(
            dsm_freq,
            dsm_consol,
            cfg,
            n_repeats=req.n_repeats,
            callback=on_run,
            cancel_event=state.cancel_event,
            log_dir=log_dir,
        )

        done_payload = {
            "type": "done",
            "mean_fitness": result["mean_fitness"],
            "std_fitness": result["std_fitness"],
            "min_fitness": result["min_fitness"],
            "max_fitness": result["max_fitness"],
            "ari_mean": result["ari_mean"],
            "runs": [
                {"run": i + 1, "fitness": r["fitness"]}
                for i, r in enumerate(result["runs"])
            ],
            "log_path": log_dir,
        }

        state.result = {k: v for k, v in done_payload.items() if k != "type"}
        state.status = "done"
        state.queue.put(done_payload)

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


@router.post("/api/sensitivity/robustness", response_model=RunStarted)
def start_robustness(req: RobustnessRequest | None = None):
    try:
        run_id, _ = run_manager.create_run()
    except RuntimeError:
        raise HTTPException(409, "A run is already in progress")

    app_config = _get_config()
    _pool.submit(_run_robustness, run_id, app_config, req or RobustnessRequest())
    return RunStarted(run_id=run_id)


@router.get("/api/sensitivity/robustness/{run_id}/stream")
async def stream_robustness(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return EventSourceResponse(sse_generator(state))


@router.post("/api/sensitivity/robustness/{run_id}/cancel")
def cancel_robustness(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    if state.status != "running":
        raise HTTPException(409, f"Run is {state.status}, not running")
    state.cancel_event.set()
    return {"status": "cancelling"}


# ---------------------------------------------------------------------------
# Weight Sweep
# ---------------------------------------------------------------------------

def _run_sweep(run_id: str, app_config: AppConfig, req: SweepRequest):
    state = run_manager.get(run_id)
    if state is None:
        return

    try:
        freq_path = req.freq_csv or app_config.data.freq_csv
        consol_path = req.consol_csv or app_config.data.consol_csv
        dsm_freq, dsm_consol, units, _ = load_data(freq_path, consol_path)

        cfg = app_config.ga
        if req.ga:
            overrides = {k: v for k, v in req.ga.model_dump().items() if v is not None}
            cfg = dc_replace(cfg, **overrides)

        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        log_dir = str(Path("sensitivity_runs") / f"{ts}_sweep")

        def on_step(
            weight_name: str,
            step_num: int,
            total_steps: int,
            value: float,
            fitness: float,
            n_clusters: int,
        ):
            state.queue.put({
                "type": "sweep_progress",
                "weight": weight_name,
                "step": step_num,
                "total_steps": total_steps,
                "value": value,
                "fitness": fitness,
                "n_clusters": n_clusters,
            })

        result = run_weight_sweep(
            dsm_freq,
            dsm_consol,
            cfg,
            n_steps=req.n_steps,
            range_multiplier=req.range_multiplier,
            callback=on_step,
            cancel_event=state.cancel_event,
            log_dir=log_dir,
        )

        state.result = {"sweeps": result["sweeps"], "log_path": log_dir}
        state.status = "done"
        state.queue.put({
            "type": "done",
            "sweeps": result["sweeps"],
            "log_path": log_dir,
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


@router.post("/api/sensitivity/sweep", response_model=RunStarted)
def start_sweep(req: SweepRequest | None = None):
    try:
        run_id, _ = run_manager.create_run()
    except RuntimeError:
        raise HTTPException(409, "A run is already in progress")

    app_config = _get_config()
    _pool.submit(_run_sweep, run_id, app_config, req or SweepRequest())
    return RunStarted(run_id=run_id)


@router.get("/api/sensitivity/sweep/{run_id}/stream")
async def stream_sweep(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return EventSourceResponse(sse_generator(state))


@router.post("/api/sensitivity/sweep/{run_id}/cancel")
def cancel_sweep(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    if state.status != "running":
        raise HTTPException(409, f"Run is {state.status}, not running")
    state.cancel_event.set()
    return {"status": "cancelling"}
