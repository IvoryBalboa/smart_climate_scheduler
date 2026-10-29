"""Aufheizraten-Engine (K/h) – Delegiert an zentrale Matrix- & Ratenfunktionen in helpers.py (Version 2.1.0)."""
from __future__ import annotations

from .helpers import (
    HEATING_EMA_ALPHA as EMA_ALPHA,
    MAX_PLAUSIBLE_RATE,
    MIN_PLAUSIBLE_RATE,
    MIN_STEP_SECONDS,
    MIN_STEP_TEMP_RISE,
    apply_step_ema,
    async_record_live_heating_rate,
    calculate_live_heating_rate,
    calculate_overall_average,
    calculate_step_heating_rate,
    get_effective_heating_rate,
    normalize_matrix,
    update_matrix_with_rate as update_matrix_with_live_rate,
)

__all__ = [
    "EMA_ALPHA",
    "MAX_PLAUSIBLE_RATE",
    "MIN_PLAUSIBLE_RATE",
    "MIN_STEP_SECONDS",
    "MIN_STEP_TEMP_RISE",
    "apply_step_ema",
    "async_record_live_heating_rate",
    "calculate_live_heating_rate",
    "calculate_overall_average",
    "calculate_step_heating_rate",
    "get_effective_heating_rate",
    "normalize_matrix",
    "update_matrix_with_live_rate",
]

