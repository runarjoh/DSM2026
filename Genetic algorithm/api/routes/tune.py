"""Optuna tuning routes — start, stream, cancel."""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace as dc_replace

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.models import RunStarted, TuneRequest
from api.state import run_manager, sse_generator
from services.config import AppConfig
from services.optuna_runner import resolve_best_params, run_optuna

log = logging.getLogger("dsm_ga.tune")
router = APIRouter(prefix="/api", tags=["tune"])
_pool = ThreadPoolExecutor(max_workers=1)


def _get_config() -> AppConfig:
    from api.main import get_app_config
    return get_app_config()


def _apply_overrides(app_config: AppConfig, req: TuneRequest) -> AppConfig:
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


def _run_tune(run_id: str, app_config: AppConfig):
    state = run_manager.get(run_id)
    if state is None:
        return

    try:
        from dsm_ga import load_data
        dsm_freq, dsm_consol, _, _ = load_data(
            app_config.data.freq_csv, app_config.data.consol_csv
        )

        # Patch dsm data into a closure the runner can use
        import services.optuna_runner as runner
        original_run_ga = runner.run_ga

        def patched_run_ga(freq, consol, cfg, **kwargs):
            return original_run_ga(dsm_freq, dsm_consol, cfg, **kwargs)

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

        resolved = resolve_best_params(best_params)
        state.result = {"best_params": resolved, "best_value": study.best_value}
        state.status = "done"
        state.queue.put({
            "type": "done",
            "best_params": resolved,
            "fitness": study.best_value,
            "result_path": None,
        })

    except Exception as exc:
        if "Cancelled" in str(exc):
            log.info("Tune %s cancelled", run_id)
            state.status = "cancelled"
            state.queue.put({"type": "cancelled"})
        else:
            log.error("Tune %s failed:\n%s", run_id, traceback.format_exc())
            state.status = "error"
            state.error = traceback.format_exc()
            state.queue.put({"type": "error", "message": traceback.format_exc()})


@router.post("/tune", response_model=RunStarted)
def start_tune(req: TuneRequest | None = None):
    try:
        run_id, _ = run_manager.create_run()
    except RuntimeError:
        raise HTTPException(409, "A run is already in progress")

    app_config = _get_config()
    if req:
        app_config = _apply_overrides(app_config, req)
    _pool.submit(_run_tune, run_id, app_config)
    return RunStarted(run_id=run_id)


@router.get("/tune/{run_id}/stream")
async def stream_tune(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return EventSourceResponse(sse_generator(state))


@router.post("/tune/{run_id}/cancel")
def cancel_tune(run_id: str):
    state = run_manager.get(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    if state.status != "running":
        raise HTTPException(409, f"Run is {state.status}, not running")
    state.cancel_event.set()
    return {"status": "cancelling"}
