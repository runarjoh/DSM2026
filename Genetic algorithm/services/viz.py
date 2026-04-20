"""Publication-quality DSM visualisation — extracted from notebook."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server use
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


def plot_dsm_paper(
    freq_df: pd.DataFrame,
    consol_df: pd.DataFrame,
    units: list[str],
    groups: list[int],
    title: str | None = None,
    dpi: int = 300,
    save_path: str | Path | None = None,
) -> Path | None:
    """Render a publication-quality DSM figure and optionally save to *save_path*.

    Returns the Path of the saved PNG, or None if *save_path* was not given.
    """
    n = len(units)
    unique_clusters = sorted(set(groups))

    c_start: dict[int, int] = {}
    c_end: dict[int, int] = {}
    for idx, g in enumerate(groups):
        if g not in c_start:
            c_start[g] = idx
        c_end[g] = idx

    CONSOL_COLOR = [0.40, 0.63, 0.85, 1.0]
    DIAG_COLOR = [0.88, 0.88, 0.88, 1.0]
    WHITE = [1.00, 1.00, 1.00, 1.0]

    rgba = np.tile(WHITE, (n, n, 1))
    freq = freq_df.values.astype(float)
    consol = consol_df.values.astype(float)
    for i in range(n):
        for j in range(n):
            if i == j:
                rgba[i, j] = DIAG_COLOR
            elif consol[i, j] == 1:
                rgba[i, j] = CONSOL_COLOR

    cell_size = max(0.28, min(0.45, 10.0 / n))
    fig_size = max(8, n * cell_size + 2.5)

    fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=dpi)
    ax.imshow(rgba, aspect="equal", interpolation="none", origin="upper")

    fontsize = max(4.5, min(8.0, 95.0 / n))
    for i in range(n):
        for j in range(n):
            if i != j and freq[i, j] > 0:
                on_blue = consol[i, j] == 1
                ax.text(
                    j, i, str(int(freq[i, j])),
                    ha="center", va="center", fontsize=fontsize,
                    color="white" if on_blue else "#333333",
                    fontfamily="sans-serif",
                )

    lw = max(1.2, min(2.0, 14.0 / n))
    for g in unique_clusters:
        s, e = c_start[g], c_end[g]
        rect = patches.Rectangle(
            (s - 0.5, s - 0.5), e - s + 1, e - s + 1,
            linewidth=lw, edgecolor="#111111", facecolor="none", zorder=4,
        )
        ax.add_patch(rect)

    lbl_fs = max(5.5, min(8.5, 85.0 / n))
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(units, rotation=90, fontsize=lbl_fs, ha="center", fontfamily="sans-serif")
    ax.set_yticklabels(units, fontsize=lbl_fs, fontfamily="sans-serif")
    ax.tick_params(
        top=True, labeltop=True, bottom=False, labelbottom=False,
        left=True, labelleft=True, length=0,
    )
    ax.xaxis.set_label_position("top")
    for spine in ax.spines.values():
        spine.set_visible(False)

    clbl_fs = max(6, min(10, 100.0 / n))
    for g in unique_clusters:
        s, e = c_start[g], c_end[g]
        ax.text(
            (s + e) / 2.0, (s + e) / 2.0, f"G{g}",
            ha="center", va="center", fontsize=clbl_fs,
            fontweight="bold", color="#222222", zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.75, linewidth=0),
        )

    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", pad=14, fontfamily="sans-serif")

    ax.legend(
        handles=[
            Patch(facecolor=CONSOL_COLOR[:3], edgecolor="none", label="Consolidation potential"),
            Patch(facecolor="white", edgecolor="#aaaaaa", linewidth=0.8, label="No consolidation potential"),
        ],
        loc="lower right", bbox_to_anchor=(1.0, -0.18),
        fontsize=8, frameon=True, framealpha=0.9, edgecolor="#cccccc", ncol=2,
    )

    plt.tight_layout(pad=1.5)

    result_path: Path | None = None
    if save_path:
        result_path = Path(save_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(result_path), dpi=dpi, bbox_inches="tight", facecolor="white")

    plt.close(fig)
    return result_path
