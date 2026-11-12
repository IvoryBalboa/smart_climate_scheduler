"""Sensor-Plattform für Smart Climate Scheduler (Version 2.3.5)."""
from __future__ import annotations

import logging
import math
import time as time_mod
from datetime import datetime, timedelta
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

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
    get_config_entry_slug,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
    get_outside_temperature,
    get_preset_temperature,
    get_target_hvac_mode,
    normalize_matrix,
    parse_time,
    safe_float as _safe_float,
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

    main_sensor = SmartClimateSchedulerSensor(config_entry, hass=hass)
    heating_rate_sensor = SmartClimateSchedulerHeatingRateSensor(config_entry, hass=hass)
    cooling_rate_sensor = SmartClimateSchedulerCoolingRateSensor(config_entry, hass=hass)
    next_action_sensor = SmartClimateSchedulerNextActionSensor(config_entry, hass=hass)
    debug_sensor = SmartClimateSchedulerDebugSensor(config_entry, main_sensor, hass=hass)

    sensors = hass.data.setdefault(f"{DOMAIN}_sensors", [])
    sensors.extend([main_sensor, heating_rate_sensor, cooling_rate_sensor, next_action_sensor, debug_sensor])

    async_add_entities([main_sensor, heating_rate_sensor, cooling_rate_sensor, next_action_sensor, debug_sensor], True)

    # Entity-Registry Deaktivierung/Aktivierung für die Raten- und Binär-Sensoren synchronisieren
    await async_sync_entity_registry_disabled(hass, config_entry)

    climate_entity = (
        config_entry.options.get(CONF_CLIMATE_ENTITY)
        or config_entry.data.get(CONF_CLIMATE_ENTITY, "")
    ).strip()

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
        """Prüft, ob Heizen aktiv ist: Brenner 'on' UND Thermostat hvac_action == 'heating'."""
        if not hass:
            return False

        # 1. Thermostat muss aktiv heizen (hvac_action == 'heating')
        thermostat_heating = False
        if climate_entity:
            cl_state = hass.states.get(climate_entity)
            if cl_state:
                hvac_act = cl_state.attributes.get("hvac_action")
                if hvac_act == "heating":
                    thermostat_heating = True
                elif not hvac_act and cl_state.state == "heat":
                    thermostat_heating = True

        if not thermostat_heating:
            return False

        # 2. Brenner-Entität muss 'on' sein (falls konfiguriert)
        if heating_active_sensor:
            act_state = hass.states.get(heating_active_sensor)
            return bool(act_state and act_state.state == "on")

        # Falls kein separater Brenner-Sensor konfiguriert ist, gilt der Thermostat-Zustand
        return thermostat_heating

    def _get_current_temp() -> float:
        """Liest die aktuelle Raumtemperatur."""
        if not climate_entity or not hass:
            return 20.0
        cl_state = hass.states.get(climate_entity)
        if not cl_state:
            return 20.0
        temp = cl_state.attributes.get("current_temperature")
        if temp is None:
            temp = cl_state.attributes.get("external_temp_ema", 20.0)
        try:
            f = float(temp)
            return 20.0 if math.isnan(f) or math.isinf(f) else f
        except (ValueError, TypeError):
            return 20.0

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

    # Automatik: Preset und optionale Zweipunkt-Regelung anwenden
    async def async_apply_schedule_to_climate(event=None):
        if not domain_data.get("automation_enabled", False):
            return
        if domain_data.get("is_setting_preset", False) or domain_data.get("is_setting_hvac", False):
            return

        state_obj = hass.states.get(climate_entity)
        entry_name = config_entry.title or config_entry.entry_id
        if not state_obj or state_obj.state in ("unavailable", "unknown", "None", None):
            cur_state = state_obj.state if state_obj else "nicht gefunden"
            last_warn = domain_data.get("_last_unavail_warn_state")
            if last_warn != cur_state:
                domain_data["_last_unavail_warn_state"] = cur_state
                _LOGGER.warning(
                    "Smart Climate Scheduler [%s]: Thermostat '%s' ist nicht verfügbar (Status: '%s')",
                    entry_name,
                    climate_entity,
                    cur_state,
                )
            return
        domain_data.pop("_last_unavail_warn_state", None)

        current_preset = state_obj.attributes.get("preset_mode")
        target_preset, _, _, _, _, _, _ = evaluate_state(hass, config_entry)
        attrs = state_obj.attributes or {}
        current_hvac_action = attrs.get("hvac_action")
        current_hvac_mode = state_obj.state
        kickstart_active = domain_data.get("opportunistic_kickstart", False)

        # Kickstart-Abschluss: Sobald das Thermostat hvac_action == "heating" meldet, sofort Soll-Preset wiederherstellen!
        if kickstart_active and current_hvac_action == "heating":
            domain_data["opportunistic_kickstart"] = False
            domain_data["is_setting_preset"] = True
            _LOGGER.info(
                "Automatik Zweipunkt [%s]: Kickstart erfolgreich (hvac_action ist nun 'heating') -> Stelle Soll-Preset '%s' wieder her",
                climate_entity,
                target_preset,
            )
            try:
                await hass.services.async_call(
                    "climate",
                    "set_preset_mode",
                    service_data={"preset_mode": target_preset},
                    target={"entity_id": climate_entity},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.error(
                    "Smart Climate Scheduler [%s]: Fehler beim Wiederherstellen von Preset '%s' auf '%s': %s",
                    entry_name,
                    target_preset,
                    climate_entity,
                    err,
                )
            finally:
                hass.loop.call_later(2, lambda: domain_data.update({"is_setting_preset": False}))

        elif not kickstart_active:
            # 1. Preset regulär anwenden (solange kein Kickstart auf Ventilöffnung wartet)
            if target_preset and str(current_preset).lower() != str(target_preset).lower():
                domain_data["is_setting_preset"] = True
                _LOGGER.info(
                    "Automatik [%s]: Übertrage Soll-Preset '%s' (bisher: '%s', Modus: '%s')",
                    climate_entity,
                    target_preset,
                    current_preset,
                    state_obj.state,
                )
                try:
                    await hass.services.async_call(
                        "climate",
                        "set_preset_mode",
                        service_data={"preset_mode": target_preset},
                        target={"entity_id": climate_entity},
                        blocking=False,
                    )
                except Exception as err:
                    _LOGGER.error(
                        "Smart Climate Scheduler [%s]: Fehler beim Setzen von Preset '%s' auf '%s': %s",
                        entry_name,
                        target_preset,
                        climate_entity,
                        err,
                    )
                finally:
                    hass.loop.call_later(2, lambda: domain_data.update({"is_setting_preset": False}))

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
        heating_active_sensor = config_entry.options.get(
            CONF_HEATING_ACTIVE_SENSOR,
            config_entry.data.get(CONF_HEATING_ACTIVE_SENSOR),
        )
        is_heating_active = False
        if heating_active_sensor:
            st = hass.states.get(heating_active_sensor)
            if not st:
                if domain_data.get("_last_burner_missing") != heating_active_sensor:
                    domain_data["_last_burner_missing"] = heating_active_sensor
                    _LOGGER.warning(
                        "Smart Climate Scheduler [%s]: Konfigurierter Heizungs-Sensor '%s' existiert nicht in Home Assistant",
                        entry_name,
                        heating_active_sensor,
                    )
            elif st.state in ("unavailable", "unknown"):
                if domain_data.get("_last_burner_state") != st.state:
                    domain_data["_last_burner_state"] = st.state
                    _LOGGER.warning(
                        "Smart Climate Scheduler [%s]: Heizungs-Sensor '%s' ist nicht verfügbar (Status: '%s')",
                        entry_name,
                        heating_active_sensor,
                        st.state,
                    )
            else:
                domain_data.pop("_last_burner_state", None)
                domain_data.pop("_last_burner_missing", None)
                if st.state.lower() in ("on", "true", "active", "heat", "heating"):
                    is_heating_active = True

        # 2. Zwei-Punkt-Regelung: Steuerung von off und heat anhand der Temperatur-Schwellen
        if hvac_off_on_target:
            current_hvac_mode = state_obj.state
            current_hvac_action = attrs.get("hvac_action")
            real_measured_temp = attrs.get("current_temperature")
            if real_measured_temp is None:
                real_measured_temp = attrs.get("external_temp_ema")

            try:
                current_temp = float(real_measured_temp) if real_measured_temp is not None else None
            except (ValueError, TypeError):
                current_temp = None

            target_temp = get_preset_temperature(state_obj, target_preset)

            fallback_tol = _safe_float(
                config_entry.options.get(
                    CONF_FALLBACK_TOLERANCE,
                    config_entry.data.get(CONF_FALLBACK_TOLERANCE),
                ),
                DEFAULT_FALLBACK_TOLERANCE,
            )
            tolerance = _safe_float(attrs.get("tolerance"), fallback_tol)

            if current_temp is not None and target_temp is not None:
                # Fall 1: Ist >= Soll -> Thermostat ausschalten (NUR wenn hvac_action != "heating")
                if current_temp >= target_temp:
                    domain_data["two_point_target_reached"] = True
                    domain_data["opportunistic_kickstart"] = False
                    if current_hvac_mode != "off":
                        if current_hvac_action == "heating":
                            _LOGGER.debug(
                                "Automatik Zweipunkt [%s]: Ist (%.1f °C) >= Soll (%.1f °C), aber hvac_action ist 'heating' -> Kein Ausschalten auf 'off'",
                                climate_entity,
                                current_temp,
                                target_temp,
                            )
                        else:
                            domain_data["is_setting_hvac"] = True
                            _LOGGER.info(
                                "Automatik Zweipunkt [%s]: Ist (%.1f °C) >= Soll (%.1f °C) & hvac_action != 'heating' -> Schalte Thermostat auf 'off'",
                                climate_entity,
                                current_temp,
                                target_temp,
                            )
                            try:
                                await hass.services.async_call(
                                    "climate",
                                    "set_hvac_mode",
                                    service_data={"hvac_mode": "off"},
                                    target={"entity_id": climate_entity},
                                    blocking=False,
                                )
                            except Exception as err:
                                _LOGGER.error(
                                    "Smart Climate Scheduler [%s]: Fehler beim Ausschalten ('off') von '%s': %s",
                                    entry_name,
                                    climate_entity,
                                    err,
                                )
                            finally:
                                hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))

                # Fall 2: Ist < Soll - Toleranz ODER Opportunistisches Mitheizen -> Thermostat wieder einschalten (hvac_mode: heat)
                elif current_temp < (target_temp - tolerance) or (opportunistic_heating and is_heating_active and current_temp < target_temp):
                    domain_data["two_point_target_reached"] = False
                    target_mode = get_target_hvac_mode(state_obj)

                    # Opportunistischer Kickstart für Better Thermostat:
                    # Liegt Ist innerhalb des Hysterese-Totbands (target_temp - tolerance <= current_temp < target_temp)
                    # und das Thermostat heizt noch nicht (off oder idle)?
                    is_opp_deadband = (
                        opportunistic_heating
                        and is_heating_active
                        and current_temp < target_temp
                        and current_temp >= (target_temp - tolerance)
                    )

                    if is_opp_deadband and (current_hvac_mode == "off" or current_hvac_action == "idle"):
                        if not domain_data.get("opportunistic_kickstart"):
                            boosted_temp = round(target_temp + tolerance, 1)
                            domain_data["opportunistic_kickstart"] = True
                            domain_data["is_setting_hvac"] = True
                            _LOGGER.info(
                                "Automatik Zweipunkt [%s]: Opportunistischer Kickstart aktiv (Brenner an, Ist %.1f °C < Soll %.1f °C, Status: %s/%s) -> Schalte '%s' & hebe Temperatur kurzfristig auf %.1f °C an",
                                climate_entity,
                                current_temp,
                                target_temp,
                                current_hvac_mode,
                                current_hvac_action,
                                target_mode,
                                boosted_temp,
                            )
                            try:
                                if current_hvac_mode == "off":
                                    await hass.services.async_call(
                                        "climate",
                                        "set_hvac_mode",
                                        service_data={"hvac_mode": target_mode},
                                        target={"entity_id": climate_entity},
                                        blocking=False,
                                    )
                                await hass.services.async_call(
                                    "climate",
                                    "set_temperature",
                                    service_data={"temperature": boosted_temp},
                                    target={"entity_id": climate_entity},
                                    blocking=False,
                                )
                            except Exception as err:
                                _LOGGER.error(
                                    "Smart Climate Scheduler [%s]: Fehler beim Kickstart (Temperatur %.1f °C) auf '%s': %s",
                                    entry_name,
                                    boosted_temp,
                                    climate_entity,
                                    err,
                                )
                            finally:
                                hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))

                    elif current_hvac_mode == "off":
                        domain_data["is_setting_hvac"] = True
                        _LOGGER.info(
                            "Automatik Zweipunkt [%s]: Ist (%.1f °C) < Schwelle (%.1f - %.2f = %.1f °C) -> Schalte Thermostat auf '%s'",
                            climate_entity,
                            current_temp,
                            target_temp,
                            tolerance,
                            target_temp - tolerance,
                            target_mode,
                        )
                        try:
                            await hass.services.async_call(
                                "climate",
                                "set_hvac_mode",
                                service_data={"hvac_mode": target_mode},
                                target={"entity_id": climate_entity},
                                blocking=False,
                            )
                        except Exception as err:
                            _LOGGER.error(
                                "Smart Climate Scheduler [%s]: Fehler beim Einschalten ('%s') von '%s': %s",
                                entry_name,
                                target_mode,
                                climate_entity,
                                err,
                            )
                        finally:
                            hass.loop.call_later(2, lambda: domain_data.update({"is_setting_hvac": False}))

    # Apply-Funktion für Switch und andere Module in domain_data registrieren
    domain_data["async_apply_schedule"] = async_apply_schedule_to_climate

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
        _async_update_all_entities()
        _reschedule_target_timer()

    tracked_entities = [climate_entity]
    if heating_active_sensor:
        tracked_entities.append(heating_active_sensor)
    if outside_sensor:
        tracked_entities.append(outside_sensor)
    if outside_weather:
        tracked_entities.append(outside_weather)
    switch_slug = get_config_entry_slug(config_entry)
    auto_suffix = get_localized_slug_suffix("automatic", get_ha_language(hass))
    tracked_entities.append(f"switch.{switch_slug}_{auto_suffix}")

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

    domain_data["reschedule_target_timer"] = _reschedule_target_timer
    domain_data["update_all_entities"] = _async_update_all_entities

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
        hass_obj = getattr(self, "hass", None)
        climate_entity = (
            self.config_entry.options.get(CONF_CLIMATE_ENTITY)
            or self.config_entry.data.get(CONF_CLIMATE_ENTITY, "")
        ).strip()
        if climate_entity and hass_obj:
            state_obj = hass_obj.states.get(climate_entity)
            if state_obj and "preset_modes" in state_obj.attributes:
                for pm in state_obj.attributes.get("preset_modes") or []:
                    pm_str = str(pm).strip().lower()
                    if pm_str and pm_str not in opts:
                        opts.append(pm_str)
        cur_val = self.native_value
        if cur_val and str(cur_val).strip().lower() not in opts:
            opts.append(str(cur_val).strip().lower())
        return opts

    @property
    def native_value(self) -> str:
        hass_obj = getattr(self, "hass", None)
        climate_entity = (
            self.config_entry.options.get(CONF_CLIMATE_ENTITY)
            or self.config_entry.data.get(CONF_CLIMATE_ENTITY, "")
        ).strip()
        climate_state = hass_obj.states.get(climate_entity) if climate_entity and hass_obj else None

        if not climate_state or climate_state.state in ("unavailable", "unknown"):
            if self._last_known_state:
                return str(self._last_known_state).strip().lower()

        preset, _, _, _, _, _, _ = evaluate_state(hass_obj, self.config_entry)
        if preset and preset not in ("unavailable", "unknown"):
            self._last_known_state = str(preset).strip().lower()
        val = preset or self._last_known_state or "eco"
        return str(val).strip().lower()

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt die aktiven und nachfolgenden Slots des Zeitplans zurück."""
        hass_obj = getattr(self, "hass", None)
        _, _, _, active_slot, next_slot, _, _ = evaluate_state(
            hass_obj, self.config_entry
        )

        return {
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

