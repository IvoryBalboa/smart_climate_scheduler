"""Binary-Sensor Plattform für Smart Climate Scheduler (Version 4.0.0)."""
from __future__ import annotations

import logging
import math
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .anomaly import evaluate_and_update_anomaly
from .const import (
    CONF_ANOMALY_DETECTION_ENABLED,
    CONF_COOLDOWN_ENABLED,
    CONF_PREHEAT_ENABLED,
    DEFAULT_ANOMALY_DETECTION_ENABLED,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_PREHEAT_ENABLED,
    DOMAIN,
)
from .evaluation import evaluate_state
from .helpers import (
    async_sync_entity_registry_disabled,
    get_climate_entities,
    get_config_entry_slug,
    get_custom_presets,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
    get_preset_temperature,
    get_raw_window_open,
    get_room_current_temperature,
    get_window_delays,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Binary-Sensor Plattform über einen Config Entry ein."""
    preheat_binary = SmartClimateSchedulerPreheatBinarySensor(config_entry, hass=hass)
    cooldown_binary = SmartClimateSchedulerCooldownBinarySensor(config_entry, hass=hass)
    anomaly_binary = SmartClimateSchedulerAnomalyBinarySensor(config_entry, hass=hass)
    heating_demand_binary = SmartClimateSchedulerHeatingDemandBinarySensor(config_entry, hass=hass)

    domain_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id) if hasattr(hass, "data") else None
    if isinstance(domain_data, dict):
        domain_data["anomaly_binary_sensor"] = anomaly_binary
        domain_data["heating_demand_binary_sensor"] = heating_demand_binary

    sensors = hass.data.setdefault(f"{DOMAIN}_sensors", [])
    sensors.extend([preheat_binary, cooldown_binary, anomaly_binary, heating_demand_binary])

    async_add_entities([preheat_binary, cooldown_binary, anomaly_binary, heating_demand_binary], True)
    await async_sync_entity_registry_disabled(hass, config_entry)


class SmartClimateSchedulerPreheatBinarySensor(BinarySensorEntity):
    """Binary-Sensor für den aktiven Zustand des Vorheizens (Preheat)."""

    _attr_icon = "mdi:radiator"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_has_entity_name = True
    _attr_translation_key = "preheat"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_preheat"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("binary_preheat", lang)
        self.entity_id = f"binary_sensor.{slug}_{suffix}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Legt fest, ob der Sensor standardmäßig aktiviert ist."""
        return bool(
            self.config_entry.options.get(
                CONF_PREHEAT_ENABLED,
                self.config_entry.data.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED),
            )
        )

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def is_on(self) -> bool:
        """Gibt an, ob aktuell die vorgezogene Aufheizphase (Preheat) aktiv ist."""
        if not self.hass:
            return False
        _, preheat, _, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
        return bool(preheat and preheat.get("is_preheating", False))

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt alle Detailattribute des Preheat-Vorgangs zurück."""
        if not self.hass:
            return {"start_time": None, "duration_minutes": 0, "effective_rate_k_h": None}
        _, preheat, _, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
        if not preheat or not isinstance(preheat, dict):
            return {
                "start_time": None,
                "duration_minutes": 0,
                "effective_rate_k_h": None,
            }
        return {
            "start_time": preheat.get("start_time"),
            "duration_minutes": preheat.get("duration_minutes", 0),
            "effective_rate_k_h": preheat.get("effective_rate_k_h"),
        }


class SmartClimateSchedulerCooldownBinarySensor(BinarySensorEntity):
    """Binary-Sensor für den aktiven Zustand des vorzeitigen Abkühlens (Cooldown)."""

    _attr_icon = "mdi:snowflake-thermometer"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_has_entity_name = True
    _attr_translation_key = "cooldown"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_cooldown"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("binary_cooldown", lang)
        self.entity_id = f"binary_sensor.{slug}_{suffix}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Legt fest, ob der Sensor standardmäßig aktiviert ist."""
        return bool(
            self.config_entry.options.get(
                CONF_COOLDOWN_ENABLED,
                self.config_entry.data.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED),
            )
        )

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def is_on(self) -> bool:
        """Gibt an, ob aktuell die vorgezogene Abkühlphase (Cooldown) aktiv ist."""
        if not self.hass:
            return False
        _, _, cooldown, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
        return bool(cooldown and cooldown.get("is_cooling_down", False))

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt alle Detailattribute des Cooldown-Vorgangs zurück."""
        if not self.hass:
            return {"start_time": None, "duration_minutes": 0, "effective_loss_rate_k_h": None}
        _, _, cooldown, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
        if not cooldown or not isinstance(cooldown, dict):
            return {
                "start_time": None,
                "duration_minutes": 0,
                "effective_loss_rate_k_h": None,
            }
        return {
            "start_time": cooldown.get("start_time"),
            "duration_minutes": cooldown.get("duration_minutes", 0),
            "effective_loss_rate_k_h": cooldown.get("effective_loss_rate_k_h"),
            "target_preset": cooldown.get("target_preset"),
        }


class SmartClimateSchedulerAnomalyBinarySensor(BinarySensorEntity):
    """Binary-Sensor (Problem) für brenner-sensitive Heiz- und Hardware-Anomalien."""

    _attr_icon = "mdi:thermometer-alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "anomaly"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        if hass is not None:
            self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_anomaly"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("binary_anomaly", lang)
        self.entity_id = f"binary_sensor.{slug}_{suffix}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Legt fest, ob der Problem-Sensor standardmäßig aktiviert ist."""
        return bool(
            self.config_entry.options.get(
                CONF_ANOMALY_DETECTION_ENABLED,
                self.config_entry.data.get(CONF_ANOMALY_DETECTION_ENABLED, DEFAULT_ANOMALY_DETECTION_ENABLED),
            )
        )

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Anomalie-Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    def _evaluate_snapshot(self) -> dict:
        hass_obj = getattr(self, "hass", None)
        if not hass_obj:
            return {"active": False, "primary_type": None, "anomalies": []}
        domain_data = (
            hass_obj.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if isinstance(getattr(hass_obj, "data", None), dict)
            else None
        )
        return evaluate_and_update_anomaly(hass_obj, self.config_entry, domain_data)

    @property
    def is_on(self) -> bool:
        """Gibt True zurück, sobald eine Heiz- oder Hardware-Anomalie erkannt wurde."""
        snap = self._evaluate_snapshot()
        return bool(snap.get("active", False))

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt Detail-Informationen zur erkannten Anomalie inklusive Brenner-Kontext zurück."""
        snap = self._evaluate_snapshot()
        return {
            "primary_type": snap.get("primary_type"),
            "anomalies": snap.get("anomalies", []),
            "detected_since": snap.get("detected_since"),
            "no_heat_threshold_minutes": snap.get("no_heat_threshold_minutes"),
            "heating_watch_minutes": snap.get("heating_watch_minutes", 0.0),
            "temp_delta": snap.get("temp_delta"),
            "unchanged_minutes": snap.get("unchanged_minutes", 0.0),
            "unavailable_threshold_minutes": snap.get("unavailable_threshold_minutes"),
            "unavailable_minutes": snap.get("unavailable_minutes", 0.0),
            "burner_configured": snap.get("burner_configured", False),
            "burner_active": snap.get("burner_active", False),
            "thermostat_heating": snap.get("thermostat_heating", False),
            "window_open": snap.get("window_open", False),
        }


class SmartClimateSchedulerHeatingDemandBinarySensor(BinarySensorEntity):
    """Binary-Sensor für den aktiven Wärmebedarf (Heizbedarf) eines Raums."""

    _attr_icon = "mdi:fire"
    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_has_entity_name = True
    _attr_translation_key = "heating_demand"

    def __init__(self, config_entry: ConfigEntry, hass: HomeAssistant | None = None) -> None:
        self.config_entry = config_entry
        if hass is not None:
            self.hass = hass
        self._attr_unique_id = f"{config_entry.entry_id}_heating_demand"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("binary_heating_demand", lang)
        self.entity_id = f"binary_sensor.{slug}_{suffix}"

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Heizbedarf-Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    def _compute_demand(self) -> dict:
        hass_obj = getattr(self, "hass", None)
        climate_entities = get_climate_entities(self.config_entry)
        if not hass_obj or not climate_entities:
            return {
                "is_on": False,
                "heating_thermostats": [],
                "heating_count": 0,
                "thermostat_count": len(climate_entities),
                "current_temperature": None,
                "target_temperature": None,
                "temp_delta": None,
                "window_open": False,
            }

        domain_data = (
            hass_obj.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if isinstance(getattr(hass_obj, "data", None), dict)
            else None
        )
        _, _, win_pause_enabled = get_window_delays(self.config_entry)
        win_state = domain_data.get("window_state") if isinstance(domain_data, dict) else None
        if isinstance(win_state, dict) and win_state.get("initialized"):
            effective_win_open = bool(win_state.get("effective_open", False))
        else:
            effective_win_open, _ = get_raw_window_open(hass_obj, self.config_entry, climate_entities)
        window_paused = bool(effective_win_open and win_pause_enabled)

        current_temp, _ = get_room_current_temperature(hass_obj, self.config_entry, climate_entities)

        heating_thermostats: list[str] = []
        target_temps: list[float] = []
        primary_state = None
        for cl_id in climate_entities:
            st = hass_obj.states.get(cl_id)
            if not st:
                continue
            mode = str(getattr(st, "state", "") or "").strip().lower()
            if mode in ("unavailable", "unknown", "none", ""):
                continue
            if primary_state is None:
                primary_state = st
            attrs = getattr(st, "attributes", None) or {}

            t_val: float | None = None
            raw_t = attrs.get("temperature")
            if raw_t is not None:
                try:
                    parsed_t = float(raw_t)
                    if not math.isnan(parsed_t) and not math.isinf(parsed_t):
                        t_val = round(parsed_t, 1)
                        target_temps.append(t_val)
                except (ValueError, TypeError):
                    pass

            if mode == "off":
                continue

            hvac_act = attrs.get("hvac_action")
            if hvac_act is not None and str(hvac_act).strip() != "":
                if str(hvac_act).strip().lower() == "heating":
                    heating_thermostats.append(cl_id)
            else:
                # Fallback für einfache Thermostate ohne hvac_action-Attribut
                local_curr = current_temp
                if local_curr is None and attrs.get("current_temperature") is not None:
                    try:
                        parsed_c = float(attrs.get("current_temperature"))
                        if not math.isnan(parsed_c) and not math.isinf(parsed_c):
                            local_curr = parsed_c
                    except (ValueError, TypeError):
                        pass
                if mode in ("heat", "auto", "heat_cool"):
                    if local_curr is not None and t_val is not None:
                        if local_curr < t_val:
                            heating_thermostats.append(cl_id)
                    elif mode == "heat":
                        heating_thermostats.append(cl_id)

        target_temp: float | None = None
        if target_temps:
            target_temp = round(sum(target_temps) / len(target_temps), 1)
        else:
            preset, _, _, _, _, _, _ = evaluate_state(hass_obj, self.config_entry)
            preset_temp = get_preset_temperature(
                primary_state,
                preset,
                config_entry=self.config_entry,
                custom_presets=get_custom_presets(self.config_entry),
            )
            if preset_temp is not None:
                target_temp = round(float(preset_temp), 1)

        temp_delta: float | None = None
        if current_temp is not None and target_temp is not None:
            temp_delta = round(target_temp - current_temp, 2)

        return {
            "is_on": (not window_paused) and bool(heating_thermostats),
            "heating_thermostats": heating_thermostats,
            "heating_count": len(heating_thermostats),
            "thermostat_count": len(climate_entities),
            "current_temperature": current_temp,
            "target_temperature": target_temp,
            "temp_delta": temp_delta,
            "window_open": effective_win_open,
        }

    @property
    def is_on(self) -> bool:
        """Gibt True zurück, wenn der Raum aktiv Wärme anfordert (und keine Fenster-Pause aktiv ist)."""
        return bool(self._compute_demand()["is_on"])

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt Detail-Attribute zum Wärmebedarf (anfordernde Thermostate, Soll-/Ist-Temperatur, Delta, Fenster) zurück."""
        snap = self._compute_demand()
        return {
            "heating_thermostats": snap["heating_thermostats"],
            "heating_count": snap["heating_count"],
            "thermostat_count": snap["thermostat_count"],
            "current_temperature": snap["current_temperature"],
            "target_temperature": snap["target_temperature"],
            "temp_delta": snap["temp_delta"],
            "window_open": snap["window_open"],
        }

