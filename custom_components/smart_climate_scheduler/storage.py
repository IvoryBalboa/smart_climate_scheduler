"""Persistenter Speicher für gelernte Aufheizraten und Scheduler-Zustände (Version 2.0)."""
from __future__ import annotations

import logging
import math
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_COOLING_RATE,
)
from .helpers import calculate_overall_average, normalize_matrix

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 2


def _clean_rate(val: any, default: float = DEFAULT_FALLBACK_HEATING_RATE) -> float:
    """Bereinigt Raten von NaN, None und ungültigen Werten."""
    if val is None or val == "":
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f) or f <= 0:
            return default
        return round(f, 3)
    except (ValueError, TypeError):
        return default


class ClimateSchedulerStorage:
    """Verwaltet das Laden und Speichern der gelernten Aufheiz- und Abkühlraten-Matrix und Einstellungen."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}_v2.storage")
        self._cached_data: dict | None = None

    async def async_get_data(self) -> dict:
        """Lädt die gespeicherten Daten (inkl. automatischer Normalisierung der Matrizen)."""
        if self._cached_data is not None:
            return self._cached_data

        data = await self._store.async_load()

        if data is None:
            data = {
                "automation_enabled": False,
                "averages": {},
                "average": DEFAULT_FALLBACK_HEATING_RATE,
                "cooling_averages": {},
                "cooling_average": DEFAULT_FALLBACK_COOLING_RATE,
                "overrides": {},
            }
            await self._store.async_save(data)
        else:
            norm_averages = normalize_matrix(data.get("averages", {}))
            raw_avg = data.get("average")
            data["averages"] = norm_averages
            data["average"] = calculate_overall_average(
                norm_averages, _clean_rate(raw_avg, DEFAULT_FALLBACK_HEATING_RATE)
            )

            norm_cooling = normalize_matrix(data.get("cooling_averages", {}))
            raw_cooling_avg = data.get("cooling_average")
            data["cooling_averages"] = norm_cooling
            data["cooling_average"] = calculate_overall_average(
                norm_cooling, _clean_rate(raw_cooling_avg, DEFAULT_FALLBACK_COOLING_RATE)
            )

            data["automation_enabled"] = bool(data.get("automation_enabled", False))
            raw_ov = data.get("overrides")
            data["overrides"] = dict(raw_ov) if isinstance(raw_ov, dict) else {}

        self._cached_data = data
        return data

    async def async_save_data(self, patch: dict) -> None:
        """Speichert Daten partiell ab und verhindert Überschreib-Konflikte im RAM."""
        current = await self.async_get_data()
        
        # Sanitize patch before saving to ensure strict JSON validity
        cleaned_patch = {}
        for k, v in patch.items():
            if k == "average":
                cleaned_patch[k] = _clean_rate(v, DEFAULT_FALLBACK_HEATING_RATE)
            elif k == "cooling_average":
                cleaned_patch[k] = _clean_rate(v, DEFAULT_FALLBACK_COOLING_RATE)
            elif k == "averages" and isinstance(v, dict):
                cleaned_patch[k] = normalize_matrix(v)
            elif k == "cooling_averages" and isinstance(v, dict):
                cleaned_patch[k] = normalize_matrix(v)
            elif k == "overrides" and isinstance(v, dict):
                cleaned_patch[k] = dict(v)
            else:
                cleaned_patch[k] = v

        current.update(cleaned_patch)
        self._cached_data = current
        await self._store.async_save(current)
