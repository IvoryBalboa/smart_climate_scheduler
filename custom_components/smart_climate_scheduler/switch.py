"""Switch-Plattform für Smart Climate Scheduler."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CLIMATE_ENTITY, DOMAIN
from .evaluation import evaluate_state
from .helpers import get_config_entry_slug, get_device_info, get_target_hvac_mode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Switch-Plattform über einen Config Entry ein."""
    async_add_entities([SmartClimateSchedulerSwitch(hass, config_entry)], True)


class SmartClimateSchedulerSwitch(SwitchEntity):
    """Schalter zum Ein- und Ausschalten der automatischen Thermostat-Steuerung."""

    _attr_icon = "mdi:thermostat-auto"
    _attr_has_entity_name = True
    _attr_translation_key = "automatic"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialisiert den Switch."""
        self.hass = hass
        self.config_entry = config_entry
        slug = get_config_entry_slug(config_entry)
        self.entity_id = f"switch.{slug}_automatik"
        
        # Zustand aus hass.data laden (wurde beim Start aus dem Storage befüllt)
        domain_data = self.hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})
        self._is_on = domain_data.get("automation_enabled", False)

        self._attr_unique_id = f"{config_entry.entry_id}_automatic"

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def is_on(self) -> bool:
        """Gibt zurück, ob die Automatik eingeschaltet ist."""
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Schaltet die Automatik ein und wendet das Preset sofort an (ohne Reload)."""
        self._is_on = True
        
        domain_data = self.hass.data.setdefault(DOMAIN, {}).setdefault(self.config_entry.entry_id, {})
        domain_data["automation_enabled"] = True
        
        # Persistent im Storage speichern (ohne Integration-Reload)
        storage = domain_data.get("storage")
        if storage:
            async def _save_status(store, enabled):
                data = await store.async_get_data()
                data["automation_enabled"] = enabled
                await store.async_save_data(data)
            self.hass.async_create_task(_save_status(storage, True))

        self.async_write_ha_state()

        # Sofortiges Anwenden des Soll-Presets und Heizmodus beim Einschalten der Automatik
        apply_fn = domain_data.get("async_apply_schedule")
        if callable(apply_fn):
            await apply_fn()
        else:
            climate_entity = (
                self.config_entry.options.get(CONF_CLIMATE_ENTITY) 
                or self.config_entry.data.get(CONF_CLIMATE_ENTITY, "")
            ).strip()
            
            if self.hass and climate_entity:
                state_obj = self.hass.states.get(climate_entity)
                if state_obj and state_obj.state not in ("unavailable", "unknown", "None", None):
                    preset, _, _, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
                    if preset and preset not in ("unavailable", "unknown", "None", None):
                        await self.hass.services.async_call(
                            "climate",
                            "set_preset_mode",
                            service_data={"preset_mode": preset},
                            target={"entity_id": climate_entity},
                            blocking=False,
                        )
                        if state_obj.state == "off" and str(preset).lower() not in ("off", "none"):
                            target_mode = get_target_hvac_mode(state_obj)
                            await self.hass.services.async_call(
                                "climate",
                                "set_hvac_mode",
                                service_data={"hvac_mode": target_mode},
                                target={"entity_id": climate_entity},
                                blocking=False,
                            )

    async def async_turn_off(self, **kwargs) -> None:
        """Schaltet die Automatik aus (ohne Reload)."""
        self._is_on = False
        
        domain_data = self.hass.data.setdefault(DOMAIN, {}).setdefault(self.config_entry.entry_id, {})
        domain_data["automation_enabled"] = False
        domain_data["two_point_target_reached"] = False
        
        # Persistent im Storage speichern (ohne Reload)
        storage = domain_data.get("storage")
        if storage:
            async def _save_status(store, enabled):
                data = await store.async_get_data()
                data["automation_enabled"] = enabled
                await store.async_save_data(data)
            self.hass.async_create_task(_save_status(storage, False))

        self.async_write_ha_state()
