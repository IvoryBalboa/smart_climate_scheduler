"""Switch-Plattform für Smart Climate Scheduler."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_COOLDOWN_ENABLED,
    CONF_ENABLE_SELF_LEARNING,
    CONF_HEATING_ACTIVE_SENSOR,
    CONF_HVAC_OFF_ON_TARGET,
    CONF_OPPORTUNISTIC_HEATING,
    CONF_PREHEAT_ENABLED,
    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_FALLBACK_TOLERANCE,
    DEFAULT_HVAC_OFF_ON_TARGET,
    DEFAULT_OPPORTUNISTIC_HEATING,
    DEFAULT_PREHEAT_ENABLED,
    DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
    DOMAIN,
)
from .evaluation import evaluate_state, invalidate_eval_cache
from .helpers import (
    async_sync_entity_registry_disabled,
    async_write_ha_state_if_enabled,
    get_config_entry_slug,
    get_device_info,
    get_ha_language,
    get_localized_slug_suffix,
    get_preset_temperature,
    get_target_hvac_mode,
    safe_float as _safe_float,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Switch-Plattform über einen Config Entry ein."""
    entities: list[SwitchEntity] = [
        SmartClimateSchedulerSwitch(hass, config_entry),
        SmartClimateSchedulerOptionSwitch(
            hass,
            config_entry,
            option_key=CONF_ENABLE_SELF_LEARNING,
            translation_key="self_learning",
            slug_suffix="self_learning",
            default_value=DEFAULT_ENABLE_SELF_LEARNING,
            icon="mdi:school",
        ),
        SmartClimateSchedulerOptionSwitch(
            hass,
            config_entry,
            option_key=CONF_PREHEAT_ENABLED,
            translation_key="preheat",
            slug_suffix="preheat",
            default_value=DEFAULT_PREHEAT_ENABLED,
            icon="mdi:fire",
        ),
        SmartClimateSchedulerOptionSwitch(
            hass,
            config_entry,
            option_key=CONF_COOLDOWN_ENABLED,
            translation_key="cooldown",
            slug_suffix="cooldown",
            default_value=DEFAULT_COOLDOWN_ENABLED,
            icon="mdi:snowflake",
        ),
        SmartClimateSchedulerOptionSwitch(
            hass,
            config_entry,
            option_key=CONF_HVAC_OFF_ON_TARGET,
            translation_key="hvac_off_on_target",
            slug_suffix="hvac_off_on_target",
            default_value=DEFAULT_HVAC_OFF_ON_TARGET,
            icon="mdi:power-standby",
        ),
        SmartClimateSchedulerOptionSwitch(
            hass,
            config_entry,
            option_key=CONF_OPPORTUNISTIC_HEATING,
            translation_key="opportunistic_heating",
            slug_suffix="opportunistic_heating",
            default_value=DEFAULT_OPPORTUNISTIC_HEATING,
            icon="mdi:heat-wave",
        ),
        SmartClimateSchedulerOptionSwitch(
            hass,
            config_entry,
            option_key=CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
            translation_key="use_weather_forecast_for_preheat",
            slug_suffix="weather_forecast_preheat",
            default_value=DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
            icon="mdi:weather-partly-cloudy",
        ),
    ]
    async_add_entities(entities, True)


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
        lang = get_ha_language(hass)
        suffix = get_localized_slug_suffix("automatic", lang)
        self.entity_id = f"switch.{slug}_{suffix}"
        
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
        domain_data["is_setting_preset"] = False
        domain_data["is_setting_hvac"] = False
        
        # Persistent im Storage speichern (ohne Integration-Reload)
        storage = domain_data.get("storage")
        if storage:
            async def _save_status(store, enabled):
                data = await store.async_get_data()
                data["automation_enabled"] = enabled
                await store.async_save_data(data)
            self.hass.async_create_task(_save_status(storage, True))

        self.async_write_ha_state()

        # Sofortiges Anwenden des Soll-Presets und der Zwei-Punkt-Regelung
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
                entry_name = self.config_entry.title or self.config_entry.entry_id
                if not state_obj or state_obj.state in ("unavailable", "unknown", "None", None):
                    cur_state = state_obj.state if state_obj else "nicht gefunden"
                    _LOGGER.warning(
                        "Smart Climate Scheduler Switch [%s]: Thermostat '%s' ist nicht verfügbar (Status: '%s')",
                        entry_name,
                        climate_entity,
                        cur_state,
                    )
                else:
                    preset, _, _, _, _, _, _ = evaluate_state(self.hass, self.config_entry)
                    if preset and preset not in ("unavailable", "unknown", "None", None):
                        try:
                            await self.hass.services.async_call(
                                "climate",
                                "set_preset_mode",
                                service_data={"preset_mode": preset},
                                target={"entity_id": climate_entity},
                                blocking=False,
                            )
                        except Exception as err:
                            _LOGGER.error(
                                "Smart Climate Scheduler Switch [%s]: Fehler beim Setzen von Preset '%s' auf '%s': %s",
                                entry_name,
                                preset,
                                climate_entity,
                                err,
                            )
                        
                        # Zwei-Punkt-Regelung anwenden falls aktiviert
                        hvac_off_on_target = bool(
                            self.config_entry.options.get(
                                CONF_HVAC_OFF_ON_TARGET,
                                self.config_entry.data.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET),
                            )
                        )
                        opportunistic_heating = bool(
                            self.config_entry.options.get(
                                CONF_OPPORTUNISTIC_HEATING,
                                self.config_entry.data.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING),
                            )
                        )
                        heating_active_sensor = self.config_entry.options.get(
                            CONF_HEATING_ACTIVE_SENSOR,
                            self.config_entry.data.get(CONF_HEATING_ACTIVE_SENSOR),
                        )
                        is_heating_active = False
                        if heating_active_sensor and self.hass:
                            st = self.hass.states.get(heating_active_sensor)
                            if st and st.state and st.state.lower() in ("on", "true", "active", "heat", "heating"):
                                is_heating_active = True

                        if hvac_off_on_target:
                            attrs = state_obj.attributes or {}
                            real_temp = attrs.get("current_temperature")
                            if real_temp is None:
                                real_temp = attrs.get("external_temp_ema")
                            try:
                                cur_t = float(real_temp) if real_temp is not None else None
                            except (ValueError, TypeError):
                                cur_t = None
                            tgt_t = get_preset_temperature(state_obj, preset)
                            tol = _safe_float(attrs.get("tolerance"), DEFAULT_FALLBACK_TOLERANCE)
                            
                            if cur_t is not None and tgt_t is not None:
                                if cur_t >= tgt_t:
                                    if state_obj.state != "off" and attrs.get("hvac_action") != "heating":
                                        try:
                                            await self.hass.services.async_call(
                                                "climate",
                                                "set_hvac_mode",
                                                service_data={"hvac_mode": "off"},
                                                target={"entity_id": climate_entity},
                                                blocking=False,
                                            )
                                        except Exception as err:
                                            _LOGGER.error(
                                                "Smart Climate Scheduler Switch [%s]: Fehler beim Ausschalten ('off') von '%s': %s",
                                                entry_name,
                                                climate_entity,
                                                err,
                                            )
                                elif cur_t < (tgt_t - tol) or (opportunistic_heating and is_heating_active and cur_t < tgt_t):
                                    if state_obj.state == "off":
                                        target_mode = get_target_hvac_mode(state_obj)
                                        try:
                                            await self.hass.services.async_call(
                                                "climate",
                                                "set_hvac_mode",
                                                service_data={"hvac_mode": target_mode},
                                                target={"entity_id": climate_entity},
                                                blocking=False,
                                            )
                                        except Exception as err:
                                            _LOGGER.error(
                                                "Smart Climate Scheduler Switch [%s]: Fehler beim Einschalten ('%s') von '%s': %s",
                                                entry_name,
                                                target_mode,
                                                climate_entity,
                                                err,
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


class SmartClimateSchedulerOptionSwitch(SwitchEntity):
    """Schalter für eine einzelne Konfigurations-Option (z. B. Vorheizen, Lernen etc.)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        option_key: str,
        translation_key: str,
        slug_suffix: str,
        default_value: bool,
        icon: str,
    ) -> None:
        """Initialisiert den Options-Schalter."""
        self.hass = hass
        self.config_entry = config_entry
        self._option_key = option_key
        self._default_value = default_value
        self._attr_translation_key = translation_key
        self._attr_icon = icon

        slug = get_config_entry_slug(config_entry)
        lang = get_ha_language(hass)
        suffix = get_localized_slug_suffix(slug_suffix, lang)
        self.entity_id = f"switch.{slug}_{suffix}"
        self._attr_unique_id = f"{config_entry.entry_id}_{translation_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Ordnet die Entität dem Device des Config Entrys zu."""
        return get_device_info(self.config_entry)

    @property
    def is_on(self) -> bool:
        """Gibt zurück, ob die Option eingeschaltet ist."""
        return bool(
            self.config_entry.options.get(
                self._option_key,
                self.config_entry.data.get(self._option_key, self._default_value),
            )
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Schaltet die Option ein und speichert sie dauerhaft in den Optionen."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Schaltet die Option aus und speichert sie dauerhaft in den Optionen."""
        await self._async_set_state(False)

    async def _async_set_state(self, target_state: bool) -> None:
        """Speichert den neuen Zustand dauerhaft in den Config-Optionen."""
        domain_data = self.hass.data.setdefault(DOMAIN, {}).setdefault(self.config_entry.entry_id, {})
        new_options = dict(self.config_entry.options)
        new_options[self._option_key] = target_state

        # Markieren, damit der update_listener keinen unnötigen Plattform-Reload ausführt
        domain_data["_updating_from_switch"] = True

        if hasattr(self.hass, "config_entries") and hasattr(self.hass.config_entries, "async_update_entry"):
            self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)

        self.async_write_ha_state()

        # Entity-Registry Deaktivierung / Reaktivierung synchronisieren VOR State-Writes
        if self._option_key in (CONF_PREHEAT_ENABLED, CONF_COOLDOWN_ENABLED, CONF_ENABLE_SELF_LEARNING):
            await async_sync_entity_registry_disabled(self.hass, self.config_entry)

        # Evaluierungs-Cache invalidieren
        invalidate_eval_cache(domain_data)

        # Alle zugehörigen Sensoren aktualisieren (nur wenn nicht in Entity Registry deaktiviert)
        for sensor in self.hass.data.get(f"{DOMAIN}_sensors", []):
            if getattr(sensor, "config_entry", None) and sensor.config_entry.entry_id == self.config_entry.entry_id:
                async_write_ha_state_if_enabled(sensor)

        # Bei Hysterese / Opportunistischem Mitheizen direkt Zeitplan anwenden falls Automatik aktiv
        if self._option_key in (CONF_HVAC_OFF_ON_TARGET, CONF_OPPORTUNISTIC_HEATING):
            apply_fn = domain_data.get("async_apply_schedule")
            if callable(apply_fn):
                await apply_fn()
