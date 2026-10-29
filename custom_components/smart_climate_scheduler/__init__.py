"""Smart Climate Scheduler Integration (Version 2.0)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import Platform
from homeassistant.util import dt as dt_util

from .helpers import (
    async_delete_matrix_entry,
    async_set_matrix_entry,
    calculate_overall_average,
    normalize_matrix,
    parse_time,
    safe_float as _safe_float,
)
from .evaluation import invalidate_eval_cache

from .const import (
    DOMAIN,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_COOLING_RATE,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_NEAR_DISTANCE,
    DEFAULT_PREHEAT_ENABLED,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_MAX_MINUTES_PREHEAT,
    DEFAULT_MAX_MINUTES_COOLDOWN,
    DEFAULT_FALLBACK_PRESET,
    CONF_CLIMATE_ENTITY,
    CONF_FALLBACK_HEATING_RATE,
    CONF_FALLBACK_COOLING_RATE,
    CONF_ENABLE_SELF_LEARNING,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_OUTSIDE_WEATHER_ENTITY,
    CONF_HEATING_ACTIVE_SENSOR,
    CONF_ZONE_HOME_ENTITY,
    CONF_ZONE_AWAY_NEAR_ENTITY,
    CONF_NEAR_DISTANCE,
    CONF_DEFAULT_PRESET,
    CONF_PREHEAT_ENABLED,
    CONF_COOLDOWN_ENABLED,
    CONF_MAX_MINUTES_PREHEAT,
    CONF_MAX_MINUTES_COOLDOWN,
)
from .storage import ClimateSchedulerStorage

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet den Smart Climate Scheduler über einen Config Entry ein."""
    hass.data.setdefault(DOMAIN, {})

    storage = ClimateSchedulerStorage(hass, entry.entry_id)
    stored_data = await storage.async_get_data()

    fallback_rate = _safe_float(
        entry.options.get(
            CONF_FALLBACK_HEATING_RATE,
            entry.data.get(CONF_FALLBACK_HEATING_RATE),
        ),
        DEFAULT_FALLBACK_HEATING_RATE,
    )

    automation_enabled = bool(
        stored_data.get(
            "automation_enabled", entry.options.get("automation_enabled", False)
        )
    )

    norm_averages = normalize_matrix(stored_data.get("averages", {}))
    overall_avg = calculate_overall_average(
        norm_averages, _safe_float(stored_data.get("average"), fallback_rate), already_normalized=True
    )

    fallback_cooling_rate = _safe_float(
        entry.options.get(
            CONF_FALLBACK_COOLING_RATE,
            entry.data.get(CONF_FALLBACK_COOLING_RATE),
        ),
        DEFAULT_FALLBACK_COOLING_RATE,
    )
    norm_cooling = normalize_matrix(stored_data.get("cooling_averages", {}))
    overall_cooling_avg = calculate_overall_average(
        norm_cooling, _safe_float(stored_data.get("cooling_average"), fallback_cooling_rate), already_normalized=True
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "data": entry.data,
        "automation_enabled": automation_enabled,
        "overrides": {},
        "averages": norm_averages,
        "average": overall_avg,
        "cooling_averages": norm_cooling,
        "cooling_average": overall_cooling_avg,
        "storage": storage,
        "active_session": None,
        "active_cooling_session": None,
        "last_heating_off_time": None,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def _resolve_entry_ids(target_entity_id: str | None) -> list[str]:
        if not hass.data.get(DOMAIN):
            return []
        if not target_entity_id:
            return list(hass.data[DOMAIN].keys())

        # 1. Über Entity Registry auflösen (unterstützt Sensoren, Switches und alle gebundenen Entitäten)
        try:
            from homeassistant.helpers import entity_registry as er
            ent_reg = er.async_get(hass)
            reg_entry = ent_reg.async_get(target_entity_id)
            if reg_entry and reg_entry.config_entry_id and reg_entry.config_entry_id in hass.data[DOMAIN]:
                return [reg_entry.config_entry_id]
        except Exception:
            pass

        # 2. Über registrierte Sensoren
        for sensor in hass.data.get(f"{DOMAIN}_sensors", []):
            if getattr(sensor, "entity_id", None) == target_entity_id:
                if getattr(sensor, "config_entry", None):
                    return [sensor.config_entry.entry_id]

        # 3. Über die zugeordnete Climate-Entität (in options oder data)
        for ent_id, store in hass.data[DOMAIN].items():
            entry_obj = hass.config_entries.async_get_entry(ent_id)
            if entry_obj:
                c_entity = entry_obj.options.get(CONF_CLIMATE_ENTITY) or entry_obj.data.get(CONF_CLIMATE_ENTITY)
                if c_entity == target_entity_id:
                    return [ent_id]
            data = store.get("data", {})
            if data.get(CONF_CLIMATE_ENTITY) == target_entity_id:
                return [ent_id]

        if len(hass.data[DOMAIN]) == 1:
            return list(hass.data[DOMAIN].keys())
        return []

    async def handle_set_override(call: ServiceCall) -> None:
        """Service zum Setzen eines temporären Overrides (mit Start/Endzeit oder Dauer)."""
        entity_id = call.data.get("entity_id")
        override_id = call.data.get("override_id")
        start_val = call.data.get("start")
        end_val = call.data.get("end")
        duration_val = call.data.get("duration")
        preset = call.data.get("preset", "boost")

        now = dt_util.now()
        if not override_id:
            override_id = f"override_{int(now.timestamp())}"

        # Dauer in Minuten ermitteln (unterstützt int, float oder Home Assistant duration dict)
        duration_minutes = None
        if duration_val is not None:
            if isinstance(duration_val, dict):
                total_sec = (
                    duration_val.get("days", 0) * 86400
                    + duration_val.get("hours", 0) * 3600
                    + duration_val.get("minutes", 0) * 60
                    + duration_val.get("seconds", 0)
                )
                duration_minutes = total_sec / 60.0
            else:
                try:
                    duration_minutes = float(duration_val)
                except (ValueError, TypeError):
                    pass

        # 1. Wenn eine Dauer angegeben wurde:
        if duration_minutes is not None and duration_minutes > 0:
            if start_val:
                if "T" in str(start_val):
                    try:
                        start_dt = datetime.fromisoformat(str(start_val))
                    except Exception:
                        start_dt = now
                    end_dt = start_dt + timedelta(minutes=duration_minutes)
                    start_str = start_dt.isoformat()
                    end_str = end_dt.isoformat()
                else:
                    s_time = parse_time(str(start_val))
                    if s_time:
                        start_dt = now.replace(hour=s_time.hour, minute=s_time.minute, second=0, microsecond=0)
                        if start_dt < now - timedelta(minutes=5):
                            start_dt += timedelta(days=1)
                        end_dt = start_dt + timedelta(minutes=duration_minutes)
                        start_str = start_dt.isoformat()
                        end_str = end_dt.isoformat()
                    else:
                        start_str = now.isoformat()
                        end_str = (now + timedelta(minutes=duration_minutes)).isoformat()
            else:
                # Keine Startzeit angegeben -> startet sofort
                start_str = now.isoformat()
                end_str = (now + timedelta(minutes=duration_minutes)).isoformat()
        else:
            # Kein duration angegeben: Start- und Endzeit wie übergeben nutzen
            start_str = str(start_val) if start_val else now.strftime("%H:%M")
            end_str = str(end_val) if end_val else (now + timedelta(hours=1)).strftime("%H:%M")

        entry_ids = _resolve_entry_ids(entity_id)
        if not entry_ids:
            _LOGGER.warning("Override '%s' fehlgeschlagen: Kein passender Eintrag für '%s' gefunden.", override_id, entity_id)
            return

        for target_entry_id in entry_ids:
            hass.data[DOMAIN][target_entry_id]["overrides"][override_id] = {
                "start": start_str,
                "end": end_str,
                "preset": preset,
            }
            _LOGGER.info("Override '%s' gesetzt: %s bis %s -> Preset: %s", override_id, start_str, end_str, preset)
            await _async_update_sensors(hass, target_entry_id)

    async def handle_remove_override(call: ServiceCall) -> None:
        """Service zum Löschen eines Overrides."""
        override_id = call.data.get("override_id")

        for target_entry_id, store in hass.data[DOMAIN].items():
            if override_id in store["overrides"]:
                store["overrides"].pop(override_id)
                _LOGGER.info("Override '%s' entfernt.", override_id)
                await _async_update_sensors(hass, target_entry_id)

    async def handle_reset_heating_rates(call: ServiceCall) -> None:
        """Service zum Zurücksetzen aller gelernten Aufheizraten."""
        entity_id = call.data.get("entity_id")
        entry_ids = _resolve_entry_ids(entity_id)

        for eid in entry_ids:
            store = hass.data[DOMAIN].get(eid)
            if not store:
                continue

            entry_obj = hass.config_entries.async_get_entry(eid)
            f_rate = DEFAULT_FALLBACK_HEATING_RATE
            if entry_obj:
                f_rate = _safe_float(
                    entry_obj.options.get(
                        CONF_FALLBACK_HEATING_RATE,
                        entry_obj.data.get(CONF_FALLBACK_HEATING_RATE),
                    ),
                    DEFAULT_FALLBACK_HEATING_RATE,
                )

            store["averages"] = {}
            store["average"] = f_rate
            store["active_session"] = None

            storage = store.get("storage")
            if storage:
                await storage.async_save_data({
                    "averages": {},
                    "average": f_rate,
                })

            _LOGGER.info("Aufheizraten für Smart Climate Scheduler (%s) erfolgreich zurückgesetzt.", eid)
            await _async_update_sensors(hass, eid)

    async def handle_set_manual_heating_rate(call: ServiceCall) -> None:
        """Service zum manuellen Überschreiben/Setzen der Aufheizrate (K/h)."""
        entity_id = call.data.get("entity_id")
        raw_rate = call.data.get("rate", 1.0)
        clamped_rate = round(max(0.05, min(5.0, _safe_float(raw_rate, 1.0))), 3)
        entry_ids = _resolve_entry_ids(entity_id)

        for eid in entry_ids:
            store = hass.data[DOMAIN].get(eid)
            if not store:
                continue

            store["average"] = clamped_rate

            storage = store.get("storage")
            if storage:
                await storage.async_save_data({"average": clamped_rate})

            _LOGGER.info(
                "Gesamt-Aufheizrate für Smart Climate Scheduler (%s) manuell auf %.2f K/h gesetzt.",
                eid, clamped_rate
            )
            await _async_update_sensors(hass, eid)

    def _get_entry_fallback_rate(eid: str, is_cooling: bool = False) -> float:
        entry_obj = hass.config_entries.async_get_entry(eid)
        conf_key = CONF_FALLBACK_COOLING_RATE if is_cooling else CONF_FALLBACK_HEATING_RATE
        def_val = DEFAULT_FALLBACK_COOLING_RATE if is_cooling else DEFAULT_FALLBACK_HEATING_RATE
        if entry_obj:
            return _safe_float(
                entry_obj.options.get(conf_key, entry_obj.data.get(conf_key)),
                def_val,
            )
        return def_val

    async def _handle_matrix_set(call: ServiceCall, is_cooling: bool = False) -> None:
        entity_id = call.data.get("entity_id")
        raw_temp = call.data.get("temperature")
        raw_rate = call.data.get("rate", 0.2 if is_cooling else 1.0)
        label = "Abkühl-Matrix" if is_cooling else "Matrix"

        for eid in _resolve_entry_ids(entity_id):
            store = hass.data[DOMAIN].get(eid)
            if not store:
                continue
            f_rate = _get_entry_fallback_rate(eid, is_cooling=is_cooling)
            temp_key, clamped_rate, overall_avg = await async_set_matrix_entry(
                store=store,
                raw_temp=raw_temp,
                raw_rate=raw_rate,
                fallback_rate=f_rate,
                is_cooling=is_cooling,
            )
            _LOGGER.info(
                "Smart Climate Scheduler (%s): %s [%s] auf %.3f K/h gesetzt. Neuer Gesamtschnitt: %.3f K/h",
                eid, label, temp_key, clamped_rate, overall_avg,
            )
            await _async_update_sensors(hass, eid)

    async def _handle_matrix_delete(call: ServiceCall, is_cooling: bool = False) -> None:
        entity_id = call.data.get("entity_id")
        raw_temp = call.data.get("temperature")
        label = "Abkühl-Matrix" if is_cooling else "Matrix"

        for eid in _resolve_entry_ids(entity_id):
            store = hass.data[DOMAIN].get(eid)
            if not store:
                continue
            f_rate = _get_entry_fallback_rate(eid, is_cooling=is_cooling)
            temp_key, overall_avg = await async_delete_matrix_entry(
                store=store,
                raw_temp=raw_temp,
                fallback_rate=f_rate,
                is_cooling=is_cooling,
            )
            if overall_avg is not None:
                _LOGGER.info(
                    "Smart Climate Scheduler (%s): %s [%s] entfernt. Neuer Gesamtschnitt: %.3f K/h",
                    eid, label, temp_key, overall_avg,
                )
                await _async_update_sensors(hass, eid)
            else:
                _LOGGER.warning(
                    "Smart Climate Scheduler (%s): %s-Eintrag [%s] nicht vorhanden.",
                    eid, label, temp_key,
                )

    async def handle_set_matrix_heating_rate(call: ServiceCall) -> None:
        """Service zum Hinzufügen oder Bearbeiten eines Werts in der Außentemperatur-Matrix."""
        await _handle_matrix_set(call, is_cooling=False)

    async def handle_delete_matrix_heating_rate(call: ServiceCall) -> None:
        """Service zum Löschen eines Werts aus der Außentemperatur-Matrix."""
        await _handle_matrix_delete(call, is_cooling=False)

    async def handle_set_matrix_cooling_rate(call: ServiceCall) -> None:
        """Service zum Hinzufügen oder Bearbeiten eines Werts in der Abkühlraten-Matrix."""
        await _handle_matrix_set(call, is_cooling=True)

    async def handle_delete_matrix_cooling_rate(call: ServiceCall) -> None:
        """Service zum Löschen eines Werts aus der Abkühlraten-Matrix."""
        await _handle_matrix_delete(call, is_cooling=True)

    if not hass.services.has_service(DOMAIN, "set_override"):
        hass.services.async_register(DOMAIN, "set_override", handle_set_override)
    if not hass.services.has_service(DOMAIN, "remove_override"):
        hass.services.async_register(DOMAIN, "remove_override", handle_remove_override)
    if not hass.services.has_service(DOMAIN, "reset_heating_rates"):
        hass.services.async_register(DOMAIN, "reset_heating_rates", handle_reset_heating_rates)
    if not hass.services.has_service(DOMAIN, "set_manual_heating_rate"):
        hass.services.async_register(DOMAIN, "set_manual_heating_rate", handle_set_manual_heating_rate)
    if not hass.services.has_service(DOMAIN, "set_matrix_heating_rate"):
        hass.services.async_register(DOMAIN, "set_matrix_heating_rate", handle_set_matrix_heating_rate)
    if not hass.services.has_service(DOMAIN, "delete_matrix_heating_rate"):
        hass.services.async_register(DOMAIN, "delete_matrix_heating_rate", handle_delete_matrix_heating_rate)
    if not hass.services.has_service(DOMAIN, "set_matrix_cooling_rate"):
        hass.services.async_register(DOMAIN, "set_matrix_cooling_rate", handle_set_matrix_cooling_rate)
    if not hass.services.has_service(DOMAIN, "delete_matrix_cooling_rate"):
        hass.services.async_register(DOMAIN, "delete_matrix_cooling_rate", handle_delete_matrix_cooling_rate)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def _async_update_sensors(hass: HomeAssistant, entry_id: str) -> None:
    """Invalidiert den Evaluierungs-Cache und triggert ein sofortiges Update aller Sensoren dieses Entrys."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
    invalidate_eval_cache(entry_data)
    for sensor in hass.data.get(f"{DOMAIN}_sensors", []):
        if getattr(sensor, "config_entry", None) and sensor.config_entry.entry_id == entry_id:
            if getattr(sensor, "hass", None):
                sensor.async_write_ha_state()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "set_override")
            hass.services.async_remove(DOMAIN, "remove_override")
            hass.services.async_remove(DOMAIN, "reset_heating_rates")
            hass.services.async_remove(DOMAIN, "set_manual_heating_rate")
            hass.services.async_remove(DOMAIN, "set_matrix_heating_rate")
            hass.services.async_remove(DOMAIN, "delete_matrix_heating_rate")
            hass.services.async_remove(DOMAIN, "set_matrix_cooling_rate")
            hass.services.async_remove(DOMAIN, "delete_matrix_cooling_rate")
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
