"""Sensor-Plattform für Smart Climate Scheduler (v4.0.0)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback as ha_callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .anomaly import evaluate_and_update_anomaly
from .debug import SmartClimateSchedulerDebugSensor
from .evaluation import evaluate_state, invalidate_eval_cache
from .cooling_rate import (
    apply_cooling_ema,
    async_record_cooling_rate,
    calculate_step_cooling_rate,
)
from .heating_rate import (
    apply_step_ema,
    async_record_live_heating_rate,
    calculate_step_heating_rate,
)
from .helpers import (
    async_get_hourly_forecast,
    async_sync_entity_registry_disabled,
    async_write_ha_state_if_enabled,
    calculate_overall_average,
    clear_window_debounce_timer,
    evaluate_window_debounce,
    get_climate_entities,
    get_config_entry_slug,
    get_custom_presets,
    get_device_info,
    get_group_hvac_heating,
    get_ha_language,
    get_localized_slug_suffix,
    get_outside_temperature,
    get_preset_temperature,
    get_profiles_and_active,
    get_raw_window_open,
    get_room_current_temperature,
    get_room_temp_sensor,
    get_target_hvac_mode,
    get_window_delays,
    get_window_sensors,
    is_hass_starting,
    is_in_startup_grace,
    normalize_matrix,
    parse_time,
    register_startup_grace_callback,
    resolve_entry_entity_id,
    safe_float as _safe_float,
    unregister_startup_grace_callback,
)
from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_OUTSIDE_WEATHER_ENTITY,
    CONF_HEATING_ACTIVE_SENSOR,
    CONF_ENABLE_SELF_LEARNING,
    CONF_FALLBACK_HEATING_RATE,
    CONF_FALLBACK_COOLING_RATE,
    CONF_HVAC_OFF_ON_TARGET,
    CONF_FALLBACK_TOLERANCE,
    CONF_OPPORTUNISTIC_HEATING,
    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_COOLING_RATE,
    DEFAULT_HVAC_OFF_ON_TARGET,
    DEFAULT_FALLBACK_TOLERANCE,
    DEFAULT_OPPORTUNISTIC_HEATING,
    DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
    DOMAIN,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
)
from .storage import ClimateSchedulerStorage

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Sensor-Plattform über einen Config Entry ein."""
    storage = ClimateSchedulerStorage(hass, config_entry.entry_id)
    stored_data = await storage.async_get_data()

    hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})
    domain_data = hass.data[DOMAIN][config_entry.entry_id]

    fallback_rate = _safe_float(
        config_entry.options.get(
            CONF_FALLBACK_HEATING_RATE,
            config_entry.data.get(CONF_FALLBACK_HEATING_RATE),
        ),
        DEFAULT_FALLBACK_HEATING_RATE,
    )

    norm_averages = normalize_matrix(stored_data.get("averages", {}))
    domain_data["storage"] = storage
    domain_data["averages"] = norm_averages
    domain_data["average"] = calculate_overall_average(
        norm_averages, _safe_float(stored_data.get("average"), fallback_rate)
    )

    fallback_cooling_rate = _safe_float(
        config_entry.options.get(
            CONF_FALLBACK_COOLING_RATE,
            config_entry.data.get(CONF_FALLBACK_COOLING_RATE),
        ),
        DEFAULT_FALLBACK_COOLING_RATE,
    )
    norm_cooling = normalize_matrix(stored_data.get("cooling_averages", {}))
    domain_data["cooling_averages"] = norm_cooling
    domain_data["cooling_average"] = calculate_overall_average(
        norm_cooling,
        _safe_float(stored_data.get("cooling_average"), fallback_cooling_rate),
        already_normalized=True,
    )

    if "automation_enabled" not in domain_data:
        domain_data["automation_enabled"] = bool(stored_data.get("automation_enabled", False))
    if "active_session" not in domain_data:
        domain_data["active_session"] = None
    if "active_cooling_session" not in domain_data:
        domain_data["active_cooling_session"] = None
    if "last_heating_off_time" not in domain_data:
        domain_data["last_heating_off_time"] = None
    if "opportunistic_kickstart" not in domain_data:
        domain_data["opportunistic_kickstart"] = False
    if "opportunistic_kickstart_done" not in domain_data:
        domain_data["opportunistic_kickstart_done"] = False
    if "opportunistic_kickstart_target" not in domain_data:
        domain_data["opportunistic_kickstart_target"] = None

    main_sensor = SmartClimateSchedulerSensor(config_entry, hass=hass)
    heating_rate_sensor = SmartClimateSchedulerHeatingRateSensor(config_entry, hass=hass)
    cooling_rate_sensor = SmartClimateSchedulerCoolingRateSensor(config_entry, hass=hass)
    next_action_sensor = SmartClimateSchedulerNextActionSensor(config_entry, hass=hass)
    debug_sensor = SmartClimateSchedulerDebugSensor(config_entry, main_sensor, hass=hass)

    domain_data["main_sensor"] = main_sensor
    sensors = hass.data.setdefault(f"{DOMAIN}_sensors", [])
    sensors.extend([main_sensor, heating_rate_sensor, cooling_rate_sensor, next_action_sensor, debug_sensor])

    async_add_entities([main_sensor, heating_rate_sensor, cooling_rate_sensor, next_action_sensor, debug_sensor], True)

    # Entity-Registry Deaktivierung/Aktivierung für die Raten- und Binär-Sensoren synchronisieren
    await async_sync_entity_registry_disabled(hass, config_entry)

    climate_entities = get_climate_entities(config_entry)
    climate_entity = climate_entities[0] if climate_entities else (
        config_entry.options.get(CONF_CLIMATE_ENTITY)
        or config_entry.data.get(CONF_CLIMATE_ENTITY, "")
    ).strip()
    if not climate_entities and climate_entity:
        climate_entities = [climate_entity]

    room_temp_sensor = get_room_temp_sensor(config_entry)
    window_sensors = get_window_sensors(config_entry)

    outside_sensor = (
        config_entry.options.get(CONF_OUTSIDE_TEMP_SENSOR)
        or config_entry.data.get(CONF_OUTSIDE_TEMP_SENSOR)
    )

    outside_weather = (
        config_entry.options.get(CONF_OUTSIDE_WEATHER_ENTITY)
        or config_entry.data.get(CONF_OUTSIDE_WEATHER_ENTITY)
    )

    heating_active_sensor = (
        config_entry.options.get(CONF_HEATING_ACTIVE_SENSOR)
        or config_entry.data.get(CONF_HEATING_ACTIVE_SENSOR)
    )

    schedule_entity = config_entry.data.get("schedule_entity")

    def _is_burner_active() -> bool:
        """Prüft, ob Heizen aktiv ist: Brenner 'on' UND mindestens ein Thermostat hvac_action == 'heating'."""
        if not hass:
            return False

        # 1. Mindestens ein Thermostat der Gruppe muss aktiv heizen
        _, thermostat_heating, _ = get_group_hvac_heating(hass, climate_entities)
        if not thermostat_heating:
            return False

        # 2. Brenner-Entität muss 'on' sein (falls konfiguriert)
        if heating_active_sensor:
            act_state = hass.states.get(heating_active_sensor)
            return bool(act_state and act_state.state == "on")

        # Falls kein separater Brenner-Sensor konfiguriert ist, gilt der Thermostat-Zustand
        return thermostat_heating

    def _get_current_temp() -> float:
        """Liest die aktuelle Raumtemperatur (externer Sensor vor Mittelwert der Thermostate)."""
        temp, _ = get_room_current_temperature(hass, config_entry, climate_entities)
        return float(temp) if temp is not None else 20.0

    def _get_outside_temp() -> float | None:
        """Liest die Außentemperatur (Sensor hat Vorrang vor Wetter-Entität)."""
        return get_outside_temperature(hass, outside_sensor, outside_weather)

    def _is_preheating_active() -> bool:
        """Prüft, ob aktuell die Vorheizphase (Preheat) aktiv ist (V2.3.2: Messung ausschließlich beim Vorheizen)."""
        try:
            _, preheat, _, _, _, _, _ = evaluate_state(hass, config_entry)
            return bool(preheat and preheat.get("is_preheating", False))
        except Exception:
            return False

    # Live-Berechnung der Aufheizrate & Lernen in die Außentemperatur-Matrix (ausschließlich beim Vorheizen, V2.3.2)
    async def async_check_heating_session(event=None):
        now_dt = dt_util.now()
        is_burner_on = _is_burner_active()
        is_preheating = _is_preheating_active()
        is_heating = is_burner_on and is_preheating
        session = domain_data.get("active_session")

        fallback_r = _safe_float(
            config_entry.options.get(
                CONF_FALLBACK_HEATING_RATE,
                config_entry.data.get(CONF_FALLBACK_HEATING_RATE),
            ),
            DEFAULT_FALLBACK_HEATING_RATE,
        )
        learning_enabled = bool(
            config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )

        if is_heating:
            domain_data["last_heating_off_time"] = None
            if domain_data.get("active_cooling_session") is not None:
                domain_data["active_cooling_session"] = None

        if is_heating and session is None:
            # Brenner eingeschaltet -> Live-Session mit Schritt-Tracking starten
            start_t = _get_current_temp()
            domain_data["active_session"] = {
                "start_time": now_dt,
                "start_temp": start_t,
                "last_step_time": now_dt,
                "last_step_temp": start_t,
                "outside_start": _get_outside_temp(),
                "live_rate": 0.0,
                "last_recorded_rate": None,
            }
            _LOGGER.debug(
                "Smart Climate Scheduler [%s]: Brenner 'on' -> Live-Messung gestartet (Temp: %.2f°C)",
                config_entry.entry_id,
                start_t,
            )
            async_write_ha_state_if_enabled(heating_rate_sensor)

        elif is_heating and session is not None:
            # Brenner ist aktiv ('on') -> Differenziellen Schritt bei mindestens 0.10°C Anstieg und 300s (5 Min) prüfen
            curr_temp = _get_current_temp()
            last_step_time = session.get("last_step_time") or session.get("start_time")
            last_step_temp = session.get("last_step_temp", session.get("start_temp", curr_temp))
            out_temp = _get_outside_temp()
            if out_temp is None:
                out_temp = session.get("outside_start")

            step_rate, is_valid_step = calculate_step_heating_rate(
                last_time=last_step_time,
                last_temp=last_step_temp,
                curr_time=now_dt,
                curr_temp=curr_temp,
                min_seconds=300,
                min_temp_delta=0.01,
            )

            if is_valid_step and step_rate is not None:
                prev_live = session.get("live_rate")
                smoothed_rate = apply_step_ema(
                    step_rate,
                    prev_live if (prev_live and prev_live > 0) else None,
                )
                session["live_rate"] = smoothed_rate
                session["last_step_time"] = now_dt
                session["last_step_temp"] = curr_temp

                if smoothed_rate > 0 and smoothed_rate != session.get("last_recorded_rate"):
                    session["last_recorded_rate"] = smoothed_rate
                    await async_record_live_heating_rate(
                        hass=hass,
                        entry_id=config_entry.entry_id,
                        live_rate=smoothed_rate,
                        outside_temp=out_temp,
                        entry_data=domain_data,
                        storage=storage,
                        fallback_rate=fallback_r,
                        learning_enabled=learning_enabled,
                    )

                async_write_ha_state_if_enabled(heating_rate_sensor)
                async_write_ha_state_if_enabled(main_sensor)

        elif not is_heating and session is not None:
            # Brenner ausgeschaltet ('off') -> Ggf. noch offenen letzten Teilschritt verbuchen
            last_step_time = session.get("last_step_time") or session.get("start_time")
            last_step_temp = session.get("last_step_temp", session.get("start_temp", 20.0))
            end_temp = _get_current_temp()
            out_temp = _get_outside_temp()
            if out_temp is None:
                out_temp = session.get("outside_start")

            step_rate, is_valid_step = calculate_step_heating_rate(
                last_time=last_step_time,
                last_temp=last_step_temp,
                curr_time=now_dt,
                curr_temp=end_temp,
                min_seconds=180,
                min_temp_delta=0.01,
            )
            if is_valid_step and step_rate is not None:
                prev_live = session.get("live_rate")
                final_rate = apply_step_ema(
                    step_rate,
                    prev_live if (prev_live and prev_live > 0) else None,
                )
                if final_rate > 0 and final_rate != session.get("last_recorded_rate"):
                    await async_record_live_heating_rate(
                        hass=hass,
                        entry_id=config_entry.entry_id,
                        live_rate=final_rate,
                        outside_temp=out_temp,
                        entry_data=domain_data,
                        storage=storage,
                        fallback_rate=fallback_r,
                        learning_enabled=learning_enabled,
                    )

            # Bei längeren Heizphasen (>= 30 Min) zusätzlich Gesamtrate der Session auswerten
            start_t = session.get("start_time")
            start_val = session.get("start_temp")
            if start_t and start_val is not None:
                tot_seconds = (now_dt - start_t).total_seconds()
                tot_delta = end_temp - start_val
                if tot_seconds >= 1800 and tot_delta >= 0.05:
                    overall_session_rate = round(tot_delta / (tot_seconds / 3600.0), 3)
                    if 0.10 <= overall_session_rate <= 3.0:
                        await async_record_live_heating_rate(
                            hass=hass,
                            entry_id=config_entry.entry_id,
                            live_rate=overall_session_rate,
                            outside_temp=out_temp,
                            entry_data=domain_data,
                            storage=storage,
                            fallback_rate=fallback_r,
                            learning_enabled=learning_enabled,
                        )

            domain_data["active_session"] = None
            domain_data["last_heating_off_time"] = now_dt
            async_write_ha_state_if_enabled(heating_rate_sensor)
            async_write_ha_state_if_enabled(main_sensor)

        elif not is_heating and session is None:
            # Brenner ist aus und keine Heiz-Session aktiv (kein unnötiger State-Write)
            if domain_data.get("last_heating_off_time") is None:
                domain_data["last_heating_off_time"] = now_dt

        # Abkühlraten-Messung: Nur wenn Heizung seit >= 30 Minuten aus ist (Schutz vor Restwärme)
        if not is_heating and learning_enabled:
            last_off = domain_data.get("last_heating_off_time")
            if last_off is not None and (now_dt - last_off).total_seconds() >= 1800:
                cooling_session = domain_data.get("active_cooling_session")
                curr_temp = _get_current_temp()
                out_temp = _get_outside_temp()

                if cooling_session is None:
                    # Neue Abkühl-Phase starten
                    domain_data["active_cooling_session"] = {
                        "start_time": now_dt,
                        "start_temp": curr_temp,
                        "last_step_time": now_dt,
                        "last_step_temp": curr_temp,
                        "outside_start": out_temp,
                        "live_rate": 0.0,
                    }
                    _LOGGER.debug(
                        "Smart Climate Scheduler [%s]: Heizung >= 30 Min aus -> Abkühl-Messung gestartet (Temp: %.2f°C)",
                        config_entry.entry_id,
                        curr_temp,
                    )
                    async_write_ha_state_if_enabled(cooling_rate_sensor)
                else:
                    last_step_time = cooling_session.get("last_step_time") or cooling_session.get("start_time")
                    last_step_temp = cooling_session.get("last_step_temp", cooling_session.get("start_temp", curr_temp))
                    if out_temp is None:
                        out_temp = cooling_session.get("outside_start")

                    if curr_temp > last_step_temp:
                        # Raum erwärmt sich (Sonne/Kochen etc.) -> Live-Rate sofort auf 0.0 K/h und Referenz nachziehen
                        cooling_session["live_rate"] = 0.0
                        cooling_session["last_step_temp"] = curr_temp
                        cooling_session["last_step_time"] = now_dt
                        async_write_ha_state_if_enabled(cooling_rate_sensor)
                    else:
                        step_rate, is_valid_step = calculate_step_cooling_rate(
                            last_time=last_step_time,
                            last_temp=last_step_temp,
                            curr_time=now_dt,
                            curr_temp=curr_temp,
                            min_seconds=900,
                            min_temp_drop=0.01,
                            max_plausible_rate=1.5,
                        )
                        if is_valid_step and step_rate is not None:
                            prev_live = cooling_session.get("live_rate")
                            smoothed_rate = apply_cooling_ema(
                                step_rate,
                                prev_live if (prev_live and prev_live > 0) else None,
                            )
                            cooling_session["live_rate"] = smoothed_rate
                            cooling_session["last_step_time"] = now_dt
                            cooling_session["last_step_temp"] = curr_temp

                            fallback_c = _safe_float(
                                config_entry.options.get(
                                    CONF_FALLBACK_COOLING_RATE,
                                    config_entry.data.get(CONF_FALLBACK_COOLING_RATE),
                                ),
                                DEFAULT_FALLBACK_COOLING_RATE,
                            )
                            await async_record_cooling_rate(
                                hass=hass,
                                entry_id=config_entry.entry_id,
                                rate=smoothed_rate,
                                outside_temp=out_temp,
                                entry_data=domain_data,
                                storage=storage,
                                fallback_rate=fallback_c,
                                learning_enabled=learning_enabled,
                            )
                            async_write_ha_state_if_enabled(cooling_rate_sensor)
                            async_write_ha_state_if_enabled(main_sensor)

    def _async_update_all_entities():
        """Triggert ein sofortiges Update aller registrierten Entitäten dieses Entrys."""
        invalidate_eval_cache(domain_data)
        for ent in hass.data.get(f"{DOMAIN}_sensors", []):
            if getattr(ent, "config_entry", None) and ent.config_entry.entry_id == config_entry.entry_id:
                async_write_ha_state_if_enabled(ent)

    def _get_heating_flags() -> tuple[bool, bool, bool]:
        hvac_off_on_target = bool(
            config_entry.options.get(
                CONF_HVAC_OFF_ON_TARGET,
                config_entry.data.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET),
            )
        )
        opportunistic_heating = bool(
            config_entry.options.get(
                CONF_OPPORTUNISTIC_HEATING,
                config_entry.data.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING),
            )
        )
        is_heating_active = False
        if heating_active_sensor:
            in_grace = is_in_startup_grace(hass)
            st = hass.states.get(heating_active_sensor)
            if not st:
                if in_grace:
                    if domain_data.get("_last_burner_debug_missing") != heating_active_sensor:
                        domain_data["_last_burner_debug_missing"] = heating_active_sensor
                        _LOGGER.debug(
                            "Smart Climate Scheduler [%s]: Heizungs-Sensor '%s' während Start-Karenzzeit noch nicht vorhanden",
                            config_entry.title or config_entry.entry_id,
                            heating_active_sensor,
                        )
                else:
                    domain_data.pop("_last_burner_debug_missing", None)
                    if domain_data.get("_last_burner_missing") != heating_active_sensor:
                        domain_data["_last_burner_missing"] = heating_active_sensor
                        _LOGGER.warning(
                            "Smart Climate Scheduler [%s]: Konfigurierter Heizungs-Sensor '%s' existiert nicht in Home Assistant",
                            config_entry.title or config_entry.entry_id,
                            heating_active_sensor,
                        )
            elif st.state in ("unavailable", "unknown"):
                if in_grace:
                    if domain_data.get("_last_burner_debug_state") != st.state:
                        domain_data["_last_burner_debug_state"] = st.state
                        _LOGGER.debug(
                            "Smart Climate Scheduler [%s]: Heizungs-Sensor '%s' während Start-Karenzzeit noch nicht verfügbar (Status: '%s')",
                            config_entry.title or config_entry.entry_id,
                            heating_active_sensor,
                            st.state,
                        )
                else:
                    domain_data.pop("_last_burner_debug_state", None)
                    if domain_data.get("_last_burner_state") != st.state:
                        domain_data["_last_burner_state"] = st.state
                        _LOGGER.warning(
                            "Smart Climate Scheduler [%s]: Heizungs-Sensor '%s' ist nicht verfügbar (Status: '%s')",
                            config_entry.title or config_entry.entry_id,
                            heating_active_sensor,
                            st.state,
                        )
            else:
                domain_data.pop("_last_burner_state", None)
                domain_data.pop("_last_burner_missing", None)
                domain_data.pop("_last_burner_debug_state", None)
                domain_data.pop("_last_burner_debug_missing", None)
                if st.state.lower() in ("on", "true", "active", "heat", "heating"):
                    is_heating_active = True
        return hvac_off_on_target, opportunistic_heating, is_heating_active

    async def _async_window_debounce_fired() -> None:
        invalidate_eval_cache(domain_data)
        await async_apply_schedule_to_climate()
        evaluate_and_update_anomaly(hass, config_entry, domain_data)
        _async_update_all_entities()

    def _schedule_window_debounce_timer(delay_sec: float):
        loop = getattr(hass, "loop", None)
        call_later = getattr(loop, "call_later", None)
        if not callable(call_later):
            return None

        @ha_callback
        def _on_window_timer() -> None:
            w_st = domain_data.get("window_state")
            if isinstance(w_st, dict):
                w_st["timer_handle"] = None
            if hasattr(hass, "async_create_task"):
                hass.async_create_task(_async_window_debounce_fired())

        return call_later(delay_sec, _on_window_timer)

    config_entry.async_on_unload(lambda: clear_window_debounce_timer(domain_data))

    # Automatik: Universelle Direkttemperatur-Steuerung, Gruppensteuerung, Fenster-Entprellung & Zweipunkt-Regelung
    async def async_apply_schedule_to_climate(event=None):
        entry_name = config_entry.title or config_entry.entry_id
        if is_hass_starting(hass):
            if not domain_data.get("_startup_apply_deferred_logged"):
                domain_data["_startup_apply_deferred_logged"] = True
                _LOGGER.debug(
                    "Smart Climate Scheduler [%s]: Erste aktive Thermostat-Schaltung wartet auf Abschluss des Home-Assistant-Starts",
                    entry_name,
                )
            return
        domain_data.pop("_startup_apply_deferred_logged", None)

        hvac_off_on_target, opportunistic_heating, is_heating_active = _get_heating_flags()

        if not domain_data.get("automation_enabled", False):
            domain_data["opportunistic_kickstart"] = False
            domain_data["opportunistic_kickstart_done"] = False
            domain_data["opportunistic_kickstart_target"] = None
            clear_window_debounce_timer(domain_data)
            return

        available_devices: list[tuple[str, Any]] = []
        unavailable_now: dict[str, str] = {}
        for cl_id in climate_entities:
            st_obj = hass.states.get(cl_id)
            if not st_obj or st_obj.state in ("unavailable", "unknown", "None", None):
                unavailable_now[cl_id] = str(st_obj.state) if st_obj else "nicht gefunden"
            else:
                available_devices.append((cl_id, st_obj))

        prev_warn_map = domain_data.setdefault("_last_unavail_warn_map", {})
        prev_debug_map = domain_data.setdefault("_last_unavail_debug_map", {})
        for cl_id in list(prev_warn_map.keys()):
            if cl_id not in unavailable_now:
                prev_warn_map.pop(cl_id, None)
        for cl_id in list(prev_debug_map.keys()):
            if cl_id not in unavailable_now:
                prev_debug_map.pop(cl_id, None)

        in_grace = is_in_startup_grace(hass)
        for cl_id, cur_state in unavailable_now.items():
            if in_grace:
                if prev_debug_map.get(cl_id) != cur_state:
                    prev_debug_map[cl_id] = cur_state
                    _LOGGER.debug(
                        "Smart Climate Scheduler [%s]: Thermostat '%s' während Start-Karenzzeit noch nicht verfügbar (Status: '%s')",
                        entry_name,
                        cl_id,
                        cur_state,
                    )
            else:
                prev_debug_map.pop(cl_id, None)
                if prev_warn_map.get(cl_id) != cur_state:
                    prev_warn_map[cl_id] = cur_state
                    _LOGGER.warning(
                        "Smart Climate Scheduler [%s]: Thermostat '%s' ist nicht verfügbar (Status: '%s')",
                        entry_name,
                        cl_id,
                        cur_state,
                    )

        if not available_devices:
            return

        raw_win_open, _ = get_raw_window_open(hass, config_entry, climate_entities)
        open_delay_min, close_delay_min, win_pause_enabled = get_window_delays(config_entry)
        win_debounce = evaluate_window_debounce(
            domain_data,
            raw_open=raw_win_open,
            open_delay_seconds=open_delay_min * 60,
            close_delay_seconds=close_delay_min * 60,
            now_dt=dt_util.now(),
            schedule_fn=_schedule_window_debounce_timer,
        )
        effective_win_open = bool(win_debounce.get("effective_open", False))
        window_or_door_open = effective_win_open
        if win_debounce.get("transition") is not None:
            invalidate_eval_cache(domain_data)

        custom_presets = get_custom_presets(config_entry)
        target_preset, _, _, _, _, _, _ = evaluate_state(hass, config_entry)
        _, primary_state = available_devices[0]

        current_temp, _ = get_room_current_temperature(hass, config_entry, climate_entities)
        target_temp = get_preset_temperature(
            primary_state,
            target_preset,
            config_entry=config_entry,
            custom_presets=custom_presets,
        )
        base_target_temp = round(
            max(
                MIN_TARGET_TEMP,
                min(MAX_TARGET_TEMP, float(target_temp if target_temp is not None else 20.0)),
            ),
            1,
        )

        # Aktive Fenster-Pause (wenn effektiver Zustand nach open_delay_min offen ist & window_pause_enabled)
        if effective_win_open and win_pause_enabled:
            was_kickstart = bool(domain_data.get("opportunistic_kickstart", False))
            domain_data["opportunistic_kickstart"] = False
            domain_data["opportunistic_kickstart_done"] = False

            w_state = domain_data.setdefault("window_state", {})
            saved_modes = w_state.setdefault("saved_hvac_modes", {})
            for cl_id, st_obj in available_devices:
                if was_kickstart:
                    attrs = st_obj.attributes or {}
                    cur_set = attrs.get("temperature")
                    needs_restore = True
                    if cur_set is not None:
                        try:
                            if abs(float(cur_set) - base_target_temp) < 0.05:
                                needs_restore = False
                        except (ValueError, TypeError):
                            pass
                    if needs_restore:
                        try:
                            await hass.services.async_call(
                                "climate",
                                "set_temperature",
                                service_data={"temperature": base_target_temp},
                                target={"entity_id": cl_id},
                                blocking=False,
                            )
                        except Exception as err:
                            _LOGGER.error(
                                "Smart Climate Scheduler [%s]: Fehler beim Zurücksetzen der Kickstart-Temperatur auf '%s': %s",
                                entry_name,
                                cl_id,
                                err,
                            )
                cur_mode = str(st_obj.state or "").strip().lower()
                if cur_mode != "off":
                    if cl_id not in saved_modes:
                        saved_modes[cl_id] = cur_mode
                    _LOGGER.info(
                        "Automatik Fenster-Pause [%s]: Fenster offen (nach %d Min Verzögerung) -> Schalte '%s' auf 'off' (vorher '%s')",
                        entry_name,
                        open_delay_min,
                        cl_id,
                        cur_mode,
                    )
                    try:
                        await hass.services.async_call(
                            "climate",
                            "set_hvac_mode",
                            service_data={"hvac_mode": "off"},
                            target={"entity_id": cl_id},
                            blocking=False,
                        )
                    except Exception as err:
                        _LOGGER.error(
                            "Smart Climate Scheduler [%s]: Fehler beim Fenster-Pause-Ausschalten ('off') von '%s': %s",
                            entry_name,
                            cl_id,
                            err,
                        )
            return

        # Zyklus-Schutzmerker zurücksetzen bei Brenner-Aus, Fensteröffnung, Sollwerterhöhung oder Zielerreichung
        prev_kick_target = domain_data.get("opportunistic_kickstart_target")
        if prev_kick_target is not None and base_target_temp > prev_kick_target:
            domain_data["opportunistic_kickstart_done"] = False

        if not opportunistic_heating or not is_heating_active or window_or_door_open:
            domain_data["opportunistic_kickstart_done"] = False
            if not opportunistic_heating or not is_heating_active:
                domain_data["opportunistic_kickstart_target"] = None
        elif current_temp is not None and current_temp >= base_target_temp:
            domain_data["opportunistic_kickstart_done"] = False

        any_heating_action = any(
            (st_obj.attributes or {}).get("hvac_action") == "heating"
            for _, st_obj in available_devices
        )

        if domain_data.get("is_setting_hvac", False):
            return

        w_state = domain_data.get("window_state")
        saved_hvac_modes: dict[str, str] = (
            w_state.get("saved_hvac_modes", {}) if isinstance(w_state, dict) else {}
        )

        fallback_tol = _safe_float(
            config_entry.options.get(
                CONF_FALLBACK_TOLERANCE,
                config_entry.data.get(CONF_FALLBACK_TOLERANCE),
            ),
            DEFAULT_FALLBACK_TOLERANCE,
            allow_zero_or_negative=True,
        )
        tolerance = max(0.0, fallback_tol)
        boosted_temp = round(min(MAX_TARGET_TEMP, base_target_temp + max(0.1, tolerance)), 1)

        async def _async_sync_direct_temp(cl_id: str, st_obj: Any, desired_t: float) -> None:
            attrs = st_obj.attributes or {}
            cur_set = attrs.get("temperature")
            needs_set = True
            if cur_set is not None:
                try:
                    if abs(float(cur_set) - desired_t) < 0.05:
                        needs_set = False
                except (ValueError, TypeError):
                    pass
            if not needs_set:
                return
            _LOGGER.info(
                "Automatik [%s]: Setze Zieltemperatur %.1f °C (bisher: %s °C, Preset: '%s')",
                cl_id,
                desired_t,
                cur_set,
                target_preset,
            )
            try:
                await hass.services.async_call(
                    "climate",
                    "set_temperature",
                    service_data={"temperature": desired_t},
                    target={"entity_id": cl_id},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.error(
                    "Smart Climate Scheduler [%s]: Fehler beim Setzen der Zieltemperatur %.1f auf '%s': %s",
                    entry_name,
                    desired_t,
                    cl_id,
                    err,
                )

        async def _async_set_direct_hvac(cl_id: str, mode_str: str, reason_text: str) -> None:
            _LOGGER.info(
                "Automatik [%s]: %s -> Schalte Thermostat auf '%s'",
                cl_id,
                reason_text,
                mode_str,
            )
            try:
                await hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    service_data={"hvac_mode": mode_str},
                    target={"entity_id": cl_id},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.error(
                    "Smart Climate Scheduler [%s]: Fehler beim Schalten ('%s') von '%s': %s",
                    entry_name,
                    mode_str,
                    cl_id,
                    err,
                )

        # Aktiven opportunistischen Kickstart abschließen oder abbrechen
        kickstart_active = bool(domain_data.get("opportunistic_kickstart", False))
        if kickstart_active:
            if any_heating_action:
                domain_data["opportunistic_kickstart"] = False
                domain_data["opportunistic_kickstart_done"] = True
                domain_data["opportunistic_kickstart_target"] = base_target_temp
                kickstart_active = False
            elif (
                not opportunistic_heating
                or not is_heating_active
                or window_or_door_open
                or (current_temp is not None and current_temp >= base_target_temp)
            ):
                domain_data["opportunistic_kickstart"] = False
                domain_data["opportunistic_kickstart_done"] = False
                kickstart_active = False

        if hvac_off_on_target and current_temp is not None:
            if current_temp >= base_target_temp:
                domain_data["two_point_target_reached"] = True
                domain_data["opportunistic_kickstart"] = False
                saved_hvac_modes.clear()
                domain_data["is_setting_hvac"] = True
                try:
                    for cl_id, st_obj in available_devices:
                        cur_act = (st_obj.attributes or {}).get("hvac_action")
                        if st_obj.state != "off" and cur_act != "heating":
                            await _async_set_direct_hvac(
                                cl_id,
                                "off",
                                f"Ist ({current_temp:.1f} °C) >= Soll ({base_target_temp:.1f} °C)",
                            )
                        elif st_obj.state != "off":
                            await _async_sync_direct_temp(cl_id, st_obj, base_target_temp)
                finally:
                    hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))
            elif current_temp < (base_target_temp - tolerance) or (
                opportunistic_heating and is_heating_active and current_temp < base_target_temp
            ):
                if window_or_door_open:
                    domain_data["opportunistic_kickstart"] = False
                    domain_data["is_setting_hvac"] = True
                    try:
                        for cl_id, st_obj in available_devices:
                            if st_obj.state != "off":
                                await _async_sync_direct_temp(cl_id, st_obj, base_target_temp)
                    finally:
                        hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))
                else:
                    domain_data["two_point_target_reached"] = False
                    is_opp_deadband = (
                        opportunistic_heating
                        and is_heating_active
                        and current_temp < base_target_temp
                        and current_temp >= (base_target_temp - tolerance)
                    )
                    domain_data["is_setting_hvac"] = True
                    try:
                        for cl_id, st_obj in available_devices:
                            attrs = st_obj.attributes or {}
                            cur_act = attrs.get("hvac_action")
                            saved_mode = saved_hvac_modes.pop(cl_id, None)
                            target_mode = saved_mode or get_target_hvac_mode(st_obj)
                            if st_obj.state == "off":
                                await _async_set_direct_hvac(
                                    cl_id,
                                    target_mode,
                                    f"Ist ({current_temp:.1f} °C) < Schwelle ({base_target_temp - tolerance:.1f} °C)",
                                )
                            desired_temp = base_target_temp
                            if kickstart_active:
                                desired_temp = boosted_temp
                            elif (
                                is_opp_deadband
                                and not domain_data.get("opportunistic_kickstart_done", False)
                                and (st_obj.state == "off" or cur_act == "idle")
                            ):
                                desired_temp = boosted_temp
                                domain_data["opportunistic_kickstart"] = True
                                domain_data["opportunistic_kickstart_target"] = base_target_temp
                            await _async_sync_direct_temp(cl_id, st_obj, desired_temp)
                    finally:
                        hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))
            else:
                # Zwischen (target - tol) und target ohne Mitheizbedarf: gespeicherten Fenster-Modus wiederherstellen & Temperatur abgleichen
                domain_data["is_setting_hvac"] = True
                try:
                    for cl_id, st_obj in available_devices:
                        saved_mode = saved_hvac_modes.pop(cl_id, None)
                        if saved_mode and st_obj.state == "off" and not window_or_door_open:
                            await _async_set_direct_hvac(cl_id, saved_mode, "Fenster wieder geschlossen")
                        if st_obj.state != "off" or saved_mode:
                            await _async_sync_direct_temp(cl_id, st_obj, base_target_temp)
                finally:
                    hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))
        else:
            # Ohne Zweipunkt-Abschaltung: gewünschte Temperatur und Heizmodus direkt synchronisieren
            domain_data["is_setting_hvac"] = True
            try:
                for cl_id, st_obj in available_devices:
                    attrs = st_obj.attributes or {}
                    cur_act = attrs.get("hvac_action")
                    saved_mode = saved_hvac_modes.pop(cl_id, None)
                    target_mode = saved_mode or get_target_hvac_mode(st_obj)
                    if st_obj.state == "off" and not window_or_door_open:
                        await _async_set_direct_hvac(cl_id, target_mode, "Zeitplan aktiv")

                    desired_temp = base_target_temp
                    if kickstart_active:
                        desired_temp = boosted_temp
                    elif (
                        opportunistic_heating
                        and is_heating_active
                        and not window_or_door_open
                        and current_temp is not None
                        and current_temp < base_target_temp
                        and cur_act == "idle"
                        and not domain_data.get("opportunistic_kickstart_done", False)
                    ):
                        desired_temp = boosted_temp
                        domain_data["opportunistic_kickstart"] = True
                        domain_data["opportunistic_kickstart_target"] = base_target_temp
                    await _async_sync_direct_temp(cl_id, st_obj, desired_temp)
            finally:
                hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))

    # 3. Gezieltes, punktgenaues Schalten via async_track_point_in_time (kein minütliches Polling)
    _unsub_timer = None

    def _get_next_target_datetime(now_dt: datetime) -> datetime | None:
        """Ermittelt den nächsten exakten Schaltzeitpunkt (Cooldown, Preheat, Slot-Wechsel)."""
        _, preheat, cooldown, active_slot, next_slot, _, _ = evaluate_state(hass, config_entry)
        candidates: list[datetime] = []

        # 1. Nächster regulärer Slot-Start
        if next_slot and next_slot.get("from") and next_slot.get("date"):
            p_time = parse_time(next_slot.get("from"))
            if p_time:
                try:
                    slot_dt = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                        hour=p_time.hour, minute=p_time.minute, second=0, microsecond=0, tzinfo=now_dt.tzinfo
                    )
                    if slot_dt > now_dt:
                        candidates.append(slot_dt)
                except Exception:
                    pass

        # 2. Ende des aktuellen aktiven Slots
        if active_slot and active_slot.get("to") and active_slot.get("date"):
            p_time = parse_time(active_slot.get("to"))
            if p_time:
                try:
                    slot_end_dt = datetime.strptime(active_slot.get("date"), "%Y-%m-%d").replace(
                        hour=p_time.hour, minute=p_time.minute, second=0, microsecond=0, tzinfo=now_dt.tzinfo
                    )
                    from_time = parse_time(active_slot.get("from"))
                    if from_time and p_time < from_time:
                        slot_end_dt += timedelta(days=1)
                    if slot_end_dt > now_dt:
                        candidates.append(slot_end_dt)
                except Exception:
                    pass

        # 3. Vorgezogenes Vorheizen (Preheat-Start)
        if preheat and preheat.get("start_time") and next_slot and next_slot.get("date"):
            p_time = parse_time(preheat.get("start_time"))
            if p_time:
                try:
                    preheat_dt = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                        hour=p_time.hour, minute=p_time.minute, second=0, microsecond=0, tzinfo=now_dt.tzinfo
                    )
                    if preheat_dt > now_dt and not preheat.get("is_preheating"):
                        candidates.append(preheat_dt)
                except Exception:
                    pass

        # 4. Vorgezogene Nachtabsenkung (Cooldown-Start)
        if cooldown and cooldown.get("start_time") and next_slot and next_slot.get("date"):
            c_time = parse_time(cooldown.get("start_time"))
            if c_time:
                try:
                    cooldown_dt = datetime.strptime(next_slot.get("date"), "%Y-%m-%d").replace(
                        hour=c_time.hour, minute=c_time.minute, second=0, microsecond=0, tzinfo=now_dt.tzinfo
                    )
                    if cooldown_dt > now_dt and not cooldown.get("is_cooling_down"):
                        candidates.append(cooldown_dt)
                except Exception:
                    pass

        valid_future = [c for c in candidates if c > now_dt]
        if valid_future:
            return min(valid_future)
        return now_dt + timedelta(hours=1)

    def _reschedule_target_timer():
        """Plant den Timer exakt auf die nächste anstehende Schaltsekunde."""
        nonlocal _unsub_timer
        if _unsub_timer is not None:
            _unsub_timer()
            _unsub_timer = None

        now_dt = dt_util.now()
        target_dt = _get_next_target_datetime(now_dt)
        if target_dt is None:
            return

        _LOGGER.debug(
            "Smart Climate Scheduler [%s]: Nächster Ziel-Schaltzeitpunkt geplant für %s",
            config_entry.entry_id,
            target_dt.isoformat(),
        )

        async def _async_target_time_reached(fired_dt):
            nonlocal _unsub_timer
            _unsub_timer = None
            _LOGGER.debug(
                "Smart Climate Scheduler [%s]: Ziel-Schaltzeitpunkt erreicht (%s)",
                config_entry.entry_id,
                fired_dt.isoformat(),
            )
            invalidate_eval_cache(domain_data)
            await async_apply_schedule_to_climate()
            _async_update_all_entities()
            _reschedule_target_timer()

        _unsub_timer = async_track_point_in_time(hass, _async_target_time_reached, target_dt)

    def _cancel_timer():
        nonlocal _unsub_timer
        if _unsub_timer is not None:
            _unsub_timer()
            _unsub_timer = None

    config_entry.async_on_unload(_cancel_timer)

    async def async_refresh_forecast(event=None):
        if outside_weather:
            try:
                fc = await async_get_hourly_forecast(hass, outside_weather)
                if fc:
                    domain_data["hourly_forecast_cache"] = fc
                    invalidate_eval_cache(domain_data)
            except Exception as e:
                _LOGGER.debug("Fehler beim Abruf der stündlichen Vorhersage: %s", e)

    if outside_weather:
        if not is_hass_starting(hass):
            hass.async_create_task(async_refresh_forecast())
        config_entry.async_on_unload(
            async_track_time_interval(hass, async_refresh_forecast, timedelta(minutes=30))
        )

    # Listener für Climate- und Sensor-Änderungen (mit Re-Scheduling bei Temperaturänderungen)
    async def async_climate_changed(event):
        if event and hasattr(event, "data") and event.data.get("entity_id") == outside_weather:
            await async_refresh_forecast(event)
        await async_check_heating_session(event)
        await async_apply_schedule_to_climate(event)
        evaluate_and_update_anomaly(hass, config_entry, domain_data)
        _async_update_all_entities()
        _reschedule_target_timer()

    tracked_entities: list[str] = list(climate_entities)
    if room_temp_sensor and room_temp_sensor not in tracked_entities:
        tracked_entities.append(room_temp_sensor)
    for ws_id in window_sensors:
        if ws_id and ws_id not in tracked_entities:
            tracked_entities.append(ws_id)
    if heating_active_sensor and heating_active_sensor not in tracked_entities:
        tracked_entities.append(heating_active_sensor)
    if outside_sensor and outside_sensor not in tracked_entities:
        tracked_entities.append(outside_sensor)
    if outside_weather and outside_weather not in tracked_entities:
        tracked_entities.append(outside_weather)
    resolved_auto_switch = resolve_entry_entity_id(
        hass,
        config_entry,
        "switch",
        "automatic",
        runtime_key="automatic_switch",
    )
    if resolved_auto_switch and resolved_auto_switch not in tracked_entities:
        tracked_entities.append(resolved_auto_switch)

    config_entry.async_on_unload(
        async_track_state_change_event(hass, tracked_entities, async_climate_changed)
    )

    async def _async_schedule_changed(event):
        invalidate_eval_cache(domain_data)
        await async_apply_schedule_to_climate(event)
        _async_update_all_entities()
        _reschedule_target_timer()

    if schedule_entity:
        config_entry.async_on_unload(
            async_track_state_change_event(hass, [schedule_entity], _async_schedule_changed)
        )

    config_entry.async_on_unload(
        async_track_state_change_event(hass, [main_sensor.entity_id], _async_schedule_changed)
    )

    domain_data["async_apply_schedule"] = async_apply_schedule_to_climate
    domain_data["reschedule_target_timer"] = _reschedule_target_timer
    domain_data["update_all_entities"] = _async_update_all_entities

    # Sofort-Abgleich unmittelbar nach vollständigem Home-Assistant-Start (EVENT_HOMEASSISTANT_STARTED)
    async def _async_on_ha_started():
        invalidate_eval_cache(domain_data)
        if outside_weather:
            await async_refresh_forecast()
        await async_apply_schedule_to_climate()
        evaluate_and_update_anomaly(hass, config_entry, domain_data)
        _async_update_all_entities()
        _reschedule_target_timer()

    # Nach Ablauf der 90s-Start-Karenzzeit ggf. noch ausstehende Warnungen / Schaltvorgänge prüfen
    async def _async_post_startup_check():
        invalidate_eval_cache(domain_data)
        await async_apply_schedule_to_climate()
        evaluate_and_update_anomaly(hass, config_entry, domain_data)
        _async_update_all_entities()
        _reschedule_target_timer()

    if is_hass_starting(hass):
        register_startup_grace_callback(
            hass,
            config_entry.entry_id,
            _async_post_startup_check,
            on_started_callback=_async_on_ha_started,
        )
    else:
        register_startup_grace_callback(hass, config_entry.entry_id, _async_post_startup_check)

    config_entry.async_on_unload(
        lambda: unregister_startup_grace_callback(hass, config_entry.entry_id)
    )

    # Minütliche Überwachung des Anomalie- & Hardware-Wächters (erkennt Zeitüberschreitungen ohne neue Events)
    async def _async_anomaly_tick(now_dt=None):
        prev_snap = domain_data.get("anomaly_state", {}).get("snapshot") or {}
        prev_key = (
            bool(prev_snap.get("active", False)),
            prev_snap.get("primary_type"),
            tuple(prev_snap.get("anomalies", [])),
        )
        prev_unavail = prev_snap.get("unavailable_minutes", 0.0)
        new_snap = evaluate_and_update_anomaly(hass, config_entry, domain_data)
        new_key = (
            bool(new_snap.get("active", False)),
            new_snap.get("primary_type"),
            tuple(new_snap.get("anomalies", [])),
        )
        new_unavail = new_snap.get("unavailable_minutes", 0.0)
        if new_key != prev_key or new_snap.get("active") or new_unavail != prev_unavail:
            anomaly_ent = domain_data.get("anomaly_binary_sensor")
            if anomaly_ent is not None:
                async_write_ha_state_if_enabled(anomaly_ent)
            async_write_ha_state_if_enabled(debug_sensor)

    config_entry.async_on_unload(
        async_track_time_interval(hass, _async_anomaly_tick, timedelta(minutes=1))
    )
    evaluate_and_update_anomaly(hass, config_entry, domain_data)

    # Initialen Ziel-Timer scharfschalten
    _reschedule_target_timer()


SCHEDULE_PRESET_OPTIONS = [
    "none",
    "home",
    "away",
    "comfort",
    "eco",
    "sleep",
    "boost",
    "activity",
]


class SmartClimateSchedulerSensor(RestoreEntity, SensorEntity):
    """Haupt-Zeitplan-Sensor mit Zustands-Wiederherstellung nach Neustarts."""

    _attr_icon = "mdi:calendar-clock"
    _attr_has_entity_name = True
    _attr_translation_key = "schedule"
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        if hass is not None:
            self.hass = hass
        self._last_known_state = None
        self._attr_unique_id = f"{config_entry.entry_id}_schedule"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("schedule", lang)
        self.entity_id = f"sensor.{slug}_{suffix}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unavailable", "unknown"):
            self._last_known_state = str(last_state.state).strip().lower()

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def options(self) -> list[str]:
        """Gibt alle zulässigen Zustandsoptionen für die ENUM-Geräteklasse zurück."""
        opts = list(SCHEDULE_PRESET_OPTIONS)
        for cp in get_custom_presets(self.config_entry):
            cid = str(cp.get("id", "")).strip().lower()
            if cid and cid not in opts:
                opts.append(cid)
        cur_val = self.native_value
        if cur_val and str(cur_val).strip().lower() not in opts:
            opts.append(str(cur_val).strip().lower())
        return opts

    @property
    def native_value(self) -> str:
        hass_obj = getattr(self, "hass", None)
        climate_entities = get_climate_entities(self.config_entry)
        any_available = False
        if climate_entities and hass_obj:
            for cl_id in climate_entities:
                cl_st = hass_obj.states.get(cl_id)
                if cl_st and cl_st.state not in ("unavailable", "unknown"):
                    any_available = True
                    break

        if not any_available:
            if self._last_known_state:
                return str(self._last_known_state).strip().lower()

        preset, _, _, _, _, _, _ = evaluate_state(hass_obj, self.config_entry)
        if preset and preset not in ("unavailable", "unknown"):
            self._last_known_state = str(preset).strip().lower()
        val = preset or self._last_known_state or "eco"
        return str(val).strip().lower()

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt das aktive Profil sowie die aktiven und nachfolgenden Slots des Zeitplans zurück."""
        hass_obj = getattr(self, "hass", None)
        _, _, _, active_slot, next_slot, _, _ = evaluate_state(
            hass_obj, self.config_entry
        )
        _, active_profile = get_profiles_and_active(self.config_entry)

        return {
            "profile": active_profile,
            "active_slot": active_slot,
            "next_slot": next_slot,
        }


class SmartClimateSchedulerHeatingRateSensor(SensorEntity):
    """Live-Sensor für die gemessene und gelernte Aufheizrate in K/h (Version 2.0)."""

    _attr_icon = "mdi:thermometer-chevron-up"
    _attr_native_unit_of_measurement = "K/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "heating_rate"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_heating_rate"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("heating_rate", lang)
        self.entity_id = f"sensor.{slug}_{suffix}"

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Sensor ist standardmäßig nur aktiv wenn Lernen aktiviert ist."""
        return bool(
            self.config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                self.config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )

    @property
    def available(self) -> bool:
        """Sensor ist deaktiviert, wenn das Lernen ausgeschaltet ist."""
        return bool(
            self.config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                self.config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )

    @property
    def native_value(self) -> float:
        """Gibt solange der Brenner 'on' ist die geglättete Schritt-Aufheizrate zurück, sonst 0.0."""
        domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        session = domain_data.get("active_session")

        if not session:
            return 0.0

        live_val = session.get("live_rate")
        if live_val is not None:
            try:
                f_live = float(live_val)
                if not math.isnan(f_live) and not math.isinf(f_live) and f_live > 0:
                    return round(f_live, 3)
            except (ValueError, TypeError):
                pass

        return 0.0

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt ausschließlich active_session, averages und average zurück."""
        domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        session = domain_data.get("active_session")

        session_dict = None
        if session:
            start_t = session.get("start_time")
            last_st = session.get("last_step_time")
            session_dict = {
                "start_time": start_t.isoformat() if start_t else None,
                "start_temp": session.get("start_temp"),
                "last_step_time": last_st.isoformat() if last_st else None,
                "last_step_temp": session.get("last_step_temp"),
                "outside_start": session.get("outside_start"),
                "live_rate": session.get("live_rate"),
            }

        fallback_rate = _safe_float(
            self.config_entry.options.get(
                CONF_FALLBACK_HEATING_RATE,
                self.config_entry.data.get(CONF_FALLBACK_HEATING_RATE),
            ),
            DEFAULT_FALLBACK_HEATING_RATE,
        )

        avg_val = domain_data.get("average")
        clean_avg = _safe_float(avg_val, fallback_rate)

        return {
            "active_session": session_dict,
            "averages": domain_data.get("averages", {}),
            "average": clean_avg,
        }


class SmartClimateSchedulerCoolingRateSensor(SensorEntity):
    """Live-Sensor für die gemessene und gelernte Abkühlrate in K/h (Version 2.3.2)."""

    _attr_icon = "mdi:thermometer-chevron-down"
    _attr_native_unit_of_measurement = "K/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "cooling_rate"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_cooling_rate"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("cooling_rate", lang)
        self.entity_id = f"sensor.{slug}_{suffix}"

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Sensor ist standardmäßig nur aktiv wenn Lernen aktiviert ist."""
        return bool(
            self.config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                self.config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )

    @property
    def available(self) -> bool:
        """Sensor ist deaktiviert, wenn das Lernen ausgeschaltet ist."""
        return bool(
            self.config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                self.config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )

    @property
    def native_value(self) -> float:
        """Gibt während einer aktiven Abkühlphase die geglättete Schritt-Abkühlrate zurück, sonst 0.0."""
        domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        session = domain_data.get("active_cooling_session")

        if not session:
            return 0.0

        live_val = session.get("live_rate")
        if live_val is not None:
            try:
                f_live = float(live_val)
                if not math.isnan(f_live) and not math.isinf(f_live) and f_live > 0:
                    return round(f_live, 3)
            except (ValueError, TypeError):
                pass

        return 0.0

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt active_session, averages und average für die Abkühlrate zurück."""
        domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        session = domain_data.get("active_cooling_session")

        session_dict = None
        if session:
            start_t = session.get("start_time")
            last_st = session.get("last_step_time")
            session_dict = {
                "start_time": start_t.isoformat() if start_t else None,
                "start_temp": session.get("start_temp"),
                "last_step_time": last_st.isoformat() if last_st else None,
                "last_step_temp": session.get("last_step_temp"),
                "outside_start": session.get("outside_start"),
                "live_rate": session.get("live_rate"),
            }

        fallback_rate = _safe_float(
            self.config_entry.options.get(
                CONF_FALLBACK_COOLING_RATE,
                self.config_entry.data.get(CONF_FALLBACK_COOLING_RATE),
            ),
            DEFAULT_FALLBACK_COOLING_RATE,
        )

        avg_val = domain_data.get("cooling_average")
        clean_avg = _safe_float(avg_val, fallback_rate)

        return {
            "active_session": session_dict,
            "averages": domain_data.get("cooling_averages", {}),
            "average": clean_avg,
        }


class SmartClimateSchedulerNextActionSensor(SensorEntity):
    """Sensor für die nächste geplante Aktion des Zeitplans (Version 2.3.2)."""

    _attr_icon = "mdi:calendar-arrow-right"
    _attr_has_entity_name = True
    _attr_translation_key = "next_action"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_next_action"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("next_action", lang)
        self.entity_id = f"sensor.{slug}_{suffix}"

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def native_value(self) -> str:
        """Gibt die nächste geplante Aktion als Zustand zurück."""
        if not self.hass:
            return "none"
        _, _, _, _, _, next_action, _ = evaluate_state(self.hass, self.config_entry)
        if isinstance(next_action, dict):
            return next_action.get("action") or "none"
        return str(next_action or "none")

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt den Zeitpunkt der nächsten Aktion als Attribut zurück."""
        if not self.hass:
            return {"time": None}
        _, _, _, _, _, next_action, _ = evaluate_state(self.hass, self.config_entry)
        if isinstance(next_action, dict):
            return {"time": next_action.get("time")}
        return {"time": None}

