"""Zentrale Hilfs-, Geräte- und Matrix-Funktionen für den Smart Climate Scheduler (Version 2.1.0)."""
from __future__ import annotations

import json
import logging
import math
from datetime import time
from typing import Any
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MAX_MATRIX_ADJUSTMENT_RATIO = 0.05  # Maximal ±5% Korrektur pro Lernschritt


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


def get_device_info(config_entry) -> DeviceInfo:
    """Erzeugt eine einheitliche DeviceInfo-Struktur für alle Entitäten eines Config Entrys."""
    name = config_entry.data.get("name", "thermostat")
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=name,
        manufacturer="Smart Climate Scheduler",
        model="Version 2.1.0",
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
    """Ermittelt die geltende Rate (Matrix-Wert mit stetiger linearer Interpolation, Ausreißer-Dämpfung und Plausibilitätsgrenzen)."""
    is_cooling = (matrix_key == "cooling_averages")
    safe_fallback = safe_float(fallback_rate, 0.2 if is_cooling else 1.0)
    if not learning_enabled:
        return round(safe_fallback, 3)

    raw_matrix = entry_data.get(matrix_key, {})
    matrix = raw_matrix if isinstance(raw_matrix, dict) else {}

    # Globaler Referenzwert (Gesamtdurchschnitt oder Fallback)
    stored_avg = entry_data.get(avg_key)
    if isinstance(stored_avg, (int, float)) and stored_avg > 0 and not math.isnan(stored_avg):
        global_avg = float(stored_avg)
    else:
        computed_avg = calculate_overall_average(matrix, safe_fallback, already_normalized=True)
        global_avg = computed_avg if computed_avg > 0 else safe_fallback

    # Numerische Buckets für stetige Interpolation aufbereiten
    numeric_buckets: dict[int, float] = {}
    for k, v in matrix.items():
        try:
            if isinstance(v, (int, float)) and v > 0 and not math.isnan(v):
                numeric_buckets[int(round(float(k)))] = float(v)
        except (ValueError, TypeError):
            continue

    local_rate: float | None = None

    if outside_temp is not None and numeric_buckets:
        try:
            t_out = float(outside_temp)
            t_low = int(math.floor(t_out))
            t_high = int(math.ceil(t_out))

            if t_low == t_high:
                if t_low in numeric_buckets:
                    local_rate = numeric_buckets[t_low]
            elif t_low in numeric_buckets and t_high in numeric_buckets:
                # Stetige lineare Interpolation zwischen benachbarten Temperaturstufen
                weight = t_out - t_low
                local_rate = (1.0 - weight) * numeric_buckets[t_low] + weight * numeric_buckets[t_high]
            elif t_low in numeric_buckets:
                local_rate = numeric_buckets[t_low]
            elif t_high in numeric_buckets:
                local_rate = numeric_buckets[t_high]
            else:
                # Nächstliegenden Bucket prüfen (innerhalb von max. 3°C Distanz)
                closest_k = min(numeric_buckets.keys(), key=lambda k: abs(k - t_out))
                if abs(closest_k - t_out) <= 3.0:
                    local_rate = numeric_buckets[closest_k]
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
    # wird er mit dem Gesamtschnitt stabilisiert, damit ein einzelner fehlerhafter Messschritt
    # (z. B. offenes Fenster oder kalter Heizkörperstart) nicht zu stundenlangen Vorheizzeiten führt.
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

    # Physikalische Plausibilitätsgrenzen
    if is_cooling:
        min_floor = max(0.02, 0.2 * safe_fallback)
        max_cap = 2.5
    else:
        min_floor = max(0.4, 0.4 * safe_fallback)
        max_cap = 5.0

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
