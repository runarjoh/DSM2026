import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest
from dsm_ga import load_data, GAConfig


FREQ_CSV   = "consolidation_potential_DSM_scenario1_interaction_frequency.csv"
CONSOL_CSV = "consolidation_potential_DSM_scenario1_SA4_FTE2_2026-08-04-12h27.csv"


def test_load_data_returns_aligned_matrices():
    dsm_freq, dsm_consol, units, header_list = load_data(FREQ_CSV, CONSOL_CSV)
    assert list(dsm_freq.index)   == sorted(units)
    assert list(dsm_freq.columns) == sorted(units)
    assert list(dsm_consol.index)   == sorted(units)
    assert list(dsm_consol.columns) == sorted(units)
    assert dsm_freq.shape == dsm_consol.shape
    assert len(header_list) == len(units)


def test_load_data_returns_30_units():
    dsm_freq, dsm_consol, units, header_list = load_data(FREQ_CSV, CONSOL_CSV)
    assert len(units) == 30


def test_gaconfig_defaults():
    cfg = GAConfig()
    assert cfg.alpha  == 0.15
    assert cfg.beta   == 0.05
    assert cfg.gamma  == 0.15
    assert cfg.delta  == 0.20
    assert cfg.max_clusters       == 10
    assert cfg.target_clusters    == 10
    assert cfg.consolidation_mode == "once"
    assert cfg.population_size == 200
    assert cfg.n_generations   == 400
    assert cfg.cxpb      == 0.5
    assert cfg.mutpb     == 0.1
    assert cfg.tournsize == 5


def test_gaconfig_override():
    cfg = GAConfig(alpha=0.3, population_size=50)
    assert cfg.alpha          == 0.3
    assert cfg.population_size == 50
    assert cfg.beta           == 0.05   # default unchanged


# ---------------------------------------------------------------------------
# run_ga tests (added in Task 3)
# ---------------------------------------------------------------------------

from dsm_ga import run_ga


def _make_synthetic_dsm(n=6):
    """Tiny symmetric interaction-frequency DSM and a zero consolidation matrix."""
    data = np.zeros((n, n))
    for i in range(3):
        for j in range(3):
            if i != j:
                data[i][j] = 1
    for i in range(3, 6):
        for j in range(3, 6):
            if i != j:
                data[i][j] = 1
    units      = [f"Unit{i}" for i in range(n)]
    dsm_freq   = pd.DataFrame(data, index=units, columns=units)
    dsm_consol = pd.DataFrame(np.zeros((n, n)), index=units, columns=units)
    return dsm_freq, dsm_consol


def test_run_ga_returns_correct_types():
    dsm_freq, dsm_consol = _make_synthetic_dsm()
    cfg = GAConfig(
        max_clusters=3,
        target_clusters=2,
        population_size=20,
        n_generations=10,
    )
    best, logbook, fitness = run_ga(dsm_freq, dsm_consol, cfg, verbose=False)
    assert isinstance(best, list)
    assert len(best) == 6
    assert all(0 <= x < cfg.max_clusters for x in best)
    assert isinstance(fitness, float)
    assert fitness > 0


def test_run_ga_logbook_has_generations():
    dsm_freq, dsm_consol = _make_synthetic_dsm()
    cfg = GAConfig(
        max_clusters=3,
        target_clusters=2,
        population_size=20,
        n_generations=5,
    )
    _, logbook, _ = run_ga(dsm_freq, dsm_consol, cfg, verbose=False)
    assert len(logbook) == 5


def test_run_ga_fitness_is_finite():
    dsm_freq, dsm_consol = _make_synthetic_dsm()
    cfg = GAConfig(
        max_clusters=3,
        target_clusters=2,
        population_size=20,
        n_generations=10,
    )
    _, _, fitness = run_ga(dsm_freq, dsm_consol, cfg, verbose=False)
    assert math.isfinite(fitness)
