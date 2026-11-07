"""Zustands- und Thermik-Evaluierung für Smart Climate Scheduler (Version 2.0)."""
from __future__ import annotations

import logging
import math
import time as time_mod
from datetime import datetime, timedelta
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_ZONE_HOME_ENTITY,
    CONF_ZONE_AWAY_NEAR_ENTITY,
    CONF_NEAR_DISTANCE,
    CONF_MAX_MINUTES_PREHEAT,
    CONF_MAX_MINUTES_COOLDOWN,
    CONF_PREHEAT_ENABLED,
    CONF_COOLDOWN_ENABLED,
    CONF_ENABLE_SELF_LEARNING,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_OUTSIDE_WEATHER_ENTITY,
    CONF_HEATING_ACTIVE_SENSOR,
    CONF_FALLBACK_HEATING_RATE,
    CONF_FALLBACK_COOLING_RATE,
    CONF_HVAC_OFF_ON_TARGET,
    CONF_FALLBACK_TOLERANCE,
    CONF_OPPORTUNISTIC_HEATING,
    DEFAULT_MAX_MINUTES_PREHEAT,
    DEFAULT_MAX_MINUTES_COOLDOWN,
    DEFAULT_NEAR_DISTANCE,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_COOLING_RATE,
    DEFAULT_HVAC_OFF_ON_TARGET,
    DEFAULT_FALLBACK_TOLERANCE,
    DEFAULT_OPPORTUNISTIC_HEATING,
    DOMAIN,
)
from .zones import evaluate_zones
from .timeline import format_slot, get_current_and_next_slot
from .actions import calculate_next_action
from .preheat import calculate_preheat
from .cooldown import calculate_cooldown
from .heating_rate import get_effective_heating_rate
from .cooling_rate import get_effective_cooling_rate
from .helpers import (
    get_preset_temperature,
    get_resolved_outside_info,
    parse_time,
    safe_float,
)

_LOGGER = logging.getLogger(__name__)

EVAL_CACHE_TTL = 0.5  # Sekunden Gültigkeit für denselben Update-Zyklus


def invalidate_eval_cache(entry_data: dict | None) -> None:
    """Invalidiert den Kurzzeit-Evaluierungs-Cache eines Config Entrys."""
    if isinstance(entry_data, dict):
        entry_data.pop("_eval_cache", None)


def _safe_val(v, default):
    """Sichere Float-Hilfsfunktion (inkl. 0 und negativer Werte)."""
    return safe_float(v, default, allow_zero_or_negative=True)


def evaluate_state(hass, config_entry) -> tuple[str, dict | None, dict | None, dict | None, dict | None, dict, dict]:
    """Ermittelt alle Zustände, Zeitplan-Werte und Thermik-Berechnungen (mit Kurzzeit-Cache pro Update-Tick)."""
    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}) if hass else {}
    now_mono = time_mod.monotonic()

    cached = entry_data.get("_eval_cache") if isinstance(entry_data, dict) else None
    if cached is not None:
        cached_ts, cached_result = cached
        if (now_mono - cached_ts) < EVAL_CACHE_TTL:
            return cached_result

    now_dt = dt_util.now()

    options = config_entry.options
    data = config_entry.data
    self_learning_enabled = bool(
        options.get(
            CONF_ENABLE_SELF_LEARNING,
            data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
        )
    )

    raw_active_slot, active_date, raw_next_slot, next_date, raw_subsequent_slot = get_current_and_next_slot(
        hass, config_entry, now_dt
    )

    active_slot = format_slot(raw_active_slot, active_date)
    next_slot = format_slot(raw_next_slot, next_date)
    subsequent_slot = format_slot(raw_subsequent_slot)

    climate_entity = (
        config_entry.options.get(CONF_CLIMATE_ENTITY)
        or config_entry.data.get(CONF_CLIMATE_ENTITY, "")
    )

    zone_home_entity = (
        config_entry.options.get(CONF_ZONE_HOME_ENTITY)
        or config_entry.data.get(CONF_ZONE_HOME_ENTITY, "zone.home")
    )
    zone_away_near_entity = (
        config_entry.options.get(CONF_ZONE_AWAY_NEAR_ENTITY)
        or config_entry.data.get(CONF_ZONE_AWAY_NEAR_ENTITY)
    )

    near_distance = _safe_val(
        config_entry.options.get(CONF_NEAR_DISTANCE, config_entry.data.get(CONF_NEAR_DISTANCE)),
        DEFAULT_NEAR_DISTANCE,
    )

    zone_status = evaluate_zones(
        hass,
        zone_home_entity,
        zone_away_near_entity,
        near_distance=near_distance,
    )

    home_count = zone_status["home_count"]
    away_near_count = zone_status["away_near_count"]
    is_home = zone_status["is_home"]
    is_away_near = zone_status["is_away_near"]
    is_away = zone_status["is_away"]
    distances = zone_status["distances"]
    min_distance_km = zone_status["min_distance_km"]

    climate_state = hass.states.get(climate_entity) if climate_entity and hass else None
    attrs = climate_state.attributes if climate_state else {}

    real_measured_temp = attrs.get("external_temp_ema")
    if real_measured_temp is None:
        real_measured_temp = attrs.get("current_temperature", 20.0)

    try:
        real_measured_temp = float(real_measured_temp)
        if math.isnan(real_measured_temp) or math.isinf(real_measured_temp):
            real_measured_temp = 20.0
    except (ValueError, TypeError):
        real_measured_temp = 20.0

    fallback_tolerance = _safe_val(
        options.get(CONF_FALLBACK_TOLERANCE, data.get(CONF_FALLBACK_TOLERANCE)),
        DEFAULT_FALLBACK_TOLERANCE,
    )
    tolerance = _safe_val(attrs.get("tolerance"), fallback_tolerance)

    # Außentemperatur ermitteln (Sensor hat Vorrang vor Wetter-Entität; Wetter nutzt Attribut 'temperature')
    outside_sensor = options.get(CONF_OUTSIDE_TEMP_SENSOR, data.get(CONF_OUTSIDE_TEMP_SENSOR))
    outside_weather = options.get(CONF_OUTSIDE_WEATHER_ENTITY, data.get(CONF_OUTSIDE_WEATHER_ENTITY))
    outside_temp, active_outside_source = get_resolved_outside_info(hass, outside_sensor, outside_weather)

    # Konfigurierte Standard-Raten (Aufheizrate & Verlustrate in K/h)
    fallback_rate = _safe_val(
        options.get(
            CONF_FALLBACK_HEATING_RATE,
            data.get(CONF_FALLBACK_HEATING_RATE),
        ),
        DEFAULT_FALLBACK_HEATING_RATE,
    )
    fallback_cooling_rate = _safe_val(
        options.get(
            CONF_FALLBACK_COOLING_RATE,
            data.get(CONF_FALLBACK_COOLING_RATE),
        ),
        DEFAULT_FALLBACK_COOLING_RATE,
    )

    schedule_preset = active_slot.get("preset", "none") if active_slot else "none"

    active_temp = get_preset_temperature(climate_state, schedule_preset)
    next_preset_name = next_slot.get("preset") if next_slot else None
    next_temp = get_preset_temperature(climate_state, next_preset_name)

    preheat_enabled = bool(options.get(CONF_PREHEAT_ENABLED, data.get(CONF_PREHEAT_ENABLED, True)))
    cooldown_enabled = bool(options.get(CONF_COOLDOWN_ENABLED, data.get(CONF_COOLDOWN_ENABLED, True)))

    max_preheat = int(
        _safe_val(
            options.get(CONF_MAX_MINUTES_PREHEAT, data.get(CONF_MAX_MINUTES_PREHEAT)),
            DEFAULT_MAX_MINUTES_PREHEAT,
        )
    )
    max_cooldown = int(
        _safe_val(
            options.get(CONF_MAX_MINUTES_COOLDOWN, data.get(CONF_MAX_MINUTES_COOLDOWN)),
            DEFAULT_MAX_MINUTES_COOLDOWN,
        )
    )

    current_ref_temp = real_measured_temp if real_measured_temp is not None else active_temp

    # 1. Geltende Abkühlrate (K/h) ermitteln und Cooldown berechnen
    effective_cooling_rate = get_effective_cooling_rate(
        entry_data=entry_data,
        outside_temp=outside_temp,
        fallback_rate=fallback_cooling_rate,
        learning_enabled=self_learning_enabled,
    )

    target_cooldown_preset = (
        next_preset_name if (next_preset_name and next_preset_name != "none") else "eco"
    )

    cooldown = {
        "is_cooling_down": False,
        "start_time": None,
        "duration_minutes": 0,
        "effective_loss_rate_k_h": round(effective_cooling_rate, 3),
        "target_preset": target_cooldown_preset,
    }
    is_cooling_down = False
    cooldown_duration = 0

    if cooldown_enabled and next_slot:
        next_from_time_c = parse_time(next_slot.get("from"))
        if next_from_time_c and next_slot.get("date"):
            try:
                next_slot_start_c = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                    hour=next_from_time_c.hour, minute=next_from_time_c.minute, second=next_from_time_c.second, tzinfo=now_dt.tzinfo
                )
                if next_slot_start_c <= now_dt:
                    next_slot_start_c += timedelta(days=1)

                cooldown_slot_key = f"{next_slot.get('date')}_{next_slot.get('from')}"
                if entry_data.get("locked_cooldown_slot_key") != cooldown_slot_key:
                    entry_data["locked_cooldown_slot_key"] = cooldown_slot_key
                    entry_data["locked_cooldown_duration"] = None
                    entry_data["cooldown_latched"] = False

                is_cooldown_latched = entry_data.get("cooldown_latched", False)
                locked_c_dur = entry_data.get("locked_cooldown_duration")

                cooldown_result = calculate_cooldown(
                    now_dt=now_dt,
                    next_slot=next_slot,
                    current_temp=current_ref_temp,
                    next_temp=next_temp,
                    cooling_rate_k_h=effective_cooling_rate,
                    tolerance=tolerance,
                    max_minutes=max_cooldown,
                    parse_time_func=parse_time,
                )

                if current_ref_temp <= (next_temp + tolerance):
                    is_cooling_down = False
                    entry_data["cooldown_latched"] = False
                    entry_data["locked_cooldown_duration"] = None
                    cooldown = {
                        "is_cooling_down": False,
                        "start_time": cooldown_result.get("start_time") if cooldown_result else None,
                        "duration_minutes": 0,
                        "effective_loss_rate_k_h": round(effective_cooling_rate, 3),
                        "target_preset": target_cooldown_preset,
                    }
                    cooldown_duration = 0
                elif is_cooldown_latched and locked_c_dur is not None:
                    cooldown_start = next_slot_start_c - timedelta(minutes=locked_c_dur)
                    if now_dt < next_slot_start_c:
                        is_cooling_down = True
                        cooldown = {
                            "is_cooling_down": True,
                            "start_time": cooldown_start.strftime("%H:%M"),
                            "duration_minutes": locked_c_dur,
                            "effective_loss_rate_k_h": round(effective_cooling_rate, 3),
                            "target_preset": target_cooldown_preset,
                        }
                        cooldown_duration = locked_c_dur
                    else:
                        entry_data["cooldown_latched"] = False
                        entry_data["locked_cooldown_duration"] = None
                elif cooldown_result and cooldown_result.get("duration_minutes", 0) > 0 and current_ref_temp > next_temp:
                    calc_c_dur = cooldown_result.get("duration_minutes")
                    if cooldown_result.get("is_cooling_down"):
                        entry_data["locked_cooldown_duration"] = calc_c_dur
                        entry_data["cooldown_latched"] = True
                        is_cooling_down = True
                        cooldown_start = next_slot_start_c - timedelta(minutes=calc_c_dur)
                        cooldown = {
                            "is_cooling_down": True,
                            "start_time": cooldown_start.strftime("%H:%M"),
                            "duration_minutes": calc_c_dur,
                            "effective_loss_rate_k_h": round(effective_cooling_rate, 3),
                            "target_preset": target_cooldown_preset,
                        }
                        cooldown_duration = calc_c_dur
                    else:
                        cooldown = dict(cooldown_result)
                        cooldown["target_preset"] = target_cooldown_preset
                        is_cooling_down = False
                        cooldown_duration = cooldown.get("duration_minutes", 0)
            except Exception as e:
                _LOGGER.error("Fehler bei Cooldown-Berechnung (V2): %s", e)

    # 2. Geltende Aufheizrate (K/h) ermitteln und Preheat berechnen
    effective_heating_rate = get_effective_heating_rate(
        entry_data=entry_data,
        outside_temp=outside_temp,
        fallback_rate=fallback_rate,
        learning_enabled=self_learning_enabled,
    )

    preheat = {
        "is_preheating": False,
        "start_time": None,
        "duration_minutes": 0,
        "effective_rate_k_h": round(effective_heating_rate, 3),
    }
    is_preheat_needed = False
    preheat_duration = 0

    if preheat_enabled and next_slot:
        next_from_time = parse_time(next_slot.get("from"))
        if next_from_time and next_slot.get("date"):
            try:
                next_slot_start = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                    hour=next_from_time.hour, minute=next_from_time.minute, second=next_from_time.second, tzinfo=now_dt.tzinfo
                )
                if next_slot_start <= now_dt:
                    next_slot_start += timedelta(days=1)

                next_slot_key = f"{next_slot.get('date')}_{next_slot.get('from')}"
                if entry_data.get("locked_slot_key") != next_slot_key:
                    entry_data["locked_slot_key"] = next_slot_key
                    entry_data["locked_preheat_duration"] = None
                    entry_data["preheat_latched"] = False

                is_latched = entry_data.get("preheat_latched", False)
                locked_dur = entry_data.get("locked_preheat_duration")

                preheat_result, raw_preheat_needed = calculate_preheat(
                    now_dt=now_dt,
                    next_slot=next_slot,
                    current_temp=current_ref_temp,
                    next_temp=next_temp,
                    heating_rate_k_h=effective_heating_rate,
                    max_minutes=max_preheat,
                    parse_time_func=parse_time,
                )

                if current_ref_temp >= next_temp:
                    # Zieltemperatur für den nächsten Slot ist bereits erreicht!
                    # Preheat ist nicht erforderlich bzw. erfolgreich beendet.
                    is_preheat_needed = False
                    entry_data["preheat_latched"] = False
                    entry_data["locked_preheat_duration"] = None
                    preheat = {
                        "is_preheating": False,
                        "start_time": preheat_result.get("start_time") if preheat_result else None,
                        "duration_minutes": 0,
                        "effective_rate_k_h": round(effective_heating_rate, 3),
                    }
                    preheat_duration = 0
                elif is_latched and locked_dur is not None:
                    # Sobald Preheat gestartet wurde und Ziel noch nicht erreicht ist:
                    # bleibt aktiv bis zum Slot-Start oder bis Zieltemperatur erreicht ist
                    preheat_start = next_slot_start - timedelta(minutes=locked_dur)
                    if now_dt < next_slot_start:
                        is_preheat_needed = True
                        preheat = {
                            "is_preheating": True,
                            "start_time": preheat_start.strftime("%H:%M"),
                            "duration_minutes": locked_dur,
                            "effective_rate_k_h": round(effective_heating_rate, 3),
                        }
                        preheat_duration = locked_dur
                    else:
                        entry_data["preheat_latched"] = False
                        entry_data["locked_preheat_duration"] = None
                elif preheat_result and preheat_result.get("duration_minutes", 0) > 0 and next_temp > current_ref_temp:
                    calc_dur = preheat_result.get("duration_minutes")

                    if raw_preheat_needed or preheat_result.get("is_preheating"):
                        entry_data["locked_preheat_duration"] = calc_dur
                        entry_data["preheat_latched"] = True
                        locked_dur = calc_dur
                        is_preheat_needed = True
                        preheat_start = next_slot_start - timedelta(minutes=locked_dur)
                        preheat = {
                            "is_preheating": True,
                            "start_time": preheat_start.strftime("%H:%M"),
                            "duration_minutes": locked_dur,
                            "effective_rate_k_h": round(effective_heating_rate, 3),
                        }
                        preheat_duration = locked_dur
                    else:
                        preheat = preheat_result
                        is_preheat_needed = False
                        preheat_duration = preheat.get("duration_minutes", 0)
            except Exception as e:
                _LOGGER.error("Fehler bei Preheat-Berechnung (V2): %s", e)

    entry_data["was_preheating"] = is_preheat_needed
    entry_data["preheat_target_temp"] = next_temp

    preheat_start_dt = None
    if preheat and (preheat.get("is_preheating") or preheat_duration > 0):
        p_start_str = preheat.get("start_time")
        if p_start_str and next_slot and next_slot.get("date"):
            try:
                p_time = parse_time(p_start_str)
                if p_time:
                    preheat_start_dt = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                        hour=p_time.hour, minute=p_time.minute, second=p_time.second, tzinfo=now_dt.tzinfo
                    )
            except Exception:
                pass

    cooldown_start_dt = None
    if cooldown and (cooldown.get("is_cooling_down") or cooldown_duration > 0):
        c_start_str = cooldown.get("start_time")
        if c_start_str and next_slot and next_slot.get("date"):
            try:
                c_time = parse_time(c_start_str)
                if c_time:
                    cooldown_start_dt = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                        hour=c_time.hour, minute=c_time.minute, second=c_time.second, tzinfo=now_dt.tzinfo
                    )
            except Exception:
                pass

    base_preset = schedule_preset if schedule_preset != "none" else "home"

    if active_slot and active_slot.get("is_override"):
        preset = base_preset
    elif is_home:
        preset = base_preset
        if is_preheat_needed and next_preset_name and next_preset_name != "none":
            preset = next_preset_name
        elif is_cooling_down:
            preset = target_cooldown_preset
    elif is_away_near:
        if active_slot and active_slot.get("is_fallback"):
            preset = "sleep"
        else:
            preset = "eco"
    else:
        preset = "away"

    next_action = calculate_next_action(
        preheat_duration=preheat_duration,
        preheat_start_dt=preheat_start_dt,
        cooldown_duration=cooldown_duration,
        cooldown_start_dt=cooldown_start_dt,
        is_preheat_needed=is_preheat_needed,
        is_cooling_down=is_cooling_down,
        active_slot=active_slot,
        next_slot=next_slot,
        subsequent_slot=subsequent_slot,
        base_preset=base_preset,
        now_dt=now_dt,
    )

    delta_to_next = (
        round(next_temp - real_measured_temp, 2)
        if (next_temp is not None and real_measured_temp is not None)
        else None
    )

    debug_info = {
        "zones": {
            "home_entity": zone_home_entity,
            "home_count": home_count,
            "away_near_entity": zone_away_near_entity,
            "away_near_count": away_near_count,
            "is_home": is_home,
            "is_away_near": is_away_near,
            "is_away": is_away,
            "distances_km": distances,
            "min_distance_km": min_distance_km,
        },
        "temperatures": {
            "current": real_measured_temp,
            "active_target": active_temp,
            "next_target": next_temp,
            "delta_to_next": delta_to_next,
            "outside": outside_temp,
            "outside_source": active_outside_source,
        },
        "thermal_parameters": {
            "effective_rate_k_h": round(effective_heating_rate, 3),
            "learned_average": entry_data.get("average", fallback_rate),
            "heating_averages": entry_data.get("averages", {}),
            "effective_cooling_rate_k_h": round(effective_cooling_rate, 3),
            "learned_cooling_average": entry_data.get("cooling_average", fallback_cooling_rate),
            "cooling_averages": entry_data.get("cooling_averages", {}),
            "fallback_heating_rate": fallback_rate,
            "fallback_cooling_rate": fallback_cooling_rate,
            "tolerance": tolerance,
        },
        "settings": {
            "climate_entity": climate_entity,
            "outside_temp_sensor": outside_sensor,
            "outside_weather_entity": outside_weather,
            "heating_active_sensor": options.get(CONF_HEATING_ACTIVE_SENSOR, data.get(CONF_HEATING_ACTIVE_SENSOR)),
            "max_preheat_minutes": max_preheat,
            "max_cooldown_minutes": max_cooldown,
            "preheat_enabled": preheat_enabled,
            "cooldown_enabled": cooldown_enabled,
            "self_learning_enabled": self_learning_enabled,
            "near_distance": near_distance,
            "hvac_off_on_target": bool(options.get(CONF_HVAC_OFF_ON_TARGET, data.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET))),
            "fallback_tolerance": fallback_tolerance,
            "opportunistic_heating": bool(options.get(CONF_OPPORTUNISTIC_HEATING, data.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING))),
        },
        "evaluation": {
            "calculated_preheat_duration": preheat.get("duration_minutes", 0) if preheat else 0,
            "calculated_cooldown_duration": cooldown.get("duration_minutes", 0) if cooldown else 0,
            "is_preheating_active": is_preheat_needed,
            "is_cooldown_active": is_cooling_down,
            "selected_next_action": next_action,
            "final_state": preset,
        },
    }

    result = (preset, preheat, cooldown, active_slot, next_slot, next_action, debug_info)
    if isinstance(entry_data, dict):
        entry_data["_eval_cache"] = (now_mono, result)

    return result
