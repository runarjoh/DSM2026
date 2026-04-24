"""YAML configuration loading, validation, and scaffolding."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Literal

import yaml

from dsm_ga import GAConfig


# ---------------------------------------------------------------------------
# Application config (mirrors the YAML schema)
# ---------------------------------------------------------------------------

@dataclass
class DataConfig:
    freq_csv: str = "consolidation_potential_DSM_scenario1_interaction_frequency.csv"
    consol_csv: str = "consolidation_potential_DSM_scenario1_SA4_FTE2_2026-08-04-12h27.csv"
    grouping_xlsx: str = ""
    output_dir: str = "./results"
    upload_dir: str = "./uploads"


@dataclass
class OptunaConfig:
    param_group: Literal[
        "weights", "ga_operators", "clustering", "fitness_and_clustering", "all"
    ] = "weights"
    n_trials: int = 50
    n_jobs: int = 1
    trial_generations: int = 100
    trial_population: int = 100


@dataclass
class AppConfig:
    data: DataConfig
    ga: GAConfig
    optuna: OptunaConfig

    def to_ga_config(self) -> GAConfig:
        return self.ga


# ---------------------------------------------------------------------------
# Load / validate
# ---------------------------------------------------------------------------

def _build_dataclass(cls, raw: dict):
    """Instantiate *cls* from *raw*, ignoring unknown keys."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in raw.items() if k in known})


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a YAML config file, returning an AppConfig."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(raw).__name__}")

    data_cfg = _build_dataclass(DataConfig, raw.get("data", {}))
    ga_cfg = _build_dataclass(GAConfig, raw.get("ga", {}))
    optuna_cfg = _build_dataclass(OptunaConfig, raw.get("optuna", {}))

    return AppConfig(data=data_cfg, ga=ga_cfg, optuna=optuna_cfg)


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

_TEMPLATE = """\
# DSM GA — Configuration
# See docs/superpowers/specs/2026-04-17-dsm-web-app-design.md for details.

data:
  freq_csv: "consolidation_potential_DSM_scenario1_interaction_frequency.csv"
  consol_csv: "consolidation_potential_DSM_scenario1_SA4_FTE2_2026-08-04-12h27.csv"
  grouping_xlsx: ""    # optional: prior grouping Excel file for baseline comparison
  output_dir: "./results"
  upload_dir: "./uploads"

ga:
  # Fitness weights (active weights must sum to < 1.0)
  alpha: 0.15        # type 1 error: connections across cluster boundaries
  beta: 0.05         # type 2 error: no connection within cluster
  gamma: 0.15        # type 3 error: consolidation potential across clusters
  delta: 0.20        # classic: size imbalance / mdl_pure+: type 4 consolidation overreach
  epsilon: 0.10      # size imbalance weight (full, anti_singleton modes)
  zeta: 0.10         # singleton penalty weight (anti_singleton mode)
  # Clustering
  max_clusters: 10
  target_clusters: 10
  consolidation_mode: "once"       # "once" | "directional"
  fitness_mode: "mdl_pure"          # "classic" | "mdl_pure" | "full" | "anti_singleton"
  matrix_preprocess: "normalize"   # "normalize" | "binary"
  freq_threshold: 0               # filter out frequency values below this before preprocessing
  # GA operators
  population_size: 200
  n_generations: 400
  cxpb: 0.5
  mutpb: 0.1
  tournsize: 5

optuna:
  param_group: "weights"   # "weights" | "ga_operators" | "clustering" | "fitness_and_clustering" | "all"
  n_trials: 50
  n_jobs: 1
  trial_generations: 100
  trial_population: 100
"""


def init_config(output_path: str | Path = "config.yaml") -> Path:
    """Write an annotated starter config.yaml and return the path."""
    p = Path(output_path)
    p.write_text(_TEMPLATE, encoding="utf-8")
    return p


def config_to_dict(cfg: AppConfig) -> dict:
    """Serialise an AppConfig to a plain dict (for JSON responses)."""
    return {
        "data": asdict(cfg.data),
        "ga": asdict(cfg.ga),
        "optuna": asdict(cfg.optuna),
    }
