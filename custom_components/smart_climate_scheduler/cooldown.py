"""Cooldown-Berechnungslogik für Smart Climate Scheduler (Version 2.0)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Callable

_LOGGER = logging.getLogger(__name__)


def calculate_cooldown(
    now_dt: datetime,
    next_slot: dict | None,
    current_temp: float,
    next_temp: float,
    cooling_rate_k_h: float,
    tolerance: float,
    max_minutes: int,
    parse_time_func: Callable,
) -> dict:
    """Berechnet die vorgezogene Auskühlphase vor Beginn des nächsten Slots anhand der Verlustrate (K/h)."""

    next_from_time = parse_time_func(next_slot.get("from")) if next_slot else None

    if not next_slot or not next_from_time:
        return {
            "is_cooling_down": False,
            "start_time": None,
            "duration_minutes": 0,
            "effective_loss_rate_k_h": cooling_rate_k_h,
        }

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
        "is_cooling_down": False,
        "start_time": next_slot_start_str,
        "duration_minutes": 0,
        "effective_loss_rate_k_h": round(float(cooling_rate_k_h), 3),
    }

    if next_temp >= current_temp:
        return default_response

    temp_delta = current_temp - next_temp - tolerance

    if temp_delta <= 0 or cooling_rate_k_h <= 0:
        return default_response

    # Exakte Dauer der Abkühlung in Minuten: (ΔT / (K/h)) * 60 Minuten
    raw_duration = (temp_delta / cooling_rate_k_h) * 60.0

    rounded_duration = int(math.ceil(raw_duration / 5.0) * 5)

    duration_minutes = min(rounded_duration, max_minutes)
    if duration_minutes <= 0:
        return default_response

    cooldown_start = next_slot_start - timedelta(minutes=duration_minutes)

    is_cooling_down = cooldown_start <= now_dt < next_slot_start

    return {
        "is_cooling_down": is_cooling_down,
        "start_time": cooldown_start.strftime("%H:%M"),
        "duration_minutes": duration_minutes,
        "effective_loss_rate_k_h": round(float(cooling_rate_k_h), 3),
    }
