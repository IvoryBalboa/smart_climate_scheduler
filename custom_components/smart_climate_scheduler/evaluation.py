"""Zustands- und Thermik-Evaluierung für Smart Climate Scheduler (Version 4.0.0)."""
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
    CONF_KICKSTART_BOOST,
    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
    CONF_PREHEAT_IGNORES_AWAY,
    CONF_AWAY_PRESET,
    CONF_AWAY_NEAR_PRESET,
    DEFAULT_MAX_MINUTES_PREHEAT,
    DEFAULT_MAX_MINUTES_COOLDOWN,
    DEFAULT_NEAR_DISTANCE,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_COOLING_RATE,
    DEFAULT_HVAC_OFF_ON_TARGET,
    DEFAULT_FALLBACK_TOLERANCE,
    DEFAULT_OPPORTUNISTIC_HEATING,
    DEFAULT_KICKSTART_BOOST,
    DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
    DEFAULT_PREHEAT_IGNORES_AWAY,
    DEFAULT_AWAY_PRESET,
    DEFAULT_AWAY_NEAR_PRESET,
    DOMAIN,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
)
from .zones import evaluate_zones
from .timeline import format_slot, get_active_override, get_current_and_next_slot
from .actions import calculate_next_action
from .preheat import calculate_preheat
from .cooldown import calculate_cooldown
from .heating_rate import get_effective_heating_rate
from .cooling_rate import get_effective_cooling_rate
from .helpers import (
    get_climate_entities,
    get_custom_presets,
    get_effective_window_open,
    get_forecast_temperature_for_window,
    get_ha_language,
    get_preset_labels_map,
    get_preset_temperature,
    get_raw_window_open,
    get_resolved_outside_info,
    get_room_current_temperature,
    get_room_temp_sensor,
    get_window_delays,
    get_window_sensors,
    parse_time,
    resolve_preset_key,
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

    climate_entities = get_climate_entities(config_entry)
    climate_entity = climate_entities[0] if climate_entities else (
        options.get(CONF_CLIMATE_ENTITY)
        or data.get(CONF_CLIMATE_ENTITY, "")
    )
    custom_presets = get_custom_presets(config_entry)
    custom_labels = get_preset_labels_map(config_entry)

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

    measured_temp, room_temp_source = get_room_current_temperature(hass, config_entry, climate_entities)
    if measured_temp is None:
        real_measured_temp = 20.0
    else:
        real_measured_temp = measured_temp

    fallback_tolerance = _safe_val(
        options.get(CONF_FALLBACK_TOLERANCE, data.get(CONF_FALLBACK_TOLERANCE)),
        DEFAULT_FALLBACK_TOLERANCE,
    )
    tolerance = max(0.0, fallback_tolerance)

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

    def _extract_override_temp(slot: dict | None) -> float | None:
        if not isinstance(slot, dict) or not slot.get("is_override"):
            return None
        raw_t = slot.get("temperature")
        if raw_t is None:
            return None
        try:
            parsed_t = float(raw_t)
            if math.isnan(parsed_t) or math.isinf(parsed_t):
                return None
            return round(max(MIN_TARGET_TEMP, min(MAX_TARGET_TEMP, parsed_t)), 1)
        except (ValueError, TypeError):
            return None

    schedule_preset = active_slot.get("preset", "none") if active_slot else "none"
    if schedule_preset != "none":
        schedule_preset = resolve_preset_key(schedule_preset, config_entry)

    active_override_temp = _extract_override_temp(active_slot)
    if active_override_temp is not None:
        active_temp = active_override_temp
    else:
        active_temp = get_preset_temperature(
            climate_state, schedule_preset, config_entry=config_entry, custom_presets=custom_presets
        )
    next_preset_name = next_slot.get("preset") if next_slot else None
    if next_preset_name and next_preset_name != "none":
        next_preset_name = resolve_preset_key(next_preset_name, config_entry)
    next_override_temp = _extract_override_temp(next_slot)
    if next_override_temp is not None:
        next_temp = next_override_temp
    else:
        next_temp = get_preset_temperature(
            climate_state, next_preset_name, config_entry=config_entry, custom_presets=custom_presets
        )

    preheat_enabled = bool(options.get(CONF_PREHEAT_ENABLED, data.get(CONF_PREHEAT_ENABLED, True)))
    preheat_ignores_away = bool(
        options.get(CONF_PREHEAT_IGNORES_AWAY, data.get(CONF_PREHEAT_IGNORES_AWAY, DEFAULT_PREHEAT_IGNORES_AWAY))
    )
    cooldown_enabled = bool(options.get(CONF_COOLDOWN_ENABLED, data.get(CONF_COOLDOWN_ENABLED, True)))

    next_is_override = bool(next_slot and next_slot.get("is_override"))
    active_is_override = bool(active_slot and active_slot.get("is_override"))
    next_slot_preheat = True if next_is_override else (bool(next_slot.get("preheat", True)) if next_slot else True)
    active_slot_cooldown = (
        False
        if active_is_override
        else (
            True
            if (active_slot and active_slot.get("is_fallback"))
            else (bool(active_slot.get("cooldown", True)) if active_slot else True)
        )
    )
    effective_preheat_enabled = preheat_enabled and next_slot_preheat
    effective_cooldown_enabled = cooldown_enabled and active_slot_cooldown

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
        next_preset_name if (next_preset_name and next_preset_name != "none") else resolve_preset_key("eco", config_entry)
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

    if effective_cooldown_enabled and next_slot:
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

    elif isinstance(entry_data, dict):
        entry_data["cooldown_latched"] = False
        entry_data["locked_cooldown_duration"] = None

    use_weather_forecast = bool(
        options.get(
            CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
            data.get(CONF_USE_WEATHER_FORECAST_FOR_PREHEAT, DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT),
        )
    )

    # 2. Geltende Aufheizrate (K/h) ermitteln und Preheat berechnen
    preheat_outside_temp = outside_temp
    forecast_outside_temp: float | None = None
    forecast_used = False
    forecast_window_str: str | None = None

    if effective_preheat_enabled and next_slot and use_weather_forecast and outside_weather:
        next_from_time_pf = parse_time(next_slot.get("from"))
        if next_from_time_pf and next_slot.get("date"):
            try:
                next_slot_start_pf = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                    hour=next_from_time_pf.hour, minute=next_from_time_pf.minute, second=next_from_time_pf.second, tzinfo=now_dt.tzinfo
                )
                if next_slot_start_pf <= now_dt:
                    next_slot_start_pf += timedelta(days=1)

                window_start = next_slot_start_pf - timedelta(minutes=max_preheat)
                forecast_cache = entry_data.get("hourly_forecast_cache") if isinstance(entry_data, dict) else None
                fc_val = get_forecast_temperature_for_window(forecast_cache, window_start, next_slot_start_pf)
                if fc_val is not None:
                    forecast_outside_temp = fc_val
                    preheat_outside_temp = fc_val
                    forecast_used = True
                    forecast_window_str = f"{window_start.strftime('%H:%M')} - {next_slot_start_pf.strftime('%H:%M')}"
            except Exception as e:
                _LOGGER.debug("Fehler bei Ermittlung der Vorhersage für Vorheizen: %s", e)

    effective_heating_rate = get_effective_heating_rate(
        entry_data=entry_data,
        outside_temp=preheat_outside_temp,
        fallback_rate=fallback_rate,
        learning_enabled=self_learning_enabled,
    )

    preheat = {
        "is_preheating": False,
        "start_time": None,
        "duration_minutes": 0,
        "effective_rate_k_h": round(effective_heating_rate, 3),
        "forecast_temp": forecast_outside_temp,
        "forecast_used": forecast_used,
        "forecast_window": forecast_window_str,
    }
    is_preheat_needed = False
    is_preheat_holding = False
    preheat_duration = 0

    if effective_preheat_enabled and next_slot:
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
                    entry_data["preheat_target_reached"] = False

                is_latched = entry_data.get("preheat_latched", False)
                is_target_reached_hold = entry_data.get("preheat_target_reached", False)
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

                if is_latched and (is_target_reached_hold or current_ref_temp >= next_temp):
                    # Vorheizen war bereits aktiv und Zieltemperatur wurde vor Slot-Start erreicht:
                    # Vorheizen-Sensor & Lernen beenden, Ziel-Preset aber bis Slot-Start halten!
                    if now_dt < next_slot_start:
                        entry_data["preheat_target_reached"] = True
                        is_preheat_holding = True
                    else:
                        entry_data["preheat_latched"] = False
                        entry_data["preheat_target_reached"] = False
                        entry_data["locked_preheat_duration"] = None
                    is_preheat_needed = False
                    preheat = {
                        "is_preheating": False,
                        "start_time": None,
                        "duration_minutes": 0,
                        "effective_rate_k_h": round(effective_heating_rate, 3),
                        "target_reached_holding": is_preheat_holding,
                    }
                    preheat_duration = 0
                elif current_ref_temp >= next_temp:
                    # Zieltemperatur ist bereits vor Vorheiz-Beginn erreicht (Preheat war noch nicht gestartet)
                    is_preheat_needed = False
                    is_preheat_holding = False
                    entry_data["preheat_latched"] = False
                    entry_data["preheat_target_reached"] = False
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
                        entry_data["preheat_target_reached"] = False
                        entry_data["locked_preheat_duration"] = None
                elif preheat_result and preheat_result.get("duration_minutes", 0) > 0 and next_temp > current_ref_temp:
                    calc_dur = preheat_result.get("duration_minutes")

                    if raw_preheat_needed or preheat_result.get("is_preheating"):
                        entry_data["locked_preheat_duration"] = calc_dur
                        entry_data["preheat_latched"] = True
                        entry_data["preheat_target_reached"] = False
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
    elif isinstance(entry_data, dict):
        entry_data["preheat_latched"] = False
        entry_data["preheat_target_reached"] = False
        entry_data["locked_preheat_duration"] = None

    if is_preheat_holding:
        is_cooling_down = False
        cooldown_duration = 0
        if isinstance(cooldown, dict):
            cooldown["is_cooling_down"] = False
            cooldown["duration_minutes"] = 0

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

    is_active_override = bool(active_slot and active_slot.get("is_override"))
    if is_active_override and active_override_temp is not None and schedule_preset == "none":
        base_preset = "none"
    else:
        base_preset = (
            schedule_preset
            if schedule_preset != "none"
            else resolve_preset_key("home", config_entry)
        )

    if not is_active_override:
        # Zusätzliche Absicherung via get_active_override
        active_ov_id, active_ov_data = get_active_override(hass, config_entry, now_dt)
        if active_ov_data:
            is_active_override = True
            ov_raw_preset = active_ov_data.get("preset")
            if active_ov_data.get("temperature") is not None:
                try:
                    parsed_ov_t = float(active_ov_data["temperature"])
                    if not math.isnan(parsed_ov_t) and not math.isinf(parsed_ov_t):
                        active_override_temp = round(max(MIN_TARGET_TEMP, min(MAX_TARGET_TEMP, parsed_ov_t)), 1)
                        active_temp = active_override_temp
                except (ValueError, TypeError):
                    pass
            if ov_raw_preset and str(ov_raw_preset).strip().lower() != "none":
                base_preset = resolve_preset_key(ov_raw_preset, config_entry)
            elif active_override_temp is not None:
                base_preset = "none"
            if active_slot:
                active_slot["is_override"] = True
                active_slot["override_id"] = active_ov_id
                active_slot["preset"] = base_preset
                if active_override_temp is not None:
                    active_slot["temperature"] = active_override_temp

    next_is_override = bool(next_slot and next_slot.get("is_override"))

    preheat_controls_preset = is_preheat_needed or is_preheat_holding

    away_preset = (
        options.get(CONF_AWAY_PRESET)
        or data.get(CONF_AWAY_PRESET)
        or DEFAULT_AWAY_PRESET
    )
    away_near_preset = (
        options.get(CONF_AWAY_NEAR_PRESET)
        or data.get(CONF_AWAY_NEAR_PRESET)
        or DEFAULT_AWAY_NEAR_PRESET
    )
    away_preset = resolve_preset_key(away_preset, config_entry)
    away_near_preset = resolve_preset_key(away_near_preset, config_entry)

    if is_active_override:
        # 1. Aktueller Slot ist ein Override -> Anwesenheit wird umgangen
        preset = base_preset
    elif next_is_override and preheat_controls_preset and next_preset_name and next_preset_name != "none":
        # 2. Nächster Slot ist ein Override und Vorheizen (inkl. Haltephase bis Slot-Start) ist aktiv -> Anwesenheit wird umgangen
        preset = next_preset_name
    elif effective_preheat_enabled and preheat_ignores_away and preheat_controls_preset and next_preset_name and next_preset_name != "none":
        # 3. Vorheizen (inkl. Haltephase bei früh erreichtem Ziel) für geplanten Zeitplan-Slot aktiv: Überstimmt Abwesenheit (sowohl away als auch away_near),
        # damit das Haus bei Feierabend (auch wenn der Arbeitsplatz in away_near liegt) rechtzeitig warm ist!
        preset = next_preset_name
    elif is_home:
        # 4. Regulär Zuhause
        preset = base_preset
        if preheat_controls_preset and next_preset_name and next_preset_name != "none":
            preset = next_preset_name
        elif is_cooling_down:
            preset = target_cooldown_preset
    elif is_away_near:
        # 5. Nahe Abwesenheit (konfigurierbares Preset, Standard: eco)
        preset = away_near_preset
    else:
        # 6. Vollständige Abwesenheit (konfigurierbares Preset, Standard: away)
        preset = away_preset

    if preset != "none":
        preset = resolve_preset_key(preset, config_entry)

    lang = get_ha_language(hass)
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
        lang=lang,
        custom_labels=custom_labels,
    )

    delta_to_next = (
        round(next_temp - real_measured_temp, 2)
        if (next_temp is not None and real_measured_temp is not None)
        else None
    )

    raw_win_open, _ = get_raw_window_open(hass, config_entry, climate_entities)
    eff_win_open = get_effective_window_open(entry_data, hass, config_entry)
    open_delay_min, close_delay_min, win_pause_enabled = get_window_delays(config_entry)
    room_temp_sensor = get_room_temp_sensor(config_entry)
    window_sensors = get_window_sensors(config_entry)

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
            "room_temp_source": room_temp_source,
            "active_target": active_temp,
            "override_temperature": active_override_temp,
            "next_target": next_temp,
            "delta_to_next": delta_to_next,
            "outside": outside_temp,
            "outside_source": active_outside_source,
            "forecast_outside": forecast_outside_temp,
            "forecast_used": forecast_used,
            "forecast_window": forecast_window_str,
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
            "climate_entities": climate_entities,
            "room_temp_sensor": room_temp_sensor,
            "window_sensors": window_sensors,
            "window_open_delay_minutes": open_delay_min,
            "window_close_delay_minutes": close_delay_min,
            "window_pause_enabled": win_pause_enabled,
            "outside_temp_sensor": outside_sensor,
            "outside_weather_entity": outside_weather,
            "heating_active_sensor": options.get(CONF_HEATING_ACTIVE_SENSOR, data.get(CONF_HEATING_ACTIVE_SENSOR)),
            "max_preheat_minutes": max_preheat,
            "max_cooldown_minutes": max_cooldown,
            "preheat_enabled": preheat_enabled,
            "cooldown_enabled": cooldown_enabled,
            "self_learning_enabled": self_learning_enabled,
            "near_distance": near_distance,
            "away_preset": away_preset,
            "away_near_preset": away_near_preset,
            "hvac_off_on_target": bool(options.get(CONF_HVAC_OFF_ON_TARGET, data.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET))),
            "fallback_tolerance": fallback_tolerance,
            "opportunistic_heating": bool(options.get(CONF_OPPORTUNISTIC_HEATING, data.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING))),
            "kickstart_boost": max(0.0, _safe_val(options.get(CONF_KICKSTART_BOOST, data.get(CONF_KICKSTART_BOOST)), DEFAULT_KICKSTART_BOOST)),
            "use_weather_forecast_for_preheat": use_weather_forecast,
            "anomaly_detection_enabled": bool(options.get("anomaly_detection_enabled", data.get("anomaly_detection_enabled", True))),
            "anomaly_no_heat_minutes": int(options.get("anomaly_no_heat_minutes", data.get("anomaly_no_heat_minutes", 45)) or 0),
        },
        "evaluation": {
            "calculated_preheat_duration": preheat.get("duration_minutes", 0) if preheat else 0,
            "calculated_cooldown_duration": cooldown.get("duration_minutes", 0) if cooldown else 0,
            "is_preheating_active": is_preheat_needed,
            "is_preheat_holding": is_preheat_holding,
            "is_cooldown_active": is_cooling_down,
            "slot_preheat_allowed": next_slot_preheat,
            "slot_cooldown_allowed": active_slot_cooldown,
            "effective_preheat_enabled": effective_preheat_enabled,
            "effective_cooldown_enabled": effective_cooldown_enabled,
            "window_or_door_open": bool(eff_win_open or raw_win_open),
            "window_raw_open": bool(raw_win_open),
            "window_effective_open": bool(eff_win_open),
            "selected_next_action": next_action,
            "final_state": preset,
        },
    }

    result = (preset, preheat, cooldown, active_slot, next_slot, next_action, debug_info)
    if isinstance(entry_data, dict):
        entry_data["_eval_cache"] = (now_mono, result)

    return result
