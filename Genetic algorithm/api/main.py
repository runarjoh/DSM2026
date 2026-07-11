"""FastAPI application — mounts routes and static files."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import replace as dc_replace
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.logging_config import setup_logging
from api.models import (
    ConfigSaveRequest,
    InitConfigRequest,
    UploadResponse,
)
from api.routes import optimize, sensitivity, tune, tune_optimize, visualize
from api.state import run_manager
from services.config import AppConfig, config_to_dict, init_config, load_config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = setup_logging()

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


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        log.error("%s %s -> 500 (%.0fms)\n%s", method, path, elapsed, traceback.format_exc())
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    elapsed = (time.perf_counter() - start) * 1000
    status = response.status_code
    if status >= 500:
        log.error("%s %s -> %d (%.0fms)", method, path, status, elapsed)
    elif status >= 400:
        log.warning("%s %s -> %d (%.0fms)", method, path, status, elapsed)
    else:
        log.info("%s %s -> %d (%.0fms)", method, path, status, elapsed)
    return response


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


@app.post("/api/compute-fitness")
def compute_fitness(req: dict):
    """Compute fitness for a given grouping without running GA."""
    import json
    from dataclasses import replace as _dc_replace
    from dsm_ga import GAConfig, _make_eval_fn, load_data

    cfg = get_app_config()
    freq_path = req.get("freq_csv") or cfg.data.freq_csv
    consol_path = req.get("consol_csv") or cfg.data.consol_csv

    try:
        dsm_freq, dsm_consol, units, _ = load_data(freq_path, consol_path)
    except Exception as e:
        raise HTTPException(400, f"Failed to load matrices: {e}")

    clusters = req.get("clusters")
    if not clusters:
        raise HTTPException(400, "clusters array is required")

    # Reorder matrices by grouping if grouping_units provided
    grouping_units = req.get("grouping_units")
    if grouping_units:
        unit_to_cluster = dict(zip(grouping_units, clusters))
        unit_groups = [unit_to_cluster.get(u, 999) for u in units]
        sorted_indices = sorted(range(len(units)), key=lambda i: unit_groups[i])
        units = [units[i] for i in sorted_indices]
        clusters = [unit_groups[i] for i in sorted_indices]
        dsm_freq = dsm_freq.iloc[sorted_indices].iloc[:, sorted_indices].copy()
        dsm_consol = dsm_consol.iloc[sorted_indices].iloc[:, sorted_indices].copy()

    # Build GAConfig from request overrides
    ga_overrides = req.get("ga", {})
    ga_config = cfg.ga
    for k, v in ga_overrides.items():
        if hasattr(ga_config, k):
            current = getattr(ga_config, k)
            # Coerce to the current field's type. When the current value is None
            # (e.g. an unset `seed`), its type can't be used as a constructor, so
            # pass the value through as-is (or None to clear it).
            coerced = v if (v is None or current is None) else type(current)(v)
            ga_config = _dc_replace(ga_config, **{k: coerced})

    import math

    # Normalize cluster IDs to contiguous 0-based values so they fit
    # within max_clusters (result files store raw GA cluster IDs which
    # may exceed the current max_clusters setting).
    unique_labels = sorted(set(clusters))
    label_map = {lab: i for i, lab in enumerate(unique_labels)}
    clusters = [label_map[c] for c in clusters]

    # Ensure max_clusters is large enough for the actual cluster count
    n_actual = len(unique_labels)
    if ga_config.max_clusters < n_actual:
        ga_config = _dc_replace(ga_config, max_clusters=n_actual)

    eval_fn = _make_eval_fn(dsm_freq.values, dsm_consol.values, ga_config)
    fitness = eval_fn(clusters)[0]

    # Compute MDL, cluster count, and fitness decomposition
    n = len(clusters)
    cluster_sizes: dict[int, int] = {}
    for c in clusters:
        cluster_sizes[c] = cluster_sizes.get(c, 0) + 1
    n_clusters = len(cluster_sizes)
    mdl_raw = n_clusters * math.log2(n) + math.log2(n) * sum(cluster_sizes.values())

    # Apply same preprocessing as fitness function to freq matrix
    raw_freq = dsm_freq.values.tolist()
    threshold = ga_config.freq_threshold
    if threshold > 0:
        raw_freq = [
            [0.0 if 0 < raw_freq[r][c] < threshold else raw_freq[r][c]
             for c in range(n)]
            for r in range(n)
        ]
    if ga_config.matrix_preprocess == "binary":
        prep_freq = [[1.0 if raw_freq[r][c] > 0 else 0.0 for c in range(n)] for r in range(n)]
    else:
        max_freq = max(
            (raw_freq[r][c] for r in range(n) for c in range(n) if r != c),
            default=1.0,
        ) or 1.0
        prep_freq = [[raw_freq[r][c] / max_freq for c in range(n)] for r in range(n)]

    consol_vals = dsm_consol.values
    consol_m = consol_vals.tolist()

    # Compute raw error terms (S1-S4)
    S1 = S2 = S3 = S4 = 0.0
    for col in range(n):
        for row in range(n):
            if col == row:
                continue
            same = clusters[col] == clusters[row]
            val = prep_freq[col][row]
            if val > 0 and not same:
                S1 += val
            if val == 0 and same:
                S2 += 1.0
            if not same:
                if ga_config.consolidation_mode == "once":
                    if col < row and (consol_m[col][row] == 1 or consol_m[row][col] == 1):
                        S3 += 1
                elif ga_config.consolidation_mode == "directional":
                    S3 += consol_m[col][row]
            if same:
                if ga_config.consolidation_mode == "once":
                    if col < row and consol_m[col][row] == 0 and consol_m[row][col] == 0:
                        S4 += 1
                elif ga_config.consolidation_mode == "directional":
                    if consol_m[col][row] == 0:
                        S4 += 1

    log_factor = 2 * math.log2(n + 1)
    mode = ga_config.fitness_mode

    # Compute weighted components
    if mode == "full":
        mdl_weight = 1.0 - ga_config.alpha - ga_config.beta - ga_config.gamma - ga_config.delta - ga_config.epsilon
    elif mode == "anti_singleton":
        mdl_weight = 1.0 - ga_config.alpha - ga_config.beta - ga_config.gamma - ga_config.delta - ga_config.epsilon - ga_config.zeta
    elif mode == "mdl_pure":
        mdl_weight = 1.0 - ga_config.alpha - ga_config.beta - ga_config.gamma - ga_config.delta
    else:
        mdl_weight = 1.0 - ga_config.alpha - ga_config.beta - ga_config.gamma

    components = {
        "mdl": {"weight": mdl_weight, "value": mdl_weight * mdl_raw},
        "freq_between": {"weight": ga_config.alpha, "value": ga_config.alpha * S1 * log_factor},
        "freq_gap": {"weight": ga_config.beta, "value": ga_config.beta * S2 * log_factor},
        "consol_between": {"weight": ga_config.gamma, "value": ga_config.gamma * S3 * log_factor},
    }
    if mode != "classic":
        components["consol_gap"] = {"weight": ga_config.delta, "value": ga_config.delta * S4 * log_factor}
    if mode in ("full", "anti_singleton"):
        ideal_size = n / ga_config.target_clusters
        size_imb = sum((cluster_sizes.get(c, 0) - ideal_size) ** 2 for c in cluster_sizes if cluster_sizes[c] > 0) / ga_config.target_clusters
        components["size_imbalance"] = {"weight": ga_config.epsilon, "value": ga_config.epsilon * size_imb * log_factor}
    if mode == "anti_singleton":
        n_sing = sum(1 for sz in cluster_sizes.values() if sz == 1)
        sp = n_sing ** 2 / ga_config.target_clusters
        components["singleton_penalty"] = {"weight": ga_config.zeta, "value": ga_config.zeta * sp * log_factor}

    # Cell counts using binarized freq (>0 = has interaction)
    freq_vals = [[1.0 if raw_freq[r][c] > 0 else 0.0 for c in range(n)] for r in range(n)]
    freq_within = freq_outside = consol_within = consol_outside = 0
    both_within = both_outside = 0
    no_freq_within = no_freq_outside = no_consol_within = no_consol_outside = 0
    blank_within = blank_outside = 0
    for r in range(n):
        for c in range(n):
            if r == c:
                continue
            same = clusters[r] == clusters[c]
            has_freq = freq_vals[r][c] > 0.0
            has_consol = consol_vals[r][c] == 1
            if has_freq:
                if same:
                    freq_within += 1
                else:
                    freq_outside += 1
            else:
                if same:
                    no_freq_within += 1
                else:
                    no_freq_outside += 1
            if has_consol:
                if same:
                    consol_within += 1
                else:
                    consol_outside += 1
            else:
                if same:
                    no_consol_within += 1
                else:
                    no_consol_outside += 1
            if has_freq and has_consol:
                if same:
                    both_within += 1
                else:
                    both_outside += 1
            if not has_freq and not has_consol:
                if same:
                    blank_within += 1
                else:
                    blank_outside += 1

    return {
        "fitness": fitness,
        "freq_within": freq_within,
        "freq_outside": freq_outside,
        "consol_within": consol_within,
        "consol_outside": consol_outside,
        "both_within": both_within,
        "both_outside": both_outside,
        "no_freq_within": no_freq_within,
        "no_freq_outside": no_freq_outside,
        "no_consol_within": no_consol_within,
        "no_consol_outside": no_consol_outside,
        "blank_within": blank_within,
        "blank_outside": blank_outside,
        "freq_threshold": threshold,
        "mdl": mdl_raw,
        "n_clusters": n_clusters,
        "components": components,
    }


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


@app.get("/api/results-list")
def results_list():
    """List all result files with metadata."""
    import datetime
    import json as _json

    from openpyxl import load_workbook

    cfg = get_app_config()
    output_dir = Path(cfg.data.output_dir)
    if not output_dir.is_dir():
        return {"results": []}

    # Load saved names
    names_file = output_dir / "result_names.json"
    saved_names: dict[str, str] = {}
    if names_file.is_file():
        try:
            saved_names = _json.loads(names_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Lazy-load eval function for computing fitness on legacy files
    _eval_fn = None

    def _get_eval_fn():
        nonlocal _eval_fn
        if _eval_fn is None:
            from dsm_ga import _make_eval_fn, load_data
            dsm_freq, dsm_consol, _units, _ = load_data(cfg.data.freq_csv, cfg.data.consol_csv)
            _eval_fn = (_make_eval_fn(dsm_freq.values, dsm_consol.values, cfg.ga), _units)
        return _eval_fn

    xlsx_files = sorted(output_dir.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    items = []
    names_dirty = False
    for f in xlsx_files:
        # Determine type from filename prefix
        name = f.name
        if name.startswith("tune_optimized_"):
            result_type = "Tune + Optimize"
        elif name.startswith("optimized_"):
            result_type = "Optimize"
        else:
            result_type = "Unknown"

        # Read Excel via openpyxl (much faster than pandas for metadata)
        n_clusters = None
        n_units = None
        fitness = None
        unit_names = None
        cluster_labels = None
        try:
            wb = load_workbook(str(f), read_only=True, data_only=True)
            if "grouping" in wb.sheetnames:
                rows = list(wb["grouping"].iter_rows(min_row=2, values_only=True))
                unit_names = [r[1] for r in rows]
                cluster_labels = [r[2] for r in rows]
                n_units = len(rows)
                n_clusters = len(set(cluster_labels))
            if "metadata" in wb.sheetnames:
                meta_rows = list(wb["metadata"].iter_rows(min_row=2, values_only=True))
                if meta_rows:
                    # New format: (parameter, value) rows — find "fitness"
                    if len(meta_rows[0]) >= 2 and meta_rows[0][0] == "fitness":
                        fitness = round(float(meta_rows[0][1]), 1)
                    # Old format: single-column with fitness in first cell
                    elif meta_rows[0][0] is not None:
                        try:
                            fitness = round(float(meta_rows[0][0]), 1)
                        except (ValueError, TypeError):
                            pass
            wb.close()
        except Exception:
            pass

        # Compute fitness for legacy files and backfill metadata sheet
        if fitness is None and unit_names is not None and cluster_labels is not None:
            try:
                eval_fn, data_units = _get_eval_fn()
                unit_to_cluster = dict(zip(unit_names, cluster_labels))
                labels_sorted = sorted(set(cluster_labels))
                label_to_int = {lab: i for i, lab in enumerate(labels_sorted)}
                clusters = [label_to_int[unit_to_cluster[u]] for u in data_units]
                fitness = round(eval_fn(clusters)[0], 1)
                # Write metadata sheet back so we don't recompute next time
                try:
                    wb_write = load_workbook(str(f))
                    ws = wb_write.create_sheet("metadata")
                    ws.append(["fitness"])
                    ws.append([fitness])
                    wb_write.save(str(f))
                    wb_write.close()
                except Exception:
                    pass
            except Exception:
                pass

        mtime = f.stat().st_mtime
        dt = datetime.datetime.fromtimestamp(mtime)
        date_str = dt.strftime("%Y-%m-%d %H:%M")

        # Auto-generate default name if none saved
        display_name = saved_names.get(name, "")
        if not display_name and n_clusters is not None:
            mode_short = {"mdl_pure": "mdl", "classic": "classic", "full": "full", "anti_singleton": "antisgl"}.get(cfg.ga.fitness_mode, cfg.ga.fitness_mode)
            prep_short = "binary" if cfg.ga.matrix_preprocess == "binary" else "norm"
            date_tag = dt.strftime("%b%d")
            type_prefix = "tune_" if result_type == "Tune + Optimize" else ""
            display_name = f"{type_prefix}{n_clusters}cl_{mode_short}_{prep_short}_{date_tag}"
            saved_names[name] = display_name
            names_dirty = True

        items.append({
            "filename": name,
            "type": result_type,
            "date": date_str,
            "n_clusters": n_clusters,
            "n_units": n_units,
            "fitness": fitness,
            "has_figure": (output_dir / (f.stem + ".png")).is_file(),
            "display_name": display_name,
        })

    # Persist any auto-generated names
    if names_dirty:
        names_file.write_text(_json.dumps(saved_names, indent=2), encoding="utf-8")

    # ---- Sensitivity runs (from sensitivity_runs/ directory) ----
    sens_dir = Path("sensitivity_runs")
    if sens_dir.is_dir():
        type_map = {"importance": "Importance", "robustness": "Robustness", "sweep": "Sweep"}
        for run_dir in sorted(sens_dir.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True):
            if not run_dir.is_dir() or not (run_dir / "summary.json").is_file():
                continue
            dir_name = run_dir.name
            # Parse type from dir name (e.g. "2026-04-22T15-17-00_importance")
            sens_type = "Sensitivity"
            for key, label in type_map.items():
                if key in dir_name:
                    sens_type = label
                    break

            try:
                summary = _json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            except Exception:
                continue

            mtime = run_dir.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(mtime)
            date_str = dt.strftime("%Y-%m-%d %H:%M")

            # Extract a fitness-like summary value depending on type
            fitness_val = None
            if sens_type == "Robustness":
                fitness_val = round(summary.get("mean_fitness", 0), 1)
            elif sens_type == "Importance":
                # Show count of params analyzed
                fitness_val = None

            # Check for figure
            has_figure = False
            for ext in ("importance.png", "robustness.png", "sweep.png"):
                if (run_dir / ext).is_file():
                    has_figure = True
                    break

            display_name = saved_names.get(dir_name, "")
            if not display_name:
                date_tag = dt.strftime("%b%d")
                display_name = f"{sens_type.lower()}_{date_tag}"
                saved_names[dir_name] = display_name
                names_dirty = True

            items.append({
                "filename": dir_name,
                "type": sens_type,
                "date": date_str,
                "n_clusters": None,
                "n_units": None,
                "fitness": fitness_val,
                "has_figure": has_figure,
                "display_name": display_name,
                "sensitivity": True,
            })

    if names_dirty:
        names_file.write_text(_json.dumps(saved_names, indent=2), encoding="utf-8")

    return {"results": items}


@app.get("/api/latest-result")
def latest_result(filename: str | None = None):
    """Return an optimization result with matrix data for rendering."""
    import pandas as pd

    cfg = get_app_config()
    output_dir = Path(cfg.data.output_dir)
    if not output_dir.is_dir():
        raise HTTPException(404, "No results directory")

    if filename:
        target = (output_dir / filename).resolve()
        if not str(target).startswith(str(output_dir.resolve())):
            raise HTTPException(403, "Access denied")
        if not target.is_file():
            raise HTTPException(404, "Result file not found")
        result_file = target
    else:
        xlsx_files = sorted(output_dir.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not xlsx_files:
            raise HTTPException(404, "No results found")
        result_file = xlsx_files[0]

    try:
        freq_df = pd.read_excel(str(result_file), sheet_name="dsm_optimized", index_col=0)
        consol_df = pd.read_excel(str(result_file), sheet_name="dsm_consolidation", index_col=0)
        grouping_df = pd.read_excel(str(result_file), sheet_name="grouping")
    except Exception as e:
        raise HTTPException(400, f"Failed to read result file: {e}")

    units = freq_df.index.tolist()
    clusters = [int(str(c).replace("Cluster ", "")) for c in grouping_df["Cluster"]]

    fig_name = result_file.stem + ".png"
    fig_path = fig_name if (output_dir / fig_name).is_file() else None
    config_fig_name = result_file.stem + "_config.png"
    config_fig_path = config_fig_name if (output_dir / config_fig_name).is_file() else None
    stats_fig_name = result_file.stem + "_stats.png"
    stats_fig_path = stats_fig_name if (output_dir / stats_fig_name).is_file() else None

    return {
        "result_freq": freq_df.values.tolist(),
        "result_consol": consol_df.values.tolist(),
        "result_units": units,
        "result_groups": clusters,
        "result_path": result_file.name,
        "figure_path": fig_path,
        "config_figure_path": config_fig_path,
        "stats_figure_path": stats_fig_path,
        "filename": result_file.name,
    }


@app.post("/api/result-name")
def set_result_name(req: dict):
    """Set a display name for a result file."""
    import json as _json

    cfg = get_app_config()
    output_dir = Path(cfg.data.output_dir)
    names_file = output_dir / "result_names.json"

    filename = req.get("filename")
    name = req.get("name", "")
    if not filename:
        raise HTTPException(400, "filename is required")

    names: dict[str, str] = {}
    if names_file.is_file():
        try:
            names = _json.loads(names_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    if name:
        names[filename] = name
    else:
        names.pop(filename, None)

    names_file.write_text(_json.dumps(names, indent=2), encoding="utf-8")
    return {"status": "saved"}


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
