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
    CONF_CLIMATE_ENTITIES,
    CONF_CLIMATE_ENTITY,
    CONF_COOLDOWN_ENABLED,
    CONF_CUSTOM_PRESETS,
    CONF_DEFAULT_PRESET,
    CONF_MAX_MINUTES_COOLDOWN,
    CONF_MAX_MINUTES_PREHEAT,
    CONF_NEAR_DISTANCE,
    CONF_PREHEAT_ENABLED,
    CONF_ROOM_TEMP_SENSOR,
    CONF_WINDOW_CLOSE_DELAY_MINUTES,
    CONF_WINDOW_OPEN_DELAY_MINUTES,
    CONF_WINDOW_PAUSE_ENABLED,
    CONF_WINDOW_SENSORS,
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
    CONF_AWAY_PRESET,
    CONF_AWAY_NEAR_PRESET,
    CONF_ANOMALY_DETECTION_ENABLED,
    CONF_ANOMALY_NO_HEAT_MINUTES,
    CUSTOM_PRESET_COLOR_OPTIONS,
    CUSTOM_PRESET_HEX_TO_KEY,
    CUSTOM_PRESET_PALETTE,
    DAYS,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_CUSTOM_PRESETS,
    DEFAULT_FALLBACK_PRESET,
    DEFAULT_AWAY_PRESET,
    DEFAULT_AWAY_NEAR_PRESET,
    DEFAULT_ANOMALY_DETECTION_ENABLED,
    DEFAULT_ANOMALY_NO_HEAT_MINUTES,
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
    DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
    DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
    DEFAULT_WINDOW_PAUSE_ENABLED,
    DOMAIN,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
)
from .helpers import (
    get_climate_entities,
    get_custom_presets,
    get_ha_language,
    get_profiles_and_active,
    get_window_delays,
    get_window_sensors,
    normalize_custom_presets,
    parse_time,
    safe_float as _safe_float,
    slugify_preset_id,
)

DEFAULT_PRESETS = [p["id"] for p in DEFAULT_CUSTOM_PRESETS]


def _normalize_entity_list(raw: Any) -> list[str]:
    """Normalizes a single entity ID or list of entity IDs into a deduplicated list."""
    result: list[str] = []
    if isinstance(raw, (list, tuple, set)):
        items = raw
    elif isinstance(raw, str) and raw.strip():
        items = [p.strip() for p in raw.split(",")]
    else:
        items = []
    for item in items:
        if isinstance(item, str):
            val = item.strip()
            if val and val not in result:
                result.append(val)
    return result


def _clamp_window_delay(raw: Any, default: int) -> int:
    try:
        return max(0, min(60, int(round(float(raw)))))
    except (ValueError, TypeError):
        return default


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
                            "preheat": bool(slot.get("preheat", True)),
                            "cooldown": bool(slot.get("cooldown", True)),
                        }
                    )
        normalized[day] = normalized_day
    return normalized


def _format_slot_item_with_flags(
    idx: int,
    slot: dict,
    lang: str,
    custom_labels: dict[str, str] | None = None,
) -> str:
    """Formats a slot line including localized preheat and cooldown status indicators."""
    p = _get_slot_preset(slot)
    p_label = _format_preset(p, lang, custom_labels=custom_labels)
    f = slot.get("from", "00:00:00")[:5]
    t = slot.get("to", "00:00:00")[:5]
    base_text = get_localized_ui_text(
        "slot_item",
        lang,
        index=idx + 1,
        from_time=f,
        to_time=t,
        preset=p_label,
    )
    preheat_state = get_localized_ui_text(
        "state_on" if bool(slot.get("preheat", True)) else "state_off",
        lang,
    )
    cooldown_state = get_localized_ui_text(
        "state_on" if bool(slot.get("cooldown", True)) else "state_off",
        lang,
    )
    flags_text = get_localized_ui_text(
        "slot_thermal_flags",
        lang,
        preheat=preheat_state,
        cooldown=cooldown_state,
    )
    return f"{base_text} [{flags_text}]"


class SmartClimateSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the initial 4-step configuration wizard for the integration."""

    VERSION = 4

    def __init__(self) -> None:
        super().__init__()
        self._config_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1/4: Room name, thermostats, room sensor, burner sensor and default preset."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input.get("name", "")).strip()
            climate_entities = _normalize_entity_list(
                user_input.get(CONF_CLIMATE_ENTITIES) or user_input.get(CONF_CLIMATE_ENTITY)
            )
            if not name:
                errors["base"] = "name_required"
            elif not climate_entities:
                errors["base"] = "climate_required"
            else:
                unique_id = name.lower().replace(" ", "_")
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                raw_room_sensor = user_input.get(CONF_ROOM_TEMP_SENSOR)
                raw_heating_sensor = user_input.get(CONF_HEATING_ACTIVE_SENSOR)
                self._config_data = {
                    "name": name,
                    CONF_CLIMATE_ENTITIES: climate_entities,
                    CONF_CLIMATE_ENTITY: climate_entities[0],
                    CONF_CUSTOM_PRESETS: normalize_custom_presets(
                        user_input.get(CONF_CUSTOM_PRESETS), fallback_to_default=True
                    ),
                    CONF_ROOM_TEMP_SENSOR: (
                        raw_room_sensor.strip()
                        if isinstance(raw_room_sensor, str) and raw_room_sensor.strip()
                        else None
                    ),
                    CONF_HEATING_ACTIVE_SENSOR: (
                        raw_heating_sensor.strip()
                        if isinstance(raw_heating_sensor, str) and raw_heating_sensor.strip()
                        else None
                    ),
                    CONF_DEFAULT_PRESET: user_input.get(CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET),
                }
                return await self.async_step_windows()

        schema = vol.Schema(
            {
                vol.Required("name"): TextSelector(TextSelectorConfig()),
                vol.Required(CONF_CLIMATE_ENTITIES): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_HEATING_ACTIVE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean"])
                ),
                vol.Optional(
                    CONF_DEFAULT_PRESET, default=DEFAULT_FALLBACK_PRESET
                ): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=DEFAULT_PRESETS,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2/4: Window/door contacts and pause delays."""
        if user_input is not None:
            self._config_data[CONF_WINDOW_SENSORS] = _normalize_entity_list(
                user_input.get(CONF_WINDOW_SENSORS)
            )
            self._config_data[CONF_WINDOW_PAUSE_ENABLED] = bool(
                user_input.get(CONF_WINDOW_PAUSE_ENABLED, DEFAULT_WINDOW_PAUSE_ENABLED)
            )
            self._config_data[CONF_WINDOW_OPEN_DELAY_MINUTES] = _clamp_window_delay(
                user_input.get(CONF_WINDOW_OPEN_DELAY_MINUTES),
                DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
            )
            self._config_data[CONF_WINDOW_CLOSE_DELAY_MINUTES] = _clamp_window_delay(
                user_input.get(CONF_WINDOW_CLOSE_DELAY_MINUTES),
                DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
            )
            return await self.async_step_thermal()

        schema = vol.Schema(
            {
                vol.Optional(CONF_WINDOW_SENSORS): EntitySelector(
                    EntitySelectorConfig(
                        domain="binary_sensor",
                        device_class=["window", "door"],
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_WINDOW_PAUSE_ENABLED, default=DEFAULT_WINDOW_PAUSE_ENABLED
                ): BooleanSelector(),
                vol.Optional(
                    CONF_WINDOW_OPEN_DELAY_MINUTES, default=DEFAULT_WINDOW_OPEN_DELAY_MINUTES
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_WINDOW_CLOSE_DELAY_MINUTES, default=DEFAULT_WINDOW_CLOSE_DELAY_MINUTES
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="windows",
            data_schema=schema,
            last_step=False,
        )

    async def async_step_thermal(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 3/4: Outdoor weather, preheat/cooldown, adaptive learning & control hysteresis."""
        if user_input is not None:
            self._config_data[CONF_OUTSIDE_TEMP_SENSOR] = user_input.get(CONF_OUTSIDE_TEMP_SENSOR)
            self._config_data[CONF_OUTSIDE_WEATHER_ENTITY] = user_input.get(CONF_OUTSIDE_WEATHER_ENTITY)
            self._config_data[CONF_USE_WEATHER_FORECAST_FOR_PREHEAT] = bool(
                user_input.get(
                    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
                    DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
                )
            )
            self._config_data[CONF_PREHEAT_ENABLED] = bool(
                user_input.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED)
            )
            self._config_data[CONF_MAX_MINUTES_PREHEAT] = max(
                0,
                min(
                    720,
                    int(
                        round(
                            _safe_float(
                                user_input.get(CONF_MAX_MINUTES_PREHEAT),
                                DEFAULT_MAX_MINUTES_PREHEAT,
                                allow_zero_or_negative=True,
                            )
                        )
                    ),
                ),
            )
            self._config_data[CONF_COOLDOWN_ENABLED] = bool(
                user_input.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED)
            )
            self._config_data[CONF_MAX_MINUTES_COOLDOWN] = max(
                0,
                min(
                    720,
                    int(
                        round(
                            _safe_float(
                                user_input.get(CONF_MAX_MINUTES_COOLDOWN),
                                DEFAULT_MAX_MINUTES_COOLDOWN,
                                allow_zero_or_negative=True,
                            )
                        )
                    ),
                ),
            )
            self._config_data[CONF_ENABLE_SELF_LEARNING] = bool(
                user_input.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING)
            )
            self._config_data[CONF_FALLBACK_HEATING_RATE] = _safe_float(
                user_input.get(CONF_FALLBACK_HEATING_RATE), DEFAULT_FALLBACK_HEATING_RATE
            )
            self._config_data[CONF_FALLBACK_COOLING_RATE] = _safe_float(
                user_input.get(CONF_FALLBACK_COOLING_RATE), DEFAULT_FALLBACK_COOLING_RATE
            )
            self._config_data[CONF_HVAC_OFF_ON_TARGET] = bool(
                user_input.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET)
            )
            self._config_data[CONF_FALLBACK_TOLERANCE] = max(
                0.0,
                _safe_float(
                    user_input.get(CONF_FALLBACK_TOLERANCE),
                    DEFAULT_FALLBACK_TOLERANCE,
                    allow_zero_or_negative=True,
                ),
            )
            self._config_data[CONF_OPPORTUNISTIC_HEATING] = bool(
                user_input.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING)
            )
            return await self.async_step_presence()

        schema = vol.Schema(
            {
                vol.Optional(CONF_OUTSIDE_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_OUTSIDE_WEATHER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
                    default=DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
                ): BooleanSelector(),
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
                vol.Optional(CONF_HVAC_OFF_ON_TARGET, default=DEFAULT_HVAC_OFF_ON_TARGET): BooleanSelector(),
                vol.Optional(
                    CONF_FALLBACK_TOLERANCE, default=DEFAULT_FALLBACK_TOLERANCE
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0, max=2.0, step=0.05, unit_of_measurement="K", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_OPPORTUNISTIC_HEATING, default=DEFAULT_OPPORTUNISTIC_HEATING
                ): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="thermal",
            data_schema=schema,
            last_step=False,
        )

    async def async_step_presence(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 4/4: Presence zones, away presets & anomaly guard."""
        if user_input is not None:
            self._config_data[CONF_ZONE_HOME_ENTITY] = user_input.get(
                CONF_ZONE_HOME_ENTITY, "zone.home"
            )
            self._config_data[CONF_ZONE_AWAY_NEAR_ENTITY] = user_input.get(CONF_ZONE_AWAY_NEAR_ENTITY)
            self._config_data[CONF_NEAR_DISTANCE] = max(
                0.0,
                _safe_float(
                    user_input.get(CONF_NEAR_DISTANCE),
                    DEFAULT_NEAR_DISTANCE,
                    allow_zero_or_negative=True,
                ),
            )
            self._config_data[CONF_AWAY_NEAR_PRESET] = user_input.get(
                CONF_AWAY_NEAR_PRESET, DEFAULT_AWAY_NEAR_PRESET
            )
            self._config_data[CONF_AWAY_PRESET] = user_input.get(
                CONF_AWAY_PRESET, DEFAULT_AWAY_PRESET
            )
            self._config_data[CONF_PREHEAT_IGNORES_AWAY] = bool(
                user_input.get(CONF_PREHEAT_IGNORES_AWAY, DEFAULT_PREHEAT_IGNORES_AWAY)
            )
            self._config_data[CONF_ANOMALY_DETECTION_ENABLED] = bool(
                user_input.get(CONF_ANOMALY_DETECTION_ENABLED, DEFAULT_ANOMALY_DETECTION_ENABLED)
            )
            self._config_data[CONF_ANOMALY_NO_HEAT_MINUTES] = max(
                0,
                min(
                    240,
                    int(
                        round(
                            _safe_float(
                                user_input.get(CONF_ANOMALY_NO_HEAT_MINUTES),
                                DEFAULT_ANOMALY_NO_HEAT_MINUTES,
                                allow_zero_or_negative=True,
                            )
                        )
                    ),
                ),
            )

            default_schedule = {day: [] for day in DAYS}
            return self.async_create_entry(
                title=self._config_data.get("name", "Room"),
                data=dict(self._config_data),
                options={"schedule": default_schedule},
            )

        schema = vol.Schema(
            {
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
                    CONF_AWAY_NEAR_PRESET, default=DEFAULT_AWAY_NEAR_PRESET
                ): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=DEFAULT_PRESETS,
                    )
                ),
                vol.Optional(
                    CONF_AWAY_PRESET, default=DEFAULT_AWAY_PRESET
                ): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=DEFAULT_PRESETS,
                    )
                ),
                vol.Optional(
                    CONF_PREHEAT_IGNORES_AWAY, default=DEFAULT_PREHEAT_IGNORES_AWAY
                ): BooleanSelector(),
                vol.Optional(
                    CONF_ANOMALY_DETECTION_ENABLED, default=DEFAULT_ANOMALY_DETECTION_ENABLED
                ): BooleanSelector(),
                vol.Optional(
                    CONF_ANOMALY_NO_HEAT_MINUTES, default=DEFAULT_ANOMALY_NO_HEAT_MINUTES
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=240, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="presence",
            data_schema=schema,
            last_step=True,
        )

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
        self.selected_custom_preset_id: str | None = None

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
            climate_entities = get_climate_entities(self.config_entry)
            open_delay, close_delay, pause_enabled = get_window_delays(self.config_entry)

            self.settings_data = {
                CONF_CLIMATE_ENTITIES: climate_entities,
                CONF_CLIMATE_ENTITY: climate_entities[0] if climate_entities else "",
                CONF_CUSTOM_PRESETS: [dict(p) for p in get_custom_presets(self.config_entry)],
                CONF_ROOM_TEMP_SENSOR: options.get(
                    CONF_ROOM_TEMP_SENSOR, data.get(CONF_ROOM_TEMP_SENSOR)
                ),
                CONF_WINDOW_SENSORS: get_window_sensors(self.config_entry),
                CONF_WINDOW_OPEN_DELAY_MINUTES: open_delay,
                CONF_WINDOW_CLOSE_DELAY_MINUTES: close_delay,
                CONF_WINDOW_PAUSE_ENABLED: pause_enabled,
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
                CONF_AWAY_NEAR_PRESET: options.get(
                    CONF_AWAY_NEAR_PRESET, data.get(CONF_AWAY_NEAR_PRESET, DEFAULT_AWAY_NEAR_PRESET)
                ),
                CONF_AWAY_PRESET: options.get(
                    CONF_AWAY_PRESET, data.get(CONF_AWAY_PRESET, DEFAULT_AWAY_PRESET)
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
                CONF_FALLBACK_TOLERANCE: max(
                    0.0,
                    _safe_float(
                        options.get(
                            CONF_FALLBACK_TOLERANCE,
                            data.get(CONF_FALLBACK_TOLERANCE),
                        ),
                        DEFAULT_FALLBACK_TOLERANCE,
                        allow_zero_or_negative=True,
                    ),
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
                CONF_ANOMALY_DETECTION_ENABLED: bool(
                    options.get(
                        CONF_ANOMALY_DETECTION_ENABLED,
                        data.get(CONF_ANOMALY_DETECTION_ENABLED, DEFAULT_ANOMALY_DETECTION_ENABLED),
                    )
                ),
                CONF_ANOMALY_NO_HEAT_MINUTES: int(
                    _safe_float(
                        options.get(
                            CONF_ANOMALY_NO_HEAT_MINUTES,
                            data.get(CONF_ANOMALY_NO_HEAT_MINUTES),
                        ),
                        DEFAULT_ANOMALY_NO_HEAT_MINUTES,
                    )
                ),
            }

    def _get_custom_presets_list(self) -> list[dict[str, Any]]:
        raw = self.settings_data.get(CONF_CUSTOM_PRESETS)
        presets = normalize_custom_presets(raw, fallback_to_default=True)
        self.settings_data[CONF_CUSTOM_PRESETS] = [dict(p) for p in presets]
        return presets

    def _custom_labels(self) -> dict[str, str]:
        return {
            p["id"]: f"{p['name']} ({p['temperature']:.1f} °C)"
            for p in self._get_custom_presets_list()
        }

    def _get_supported_presets(self) -> list[str]:
        return [p["id"] for p in self._get_custom_presets_list()]

    def _build_preset_selector(self, include_none: bool = False) -> SelectSelector:
        lang = get_ha_language(getattr(self, "hass", None))
        options: list[dict[str, str]] = []
        if include_none:
            options.append({"value": "none", "label": _format_preset("none", lang)})
        for p in self._get_custom_presets_list():
            options.append(
                {
                    "value": p["id"],
                    "label": f"{p['name']} ({p['temperature']:.1f} °C)",
                }
            )
        return SelectSelector(SelectSelectorConfig(options=options))

    def _remap_deleted_preset(self, deleted_id: str, replacement_id: str) -> None:
        if self.current_schedule:
            for day in DAYS:
                for slot in self.current_schedule.get(day, []):
                    if _get_slot_preset(slot) == deleted_id:
                        slot["preset"] = replacement_id
        if self.profiles:
            for prof_sched in self.profiles.values():
                if isinstance(prof_sched, dict):
                    for day in DAYS:
                        for slot in prof_sched.get(day, []):
                            if isinstance(slot, dict) and _get_slot_preset(slot) == deleted_id:
                                slot["preset"] = replacement_id
        for key in (CONF_DEFAULT_PRESET, CONF_AWAY_NEAR_PRESET, CONF_AWAY_PRESET):
            if self.settings_data.get(key) == deleted_id:
                self.settings_data[key] = replacement_id

    def _ensure_valid_direct_presets_in_settings(self) -> None:
        presets = self._get_custom_presets_list()
        valid_ids = {p["id"] for p in presets}
        if not valid_ids:
            return
        fallback_first = presets[0]["id"]
        for key, preferred in (
            (CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET),
            (CONF_AWAY_NEAR_PRESET, DEFAULT_AWAY_NEAR_PRESET),
            (CONF_AWAY_PRESET, DEFAULT_AWAY_PRESET),
        ):
            cur = str(self.settings_data.get(key) or "").strip().lower()
            if cur not in valid_ids:
                self.settings_data[key] = preferred if preferred in valid_ids else fallback_first

    def _async_commit_and_save(self) -> config_entries.ConfigFlowResult:
        """Persists buffered profiles, schedule, and settings into entry data & options."""
        if self.profiles is not None and self.current_schedule is not None:
            self.profiles[self.active_profile] = copy.deepcopy(self.current_schedule)

        entities = _normalize_entity_list(self.settings_data.get(CONF_CLIMATE_ENTITIES))
        if not entities:
            entities = get_climate_entities(self.config_entry)
        self.settings_data[CONF_CLIMATE_ENTITIES] = entities
        if entities:
            self.settings_data[CONF_CLIMATE_ENTITY] = entities[0]
        self.settings_data[CONF_CUSTOM_PRESETS] = self._get_custom_presets_list()
        self._ensure_valid_direct_presets_in_settings()

        new_options = {
            "schedule": self.current_schedule,
            "profiles": self.profiles,
            "active_profile": self.active_profile,
            **self.settings_data,
        }
        new_data = dict(self.config_entry.data)
        new_data.update(self.settings_data)
        for legacy_key in (
            "control_mode",
            "tolerance_entity",
            "window_open_delay_seconds",
            "window_close_delay_seconds",
        ):
            new_data.pop(legacy_key, None)
            new_options.pop(legacy_key, None)
        data_changed = new_data != dict(self.config_entry.data)
        options_changed = new_options != dict(self.config_entry.options)
        if data_changed:
            if options_changed:
                domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                if isinstance(domain_data, dict):
                    domain_data["_updating_from_options_data"] = True
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

        return self.async_create_entry(
            title="",
            data=new_options,
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Main menu step."""
        self._init_data()

        if user_input is not None:
            action = user_input.get("main_action")
            if action == "settings":
                return await self.async_step_settings()
            elif action == "custom_presets":
                return await self.async_step_custom_presets()
            elif action == "schedules":
                return await self.async_step_schedule_menu()
            elif action == "save":
                return self._async_commit_and_save()

        schema = vol.Schema(
            {
                vol.Required("main_action", default="schedules"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="init_action",
                        options=["schedules", "custom_presets", "settings", "save"],
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_custom_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage room custom presets (0.1 °C steps)."""
        self._init_data()
        presets = self._get_custom_presets_list()

        if user_input is not None:
            action = user_input.get("preset_action")
            if action == "add":
                return await self.async_step_add_custom_preset()
            if action == "edit" and presets:
                return await self.async_step_select_custom_preset()
            if action == "back":
                return await self.async_step_init()

        actions = ["add"]
        if presets:
            actions.append("edit")
        actions.append("back")

        preset_lines = "\n" + "\n".join(
            f"• {p['name']}: {p['temperature']:.1f} °C ({p['color']})"
            for p in presets
        )
        schema = vol.Schema(
            {
                vol.Required("preset_action", default="add"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="custom_preset_action",
                        options=actions,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="custom_presets",
            data_schema=schema,
            description_placeholders={
                "presets_count": str(len(presets)),
                "presets_list": preset_lines,
            },
        )

    async def async_step_add_custom_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new custom preset in 0.1 °C precision."""
        self._init_data()
        presets = self._get_custom_presets_list()
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_name = str(user_input.get("name", "")).strip()
            if not raw_name:
                errors["base"] = "preset_name_empty"
            else:
                existing_ids = {p["id"] for p in presets}
                new_id = slugify_preset_id(raw_name, existing_ids)
                new_item = normalize_custom_presets(
                    [
                        {
                            "id": new_id,
                            "name": raw_name,
                            "temperature": user_input.get("temperature", 20.0),
                            "color": user_input.get("color", CUSTOM_PRESET_PALETTE[len(presets) % len(CUSTOM_PRESET_PALETTE)]),
                        }
                    ],
                    fallback_to_default=False,
                )[0]
                new_item["id"] = new_id
                presets.append(new_item)
                self.settings_data[CONF_CUSTOM_PRESETS] = presets
                return await self.async_step_custom_presets()

        default_color_key = CUSTOM_PRESET_COLOR_OPTIONS[len(presets) % len(CUSTOM_PRESET_COLOR_OPTIONS)]
        schema = vol.Schema(
            {
                vol.Required("name"): TextSelector(TextSelectorConfig()),
                vol.Required("temperature", default=20.0): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TARGET_TEMP,
                        max=MAX_TARGET_TEMP,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required("color", default=default_color_key): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset_color",
                        options=CUSTOM_PRESET_COLOR_OPTIONS,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="add_custom_preset",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_select_custom_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a custom preset to edit or delete."""
        self._init_data()
        presets = self._get_custom_presets_list()
        if not presets:
            return await self.async_step_custom_presets()

        if user_input is not None:
            self.selected_custom_preset_id = user_input.get("selected_preset")
            return await self.async_step_edit_custom_preset()

        options = [
            {"value": p["id"], "label": f"{p['name']} ({p['temperature']:.1f} °C)"}
            for p in presets
        ]
        schema = vol.Schema(
            {
                vol.Required("selected_preset", default=presets[0]["id"]): SelectSelector(
                    SelectSelectorConfig(options=options)
                )
            }
        )
        return self.async_show_form(step_id="select_custom_preset", data_schema=schema)

    async def async_step_edit_custom_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit or delete the selected custom preset."""
        self._init_data()
        presets = self._get_custom_presets_list()
        target_idx = next(
            (i for i, p in enumerate(presets) if p["id"] == self.selected_custom_preset_id),
            None,
        )
        if target_idx is None:
            return await self.async_step_custom_presets()

        current = presets[target_idx]
        errors: dict[str, str] = {}

        if user_input is not None:
            action = user_input.get("action", "update")
            if action == "delete":
                if len(presets) <= 1:
                    errors["base"] = "cannot_delete_last_preset"
                else:
                    deleted = presets.pop(target_idx)
                    self.settings_data[CONF_CUSTOM_PRESETS] = presets
                    self._remap_deleted_preset(deleted["id"], presets[0]["id"])
                    return await self.async_step_custom_presets()
            else:
                raw_name = str(user_input.get("name", "")).strip()
                if not raw_name:
                    errors["base"] = "preset_name_empty"
                else:
                    updated = normalize_custom_presets(
                        [
                            {
                                "id": current["id"],
                                "name": raw_name,
                                "temperature": user_input.get("temperature", current["temperature"]),
                                "color": user_input.get("color", current["color"]),
                            }
                        ],
                        fallback_to_default=False,
                    )[0]
                    updated["id"] = current["id"]
                    presets[target_idx] = updated
                    self.settings_data[CONF_CUSTOM_PRESETS] = presets
                    return await self.async_step_custom_presets()

        schema = vol.Schema(
            {
                vol.Required("action", default="update"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="edit_action",
                        options=["update", "delete"],
                    )
                ),
                vol.Required("name", default=current["name"]): TextSelector(TextSelectorConfig()),
                vol.Required("temperature", default=float(current["temperature"])): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TARGET_TEMP,
                        max=MAX_TARGET_TEMP,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    "color",
                    default=CUSTOM_PRESET_HEX_TO_KEY.get(
                        str(current["color"]).strip().lower(),
                        CUSTOM_PRESET_COLOR_OPTIONS[0],
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset_color",
                        options=CUSTOM_PRESET_COLOR_OPTIONS,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="edit_custom_preset",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Settings category submenu."""
        self._init_data()

        if user_input is not None:
            section = user_input.get("settings_section")
            if section == "devices":
                return await self.async_step_settings_devices()
            if section == "windows":
                return await self.async_step_settings_windows()
            if section == "thermal":
                return await self.async_step_settings_thermal()
            if section == "presence":
                return await self.async_step_settings_presence()
            if section == "save":
                return self._async_commit_and_save()
            if section == "back":
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("settings_section", default="devices"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="settings_section",
                        options=["devices", "windows", "thermal", "presence", "save", "back"],
                    )
                )
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_settings_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Settings category 1/4: Thermostats, room sensor, burner entity & default preset."""
        self._init_data()
        errors: dict[str, str] = {}

        if user_input is not None:
            has_climate_input = (
                CONF_CLIMATE_ENTITIES in user_input or CONF_CLIMATE_ENTITY in user_input
            )
            if has_climate_input:
                climate_entities = _normalize_entity_list(
                    user_input.get(CONF_CLIMATE_ENTITIES) or user_input.get(CONF_CLIMATE_ENTITY)
                )
            else:
                climate_entities = _normalize_entity_list(
                    self.settings_data.get(CONF_CLIMATE_ENTITIES)
                    or self.settings_data.get(CONF_CLIMATE_ENTITY)
                )
            if has_climate_input and not climate_entities:
                errors["base"] = "climate_required"
            else:
                self.settings_data[CONF_CLIMATE_ENTITIES] = climate_entities
                if climate_entities:
                    self.settings_data[CONF_CLIMATE_ENTITY] = climate_entities[0]
                raw_room_sensor = user_input.get(CONF_ROOM_TEMP_SENSOR)
                self.settings_data[CONF_ROOM_TEMP_SENSOR] = (
                    raw_room_sensor.strip()
                    if isinstance(raw_room_sensor, str) and raw_room_sensor.strip()
                    else None
                )
                raw_heating_sensor = user_input.get(CONF_HEATING_ACTIVE_SENSOR)
                self.settings_data[CONF_HEATING_ACTIVE_SENSOR] = (
                    raw_heating_sensor.strip()
                    if isinstance(raw_heating_sensor, str) and raw_heating_sensor.strip()
                    else None
                )
                self.settings_data[CONF_DEFAULT_PRESET] = user_input.get(
                    CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET
                )
                self._ensure_valid_direct_presets_in_settings()
                return await self.async_step_settings()

        self._ensure_valid_direct_presets_in_settings()
        preset_selector = self._build_preset_selector(include_none=False)
        schema = vol.Schema(
            {
                vol.Required(CONF_CLIMATE_ENTITIES): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_HEATING_ACTIVE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean"])
                ),
                vol.Optional(CONF_DEFAULT_PRESET): preset_selector,
            }
        )
        return self.async_show_form(
            step_id="settings_devices",
            data_schema=self.add_suggested_values_to_schema(schema, self.settings_data),
            errors=errors,
        )

    async def async_step_settings_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Settings category 2/4: Window/door sensors and pause delays."""
        self._init_data()

        if user_input is not None:
            self.settings_data[CONF_WINDOW_SENSORS] = _normalize_entity_list(
                user_input.get(CONF_WINDOW_SENSORS)
            )
            self.settings_data[CONF_WINDOW_PAUSE_ENABLED] = bool(
                user_input.get(CONF_WINDOW_PAUSE_ENABLED, DEFAULT_WINDOW_PAUSE_ENABLED)
            )
            self.settings_data[CONF_WINDOW_OPEN_DELAY_MINUTES] = _clamp_window_delay(
                user_input.get(CONF_WINDOW_OPEN_DELAY_MINUTES),
                DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
            )
            self.settings_data[CONF_WINDOW_CLOSE_DELAY_MINUTES] = _clamp_window_delay(
                user_input.get(CONF_WINDOW_CLOSE_DELAY_MINUTES),
                DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
            )
            return await self.async_step_settings()

        schema = vol.Schema(
            {
                vol.Optional(CONF_WINDOW_SENSORS): EntitySelector(
                    EntitySelectorConfig(
                        domain="binary_sensor",
                        device_class=["window", "door"],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_WINDOW_PAUSE_ENABLED): BooleanSelector(),
                vol.Optional(CONF_WINDOW_OPEN_DELAY_MINUTES): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_WINDOW_CLOSE_DELAY_MINUTES): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="settings_windows",
            data_schema=self.add_suggested_values_to_schema(schema, self.settings_data),
        )

    async def async_step_settings_thermal(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Settings category 3/4: Weather, preheat/cooldown, self-learning & control hysteresis."""
        self._init_data()

        if user_input is not None:
            self.settings_data[CONF_OUTSIDE_TEMP_SENSOR] = user_input.get(CONF_OUTSIDE_TEMP_SENSOR)
            self.settings_data[CONF_OUTSIDE_WEATHER_ENTITY] = user_input.get(CONF_OUTSIDE_WEATHER_ENTITY)
            self.settings_data[CONF_USE_WEATHER_FORECAST_FOR_PREHEAT] = bool(
                user_input.get(
                    CONF_USE_WEATHER_FORECAST_FOR_PREHEAT,
                    DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT,
                )
            )
            self.settings_data[CONF_PREHEAT_ENABLED] = bool(
                user_input.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED)
            )
            self.settings_data[CONF_MAX_MINUTES_PREHEAT] = max(
                0,
                min(
                    720,
                    int(
                        round(
                            _safe_float(
                                user_input.get(CONF_MAX_MINUTES_PREHEAT),
                                DEFAULT_MAX_MINUTES_PREHEAT,
                                allow_zero_or_negative=True,
                            )
                        )
                    ),
                ),
            )
            self.settings_data[CONF_COOLDOWN_ENABLED] = bool(
                user_input.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED)
            )
            self.settings_data[CONF_MAX_MINUTES_COOLDOWN] = max(
                0,
                min(
                    720,
                    int(
                        round(
                            _safe_float(
                                user_input.get(CONF_MAX_MINUTES_COOLDOWN),
                                DEFAULT_MAX_MINUTES_COOLDOWN,
                                allow_zero_or_negative=True,
                            )
                        )
                    ),
                ),
            )
            self.settings_data[CONF_ENABLE_SELF_LEARNING] = bool(
                user_input.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING)
            )
            self.settings_data[CONF_FALLBACK_HEATING_RATE] = _safe_float(
                user_input.get(CONF_FALLBACK_HEATING_RATE), DEFAULT_FALLBACK_HEATING_RATE
            )
            self.settings_data[CONF_FALLBACK_COOLING_RATE] = _safe_float(
                user_input.get(CONF_FALLBACK_COOLING_RATE), DEFAULT_FALLBACK_COOLING_RATE
            )
            self.settings_data[CONF_HVAC_OFF_ON_TARGET] = bool(
                user_input.get(CONF_HVAC_OFF_ON_TARGET, DEFAULT_HVAC_OFF_ON_TARGET)
            )
            self.settings_data[CONF_FALLBACK_TOLERANCE] = max(
                0.0,
                _safe_float(
                    user_input.get(CONF_FALLBACK_TOLERANCE),
                    DEFAULT_FALLBACK_TOLERANCE,
                    allow_zero_or_negative=True,
                ),
            )
            self.settings_data[CONF_OPPORTUNISTIC_HEATING] = bool(
                user_input.get(CONF_OPPORTUNISTIC_HEATING, DEFAULT_OPPORTUNISTIC_HEATING)
            )
            return await self.async_step_settings()

        schema = vol.Schema(
            {
                vol.Optional(CONF_OUTSIDE_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_OUTSIDE_WEATHER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(CONF_USE_WEATHER_FORECAST_FOR_PREHEAT): BooleanSelector(),
                vol.Optional(CONF_PREHEAT_ENABLED): BooleanSelector(),
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
                vol.Optional(CONF_HVAC_OFF_ON_TARGET): BooleanSelector(),
                vol.Optional(CONF_FALLBACK_TOLERANCE): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0, max=2.0, step=0.05, unit_of_measurement="K", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_OPPORTUNISTIC_HEATING): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="settings_thermal",
            data_schema=self.add_suggested_values_to_schema(schema, self.settings_data),
        )

    async def async_step_settings_presence(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Settings category 4/4: Presence zones, away presets & anomaly guard."""
        self._init_data()

        if user_input is not None:
            self.settings_data[CONF_ZONE_HOME_ENTITY] = user_input.get(
                CONF_ZONE_HOME_ENTITY, "zone.home"
            )
            self.settings_data[CONF_ZONE_AWAY_NEAR_ENTITY] = user_input.get(
                CONF_ZONE_AWAY_NEAR_ENTITY
            )
            self.settings_data[CONF_NEAR_DISTANCE] = max(
                0.0,
                _safe_float(
                    user_input.get(CONF_NEAR_DISTANCE),
                    DEFAULT_NEAR_DISTANCE,
                    allow_zero_or_negative=True,
                ),
            )
            self.settings_data[CONF_AWAY_NEAR_PRESET] = user_input.get(
                CONF_AWAY_NEAR_PRESET, DEFAULT_AWAY_NEAR_PRESET
            )
            self.settings_data[CONF_AWAY_PRESET] = user_input.get(
                CONF_AWAY_PRESET, DEFAULT_AWAY_PRESET
            )
            self._ensure_valid_direct_presets_in_settings()
            self.settings_data[CONF_PREHEAT_IGNORES_AWAY] = bool(
                user_input.get(CONF_PREHEAT_IGNORES_AWAY, DEFAULT_PREHEAT_IGNORES_AWAY)
            )
            self.settings_data[CONF_ANOMALY_DETECTION_ENABLED] = bool(
                user_input.get(CONF_ANOMALY_DETECTION_ENABLED, DEFAULT_ANOMALY_DETECTION_ENABLED)
            )
            raw_anom_mins = user_input.get(CONF_ANOMALY_NO_HEAT_MINUTES)
            if raw_anom_mins is None:
                anom_mins = DEFAULT_ANOMALY_NO_HEAT_MINUTES
            else:
                try:
                    anom_mins = max(0, min(240, int(round(float(raw_anom_mins)))))
                except (ValueError, TypeError):
                    anom_mins = DEFAULT_ANOMALY_NO_HEAT_MINUTES
            self.settings_data[CONF_ANOMALY_NO_HEAT_MINUTES] = anom_mins
            return await self.async_step_settings()

        self._ensure_valid_direct_presets_in_settings()
        preset_selector = self._build_preset_selector(include_none=False)
        schema = vol.Schema(
            {
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
                vol.Optional(CONF_AWAY_NEAR_PRESET): preset_selector,
                vol.Optional(CONF_AWAY_PRESET): preset_selector,
                vol.Optional(CONF_PREHEAT_IGNORES_AWAY): BooleanSelector(),
                vol.Optional(CONF_ANOMALY_DETECTION_ENABLED): BooleanSelector(),
                vol.Optional(CONF_ANOMALY_NO_HEAT_MINUTES): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=240, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="settings_presence",
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
        custom_labels = self._custom_labels()
        if slots:
            slot_lines = [
                f"• {_format_slot_item_with_flags(idx, s, lang, custom_labels=custom_labels)}"
                for idx, s in enumerate(slots)
            ]
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
        custom_labels = self._custom_labels()
        options = [
            {
                "value": f"slot_{idx}",
                "label": _format_slot_item_with_flags(idx, slot, lang, custom_labels=custom_labels),
            }
            for idx, slot in enumerate(slots)
        ]

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
                    "preheat": bool(user_input.get("preheat", True)),
                    "cooldown": bool(user_input.get("cooldown", True)),
                }

                day_slots = list(self.current_schedule.get(self.selected_day, []))
                day_slots.append(slot_data)
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

        supported_presets = self._get_supported_presets()
        default_preset = supported_presets[0] if supported_presets else "none"
        preset_selector = self._build_preset_selector(include_none=True)

        schema = vol.Schema(
            {
                vol.Required("start_time"): TimeSelector(),
                vol.Required("end_time"): TimeSelector(),
                vol.Required("preset", default=default_preset): preset_selector,
                vol.Optional("preheat", default=True): BooleanSelector(),
                vol.Optional("cooldown", default=True): BooleanSelector(),
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
                    "preheat": bool(user_input.get("preheat", True)),
                    "cooldown": bool(user_input.get("cooldown", True)),
                }

                day_slots[self.selected_slot_index] = updated_slot
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

        supported_presets = self._get_supported_presets()
        raw_preset = current_slot.get("preset") or "none"
        if raw_preset != "none" and raw_preset not in supported_presets:
            current_preset = supported_presets[0] if supported_presets else "none"
        else:
            current_preset = raw_preset or (supported_presets[0] if supported_presets else "none")
        preset_selector = self._build_preset_selector(include_none=True)

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
            vol.Required("preset", default=current_preset): preset_selector,
            vol.Optional(
                "preheat", default=bool(current_slot.get("preheat", True))
            ): BooleanSelector(),
            vol.Optional(
                "cooldown", default=bool(current_slot.get("cooldown", True))
            ): BooleanSelector(),
        }

        return self.async_show_form(step_id="edit_slot", data_schema=vol.Schema(edit_schema_dict), errors=errors)
