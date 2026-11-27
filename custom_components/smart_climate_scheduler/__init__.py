"""Smart Climate Scheduler Integration (Version 4.0.0)."""
from __future__ import annotations

import copy
import logging
from datetime import datetime, timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import Platform
from homeassistant.util import dt as dt_util

from .helpers import (
    async_delete_matrix_entry,
    async_set_matrix_entry,
    async_sync_device_registry_version,
    async_sync_entity_registry_disabled,
    async_write_ha_state_if_enabled,
    calculate_overall_average,
    clear_startup_grace_state,
    convert_legacy_seconds_to_delay_minutes,
    get_climate_entities,
    get_profiles_and_active,
    normalize_custom_presets,
    normalize_matrix,
    parse_time,
    safe_float as _safe_float,
)
from .evaluation import invalidate_eval_cache
from .frontend_api import async_register_frontend_and_ws

from .const import (
    CONF_AWAY_NEAR_PRESET,
    CONF_AWAY_PRESET,
    CONF_CLIMATE_ENTITIES,
    CONF_CLIMATE_ENTITY,
    CONF_CUSTOM_PRESETS,
    CONF_DEFAULT_PRESET,
    CONF_FALLBACK_COOLING_RATE,
    CONF_FALLBACK_HEATING_RATE,
    CONF_WINDOW_CLOSE_DELAY_MINUTES,
    CONF_WINDOW_OPEN_DELAY_MINUTES,
    DEFAULT_AWAY_NEAR_PRESET,
    DEFAULT_AWAY_PRESET,
    DEFAULT_CUSTOM_PRESETS,
    DEFAULT_FALLBACK_COOLING_RATE,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_PRESET,
    DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
    DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
    DOMAIN,
)
from .storage import ClimateSchedulerStorage

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.CLIMATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migriert bestehende v1/v2/v3 Config Entries automatisch und verlustfrei auf v4.0.0."""
    current_version = getattr(config_entry, "version", 1)
    if current_version >= 4:
        return True

    _LOGGER.info(
        "Migriere Smart Climate Scheduler Eintrag '%s' von Version %s auf Version 4 (v4.0.0)",
        getattr(config_entry, "title", config_entry.entry_id),
        current_version,
    )

    new_data = copy.deepcopy(dict(getattr(config_entry, "data", {}) or {}))
    new_options = copy.deepcopy(dict(getattr(config_entry, "options", {}) or {}))

    # 1. Thermostat-Liste aus legacy climate_entity / climate_entities vereinheitlichen
    climate_entities = get_climate_entities(config_entry)
    if climate_entities:
        new_data[CONF_CLIMATE_ENTITIES] = list(climate_entities)
        new_data[CONF_CLIMATE_ENTITY] = climate_entities[0]
        if CONF_CLIMATE_ENTITIES in new_options or CONF_CLIMATE_ENTITY in new_options:
            new_options[CONF_CLIMATE_ENTITIES] = list(climate_entities)
            new_options[CONF_CLIMATE_ENTITY] = climate_entities[0]

    # 2. Eigene Raum-Presets sicherstellen (mit Starter-Defaults falls bisher noch keine vorhanden)
    raw_presets = new_options.get(CONF_CUSTOM_PRESETS)
    if raw_presets is None:
        raw_presets = new_data.get(CONF_CUSTOM_PRESETS)
    presets = normalize_custom_presets(raw_presets, fallback_to_default=True)
    if not presets:
        presets = [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
    new_data[CONF_CUSTOM_PRESETS] = copy.deepcopy(presets)
    if new_options or CONF_CUSTOM_PRESETS in new_options:
        new_options[CONF_CUSTOM_PRESETS] = copy.deepcopy(presets)

    valid_ids = {p["id"] for p in presets}
    first_id = presets[0]["id"]
    for key, fallback_id in (
        (CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET),
        (CONF_AWAY_NEAR_PRESET, DEFAULT_AWAY_NEAR_PRESET),
        (CONF_AWAY_PRESET, DEFAULT_AWAY_PRESET),
    ):
        for target_dict in (new_data, new_options):
            if key in target_dict:
                cur_val = str(target_dict.get(key) or "").strip().lower()
                if cur_val not in valid_ids:
                    target_dict[key] = fallback_id if fallback_id in valid_ids else first_id

    # 3. Fenster-/Tür-Verzögerungen von Sekunden auf ganze Minuten migrieren
    for sec_key, min_key, default_min in (
        ("window_open_delay_seconds", CONF_WINDOW_OPEN_DELAY_MINUTES, DEFAULT_WINDOW_OPEN_DELAY_MINUTES),
        ("window_close_delay_seconds", CONF_WINDOW_CLOSE_DELAY_MINUTES, DEFAULT_WINDOW_CLOSE_DELAY_MINUTES),
    ):
        if min_key not in new_data:
            if sec_key in new_data:
                new_data[min_key] = convert_legacy_seconds_to_delay_minutes(new_data.get(sec_key), default_min)
            else:
                new_data[min_key] = default_min
        if min_key not in new_options and sec_key in new_options:
            new_options[min_key] = convert_legacy_seconds_to_delay_minutes(new_options.get(sec_key), default_min)
        new_data.pop(sec_key, None)
        new_options.pop(sec_key, None)

    # 4. Veraltete v3-Altlasten entfernen (control_mode, tolerance_entity)
    for legacy_key in ("control_mode", "tolerance_entity"):
        new_data.pop(legacy_key, None)
        new_options.pop(legacy_key, None)

    # 5. ConfigEntry aktualisieren (kompatibel mit HA >=2024.1 version-kwarg und Test-Mocks)
    try:
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
            version=4,
        )
    except TypeError:
        config_entry.version = 4
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
        )

    # 6. Persistentes Storage von eventuellen tolerance_backup-Resten bereinigen
    try:
        storage = ClimateSchedulerStorage(hass, config_entry.entry_id)
        stored = await storage.async_get_data()
        if isinstance(stored, dict) and "tolerance_backup" in stored:
            stored.pop("tolerance_backup", None)
            await storage.async_save_data(stored)
    except Exception as err:
        _LOGGER.debug("Storage-Bereinigung während v4-Migration übersprungen: %s", err)

    _LOGGER.info(
        "Smart Climate Scheduler Eintrag '%s' erfolgreich auf Version 4 migriert.",
        getattr(config_entry, "title", config_entry.entry_id),
    )
    return True


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

    now_dt = dt_util.now()
    raw_overrides = stored_data.get("overrides", {})
    active_overrides: dict[str, dict] = {}
    overrides_pruned = False

    if isinstance(raw_overrides, dict):
        for ov_id, ov_data in raw_overrides.items():
            if not isinstance(ov_data, dict):
                overrides_pruned = True
                continue
            start_val = ov_data.get("start")
            end_val = ov_data.get("end")
            if not start_val or not end_val:
                overrides_pruned = True
                continue
            try:
                if "T" in str(end_val):
                    end_dt = datetime.fromisoformat(str(end_val))
                    if now_dt.tzinfo and end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=now_dt.tzinfo)
                    if end_dt > now_dt:
                        active_overrides[ov_id] = ov_data
                    else:
                        overrides_pruned = True
                else:
                    created_at_str = ov_data.get("created_at")
                    if created_at_str and "T" in str(created_at_str):
                        try:
                            c_dt = datetime.fromisoformat(str(created_at_str))
                            if c_dt.date() < now_dt.date():
                                overrides_pruned = True
                                continue
                        except Exception:
                            pass
                    end_t = parse_time(str(end_val)[:5])
                    start_t = parse_time(str(start_val)[:5])
                    if end_t and start_t:
                        if start_t <= end_t and now_dt.time() >= end_t:
                            overrides_pruned = True
                            continue
                        active_overrides[ov_id] = ov_data
                    else:
                        active_overrides[ov_id] = ov_data
            except Exception:
                overrides_pruned = True

    if overrides_pruned:
        await storage.async_save_data({"overrides": active_overrides})

    raw_climate_mode = str(stored_data.get("climate_mode") or "").strip().lower()
    if automation_enabled:
        climate_mode = "auto"
    elif raw_climate_mode in ("heat", "off"):
        climate_mode = raw_climate_mode
    else:
        climate_mode = "off"

    manual_temperature = None
    if stored_data.get("manual_temperature") is not None:
        parsed_manual = _safe_float(stored_data.get("manual_temperature"), None, allow_zero_or_negative=True)
        if parsed_manual is not None:
            manual_temperature = round(parsed_manual, 1)

    hass.data[DOMAIN][entry.entry_id] = {
        "data": entry.data,
        "automation_enabled": automation_enabled,
        "climate_mode": climate_mode,
        "manual_temperature": manual_temperature,
        "overrides": active_overrides,
        "averages": norm_averages,
        "average": overall_avg,
        "cooling_averages": norm_cooling,
        "cooling_average": overall_cooling_avg,
        "storage": storage,
        "active_session": None,
        "active_cooling_session": None,
        "last_heating_off_time": None,
        "opportunistic_kickstart": False,
        "opportunistic_kickstart_done": False,
        "opportunistic_kickstart_target": None,
        "anomaly_state": {},
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_sync_device_registry_version(hass, entry)
    await async_sync_entity_registry_disabled(hass, entry)
    await async_register_frontend_and_ws(hass)

    def _resolve_entry_ids(call_or_data: ServiceCall | dict | str | None) -> list[str]:
        if not hass.data.get(DOMAIN):
            return []

        resolved: set[str] = set()

        data: dict = {}
        if hasattr(call_or_data, "data"):
            data = getattr(call_or_data, "data", {}) or {}
        elif isinstance(call_or_data, dict):
            data = call_or_data
        elif isinstance(call_or_data, str):
            data = {"entity_id": call_or_data}

        # 1. Direkte entry_id / config_entry_id / config_entry
        raw_entries = data.get("entry_id") or data.get("config_entry_id") or data.get("config_entry")
        if raw_entries:
            if isinstance(raw_entries, str):
                raw_entries = [raw_entries]
            for ce_id in raw_entries:
                if ce_id in hass.data[DOMAIN] and isinstance(hass.data[DOMAIN][ce_id], dict):
                    resolved.add(ce_id)

        # 2. device_id aus target oder call data
        raw_device_ids = data.get("device_id")
        if raw_device_ids:
            if isinstance(raw_device_ids, str):
                raw_device_ids = [raw_device_ids]
            try:
                from homeassistant.helpers import device_registry as dr
                dev_reg = dr.async_get(hass)
                for dev_id in raw_device_ids:
                    device = dev_reg.async_get(dev_id)
                    if device:
                        for identifier in device.identifiers:
                            if len(identifier) == 2 and identifier[0] == DOMAIN:
                                if identifier[1] in hass.data[DOMAIN]:
                                    resolved.add(identifier[1])
                        if hasattr(device, "config_entry_id"):
                            ce_id = device.config_entry_id
                            if ce_id and ce_id in hass.data[DOMAIN]:
                                resolved.add(ce_id)
                        else:
                            for old_ce_id in getattr(device, "config_entries", ()):
                                if old_ce_id in hass.data[DOMAIN]:
                                    resolved.add(old_ce_id)
            except Exception as err:
                _LOGGER.debug("Fehler beim Auflösen der device_id: %s", err)

        # 3. area_id aus target oder call data
        raw_area_ids = data.get("area_id")
        if raw_area_ids:
            if isinstance(raw_area_ids, str):
                raw_area_ids = [raw_area_ids]
            try:
                from homeassistant.helpers import device_registry as dr
                dev_reg = dr.async_get(hass)
                for area_id in raw_area_ids:
                    for device in dev_reg.devices.get_devices_for_area_id(area_id):
                        for identifier in device.identifiers:
                            if len(identifier) == 2 and identifier[0] == DOMAIN:
                                if identifier[1] in hass.data[DOMAIN]:
                                    resolved.add(identifier[1])
                        if hasattr(device, "config_entry_id"):
                            ce_id = device.config_entry_id
                            if ce_id and ce_id in hass.data[DOMAIN]:
                                resolved.add(ce_id)
                        else:
                            for old_ce_id in getattr(device, "config_entries", ()):
                                if old_ce_id in hass.data[DOMAIN]:
                                    resolved.add(old_ce_id)
            except Exception as err:
                _LOGGER.debug("Fehler beim Auflösen der area_id: %s", err)

        # 4. Rückwärtskompatibilität: entity_id (falls in YAML noch angegeben)
        raw_entity_ids = data.get("entity_id")
        if raw_entity_ids:
            if isinstance(raw_entity_ids, str):
                raw_entity_ids = [raw_entity_ids]
            for ent_id in raw_entity_ids:
                try:
                    from homeassistant.helpers import entity_registry as er
                    ent_reg = er.async_get(hass)
                    reg_entry = ent_reg.async_get(ent_id)
                    if reg_entry and reg_entry.config_entry_id and reg_entry.config_entry_id in hass.data[DOMAIN]:
                        resolved.add(reg_entry.config_entry_id)
                except Exception:
                    pass

                for sensor in hass.data.get(f"{DOMAIN}_sensors", []):
                    if getattr(sensor, "entity_id", None) == ent_id:
                        if getattr(sensor, "config_entry", None):
                            resolved.add(sensor.config_entry.entry_id)

                for eid, store in hass.data[DOMAIN].items():
                    if not isinstance(store, dict) or str(eid).startswith("_"):
                        continue
                    entry_obj = hass.config_entries.async_get_entry(eid)
                    if entry_obj:
                        c_entities = get_climate_entities(entry_obj)
                        if ent_id in c_entities:
                            resolved.add(eid)
                    store_data = store.get("data", {})
                    if store_data.get(CONF_CLIMATE_ENTITY) == ent_id or ent_id in (store_data.get("climate_entities") or []):
                        resolved.add(eid)

        if resolved:
            return list(resolved)

        room_entry_ids = [
            eid for eid, store in hass.data[DOMAIN].items()
            if isinstance(store, dict) and not str(eid).startswith("_")
        ]
        if len(room_entry_ids) == 1:
            return room_entry_ids
        return []

    async def handle_set_override(call: ServiceCall) -> None:
        """Service zum Setzen eines temporären Overrides (mit Start/Endzeit oder Dauer)."""
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

        entry_ids = _resolve_entry_ids(call)
        if not entry_ids:
            _LOGGER.warning("Override '%s' fehlgeschlagen: Kein passender Smart Climate Scheduler Eintrag gefunden.", override_id)
            return

        for target_entry_id in entry_ids:
            store = hass.data[DOMAIN][target_entry_id]
            store["overrides"][override_id] = {
                "start": start_str,
                "end": end_str,
                "preset": preset,
                "created_at": now.isoformat(),
            }
            _LOGGER.info("Override '%s' gesetzt: %s bis %s -> Preset: %s (Raum: %s)", override_id, start_str, end_str, preset, target_entry_id)
            storage = store.get("storage")
            if storage and hasattr(storage, "async_save_data"):
                await storage.async_save_data({"overrides": store["overrides"]})
            await _async_update_sensors(hass, target_entry_id)

    async def handle_remove_override(call: ServiceCall) -> None:
        """Service zum Löschen eines einzelnen oder aller Overrides für ausgewählte Räume."""
        raw_override_id = call.data.get("override_id")
        override_id = str(raw_override_id).strip() if raw_override_id is not None else ""
        entry_ids = _resolve_entry_ids(call)
        has_explicit_target = any(
            call.data.get(k)
            for k in ("entry_id", "config_entry_id", "config_entry", "device_id", "area_id", "entity_id")
        )
        if entry_ids:
            target_entry_ids = [
                eid
                for eid in entry_ids
                if isinstance(hass.data[DOMAIN].get(eid), dict) and not str(eid).startswith("_")
            ]
        elif not has_explicit_target:
            target_entry_ids = [
                eid
                for eid, st in hass.data[DOMAIN].items()
                if isinstance(st, dict) and not str(eid).startswith("_")
            ]
        else:
            _LOGGER.warning("remove_override: Ziel-Raum konnte nicht aufgelöst werden (%s).", dict(call.data))
            return

        for eid in target_entry_ids:
            store = hass.data[DOMAIN][eid]
            if override_id:
                if override_id in store.get("overrides", {}):
                    store["overrides"].pop(override_id)
                    _LOGGER.info("Override '%s' entfernt (Raum: %s).", override_id, eid)
            else:
                removed_count = len(store.get("overrides", {}))
                store.setdefault("overrides", {}).clear()
                _LOGGER.info("Alle Overrides (%d) entfernt (Raum: %s).", removed_count, eid)
            storage = store.get("storage")
            if storage and hasattr(storage, "async_save_data"):
                await storage.async_save_data({"overrides": store.get("overrides", {})})
            await _async_update_sensors(hass, eid)

    async def handle_reset_heating_rates(call: ServiceCall) -> None:
        """Service zum Zurücksetzen aller gelernten Aufheizraten."""
        entry_ids = _resolve_entry_ids(call)

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
        raw_rate = call.data.get("rate", 1.0)
        clamped_rate = round(max(0.05, min(5.0, _safe_float(raw_rate, 1.0))), 3)
        entry_ids = _resolve_entry_ids(call)

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
        raw_temp = call.data.get("temperature")
        raw_rate = call.data.get("rate", 0.2 if is_cooling else 1.0)
        label = "Abkühl-Matrix" if is_cooling else "Matrix"

        for eid in _resolve_entry_ids(call):
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
        raw_temp = call.data.get("temperature")
        label = "Abkühl-Matrix" if is_cooling else "Matrix"

        for eid in _resolve_entry_ids(call):
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

    async def handle_set_schedule_profile(call: ServiceCall) -> None:
        """Service zum Wechseln des aktiven Zeitplan-Profils."""
        profile_name = call.data.get("profile")
        if not profile_name:
            _LOGGER.warning("Service set_schedule_profile ohne Profil-Namen aufgerufen.")
            return

        entry_ids = _resolve_entry_ids(call)
        if not entry_ids:
            _LOGGER.warning("Kein passender Smart Climate Scheduler Raum für set_schedule_profile gefunden.")
            return

        for target_entry_id in entry_ids:
            entry_obj = hass.config_entries.async_get_entry(target_entry_id)
            if not entry_obj:
                continue

            profiles, _ = get_profiles_and_active(entry_obj)
            if profile_name not in profiles:
                _LOGGER.warning(
                    "Profil '%s' existiert nicht für Eintrag '%s'. Verfügbare Profile: %s",
                    profile_name,
                    target_entry_id,
                    list(profiles.keys()),
                )
                continue

            select_entity = hass.data.get(DOMAIN, {}).get(target_entry_id, {}).get("profile_select")
            if select_entity and hasattr(select_entity, "async_select_option"):
                await select_entity.async_select_option(profile_name)
            else:
                new_options = dict(entry_obj.options)
                new_options["active_profile"] = profile_name
                hass.config_entries.async_update_entry(entry_obj, options=new_options)
                await _async_update_sensors(hass, target_entry_id)

            _LOGGER.info("Zeitplan-Profil für '%s' auf '%s' gewechselt.", target_entry_id, profile_name)

    if not hass.services.has_service(DOMAIN, "set_override"):
        hass.services.async_register(DOMAIN, "set_override", handle_set_override)
    if not hass.services.has_service(DOMAIN, "remove_override"):
        hass.services.async_register(DOMAIN, "remove_override", handle_remove_override)
    if not hass.services.has_service(DOMAIN, "set_schedule_profile"):
        hass.services.async_register(DOMAIN, "set_schedule_profile", handle_set_schedule_profile)
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
            async_write_ha_state_if_enabled(sensor)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        sensors_list = hass.data.get(f"{DOMAIN}_sensors")
        if isinstance(sensors_list, list):
            sensors_list[:] = [
                ent
                for ent in sensors_list
                if not (
                    getattr(ent, "config_entry", None)
                    and ent.config_entry.entry_id == entry.entry_id
                )
            ]
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            clear_startup_grace_state(hass)
            hass.services.async_remove(DOMAIN, "set_override")
            hass.services.async_remove(DOMAIN, "remove_override")
            hass.services.async_remove(DOMAIN, "set_schedule_profile")
            hass.services.async_remove(DOMAIN, "reset_heating_rates")
            hass.services.async_remove(DOMAIN, "set_manual_heating_rate")
            hass.services.async_remove(DOMAIN, "set_matrix_heating_rate")
            hass.services.async_remove(DOMAIN, "delete_matrix_heating_rate")
            hass.services.async_remove(DOMAIN, "set_matrix_cooling_rate")
            hass.services.async_remove(DOMAIN, "delete_matrix_cooling_rate")
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener when options change."""
    domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if domain_data and domain_data.pop("_updating_from_options_data", False):
        # Zwischenschritt beim Speichern im OptionsFlow (entry.data-Sync vor async_create_entry):
        # Kein verfrühter Reload nötig, da direkt anschließend das finale Options-Update lädt.
        return
    if domain_data and (
        domain_data.pop("_updating_from_switch", False)
        or domain_data.pop("_updating_from_card", False)
    ):
        # Optionen wurden durch Options-Switch oder Timeline-Karte geändert:
        # Kein störender Plattform-Reload nötig, sofortiges Update der Sensoren und Schalter
        await async_sync_entity_registry_disabled(hass, entry)
        await _async_update_sensors(hass, entry.entry_id)
        return
    await async_sync_entity_registry_disabled(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)
