"""Compute cluster statistics (fitness components, rates) for result export."""

from __future__ import annotations

import math
from dataclasses import asdict


def compute_cluster_stats(
    clusters: list[int],
    freq_matrix,
    consol_matrix,
    ga_config,
) -> dict:
    """Compute fitness components and capture rates for a given clustering.

    Returns a dict with keys: fitness, mdl, n_clusters, components, rates.
    """
    from dsm_ga import _make_eval_fn

    n = len(clusters)

    # Normalize cluster IDs to contiguous 0-based
    unique_labels = sorted(set(clusters))
    label_map = {lab: i for i, lab in enumerate(unique_labels)}
    norm_clusters = [label_map[c] for c in clusters]
    n_clusters = len(unique_labels)

    from dataclasses import replace as _dc_replace
    cfg = ga_config
    if cfg.max_clusters < n_clusters:
        cfg = _dc_replace(cfg, max_clusters=n_clusters)

    eval_fn = _make_eval_fn(freq_matrix, consol_matrix, cfg)
    fitness = eval_fn(norm_clusters)[0]

    # Cluster sizes
    cluster_sizes: dict[int, int] = {}
    for c in norm_clusters:
        cluster_sizes[c] = cluster_sizes.get(c, 0) + 1

    mdl_raw = n_clusters * math.log2(n) + math.log2(n) * sum(cluster_sizes.values())

    # Preprocess freq matrix same as fitness function
    raw_freq = freq_matrix.tolist() if hasattr(freq_matrix, 'tolist') else freq_matrix
    threshold = cfg.freq_threshold
    if threshold > 0:
        raw_freq = [
            [0.0 if 0 < raw_freq[r][c] < threshold else raw_freq[r][c]
             for c in range(n)]
            for r in range(n)
        ]
    if cfg.matrix_preprocess == "binary":
        prep_freq = [[1.0 if raw_freq[r][c] > 0 else 0.0 for c in range(n)] for r in range(n)]
    else:
        max_freq = max(
            (raw_freq[r][c] for r in range(n) for c in range(n) if r != c),
            default=1.0,
        ) or 1.0
        prep_freq = [[raw_freq[r][c] / max_freq for c in range(n)] for r in range(n)]

    consol_vals = consol_matrix.tolist() if hasattr(consol_matrix, 'tolist') else consol_matrix

    # Compute raw error terms (S1-S4)
    S1 = S2 = S3 = S4 = 0.0
    for col in range(n):
        for row in range(n):
            if col == row:
                continue
            same = norm_clusters[col] == norm_clusters[row]
            val = prep_freq[col][row]
            if val > 0 and not same:
                S1 += val
            if val == 0 and same:
                S2 += 1.0
            if not same:
                if cfg.consolidation_mode == "once":
                    if col < row and (consol_vals[col][row] == 1 or consol_vals[row][col] == 1):
                        S3 += 1
                elif cfg.consolidation_mode == "directional":
                    S3 += consol_vals[col][row]
            if same:
                if cfg.consolidation_mode == "once":
                    if col < row and consol_vals[col][row] == 0 and consol_vals[row][col] == 0:
                        S4 += 1
                elif cfg.consolidation_mode == "directional":
                    if consol_vals[col][row] == 0:
                        S4 += 1

    log_factor = 2 * math.log2(n + 1)
    mode = cfg.fitness_mode

    if mode == "full":
        mdl_weight = 1.0 - cfg.alpha - cfg.beta - cfg.gamma - cfg.delta - cfg.epsilon
    elif mode == "anti_singleton":
        mdl_weight = 1.0 - cfg.alpha - cfg.beta - cfg.gamma - cfg.delta - cfg.epsilon - cfg.zeta
    elif mode == "mdl_pure":
        mdl_weight = 1.0 - cfg.alpha - cfg.beta - cfg.gamma - cfg.delta
    else:
        mdl_weight = 1.0 - cfg.alpha - cfg.beta - cfg.gamma

    components = {
        "mdl": {"weight": mdl_weight, "value": mdl_weight * mdl_raw},
        "freq_between": {"weight": cfg.alpha, "value": cfg.alpha * S1 * log_factor},
        "freq_gap": {"weight": cfg.beta, "value": cfg.beta * S2 * log_factor},
        "consol_between": {"weight": cfg.gamma, "value": cfg.gamma * S3 * log_factor},
    }
    if mode != "classic":
        components["consol_gap"] = {"weight": cfg.delta, "value": cfg.delta * S4 * log_factor}
    if mode in ("full", "anti_singleton"):
        ideal_size = n / cfg.target_clusters
        size_imb = sum((cluster_sizes.get(c, 0) - ideal_size) ** 2
                       for c in cluster_sizes if cluster_sizes[c] > 0) / cfg.target_clusters
        components["size_imbalance"] = {"weight": cfg.epsilon, "value": cfg.epsilon * size_imb * log_factor}
    if mode == "anti_singleton":
        n_sing = sum(1 for sz in cluster_sizes.values() if sz == 1)
        sp = n_sing ** 2 / cfg.target_clusters
        components["singleton_penalty"] = {"weight": cfg.zeta, "value": cfg.zeta * sp * log_factor}

    # Cell counts for rates
    freq_bin = [[1.0 if raw_freq[r][c] > 0 else 0.0 for c in range(n)] for r in range(n)]
    freq_within = freq_outside = consol_within = consol_outside = 0
    both_within = both_outside = blank_within = blank_outside = 0
    for r in range(n):
        for c in range(n):
            if r == c:
                continue
            same = norm_clusters[r] == norm_clusters[c]
            has_freq = freq_bin[r][c] > 0
            has_consol = consol_vals[r][c] == 1
            if has_freq:
                if same:
                    freq_within += 1
                else:
                    freq_outside += 1
            if has_consol:
                if same:
                    consol_within += 1
                else:
                    consol_outside += 1
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

    no_freq_within = (freq_within + blank_within + (consol_within - both_within))
    # Simpler: just count directly
    total_within = sum(1 for r in range(n) for c in range(n) if r != c and norm_clusters[r] == norm_clusters[c])
    total_freq = freq_within + freq_outside
    total_consol = consol_within + consol_outside
    total_both = both_within + both_outside

    rates = {}
    rates["freqCapture"] = freq_within / total_freq * 100 if total_freq > 0 else 0
    rates["consolCapture"] = consol_within / total_consol * 100 if total_consol > 0 else 0
    rates["bothCapture"] = both_within / total_both * 100 if total_both > 0 else 0
    rates["density"] = freq_within / total_within * 100 if total_within > 0 else 0
    rates["alignment"] = consol_within / total_within * 100 if total_within > 0 else 0
    rates["noise"] = blank_within / total_within * 100 if total_within > 0 else 0

    return {
        "fitness": fitness,
        "mdl": mdl_raw,
        "n_clusters": n_clusters,
        "components": components,
        "rates": rates,
    }
