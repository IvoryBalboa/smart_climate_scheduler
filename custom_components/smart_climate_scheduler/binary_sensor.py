"""Binary-Sensor Plattform für Smart Climate Scheduler (Version 2.3.2)."""
from __future__ import annotations

import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COOLDOWN_ENABLED,
    CONF_PREHEAT_ENABLED,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_PREHEAT_ENABLED,
    DOMAIN,
)
from .evaluation import evaluate_state
from .helpers import (
    async_sync_entity_registry_disabled,
    get_config_entry_slug,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
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

    sensors = hass.data.setdefault(f"{DOMAIN}_sensors", [])
    sensors.extend([preheat_binary, cooldown_binary])

    async_add_entities([preheat_binary, cooldown_binary], True)
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
