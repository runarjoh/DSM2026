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

    CONSOL_COLOR = [0.231, 0.310, 0.894, 1.0]  # Reconfig Blue #3B4FE4
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


# ---------------------------------------------------------------------------
# Configuration summary image
# ---------------------------------------------------------------------------

def plot_config_summary(
    config: dict,
    title: str | None = None,
    dpi: int = 200,
    save_path: str | Path | None = None,
) -> Path | None:
    """Render the GA configuration as a clean table image."""

    weight_keys = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"]
    cluster_keys = ["max_clusters", "target_clusters", "consolidation_mode",
                    "fitness_mode", "matrix_preprocess", "freq_threshold"]
    operator_keys = ["population_size", "n_generations", "cxpb", "mutpb", "tournsize"]

    sections = [
        ("Fitness Weights", [(k, config[k]) for k in weight_keys if k in config]),
        ("Clustering", [(k, config[k]) for k in cluster_keys if k in config]),
        ("GA Operators", [(k, config[k]) for k in operator_keys if k in config]),
    ]

    total_rows = sum(len(rows) + 1 for _, rows in sections)  # +1 for section headers
    fig_h = max(2.5, 0.30 * total_rows + 0.8)
    fig, ax = plt.subplots(figsize=(5, fig_h), dpi=dpi)
    ax.axis("off")

    y = 0.97
    line_h = 0.88 / total_rows

    if title:
        ax.text(0.5, y, title, transform=ax.transAxes,
                fontsize=10, fontweight="bold", ha="center", va="top",
                fontfamily="sans-serif")
        y -= line_h * 1.2

    for section_name, rows in sections:
        ax.text(0.05, y, section_name, transform=ax.transAxes,
                fontsize=8.5, fontweight="bold", color="#3B4FE4",
                va="top", fontfamily="sans-serif")
        y -= line_h
        for key, val in rows:
            display_val = f"{val:.4f}" if isinstance(val, float) else str(val)
            ax.text(0.08, y, key, transform=ax.transAxes,
                    fontsize=7.5, color="#555555", va="top",
                    fontfamily="sans-serif")
            ax.text(0.55, y, display_val, transform=ax.transAxes,
                    fontsize=7.5, color="#1A1D26", va="top",
                    fontfamily="monospace", fontweight="bold")
            y -= line_h
        y -= line_h * 0.3

    plt.tight_layout(pad=0.5)
    result_path: Path | None = None
    if save_path:
        result_path = Path(save_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(result_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return result_path


# ---------------------------------------------------------------------------
# Cluster statistics image
# ---------------------------------------------------------------------------

def plot_cluster_stats(
    fitness: float,
    n_clusters: int,
    mdl: float,
    components: dict[str, dict],
    rates: dict[str, float],
    title: str | None = None,
    dpi: int = 200,
    save_path: str | Path | None = None,
) -> Path | None:
    """Render cluster statistics (fitness decomposition + rates) as a table image."""

    comp_labels = {
        "mdl": "MDL", "freq_between": "Freq between", "freq_gap": "Freq gap",
        "consol_between": "Consol between", "consol_gap": "Consol gap",
        "size_imbalance": "Size imbalance", "singleton_penalty": "Singleton penalty",
    }
    rate_labels = {
        "freqCapture": "Freq capture", "consolCapture": "Consol capture",
        "bothCapture": "Both capture", "density": "Cluster density",
        "alignment": "Cluster alignment", "noise": "Cluster noise",
    }

    n_comp = len(components)
    n_rate = len(rates)
    total_rows = 3 + n_comp + 2 + n_rate  # header + components + divider + rates
    fig_h = max(3.0, 0.28 * total_rows + 1.2)
    fig, ax = plt.subplots(figsize=(6, fig_h), dpi=dpi)
    ax.axis("off")

    y = 0.97
    line_h = 0.85 / total_rows

    # Title
    heading = title or "Cluster Statistics"
    ax.text(0.5, y, heading, transform=ax.transAxes,
            fontsize=10, fontweight="bold", ha="center", va="top",
            fontfamily="sans-serif")
    y -= line_h * 1.3

    # Summary line
    summary = f"Clusters: {n_clusters}     MDL: {mdl:.1f}     Fitness: {fitness:.2f}"
    ax.text(0.5, y, summary, transform=ax.transAxes,
            fontsize=8, ha="center", va="top", color="#333333",
            fontfamily="monospace")
    y -= line_h * 1.5

    # Fitness decomposition header
    ax.text(0.05, y, "Component", transform=ax.transAxes,
            fontsize=7.5, fontweight="bold", color="#8B92A5", va="top",
            fontfamily="sans-serif")
    ax.text(0.50, y, "Weight", transform=ax.transAxes,
            fontsize=7.5, fontweight="bold", color="#8B92A5", va="top",
            ha="right", fontfamily="sans-serif")
    ax.text(0.95, y, "Value", transform=ax.transAxes,
            fontsize=7.5, fontweight="bold", color="#8B92A5", va="top",
            ha="right", fontfamily="sans-serif")
    y -= line_h

    for key, comp in components.items():
        label = comp_labels.get(key, key)
        weight = comp.get("weight", 0)
        value = comp.get("value", 0)
        pct = f"({value / fitness * 100:.0f}%)" if fitness > 0 else ""
        ax.text(0.05, y, label, transform=ax.transAxes,
                fontsize=7.5, color="#4A4F63", va="top", fontfamily="sans-serif")
        ax.text(0.50, y, f"{weight * 100:.1f}%", transform=ax.transAxes,
                fontsize=7.5, color="#8B92A5", va="top", ha="right",
                fontfamily="monospace")
        ax.text(0.95, y, f"{value:.1f} {pct}", transform=ax.transAxes,
                fontsize=7.5, color="#1A1D26", fontweight="bold", va="top",
                ha="right", fontfamily="monospace")
        y -= line_h

    # Divider
    y -= line_h * 0.3
    ax.plot([0.05, 0.95], [y + line_h * 0.15, y + line_h * 0.15],
            color="#E2E5EB", linewidth=0.5, transform=ax.transAxes, clip_on=False)
    y -= line_h * 0.3

    # Rates header
    ax.text(0.05, y, "Rate", transform=ax.transAxes,
            fontsize=7.5, fontweight="bold", color="#8B92A5", va="top",
            fontfamily="sans-serif")
    ax.text(0.95, y, "Value", transform=ax.transAxes,
            fontsize=7.5, fontweight="bold", color="#8B92A5", va="top",
            ha="right", fontfamily="sans-serif")
    y -= line_h

    for key, value in rates.items():
        label = rate_labels.get(key, key)
        ax.text(0.05, y, label, transform=ax.transAxes,
                fontsize=7.5, color="#4A4F63", va="top", fontfamily="sans-serif")
        ax.text(0.95, y, f"{value:.1f}%", transform=ax.transAxes,
                fontsize=7.5, color="#1A1D26", fontweight="bold", va="top",
                ha="right", fontfamily="monospace")
        y -= line_h

    plt.tight_layout(pad=0.5)
    result_path: Path | None = None
    if save_path:
        result_path = Path(save_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(result_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return result_path
