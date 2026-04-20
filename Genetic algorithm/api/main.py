"""FastAPI application — mounts routes and static files."""

from __future__ import annotations

import asyncio
import hashlib
import re
from contextlib import asynccontextmanager
from dataclasses import replace as dc_replace
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.models import (
    ConfigSaveRequest,
    InitConfigRequest,
    UploadResponse,
)
from api.routes import optimize, sensitivity, tune, tune_optimize, visualize
from api.state import run_manager
from services.config import AppConfig, config_to_dict, init_config, load_config

# ---------------------------------------------------------------------------
# App-level config (loaded once at startup, can be refreshed)
# ---------------------------------------------------------------------------

_app_config: AppConfig | None = None
_config_path: str = "config.yaml"


def get_app_config() -> AppConfig:
    global _app_config
    if _app_config is None:
        _app_config = load_config(_config_path)
    return _app_config


# ---------------------------------------------------------------------------
# Lifespan — background cleanup task
# ---------------------------------------------------------------------------

async def _cleanup_loop():
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        run_manager.cleanup_stale(max_age_minutes=30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="DSM GA", version="0.1.0", lifespan=lifespan)

# Mount route modules
app.include_router(optimize.router)
app.include_router(tune.router)
app.include_router(tune_optimize.router)
app.include_router(visualize.router)
app.include_router(sensitivity.router)


# ---------------------------------------------------------------------------
# Config routes
# ---------------------------------------------------------------------------

@app.get("/api/config")
def read_config():
    return config_to_dict(get_app_config())


@app.get("/api/matrix-preview")
def matrix_preview(
    freq_csv: str | None = None,
    consol_csv: str | None = None,
    grouping_units: str | None = None,
    grouping_clusters: str | None = None,
):
    """Return raw matrix data for frontend heatmap/table rendering.

    If grouping_units and grouping_clusters are provided (JSON arrays),
    reorder the matrices by cluster assignment.
    """
    import json
    from dsm_ga import load_data

    cfg = get_app_config()
    freq_path = freq_csv or cfg.data.freq_csv
    consol_path = consol_csv or cfg.data.consol_csv

    try:
        dsm_freq, dsm_consol, units, _ = load_data(freq_path, consol_path)
    except Exception as e:
        raise HTTPException(400, f"Failed to load matrices: {e}")

    groups = None
    if grouping_units and grouping_clusters:
        try:
            g_units = json.loads(grouping_units)
            g_clusters = json.loads(grouping_clusters)
            unit_to_cluster = dict(zip(g_units, g_clusters))

            # Assign clusters to current units (default to 999 for unmatched)
            unit_groups = [unit_to_cluster.get(u, 999) for u in units]

            # Sort by cluster
            sorted_indices = sorted(range(len(units)), key=lambda i: unit_groups[i])
            units = [units[i] for i in sorted_indices]
            groups = [unit_groups[i] for i in sorted_indices]

            dsm_freq = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
            dsm_freq.index = dsm_freq.columns = units
            dsm_consol = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()
            dsm_consol.index = dsm_consol.columns = units
        except Exception as e:
            raise HTTPException(400, f"Failed to apply grouping: {e}")

    result = {
        "units": units,
        "freq": dsm_freq.values.tolist(),
        "consol": dsm_consol.values.tolist(),
        "shape": [len(units), len(units)],
    }
    if groups is not None:
        result["groups"] = groups
    return result


@app.get("/api/parse-grouping-path")
def parse_grouping_path(path: str):
    """Parse a grouping Excel file from a local path."""
    import pandas as pd

    try:
        grouping_df = pd.read_excel(path, sheet_name="grouping")
    except Exception as e:
        raise HTTPException(400, f"Failed to read grouping file: {e}")

    units = grouping_df["Unit Name"].tolist()
    clusters = [int(str(c).replace("Cluster ", "")) for c in grouping_df["Cluster"]]
    return {"units": units, "clusters": clusters}


@app.post("/api/parse-grouping")
async def parse_grouping(file: UploadFile):
    """Parse a grouping Excel file and return unit-to-cluster mapping."""
    import io
    import pandas as pd

    content = await file.read()
    try:
        grouping_df = pd.read_excel(io.BytesIO(content), sheet_name="grouping")
    except Exception as e:
        raise HTTPException(400, f"Failed to read grouping sheet: {e}")

    units = grouping_df["Unit Name"].tolist()
    clusters = [int(str(c).replace("Cluster ", "")) for c in grouping_df["Cluster"]]
    return {"units": units, "clusters": clusters}


@app.post("/api/config/save")
def save_config(req: ConfigSaveRequest | None = None):
    cfg = get_app_config()
    if req and req.ga:
        ga_overrides = {k: v for k, v in req.ga.model_dump().items() if v is not None}
        cfg = dc_replace(cfg, ga=dc_replace(cfg.ga, **ga_overrides))
    if req and req.optuna:
        opt_overrides = {k: v for k, v in req.optuna.model_dump().items() if v is not None}
        cfg = dc_replace(cfg, optuna=dc_replace(cfg.optuna, **opt_overrides))

    with open(_config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_to_dict(cfg), f, default_flow_style=False, sort_keys=False)

    global _app_config
    _app_config = cfg
    return {"status": "saved"}


@app.post("/api/config/init")
def scaffold_config(req: InitConfigRequest | None = None):
    path = (req.output_path if req else "config.yaml")
    p = init_config(path)
    return {"path": str(p)}


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

_SAFE_FILENAME = re.compile(r"[^a-zA-Z0-9_\-.]")


@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(files: list[UploadFile]):
    cfg = get_app_config()
    upload_dir = Path(cfg.data.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for f in files:
        if not f.filename:
            continue
        safe_name = _SAFE_FILENAME.sub("_", f.filename)
        dest = upload_dir / safe_name
        if dest.exists():
            h = hashlib.md5(safe_name.encode()).hexdigest()[:6]
            stem = dest.stem
            dest = upload_dir / f"{stem}_{h}{dest.suffix}"
        content = await f.read()
        dest.write_bytes(content)
        saved.append(str(dest))

    return UploadResponse(paths=saved)


# ---------------------------------------------------------------------------
# Results file serving (path-traversal protected)
# ---------------------------------------------------------------------------

@app.get("/api/results/{filename:path}")
def serve_result(filename: str):
    cfg = get_app_config()
    output_dir = Path(cfg.data.output_dir).resolve()
    target = (output_dir / filename).resolve()

    if not str(target).startswith(str(output_dir)):
        raise HTTPException(403, "Access denied")
    if not target.is_file():
        raise HTTPException(404, "File not found")

    return FileResponse(str(target))


# ---------------------------------------------------------------------------
# Static files (frontend) — must be last so it doesn't shadow API routes
# ---------------------------------------------------------------------------

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
