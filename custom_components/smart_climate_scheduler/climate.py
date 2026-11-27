"""Optionale Climate-Plattform (Raum-Wrapper) für Smart Climate Scheduler (Version 4.0.0)."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CLIMATE_MANUAL_OVERRIDE_ID,
    DOMAIN,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
)
from .evaluation import evaluate_state, invalidate_eval_cache
from .helpers import (
    async_cleanup_virtual_climate_entity,
    async_write_ha_state_if_enabled,
    get_climate_entities,
    get_config_entry_slug,
    get_custom_presets,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
    get_preset_temperature,
    get_profiles_and_active,
    get_raw_window_open,
    get_room_current_temperature,
    get_target_hvac_mode,
    get_window_delays,
    is_climate_entity_enabled,
    resolve_preset_key,
)
from .timeline import get_next_regular_slot_start

_LOGGER = logging.getLogger(__name__)


def _normalize_mode_value(raw: Any) -> str:
    """Normalisiert HVACMode-Enums oder Strings auf Kleinbuchstaben ('auto', 'heat', 'off')."""
    if hasattr(raw, "value"):
        raw = raw.value
    return str(raw or "").strip().lower()


def _clamp_target_temp(raw_temp: Any) -> float | None:
    """Klemmt eine Zieltemperatur auf [MIN_TARGET_TEMP, MAX_TARGET_TEMP] mit 0,1 °C Präzision."""
    if raw_temp is None:
        return None
    try:
        val = float(raw_temp)
        if math.isnan(val) or math.isinf(val):
            return None
        return round(max(MIN_TARGET_TEMP, min(MAX_TARGET_TEMP, val)), 1)
    except (ValueError, TypeError):
        return None


def _build_supported_features() -> Any:
    """Ermittelt ClimateEntityFeature-Flags kompatibel mit verschiedenen HA-Versionen."""
    features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    for attr_name in ("TURN_ON", "TURN_OFF"):
        flag = getattr(ClimateEntityFeature, attr_name, None)
        if flag is not None:
            try:
                features = features | flag
            except TypeError:
                pass
    return features


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die optionale Raum-Climate-Plattform über einen Config Entry ein."""
    domain_data = hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})

    if not is_climate_entity_enabled(config_entry):
        domain_data.pop("climate_entity", None)
        await async_cleanup_virtual_climate_entity(hass, config_entry)
        return

    entity = SmartClimateSchedulerClimate(hass, config_entry)
    domain_data["climate_entity"] = entity

    sensors = hass.data.setdefault(f"{DOMAIN}_sensors", [])
    sensors[:] = [
        ent
        for ent in sensors
        if not (
            getattr(ent, "unique_id", None) == entity.unique_id
            or getattr(ent, "_attr_unique_id", None) == entity.unique_id
        )
    ]
    sensors.append(entity)

    async_add_entities([entity], True)


class SmartClimateSchedulerClimate(ClimateEntity):
    """Optionale Raum-Thermostat-Entität (reiner Wrapper ohne PID-/Offset-Regelung)."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = getattr(UnitOfTemperature, "CELSIUS", "°C")
    _attr_min_temp = MIN_TARGET_TEMP
    _attr_max_temp = MAX_TARGET_TEMP
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = _build_supported_features()
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_climate"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass)
        suffix = get_localized_slug_suffix("room_thermostat", lang)
        self.entity_id = f"climate.{slug}_{suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Raum-Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    def _get_domain_data(self) -> dict[str, Any]:
        if not self.hass or not isinstance(getattr(self.hass, "data", None), dict):
            return {}
        return self.hass.data.setdefault(DOMAIN, {}).setdefault(self.config_entry.entry_id, {})

    async def _async_persist_storage(self, updates: dict[str, Any]) -> None:
        domain_data = self._get_domain_data()
        storage = domain_data.get("storage")
        if storage and hasattr(storage, "async_save_data"):
            try:
                await storage.async_save_data(updates)
            except Exception as err:
                _LOGGER.debug(
                    "Smart Climate Scheduler Climate [%s]: Storage-Speichern fehlgeschlagen: %s",
                    self.config_entry.entry_id,
                    err,
                )

    def _sync_automatic_switch(self, enabled: bool) -> None:
        domain_data = self._get_domain_data()
        domain_data["automation_enabled"] = bool(enabled)
        if not enabled:
            domain_data["two_point_target_reached"] = False
            domain_data["opportunistic_kickstart"] = False
            domain_data["opportunistic_kickstart_done"] = False
            domain_data["opportunistic_kickstart_target"] = None
        else:
            domain_data["is_setting_preset"] = False
            domain_data["is_setting_hvac"] = False

        auto_switch = domain_data.get("automatic_switch")
        if auto_switch is not None:
            auto_switch._is_on = bool(enabled)
            async_write_ha_state_if_enabled(auto_switch)

    def _refresh_room_entities(self) -> None:
        domain_data = self._get_domain_data()
        invalidate_eval_cache(domain_data)
        update_all = domain_data.get("update_all_entities")
        if callable(update_all):
            update_all()
        else:
            for ent in self.hass.data.get(f"{DOMAIN}_sensors", []):
                if getattr(ent, "config_entry", None) and ent.config_entry.entry_id == self.config_entry.entry_id:
                    async_write_ha_state_if_enabled(ent)
            async_write_ha_state_if_enabled(self)

        resched = domain_data.get("reschedule_target_timer")
        if callable(resched):
            resched()

    def _compute_room_snapshot(self) -> dict[str, Any]:
        """Berechnet Ist-Temperatur, Fensterpause und aktiven Heizbedarf aus den physischen TRVs."""
        climate_entities = get_climate_entities(self.config_entry)
        domain_data = self._get_domain_data()
        _, _, win_pause_enabled = get_window_delays(self.config_entry)
        win_state = domain_data.get("window_state")
        if isinstance(win_state, dict) and win_state.get("initialized"):
            effective_win_open = bool(win_state.get("effective_open", False))
        else:
            effective_win_open, _ = get_raw_window_open(self.hass, self.config_entry, climate_entities)
        window_paused = bool(effective_win_open and win_pause_enabled)

        current_temp, room_temp_source = get_room_current_temperature(
            self.hass, self.config_entry, climate_entities
        )

        heating_thermostats: list[str] = []
        any_trv_active = False
        primary_state = None
        states_mgr = getattr(self.hass, "states", None)
        for cl_id in climate_entities:
            st = states_mgr.get(cl_id) if states_mgr else None
            if not st:
                continue
            mode = str(getattr(st, "state", "") or "").strip().lower()
            if mode in ("unavailable", "unknown", "none", ""):
                continue
            if primary_state is None:
                primary_state = st
            if mode == "off":
                continue
            any_trv_active = True
            attrs = getattr(st, "attributes", None) or {}
            hvac_act = attrs.get("hvac_action")
            if hvac_act is not None and str(hvac_act).strip() != "":
                if str(hvac_act).strip().lower() == "heating":
                    heating_thermostats.append(cl_id)
            else:
                local_curr = current_temp
                if local_curr is None and attrs.get("current_temperature") is not None:
                    local_curr = _clamp_target_temp(attrs.get("current_temperature"))
                t_val = _clamp_target_temp(attrs.get("temperature"))
                if mode in ("heat", "auto", "heat_cool"):
                    if local_curr is not None and t_val is not None:
                        if local_curr < t_val:
                            heating_thermostats.append(cl_id)
                    elif mode == "heat":
                        heating_thermostats.append(cl_id)

        return {
            "climate_entities": climate_entities,
            "primary_state": primary_state,
            "current_temp": round(float(current_temp), 1) if current_temp is not None else None,
            "room_temp_source": room_temp_source,
            "window_open": effective_win_open,
            "window_paused": window_paused,
            "heating_thermostats": heating_thermostats,
            "heating_demand": (not window_paused) and bool(heating_thermostats),
            "any_trv_active": any_trv_active,
        }

    def _resolve_evaluated_target_temp(self, primary_state: Any) -> tuple[float, str, dict | None, dict | None, dict | None]:
        """Liefert effektive Solltemperatur, Preset, Preheat, Cooldown und active_slot aus evaluate_state."""
        preset, preheat, cooldown, active_slot, _, _, _ = evaluate_state(self.hass, self.config_entry)
        override_temp = None
        if isinstance(active_slot, dict) and active_slot.get("is_override"):
            override_temp = _clamp_target_temp(active_slot.get("temperature"))
        if override_temp is not None:
            return override_temp, preset, preheat, cooldown, active_slot

        custom_presets = get_custom_presets(self.config_entry)
        preset_temp = get_preset_temperature(
            primary_state,
            preset,
            config_entry=self.config_entry,
            custom_presets=custom_presets,
        )
        clamped = _clamp_target_temp(preset_temp)
        return (clamped if clamped is not None else 20.0), preset, preheat, cooldown, active_slot

    @property
    def native_current_temperature(self) -> float | None:
        """Aktuelle Raumtemperatur (externer Raumsensor vor TRV-Durchschnitt)."""
        return self._compute_room_snapshot()["current_temp"]

    @property
    def hvac_mode(self) -> HVACMode:
        """Aktueller Betriebsmodus: AUTO (Zeitplan), HEAT (Manuell) oder OFF (Aus)."""
        domain_data = self._get_domain_data()
        if domain_data.get("automation_enabled", False):
            return HVACMode.AUTO

        stored_mode = _normalize_mode_value(domain_data.get("climate_mode"))
        if stored_mode == "off":
            return HVACMode.OFF
        if stored_mode == "heat":
            return HVACMode.HEAT

        snap = self._compute_room_snapshot()
        return HVACMode.HEAT if snap["any_trv_active"] else HVACMode.OFF

    @property
    def native_target_temperature(self) -> float | None:
        """Effektive Solltemperatur (im AUTO-Modus aus Zeitplan/Override, sonst manuelle Solltemperatur)."""
        snap = self._compute_room_snapshot()
        cur_mode = self.hvac_mode
        if cur_mode == HVACMode.AUTO:
            tgt, _, _, _, _ = self._resolve_evaluated_target_temp(snap["primary_state"])
            return tgt

        domain_data = self._get_domain_data()
        manual_t = _clamp_target_temp(domain_data.get("manual_temperature"))
        if manual_t is not None:
            return manual_t

        primary_state = snap["primary_state"]
        if primary_state is not None:
            trv_t = _clamp_target_temp((getattr(primary_state, "attributes", None) or {}).get("temperature"))
            if trv_t is not None:
                return trv_t

        tgt, _, _, _, _ = self._resolve_evaluated_target_temp(primary_state)
        return tgt

    @property
    def hvac_action(self) -> HVACAction:
        """Live-Heizstatus abgeleitet aus Modus, Fensterpause und physischen TRVs."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        snap = self._compute_room_snapshot()
        if snap["window_paused"]:
            return HVACAction.OFF
        if snap["heating_demand"]:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_modes(self) -> list[str]:
        """Verfügbare Raum-Presets plus 'none' zum Beenden eines manuellen Overrides."""
        custom_presets = get_custom_presets(self.config_entry)
        modes = ["none"]
        for p in custom_presets:
            pid = str(p.get("id") or "").strip().lower()
            if pid and pid not in modes:
                modes.append(pid)
        return modes

    @property
    def preset_mode(self) -> str:
        """Aktives Preset im AUTO-Modus; 'none' bei manuellem Dauerbetrieb, Aus oder freiem Temp-Override."""
        if self.hvac_mode != HVACMode.AUTO:
            return "none"
        snap = self._compute_room_snapshot()
        _, preset, _, _, active_slot = self._resolve_evaluated_target_temp(snap["primary_state"])
        if (
            isinstance(active_slot, dict)
            and active_slot.get("is_override")
            and active_slot.get("temperature") is not None
            and str(active_slot.get("preset") or "none").strip().lower() == "none"
        ):
            return "none"
        valid = self.preset_modes
        return preset if preset in valid else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Transparente Raum-Diagnoseattribute (ohne eigene Regelungs-Parameter)."""
        snap = self._compute_room_snapshot()
        _, _, preheat, cooldown, active_slot = self._resolve_evaluated_target_temp(snap["primary_state"])
        _, active_profile = get_profiles_and_active(self.config_entry)
        domain_data = self._get_domain_data()
        is_override = bool(isinstance(active_slot, dict) and active_slot.get("is_override"))
        override_id = active_slot.get("override_id") if is_override else None
        override_temp = (
            _clamp_target_temp(active_slot.get("temperature"))
            if is_override and isinstance(active_slot, dict)
            else None
        )
        override_end = None
        if override_id:
            ov_entry = domain_data.get("overrides", {}).get(override_id)
            if isinstance(ov_entry, dict):
                override_end = ov_entry.get("end")

        return {
            "climate_entities": snap["climate_entities"],
            "room_temp_source": snap["room_temp_source"],
            "window_open": snap["window_open"],
            "window_pause_active": snap["window_paused"],
            "heating_demand": snap["heating_demand"],
            "heating_thermostats": snap["heating_thermostats"],
            "active_profile": active_profile,
            "preheat_active": bool(preheat and preheat.get("is_preheating", False)),
            "cooldown_active": bool(cooldown and cooldown.get("is_cooling_down", False)),
            "is_override": is_override,
            "override_id": override_id,
            "override_end": override_end,
            "override_temperature": override_temp,
        }

    async def _async_push_trvs_manual_heat(self, target_temp: float) -> None:
        """Fallback-Direktsteuerung der physischen TRVs im manuellen HEAT-Modus (mit Fensterpause)."""
        climate_entities = get_climate_entities(self.config_entry)
        if not climate_entities:
            return
        snap = self._compute_room_snapshot()
        states_mgr = getattr(self.hass, "states", None)
        for cl_id in climate_entities:
            st_obj = states_mgr.get(cl_id) if states_mgr else None
            if not st_obj or st_obj.state in ("unavailable", "unknown", "None", None):
                continue
            if snap["window_paused"]:
                if str(st_obj.state).lower() != "off":
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        service_data={"hvac_mode": "off"},
                        target={"entity_id": cl_id},
                        blocking=False,
                    )
                continue
            if str(st_obj.state).lower() == "off":
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    service_data={"hvac_mode": get_target_hvac_mode(st_obj)},
                    target={"entity_id": cl_id},
                    blocking=False,
                )
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                service_data={"temperature": target_temp},
                target={"entity_id": cl_id},
                blocking=False,
            )

    async def _async_turn_off_physical_trvs(self) -> None:
        """Schaltet alle erreichbaren physischen Thermostate des Raums auf 'off'."""
        climate_entities = get_climate_entities(self.config_entry)
        states_mgr = getattr(self.hass, "states", None)
        for cl_id in climate_entities:
            st_obj = states_mgr.get(cl_id) if states_mgr else None
            if not st_obj or st_obj.state in ("unavailable", "unknown", "None", None):
                continue
            if str(st_obj.state).lower() != "off":
                try:
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        service_data={"hvac_mode": "off"},
                        target={"entity_id": cl_id},
                        blocking=False,
                    )
                except Exception as err:
                    _LOGGER.error(
                        "Smart Climate Scheduler Climate [%s]: Fehler beim Ausschalten von '%s': %s",
                        self.config_entry.entry_id,
                        cl_id,
                        err,
                    )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode | str) -> None:
        """Wechselt zwischen AUTO (Zeitplan), HEAT (Manuell) und OFF (Aus)."""
        mode_str = _normalize_mode_value(hvac_mode)
        if mode_str not in ("auto", "heat", "off"):
            _LOGGER.warning("Nicht unterstützter HVAC-Modus '%s' für %s", hvac_mode, self.entity_id)
            return

        domain_data = self._get_domain_data()
        apply_fn = domain_data.get("async_apply_schedule")

        if mode_str == "auto":
            domain_data["climate_mode"] = "auto"
            domain_data["_last_active_climate_mode"] = "auto"
            self._sync_automatic_switch(True)
            await self._async_persist_storage({"automation_enabled": True, "climate_mode": "auto"})
            if callable(apply_fn):
                await apply_fn()
            self._refresh_room_entities()
            return

        if mode_str == "heat":
            current_target = self.native_target_temperature
            manual_temp = _clamp_target_temp(domain_data.get("manual_temperature"))
            if manual_temp is None:
                manual_temp = current_target if current_target is not None else 20.0
            domain_data["manual_temperature"] = manual_temp
            domain_data["climate_mode"] = "heat"
            domain_data["_last_active_climate_mode"] = "heat"
            self._sync_automatic_switch(False)
            await self._async_persist_storage(
                {
                    "automation_enabled": False,
                    "climate_mode": "heat",
                    "manual_temperature": manual_temp,
                }
            )
            if callable(apply_fn):
                await apply_fn()
            else:
                await self._async_push_trvs_manual_heat(manual_temp)
            self._refresh_room_entities()
            return

        # mode_str == "off"
        if self.hvac_mode in (HVACMode.AUTO, HVACMode.HEAT):
            domain_data["_last_active_climate_mode"] = _normalize_mode_value(self.hvac_mode)
        domain_data["climate_mode"] = "off"
        self._sync_automatic_switch(False)
        await self._async_persist_storage({"automation_enabled": False, "climate_mode": "off"})
        await self._async_turn_off_physical_trvs()
        self._refresh_room_entities()

    async def async_turn_on(self) -> None:
        """Schaltet den Raum wieder ein (Standard: letzter aktiver Modus bzw. AUTO)."""
        domain_data = self._get_domain_data()
        last_mode = _normalize_mode_value(domain_data.get("_last_active_climate_mode"))
        await self.async_set_hvac_mode(HVACMode.HEAT if last_mode == "heat" else HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Schaltet den Raum aus (HVACMode.OFF)."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Setzt die Zieltemperatur (in AUTO als Override bis zum nächsten Zeitplan-Wechsel, in HEAT dauerhaft)."""
        temp_key = ATTR_TEMPERATURE if isinstance(ATTR_TEMPERATURE, str) else "temperature"
        raw_temp = kwargs.get(temp_key, kwargs.get("temperature"))
        clamped_temp = _clamp_target_temp(raw_temp)
        requested_mode_raw = kwargs.get("hvac_mode")
        requested_mode = _normalize_mode_value(requested_mode_raw) if requested_mode_raw is not None else ""

        domain_data = self._get_domain_data()
        apply_fn = domain_data.get("async_apply_schedule")

        if clamped_temp is None:
            if requested_mode in ("auto", "heat", "off"):
                await self.async_set_hvac_mode(requested_mode)
            return

        if requested_mode == "off":
            domain_data["manual_temperature"] = clamped_temp
            await self._async_persist_storage({"manual_temperature": clamped_temp})
            await self.async_set_hvac_mode(HVACMode.OFF)
            return

        if requested_mode == "heat":
            domain_data["manual_temperature"] = clamped_temp
            await self.async_set_hvac_mode(HVACMode.HEAT)
            return

        if requested_mode == "auto" and self.hvac_mode != HVACMode.AUTO:
            domain_data["climate_mode"] = "auto"
            domain_data["_last_active_climate_mode"] = "auto"
            self._sync_automatic_switch(True)
            await self._async_persist_storage({"automation_enabled": True, "climate_mode": "auto"})

        cur_mode = self.hvac_mode

        if cur_mode == HVACMode.AUTO:
            now_dt = dt_util.now()
            end_dt = get_next_regular_slot_start(self.config_entry, now_dt)
            overrides = domain_data.setdefault("overrides", {})
            overrides[CLIMATE_MANUAL_OVERRIDE_ID] = {
                "start": now_dt.isoformat(),
                "end": end_dt.isoformat(),
                "preset": "none",
                "temperature": clamped_temp,
                "created_at": now_dt.isoformat(),
            }
            _LOGGER.info(
                "Climate-Override [%s]: %.1f °C bis %s (nächster Zeitplan-Wechsel)",
                self.entity_id,
                clamped_temp,
                end_dt.isoformat(),
            )
            invalidate_eval_cache(domain_data)
            await self._async_persist_storage({"overrides": overrides})
            if callable(apply_fn):
                await apply_fn()
            else:
                await self._async_push_trvs_manual_heat(clamped_temp)
            self._refresh_room_entities()
            return

        # In HEAT oder OFF: manuelle Zieltemperatur übernehmen (aus OFF heraus direkt in HEAT wechseln)
        domain_data["manual_temperature"] = clamped_temp
        domain_data["climate_mode"] = "heat"
        domain_data["_last_active_climate_mode"] = "heat"
        self._sync_automatic_switch(False)
        await self._async_persist_storage(
            {
                "automation_enabled": False,
                "climate_mode": "heat",
                "manual_temperature": clamped_temp,
            }
        )
        if callable(apply_fn):
            await apply_fn()
        else:
            await self._async_push_trvs_manual_heat(clamped_temp)
        self._refresh_room_entities()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Aktiviert ein Raum-Preset als temporären Override bis zum nächsten Zeitplan-Wechsel ('none' hebt ihn auf)."""
        raw_p = str(preset_mode or "").strip().lower()
        domain_data = self._get_domain_data()
        overrides = domain_data.setdefault("overrides", {})
        apply_fn = domain_data.get("async_apply_schedule")

        if raw_p in ("", "none"):
            if CLIMATE_MANUAL_OVERRIDE_ID in overrides:
                overrides.pop(CLIMATE_MANUAL_OVERRIDE_ID, None)
                invalidate_eval_cache(domain_data)
                await self._async_persist_storage({"overrides": overrides})
            if self.hvac_mode == HVACMode.AUTO and callable(apply_fn):
                await apply_fn()
            self._refresh_room_entities()
            return

        resolved = resolve_preset_key(raw_p, self.config_entry)
        if resolved not in self.preset_modes:
            _LOGGER.warning("Unbekanntes Preset '%s' für %s", preset_mode, self.entity_id)
            return

        if self.hvac_mode != HVACMode.AUTO:
            domain_data["climate_mode"] = "auto"
            domain_data["_last_active_climate_mode"] = "auto"
            self._sync_automatic_switch(True)

        now_dt = dt_util.now()
        end_dt = get_next_regular_slot_start(self.config_entry, now_dt)
        overrides[CLIMATE_MANUAL_OVERRIDE_ID] = {
            "start": now_dt.isoformat(),
            "end": end_dt.isoformat(),
            "preset": resolved,
            "created_at": now_dt.isoformat(),
        }
        _LOGGER.info(
            "Climate-Preset-Override [%s]: Preset '%s' bis %s (nächster Zeitplan-Wechsel)",
            self.entity_id,
            resolved,
            end_dt.isoformat(),
        )
        invalidate_eval_cache(domain_data)
        await self._async_persist_storage(
            {
                "automation_enabled": True,
                "climate_mode": "auto",
                "overrides": overrides,
            }
        )
        if callable(apply_fn):
            await apply_fn()
        self._refresh_room_entities()
