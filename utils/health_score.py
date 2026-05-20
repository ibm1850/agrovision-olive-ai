from __future__ import annotations

from typing import Tuple

import numpy as np

SEVERITY_WEIGHTS = {
    "none": 0.0,
    "mild": 0.3,
    "moderate": 0.6,
    "severe": 1.0,
}


def severity_from_probability(disease_probability: float, healthy_prediction: bool) -> str:
    if healthy_prediction or disease_probability < 0.2:
        return "none"
    if disease_probability < 0.45:
        return "mild"
    if disease_probability < 0.72:
        return "moderate"
    return "severe"


def compute_tree_health_score(
    disease_probability: float, severity: str, leaf_condition: float
) -> Tuple[int, str, str]:
    severity_key = severity.lower().strip()
    severity_weight = SEVERITY_WEIGHTS.get(severity_key, 0.6)

    disease_penalty = np.clip(disease_probability, 0, 1) * 55.0
    severity_penalty = severity_weight * 30.0
    leaf_bonus = (np.clip(leaf_condition, 0, 1) - 0.5) * 22.0
    raw_score = 100.0 - disease_penalty - severity_penalty + leaf_bonus
    score = int(np.clip(round(raw_score), 0, 100))

    if score >= 85:
        return score, "Healthy tree", "Healthy"
    if score >= 60:
        return score, "Mild stress", "Needs monitoring"
    if score >= 40:
        return score, "Moderate disease", "At risk"
    return score, "Severe disease", "Critical"

