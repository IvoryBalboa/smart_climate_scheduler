"""Konstanten für den Smart Climate Scheduler (Version 2.0)."""
from __future__ import annotations

DOMAIN = "smart_climate_scheduler"
VERSION = "2.4.4"

CONF_CLIMATE_ENTITY = "climate_entity"
CONF_ZONE_HOME_ENTITY = "zone_home_entity"
CONF_ZONE_AWAY_NEAR_ENTITY = "zone_away_near_entity"
CONF_NEAR_DISTANCE = "near_distance"
CONF_DEFAULT_PRESET = "default_preset"
CONF_MAX_MINUTES_PREHEAT = "max_minutes_preheat"
CONF_MAX_MINUTES_COOLDOWN = "max_minutes_cooldown"
CONF_PREHEAT_ENABLED = "preheat_enabled"
CONF_COOLDOWN_ENABLED = "cooldown_enabled"
CONF_ENABLE_SELF_LEARNING = "enable_self_learning"

# Version 2.0: Außentemperatur-Quellen, Brenner-Sensor & Standard-Raten
CONF_OUTSIDE_TEMP_SENSOR = "outside_temp_sensor"
CONF_OUTSIDE_WEATHER_ENTITY = "outside_weather_entity"
CONF_HEATING_ACTIVE_SENSOR = "heating_active_sensor"
CONF_FALLBACK_HEATING_RATE = "fallback_heating_rate"
CONF_FALLBACK_COOLING_RATE = "fallback_cooling_rate"
CONF_HVAC_OFF_ON_TARGET = "hvac_off_on_target"
CONF_FALLBACK_TOLERANCE = "fallback_tolerance"
CONF_OPPORTUNISTIC_HEATING = "opportunistic_heating"
CONF_USE_WEATHER_FORECAST_FOR_PREHEAT = "use_weather_forecast_for_preheat"

DEFAULT_FALLBACK_PRESET = "eco"
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

# Standard-Defaults für Aufheizrate und Verlustrate in K/h (°C/h)
DEFAULT_FALLBACK_HEATING_RATE = 1.0
DEFAULT_FALLBACK_COOLING_RATE = 0.2

DAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
