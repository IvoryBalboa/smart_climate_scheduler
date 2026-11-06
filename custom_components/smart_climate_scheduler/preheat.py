"""Preheat-Berechnungslogik für Smart Climate Scheduler (Version 2.0)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Callable

_LOGGER = logging.getLogger(__name__)


def calculate_preheat(
    now_dt: datetime,
    next_slot: dict | None,
    current_temp: float,
    next_temp: float,
    heating_rate_k_h: float,
    max_minutes: int,
    parse_time_func: Callable,
) -> tuple[dict, bool]:
    """Berechnet die vorgezogene Aufheizphase (Preheat) basierend auf der realen Aufheizrate (K/h)."""

    next_from_time = parse_time_func(next_slot.get("from")) if next_slot else None

    if not next_slot or not next_from_time:
        return {
            "is_preheating": False,
            "start_time": None,
            "duration_minutes": 0,
            "effective_rate_k_h": heating_rate_k_h,
        }, False

    slot_date_str = next_slot.get("date") if next_slot else None
    if slot_date_str:
        try:
            next_slot_start = datetime.strptime(slot_date_str, "%Y-%m-%d").replace(
                hour=next_from_time.hour,
                minute=next_from_time.minute,
                second=next_from_time.second,
                tzinfo=now_dt.tzinfo,
            )
        except Exception:
            next_slot_start = datetime.combine(
                now_dt.date(), next_from_time, tzinfo=now_dt.tzinfo
            )
    else:
        next_slot_start = datetime.combine(
            now_dt.date(), next_from_time, tzinfo=now_dt.tzinfo
        )

    if next_slot_start <= now_dt:
        next_slot_start += timedelta(days=1)

    next_slot_start_str = next_slot_start.strftime("%H:%M:%S")

    default_response = {
        "is_preheating": False,
        "start_time": next_slot_start_str,
        "duration_minutes": 0,
        "effective_rate_k_h": heating_rate_k_h,
    }

    if next_temp <= current_temp or heating_rate_k_h <= 0:
        return default_response, False

    temp_delta = next_temp - current_temp
    if temp_delta <= 0:
        return default_response, False

    # Exakte Dauer in Minuten: (ΔT / (K/h)) * 60 Minuten
    raw_duration = (temp_delta / heating_rate_k_h) * 60.0

    rounded_duration = int(math.ceil(raw_duration / 5.0) * 5)
    duration_minutes = min(rounded_duration, max_minutes)
    if duration_minutes <= 0:
        return default_response, False

    preheat_start = next_slot_start - timedelta(minutes=duration_minutes)
    is_preheating = preheat_start <= now_dt < next_slot_start

    preheat_dict = {
        "is_preheating": is_preheating,
        "start_time": preheat_start.strftime("%H:%M"),
        "duration_minutes": duration_minutes,
        "effective_rate_k_h": round(heating_rate_k_h, 3),
    }

    return preheat_dict, is_preheating