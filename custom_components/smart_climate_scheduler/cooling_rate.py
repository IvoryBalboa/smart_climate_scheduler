"""Abkühlraten-Engine (K/h) für Smart Climate Scheduler.

Verantwortlich für die differentielle Messung der Raum-Wärmeverlustrate (K/h),
die exponentielle Glättung (EMA), das Lernen in die Außentemperatur-Matrix
und die Ermittlung der effektiven Abkühlrate für das vorzeitige Auskühlen (Cooldown).
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

# Konfiguration und Schwellwerte für die Abkühlraten-Messung
COOLING_EMA_ALPHA = 0.30
MIN_COOLING_STEP_SECONDS = 900
MIN_COOLING_TEMP_DROP = 0.01
MIN_PLAUSIBLE_COOLING_RATE = 0.02
MAX_PLAUSIBLE_COOLING_RATE = 1.5


def apply_cooling_ema(new_rate: float, current_ema: float | None, alpha: float = COOLING_EMA_ALPHA) -> float:
    """Glättet die Schritt-Abkühlrate mit exponentiellem gleitendem Durchschnitt (EMA)."""
    return apply_ema(new_rate, current_ema, alpha)


def calculate_step_cooling_rate(
    last_time: datetime | None,
    last_temp: float | None,
    curr_time: datetime,
    curr_temp: float,
    min_seconds: int = MIN_COOLING_STEP_SECONDS,
    min_temp_drop: float = MIN_COOLING_TEMP_DROP,
    max_plausible_rate: float = MAX_PLAUSIBLE_COOLING_RATE,
    min_plausible_rate: float = MIN_PLAUSIBLE_COOLING_RATE,
) -> tuple[float | None, bool]:
    """Berechnet die differentielle Abkühlrate ((T_alt - T_neu) / Δt) * 3600."""
    if last_time is None or last_temp is None:
        return None, False

    try:
        dt_seconds = (curr_time - last_time).total_seconds()
        if dt_seconds < min_seconds:
            return None, False

        temp_drop = float(last_temp) - float(curr_temp)
        if temp_drop < min_temp_drop:
            return None, False

        dt_hours = dt_seconds / 3600.0
        if dt_hours <= 0:
            return None, False

        raw_rate = temp_drop / dt_hours
        if math.isnan(raw_rate) or math.isinf(raw_rate):
            return None, False

        if raw_rate > max_plausible_rate:
            _LOGGER.debug(
                "Abkühlrate von %.2f K/h überschreitet Plausibilitätsgrenze (vermutlich Lüftung) -> verworfen",
                raw_rate,
            )
            return None, False

        if raw_rate < min_plausible_rate:
            return None, False

        return round(raw_rate, 3), True
    except Exception as e:
        _LOGGER.debug("Fehler bei Schritt-Berechnung der Abkühlrate: %s", e)
        return None, False


async def async_record_cooling_rate(
    hass: HomeAssistant,
    entry_id: str,
    rate: float | None,
    outside_temp: float | None,
    entry_data: dict,
    storage,
    fallback_rate: float = 0.2,
    learning_enabled: bool = True,
) -> float | None:
    """Speichert einen validen Abkühlwert in der Außentemperatur-Matrix der Abkühlung."""
    if not learning_enabled:
        return None

    if rate is None or math.isnan(rate) or rate <= 0:
        return None

    safe_fallback = safe_float(fallback_rate, 0.2)
    current_matrix = entry_data.get("cooling_averages", {})
    updated_matrix, bucket_avg, overall_avg = update_matrix_with_rate(
        matrix=current_matrix,
        outside_temp=outside_temp,
        rate=rate,
        fallback_rate=safe_fallback,
    )

    entry_data["cooling_averages"] = updated_matrix
    entry_data["cooling_average"] = overall_avg

    _LOGGER.debug(
        "Abkühlrate gelernt [%s]: Schritt=%.3f K/h, Außentemp=%s°C -> Matrix-Ø=%.3f K/h, Gesamt-Ø=%.3f K/h",
        entry_id,
        rate,
        outside_temp,
        bucket_avg,
        overall_avg,
    )

    if storage:
        await storage.async_save_data(
            {
                "cooling_averages": updated_matrix,
                "cooling_average": overall_avg,
            }
        )

    return bucket_avg


def get_effective_cooling_rate(
    entry_data: dict,
    outside_temp: float | None,
    fallback_rate: float = 0.2,
    learning_enabled: bool = True,
) -> float:
    """Ermittelt die geltende Abkühlrate für Cooldown (Matrix -> Gesamtdurchschnitt -> Fallback)."""
    return get_effective_rate(
        entry_data=entry_data,
        outside_temp=outside_temp,
        fallback_rate=fallback_rate,
        learning_enabled=learning_enabled,
        matrix_key="cooling_averages",
        avg_key="cooling_average",
    )
