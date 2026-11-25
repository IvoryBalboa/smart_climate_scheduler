"""Debug-Sensor für Smart Climate Scheduler (Version 2.3.2)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from .anomaly import get_anomaly_snapshot
from .const import DOMAIN
from .evaluation import evaluate_state
from .helpers import (
    get_config_entry_slug,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
    get_profiles_and_active,
)


class SmartClimateSchedulerDebugSensor(SensorEntity):
    """Debug-Sensor zur Überwachung aller internen Berechnungen und Thermik-Werte (V2.3.2)."""

    _attr_icon = "mdi:bug"
    _attr_has_entity_name = True
    _attr_translation_key = "debug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, config_entry: ConfigEntry, main_sensor, hass: HomeAssistant | None = None) -> None:
        """Initialisiert den Debug-Sensor."""
        self.config_entry = config_entry
        self.main_sensor = main_sensor
        self._attr_unique_id = f"{config_entry.entry_id}_debug"
        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass or getattr(main_sensor, "hass", None) or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("diagnostics", lang)
        self.entity_id = f"sensor.{slug}_{suffix}"

    async def async_update(self) -> None:
        """Manuelle Aktualisierung des Debug-Sensors."""
        pass

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def native_value(self) -> str:
        return "OK"

    @property
    def extra_state_attributes(self) -> dict:
        """Gibt alle Detail- und Debug-Informationen sowie die vollständigen Preheat/Cooldown-Dicts zurück."""
        hass_obj = self.main_sensor.hass
        preset, preheat, cooldown, active_slot, next_slot, next_action, debug_info = evaluate_state(
            hass_obj, self.config_entry
        )

        if not isinstance(debug_info, dict):
            debug_info = {}

        _, active_profile = get_profiles_and_active(self.config_entry)
        domain_data = (
            hass_obj.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if (hass_obj and isinstance(getattr(hass_obj, "data", None), dict))
            else None
        )
        anomaly_snap = get_anomaly_snapshot(hass_obj, self.config_entry, domain_data)

        return {
            "profile": active_profile,
            "preset": preset,
            "active_slot": active_slot,
            "next_slot": next_slot,
            "next_action": next_action,
            "preheat": preheat,
            "cooldown": cooldown,
            "anomaly": anomaly_snap,
            **debug_info,
        }
