"""Frontend static hosting, JS resource registration, and WebSocket API for the Timeline Lovelace Card."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from .actions import PRESET_TRANSLATIONS
from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_DEFAULT_PRESET,
    DAYS,
    DEFAULT_FALLBACK_PRESET,
    DOMAIN,
    VERSION,
)
from .evaluation import evaluate_state, invalidate_eval_cache
from .helpers import (
    async_restore_tolerance,
    get_config_entry_slug,
    get_ha_language,
    get_localized_slug_suffix,
    get_preset_temperature,
    get_profiles_and_active,
    parse_time,
    resolve_entry_entity_id,
    safe_float as _safe_float,
)

_LOGGER = logging.getLogger(__name__)

FRONTEND_URL_BASE = "/smart_climate_scheduler_files"
CARD_JS_FILENAME = "smart-climate-scheduler-card.js"
DEFAULT_PRESETS = ["none", "home", "away", "boost", "comfort", "eco", "sleep", "activity"]


def get_card_js_url(version: str = VERSION) -> str:
    """Return the static URL path (with cache-busting version query) for the Lovelace card JS."""
    return f"{FRONTEND_URL_BASE}/{CARD_JS_FILENAME}?v={version}"


def _normalize_time_str(raw_val: Any) -> str | None:
    """Normalize HH:MM or HH:MM:SS into HH:MM:SS (special-casing 24:00 -> 23:59:00? Keep 24:00 support? No, parse_time expects 00:00..23:59)."""
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if s.startswith("24:00"):
        return "23:59:00"
    parsed = parse_time(s)
    if not parsed:
        return None
    return f"{parsed.hour:02d}:{parsed.minute:02d}:00"


def _normalize_schedule_dict(raw_schedule: dict | None) -> dict[str, list[dict[str, Any]]]:
    """Return a clean 7-day normalized schedule dict."""
    result: dict[str, list[dict[str, Any]]] = {day: [] for day in DAYS}
    if not isinstance(raw_schedule, dict):
        return result
    for day in DAYS:
        day_slots = raw_schedule.get(day, [])
        cleaned: list[dict[str, Any]] = []
        if isinstance(day_slots, list):
            for slot in day_slots:
                if not isinstance(slot, dict):
                    continue
                from_norm = _normalize_time_str(slot.get("from"))
                to_norm = _normalize_time_str(slot.get("to"))
                if not from_norm or not to_norm or from_norm >= to_norm:
                    continue
                preset = slot.get("preset")
                if not preset and isinstance(slot.get("data"), dict):
                    preset = slot["data"].get("preset")
                cleaned.append(
                    {
                        "from": from_norm,
                        "to": to_norm,
                        "preset": str(preset or "none").strip() or "none",
                        "preheat": bool(slot.get("preheat", True)),
                        "cooldown": bool(slot.get("cooldown", True)),
                    }
                )
        cleaned.sort(key=lambda item: item["from"])
        result[day] = cleaned
    return result


def _normalize_all_profiles(config_entry: Any) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], str]:
    """Read and normalize all schedule profiles + active profile name from a config entry."""
    raw_profiles, active_profile = get_profiles_and_active(config_entry)
    normalized = {
        str(name): _normalize_schedule_dict(sched)
        for name, sched in raw_profiles.items()
    }
    if not normalized:
        normalized = {"Standard": _normalize_schedule_dict({})}
    if active_profile not in normalized:
        active_profile = list(normalized.keys())[0]
    return normalized, active_profile


def _resolve_target_entry(hass: Any, entry_id: str | None = None, entity_id: str | None = None):
    """Resolve the matching ConfigEntry and domain_data from entry_id or entity_id."""
    if not hass:
        return None, None

    domain_entries = hass.data.get(DOMAIN, {})
    target_eid = entry_id

    if not target_eid and entity_id:
        for sensor in hass.data.get(f"{DOMAIN}_sensors", []):
            if getattr(sensor, "entity_id", None) == entity_id and getattr(sensor, "config_entry", None):
                target_eid = sensor.config_entry.entry_id
                break

        if not target_eid:
            try:
                from homeassistant.helpers import entity_registry as er

                ent_reg = er.async_get(hass)
                reg_entry = ent_reg.async_get(entity_id) if ent_reg else None
                if reg_entry and reg_entry.config_entry_id in domain_entries:
                    target_eid = reg_entry.config_entry_id
            except Exception:
                pass

        if not target_eid:
            for eid, store in domain_entries.items():
                if not isinstance(store, dict) or eid.startswith("_"):
                    continue
                ce = hass.config_entries.async_get_entry(eid)
                if ce:
                    cl_id = ce.options.get(CONF_CLIMATE_ENTITY) or ce.data.get(CONF_CLIMATE_ENTITY)
                    if cl_id == entity_id:
                        target_eid = eid
                        break

    if not target_eid:
        real_eids = [k for k, v in domain_entries.items() if isinstance(v, dict) and not k.startswith("_")]
        if len(real_eids) == 1:
            target_eid = real_eids[0]

    if not target_eid:
        return None, None

    entry_obj = hass.config_entries.async_get_entry(target_eid)
    domain_data = domain_entries.get(target_eid)
    return entry_obj, domain_data


def _build_schedule_payload(hass: Any, entry_obj: Any, domain_data: dict | None) -> dict[str, Any]:
    """Assemble full schedule, live status, and linked entity metadata for the Lovelace card."""
    lang = get_ha_language(hass)
    schedule_entity_id = resolve_entry_entity_id(
        hass,
        entry_obj,
        "sensor",
        "schedule",
        runtime_key="main_sensor",
    )
    automation_switch_entity_id = resolve_entry_entity_id(
        hass,
        entry_obj,
        "switch",
        "automatic",
        runtime_key="automatic_switch",
    )
    profile_select_entity_id = resolve_entry_entity_id(
        hass,
        entry_obj,
        "select",
        "schedule_profile",
        runtime_key="profile_select",
    )

    profiles, active_profile = _normalize_all_profiles(entry_obj)

    climate_entity = (
        entry_obj.options.get(CONF_CLIMATE_ENTITY)
        or entry_obj.data.get(CONF_CLIMATE_ENTITY, "")
    ).strip()

    default_preset = entry_obj.options.get(
        CONF_DEFAULT_PRESET,
        entry_obj.data.get(CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET),
    )

    climate_state = hass.states.get(climate_entity) if climate_entity and getattr(hass, "states", None) else None
    supported_presets = list(DEFAULT_PRESETS)
    current_temp = None
    target_temp = None
    hvac_mode = None
    hvac_action = None

    if climate_state:
        attrs = climate_state.attributes or {}
        raw_modes = attrs.get("preset_modes")
        if isinstance(raw_modes, list) and raw_modes:
            supported_presets = [str(m) for m in raw_modes if m is not None]
        raw_cur = attrs.get("current_temperature")
        if raw_cur is None:
            raw_cur = attrs.get("external_temp_ema")
        if raw_cur is not None:
            current_temp = _safe_float(raw_cur, 20.0, allow_zero_or_negative=True)
        hvac_mode = climate_state.state
        hvac_action = attrs.get("hvac_action")

    preset_temperatures: dict[str, float] = {}
    preset_labels: dict[str, str] = {}
    all_presets_for_meta = list(dict.fromkeys([*supported_presets, *DEFAULT_PRESETS, str(default_preset)]))
    for p_key in all_presets_for_meta:
        if climate_state:
            preset_temperatures[p_key] = round(get_preset_temperature(climate_state, p_key), 1)
        p_lower = p_key.lower().strip()
        if p_lower in PRESET_TRANSLATIONS:
            preset_labels[p_key] = PRESET_TRANSLATIONS[p_lower].get(lang, PRESET_TRANSLATIONS[p_lower]["en"])
        else:
            preset_labels[p_key] = p_key.replace("_", " ").title()

    eval_preset, preheat, cooldown, active_slot, next_slot, next_action, debug_info = evaluate_state(
        hass, entry_obj
    )
    if eval_preset and climate_state:
        target_temp = round(get_preset_temperature(climate_state, eval_preset), 1)
    elif climate_state and (climate_state.attributes or {}).get("temperature") is not None:
        target_temp = _safe_float(climate_state.attributes.get("temperature"), 20.0, allow_zero_or_negative=True)

    automation_enabled = bool(domain_data.get("automation_enabled", False)) if isinstance(domain_data, dict) else False
    overrides = copy.deepcopy(domain_data.get("overrides", {})) if isinstance(domain_data, dict) else {}

    # List all configured rooms so users/editor can switch or inspect
    available_rooms: list[dict[str, str]] = []
    for eid, ddata in hass.data.get(DOMAIN, {}).items():
        if not isinstance(ddata, dict) or eid.startswith("_"):
            continue
        ce = hass.config_entries.async_get_entry(eid)
        if ce:
            r_sched = resolve_entry_entity_id(
                hass,
                ce,
                "sensor",
                "schedule",
                runtime_key="main_sensor",
            )
            available_rooms.append(
                {
                    "entry_id": eid,
                    "name": ce.title or ce.data.get("name") or eid,
                    "entity_id": r_sched,
                }
            )

    return {
        "entry_id": entry_obj.entry_id,
        "room_name": entry_obj.title or entry_obj.data.get("name") or entry_obj.entry_id,
        "language": lang,
        "version": VERSION,
        "profiles": profiles,
        "active_profile": active_profile,
        "default_preset": default_preset,
        "supported_presets": supported_presets,
        "preset_temperatures": preset_temperatures,
        "preset_labels": preset_labels,
        "climate_entity": climate_entity,
        "schedule_entity_id": schedule_entity_id,
        "automation_switch_entity_id": automation_switch_entity_id,
        "profile_select_entity_id": profile_select_entity_id,
        "automation_enabled": automation_enabled,
        "current_temperature": current_temp,
        "target_temperature": target_temp,
        "active_preset": eval_preset,
        "hvac_mode": hvac_mode,
        "hvac_action": hvac_action,
        "preheat": preheat,
        "cooldown": cooldown,
        "active_slot": active_slot,
        "next_slot": next_slot,
        "next_action": next_action,
        "overrides": overrides,
        "heating_rate": debug_info.get("heating_rate") if isinstance(debug_info, dict) else None,
        "cooling_rate": debug_info.get("cooling_rate") if isinstance(debug_info, dict) else None,
        "available_rooms": available_rooms,
    }


async def _async_persist_profiles_and_apply(
    hass: Any,
    entry_obj: Any,
    domain_data: dict | None,
    profiles: dict[str, dict[str, list[dict[str, Any]]]],
    active_profile: str,
) -> None:
    """Persist updated profiles & active schedule quietly without triggering a full platform reload."""
    new_options = dict(entry_obj.options)
    new_options["profiles"] = profiles
    new_options["active_profile"] = active_profile
    new_options["schedule"] = copy.deepcopy(profiles.get(active_profile, {d: [] for d in DAYS}))

    if isinstance(domain_data, dict):
        domain_data["_updating_from_card"] = True
        invalidate_eval_cache(domain_data)

    hass.config_entries.async_update_entry(entry_obj, options=new_options)

    if isinstance(domain_data, dict):
        prof_sel = domain_data.get("profile_select")
        if prof_sel and hasattr(prof_sel, "async_write_ha_state"):
            prof_sel.async_write_ha_state()

        apply_fn = domain_data.get("async_apply_schedule")
        if callable(apply_fn):
            await apply_fn()

        update_all = domain_data.get("update_all_entities")
        if callable(update_all):
            update_all()

        resched = domain_data.get("reschedule_target_timer")
        if callable(resched):
            resched()


def _list_available_rooms(hass: Any) -> list[dict[str, str]]:
    """Return all configured Smart Climate Scheduler rooms with config_entry id and climate entity."""
    rooms: list[dict[str, str]] = []
    if not hass:
        return rooms
    for eid, ddata in hass.data.get(DOMAIN, {}).items():
        if not isinstance(ddata, dict) or eid.startswith("_"):
            continue
        ce = hass.config_entries.async_get_entry(eid)
        if not ce:
            continue
        r_sched = resolve_entry_entity_id(
            hass,
            ce,
            "sensor",
            "schedule",
            runtime_key="main_sensor",
        )
        cl_ent = (ce.options.get(CONF_CLIMATE_ENTITY) or ce.data.get(CONF_CLIMATE_ENTITY, "")).strip()
        rooms.append(
            {
                "entry_id": eid,
                "config_entry": eid,
                "name": ce.title or ce.data.get("name") or eid,
                "entity_id": r_sched,
                "climate_entity": cl_ent,
            }
        )
    rooms.sort(key=lambda item: item["name"].lower())
    return rooms


async def async_ws_list_entries(hass: Any, msg: dict[str, Any] | None = None) -> tuple[dict[str, Any], None]:
    """Return all configured Smart Climate Scheduler config entries for card & editor selection."""
    return {"entries": _list_available_rooms(hass)}, None


async def async_ws_get_schedule(hass: Any, msg: dict[str, Any]) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
    """Handle get_schedule WebSocket request."""
    entry_obj, domain_data = _resolve_target_entry(
        hass,
        entry_id=msg.get("config_entry") or msg.get("entry_id"),
        entity_id=msg.get("entity_id"),
    )
    if not entry_obj:
        return None, ("not_found", "Smart Climate Scheduler room entry not found")
    return _build_schedule_payload(hass, entry_obj, domain_data), None


async def async_ws_save_day_slots(hass: Any, msg: dict[str, Any]) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
    """Validate and save slots for a single weekday in the selected or active profile."""
    entry_obj, domain_data = _resolve_target_entry(
        hass,
        entry_id=msg.get("config_entry") or msg.get("entry_id"),
        entity_id=msg.get("entity_id"),
    )
    if not entry_obj:
        return None, ("not_found", "Smart Climate Scheduler room entry not found")

    day = str(msg.get("day", "")).strip().lower()
    if day not in DAYS:
        return None, ("invalid_day", f"Unsupported weekday: {day}")

    raw_slots = msg.get("slots", [])
    if not isinstance(raw_slots, list):
        return None, ("invalid_slots", "slots must be a list")

    cleaned_slots: list[dict[str, Any]] = []
    for idx, slot in enumerate(raw_slots):
        if not isinstance(slot, dict):
            return None, ("invalid_slot", f"Slot {idx} must be an object")
        from_norm = _normalize_time_str(slot.get("from"))
        to_norm = _normalize_time_str(slot.get("to"))
        if not from_norm or not to_norm or from_norm >= to_norm:
            return None, ("invalid_time_range", f"Slot {idx + 1} has invalid start/end times")
        preset = str(slot.get("preset") or "none").strip() or "none"
        cleaned_slots.append(
            {
                "from": from_norm,
                "to": to_norm,
                "preset": preset,
                "preheat": bool(slot.get("preheat", True)),
                "cooldown": bool(slot.get("cooldown", True)),
            }
        )
    cleaned_slots.sort(key=lambda item: item["from"])

    profiles, active_profile = _normalize_all_profiles(entry_obj)
    target_profile = str(msg.get("profile") or active_profile).strip() or active_profile
    if target_profile not in profiles:
        return None, ("profile_not_found", f"Profile '{target_profile}' does not exist")

    profiles[target_profile][day] = cleaned_slots
    await _async_persist_profiles_and_apply(hass, entry_obj, domain_data, profiles, active_profile)
    return _build_schedule_payload(hass, entry_obj, domain_data), None


async def async_ws_copy_day_slots(hass: Any, msg: dict[str, Any]) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
    """Copy slots from one weekday to one or more target weekdays."""
    entry_obj, domain_data = _resolve_target_entry(
        hass,
        entry_id=msg.get("config_entry") or msg.get("entry_id"),
        entity_id=msg.get("entity_id"),
    )
    if not entry_obj:
        return None, ("not_found", "Smart Climate Scheduler room entry not found")

    source_day = str(msg.get("source_day", "")).strip().lower()
    if source_day not in DAYS:
        return None, ("invalid_day", f"Unsupported source_day: {source_day}")

    raw_targets = msg.get("target_days", [])
    if not isinstance(raw_targets, list) or not raw_targets:
        return None, ("invalid_targets", "target_days must be a non-empty list")

    target_days = [str(d).strip().lower() for d in raw_targets if str(d).strip().lower() in DAYS and str(d).strip().lower() != source_day]
    if not target_days:
        return None, ("invalid_targets", "No valid target weekdays provided")

    profiles, active_profile = _normalize_all_profiles(entry_obj)
    target_profile = str(msg.get("profile") or active_profile).strip() or active_profile
    if target_profile not in profiles:
        return None, ("profile_not_found", f"Profile '{target_profile}' does not exist")

    source_slots = copy.deepcopy(profiles[target_profile].get(source_day, []))
    for t_day in target_days:
        profiles[target_profile][t_day] = copy.deepcopy(source_slots)

    await _async_persist_profiles_and_apply(hass, entry_obj, domain_data, profiles, active_profile)
    return _build_schedule_payload(hass, entry_obj, domain_data), None


async def async_ws_manage_profile(hass: Any, msg: dict[str, Any]) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
    """Switch, create, rename, or delete a schedule profile from the Lovelace card."""
    entry_obj, domain_data = _resolve_target_entry(
        hass,
        entry_id=msg.get("config_entry") or msg.get("entry_id"),
        entity_id=msg.get("entity_id"),
    )
    if not entry_obj:
        return None, ("not_found", "Smart Climate Scheduler room entry not found")

    action = str(msg.get("action", "")).strip().lower()
    profiles, active_profile = _normalize_all_profiles(entry_obj)

    if action == "switch":
        target = str(msg.get("profile", "")).strip()
        if target not in profiles:
            return None, ("profile_not_found", f"Profile '{target}' does not exist")
        active_profile = target
    elif action == "create":
        new_name = str(msg.get("new_name", "")).strip()
        if not new_name:
            return None, ("profile_name_empty", "Profile name must not be empty")
        if new_name in profiles:
            return None, ("profile_name_exists", f"Profile '{new_name}' already exists")
        source_profile = msg.get("source_profile")
        if source_profile and source_profile in profiles:
            profiles[new_name] = copy.deepcopy(profiles[source_profile])
        else:
            profiles[new_name] = _normalize_schedule_dict({})
        active_profile = new_name
    elif action == "rename":
        old_name = str(msg.get("profile", "")).strip()
        new_name = str(msg.get("new_name", "")).strip()
        if old_name not in profiles:
            return None, ("profile_not_found", f"Profile '{old_name}' does not exist")
        if not new_name:
            return None, ("profile_name_empty", "Profile name must not be empty")
        if new_name in profiles and new_name != old_name:
            return None, ("profile_name_exists", f"Profile '{new_name}' already exists")
        rebuilt: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for k, v in profiles.items():
            rebuilt[new_name if k == old_name else k] = v
        profiles = rebuilt
        if active_profile == old_name:
            active_profile = new_name
    elif action == "delete":
        target = str(msg.get("profile", "")).strip()
        if target not in profiles:
            return None, ("profile_not_found", f"Profile '{target}' does not exist")
        if len(profiles) <= 1:
            return None, ("cannot_delete_last", "Cannot delete the last remaining profile")
        profiles.pop(target)
        if active_profile == target:
            active_profile = list(profiles.keys())[0]
    else:
        return None, ("invalid_action", f"Unsupported profile action: {action}")

    await _async_persist_profiles_and_apply(hass, entry_obj, domain_data, profiles, active_profile)
    return _build_schedule_payload(hass, entry_obj, domain_data), None


async def _async_apply_automation_for_entry(
    hass: Any,
    entry_obj: Any,
    domain_data: dict | None,
    enabled: bool,
) -> dict[str, Any]:
    """Set automation on/off for a single ConfigEntry regardless of renamed switch entity_ids."""
    if not isinstance(domain_data, dict):
        domain_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_obj.entry_id, {})

    auto_switch = domain_data.get("automatic_switch")
    if auto_switch is not None and (
        hasattr(auto_switch, "async_turn_on") and hasattr(auto_switch, "async_turn_off")
    ):
        if enabled:
            await auto_switch.async_turn_on()
        else:
            await auto_switch.async_turn_off()
    else:
        domain_data["automation_enabled"] = enabled
        if enabled:
            domain_data["is_setting_preset"] = False
            domain_data["is_setting_hvac"] = False
        else:
            domain_data["two_point_target_reached"] = False
            domain_data["tolerance_kickstart_done"] = False
            domain_data["tolerance_kickstart_target"] = None
            await async_restore_tolerance(hass, domain_data, reason="automation_disabled")

        storage = domain_data.get("storage")
        if storage and hasattr(storage, "async_save_data"):
            await storage.async_save_data({"automation_enabled": enabled})

        if enabled:
            apply_fn = domain_data.get("async_apply_schedule")
            if callable(apply_fn):
                res = apply_fn()
                if hasattr(res, "__await__"):
                    await res

        update_all = domain_data.get("update_all_entities")
        if callable(update_all):
            update_all()

    return _build_schedule_payload(hass, entry_obj, domain_data)


async def async_ws_set_automation(hass: Any, msg: dict[str, Any]) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
    """Enable or disable room automation by config_entry/entry_id (single or bulk entry_ids)."""
    enabled = bool(msg.get("enabled"))
    raw_entry_ids = msg.get("entry_ids")

    if isinstance(raw_entry_ids, list):
        target_ids = [str(eid).strip() for eid in raw_entry_ids if str(eid).strip()]
        if not target_ids:
            return None, ("invalid_targets", "entry_ids must be a non-empty list")

        payloads: list[dict[str, Any]] = []
        for eid in target_ids:
            entry_obj, domain_data = _resolve_target_entry(hass, entry_id=eid)
            if entry_obj:
                payloads.append(await _async_apply_automation_for_entry(hass, entry_obj, domain_data, enabled))

        if not payloads:
            return None, ("not_found", "No matching Smart Climate Scheduler room entries found")
        return {"rooms": payloads, "updated_count": len(payloads)}, None

    entry_obj, domain_data = _resolve_target_entry(
        hass,
        entry_id=msg.get("config_entry") or msg.get("entry_id"),
        entity_id=msg.get("entity_id"),
    )
    if not entry_obj:
        return None, ("not_found", "Smart Climate Scheduler room entry not found")

    payload = await _async_apply_automation_for_entry(hass, entry_obj, domain_data, enabled)
    return payload, None


async def async_register_frontend_and_ws(hass: Any) -> None:
    """Register static frontend asset route, auto-load Lovelace JS URL, and register WS commands once."""
    if not hass:
        return

    reg_key = f"{DOMAIN}_frontend_registered"
    if hass.data.get(reg_key):
        return
    hass.data[reg_key] = True

    frontend_dir = Path(__file__).parent / "frontend"
    card_url = get_card_js_url(VERSION)

    # 1. Serve embedded Lovelace card directory over Home Assistant HTTP (HA 2025.1+)
    try:
        if hasattr(hass, "http") and hass.http is not None:
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [StaticPathConfig(FRONTEND_URL_BASE, str(frontend_dir), False)]
            )
    except Exception as err:
        _LOGGER.warning("Konnte statischen Frontend-Pfad '%s' nicht registrieren: %s", FRONTEND_URL_BASE, err)

    # 2. Register module JS globally via HA Frontend add_extra_js_url (works in Storage & YAML dashboards)
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, card_url)
    except Exception as err:
        _LOGGER.debug("add_extra_js_url nicht verfügbar (%s) - manuelle Lovelace-Ressource '%s' nutzen.", err, card_url)

    # 3. Register WebSocket API commands
    try:
        import voluptuous as vol
        from homeassistant.components import websocket_api

        @websocket_api.websocket_command(
            {
                vol.Required("type"): f"{DOMAIN}/list_entries",
            }
        )
        @websocket_api.async_response
        async def _ws_list_entries(hass_obj, connection, msg):
            res, _ = await async_ws_list_entries(hass_obj, msg)
            connection.send_result(msg["id"], res)

        @websocket_api.websocket_command(
            {
                vol.Required("type"): f"{DOMAIN}/get_schedule",
                vol.Optional("config_entry"): str,
                vol.Optional("entry_id"): str,
                vol.Optional("entity_id"): str,
            }
        )
        @websocket_api.async_response
        async def _ws_get_schedule(hass_obj, connection, msg):
            res, err = await async_ws_get_schedule(hass_obj, msg)
            if err:
                connection.send_error(msg["id"], err[0], err[1])
            else:
                connection.send_result(msg["id"], res)

        @websocket_api.websocket_command(
            {
                vol.Required("type"): f"{DOMAIN}/save_day_slots",
                vol.Optional("config_entry"): str,
                vol.Optional("entry_id"): str,
                vol.Optional("entity_id"): str,
                vol.Optional("profile"): str,
                vol.Required("day"): str,
                vol.Required("slots"): list,
            }
        )
        @websocket_api.async_response
        async def _ws_save_day_slots(hass_obj, connection, msg):
            res, err = await async_ws_save_day_slots(hass_obj, msg)
            if err:
                connection.send_error(msg["id"], err[0], err[1])
            else:
                connection.send_result(msg["id"], res)

        @websocket_api.websocket_command(
            {
                vol.Required("type"): f"{DOMAIN}/copy_day_slots",
                vol.Optional("config_entry"): str,
                vol.Optional("entry_id"): str,
                vol.Optional("entity_id"): str,
                vol.Optional("profile"): str,
                vol.Required("source_day"): str,
                vol.Required("target_days"): list,
            }
        )
        @websocket_api.async_response
        async def _ws_copy_day_slots(hass_obj, connection, msg):
            res, err = await async_ws_copy_day_slots(hass_obj, msg)
            if err:
                connection.send_error(msg["id"], err[0], err[1])
            else:
                connection.send_result(msg["id"], res)

        @websocket_api.websocket_command(
            {
                vol.Required("type"): f"{DOMAIN}/manage_profile",
                vol.Optional("config_entry"): str,
                vol.Optional("entry_id"): str,
                vol.Optional("entity_id"): str,
                vol.Required("action"): str,
                vol.Optional("profile"): str,
                vol.Optional("new_name"): str,
                vol.Optional("source_profile"): str,
            }
        )
        @websocket_api.async_response
        async def _ws_manage_profile(hass_obj, connection, msg):
            res, err = await async_ws_manage_profile(hass_obj, msg)
            if err:
                connection.send_error(msg["id"], err[0], err[1])
            else:
                connection.send_result(msg["id"], res)

        @websocket_api.websocket_command(
            {
                vol.Required("type"): f"{DOMAIN}/set_automation",
                vol.Required("enabled"): bool,
                vol.Optional("config_entry"): str,
                vol.Optional("entry_id"): str,
                vol.Optional("entity_id"): str,
                vol.Optional("entry_ids"): list,
            }
        )
        @websocket_api.async_response
        async def _ws_set_automation(hass_obj, connection, msg):
            res, err = await async_ws_set_automation(hass_obj, msg)
            if err:
                connection.send_error(msg["id"], err[0], err[1])
            else:
                connection.send_result(msg["id"], res)

        websocket_api.async_register_command(hass, _ws_list_entries)
        websocket_api.async_register_command(hass, _ws_get_schedule)
        websocket_api.async_register_command(hass, _ws_save_day_slots)
        websocket_api.async_register_command(hass, _ws_copy_day_slots)
        websocket_api.async_register_command(hass, _ws_manage_profile)
        websocket_api.async_register_command(hass, _ws_set_automation)
    except Exception as err:
        _LOGGER.debug("WebSocket-Registrierung übersprungen (%s)", err)
