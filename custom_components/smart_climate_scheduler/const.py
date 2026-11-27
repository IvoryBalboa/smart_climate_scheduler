"""Konstanten für den Smart Climate Scheduler (Version 4.0.0)."""
from __future__ import annotations

DOMAIN = "smart_climate_scheduler"
VERSION = "4.0.0"

CONF_CLIMATE_ENTITY = "climate_entity"
CONF_CLIMATE_ENTITIES = "climate_entities"
CONF_CUSTOM_PRESETS = "custom_presets"
CONF_ROOM_TEMP_SENSOR = "room_temp_sensor"
CONF_WINDOW_SENSORS = "window_sensors"
CONF_WINDOW_OPEN_DELAY_MINUTES = "window_open_delay_minutes"
CONF_WINDOW_CLOSE_DELAY_MINUTES = "window_close_delay_minutes"
CONF_WINDOW_PAUSE_ENABLED = "window_pause_enabled"
CONF_ZONE_HOME_ENTITY = "zone_home_entity"
CONF_ZONE_AWAY_NEAR_ENTITY = "zone_away_near_entity"
CONF_NEAR_DISTANCE = "near_distance"
CONF_DEFAULT_PRESET = "default_preset"
CONF_MAX_MINUTES_PREHEAT = "max_minutes_preheat"
CONF_MAX_MINUTES_COOLDOWN = "max_minutes_cooldown"
CONF_PREHEAT_ENABLED = "preheat_enabled"
CONF_COOLDOWN_ENABLED = "cooldown_enabled"
CONF_ENABLE_SELF_LEARNING = "enable_self_learning"

# Außentemperatur-Quellen, Brenner-Sensor & Standard-Raten
CONF_OUTSIDE_TEMP_SENSOR = "outside_temp_sensor"
CONF_OUTSIDE_WEATHER_ENTITY = "outside_weather_entity"
CONF_HEATING_ACTIVE_SENSOR = "heating_active_sensor"
CONF_FALLBACK_HEATING_RATE = "fallback_heating_rate"
CONF_FALLBACK_COOLING_RATE = "fallback_cooling_rate"
CONF_HVAC_OFF_ON_TARGET = "hvac_off_on_target"
CONF_FALLBACK_TOLERANCE = "fallback_tolerance"
CONF_OPPORTUNISTIC_HEATING = "opportunistic_heating"
CONF_USE_WEATHER_FORECAST_FOR_PREHEAT = "use_weather_forecast_for_preheat"
CONF_PREHEAT_IGNORES_AWAY = "preheat_ignores_away"
CONF_AWAY_PRESET = "away_preset"
CONF_AWAY_NEAR_PRESET = "away_near_preset"
CONF_ANOMALY_DETECTION_ENABLED = "anomaly_detection_enabled"
CONF_ANOMALY_NO_HEAT_MINUTES = "anomaly_no_heat_minutes"

DEFAULT_WINDOW_OPEN_DELAY_MINUTES = 1
DEFAULT_WINDOW_CLOSE_DELAY_MINUTES = 2
DEFAULT_WINDOW_PAUSE_ENABLED = True
MIN_TARGET_TEMP = 5.0
MAX_TARGET_TEMP = 30.0
DEFAULT_CUSTOM_PRESETS = [
    {"id": "comfort", "name": "Komfort", "temperature": 21.0, "color": "#f59e0b"},
    {"id": "home", "name": "Zuhause", "temperature": 20.5, "color": "#0ea5e9"},
    {"id": "eco", "name": "Eco", "temperature": 18.0, "color": "#10b981"},
    {"id": "sleep", "name": "Schlafen", "temperature": 17.0, "color": "#6366f1"},
    {"id": "boost", "name": "Boost", "temperature": 23.0, "color": "#ef4444"},
    {"id": "away", "name": "Abwesend", "temperature": 15.5, "color": "#64748b"},
]
CUSTOM_PRESET_COLOR_MAP = {
    "amber": "#f59e0b",
    "emerald": "#10b981",
    "indigo": "#6366f1",
    "red": "#ef4444",
    "sky": "#0ea5e9",
    "pink": "#ec4899",
    "violet": "#8b5cf6",
    "slate": "#64748b",
}
CUSTOM_PRESET_COLOR_OPTIONS = list(CUSTOM_PRESET_COLOR_MAP.keys())
CUSTOM_PRESET_HEX_TO_KEY = {v: k for k, v in CUSTOM_PRESET_COLOR_MAP.items()}
CUSTOM_PRESET_PALETTE = list(CUSTOM_PRESET_COLOR_MAP.values())

DEFAULT_FALLBACK_PRESET = "eco"
DEFAULT_AWAY_PRESET = "away"
DEFAULT_AWAY_NEAR_PRESET = "eco"
DEFAULT_MAX_MINUTES_PREHEAT = 240
DEFAULT_MAX_MINUTES_COOLDOWN = 120
DEFAULT_NEAR_DISTANCE = 0.5
DEFAULT_PREHEAT_ENABLED = True
DEFAULT_COOLDOWN_ENABLED = True
DEFAULT_ENABLE_SELF_LEARNING = True
DEFAULT_HVAC_OFF_ON_TARGET = False
DEFAULT_FALLBACK_TOLERANCE = 0.3
DEFAULT_OPPORTUNISTIC_HEATING = False
DEFAULT_USE_WEATHER_FORECAST_FOR_PREHEAT = False
DEFAULT_PREHEAT_IGNORES_AWAY = True
DEFAULT_ANOMALY_DETECTION_ENABLED = True
DEFAULT_ANOMALY_NO_HEAT_MINUTES = 45

ANOMALY_MIN_TEMP_RISE = 0.05
ANOMALY_UNAVAILABLE_MINUTES = 5
ANOMALY_FROZEN_DEMAND_MINUTES = 180
ANOMALY_FROZEN_IDLE_MINUTES = 360

# Standard-Defaults für Aufheizrate und Verlustrate in K/h (°C/h)
DEFAULT_FALLBACK_HEATING_RATE = 1.0
DEFAULT_FALLBACK_COOLING_RATE = 0.2

# Karenzzeit nach dem Start von Home Assistant, in der verzögerte Integrationen (z. B. Zigbee-, Matter- oder Z-Wave-Thermostate)
# noch initialisieren dürfen, ohne Unverfügbarkeits-Warnungen auszulösen
STARTUP_GRACE_SECONDS = 90

DAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
