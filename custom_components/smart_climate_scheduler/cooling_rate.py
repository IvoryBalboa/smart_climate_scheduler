"""Abkühlraten-Engine (Wärmeverlustrate in K/h) – Delegiert an zentrale Funktionen in helpers.py (Version 2.1.0)."""
from __future__ import annotations

from .helpers import (
    COOLING_EMA_ALPHA,
    MAX_PLAUSIBLE_COOLING_RATE,
    MIN_COOLING_STEP_SECONDS,
    MIN_COOLING_TEMP_DROP,
    MIN_PLAUSIBLE_COOLING_RATE,
    apply_cooling_ema,
    async_record_cooling_rate,
    calculate_overall_average as calculate_overall_cooling_average,
    calculate_step_cooling_rate,
    get_effective_cooling_rate,
    normalize_matrix as normalize_cooling_matrix,
    update_matrix_with_rate as update_cooling_matrix_with_rate,
)

__all__ = [
    "COOLING_EMA_ALPHA",
    "MAX_PLAUSIBLE_COOLING_RATE",
    "MIN_COOLING_STEP_SECONDS",
    "MIN_COOLING_TEMP_DROP",
    "MIN_PLAUSIBLE_COOLING_RATE",
    "apply_cooling_ema",
    "async_record_cooling_rate",
    "calculate_overall_cooling_average",
    "calculate_step_cooling_rate",
    "get_effective_cooling_rate",
    "normalize_cooling_matrix",
    "update_cooling_matrix_with_rate",
]

