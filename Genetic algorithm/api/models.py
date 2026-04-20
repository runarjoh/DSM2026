"""Pydantic request / response models for the DSM GA API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# GA / Optimize
# ---------------------------------------------------------------------------

class GAOverrides(BaseModel):
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    delta: float | None = None
    max_clusters: int | None = None
    target_clusters: int | None = None
    consolidation_mode: Literal["once", "directional"] | None = None
    population_size: int | None = None
    n_generations: int | None = None
    cxpb: float | None = None
    mutpb: float | None = None
    tournsize: int | None = None


class OptimizeRequest(BaseModel):
    ga: GAOverrides | None = None
    freq_csv: str | None = None
    consol_csv: str | None = None


# ---------------------------------------------------------------------------
# Optuna / Tune
# ---------------------------------------------------------------------------

class OptunaOverrides(BaseModel):
    param_group: Literal[
        "weights", "ga_operators", "clustering", "fitness_and_clustering", "all"
    ] | None = None
    n_trials: int | None = None
    n_jobs: int | None = None
    trial_generations: int | None = None
    trial_population: int | None = None


class TuneRequest(BaseModel):
    optuna: OptunaOverrides | None = None
    ga: GAOverrides | None = None
    freq_csv: str | None = None
    consol_csv: str | None = None


# ---------------------------------------------------------------------------
# Tune-then-Optimize
# ---------------------------------------------------------------------------

class TuneOptimizeRequest(BaseModel):
    optuna: OptunaOverrides | None = None
    ga: GAOverrides | None = None
    freq_csv: str | None = None
    consol_csv: str | None = None


# ---------------------------------------------------------------------------
# Visualize
# ---------------------------------------------------------------------------

class VisualizeRequest(BaseModel):
    freq_csv: str
    consol_csv: str
    result_xlsx: str | None = None
    title: str | None = None
    dpi: int = 300


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ConfigSaveRequest(BaseModel):
    """Optionally include overrides to persist."""
    ga: GAOverrides | None = None
    optuna: OptunaOverrides | None = None


class InitConfigRequest(BaseModel):
    output_path: str = "config.yaml"


# ---------------------------------------------------------------------------
# Sensitivity Analysis
# ---------------------------------------------------------------------------

class ImportanceRequest(BaseModel):
    n_trials: int = 30
    param_group: str = "all"
    ga: GAOverrides | None = None
    freq_csv: str | None = None
    consol_csv: str | None = None


class RobustnessRequest(BaseModel):
    n_repeats: int = 10
    ga: GAOverrides | None = None
    freq_csv: str | None = None
    consol_csv: str | None = None


class SweepRequest(BaseModel):
    n_steps: int = 10
    range_multiplier: float = 2.0
    ga: GAOverrides | None = None
    freq_csv: str | None = None
    consol_csv: str | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class RunStarted(BaseModel):
    run_id: str


class UploadResponse(BaseModel):
    paths: list[str]
