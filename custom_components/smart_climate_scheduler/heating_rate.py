"""Aufheizraten-Engine (K/h) für Smart Climate Scheduler.

Verantwortlich für die differentielle Messung der Aufheizrate (K/h),
die exponentielle Glättung (EMA), das Lernen in die Außentemperatur-Matrix
und die Ermittlung der effektiven Aufheizrate für das Vorheizen.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from homeassistant.core import HomeAssistant

from .helpers import (
    apply_ema,
    get_effective_rate,
    safe_float,
    update_matrix_with_rate,
)

_LOGGER = logging.getLogger(__name__)

# Konfiguration und Schwellwerte für die Aufheizraten-Messung
HEATING_EMA_ALPHA = 0.25
MIN_STEP_SECONDS = 300
MIN_STEP_TEMP_RISE = 0.01
MIN_PLAUSIBLE_RATE = 0.10
MAX_PLAUSIBLE_RATE = 3.0


def apply_step_ema(new_rate: float, current_ema: float | None, alpha: float = HEATING_EMA_ALPHA) -> float:
    """Glättet die Schritt-Aufheizrate mit exponentiellem gleitendem Durchschnitt (EMA)."""
    return apply_ema(new_rate, current_ema, alpha)


def calculate_step_heating_rate(
    last_time: datetime | None,
    last_temp: float | None,
    curr_time: datetime,
    curr_temp: float,
    min_seconds: int = MIN_STEP_SECONDS,
    min_temp_delta: float = MIN_STEP_TEMP_RISE,
) -> tuple[float | None, bool]:
    """Berechnet die differentielle Schritt-Aufheizrate ((T_neu - T_alt) / Δt) * 3600."""
    if last_time is None or last_temp is None:
        return None, False

    try:
        dt_seconds = (curr_time - last_time).total_seconds()
        if dt_seconds < min_seconds:
            return None, False

        temp_diff = float(curr_temp) - float(last_temp)
        if temp_diff < min_temp_delta:
            return None, False

        dt_hours = dt_seconds / 3600.0
        if dt_hours <= 0:
            return None, False

        raw_rate = temp_diff / dt_hours
        if math.isnan(raw_rate) or math.isinf(raw_rate):
            return None, False

        clamped = max(MIN_PLAUSIBLE_RATE, min(MAX_PLAUSIBLE_RATE, raw_rate))
        return round(clamped, 3), True
    except Exception as e:
        _LOGGER.debug("Fehler bei Schritt-Berechnung der Aufheizrate: %s", e)
        return None, False


async def async_record_live_heating_rate(
    hass: HomeAssistant,
    entry_id: str,
    live_rate: float | None,
    outside_temp: float | None,
    entry_data: dict,
    storage,
    fallback_rate: float = 1.0,
    learning_enabled: bool = True,
) -> float | None:
    """Speichert einen positiven Live-Aufheizwert in der Außentemperatur-Matrix und bildet den Gesamt-Durchschnitt."""
    if not learning_enabled:
        return None

    if live_rate is None or math.isnan(live_rate) or live_rate <= 0:
        return None

    safe_fallback = safe_float(fallback_rate, 1.0)
    current_matrix = entry_data.get("averages", {})
    updated_matrix, bucket_avg, overall_avg = update_matrix_with_rate(
        matrix=current_matrix,
        outside_temp=outside_temp,
        rate=live_rate,
        fallback_rate=safe_fallback,
    )

    entry_data["averages"] = updated_matrix
    entry_data["average"] = overall_avg

    _LOGGER.debug(
        "Live-Aufheizrate gelernt [%s]: Live=%.3f K/h, Außentemp=%s°C -> Matrix-Ø=%.3f K/h, Gesamt-Ø=%.3f K/h",
        entry_id,
        live_rate,
        outside_temp,
        bucket_avg,
        overall_avg,
    )

    if storage:
        await storage.async_save_data(
            {
                "averages": updated_matrix,
                "average": overall_avg,
            }
        )

    return bucket_avg


def get_effective_heating_rate(
    entry_data: dict,
    outside_temp: float | None,
    fallback_rate: float = 1.0,
    learning_enabled: bool = True,
) -> float:
    """Ermittelt die geltende Aufheizrate für Preheat (Matrix-Durchschnitt -> Gesamt-Durchschnitt -> Default)."""
    return get_effective_rate(
        entry_data=entry_data,
        outside_temp=outside_temp,
        fallback_rate=fallback_rate,
        learning_enabled=learning_enabled,
        matrix_key="averages",
        avg_key="average",
    )
