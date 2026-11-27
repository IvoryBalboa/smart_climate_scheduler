"""Brenner-sensitiver Anomalie- und Hardware-Wächter für Smart Climate Scheduler (v3.3.0)."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    ANOMALY_FROZEN_DEMAND_MINUTES,
    ANOMALY_FROZEN_IDLE_MINUTES,
    ANOMALY_MIN_TEMP_RISE,
    ANOMALY_UNAVAILABLE_MINUTES,
    CONF_ANOMALY_DETECTION_ENABLED,
    CONF_ANOMALY_NO_HEAT_MINUTES,
    CONF_CLIMATE_ENTITY,
    CONF_HEATING_ACTIVE_SENSOR,
    DEFAULT_ANOMALY_DETECTION_ENABLED,
    DEFAULT_ANOMALY_NO_HEAT_MINUTES,
)
from .helpers import (
    get_climate_entities,
    get_effective_window_open,
    get_group_hvac_heating,
    get_raw_window_open,
    get_room_temp_with_timestamp,
    is_in_startup_grace,
)

BURNER_ACTIVE_STATES = ("on", "true", "active", "heat", "heating")


def _get_opt(config_entry: Any, key: str, default: Any = None) -> Any:
    if not config_entry:
        return default
    opts = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}
    if key in opts and opts[key] is not None:
        return opts[key]
    if key in data and data[key] is not None:
        return data[key]
    return default


def _to_float_or_none(val: Any) -> float | None:
    if val is None or val == "" or isinstance(val, bool):
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 3)
    except (ValueError, TypeError):
        return None


def _elapsed_minutes(earlier: datetime | None, later: datetime | None) -> float:
    if not isinstance(earlier, datetime) or not isinstance(later, datetime):
        return 0.0
    try:
        e_cmp = earlier
        l_cmp = later
        if (e_cmp.tzinfo is None) != (l_cmp.tzinfo is None):
            e_cmp = e_cmp.replace(tzinfo=None)
            l_cmp = l_cmp.replace(tzinfo=None)
        diff = (l_cmp - e_cmp).total_seconds()
        return max(0.0, diff / 60.0)
    except Exception:
        return 0.0


def evaluate_and_update_anomaly(
    hass: Any,
    config_entry: Any,
    domain_data: dict[str, Any] | None,
    now_dt: datetime | None = None,
) -> dict[str, Any]:
    """Wertet Hardware- & Heiz-Anomalien über Thermostatgruppen, optionalen Raumsensor, Fenstersensoren & Brenner aus."""
    now = now_dt or dt_util.now()
    enabled = bool(_get_opt(config_entry, CONF_ANOMALY_DETECTION_ENABLED, DEFAULT_ANOMALY_DETECTION_ENABLED))

    raw_threshold = _get_opt(config_entry, CONF_ANOMALY_NO_HEAT_MINUTES, DEFAULT_ANOMALY_NO_HEAT_MINUTES)
    try:
        no_heat_minutes = max(0, min(240, int(round(float(raw_threshold)))))
    except (ValueError, TypeError):
        no_heat_minutes = DEFAULT_ANOMALY_NO_HEAT_MINUTES

    climate_entities = get_climate_entities(config_entry)
    climate_entity = climate_entities[0] if climate_entities else str(_get_opt(config_entry, CONF_CLIMATE_ENTITY, "") or "").strip()
    if not climate_entities and climate_entity:
        climate_entities = [climate_entity]

    raw_burner = _get_opt(config_entry, CONF_HEATING_ACTIVE_SENSOR, None)
    heating_active_sensor = str(raw_burner).strip() if isinstance(raw_burner, str) and raw_burner.strip() else None

    tracker = domain_data.setdefault("anomaly_state", {}) if isinstance(domain_data, dict) else {}

    if not enabled:
        tracker["heating_watch_start"] = None
        tracker["heating_baseline_temp"] = None
        tracker["heating_max_temp"] = None
        tracker["unavailable_since"] = None
        tracker["frozen_since"] = None
        tracker["detected_since"] = None
        snapshot = {
            "enabled": False,
            "active": False,
            "primary_type": None,
            "anomalies": [],
            "detected_since": None,
            "no_heat_threshold_minutes": no_heat_minutes,
            "heating_watch_minutes": 0.0,
            "temp_delta": None,
            "unchanged_minutes": 0.0,
            "unavailable_threshold_minutes": ANOMALY_UNAVAILABLE_MINUTES,
            "unavailable_minutes": 0.0,
            "burner_configured": bool(heating_active_sensor),
            "burner_active": False,
            "thermostat_heating": False,
            "window_open": False,
            "climate_state": None,
            "climate_entities": climate_entities,
            "unavailable_entities": [],
        }
        tracker["snapshot"] = snapshot
        return snapshot

    states_mgr = getattr(hass, "states", None) if hass else None
    in_grace = is_in_startup_grace(hass)

    unavailable_entities: list[str] = []
    available_states: list[tuple[str, Any]] = []
    primary_state_str: str | None = None

    for idx, cl_id in enumerate(climate_entities):
        st = states_mgr.get(cl_id) if states_mgr else None
        st_str = str(getattr(st, "state", "") or "").strip().lower() if st else None
        if idx == 0:
            primary_state_str = st_str
        if st is None or st_str in ("unavailable", "unknown"):
            unavailable_entities.append(cl_id)
        else:
            available_states.append((cl_id, st))

    is_any_unavailable = bool(unavailable_entities)
    is_all_unavailable = bool(climate_entities) and len(unavailable_entities) == len(climate_entities)

    active_anomalies: list[str] = []
    thermostat_heating = False
    burner_configured = bool(heating_active_sensor)
    burner_active = False
    window_open = False
    curr_temp: float | None = None
    target_temp: float | None = None
    heating_watch_minutes = 0.0
    temp_delta: float | None = None
    unchanged_minutes = 0.0
    unavailable_minutes = 0.0

    # 1. Mindestens ein Thermostat nicht verfügbar (mit 90s-Start-Karenzzeit + Entprell-Wartezeit gegen kurze Aussetzer)
    if is_any_unavailable:
        if is_all_unavailable:
            tracker["heating_watch_start"] = None
            tracker["heating_baseline_temp"] = None
            tracker["heating_max_temp"] = None
        if not in_grace:
            if not isinstance(tracker.get("unavailable_since"), datetime):
                tracker["unavailable_since"] = now
            unavailable_minutes = _elapsed_minutes(tracker.get("unavailable_since"), now)
            if unavailable_minutes >= ANOMALY_UNAVAILABLE_MINUTES:
                active_anomalies.append("thermostat_unavailable")
        else:
            tracker["unavailable_since"] = None
    else:
        tracker["unavailable_since"] = None

    # 2. Sensorwerte & Heiz-/Brennerstatus über verfügbare Thermostate + externen Raumsensor prüfen
    if available_states or not is_all_unavailable:
        _, thermostat_heating, _ = get_group_hvac_heating(hass, climate_entities)
        curr_temp, _, temp_last_updated = get_room_temp_with_timestamp(hass, config_entry, climate_entities)

        valid_targets: list[float] = []
        for _, st in available_states:
            t_val = _to_float_or_none((getattr(st, "attributes", None) or {}).get("temperature"))
            if t_val is not None:
                valid_targets.append(t_val)
        target_temp = max(valid_targets) if valid_targets else None

        raw_win_open, _ = get_raw_window_open(hass, config_entry, climate_entities)
        eff_win_open = get_effective_window_open(domain_data, hass, config_entry)
        window_open = bool(eff_win_open or raw_win_open)

        if burner_configured and states_mgr:
            b_state = states_mgr.get(heating_active_sensor)
            b_state_str = str(getattr(b_state, "state", "") or "").strip().lower() if b_state else ""
            burner_active = b_state_str in BURNER_ACTIVE_STATES
        else:
            # Ohne separaten Brenner-Sensor folgt der Brenner-Status dem heizenden Ventil
            burner_active = thermostat_heating

        # 2a. Eingefrorener Temperatursensor (beachtet externen Raumsensor vor Thermostat-Mittelwert)
        if curr_temp is not None:
            prev_temp = tracker.get("last_temp")
            if prev_temp is None or abs(curr_temp - prev_temp) >= 0.05:
                tracker["last_temp"] = curr_temp
                tracker["last_temp_change_ts"] = now
                tracker["frozen_since"] = None
                unchanged_minutes = 0.0
            else:
                unchanged_minutes = _elapsed_minutes(tracker.get("last_temp_change_ts"), now)

            stale_updated_minutes = 0.0
            if isinstance(temp_last_updated, datetime):
                stale_updated_minutes = _elapsed_minutes(temp_last_updated, now)

            has_temp_demand = bool(
                (thermostat_heating and burner_active and not window_open)
                or (target_temp is not None and abs(target_temp - curr_temp) >= 0.5 and not window_open)
            )
            effective_stale = max(unchanged_minutes, stale_updated_minutes)
            if not in_grace and (
                stale_updated_minutes >= ANOMALY_FROZEN_DEMAND_MINUTES
                or (has_temp_demand and unchanged_minutes >= ANOMALY_FROZEN_DEMAND_MINUTES)
                or unchanged_minutes >= ANOMALY_FROZEN_IDLE_MINUTES
            ):
                if tracker.get("frozen_since") is None:
                    tracker["frozen_since"] = now
                active_anomalies.append("sensor_frozen")
                unchanged_minutes = effective_stale
        else:
            tracker["frozen_since"] = None

        # 2b. Keine Erwärmung trotz aktivem Brenner & heizendem Thermostat (und geschlossenem Fenster)
        needs_heat = target_temp is None or curr_temp is None or curr_temp < (target_temp - 0.1)
        watch_preconditions = (
            no_heat_minutes > 0
            and curr_temp is not None
            and thermostat_heating
            and burner_active
            and not window_open
            and needs_heat
        )

        if watch_preconditions:
            watch_start = tracker.get("heating_watch_start")
            if not isinstance(watch_start, datetime):
                tracker["heating_watch_start"] = now
                tracker["heating_baseline_temp"] = curr_temp
                tracker["heating_max_temp"] = curr_temp
                heating_watch_minutes = 0.0
                temp_delta = 0.0
            else:
                baseline = tracker.get("heating_baseline_temp")
                if baseline is None:
                    baseline = curr_temp
                    tracker["heating_baseline_temp"] = baseline
                rise = round(curr_temp - baseline, 2)
                if rise >= ANOMALY_MIN_TEMP_RISE:
                    # Raum erwärmt sich messbar -> Referenzfenster nachziehen
                    tracker["heating_watch_start"] = now
                    tracker["heating_baseline_temp"] = curr_temp
                    tracker["heating_max_temp"] = curr_temp
                    heating_watch_minutes = 0.0
                    temp_delta = 0.0
                else:
                    tracker["heating_max_temp"] = max(
                        tracker.get("heating_max_temp", curr_temp),
                        curr_temp,
                    )
                    heating_watch_minutes = _elapsed_minutes(watch_start, now)
                    temp_delta = rise
                    if not in_grace and heating_watch_minutes >= no_heat_minutes:
                        active_anomalies.append("no_heating_response")
        else:
            tracker["heating_watch_start"] = None
            tracker["heating_baseline_temp"] = None
            tracker["heating_max_temp"] = None
    else:
        tracker["heating_watch_start"] = None
        tracker["heating_baseline_temp"] = None
        tracker["heating_max_temp"] = None

    primary_type: str | None = None
    for candidate in ("thermostat_unavailable", "no_heating_response", "sensor_frozen"):
        if candidate in active_anomalies:
            primary_type = candidate
            break

    is_active = bool(active_anomalies)
    if is_active:
        if not isinstance(tracker.get("detected_since"), datetime):
            tracker["detected_since"] = now
    else:
        tracker["detected_since"] = None

    detected_since_dt = tracker.get("detected_since")
    snapshot = {
        "enabled": True,
        "active": is_active,
        "primary_type": primary_type,
        "anomalies": active_anomalies,
        "detected_since": detected_since_dt.isoformat() if isinstance(detected_since_dt, datetime) else None,
        "no_heat_threshold_minutes": no_heat_minutes,
        "heating_watch_minutes": round(heating_watch_minutes, 1),
        "temp_delta": temp_delta,
        "unchanged_minutes": round(unchanged_minutes, 1),
        "unavailable_threshold_minutes": ANOMALY_UNAVAILABLE_MINUTES,
        "unavailable_minutes": round(unavailable_minutes, 1),
        "burner_configured": burner_configured,
        "burner_active": burner_active,
        "thermostat_heating": thermostat_heating,
        "window_open": window_open,
        "climate_state": primary_state_str,
        "climate_entities": climate_entities,
        "unavailable_entities": unavailable_entities,
    }
    tracker["snapshot"] = snapshot
    return snapshot


def get_anomaly_snapshot(
    hass: Any,
    config_entry: Any,
    domain_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Liefert den aktuellen Anomalie-Status (nutzt gespeicherten Snapshot oder wertet frisch aus)."""
    if isinstance(domain_data, dict):
        snap = domain_data.get("anomaly_state", {}).get("snapshot")
        if isinstance(snap, dict):
            return snap
    return evaluate_and_update_anomaly(hass, config_entry, domain_data)
