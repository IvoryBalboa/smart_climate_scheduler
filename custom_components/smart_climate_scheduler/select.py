"""Select platform for Smart Climate Scheduler (schedule profiles)."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_CLIMATE_ENTITY
from .evaluation import evaluate_state, invalidate_eval_cache
from .helpers import (
    get_config_entry_slug,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
    get_profiles_and_active,
    get_preset_temperature,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform from a config entry."""
    entity = SmartClimateSchedulerProfileSelect(hass, config_entry)
    async_add_entities([entity], True)

    domain_data = hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})
    domain_data["profile_select"] = entity


class SmartClimateSchedulerProfileSelect(SelectEntity):
    """Select entity for choosing and switching the active schedule profile."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-account"
    _attr_translation_key = "schedule_profile"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the schedule profile selector."""
        self.hass = hass
        self.config_entry = config_entry
        self._slug = get_config_entry_slug(config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_schedule_profile"
        lang = get_ha_language(hass or getattr(config_entry, "hass", None))
        suffix = get_localized_slug_suffix("schedule_profile", lang)
        self.entity_id = f"select.{self._slug}_{suffix}"
        self._attr_device_info = get_device_info(config_entry)
        self._update_from_entry()

    def _update_from_entry(self) -> None:
        """Load available profiles and the active profile from the config entry."""
        profiles, active_profile = get_profiles_and_active(self.config_entry)
        self._attr_options = list(profiles.keys())
        self._attr_current_option = active_profile

    @property
    def options(self) -> list[str]:
        """Return the list of available schedule profiles."""
        profiles, _ = get_profiles_and_active(self.config_entry)
        return list(profiles.keys())

    @property
    def current_option(self) -> str | None:
        """Return the currently active schedule profile."""
        _, active_profile = get_profiles_and_active(self.config_entry)
        return active_profile

    async def async_select_option(self, option: str) -> None:
        """Switch the active schedule profile."""
        profiles, current_profile = get_profiles_and_active(self.config_entry)
        if option not in profiles:
            _LOGGER.warning("Invalid schedule profile '%s' selected. Available: %s", option, list(profiles.keys()))
            return

        if option == current_profile:
            return

        _LOGGER.info("Schedule profile for '%s' switched: %s -> %s", self.entity_id, current_profile, option)

        # 1. Update config entry options
        new_options = dict(self.config_entry.options)
        new_options["active_profile"] = option
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)

        # 2. Invalidate eval cache so subsequent calls re-evaluate with the new profile immediately
        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        invalidate_eval_cache(entry_data)

        # 3. Write state of select entity
        self._attr_current_option = option
        self.async_write_ha_state()

        # 4. Trigger scheduler evaluation and climate preset update
        try:
            preset, _, _, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
            climate_entity = (
                self.config_entry.options.get(CONF_CLIMATE_ENTITY)
                or self.config_entry.data.get(CONF_CLIMATE_ENTITY)
            )
            if climate_entity and preset and preset not in ("unavailable", "unknown", "None", None):
                if hasattr(self.hass, "services") and self.hass.services.has_service("climate", "set_preset_mode"):
                    await self.hass.services.async_call(
                        "climate",
                        "set_preset_mode",
                        service_data={"preset_mode": preset},
                        target={"entity_id": climate_entity},
                    )
                tgt_t = get_preset_temperature(self.hass.states.get(climate_entity), preset)
                if tgt_t and hasattr(self.hass, "services") and self.hass.services.has_service("climate", "set_temperature"):
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        service_data={"temperature": tgt_t},
                        target={"entity_id": climate_entity},
                    )
        except Exception as err:
            _LOGGER.debug("Error during immediate preset update after profile change: %s", err)
