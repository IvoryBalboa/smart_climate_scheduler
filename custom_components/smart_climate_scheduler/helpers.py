"""Zentrale Hilfs-, Geräte- und Matrix-Funktionen für den Smart Climate Scheduler (Version 2.3.5)."""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, time
from typing import Any
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_COOLDOWN_ENABLED,
    CONF_ENABLE_SELF_LEARNING,
    CONF_PREHEAT_ENABLED,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_PREHEAT_ENABLED,
    DOMAIN,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

MAX_MATRIX_ADJUSTMENT_RATIO = 0.15  # Maximal ±15% Korrektur pro Lernschritt


def parse_time(time_str: str | None) -> time | None:
    """Wandelt einen Zeit-String im Format HH:MM:SS oder HH:MM in ein time-Objekt um."""
    if not time_str:
        return None
    try:
        parts = [int(p) for p in str(time_str).split(":")]
        if len(parts) == 2:
            return time(parts[0], parts[1])
        elif len(parts) == 3:
            return time(parts[0], parts[1], parts[2])
    except (ValueError, AttributeError, IndexError):
        pass
    return None


def safe_float(
    val: Any,
    default: float = 1.0,
    allow_zero_or_negative: bool = False,
) -> float:
    """Sicheres Parsen von Float-Werten mit Schutz vor None, Leerstrings, NaN und Inf."""
    if val is None or val == "":
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        if not allow_zero_or_negative and f <= 0:
            return default
        return round(f, 3)
    except (ValueError, TypeError):
        return default


def get_config_entry_slug(config_entry) -> str:
    name = (
        (config_entry.data.get("name") or config_entry.data.get("room_name"))
        if hasattr(config_entry, "data") and isinstance(config_entry.data, dict)
        else None
    ) or getattr(config_entry, "title", None) or "thermostat"
    try:
        from homeassistant.util import slugify
        return slugify(name)
    except Exception:
        import re
        return re.sub(r"[^\w]+", "_", str(name).lower().strip()).strip("_") or "thermostat"


ENTITY_SLUG_SUFFIXES: dict[str, dict[str, str]] = {
    # Switches
    "automatic": {
        "de": "automatik",
        "en": "auto",
        "es": "automatico",
        "fr": "automatique",
        "it": "automatico",
        "nl": "automatisch",
        "pl": "automatyczny",
    },
    "self_learning": {
        "de": "adaptives_lernen",
        "en": "self_learning",
        "es": "aprendizaje_adaptativo",
        "fr": "apprentissage_adaptatif",
        "it": "apprendimento_adattivo",
        "nl": "zelflerend",
        "pl": "samouczenie",
    },
    "preheat": {
        "de": "vorheizen",
        "en": "preheat",
        "es": "precalentamiento",
        "fr": "prechauffage",
        "it": "preriscaldamento",
        "nl": "voorverwarmen",
        "pl": "wstepne_nagrzewanie",
    },
    "cooldown": {
        "de": "auskuehlen",
        "en": "cooldown",
        "es": "enfriamiento",
        "fr": "refroidissement",
        "it": "raffreddamento",
        "nl": "afkoelen",
        "pl": "ochladzanie",
    },
    "hvac_off_on_target": {
        "de": "abschaltung_bei_zieltemperatur",
        "en": "turn_off_at_target",
        "es": "apagar_en_temperatura_objetivo",
        "fr": "arret_temperature_cible",
        "it": "spegni_alla_temperatura_desiderata",
        "nl": "uitschakelen_bij_doeltemperatuur",
        "pl": "wylacz_przy_temp_docelowej",
    },
    "opportunistic_heating": {
        "de": "opportunistisches_mitheizen",
        "en": "opportunistic_heating",
        "es": "calefaccion_oportunista",
        "fr": "chauffage_opportuniste",
        "it": "riscaldamento_opportunistico",
        "nl": "opportunistische_verwarming",
        "pl": "ogrzewanie_oportunistyczne",
    },
    "weather_forecast_preheat": {
        "de": "wettervorhersage_vorheizen",
        "en": "weather_forecast_preheat",
        "es": "pronostico_tiempo_precalentamiento",
        "fr": "previsions_meteo_prechauffage",
        "it": "previsioni_meteo_preriscaldamento",
        "nl": "weersverwachting_voorverwarmen",
        "pl": "prognoza_pogody_nagrzewanie",
    },
    "preheat_ignores_away": {
        "de": "vorheizen_bei_abwesenheit",
        "en": "preheat_ignores_away",
        "es": "precalentamiento_en_ausencia",
        "fr": "prechauffage_en_absence",
        "it": "preriscaldamento_in_assenza",
        "nl": "voorverwarmen_bij_afwezigheid",
        "pl": "nagrzewanie_podczas_nieobecnosci",
    },
    # Sensors
    "schedule": {
        "de": "zeitplan",
        "en": "schedule",
        "es": "horario",
        "fr": "programme",
        "it": "programma",
        "nl": "schema",
        "pl": "harmonogram",
    },
    "heating_rate": {
        "de": "aufheizrate",
        "en": "heating_rate",
        "es": "tasa_calentamiento",
        "fr": "taux_chauffe",
        "it": "tasso_riscaldamento",
        "nl": "opwarmsnelheid",
        "pl": "wskaznik_nagrzewania",
    },
    "cooling_rate": {
        "de": "abkuehlrate",
        "en": "cooling_rate",
        "es": "tasa_enfriamiento",
        "fr": "taux_refroidissement",
        "it": "tasso_raffreddamento",
        "nl": "afkoelsnelheid",
        "pl": "wskaznik_ochladzania",
    },
    "next_action": {
        "de": "naechste_aktion",
        "en": "next_action",
        "es": "proxima_accion",
        "fr": "action_suivante",
        "it": "prossima_azione",
        "nl": "volgende_actie",
        "pl": "nastepna_akcja",
    },
    # Binary sensors
    "binary_preheat": {
        "de": "vorheizen",
        "en": "preheat",
        "es": "precalentamiento",
        "fr": "prechauffage",
        "it": "preriscaldamento",
        "nl": "voorverwarmen",
        "pl": "wstepne_nagrzewanie",
    },
    "binary_cooldown": {
        "de": "abkuehlen",
        "en": "cooldown",
        "es": "enfriamiento",
        "fr": "refroidissement",
        "it": "raffreddamento",
        "nl": "afkoelen",
        "pl": "ochladzanie",
    },
    # Debug sensor
    "diagnostics": {
        "de": "diagnose",
        "en": "diagnostics",
        "es": "diagnostico",
        "fr": "diagnostic",
        "it": "diagnosi",
        "nl": "diagnose",
        "pl": "diagnostyka",
    },
    # Select entity
    "schedule_profile": {
        "de": "zeitplan_profil",
        "en": "schedule_profile",
        "es": "perfil_horario",
        "fr": "profil_programme",
        "it": "profilo_programma",
        "nl": "schemaprofiel",
        "pl": "profil_harmonogramu",
    },
}

# Legacy key aliases for backwards compatibility
ENTITY_SLUG_KEY_ALIASES: dict[str, str] = {
    "automatik": "automatic",
    "adaptives_lernen": "self_learning",
    "vorheizen": "preheat",
    "auskuehlen": "cooldown",
    "abschaltung_bei_zieltemperatur": "hvac_off_on_target",
    "opportunistisches_mitheizen": "opportunistic_heating",
    "wettervorhersage_vorheizen": "weather_forecast_preheat",
    "zeitplan": "schedule",
    "aufheizrate": "heating_rate",
    "abkuehlrate": "cooling_rate",
    "naechste_aktion": "next_action",
    "binary_vorheizen": "binary_preheat",
    "binary_abkuehlen": "binary_cooldown",
    "diagnose": "diagnostics",
    "zeitplan_profil": "schedule_profile",
}


def get_ha_language(hass) -> str:
    """Returns the 2-letter language code configured in Home Assistant."""
    if not hass:
        return "de"
    config = getattr(hass, "config", None)
    lang = getattr(config, "language", "de") if config else "de"
    if isinstance(lang, str) and lang:
        return lang.split("-")[0].split("_")[0].lower()
    return "de"


def get_localized_slug_suffix(key: str, lang: str = "de") -> str:
    """Returns the localized entity_id slug suffix for the given key and language."""
    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) else "de"
    canonical_key = ENTITY_SLUG_KEY_ALIASES.get(key, key)
    mapping = ENTITY_SLUG_SUFFIXES.get(canonical_key, {})
    return mapping.get(clean_lang, mapping.get("en", key))


def get_device_info(config_entry) -> DeviceInfo:
    """Erzeugt eine einheitliche DeviceInfo-Struktur für alle Entitäten eines Config Entrys."""
    name = config_entry.data.get("name", "thermostat")
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=name,
        manufacturer="Smart Climate Scheduler",
        model="Smart Climate Scheduler Hub",
        sw_version=VERSION,
    )


def get_preset_temperature(climate_state, preset_name: str | None) -> float:
    """Sucht die Zieltemperatur für ein Preset aus den Climate-Attributen heraus."""
    if not climate_state or not preset_name:
        return 20.0

    attrs = climate_state.attributes

    raw_heat_temps = attrs.get("bt_preset_heat_temperatures") or attrs.get("preset_temperatures")

    if isinstance(raw_heat_temps, str):
        try:
            raw_heat_temps = json.loads(raw_heat_temps)
        except Exception:
            raw_heat_temps = {}

    if isinstance(raw_heat_temps, dict) and preset_name in raw_heat_temps:
        try:
            return float(raw_heat_temps[preset_name])
        except (ValueError, TypeError):
            pass

    raw_cool_temps = attrs.get("bt_preset_cool_temperatures")
    if isinstance(raw_cool_temps, str):
        try:
            raw_cool_temps = json.loads(raw_cool_temps)
        except Exception:
            raw_cool_temps = {}

    if isinstance(raw_cool_temps, dict) and preset_name in raw_cool_temps:
        try:
            return float(raw_cool_temps[preset_name])
        except (ValueError, TypeError):
            pass

    attr_key = f"{preset_name}_temperature"
    if attr_key in attrs:
        try:
            return float(attrs[attr_key])
        except (ValueError, TypeError):
            pass

    defaults = {
        "comfort": 21.0,
        "home": 21.0,
        "eco": 18.0,
        "sleep": 17.0,
        "away": 15.0,
        "boost": 23.0,
        "none": 20.0,
    }
    return defaults.get(preset_name, 20.0)


def get_outside_temperature(
    hass,
    outside_sensor: str | None = None,
    outside_weather_entity: str | None = None,
) -> float | None:
    """Ermittelt die Außentemperatur: Sensor hat Vorrang vor Wetter-Entität ('temperature'-Attribut)."""
    val, _ = get_resolved_outside_info(hass, outside_sensor, outside_weather_entity)
    return val


def get_resolved_outside_info(
    hass,
    outside_sensor: str | None = None,
    outside_weather_entity: str | None = None,
) -> tuple[float | None, str | None]:
    """Ermittelt die Außentemperatur und die aktive Quell-Entität (Sensor vor Wetter-Entität)."""
    if not hass:
        return None, None

    # 1. Höchste Priorität: Direkter Sensor (Zustand ist numerisch)
    if outside_sensor:
        st = hass.states.get(outside_sensor)
        if st and st.state not in ("unavailable", "unknown", "None", None):
            try:
                return float(st.state), outside_sensor
            except (ValueError, TypeError):
                pass

    # 2. Fallback: Wetter-Entität (Nutzt das Attribut 'temperature')
    if outside_weather_entity:
        st = hass.states.get(outside_weather_entity)
        if st and st.state not in ("unavailable", "unknown", "None", None):
            temp_attr = st.attributes.get("temperature")
            if temp_attr is not None:
                try:
                    return float(temp_attr), outside_weather_entity
                except (ValueError, TypeError):
                    pass

    return None, None


def parse_datetime(dt_val: Any) -> datetime | None:
    """Parst einen ISO-8601 Zeitstempel oder datetime-Objekt."""
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    try:
        dt_str = str(dt_val)
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


async def async_get_hourly_forecast(hass, weather_entity: str | None) -> list[dict]:
    """Ermittelt die stündliche Wettervorhersage (modern per weather.get_forecasts oder Attribut)."""
    if not hass or not weather_entity:
        return []

    # Schutz vor Warning in homeassistant.helpers.service / helpers/target.py:176:
    # Service Call nur ausführen, wenn die Entität in Home Assistant registriert und verfügbar ist!
    if hasattr(hass, "states"):
        st = hass.states.get(weather_entity)
        if not st or st.state in ("unavailable", "unknown", "None", None):
            _LOGGER.debug(
                "Wetter-Entität '%s' nicht verfügbar (Status: %s) - überspringe weather.get_forecasts",
                weather_entity,
                st.state if st else "None",
            )
            return []

    forecast_items = []

    # 1. Moderner Weg: weather.get_forecasts Service Call (Home Assistant 2023.12+)
    try:
        if hasattr(hass, "services") and hass.services.has_service("weather", "get_forecasts"):
            res = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            if isinstance(res, dict) and weather_entity in res:
                raw_fc = res[weather_entity].get("forecast")
                if isinstance(raw_fc, list):
                    forecast_items = raw_fc
    except Exception as e:
        _LOGGER.debug("weather.get_forecasts Service Call fehlgeschlagen für %s: %s", weather_entity, e)

    # 2. Abwärtskompatibler Fallback: Attribut 'forecast' des Wetter-States
    if not forecast_items and hasattr(hass, "states"):
        st = hass.states.get(weather_entity)
        if st and isinstance(st.attributes.get("forecast"), list):
            forecast_items = st.attributes.get("forecast", [])

    parsed_forecast = []
    for item in forecast_items:
        if not isinstance(item, dict):
            continue
        dt = parse_datetime(item.get("datetime"))
        temp = item.get("temperature")
        if dt is not None and temp is not None:
            try:
                parsed_forecast.append({
                    "datetime": dt,
                    "temperature": float(temp),
                })
            except (ValueError, TypeError):
                continue

    return parsed_forecast


def get_forecast_temperature_for_window(
    forecast_list: list[dict] | None,
    window_start: datetime,
    window_end: datetime,
) -> float | None:
    """Berechnet das arithmetische Mittel der prognostizierten Außentemperaturen im Vorheiz-Zeitfenster."""
    if not forecast_list or window_start >= window_end:
        return None

    matching_temps = []
    for item in forecast_list:
        raw_dt = item.get("datetime")
        temp = item.get("temperature")
        if not raw_dt or temp is None:
            continue

        dt = parse_datetime(raw_dt) if isinstance(raw_dt, str) else raw_dt
        if not isinstance(dt, datetime):
            continue

        if window_start.tzinfo and not dt.tzinfo:
            dt = dt.replace(tzinfo=window_start.tzinfo)
        elif not window_start.tzinfo and dt.tzinfo:
            dt = dt.replace(tzinfo=None)

        if window_start <= dt <= window_end:
            matching_temps.append(float(temp))

    if not matching_temps:
        mid_time = window_start + (window_end - window_start) / 2
        closest_diff = None
        closest_temp = None
        for item in forecast_list:
            raw_dt = item.get("datetime")
            temp = item.get("temperature")
            if not raw_dt or temp is None:
                continue
            dt = parse_datetime(raw_dt) if isinstance(raw_dt, str) else raw_dt
            if not isinstance(dt, datetime):
                continue
            if mid_time.tzinfo and not dt.tzinfo:
                dt = dt.replace(tzinfo=mid_time.tzinfo)
            elif not mid_time.tzinfo and dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            diff = abs((dt - mid_time).total_seconds())
            if diff <= 7200:
                if closest_diff is None or diff < closest_diff:
                    closest_diff = diff
                    closest_temp = float(temp)
        if closest_temp is not None:
            return round(closest_temp, 2)
        return None

    return round(sum(matching_temps) / len(matching_temps), 2)


# ---------------------------------------------------------------------------
# Zentrale Matrix-, EMA- & Raten-Berechnungsfunktionen (Aufheizen & Abkühlen)
# ---------------------------------------------------------------------------


def normalize_temp_key(raw_temp: Any) -> str:
    """Vereinheitlicht einen Außentemperatur-Schlüssel auf Ganzzahl-String (z. B. '5', '-2') oder 'default'."""
    if raw_temp is None or str(raw_temp).strip().lower() in ("default", "none", ""):
        return "default"
    try:
        return str(int(round(float(raw_temp))))
    except (ValueError, TypeError):
        return str(raw_temp).strip()


def normalize_matrix(raw_matrix: dict | None) -> dict[str, float]:
    """Normalisiert eine Außentemperatur-Matrix auf positive Float-Durchschnittswerte."""
    if not isinstance(raw_matrix, dict):
        return {}

    normalized: dict[str, float] = {}
    for key, val in raw_matrix.items():
        k_str = str(key)
        try:
            if isinstance(val, (int, float)):
                f_val = float(val)
                if not math.isnan(f_val) and not math.isinf(f_val) and f_val > 0:
                    normalized[k_str] = round(f_val, 3)
            elif isinstance(val, list):
                pos_vals = []
                for x in val:
                    fx = float(x)
                    if not math.isnan(fx) and not math.isinf(fx) and fx > 0:
                        pos_vals.append(fx)
                if pos_vals:
                    normalized[k_str] = round(sum(pos_vals) / len(pos_vals), 3)
        except (ValueError, TypeError):
            continue
    return normalized


def calculate_overall_average(
    matrix: dict[str, float] | None,
    fallback_rate: float = 1.0,
    already_normalized: bool = False,
) -> float:
    """Bildet aus allen Werten einer Matrix den Gesamt-Durchschnitt."""
    safe_fallback = safe_float(fallback_rate, 1.0)
    norm = matrix if (already_normalized and isinstance(matrix, dict)) else normalize_matrix(matrix)
    valid_vals = [v for v in norm.values() if isinstance(v, (int, float)) and v > 0]
    if not valid_vals:
        return round(safe_fallback, 3)
    return round(sum(valid_vals) / len(valid_vals), 3)


def update_matrix_with_rate(
    matrix: dict | None,
    outside_temp: float | None,
    rate: float,
    fallback_rate: float = 1.0,
    max_adjustment_ratio: float = MAX_MATRIX_ADJUSTMENT_RATIO,
) -> tuple[dict[str, float], float, float]:
    """Ordnet einen gemessenen Ratenwert der Außentemperatur-Matrix zu (max. ±5% Korrektur)."""
    norm_matrix = normalize_matrix(matrix)
    safe_fallback = safe_float(fallback_rate, 1.0)

    try:
        rate_val = float(rate)
    except (ValueError, TypeError):
        rate_val = 0.0

    if math.isnan(rate_val) or rate_val <= 0:
        overall = calculate_overall_average(norm_matrix, safe_fallback, already_normalized=True)
        return norm_matrix, 0.0, overall

    bucket_key = normalize_temp_key(outside_temp)

    if bucket_key in norm_matrix and norm_matrix[bucket_key] > 0:
        old_avg = norm_matrix[bucket_key]
        min_allowed = old_avg * (1.0 - max_adjustment_ratio)
        max_allowed = old_avg * (1.0 + max_adjustment_ratio)
        candidate_avg = (old_avg + rate_val) / 2.0

        if rate_val >= max_allowed:
            new_bucket_avg = round(max_allowed, 3)
        elif rate_val <= min_allowed:
            new_bucket_avg = round(min_allowed, 3)
        else:
            new_bucket_avg = round(max(min_allowed, min(max_allowed, candidate_avg)), 3)
    else:
        new_bucket_avg = round(rate_val, 3)

    norm_matrix[bucket_key] = new_bucket_avg
    overall_avg = calculate_overall_average(norm_matrix, safe_fallback, already_normalized=True)
    return norm_matrix, new_bucket_avg, overall_avg


def apply_ema(new_rate: float, current_ema: float | None, alpha: float = 0.35) -> float:
    """Glättet einen Ratenwert mit exponentiellem gleitendem Durchschnitt (EMA)."""
    if current_ema is None or current_ema <= 0:
        return round(new_rate, 3)
    smoothed = (alpha * new_rate) + ((1.0 - alpha) * current_ema)
    return round(smoothed, 3)


def get_effective_rate(
    entry_data: dict,
    outside_temp: float | None,
    fallback_rate: float = 1.0,
    learning_enabled: bool = True,
    matrix_key: str = "averages",
    avg_key: str = "average",
) -> float:
    """Ermittelt die geltende Rate (Matrix-Wert mit stetiger linearer Interpolation, Ausreißer-Dämpfung und festen Plausibilitätsgrenzen)."""
    is_cooling = (matrix_key == "cooling_averages")
    safe_fallback = safe_float(fallback_rate, 0.2 if is_cooling else 1.0)
    if not learning_enabled:
        return round(safe_fallback, 3)

    raw_matrix = entry_data.get(matrix_key, {})
    matrix = raw_matrix if isinstance(raw_matrix, dict) else {}

    # Numerische Buckets für stetige Interpolation aufbereiten
    numeric_buckets: dict[int, float] = {}
    for k, v in matrix.items():
        try:
            if isinstance(v, (int, float)) and v > 0 and not math.isnan(v):
                numeric_buckets[int(round(float(k)))] = float(v)
        except (ValueError, TypeError):
            continue

    # Wenn die Matrix noch komplett leer ist (Kaltstart vor allererster Messung), Fallback nutzen
    if not numeric_buckets and not matrix.get("default"):
        return round(safe_fallback, 3)

    # Globaler Referenzwert rein aus gelernten Daten berechnen (ohne Fallback-Verfälschung)
    stored_avg = entry_data.get(avg_key)
    if isinstance(stored_avg, (int, float)) and stored_avg > 0 and not math.isnan(stored_avg):
        global_avg = float(stored_avg)
    elif numeric_buckets:
        global_avg = sum(numeric_buckets.values()) / float(len(numeric_buckets))
    else:
        computed_avg = calculate_overall_average(matrix, safe_fallback, already_normalized=True)
        global_avg = computed_avg if computed_avg > 0 else safe_fallback

    local_rate: float | None = None

    if outside_temp is not None and numeric_buckets:
        try:
            t_out = float(outside_temp)
            sorted_keys = sorted(numeric_buckets.keys())

            if t_out <= sorted_keys[0]:
                local_rate = numeric_buckets[sorted_keys[0]]
            elif t_out >= sorted_keys[-1]:
                local_rate = numeric_buckets[sorted_keys[-1]]
            else:
                # Stetige lineare Interpolation zwischen den zwei nächstliegenden Stützpunkten
                k_low = max(k for k in sorted_keys if k <= t_out)
                k_high = min(k for k in sorted_keys if k >= t_out)
                if k_low == k_high:
                    local_rate = numeric_buckets[k_low]
                else:
                    weight = (t_out - k_low) / float(k_high - k_low)
                    local_rate = (1.0 - weight) * numeric_buckets[k_low] + weight * numeric_buckets[k_high]
        except (ValueError, TypeError):
            pass

    # Falls Außentemperatur nicht zuordenbar, 'default' oder Gesamtmittelwert nutzen
    if local_rate is None or local_rate <= 0:
        default_val = matrix.get("default")
        if isinstance(default_val, (int, float)) and default_val > 0:
            local_rate = float(default_val)
        else:
            local_rate = global_avg

    # Ausreißer-Schutz und Glättung:
    # Weicht ein einzelner Bucket drastisch (>40%) nach unten vom Gesamt-Durchschnitt ab,
    # wird er mit dem Gesamtschnitt stabilisiert
    if global_avg > 0:
        if not is_cooling:
            if local_rate < 0.6 * global_avg:
                local_rate = 0.5 * local_rate + 0.5 * global_avg
            elif local_rate > 2.5 * global_avg:
                local_rate = 0.6 * local_rate + 0.4 * global_avg
        else:
            if local_rate < 0.5 * global_avg:
                local_rate = 0.5 * local_rate + 0.5 * global_avg
            elif local_rate > 2.5 * global_avg:
                local_rate = 0.6 * local_rate + 0.4 * global_avg

    # Feste physikalische Plausibilitätsgrenzen (unabhängig von der Fallback-Rate)
    if is_cooling:
        min_floor = 0.02
        max_cap = 1.50
    else:
        min_floor = 0.10
        max_cap = 3.00

    clamped_rate = max(min_floor, min(max_cap, local_rate))
    return round(clamped_rate, 3)


async def async_set_matrix_entry(
    store: dict,
    raw_temp: Any,
    raw_rate: Any,
    fallback_rate: float,
    is_cooling: bool = False,
) -> tuple[str, float, float]:
    """Setzt oder aktualisiert einen Eintrag in der Aufheiz- oder Abkühl-Matrix inkl. Persistenz."""
    temp_key = normalize_temp_key(raw_temp)
    min_r, max_r, def_r = (0.01, 2.0, 0.2) if is_cooling else (0.05, 5.0, 1.0)
    matrix_key = "cooling_averages" if is_cooling else "averages"
    avg_key = "cooling_average" if is_cooling else "average"

    clamped_rate = round(max(min_r, min(max_r, safe_float(raw_rate, def_r))), 3)
    averages = dict(store.get(matrix_key, {}))
    averages[temp_key] = clamped_rate
    store[matrix_key] = averages

    overall_avg = calculate_overall_average(averages, fallback_rate, already_normalized=True)
    store[avg_key] = overall_avg

    storage = store.get("storage")
    if storage:
        await storage.async_save_data({
            matrix_key: averages,
            avg_key: overall_avg,
        })

    return temp_key, clamped_rate, overall_avg


async def async_delete_matrix_entry(
    store: dict,
    raw_temp: Any,
    fallback_rate: float,
    is_cooling: bool = False,
) -> tuple[str, float | None]:
    """Entfernt einen Eintrag aus der Aufheiz- oder Abkühl-Matrix inkl. Persistenz."""
    temp_key = normalize_temp_key(raw_temp)
    matrix_key = "cooling_averages" if is_cooling else "averages"
    avg_key = "cooling_average" if is_cooling else "average"

    averages = dict(store.get(matrix_key, {}))
    if temp_key not in averages:
        return temp_key, None

    averages.pop(temp_key)
    store[matrix_key] = averages

    overall_avg = calculate_overall_average(averages, fallback_rate, already_normalized=True)
    store[avg_key] = overall_avg

    storage = store.get("storage")
    if storage:
        await storage.async_save_data({
            matrix_key: averages,
            avg_key: overall_avg,
        })

    return temp_key, overall_avg


def get_target_hvac_mode(climate_state: Any) -> str:
    """Ermittelt den passenden Heiz-Modus für ein Climate Entity (heat, auto, etc.)."""
    if not climate_state:
        return "heat"
    attrs = getattr(climate_state, "attributes", None) or {}
    supported_modes = attrs.get("hvac_modes") or []
    if "heat" in supported_modes:
        return "heat"
    if "auto" in supported_modes:
        return "auto"
    if "heat_cool" in supported_modes:
        return "heat_cool"
    return "heat"


async def async_sync_entity_registry_disabled(hass: Any, config_entry: Any) -> None:
    """Synchronisiert den Deaktiviert-Status in der Entity Registry basierend auf den Optionen."""
    if not hass or not config_entry:
        return
    try:
        from homeassistant.helpers import entity_registry as er
        ent_reg = er.async_get(hass)

        def _sync_entity(domain_plat: str, unique_id: str, is_active: bool) -> None:
            ent_id = ent_reg.async_get_entity_id(domain_plat, DOMAIN, unique_id)
            if not ent_id:
                return
            reg_entry = ent_reg.async_get(ent_id)
            if not reg_entry:
                return
            if not is_active and not reg_entry.disabled:
                ent_reg.async_update_entity(ent_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
                _LOGGER.info("Sensor '%s' in Entity Registry deaktiviert (Option ausgeschaltet).", ent_id)
            elif is_active and reg_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                ent_reg.async_update_entity(ent_id, disabled_by=None)
                _LOGGER.info("Sensor '%s' in Entity Registry reaktiviert (Option eingeschaltet).", ent_id)

        # 1. Vorheizen (binary_sensor.<entry_id>_preheat)
        preheat_on = bool(
            config_entry.options.get(
                CONF_PREHEAT_ENABLED,
                config_entry.data.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED),
            )
        )
        _sync_entity("binary_sensor", f"{config_entry.entry_id}_preheat", preheat_on)

        # 2. Auskühlen (binary_sensor.<entry_id>_cooldown)
        cooldown_on = bool(
            config_entry.options.get(
                CONF_COOLDOWN_ENABLED,
                config_entry.data.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED),
            )
        )
        _sync_entity("binary_sensor", f"{config_entry.entry_id}_cooldown", cooldown_on)

        # 3. Selbstlernen (sensor.<entry_id>_heating_rate, sensor.<entry_id>_cooling_rate)
        learning_on = bool(
            config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )
        _sync_entity("sensor", f"{config_entry.entry_id}_heating_rate", learning_on)
        _sync_entity("sensor", f"{config_entry.entry_id}_cooling_rate", learning_on)
    except Exception as err:
        _LOGGER.debug("Fehler beim Synchronisieren der Entity-Registry Deaktivierung: %s", err)


async def async_sync_device_registry_version(hass: Any, config_entry: Any) -> str:
    """Synchronisiert die Firmware-Anzeige (sw_version) in der Home Assistant Device Registry direkt mit manifest.json."""
    live_version = VERSION
    if not hass or not config_entry:
        return live_version

    try:
        from homeassistant.loader import async_get_integration
        integration = await async_get_integration(hass, DOMAIN)
        if integration and getattr(integration, "version", None):
            live_version = str(integration.version)
    except Exception:
        live_version = VERSION

    try:
        from homeassistant.helpers import device_registry as dr
        dev_reg = dr.async_get(hass)
        if dev_reg:
            devices_to_check: list[Any] = []
            if hasattr(dr, "async_entries_for_config_entry"):
                entries = dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id)
                if isinstance(entries, (list, tuple, set)):
                    devices_to_check.extend(entries)
            if not devices_to_check and hasattr(dev_reg, "async_get_device_by_identifier"):
                dev = dev_reg.async_get_device_by_identifier((DOMAIN, config_entry.entry_id))
                if dev:
                    devices_to_check.append(dev)

            target_ident = (DOMAIN, config_entry.entry_id)
            for device in devices_to_check:
                idents = getattr(device, "identifiers", None) or set()
                if not idents or target_ident in idents:
                    if getattr(device, "sw_version", None) != live_version:
                        dev_reg.async_update_device(
                            device.id,
                            sw_version=live_version,
                            manufacturer="Smart Climate Scheduler",
                            model="Smart Climate Scheduler Hub",
                        )
    except Exception as err:
        _LOGGER.debug("Fehler beim Synchronisieren der Device-Registry Version: %s", err)

    return live_version


def get_profiles_and_active(config_entry: Any) -> tuple[dict[str, dict[str, list[dict]]], str]:
    """Extrahiert alle Zeitplan-Profile und den Namen des aktiven Profils (mit automatischer Migration von 'schedule')."""
    if not config_entry:
        return {"Standard": {}}, "Standard"

    options = getattr(config_entry, "options", {}) or {}
    data = getattr(config_entry, "data", {}) or {}

    raw_profiles = options.get("profiles") or data.get("profiles")
    if isinstance(raw_profiles, dict) and raw_profiles:
        profiles = {str(k): (v if isinstance(v, dict) else {}) for k, v in raw_profiles.items()}
    else:
        # Fallback / Migration: Einzelzeitplan 'schedule' wird als 'Standard'-Profil übernommen
        legacy_schedule = options.get("schedule") or data.get("schedule") or {}
        profiles = {"Standard": legacy_schedule if isinstance(legacy_schedule, dict) else {}}

    if not profiles:
        profiles = {"Standard": {}}

    active_profile = options.get("active_profile") or data.get("active_profile") or "Standard"
    if active_profile not in profiles:
        active_profile = list(profiles.keys())[0]

    return profiles, str(active_profile)


def async_write_ha_state_if_enabled(entity: Any) -> None:
    """Schreibt den Zustand der Entität nur dann, wenn sie existiert, hass hat und NICHT deaktiviert ist."""
    if entity is None:
        return
    if getattr(entity, "hass", None) is None:
        return
    # In Home Assistant ist `entity.enabled` False, wenn die Entität in der Entity Registry deaktiviert ist.
    if getattr(entity, "enabled", True) is False:
        return
    entity.async_write_ha_state()

