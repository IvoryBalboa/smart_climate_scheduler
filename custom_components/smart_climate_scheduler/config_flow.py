"""Config Flow and Options Flow for Smart Climate Scheduler."""
from __future__ import annotations

import copy
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TimeSelector,
    TextSelector,
    TextSelectorConfig,
)

from .actions import _format_preset, get_localized_ui_text
from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_COOLDOWN_ENABLED,
    CONF_DEFAULT_PRESET,
    CONF_MAX_MINUTES_COOLDOWN,
    CONF_MAX_MINUTES_PREHEAT,
    CONF_NEAR_DISTANCE,
    CONF_PREHEAT_ENABLED,
    CONF_ZONE_AWAY_NEAR_ENTITY,
    CONF_ZONE_HOME_ENTITY,
    CONF_ENABLE_SELF_LEARNING,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_OUTSIDE_WEATHER_ENTITY,
    CONF_HEATING_ACTIVE_SENSOR,
    CONF_FALLBACK_HEATING_RATE,
    CONF_FALLBACK_COOLING_RATE,
    CONF_HVAC_OFF_ON_TARGET,
    CONF_FALLBACK_TOLERANCE,
    CONF_OPPORTUNISTIC_HEATING,
    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
    CONF_PREHEAT_IGNORES_AWAY,
    DAYS,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_FALLBACK_PRESET,
    DEFAULT_MAX_MINUTES_PREHEAT,
    DEFAULT_MAX_MINUTES_COOLDOWN,
    DEFAULT_NEAR_DISTANCE,
    DEFAULT_PREHEAT_ENABLED,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_FALLBACK_HEATING_RATE,
    DEFAULT_FALLBACK_COOLING_RATE,
    DEFAULT_HVAC_OFF_ON_TARGET,
    DEFAULT_FALLBACK_TOLERANCE,
    DEFAULT_OPPORTUNISTIC_HEATING,
    DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
    DEFAULT_PREHEAT_IGNORES_AWAY,
    DOMAIN,
)
from .helpers import (
    get_ha_language,
    get_profiles_and_active,
    parse_time,
    safe_float as _safe_float,
)

DEFAULT_PRESETS = ["none", "home", "away", "boost", "comfort", "eco", "sleep", "activity"]


def _get_slot_preset(slot: dict) -> str:
    """Extracts the preset name with fallback 'none'."""
    if "preset" in slot and slot["preset"]:
        return slot["preset"]
    if "data" in slot and isinstance(slot["data"], dict):
        return slot["data"].get("preset", "none")
    return "none"


def _normalize_schedule(raw_schedule: dict | None) -> dict[str, list[dict]]:
    """Normalizes the schedule into a uniform dictionary structure."""
    if not isinstance(raw_schedule, dict):
        return {day: [] for day in DAYS}

    normalized = {}
    for day in DAYS:
        day_list = raw_schedule.get(day, [])
        normalized_day = []
        if isinstance(day_list, list):
            for slot in day_list:
                if isinstance(slot, dict):
                    normalized_day.append(
                        {
                            "from": slot.get("from", "00:00:00"),
                            "to": slot.get("to", "00:00:00"),
                            "preset": _get_slot_preset(slot),
                        }
                    )
        normalized[day] = normalized_day
    return normalized


class SmartClimateSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the initial configuration flow for the integration."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initial setup of the integration entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get("name", "").strip()
            if not name:
                errors["base"] = "name_required"
            else:
                unique_id = name.lower().replace(" ", "_")
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                user_input[CONF_FALLBACK_HEATING_RATE] = _safe_float(
                    user_input.get(CONF_FALLBACK_HEATING_RATE), DEFAULT_FALLBACK_HEATING_RATE
                )
                user_input[CONF_FALLBACK_COOLING_RATE] = _safe_float(
                    user_input.get(CONF_FALLBACK_COOLING_RATE), DEFAULT_FALLBACK_COOLING_RATE
                )
                user_input[CONF_ENABLE_SELF_LEARNING] = bool(
                    user_input.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING)
                )
                user_input[CONF_OPPORTUNISTIC_HEATING] = bool(
                    user_input.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING)
                )
                user_input[CONF_USE_WEATHER_FORECAST_FOR_PREHEAT] = bool(
                    user_input.get(CONF_USE_WEATHER_FORECAST_FOR_PREHEAT, DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT)
                )

                default_schedule = {day: [] for day in DAYS}
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                    options={"schedule": default_schedule},
                )

        schema = vol.Schema(
            {
                vol.Required("name"): TextSelector(TextSelectorConfig()),
                vol.Required(CONF_CLIMATE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="climate")
                ),
                vol.Optional(CONF_OUTSIDE_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_OUTSIDE_WEATHER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(CONF_HEATING_ACTIVE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean"])
                ),
                vol.Optional(
                    CONF_ENABLE_SELF_LEARNING, default=DEFAULT_ENABLE_SELF_LEARNING
                ): BooleanSelector(),
                vol.Optional(
                    CONF_FALLBACK_HEATING_RATE, default=DEFAULT_FALLBACK_HEATING_RATE
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.05, max=5.0, step=0.05, unit_of_measurement="K/h", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_FALLBACK_COOLING_RATE, default=DEFAULT_FALLBACK_COOLING_RATE
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.01, max=3.0, step=0.01, unit_of_measurement="K/h", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_ZONE_HOME_ENTITY, default="zone.home"): EntitySelector(
                    EntitySelectorConfig(domain="zone")
                ),
                vol.Optional(CONF_ZONE_AWAY_NEAR_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="zone")
                ),
                vol.Optional(
                    CONF_NEAR_DISTANCE, default=DEFAULT_NEAR_DISTANCE
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0, max=5.0, step=0.05, unit_of_measurement="km", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_DEFAULT_PRESET, default=DEFAULT_FALLBACK_PRESET
                ): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=DEFAULT_PRESETS,
                    )
                ),
                vol.Optional(CONF_PREHEAT_ENABLED, default=DEFAULT_PREHEAT_ENABLED): BooleanSelector(),
                vol.Optional(
                    CONF_MAX_MINUTES_PREHEAT, default=DEFAULT_MAX_MINUTES_PREHEAT
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=720, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_COOLDOWN_ENABLED, default=DEFAULT_COOLDOWN_ENABLED): BooleanSelector(),
                vol.Optional(
                    CONF_MAX_MINUTES_COOLDOWN, default=DEFAULT_MAX_MINUTES_COOLDOWN
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=720, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_HVAC_OFF_ON_TARGET, default=DEFAULT_HVAC_OFF_ON_TARGET): BooleanSelector(),
                vol.Optional(
                    CONF_FALLBACK_TOLERANCE, default=DEFAULT_FALLBACK_TOLERANCE
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.05, max=2.0, step=0.05, unit_of_measurement="K", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_OPPORTUNISTIC_HEATING, default=DEFAULT_OPPORTUNISTIC_HEATING
                ): BooleanSelector(),
                vol.Optional(
                    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT, default=DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT
                ): BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Creates the Options Flow handler."""
        return SmartClimateSchedulerOptionsFlowHandler()


class SmartClimateSchedulerOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow with structured main menu and profile management."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, list[dict]]] | None = None
        self.active_profile: str = "Standard"
        self.current_schedule: dict[str, list[dict]] | None = None
        self.settings_data: dict[str, Any] = {}
        self.selected_day: str = "monday"
        self.selected_slot_index: int | None = None

    def _init_data(self) -> None:
        """Loads schedules, profiles, and settings into the temporary buffer."""
        if self.profiles is None:
            raw_profiles, active_prof = get_profiles_and_active(self.config_entry)
            self.profiles = copy.deepcopy(raw_profiles)
            self.active_profile = active_prof
            self.current_schedule = _normalize_schedule(self.profiles.get(self.active_profile, {}))

        if not self.settings_data:
            options = self.config_entry.options
            data = self.config_entry.data

            self.settings_data = {
                CONF_OUTSIDE_TEMP_SENSOR: options.get(
                    CONF_OUTSIDE_TEMP_SENSOR, data.get(CONF_OUTSIDE_TEMP_SENSOR)
                ),
                CONF_OUTSIDE_WEATHER_ENTITY: options.get(
                    CONF_OUTSIDE_WEATHER_ENTITY, data.get(CONF_OUTSIDE_WEATHER_ENTITY)
                ),
                CONF_HEATING_ACTIVE_SENSOR: options.get(
                    CONF_HEATING_ACTIVE_SENSOR, data.get(CONF_HEATING_ACTIVE_SENSOR)
                ),
                CONF_ENABLE_SELF_LEARNING: bool(
                    options.get(
                        CONF_ENABLE_SELF_LEARNING,
                        data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
                    )
                ),
                CONF_FALLBACK_HEATING_RATE: _safe_float(
                    options.get(
                        CONF_FALLBACK_HEATING_RATE,
                        data.get(CONF_FALLBACK_HEATING_RATE),
                    ),
                    DEFAULT_FALLBACK_HEATING_RATE,
                ),
                CONF_FALLBACK_COOLING_RATE: _safe_float(
                    options.get(
                        CONF_FALLBACK_COOLING_RATE,
                        data.get(CONF_FALLBACK_COOLING_RATE),
                    ),
                    DEFAULT_FALLBACK_COOLING_RATE,
                ),
                CONF_ZONE_HOME_ENTITY: options.get(
                    CONF_ZONE_HOME_ENTITY, data.get(CONF_ZONE_HOME_ENTITY, "zone.home")
                ),
                CONF_ZONE_AWAY_NEAR_ENTITY: options.get(
                    CONF_ZONE_AWAY_NEAR_ENTITY, data.get(CONF_ZONE_AWAY_NEAR_ENTITY)
                ),
                CONF_NEAR_DISTANCE: _safe_float(
                    options.get(
                        CONF_NEAR_DISTANCE,
                        data.get(CONF_NEAR_DISTANCE),
                    ),
                    DEFAULT_NEAR_DISTANCE,
                ),
                CONF_DEFAULT_PRESET: options.get(
                    CONF_DEFAULT_PRESET, data.get(CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET)
                ),
                CONF_PREHEAT_ENABLED: bool(
                    options.get(
                        CONF_PREHEAT_ENABLED,
                        data.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED),
                    )
                ),
                CONF_COOLDOWN_ENABLED: bool(
                    options.get(
                        CONF_COOLDOWN_ENABLED,
                        data.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED),
                    )
                ),
                CONF_MAX_MINUTES_PREHEAT: int(
                    _safe_float(
                        options.get(
                            CONF_MAX_MINUTES_PREHEAT,
                            data.get(CONF_MAX_MINUTES_PREHEAT),
                        ),
                        DEFAULT_MAX_MINUTES_PREHEAT,
                    )
                ),
                CONF_MAX_MINUTES_COOLDOWN: int(
                    _safe_float(
                        options.get(
                            CONF_MAX_MINUTES_COOLDOWN,
                            data.get(CONF_MAX_MINUTES_COOLDOWN),
                        ),
                        DEFAULT_MAX_MINUTES_COOLDOWN,
                    )
                ),
                CONF_HVAC_OFF_ON_TARGET: bool(
                    options.get(
                        CONF_HVAC_OFF_ON_TARGET,
                        data.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET),
                    )
                ),
                CONF_FALLBACK_TOLERANCE: _safe_float(
                    options.get(
                        CONF_FALLBACK_TOLERANCE,
                        data.get(CONF_FALLBACK_TOLERANCE),
                    ),
                    DEFAULT_FALLBACK_TOLERANCE,
                ),
                CONF_OPPORTUNISTIC_HEATING: bool(
                    options.get(
                        CONF_OPPORTUNISTIC_HEATING,
                        data.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING),
                    )
                ),
                CONF_USE_WEATHER_FORECAST_FOR_PREHEAT: bool(
                    options.get(
                        CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
                        data.get(CONF_USE_WEATHER_FORECAST_FOR_PREHEAT, DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT),
                    )
                ),
                CONF_PREHEAT_IGNORES_AWAY: bool(
                    options.get(
                        CONF_PREHEAT_IGNORES_AWAY,
                        data.get(CONF_PREHEAT_IGNORES_AWAY, DEFAULT_PREHEAT_IGNORES_AWAY),
                    )
                ),
            }

    def _get_supported_presets(self) -> list[str]:
        climate_entity = self.config_entry.data.get(CONF_CLIMATE_ENTITY)
        if climate_entity and self.hass:
            state = self.hass.states.get(climate_entity)
            if state and "preset_modes" in state.attributes:
                modes = state.attributes.get("preset_modes")
                if isinstance(modes, list) and modes:
                    return modes
        return DEFAULT_PRESETS

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Main menu step."""
        self._init_data()

        if user_input is not None:
            action = user_input.get("main_action")
            if action == "settings":
                return await self.async_step_settings()
            elif action == "schedules":
                return await self.async_step_schedule_menu()
            elif action == "save":
                if self.profiles is not None and self.current_schedule is not None:
                    self.profiles[self.active_profile] = copy.deepcopy(self.current_schedule)

                new_data = dict(self.config_entry.data)
                new_data.update(self.settings_data)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                return self.async_create_entry(
                    title="",
                    data={
                        "schedule": self.current_schedule,
                        "profiles": self.profiles,
                        "active_profile": self.active_profile,
                        **self.settings_data,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required("main_action", default="schedules"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="init_action",
                        options=["schedules", "settings", "save"],
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit general settings and thermal parameters."""
        self._init_data()

        if user_input is not None:
            self.settings_data[CONF_OUTSIDE_TEMP_SENSOR] = user_input.get(CONF_OUTSIDE_TEMP_SENSOR)
            self.settings_data[CONF_OUTSIDE_WEATHER_ENTITY] = user_input.get(CONF_OUTSIDE_WEATHER_ENTITY)
            self.settings_data[CONF_HEATING_ACTIVE_SENSOR] = user_input.get(CONF_HEATING_ACTIVE_SENSOR)
            self.settings_data[CONF_ENABLE_SELF_LEARNING] = bool(
                user_input.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING)
            )
            self.settings_data[CONF_FALLBACK_HEATING_RATE] = _safe_float(
                user_input.get(CONF_FALLBACK_HEATING_RATE), DEFAULT_FALLBACK_HEATING_RATE
            )
            self.settings_data[CONF_FALLBACK_COOLING_RATE] = _safe_float(
                user_input.get(CONF_FALLBACK_COOLING_RATE), DEFAULT_FALLBACK_COOLING_RATE
            )
            self.settings_data[CONF_ZONE_HOME_ENTITY] = user_input.get(CONF_ZONE_HOME_ENTITY, "zone.home")
            self.settings_data[CONF_ZONE_AWAY_NEAR_ENTITY] = user_input.get(CONF_ZONE_AWAY_NEAR_ENTITY)
            self.settings_data[CONF_NEAR_DISTANCE] = _safe_float(
                user_input.get(CONF_NEAR_DISTANCE), DEFAULT_NEAR_DISTANCE
            )
            self.settings_data[CONF_DEFAULT_PRESET] = user_input.get(CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET)
            self.settings_data[CONF_PREHEAT_ENABLED] = bool(user_input.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED))
            self.settings_data[CONF_COOLDOWN_ENABLED] = bool(user_input.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED))
            self.settings_data[CONF_MAX_MINUTES_PREHEAT] = int(
                _safe_float(user_input.get(CONF_MAX_MINUTES_PREHEAT), DEFAULT_MAX_MINUTES_PREHEAT)
            )
            self.settings_data[CONF_MAX_MINUTES_COOLDOWN] = int(
                _safe_float(user_input.get(CONF_MAX_MINUTES_COOLDOWN), DEFAULT_MAX_MINUTES_COOLDOWN)
            )
            self.settings_data[CONF_HVAC_OFF_ON_TARGET] = bool(
                user_input.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET)
            )
            self.settings_data[CONF_FALLBACK_TOLERANCE] = _safe_float(
                user_input.get(CONF_FALLBACK_TOLERANCE), DEFAULT_FALLBACK_TOLERANCE
            )
            self.settings_data[CONF_OPPORTUNISTIC_HEATING] = bool(
                user_input.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING)
            )
            self.settings_data[CONF_USE_WEATHER_FORECAST_FOR_PREHEAT] = bool(
                user_input.get(CONF_USE_WEATHER_FORECAST_FOR_PREHEAT, DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT)
            )
            self.settings_data[CONF_PREHEAT_IGNORES_AWAY] = bool(
                user_input.get(CONF_PREHEAT_IGNORES_AWAY, DEFAULT_PREHEAT_IGNORES_AWAY)
            )
            return await self.async_step_init()

        supported_presets = self._get_supported_presets()

        schema = vol.Schema(
            {
                vol.Optional(CONF_OUTSIDE_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_OUTSIDE_WEATHER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(CONF_HEATING_ACTIVE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean"])
                ),
                vol.Optional(CONF_ENABLE_SELF_LEARNING): BooleanSelector(),
                vol.Optional(CONF_FALLBACK_HEATING_RATE): NumberSelector(
                    NumberSelectorConfig(
                        min=0.05, max=5.0, step=0.05, unit_of_measurement="K/h", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_FALLBACK_COOLING_RATE): NumberSelector(
                    NumberSelectorConfig(
                        min=0.01, max=3.0, step=0.01, unit_of_measurement="K/h", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_ZONE_HOME_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="zone")
                ),
                vol.Optional(CONF_ZONE_AWAY_NEAR_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="zone")
                ),
                vol.Optional(CONF_NEAR_DISTANCE): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0, max=5.0, step=0.05, unit_of_measurement="km", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_DEFAULT_PRESET): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=supported_presets,
                    )
                ),
                vol.Optional(CONF_PREHEAT_ENABLED): BooleanSelector(),
                vol.Optional(CONF_PREHEAT_IGNORES_AWAY): BooleanSelector(),
                vol.Optional(CONF_MAX_MINUTES_PREHEAT): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=720, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_COOLDOWN_ENABLED): BooleanSelector(),
                vol.Optional(CONF_MAX_MINUTES_COOLDOWN): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=720, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_HVAC_OFF_ON_TARGET): BooleanSelector(),
                vol.Optional(CONF_FALLBACK_TOLERANCE): NumberSelector(
                    NumberSelectorConfig(
                        min=0.05, max=2.0, step=0.05, unit_of_measurement="K", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_OPPORTUNISTIC_HEATING): BooleanSelector(),
                vol.Optional(CONF_USE_WEATHER_FORECAST_FOR_PREHEAT): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(schema, self.settings_data),
        )

    async def async_step_schedule_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Menu for schedules and profiles."""
        self._init_data()

        if user_input is not None:
            action = user_input.get("action") or user_input.get("aktion")
            if action == "back":
                return await self.async_step_init()
            if action == "switch_profile":
                return await self.async_step_switch_profile()
            if action == "add_profile":
                return await self.async_step_add_profile()
            if action == "rename_profile":
                return await self.async_step_rename_profile()
            if action == "delete_profile":
                return await self.async_step_delete_profile()
            if action == "edit":
                self.selected_day = user_input.get("day") or user_input.get("tag") or self.selected_day
                return await self.async_step_slot_overview()

        schedule_actions = ["edit", "switch_profile", "add_profile", "rename_profile"]
        if self.profiles and len(self.profiles) > 1:
            schedule_actions.append("delete_profile")
        schedule_actions.append("back")

        schema = vol.Schema(
            {
                vol.Required("action", default="edit"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="schedule_action",
                        options=schedule_actions,
                    )
                ),
                vol.Required("day", default=self.selected_day): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="day",
                        options=DAYS,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="schedule_menu",
            data_schema=schema,
            description_placeholders={"active_profile": self.active_profile},
        )

    async def async_step_switch_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select active schedule profile."""
        self._init_data()

        if user_input is not None:
            chosen = user_input["profile"]
            if self.profiles and chosen in self.profiles:
                if self.current_schedule is not None:
                    self.profiles[self.active_profile] = copy.deepcopy(self.current_schedule)
                self.active_profile = chosen
                self.current_schedule = _normalize_schedule(self.profiles.get(chosen, {}))
            return await self.async_step_schedule_menu()

        profile_options = list(self.profiles.keys()) if self.profiles else ["Standard"]
        schema = vol.Schema(
            {
                vol.Required("profile", default=self.active_profile): SelectSelector(
                    SelectSelectorConfig(options=profile_options)
                )
            }
        )
        return self.async_show_form(step_id="switch_profile", data_schema=schema)

    async def async_step_add_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new schedule profile."""
        self._init_data()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_name = str(user_input.get("profile_name", "")).strip()
            if not new_name:
                errors["base"] = "profile_name_empty"
            elif self.profiles and new_name in self.profiles:
                errors["base"] = "profile_name_exists"
            else:
                source = user_input.get("source_profile", "empty")
                if self.profiles is not None:
                    if self.current_schedule is not None:
                        self.profiles[self.active_profile] = copy.deepcopy(self.current_schedule)

                    if source != "empty" and source in self.profiles:
                        self.profiles[new_name] = copy.deepcopy(self.profiles[source])
                    else:
                        self.profiles[new_name] = _normalize_schedule({})

                    self.active_profile = new_name
                    self.current_schedule = _normalize_schedule(self.profiles[new_name])
                    return await self.async_step_schedule_menu()

        lang = get_ha_language(getattr(self, "hass", None))
        empty_label = get_localized_ui_text("empty_schedule", lang)
        profile_choices = [{"value": "empty", "label": empty_label}] + [
            {
                "value": p,
                "label": get_localized_ui_text("copy_of_profile", lang, profile=p),
            }
            for p in (self.profiles.keys() if self.profiles else [])
        ]
        schema = vol.Schema(
            {
                vol.Required("profile_name"): TextSelector(),
                vol.Required("source_profile", default="empty"): SelectSelector(
                    SelectSelectorConfig(options=profile_choices)
                ),
            }
        )
        return self.async_show_form(step_id="add_profile", data_schema=schema, errors=errors)

    async def async_step_rename_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Rename an existing schedule profile (including Standard)."""
        self._init_data()
        errors: dict[str, str] = {}

        if user_input is not None:
            old_name = user_input.get("old_profile")
            new_name = str(user_input.get("new_name", "")).strip()

            if not new_name:
                errors["base"] = "profile_name_empty"
            elif self.profiles and new_name in self.profiles and new_name != old_name:
                errors["base"] = "profile_name_exists"
            elif self.profiles and old_name in self.profiles:
                if self.current_schedule is not None and old_name == self.active_profile:
                    self.profiles[old_name] = copy.deepcopy(self.current_schedule)

                profile_data = self.profiles.pop(old_name)
                self.profiles[new_name] = profile_data

                if old_name == self.active_profile:
                    self.active_profile = new_name
                    self.current_schedule = profile_data

                return await self.async_step_schedule_menu()

        profile_options = list(self.profiles.keys()) if self.profiles else ["Standard"]
        default_old = self.active_profile if self.active_profile in profile_options else profile_options[0]

        schema = vol.Schema(
            {
                vol.Required("old_profile", default=default_old): SelectSelector(
                    SelectSelectorConfig(options=profile_options)
                ),
                vol.Required("new_name", default=default_old): TextSelector(),
            }
        )
        return self.async_show_form(step_id="rename_profile", data_schema=schema, errors=errors)

    async def async_step_delete_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Delete an existing schedule profile."""
        self._init_data()
        errors: dict[str, str] = {}

        if not self.profiles or len(self.profiles) <= 1:
            return await self.async_step_schedule_menu()

        if user_input is not None:
            to_delete = user_input.get("profile_to_delete")
            if to_delete in self.profiles and len(self.profiles) > 1:
                self.profiles.pop(to_delete)
                if to_delete == self.active_profile:
                    self.active_profile = list(self.profiles.keys())[0]
                    self.current_schedule = _normalize_schedule(self.profiles[self.active_profile])
                return await self.async_step_schedule_menu()

        deletable_profiles = list(self.profiles.keys())
        schema = vol.Schema(
            {
                vol.Required("profile_to_delete"): SelectSelector(
                    SelectSelectorConfig(options=deletable_profiles)
                )
            }
        )
        return self.async_show_form(step_id="delete_profile", data_schema=schema, errors=errors)

    async def async_step_slot_overview(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Overview and actions for the selected weekday's slots."""
        self._init_data()

        if user_input is not None:
            choice = user_input.get("slot_action") or user_input.get("slot_aktion")
            if choice == "add":
                return await self.async_step_add_slot()
            if choice == "edit":
                return await self.async_step_select_slot_to_edit()
            if choice == "copy":
                return await self.async_step_copy_slots()
            if choice == "clear":
                self.current_schedule[self.selected_day] = []
                return await self.async_step_slot_overview()
            if choice == "back":
                return await self.async_step_schedule_menu()

        slots = self.current_schedule.get(self.selected_day, [])
        has_slots = len(slots) > 0

        actions = ["add"]
        if has_slots:
            actions.extend(["edit", "copy", "clear"])
        actions.append("back")

        schema = vol.Schema(
            {
                vol.Required("slot_action", default="add"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="slot_action",
                        options=actions,
                    )
                )
            }
        )

        lang = get_ha_language(getattr(self, "hass", None))
        if slots:
            slot_lines = []
            for idx, s in enumerate(slots):
                p = s.get("preset", "none")
                p_label = _format_preset(p, lang)
                f = s.get("from", "00:00:00")[:5]
                t = s.get("to", "00:00:00")[:5]
                item_text = get_localized_ui_text(
                    "slot_item",
                    lang,
                    index=idx + 1,
                    from_time=f,
                    to_time=t,
                    preset=p_label,
                )
                slot_lines.append(f"• {item_text}")
            slots_list_str = "\n" + "\n".join(slot_lines)
        else:
            slots_list_str = "\n" + get_localized_ui_text("no_slots_configured", lang)

        return self.async_show_form(
            step_id="slot_overview",
            data_schema=schema,
            description_placeholders={
                "slots_count": str(len(slots)),
                "slots_list": slots_list_str,
            },
        )

    async def async_step_select_slot_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Displays a list of all slots of a day for selection."""
        self._init_data()
        slots = self.current_schedule.get(self.selected_day, [])

        if not slots:
            return await self.async_step_slot_overview()

        if user_input is not None:
            selected_val = user_input["selected_slot"]
            if selected_val.startswith("slot_"):
                self.selected_slot_index = int(selected_val.split("_")[1])
                return await self.async_step_edit_slot()

        lang = get_ha_language(getattr(self, "hass", None))
        options = []
        for idx, slot in enumerate(slots):
            preset = slot.get("preset", "none")
            preset_label = _format_preset(preset, lang)
            from_t = slot.get("from", "00:00:00")
            to_t = slot.get("to", "00:00:00")
            label = get_localized_ui_text(
                "slot_item",
                lang,
                index=idx + 1,
                from_time=from_t[:5],
                to_time=to_t[:5],
                preset=preset_label,
            )
            options.append({"value": f"slot_{idx}", "label": label})

        schema = vol.Schema(
            {
                vol.Required("selected_slot"): SelectSelector(
                    SelectSelectorConfig(options=options)
                )
            }
        )

        return self.async_show_form(
            step_id="select_slot_to_edit",
            data_schema=schema,
        )

    async def async_step_copy_slots(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Copies the slots of the current day to multiple selected weekdays."""
        self._init_data()

        if user_input is not None:
            target_days = user_input.get("target_days", [])
            source_slots = self.current_schedule.get(self.selected_day, [])

            for day in target_days:
                self.current_schedule[day] = copy.deepcopy(source_slots)

            return await self.async_step_slot_overview()

        other_days = [d for d in DAYS if d != self.selected_day]

        schema = vol.Schema(
            {
                vol.Required("target_days"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="day",
                        options=other_days,
                        multiple=True,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="copy_slots",
            data_schema=schema,
        )

    async def async_step_add_slot(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a slot with time range validation."""
        self._init_data()
        errors: dict[str, str] = {}

        if user_input is not None:
            start_str = user_input.get("start_time") or user_input.get("startzeit")
            end_str = user_input.get("end_time") or user_input.get("endzeit")
            start_t = parse_time(start_str)
            end_t = parse_time(end_str)

            if start_t and end_t and start_t >= end_t:
                errors["base"] = "invalid_time_range"
            else:
                slot_data: dict[str, Any] = {
                    "from": start_str,
                    "to": end_str,
                    "preset": user_input["preset"],
                }

                day_slots = list(self.current_schedule.get(self.selected_day, []))
                day_slots.append(slot_data)
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

        supported_presets = self._get_supported_presets()
        default_preset = supported_presets[0] if supported_presets else "none"

        schema = vol.Schema(
            {
                vol.Required("start_time"): TimeSelector(),
                vol.Required("end_time"): TimeSelector(),
                vol.Required("preset", default=default_preset): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=supported_presets,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="add_slot", data_schema=schema, errors=errors)

    async def async_step_edit_slot(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit or delete a slot with time range validation."""
        self._init_data()
        day_slots = list(self.current_schedule.get(self.selected_day, []))
        errors: dict[str, str] = {}

        if (
            self.selected_slot_index is None
            or self.selected_slot_index >= len(day_slots)
        ):
            return await self.async_step_slot_overview()

        current_slot = day_slots[self.selected_slot_index]

        if user_input is not None:
            action = user_input.get("action") or user_input.get("aktion")
            if action == "delete":
                day_slots.pop(self.selected_slot_index)
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

            start_str = user_input.get("start_time") or user_input.get("startzeit")
            end_str = user_input.get("end_time") or user_input.get("endzeit")
            start_t = parse_time(start_str)
            end_t = parse_time(end_str)

            if start_t and end_t and start_t >= end_t:
                errors["base"] = "invalid_time_range"
            else:
                updated_slot: dict[str, Any] = {
                    "from": start_str,
                    "to": end_str,
                    "preset": user_input["preset"],
                }

                day_slots[self.selected_slot_index] = updated_slot
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

        supported_presets = self._get_supported_presets()
        current_preset = current_slot.get("preset") or (
            supported_presets[0] if supported_presets else "none"
        )

        edit_schema_dict: dict[Any, Any] = {
            vol.Required("action", default="update"): SelectSelector(
                SelectSelectorConfig(
                    translation_key="edit_action",
                    options=["update", "delete"],
                )
            ),
            vol.Required(
                "start_time", default=current_slot.get("from", "00:00:00")
            ): TimeSelector(),
            vol.Required(
                "end_time", default=current_slot.get("to", "00:00:00")
            ): TimeSelector(),
            vol.Required("preset", default=current_preset): SelectSelector(
                SelectSelectorConfig(
                    translation_key="preset",
                    options=supported_presets,
                )
            ),
        }

        return self.async_show_form(step_id="edit_slot", data_schema=vol.Schema(edit_schema_dict), errors=errors)
