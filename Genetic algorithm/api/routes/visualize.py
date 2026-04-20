"""Visualize route — generate DSM figure."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

from api.models import VisualizeRequest
from services.viz import plot_dsm_paper

router = APIRouter(prefix="/api", tags=["visualize"])


def _get_config():
    from api.main import get_app_config
    return get_app_config()


@router.post("/visualize")
def visualize(req: VisualizeRequest):
    try:
        from dsm_ga import load_data
        dsm_freq, dsm_consol, units, _ = load_data(req.freq_csv, req.consol_csv)
    except Exception as exc:
        raise HTTPException(400, f"Failed to load data: {exc}")

    # If a result Excel is provided, read grouping from it
    groups = list(range(len(units)))  # default: each unit in its own group
    if req.result_xlsx:
        try:
            grouping_df = pd.read_excel(req.result_xlsx, sheet_name="grouping")
            # Reorder DSM to match the grouping
            unit_to_cluster: dict[str, int] = {}
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
        except Exception as exc:
            raise HTTPException(400, f"Failed to read result Excel: {exc}")

    app_config = _get_config()
    output_dir = Path(app_config.data.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import hashlib, time
    tag = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    fig_name = f"dsm_figure_{tag}.png"
    fig_path = output_dir / fig_name

    plot_dsm_paper(
        dsm_freq, dsm_consol, units, groups,
        title=req.title,
        dpi=req.dpi,
        save_path=str(fig_path),
    )

    return {"figure_path": fig_name}
