"""Config Flow und Options Flow für Smart Climate Scheduler (Version 2.0)."""
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
    DOMAIN,
)
from .helpers import parse_time, safe_float as _safe_float

DEFAULT_PRESETS = ["none", "home", "away", "boost", "comfort", "eco", "sleep", "activity"]

PRESET_NAMES_DE = {
    "none": "Keins / Aus",
    "home": "Zuhause",
    "away": "Abwesend",
    "comfort": "Komfort",
    "eco": "Eco",
    "sleep": "Schlafen",
    "boost": "Boost",
    "activity": "Aktivität",
}


def _get_slot_preset(slot: dict) -> str:
    """Extrahiert den Preset-Namen mit Fallback 'none'."""
    if "preset" in slot and slot["preset"]:
        return slot["preset"]
    if "data" in slot and isinstance(slot["data"], dict):
        return slot["data"].get("preset", "none")
    return "none"


def _normalize_schedule(raw_schedule: dict | None) -> dict[str, list[dict]]:
    """Normalisiert den Zeitplan in eine einheitliche Struktur."""
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
    """Handhabt den Erstellungsprozess der Integration (Version 2.0)."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ersteinrichtung des Integrationseintrags."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get("name", "").strip()
            if not name:
                errors["base"] = "name_required"
            else:
                unique_id = name.lower().replace(" ", "_")
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Sichere Standardwerte für Raten & Lernen
                user_input[CONF_FALLBACK_HEATING_RATE] = _safe_float(
                    user_input.get(CONF_FALLBACK_HEATING_RATE), DEFAULT_FALLBACK_HEATING_RATE
                )
                user_input[CONF_FALLBACK_COOLING_RATE] = _safe_float(
                    user_input.get(CONF_FALLBACK_COOLING_RATE), DEFAULT_FALLBACK_COOLING_RATE
                )
                user_input[CONF_ENABLE_SELF_LEARNING] = bool(
                    user_input.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING)
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
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Erstellt den Options Flow Handler."""
        return SmartClimateSchedulerOptionsFlowHandler()


class SmartClimateSchedulerOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow mit strukturiertem Hauptmenü (Version 2.0)."""

    def __init__(self) -> None:
        self.current_schedule: dict[str, list[dict]] | None = None
        self.settings_data: dict[str, Any] = {}
        self.selected_day: str = "monday"
        self.selected_slot_index: int | None = None

    def _init_data(self) -> None:
        """Lädt Zeitpläne und Einstellungen in den Zwischenspeicher."""
        if self.current_schedule is None:
            raw_schedule = self.config_entry.options.get("schedule")
            if not raw_schedule and "schedule" in self.config_entry.data:
                raw_schedule = self.config_entry.data.get("schedule", {})
            self.current_schedule = _normalize_schedule(raw_schedule)

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
        """Hauptmenü."""
        self._init_data()

        if user_input is not None:
            action = user_input.get("main_action")
            if action == "settings":
                return await self.async_step_settings()
            elif action == "schedules":
                return await self.async_step_schedule_menu()
            elif action == "save":
                new_data = dict(self.config_entry.data)
                new_data.update(self.settings_data)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                return self.async_create_entry(
                    title="",
                    data={
                        "schedule": self.current_schedule,
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
        """Einstellungen bearbeiten."""
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
            }
        )

        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(schema, self.settings_data),
        )

    async def async_step_schedule_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Wochentag auswählen."""
        self._init_data()

        if user_input is not None:
            if user_input["aktion"] == "back":
                return await self.async_step_init()
            self.selected_day = user_input["tag"]
            return await self.async_step_slot_overview()

        schema = vol.Schema(
            {
                vol.Required("aktion", default="edit"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="schedule_action",
                        options=["edit", "back"],
                    )
                ),
                vol.Required("tag", default=self.selected_day): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="day",
                        options=DAYS,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="schedule_menu", data_schema=schema)

    async def async_step_slot_overview(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Hauptmenü für den ausgewählten Wochentag (Aktionen)."""
        self._init_data()

        if user_input is not None:
            choice = user_input["slot_aktion"]
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
                vol.Required("slot_aktion", default="add"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="slot_action",
                        options=actions,
                    )
                )
            }
        )

        if slots:
            slot_lines = []
            for idx, s in enumerate(slots):
                p = s.get("preset", "none")
                p_label = PRESET_NAMES_DE.get(p, p.capitalize())
                f = s.get("from", "00:00:00")[:5]
                t = s.get("to", "00:00:00")[:5]
                slot_lines.append(f"• Slot {idx + 1}: {f} - {t} ({p_label})")
            slots_list_str = "\n" + "\n".join(slot_lines)
        else:
            slots_list_str = "\n(Keine Slots konfiguriert)"

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
        """Zeigt eine saubere Liste aller Slots eines Tages zur Auswahl an."""
        self._init_data()
        slots = self.current_schedule.get(self.selected_day, [])

        if not slots:
            return await self.async_step_slot_overview()

        if user_input is not None:
            selected_val = user_input["selected_slot"]
            if selected_val.startswith("slot_"):
                self.selected_slot_index = int(selected_val.split("_")[1])
                return await self.async_step_edit_slot()

        options = []
        for idx, slot in enumerate(slots):
            preset = slot.get("preset", "none")
            preset_label = PRESET_NAMES_DE.get(preset, preset.capitalize())
            from_t = slot.get("from", "00:00:00")
            to_t = slot.get("to", "00:00:00")
            label = f"Slot {idx + 1}: {from_t[:5]} - {to_t[:5]} ({preset_label})"
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
        """Kopiert die Slots des aktuellen Tages auf mehrere ausgewählte Wochentage."""
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
        """Slot hinzufügen mit Zeitvalidierung."""
        self._init_data()
        errors: dict[str, str] = {}

        if user_input is not None:
            start_str = user_input["startzeit"]
            end_str = user_input["endzeit"]
            start_t = parse_time(start_str)
            end_t = parse_time(end_str)

            if start_t and end_t and start_t >= end_t:
                errors["base"] = "invalid_time_range"
            else:
                day_slots = list(self.current_schedule.get(self.selected_day, []))
                day_slots.append(
                    {
                        "from": start_str,
                        "to": end_str,
                        "preset": user_input["preset"],
                    }
                )
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

        supported_presets = self._get_supported_presets()
        default_preset = supported_presets[0] if supported_presets else "none"

        schema = vol.Schema(
            {
                vol.Required("startzeit"): TimeSelector(),
                vol.Required("endzeit"): TimeSelector(),
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
        """Slot bearbeiten mit Zeitvalidierung."""
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
            if user_input["aktion"] == "delete":
                day_slots.pop(self.selected_slot_index)
                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

            start_str = user_input["startzeit"]
            end_str = user_input["endzeit"]
            start_t = parse_time(start_str)
            end_t = parse_time(end_str)

            if start_t and end_t and start_t >= end_t:
                errors["base"] = "invalid_time_range"
            else:
                day_slots[self.selected_slot_index] = {
                    "from": start_str,
                    "to": end_str,
                    "preset": user_input["preset"],
                }

                day_slots.sort(key=lambda s: s.get("from", "00:00:00"))
                self.current_schedule[self.selected_day] = day_slots
                return await self.async_step_slot_overview()

        supported_presets = self._get_supported_presets()
        current_preset = current_slot.get("preset") or (
            supported_presets[0] if supported_presets else "none"
        )

        schema = vol.Schema(
            {
                vol.Required("aktion", default="update"): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="edit_action",
                        options=["update", "delete"],
                    )
                ),
                vol.Required(
                    "startzeit", default=current_slot.get("from", "00:00:00")
                ): TimeSelector(),
                vol.Required(
                    "endzeit", default=current_slot.get("to", "00:00:00")
                ): TimeSelector(),
                vol.Required("preset", default=current_preset): SelectSelector(
                    SelectSelectorConfig(
                        translation_key="preset",
                        options=supported_presets,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="edit_slot", data_schema=schema, errors=errors)
