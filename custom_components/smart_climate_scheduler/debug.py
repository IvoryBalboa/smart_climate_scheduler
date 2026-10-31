"""Debug-Sensor für Smart Climate Scheduler (Version 2.0)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from .evaluation import evaluate_state
from .helpers import get_config_entry_slug, get_device_info


class SmartClimateSchedulerDebugSensor(SensorEntity):
    """Debug-Sensor zur Überwachung aller internen Berechnungen und Thermik-Werte (V2)."""

    _attr_icon = "mdi:bug"
    _attr_has_entity_name = True
    _attr_translation_key = "debug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, config_entry: ConfigEntry, main_sensor) -> None:
        """Initialisiert den Debug-Sensor."""
        self.config_entry = config_entry
        self.main_sensor = main_sensor
        self._attr_unique_id = f"{config_entry.entry_id}_debug"
        slug = get_config_entry_slug(config_entry)
        self.entity_id = f"sensor.{slug}_diagnose"

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
        preset, preheat, cooldown, active_slot, next_slot, next_action, debug_info = evaluate_state(
            self.main_sensor.hass, self.config_entry
        )

        if not isinstance(debug_info, dict):
            debug_info = {}

        return {
            "preset": preset,
            "active_slot": active_slot,
            "next_slot": next_slot,
            "next_action": next_action,
            "preheat": preheat,
            "cooldown": cooldown,
            **debug_info,
        }
